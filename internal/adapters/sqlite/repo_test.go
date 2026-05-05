package sqlite

import (
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/elpic/taskflow/internal/domain"
)

func newTestDB(t *testing.T) *Repository {
	t.Helper()
	dbPath := filepath.Join(t.TempDir(), "test.db")
	db, err := Open(dbPath)
	require.NoError(t, err)
	t.Cleanup(func() { db.Close() })
	require.NoError(t, Initialize(db))
	return NewRepository(db)
}

// --- CreateTask / GetTask ---

func TestCreateTask_BasicFields(t *testing.T) {
	repo := newTestDB(t)
	task, err := repo.CreateTask("My Task", "Some description", nil, nil, nil, nil)
	require.NoError(t, err)
	require.NotNil(t, task)

	assert.Len(t, task.ID, 8, "ID should be 8 hex chars")
	assert.Equal(t, "My Task", task.Name)
	assert.Equal(t, "Some description", task.Description)
	assert.Equal(t, domain.StatusPending, task.Status)
	assert.Nil(t, task.ParentID)
	assert.NotEmpty(t, task.CreatedAt)
}

func TestCreateTask_WithParent(t *testing.T) {
	repo := newTestDB(t)
	parent, err := repo.CreateTask("Parent", "", nil, nil, nil, nil)
	require.NoError(t, err)

	child, err := repo.CreateTask("Child", "", &parent.ID, nil, nil, nil)
	require.NoError(t, err)
	require.NotNil(t, child)
	require.NotNil(t, child.ParentID)
	assert.Equal(t, parent.ID, *child.ParentID)
}

func TestCreateTask_InvalidParent(t *testing.T) {
	repo := newTestDB(t)
	nonExistent := "deadbeef"
	_, err := repo.CreateTask("Child", "", &nonExistent, nil, nil, nil)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "not found")
}

func TestCreateTask_WithVerificationCriteria(t *testing.T) {
	repo := newTestDB(t)
	vc := "must pass all tests"
	task, err := repo.CreateTask("Task", "", nil, &vc, nil, nil)
	require.NoError(t, err)
	require.NotNil(t, task.VerificationCriteria)
	assert.Equal(t, vc, *task.VerificationCriteria)
}

func TestCreateTask_WithMetadata(t *testing.T) {
	repo := newTestDB(t)
	meta := map[string]any{"agent": "developer", "priority": 1}
	task, err := repo.CreateTask("Task", "", nil, nil, meta, nil)
	require.NoError(t, err)
	assert.Contains(t, task.Metadata, "developer")
}

func TestGetTask_NotFound(t *testing.T) {
	repo := newTestDB(t)
	task, err := repo.GetTask("notfound")
	require.NoError(t, err)
	assert.Nil(t, task)
}

// --- UpdateTask ---

func TestUpdateTask_StatusChange(t *testing.T) {
	repo := newTestDB(t)
	task, err := repo.CreateTask("Task", "", nil, nil, nil, nil)
	require.NoError(t, err)

	updated, err := repo.UpdateTask(task.ID, map[string]any{
		"status":     "in_progress",
		"started_at": "2024-01-01T10:00:00.000000+00:00",
	})
	require.NoError(t, err)
	assert.Equal(t, domain.StatusInProgress, updated.Status)
	require.NotNil(t, updated.StartedAt)
}

func TestUpdateTask_DisallowedField(t *testing.T) {
	repo := newTestDB(t)
	task, err := repo.CreateTask("Task", "", nil, nil, nil, nil)
	require.NoError(t, err)

	// Disallowed field is silently ignored
	updated, err := repo.UpdateTask(task.ID, map[string]any{
		"created_at": "2000-01-01",
	})
	require.NoError(t, err)
	// created_at should not change
	assert.Equal(t, task.CreatedAt, updated.CreatedAt)
}

// --- DeleteTask ---

func TestDeleteTask_CascadesChildren(t *testing.T) {
	repo := newTestDB(t)
	parent, _ := repo.CreateTask("Parent", "", nil, nil, nil, nil)
	child, _ := repo.CreateTask("Child", "", &parent.ID, nil, nil, nil)

	require.NoError(t, repo.DeleteTask(parent.ID))

	got, err := repo.GetTask(parent.ID)
	require.NoError(t, err)
	assert.Nil(t, got, "parent should be deleted")

	got, err = repo.GetTask(child.ID)
	require.NoError(t, err)
	assert.Nil(t, got, "child should be deleted via cascade")
}

