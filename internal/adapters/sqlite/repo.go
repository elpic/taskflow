package sqlite

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/elpic/taskflow/internal/domain"
)

// Repository implements domain.TaskRepository and app.AnalyticsRepository using SQLite.
type Repository struct {
	db *sql.DB
}

// NewRepository creates a new SQLite repository.
func NewRepository(db *sql.DB) *Repository {
	return &Repository{db: db}
}

// nowUTC returns the current time in Python-compatible isoformat.
func nowUTC() string {
	return time.Now().UTC().Format("2006-01-02T15:04:05.999999-07:00")
}

// newID returns a new 8-character task ID.
func newID() string {
	return uuid.NewString()[:8]
}

// CreateTask creates a new task and returns it.
func (r *Repository) CreateTask(
	name, description string,
	parentID *string,
	verificationCriteria *string,
	metadata map[string]any,
	idempotencyKey *string,
) (*domain.Task, error) {
	taskID := newID()
	now := nowUTC()
	metaJSON := "{}"
	if metadata != nil {
		b, _ := json.Marshal(metadata)
		metaJSON = string(b)
	}

	if parentID != nil && *parentID != "" {
		var pid string
		err := r.db.QueryRow("SELECT id FROM tasks WHERE id = ?", *parentID).Scan(&pid)
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("parent task '%s' not found", *parentID)
		}
		if err != nil {
			return nil, fmt.Errorf("checking parent: %w", err)
		}
	}

	_, err := r.db.Exec(
		`INSERT INTO tasks (id, name, description, status, parent_id,
           verification_criteria, metadata, created_at, idempotency_key)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		taskID, name, description, string(domain.StatusPending),
		parentID, verificationCriteria, metaJSON, now, idempotencyKey,
	)
	if err != nil {
		return nil, fmt.Errorf("inserting task: %w", err)
	}

	return r.GetTask(taskID)
}

// GetTask retrieves a task by ID.
func (r *Repository) GetTask(id string) (*domain.Task, error) {
	row := r.db.QueryRow(
		"SELECT "+selectTaskCols+" FROM tasks WHERE id = ?", id,
	)
	t, err := rowToTask(row)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return t, err
}

// GetChildren retrieves all direct children of a task.
func (r *Repository) GetChildren(parentID string) ([]*domain.Task, error) {
	rows, err := r.db.Query(
		"SELECT "+selectTaskCols+" FROM tasks WHERE parent_id = ?"+
			" ORDER BY position ASC NULLS LAST, created_at ASC",
		parentID,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanTasks(rows)
}

// GetAllTasks retrieves all tasks ordered by creation time.
func (r *Repository) GetAllTasks() ([]*domain.Task, error) {
	rows, err := r.db.Query("SELECT " + selectTaskCols + " FROM tasks ORDER BY created_at")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanTasks(rows)
}

// SearchTasks searches tasks by name or description.
func (r *Repository) SearchTasks(query string) ([]*domain.Task, error) {
	pattern := "%" + query + "%"
	rows, err := r.db.Query(
		"SELECT "+selectTaskCols+" FROM tasks"+
			" WHERE name LIKE ? COLLATE NOCASE"+
			" OR description LIKE ? COLLATE NOCASE"+
			" ORDER BY created_at",
		pattern, pattern,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanTasks(rows)
}

// GetTasksFiltered retrieves tasks with optional status and parent_id filters.
func (r *Repository) GetTasksFiltered(status *string, parentID *string) ([]*domain.Task, error) {
	var conditions []string
	var params []any

	if status != nil {
		conditions = append(conditions, "status = ?")
		params = append(params, *status)
	}
	if parentID != nil {
		conditions = append(conditions, "parent_id = ?")
		params = append(params, *parentID)
	}

	where := ""
	if len(conditions) > 0 {
		where = " WHERE " + strings.Join(conditions, " AND ")
	}
	q := "SELECT " + selectTaskCols + " FROM tasks" + where +
		" ORDER BY position ASC NULLS LAST, created_at ASC"

	rows, err := r.db.Query(q, params...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanTasks(rows)
}

// UpdateTask updates allowed fields of a task.
func (r *Repository) UpdateTask(id string, fields map[string]any) (*domain.Task, error) {
	allowed := map[string]bool{
		"name": true, "description": true, "status": true,
		"verification_criteria": true, "verification_result": true,
		"metadata": true, "started_at": true, "completed_at": true,
		"agent_output": true, "context_summary": true, "position": true,
	}

	var setClauses []string
	var values []any
	for k, v := range fields {
		if !allowed[k] {
			continue
		}
		setClauses = append(setClauses, k+" = ?")
		values = append(values, v)
	}

	if len(setClauses) == 0 {
		return r.GetTask(id)
	}

	values = append(values, id)
	q := "UPDATE tasks SET " + strings.Join(setClauses, ", ") + " WHERE id = ?"
	if _, err := r.db.Exec(q, values...); err != nil {
		return nil, fmt.Errorf("updating task: %w", err)
	}
	return r.GetTask(id)
}

// ResetTask resets a task to pending with cleared timing and output fields.
func (r *Repository) ResetTask(id string) error {
	_, err := r.db.Exec(
		`UPDATE tasks SET
			status = ?,
			started_at = NULL,
			completed_at = NULL,
			agent_output = NULL,
			context_summary = NULL,
			verification_result = NULL
		WHERE id = ?`,
		string(domain.StatusPending), id,
	)
	return err
}

// DeleteTask deletes a task and all its descendants (cascade via FK).
func (r *Repository) DeleteTask(id string) error {
	// Recursively collect all descendant IDs
	toDelete := []string{id}
	queue := []string{id}
	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]
		rows, err := r.db.Query("SELECT id FROM tasks WHERE parent_id = ?", current)
		if err != nil {
			return err
		}
		for rows.Next() {
			var cid string
			if err := rows.Scan(&cid); err != nil {
				rows.Close()
				return err
			}
			toDelete = append(toDelete, cid)
			queue = append(queue, cid)
		}
		rows.Close()
	}

	// Clear current_task if it's being deleted
	var currentID sql.NullString
	_ = r.db.QueryRow("SELECT task_id FROM current_task WHERE id = 1").Scan(&currentID)
	if currentID.Valid {
		for _, tid := range toDelete {
			if tid == currentID.String {
				if _, err := r.db.Exec("UPDATE current_task SET task_id = NULL WHERE id = 1"); err != nil {
					return err
				}
				break
			}
		}
	}

	// Delete in reverse order (children first)
	for i := len(toDelete) - 1; i >= 0; i-- {
		if _, err := r.db.Exec("DELETE FROM tasks WHERE id = ?", toDelete[i]); err != nil {
			return err
		}
	}
	return nil
}

// MoveTask changes a task's parent with cycle detection.
func (r *Repository) MoveTask(id string, newParentID *string) error {
	if newParentID != nil {
		// Cycle detection: walk up from newParentID to root
		current := *newParentID
		for current != "" {
			if current == id {
				return fmt.Errorf("cycle detected")
			}
			var parentID sql.NullString
			err := r.db.QueryRow("SELECT parent_id FROM tasks WHERE id = ?", current).Scan(&parentID)
			if err != nil || !parentID.Valid {
				break
			}
			current = parentID.String
		}
	}

	_, err := r.db.Exec("UPDATE tasks SET parent_id = ? WHERE id = ?", newParentID, id)
	return err
}

// GetAllDescendants returns all tasks in the subtree under rootID (not including root).
func (r *Repository) GetAllDescendants(rootID string) ([]*domain.Task, error) {
	var result []*domain.Task
	queue := []string{rootID}
	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]
		children, err := r.GetChildren(current)
		if err != nil {
			return nil, err
		}
		for _, child := range children {
			result = append(result, child)
			queue = append(queue, child.ID)
		}
	}
	return result, nil
}

// FindByIdempotencyKey finds a task by its idempotency key.
func (r *Repository) FindByIdempotencyKey(key string) (*domain.Task, error) {
	row := r.db.QueryRow(
		"SELECT "+selectTaskCols+" FROM tasks WHERE idempotency_key = ?", key,
	)
	t, err := rowToTask(row)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return t, err
}

// SetCurrentTask updates the current_task singleton.
func (r *Repository) SetCurrentTask(id *string) error {
	_, err := r.db.Exec("UPDATE current_task SET task_id = ? WHERE id = 1", id)
	return err
}

// GetCurrentTaskID returns the current task ID or nil.
func (r *Repository) GetCurrentTaskID() (*string, error) {
	var id sql.NullString
	err := r.db.QueryRow("SELECT task_id FROM current_task WHERE id = 1").Scan(&id)
	if err != nil {
		return nil, err
	}
	if !id.Valid {
		return nil, nil
	}
	return &id.String, nil
}

// AddDependencies adds dependency edges: taskID is blocked by each id in blockedByIDs.
func (r *Repository) AddDependencies(taskID string, blockedByIDs []string) error {
	if len(blockedByIDs) == 0 {
		return nil
	}

	// Validate taskID exists and is PENDING
	var status string
	err := r.db.QueryRow("SELECT status FROM tasks WHERE id = ?", taskID).Scan(&status)
	if err == sql.ErrNoRows {
		return fmt.Errorf("task '%s' not found", taskID)
	}
	if err != nil {
		return err
	}
	if status != string(domain.StatusPending) {
		return fmt.Errorf("can only add dependencies to pending tasks")
	}

	// Validate all blockedByIDs exist; reject self-dependency
	for _, bid := range blockedByIDs {
		if bid == taskID {
			return fmt.Errorf("task cannot depend on itself")
		}
		var exists string
		err := r.db.QueryRow("SELECT id FROM tasks WHERE id = ?", bid).Scan(&exists)
		if err == sql.ErrNoRows {
			return fmt.Errorf("blocker task '%s' not found", bid)
		}
		if err != nil {
			return err
		}
	}

	// Cycle detection: BFS from each blockedByID through existing dependency edges.
	for _, bid := range blockedByIDs {
		visited := make(map[string]bool)
		queue := []string{bid}
		for len(queue) > 0 {
			current := queue[0]
			queue = queue[1:]
			if visited[current] {
				continue
			}
			visited[current] = true
			if current == taskID {
				return fmt.Errorf("cycle detected")
			}
			rows, err := r.db.Query(
				"SELECT blocked_by_id FROM task_dependencies WHERE task_id = ?", current,
			)
			if err != nil {
				return err
			}
			for rows.Next() {
				var depID string
				if err := rows.Scan(&depID); err != nil {
					rows.Close()
					return err
				}
				queue = append(queue, depID)
			}
			rows.Close()
		}
	}

	for _, bid := range blockedByIDs {
		if _, err := r.db.Exec(
			"INSERT OR IGNORE INTO task_dependencies (task_id, blocked_by_id) VALUES (?, ?)",
			taskID, bid,
		); err != nil {
			return fmt.Errorf("inserting dependency: %w", err)
		}
	}
	return nil
}

// GetBlockers returns tasks that taskID is blocked by.
func (r *Repository) GetBlockers(taskID string) ([]*domain.Task, error) {
	rows, err := r.db.Query(
		`SELECT t.`+selectTaskCols+` FROM tasks t
		JOIN task_dependencies d ON t.id = d.blocked_by_id
		WHERE d.task_id = ?
		ORDER BY t.created_at`,
		taskID,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanTasks(rows)
}

// GetDependents returns tasks that are blocked by taskID.
func (r *Repository) GetDependents(taskID string) ([]*domain.Task, error) {
	rows, err := r.db.Query(
		`SELECT t.`+selectTaskCols+` FROM tasks t
		JOIN task_dependencies d ON t.id = d.task_id
		WHERE d.blocked_by_id = ?
		ORDER BY t.created_at`,
		taskID,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanTasks(rows)
}

// GetReadyTasks returns PENDING tasks whose blockers are all DONE.
func (r *Repository) GetReadyTasks(parentID *string) ([]*domain.Task, error) {
	conditions := []string{"t.status = ?"}
	params := []any{string(domain.StatusPending)}

	if parentID != nil {
		conditions = append(conditions, "t.parent_id = ?")
		params = append(params, *parentID)
	}

	where := strings.Join(conditions, " AND ")
	q := fmt.Sprintf(`
		SELECT t.%s FROM tasks t
		WHERE %s
		  AND NOT EXISTS (
			  SELECT 1 FROM task_dependencies d
			  JOIN tasks b ON b.id = d.blocked_by_id
			  WHERE d.task_id = t.id
				AND b.status != ?
		  )
		ORDER BY t.position ASC NULLS LAST, t.created_at ASC
	`, selectTaskCols, where)
	params = append(params, string(domain.StatusDone))

	rows, err := r.db.Query(q, params...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanTasks(rows)
}

// LogEvent appends an event to the audit trail.
func (r *Repository) LogEvent(taskID, eventType string, details map[string]any) error {
	now := nowUTC()
	detailsJSON := "{}"
	if details != nil {
		b, _ := json.Marshal(details)
		detailsJSON = string(b)
	}
	_, err := r.db.Exec(
		"INSERT INTO task_events (task_id, event_type, timestamp, details) VALUES (?, ?, ?, ?)",
		taskID, eventType, now, detailsJSON,
	)
	return err
}

// GetTaskHistory returns the event log for a task.
func (r *Repository) GetTaskHistory(taskID string, recursive bool) ([]map[string]any, error) {
	var (
		rows *sql.Rows
		err  error
	)

	if recursive {
		allIDs := []string{taskID}
		queue := []string{taskID}
		for len(queue) > 0 {
			current := queue[0]
			queue = queue[1:]
			childRows, err := r.db.Query("SELECT id FROM tasks WHERE parent_id = ?", current)
			if err != nil {
				return nil, err
			}
			for childRows.Next() {
				var cid string
				if err := childRows.Scan(&cid); err != nil {
					childRows.Close()
					return nil, err
				}
				allIDs = append(allIDs, cid)
				queue = append(queue, cid)
			}
			childRows.Close()
		}
		placeholders := strings.Repeat("?,", len(allIDs))
		placeholders = placeholders[:len(placeholders)-1]
		params := make([]any, len(allIDs))
		for i, id := range allIDs {
			params[i] = id
		}
		rows, err = r.db.Query(
			fmt.Sprintf(`SELECT e.event_type, e.timestamp, e.details, t.name AS task_name
				FROM task_events e
				JOIN tasks t ON t.id = e.task_id
				WHERE e.task_id IN (%s)
				ORDER BY e.timestamp ASC`, placeholders),
			params...,
		)
	} else {
		rows, err = r.db.Query(
			`SELECT e.event_type, e.timestamp, e.details, t.name AS task_name
			FROM task_events e
			JOIN tasks t ON t.id = e.task_id
			WHERE e.task_id = ?
			ORDER BY e.timestamp ASC`,
			taskID,
		)
	}
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var events []map[string]any
	for rows.Next() {
		var eventType, timestamp, details, taskName string
		if err := rows.Scan(&eventType, &timestamp, &details, &taskName); err != nil {
			return nil, err
		}
		events = append(events, map[string]any{
			"event_type": eventType,
			"timestamp":  timestamp,
			"task_name":  taskName,
			"details":    details,
		})
	}
	return events, rows.Err()
}

// HasTasks returns true if at least one task exists.
func (r *Repository) HasTasks() (bool, error) {
	var count int
	err := r.db.QueryRow("SELECT COUNT(1) FROM tasks LIMIT 1").Scan(&count)
	return count > 0, err
}

// CleanupDoneRoots deletes completed root tasks older than days. Returns count deleted.
func (r *Repository) CleanupDoneRoots(days int) (int, error) {
	cutoff := time.Now().UTC().Add(-time.Duration(days) * 24 * time.Hour).Format("2006-01-02T15:04:05.999999-07:00")

	rows, err := r.db.Query(`
		SELECT t.id FROM tasks t
		WHERE t.parent_id IS NULL
		  AND t.status = 'done'
		  AND t.completed_at IS NOT NULL
		  AND t.completed_at < ?
		  AND NOT EXISTS (
			  WITH RECURSIVE subtree(id) AS (
				  SELECT id FROM tasks WHERE parent_id = t.id
				  UNION ALL
				  SELECT c.id FROM tasks c
				  JOIN subtree s ON c.parent_id = s.id
			  )
			  SELECT 1 FROM subtree s
			  JOIN tasks d ON d.id = s.id
			  WHERE d.status != 'done'
		  )
	`, cutoff)
	if err != nil {
		return 0, err
	}
	var rootIDs []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return 0, err
		}
		rootIDs = append(rootIDs, id)
	}
	rows.Close()

	for _, rid := range rootIDs {
		if err := r.DeleteTask(rid); err != nil {
			return 0, err
		}
	}
	return len(rootIDs), nil
}

// FindActiveRoot finds the most recent root task with in-progress work in its subtree.
func (r *Repository) FindActiveRoot() (*domain.Task, error) {
	row := r.db.QueryRow(`
		WITH RECURSIVE subtree(id, root_id) AS (
			SELECT id, id AS root_id FROM tasks WHERE parent_id IS NULL
			UNION ALL
			SELECT t.id, s.root_id
			FROM tasks t
			JOIN subtree s ON t.parent_id = s.id
		)
		SELECT t.`+selectTaskCols+` FROM tasks t
		WHERE t.parent_id IS NULL
		  AND EXISTS (
			  SELECT 1 FROM subtree s
			  JOIN tasks d ON d.id = s.id
			  WHERE s.root_id = t.id
				AND d.status = ?
		  )
		ORDER BY t.created_at DESC
		LIMIT 1
	`, string(domain.StatusInProgress))

	t, err := rowToTask(row)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return t, err
}

// --- Analytics (implements app.AnalyticsRepository) ---

// WorkflowSummary returns average duration, completion rate, and count by workflow type.
func (r *Repository) WorkflowSummary(days int) (string, error) {
	cutoff := time.Now().UTC().Add(-time.Duration(days) * 24 * time.Hour).Format("2006-01-02T15:04:05.999999-07:00")

	rows, err := r.db.Query(`
		SELECT
			t.id, t.name, t.status, t.started_at, t.completed_at,
			COUNT(c.id) as step_count
		FROM tasks t
		LEFT JOIN tasks c ON c.parent_id = t.id
		WHERE t.parent_id IS NULL
		  AND t.created_at >= ?
		GROUP BY t.id
		HAVING step_count > 0
		ORDER BY t.created_at DESC
	`, cutoff)
	if err != nil {
		return "", err
	}
	defer rows.Close()

	type wfRow struct {
		id          string
		name        string
		status      string
		startedAt   sql.NullString
		completedAt sql.NullString
		stepCount   int
	}

	var wfRows []wfRow
	for rows.Next() {
		var r wfRow
		if err := rows.Scan(&r.id, &r.name, &r.status, &r.startedAt, &r.completedAt, &r.stepCount); err != nil {
			return "", err
		}
		wfRows = append(wfRows, r)
	}
	if err := rows.Err(); err != nil {
		return "", err
	}

	if len(wfRows) == 0 {
		return "No data for the specified period.", nil
	}

	total := len(wfRows)
	done := 0
	failed := 0
	var durations []float64

	for _, row := range wfRows {
		if row.status == "done" {
			done++
		}
		if row.status == "failed" {
			failed++
		}
		if row.startedAt.Valid && row.completedAt.Valid {
			start, err1 := time.Parse(time.RFC3339Nano, row.startedAt.String)
			end, err2 := time.Parse(time.RFC3339Nano, row.completedAt.String)
			if err1 != nil {
				start, err1 = time.Parse("2006-01-02T15:04:05.999999-07:00", row.startedAt.String)
			}
			if err2 != nil {
				end, err2 = time.Parse("2006-01-02T15:04:05.999999-07:00", row.completedAt.String)
			}
			if err1 == nil && err2 == nil {
				durations = append(durations, end.Sub(start).Seconds())
			}
		}
	}

	var lines []string
	lines = append(lines, fmt.Sprintf("Workflow Summary (last %d days):", days), "")
	lines = append(lines, fmt.Sprintf("Total workflows: %d", total))
	if total > 0 {
		lines = append(lines, fmt.Sprintf("Completed: %d (%d%%)", done, roundPct(done, total)))
		lines = append(lines, fmt.Sprintf("Failed: %d (%d%%)", failed, roundPct(failed, total)))
		lines = append(lines, fmt.Sprintf("In progress: %d", total-done-failed))
	}
	if len(durations) > 0 {
		avg := sum(durations) / float64(len(durations))
		lines = append(lines, fmt.Sprintf("Avg duration: %s", formatDurationSeconds(int(avg))))
		lines = append(lines, fmt.Sprintf("Min duration: %s", formatDurationSeconds(int(minFloat(durations)))))
		lines = append(lines, fmt.Sprintf("Max duration: %s", formatDurationSeconds(int(maxFloat(durations)))))
	}
	return strings.Join(lines, "\n"), nil
}

// StepBottlenecks returns top 10 slowest steps by average duration.
func (r *Repository) StepBottlenecks(days int) (string, error) {
	cutoff := time.Now().UTC().Add(-time.Duration(days) * 24 * time.Hour).Format("2006-01-02T15:04:05.999999-07:00")

	rows, err := r.db.Query(`
		SELECT
			t.name,
			AVG(CAST(
				(julianday(t.completed_at) - julianday(t.started_at)) * 86400
			AS REAL)) as avg_seconds,
			MAX(CAST(
				(julianday(t.completed_at) - julianday(t.started_at)) * 86400
			AS REAL)) as max_seconds,
			COUNT(*) as count
		FROM tasks t
		WHERE t.parent_id IS NOT NULL
		  AND t.status = 'done'
		  AND t.started_at IS NOT NULL
		  AND t.completed_at IS NOT NULL
		  AND t.created_at >= ?
		GROUP BY t.name
		ORDER BY avg_seconds DESC
		LIMIT 10
	`, cutoff)
	if err != nil {
		return "", err
	}
	defer rows.Close()

	type btRow struct {
		name       string
		avgSeconds sql.NullFloat64
		maxSeconds sql.NullFloat64
		count      int
	}

	var btRows []btRow
	for rows.Next() {
		var br btRow
		if err := rows.Scan(&br.name, &br.avgSeconds, &br.maxSeconds, &br.count); err != nil {
			return "", err
		}
		btRows = append(btRows, br)
	}

	if len(btRows) == 0 {
		return "No data for the specified period.", nil
	}

	var lines []string
	lines = append(lines, fmt.Sprintf("Step Bottlenecks (last %d days):", days), "")
	lines = append(lines, fmt.Sprintf("%-4s%-40s%10s%10s%7s", "#", "Step", "Avg", "Max", "Count"))
	lines = append(lines, strings.Repeat("-", 71))

	for i, row := range btRows {
		avg := "N/A"
		mx := "N/A"
		if row.avgSeconds.Valid {
			avg = formatDurationSeconds(int(row.avgSeconds.Float64))
		}
		if row.maxSeconds.Valid {
			mx = formatDurationSeconds(int(row.maxSeconds.Float64))
		}
		name := row.name
		if len(name) > 38 {
			name = name[:38]
		}
		lines = append(lines, fmt.Sprintf("%-4d%-40s%10s%10s%7d", i+1, name, avg, mx, row.count))
	}
	return strings.Join(lines, "\n"), nil
}

// AgentPerformance returns success rate grouped by agent.
func (r *Repository) AgentPerformance(days int) (string, error) {
	cutoff := time.Now().UTC().Add(-time.Duration(days) * 24 * time.Hour).Format("2006-01-02T15:04:05.999999-07:00")

	rows, err := r.db.Query(`
		SELECT t.metadata, t.status
		FROM tasks t
		WHERE t.parent_id IS NOT NULL
		  AND t.status IN ('done', 'failed')
		  AND t.created_at >= ?
	`, cutoff)
	if err != nil {
		return "", err
	}
	defer rows.Close()

	agentStats := make(map[string]map[string]int)
	hasRows := false
	for rows.Next() {
		hasRows = true
		var metadata, status string
		if err := rows.Scan(&metadata, &status); err != nil {
			return "", err
		}
		var meta map[string]any
		if err := json.Unmarshal([]byte(metadata), &meta); err != nil {
			meta = map[string]any{}
		}
		agent := "unknown"
		if a, ok := meta["agent"].(string); ok && a != "" {
			agent = a
		}
		if agentStats[agent] == nil {
			agentStats[agent] = map[string]int{"done": 0, "failed": 0}
		}
		agentStats[agent][status]++
	}

	if !hasRows {
		return "No data for the specified period.", nil
	}

	var lines []string
	lines = append(lines, fmt.Sprintf("Agent Performance (last %d days):", days), "")
	lines = append(lines, fmt.Sprintf("%-25s%7s%7s%7s%9s", "Agent", "Total", "Done", "Failed", "Success"))
	lines = append(lines, strings.Repeat("-", 55))

	// Sort agents
	agents := make([]string, 0, len(agentStats))
	for a := range agentStats {
		agents = append(agents, a)
	}
	sortStrings(agents)

	for _, agent := range agents {
		stats := agentStats[agent]
		total := stats["done"] + stats["failed"]
		rate := "N/A"
		if total > 0 {
			rate = fmt.Sprintf("%d%%", roundPct(stats["done"], total))
		}
		lines = append(lines, fmt.Sprintf("%-25s%7d%7d%7d%9s", agent, total, stats["done"], stats["failed"], rate))
	}
	return strings.Join(lines, "\n"), nil
}

// Velocity returns tasks completed per week over the specified period.
func (r *Repository) Velocity(days int) (string, error) {
	cutoff := time.Now().UTC().Add(-time.Duration(days) * 24 * time.Hour).Format("2006-01-02T15:04:05.999999-07:00")

	rows, err := r.db.Query(`
		SELECT t.completed_at, t.status
		FROM tasks t
		WHERE t.parent_id IS NULL
		  AND t.status IN ('done', 'failed')
		  AND t.completed_at IS NOT NULL
		  AND t.completed_at >= ?
		ORDER BY t.completed_at ASC
	`, cutoff)
	if err != nil {
		return "", err
	}
	defer rows.Close()

	weeks := make(map[string]map[string]int)
	weekOrder := make([]string, 0)
	hasRows := false

	for rows.Next() {
		hasRows = true
		var completedAt, status string
		if err := rows.Scan(&completedAt, &status); err != nil {
			return "", err
		}
		t, err := time.Parse(time.RFC3339Nano, completedAt)
		if err != nil {
			t, err = time.Parse("2006-01-02T15:04:05.999999-07:00", completedAt)
		}
		if err != nil {
			continue
		}
		year, week := t.ISOWeek()
		weekKey := fmt.Sprintf("%04d-W%02d", year, week)
		if weeks[weekKey] == nil {
			weeks[weekKey] = map[string]int{"done": 0, "failed": 0}
			weekOrder = append(weekOrder, weekKey)
		}
		weeks[weekKey][status]++
	}

	if !hasRows {
		return "No data for the specified period.", nil
	}

	sortStrings(weekOrder)

	var lines []string
	lines = append(lines, fmt.Sprintf("Velocity (last %d days):", days), "")
	lines = append(lines, fmt.Sprintf("%-12s%10s%10s", "Week", "Completed", "Failed"))
	lines = append(lines, strings.Repeat("-", 32))

	totalDone := 0
	for _, week := range weekOrder {
		stats := weeks[week]
		lines = append(lines, fmt.Sprintf("%-12s%10d%10d", week, stats["done"], stats["failed"]))
		totalDone += stats["done"]
	}

	totalWeeks := len(weekOrder)
	if totalWeeks > 0 {
		lines = append(lines, "")
		lines = append(lines, fmt.Sprintf("Avg: %.1f workflows/week", float64(totalDone)/float64(totalWeeks)))
	}
	return strings.Join(lines, "\n"), nil
}

// --- helper utilities ---

func scanTasks(rows *sql.Rows) ([]*domain.Task, error) {
	var tasks []*domain.Task
	for rows.Next() {
		t, err := rowsToTask(rows)
		if err != nil {
			return nil, err
		}
		tasks = append(tasks, t)
	}
	return tasks, rows.Err()
}

func roundPct(part, total int) int {
	if total == 0 {
		return 0
	}
	return int(float64(part)*100/float64(total) + 0.5)
}

func sum(fs []float64) float64 {
	var s float64
	for _, f := range fs {
		s += f
	}
	return s
}

func minFloat(fs []float64) float64 {
	if len(fs) == 0 {
		return 0
	}
	m := fs[0]
	for _, f := range fs[1:] {
		if f < m {
			m = f
		}
	}
	return m
}

func maxFloat(fs []float64) float64 {
	if len(fs) == 0 {
		return 0
	}
	m := fs[0]
	for _, f := range fs[1:] {
		if f > m {
			m = f
		}
	}
	return m
}

func formatDurationSeconds(total int) string {
	if total < 60 {
		return fmt.Sprintf("%ds", total)
	}
	minutes := total / 60
	secs := total % 60
	if minutes < 60 {
		return fmt.Sprintf("%dm %ds", minutes, secs)
	}
	hours := minutes / 60
	mins := minutes % 60
	return fmt.Sprintf("%dh %dm", hours, mins)
}

func sortStrings(ss []string) {
	// simple insertion sort for small slices
	for i := 1; i < len(ss); i++ {
		key := ss[i]
		j := i - 1
		for j >= 0 && ss[j] > key {
			ss[j+1] = ss[j]
			j--
		}
		ss[j+1] = key
	}
}