// --- Dependencies ---

func TestAddDependencies_GetBlockers(t *testing.T) {
	repo := newTestDB(t)
	taskA, _ := repo.CreateTask("A", "", nil, nil, nil, nil)
	taskB, _ := repo.CreateTask("B", "", nil, nil, nil, nil)

	err := repo.AddDependencies(taskB.ID, []string{taskA.ID})
	require.NoError(t, err)

	blockers, err := repo.GetBlockers(taskB.ID)
	require.NoError(t, err)
	require.Len(t, blockers, 1)
	assert.Equal(t, taskA.ID, blockers[0].ID)
}

func TestAddDependencies_GetDependents(t *testing.T) {
	repo := newTestDB(t)
	taskA, _ := repo.CreateTask("A", "", nil, nil, nil, nil)
	taskB, _ := repo.CreateTask("B", "", nil, nil, nil, nil)

	err := repo.AddDependencies(taskB.ID, []string{taskA.ID})
	require.NoError(t, err)

	dependents, err := repo.GetDependents(taskA.ID)
	require.NoError(t, err)
	require.Len(t, dependents, 1)
	assert.Equal(t, taskB.ID, dependents[0].ID)
}

func TestAddDependencies_SelfDependency(t *testing.T) {
	repo := newTestDB(t)
	task, _ := repo.CreateTask("Task", "", nil, nil, nil, nil)
	err := repo.AddDependencies(task.ID, []string{task.ID})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "itself")
}

func TestAddDependencies_CycleDetection(t *testing.T) {
	repo := newTestDB(t)
	a, _ := repo.CreateTask("A", "", nil, nil, nil, nil)
	b, _ := repo.CreateTask("B", "", nil, nil, nil, nil)

	// A depends on B
	require.NoError(t, repo.AddDependencies(a.ID, []string{b.ID}))

	// B depends on A — should fail (cycle)
	err := repo.AddDependencies(b.ID, []string{a.ID})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "cycle")
}

// --- GetReadyTasks ---

func TestGetReadyTasks_UnblockedTask(t *testing.T) {
	repo := newTestDB(t)
	// Task with no deps is ready
	task, _ := repo.CreateTask("Ready", "", nil, nil, nil, nil)
	ready, err := repo.GetReadyTasks(nil)
	require.NoError(t, err)
	assert.Len(t, ready, 1)
	assert.Equal(t, task.ID, ready[0].ID)
}

func TestGetReadyTasks_BlockedTask(t *testing.T) {
	repo := newTestDB(t)
	blocker, _ := repo.CreateTask("Blocker", "", nil, nil, nil, nil)
	blocked, _ := repo.CreateTask("Blocked", "", nil, nil, nil, nil)

	require.NoError(t, repo.AddDependencies(blocked.ID, []string{blocker.ID}))

	ready, err := repo.GetReadyTasks(nil)
	require.NoError(t, err)
	// Only the blocker (no deps) should be ready
	for _, task := range ready {
		assert.NotEqual(t, blocked.ID, task.ID, "blocked task should not be ready")
	}
}

func TestGetReadyTasks_UnblocksAfterDone(t *testing.T) {
	repo := newTestDB(t)
	blocker, _ := repo.CreateTask("Blocker", "", nil, nil, nil, nil)
	blocked, _ := repo.CreateTask("Blocked", "", nil, nil, nil, nil)
	require.NoError(t, repo.AddDependencies(blocked.ID, []string{blocker.ID}))

	// Mark blocker done
	_, err := repo.UpdateTask(blocker.ID, map[string]any{"status": "done"})
	require.NoError(t, err)

	ready, err := repo.GetReadyTasks(nil)
	require.NoError(t, err)
	ids := make([]string, len(ready))
	for i, r := range ready {
		ids[i] = r.ID
	}
	assert.Contains(t, ids, blocked.ID, "task should be ready after blocker is done")
}

func TestGetReadyTasks_FilterByParent(t *testing.T) {
	repo := newTestDB(t)
	parent, _ := repo.CreateTask("Parent", "", nil, nil, nil, nil)
	child1, _ := repo.CreateTask("Child1", "", &parent.ID, nil, nil, nil)
	_, _ = repo.CreateTask("Standalone", "", nil, nil, nil, nil)

	ready, err := repo.GetReadyTasks(&parent.ID)
	require.NoError(t, err)
	assert.Len(t, ready, 1)
	assert.Equal(t, child1.ID, ready[0].ID)
}

// --- FindByIdempotencyKey ---

func TestFindByIdempotencyKey(t *testing.T) {
	repo := newTestDB(t)
	key := "my-unique-key-123"
	task, err := repo.CreateTask("Task", "", nil, nil, nil, &key)
	require.NoError(t, err)

	found, err := repo.FindByIdempotencyKey(key)
	require.NoError(t, err)
	require.NotNil(t, found)
	assert.Equal(t, task.ID, found.ID)
}

func TestFindByIdempotencyKey_NotFound(t *testing.T) {
	repo := newTestDB(t)
	found, err := repo.FindByIdempotencyKey("nonexistent")
	require.NoError(t, err)
	assert.Nil(t, found)
}

// --- LogEvent / GetTaskHistory ---

func TestLogEvent_GetTaskHistory(t *testing.T) {
	repo := newTestDB(t)
	task, _ := repo.CreateTask("Task", "", nil, nil, nil, nil)

	require.NoError(t, repo.LogEvent(task.ID, domain.EventCreated, map[string]any{"name": "Task"}))
	require.NoError(t, repo.LogEvent(task.ID, domain.EventStarted, nil))

	history, err := repo.GetTaskHistory(task.ID, false)
	require.NoError(t, err)
	assert.Len(t, history, 2)
	assert.Equal(t, domain.EventCreated, history[0]["event_type"])
	assert.Equal(t, domain.EventStarted, history[1]["event_type"])
}

func TestGetTaskHistory_Recursive(t *testing.T) {
	repo := newTestDB(t)
	parent, _ := repo.CreateTask("Parent", "", nil, nil, nil, nil)
	child, _ := repo.CreateTask("Child", "", &parent.ID, nil, nil, nil)

	require.NoError(t, repo.LogEvent(parent.ID, domain.EventCreated, nil))
	require.NoError(t, repo.LogEvent(child.ID, domain.EventCreated, nil))

	// Non-recursive: only parent events
	history, err := repo.GetTaskHistory(parent.ID, false)
	require.NoError(t, err)
	assert.Len(t, history, 1)

	// Recursive: parent + child events
	history, err = repo.GetTaskHistory(parent.ID, true)
	require.NoError(t, err)
	assert.Len(t, history, 2)
}

// --- SetCurrentTask / GetCurrentTaskID ---

func TestSetCurrentTask_GetCurrentTaskID(t *testing.T) {
	repo := newTestDB(t)
	task, _ := repo.CreateTask("Active", "", nil, nil, nil, nil)

	require.NoError(t, repo.SetCurrentTask(&task.ID))

	currentID, err := repo.GetCurrentTaskID()
	require.NoError(t, err)
	require.NotNil(t, currentID)
	assert.Equal(t, task.ID, *currentID)
}

func TestSetCurrentTask_ClearCurrent(t *testing.T) {
	repo := newTestDB(t)
	task, _ := repo.CreateTask("Task", "", nil, nil, nil, nil)
	require.NoError(t, repo.SetCurrentTask(&task.ID))

	require.NoError(t, repo.SetCurrentTask(nil))

	currentID, err := repo.GetCurrentTaskID()
	require.NoError(t, err)
	assert.Nil(t, currentID)
}

// --- HasTasks ---

func TestHasTasks_Empty(t *testing.T) {
	repo := newTestDB(t)
	has, err := repo.HasTasks()
	require.NoError(t, err)
	assert.False(t, has)
}

func TestHasTasks_WithTask(t *testing.T) {
	repo := newTestDB(t)
	_, _ = repo.CreateTask("Task", "", nil, nil, nil, nil)
	has, err := repo.HasTasks()
	require.NoError(t, err)
	assert.True(t, has)
}

// --- GetChildren ---

func TestGetChildren_Empty(t *testing.T) {
	repo := newTestDB(t)
	parent, _ := repo.CreateTask("Parent", "", nil, nil, nil, nil)
	children, err := repo.GetChildren(parent.ID)
	require.NoError(t, err)
	assert.Empty(t, children)
}

func TestGetChildren_Multiple(t *testing.T) {
	repo := newTestDB(t)
	parent, _ := repo.CreateTask("Parent", "", nil, nil, nil, nil)
	_, _ = repo.CreateTask("C1", "", &parent.ID, nil, nil, nil)
	_, _ = repo.CreateTask("C2", "", &parent.ID, nil, nil, nil)

	children, err := repo.GetChildren(parent.ID)
	require.NoError(t, err)
	assert.Len(t, children, 2)
}

// --- ResetTask ---

func TestResetTask(t *testing.T) {
	repo := newTestDB(t)
	task, _ := repo.CreateTask("Task", "", nil, nil, nil, nil)

	// Mark as done
	now := "2024-01-01T10:00:00.000000+00:00"
	_, err := repo.UpdateTask(task.ID, map[string]any{
		"status":       "done",
		"completed_at": now,
		"started_at":   now,
	})
	require.NoError(t, err)

	require.NoError(t, repo.ResetTask(task.ID))

	reset, err := repo.GetTask(task.ID)
	require.NoError(t, err)
	assert.Equal(t, domain.StatusPending, reset.Status)
	assert.Nil(t, reset.StartedAt)
	assert.Nil(t, reset.CompletedAt)
}

// --- GetAllDescendants ---

func TestGetAllDescendants(t *testing.T) {
	repo := newTestDB(t)
	root, _ := repo.CreateTask("Root", "", nil, nil, nil, nil)
	c1, _ := repo.CreateTask("C1", "", &root.ID, nil, nil, nil)
	_, _ = repo.CreateTask("C2", "", &root.ID, nil, nil, nil)
	_, _ = repo.CreateTask("GC1", "", &c1.ID, nil, nil, nil)

	desc, err := repo.GetAllDescendants(root.ID)
	require.NoError(t, err)
	assert.Len(t, desc, 3, "should have 3 descendants (C1, C2, GC1)")
}

// --- SearchTasks ---

func TestSearchTasks(t *testing.T) {
	repo := newTestDB(t)
	_, _ = repo.CreateTask("Fix login bug", "authentication issue", nil, nil, nil, nil)
	_, _ = repo.CreateTask("Add unit tests", "testing coverage", nil, nil, nil, nil)

	results, err := repo.SearchTasks("login")
	require.NoError(t, err)
	assert.Len(t, results, 1)
	assert.Equal(t, "Fix login bug", results[0].Name)
}

func TestSearchTasks_CaseInsensitive(t *testing.T) {
	repo := newTestDB(t)
	_, _ = repo.CreateTask("Fix Login Bug", "", nil, nil, nil, nil)

	results, err := repo.SearchTasks("login")
	require.NoError(t, err)
	assert.Len(t, results, 1)
}

func TestSearchTasks_NoResults(t *testing.T) {
	repo := newTestDB(t)
	_, _ = repo.CreateTask("Task", "", nil, nil, nil, nil)

	results, err := repo.SearchTasks("nonexistent")
	require.NoError(t, err)
	assert.Empty(t, results)
}

// --- CleanupDoneRoots ---

func TestCleanupDoneRoots_NoOldTasks(t *testing.T) {
	repo := newTestDB(t)
	// Recent task: won't be cleaned up
	task, _ := repo.CreateTask("Recent", "", nil, nil, nil, nil)
	_, _ = repo.UpdateTask(task.ID, map[string]any{
		"status":       "done",
		"completed_at": "2099-01-01T00:00:00.000000+00:00",
	})

	count, err := repo.CleanupDoneRoots(30)
	require.NoError(t, err)
	assert.Equal(t, 0, count)
}

func TestCleanupDoneRoots_DeletesOldTasks(t *testing.T) {
	repo := newTestDB(t)
	task, _ := repo.CreateTask("Old Task", "", nil, nil, nil, nil)

	// Set completed_at far in the past
	_, _ = repo.UpdateTask(task.ID, map[string]any{
		"status":       "done",
		"completed_at": "2000-01-01T00:00:00.000000+00:00",
	})

	count, err := repo.CleanupDoneRoots(30)
	require.NoError(t, err)
	assert.Equal(t, 1, count)

	got, err := repo.GetTask(task.ID)
	require.NoError(t, err)
	assert.Nil(t, got)
}
