package app

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/elpic/taskflow/internal/domain"
)

// Get returns the details and children of a task.
func (s *Service) Get(taskID string) (string, error) {
	task, err := s.repo.GetTask(taskID)
	if err != nil || task == nil {
		return "error:not found", nil
	}

	children, err := s.repo.GetChildren(taskID)
	if err != nil {
		return "", err
	}
	tree := domain.RenderSubtree(task, children)

	parts := []string{tree}
	if task.Description != "" {
		parts = append(parts, "\nDescription: "+task.Description)
	}
	if task.VerificationCriteria != nil && *task.VerificationCriteria != "" {
		parts = append(parts, "Criteria: "+*task.VerificationCriteria)
	}
	if task.Metadata != "" && task.Metadata != "{}" {
		parts = append(parts, "Metadata: "+task.Metadata)
	}
	if task.ContextSummary != nil {
		parts = append(parts, "Summary: "+*task.ContextSummary)
	}
	if task.AgentOutput != nil {
		parts = append(parts, "Output: "+*task.AgentOutput)
	}

	blockers, err := s.repo.GetBlockers(taskID)
	if err != nil {
		return "", err
	}
	if len(blockers) > 0 {
		var blockerStrs []string
		for _, b := range blockers {
			blockerStrs = append(blockerStrs, fmt.Sprintf("%s (%s) [%s]", b.ID, b.Name, b.Status))
		}
		parts = append(parts, "Blocked by: "+strings.Join(blockerStrs, ", "))
	}

	return strings.Join(parts, "\n"), nil
}

// List returns tasks as a rendered tree, optionally filtered.
func (s *Service) List(status *string, parentID *string, ready bool) (string, error) {
	if ready {
		if parentID != nil {
			parent, err := s.repo.GetTask(*parentID)
			if err != nil || parent == nil {
				return "error:not found", nil
			}
		}
		tasks, err := s.repo.GetReadyTasks(parentID)
		if err != nil {
			return "", err
		}
		return domain.RenderTree(tasks), nil
	}

	if status != nil {
		valid := map[string]bool{
			"pending": true, "in_progress": true, "verifying": true,
			"done": true, "failed": true,
		}
		if !valid[*status] {
			return fmt.Sprintf("error:invalid status '%s'. Valid: done, failed, in_progress, pending, verifying", *status), nil
		}
	}

	if status != nil || parentID != nil {
		if parentID != nil {
			parent, err := s.repo.GetTask(*parentID)
			if err != nil || parent == nil {
				return "error:not found", nil
			}
		}
		tasks, err := s.repo.GetTasksFiltered(status, parentID)
		if err != nil {
			return "", err
		}
		return domain.RenderTree(tasks), nil
	}

	tasks, err := s.repo.GetAllTasks()
	if err != nil {
		return "", err
	}
	return domain.RenderTree(tasks), nil
}

// Search searches tasks by name or description.
func (s *Service) Search(query string) (string, error) {
	if strings.TrimSpace(query) == "" {
		return "error:empty query", nil
	}

	tasks, err := s.repo.SearchTasks(query)
	if err != nil {
		return "", err
	}
	if len(tasks) == 0 {
		return "No matching tasks.", nil
	}

	var lines []string
	for _, task := range tasks {
		parentInfo := ""
		if task.ParentID != nil {
			parentInfo = " (parent: " + *task.ParentID + ")"
		}
		lines = append(lines, fmt.Sprintf("[%s] %s [%s]%s", task.ID, task.Name, task.Status, parentInfo))
	}
	return strings.Join(lines, "\n"), nil
}

// Stats returns timing statistics for a task and its subtree.
func (s *Service) Stats(taskID string) (string, error) {
	task, err := s.repo.GetTask(taskID)
	if err != nil || task == nil {
		return "error:not found", nil
	}

	children, err := s.repo.GetChildren(taskID)
	if err != nil {
		return "", err
	}

	lines := []string{fmt.Sprintf("Stats: %s [%s]", task.Name, task.Status)}

	if task.StartedAt != nil && task.CompletedAt != nil {
		start, _ := time.Parse(time.RFC3339Nano, *task.StartedAt)
		end, _ := time.Parse(time.RFC3339Nano, *task.CompletedAt)
		duration := end.Sub(start)
		lines = append(lines, "Duration: "+formatDuration(duration))
	} else if task.StartedAt != nil {
		start, _ := time.Parse(time.RFC3339Nano, *task.StartedAt)
		elapsed := time.Since(start)
		lines = append(lines, "Elapsed: "+formatDuration(elapsed)+" (in progress)")
	}

	if len(children) > 0 {
		total := len(children)
		done := 0
		failed := 0
		for _, c := range children {
			if c.Status == domain.StatusDone {
				done++
			}
			if c.Status == domain.StatusFailed {
				failed++
			}
		}
		lines = append(lines, fmt.Sprintf("Children: %d/%d done, %d failed", done, total, failed))

		for _, child := range children {
			dur := ""
			if child.StartedAt != nil && child.CompletedAt != nil {
				s, _ := time.Parse(time.RFC3339Nano, *child.StartedAt)
				e, _ := time.Parse(time.RFC3339Nano, *child.CompletedAt)
				dur = " (" + formatDuration(e.Sub(s)) + ")"
			}
			lines = append(lines, fmt.Sprintf("  - %s [%s]%s", child.Name, child.Status, dur))
		}
	}

	return strings.Join(lines, "\n"), nil
}

// History returns the audit trail for a task.
func (s *Service) History(taskID string, recursive bool) (string, error) {
	task, err := s.repo.GetTask(taskID)
	if err != nil || task == nil {
		return "error:not found", nil
	}

	events, err := s.repo.GetTaskHistory(taskID, recursive)
	if err != nil {
		return "", err
	}
	if len(events) == 0 {
		return "No events found.", nil
	}

	var lines []string
	for _, event := range events {
		detailsStr := ""
		if raw, ok := event["details"].(string); ok && raw != "" && raw != "{}" {
			var details map[string]any
			if json.Unmarshal([]byte(raw), &details) == nil && len(details) > 0 {
				var parts []string
				for k, v := range details {
					parts = append(parts, fmt.Sprintf("%s: %v", k, v))
				}
				detailsStr = " — " + strings.Join(parts, ", ")
			}
		}
		lines = append(lines, fmt.Sprintf("[%s] %s: %s%s",
			event["timestamp"], event["event_type"], event["task_name"], detailsStr))
	}
	return strings.Join(lines, "\n"), nil
}

// Current returns the currently active task.
func (s *Service) Current() (string, error) {
	currentID, err := s.repo.GetCurrentTaskID()
	if err != nil || currentID == nil {
		return "No active task.", nil
	}

	task, err := s.repo.GetTask(*currentID)
	if err != nil || task == nil {
		return "No active task.", nil
	}

	children, err := s.repo.GetChildren(*currentID)
	if err != nil {
		return "", err
	}
	tree := domain.RenderSubtree(task, children)

	// Build breadcrumb
	var breadcrumb []string
	parentID := task.ParentID
	for parentID != nil {
		parent, err := s.repo.GetTask(*parentID)
		if err != nil || parent == nil {
			break
		}
		breadcrumb = append(breadcrumb, parent.Name)
		parentID = parent.ParentID
	}
	// Reverse
	for i, j := 0, len(breadcrumb)-1; i < j; i, j = i+1, j-1 {
		breadcrumb[i], breadcrumb[j] = breadcrumb[j], breadcrumb[i]
	}

	var parts []string
	if len(breadcrumb) > 0 {
		parts = append(parts, "Context: "+strings.Join(breadcrumb, " > "))
	}
	parts = append(parts, tree)
	return strings.Join(parts, "\n"), nil
}

// Resume summarises active work for a root task.
func (s *Service) Resume(rootID *string) (string, error) {
	var root *domain.Task
	var err error

	if rootID != nil {
		root, err = s.repo.GetTask(*rootID)
		if err != nil || root == nil {
			return "error:not found", nil
		}
		if root.ParentID != nil {
			return "error:task is not a root task", nil
		}
	} else {
		root, err = s.repo.FindActiveRoot()
		if err != nil || root == nil {
			return "No active work found.", nil
		}
	}

	// BFS to find deepest in-progress task
	type qItem struct {
		task  *domain.Task
		crumb []string
	}
	queue := []qItem{{task: root, crumb: nil}}
	var inProgressTask *domain.Task
	var inProgressCrumb []string

	for len(queue) > 0 {
		item := queue[0]
		queue = queue[1:]
		current := item.task

		if current.Status == domain.StatusInProgress {
			inProgressTask = current
			inProgressCrumb = append(item.crumb, current.Name)
		}

		children, _ := s.repo.GetChildren(current.ID)
		for _, child := range children {
			if child.Status == domain.StatusInProgress {
				newCrumb := make([]string, len(item.crumb))
				copy(newCrumb, item.crumb)
				newCrumb = append(newCrumb, current.Name)
				queue = append(queue, qItem{task: child, crumb: newCrumb})
			}
		}
	}

	// Find next ready task
	readyTasks, _ := s.repo.GetReadyTasks(&root.ID)
	if len(readyTasks) == 0 && inProgressTask != nil && inProgressTask.ParentID != nil {
		readyTasks, _ = s.repo.GetReadyTasks(inProgressTask.ParentID)
	}

	// Collect completed sibling context
	var contextLines []string
	sibParentID := root.ID
	if inProgressTask != nil && inProgressTask.ParentID != nil {
		sibParentID = *inProgressTask.ParentID
	}
	siblings, _ := s.repo.GetChildren(sibParentID)
	for _, sib := range siblings {
		if sib.Status != domain.StatusDone {
			continue
		}
		if sib.ContextSummary != nil {
			contextLines = append(contextLines, "  - "+sib.Name+": "+*sib.ContextSummary)
		} else if sib.AgentOutput != nil {
			truncated := *sib.AgentOutput
			if len(truncated) > 500 {
				truncated = truncated[:500] + "…"
			}
			contextLines = append(contextLines, "  - "+sib.Name+": "+truncated)
		}
	}

	var parts []string
	parts = append(parts, fmt.Sprintf("Resume: %s [%s]", root.Name, root.Status))

	if inProgressTask != nil {
		crumbStr := strings.Join(inProgressCrumb, " > ")
		parts = append(parts, "Current: "+inProgressTask.Name+" (path: "+crumbStr+")")
	} else {
		parts = append(parts, "Current: (none)")
	}

	if len(readyTasks) > 0 {
		next := readyTasks[0]
		meta := next.MetadataMap()
		agent, _ := meta["agent"].(string)
		agentStr := ""
		if agent != "" {
			agentStr = " (" + agent + ")"
		}
		parts = append(parts, "Next ready: "+next.Name+agentStr)
	} else {
		parts = append(parts, "Next ready: (none)")
	}

	if len(contextLines) > 0 {
		parts = append(parts, "Context from completed steps:")
		parts = append(parts, contextLines...)
	}

	return strings.Join(parts, "\n"), nil
}

// Next finds the next actionable step under a root task.
func (s *Service) Next(rootID string) (string, error) {
	root, err := s.repo.GetTask(rootID)
	if err != nil || root == nil {
		return "error:not found", nil
	}

	nextTask, err := s.findDeepestReady(rootID)
	if err != nil {
		return "", err
	}

	if nextTask != nil {
		meta := nextTask.MetadataMap()
		agent, _ := meta["agent"].(string)

		// Collect completed sibling outputs for context
		var contextEntries []map[string]string
		if nextTask.ParentID != nil {
			siblings, _ := s.repo.GetChildren(*nextTask.ParentID)
			for _, sib := range siblings {
				if sib.ID == nextTask.ID {
					break
				}
				if sib.Status != domain.StatusDone {
					continue
				}
				var contextText string
				if sib.ContextSummary != nil {
					contextText = *sib.ContextSummary
				} else if sib.AgentOutput != nil {
					contextText = *sib.AgentOutput
					if len(contextText) > 500 {
						contextText = contextText[:500] + "…"
					}
				} else {
					continue
				}
				contextEntries = append(contextEntries, map[string]string{
					"step":   sib.Name,
					"output": contextText,
				})
			}
		}

		// Build breadcrumb
		var breadcrumbParts []string
		walkID := nextTask.ParentID
		for walkID != nil && *walkID != rootID {
			parent, _ := s.repo.GetTask(*walkID)
			if parent == nil {
				break
			}
			breadcrumbParts = append([]string{parent.Name}, breadcrumbParts...)
			walkID = parent.ParentID
		}
		parentPath := strings.Join(breadcrumbParts, " > ")

		payload := map[string]any{
			"status":      "next",
			"step_id":     nextTask.ID,
			"step_name":   nextTask.Name,
			"agent":       agent,
			"description": nextTask.Description,
			"parent_path": parentPath,
			"context":     contextEntries,
		}
		if nextTask.VerificationCriteria != nil {
			payload["verification_criteria"] = *nextTask.VerificationCriteria
		}
		if contextEntries == nil {
			payload["context"] = []map[string]string{}
		}

		b, _ := json.Marshal(payload)
		return string(b), nil
	}

	// No ready task found
	descendants, err := s.repo.GetAllDescendants(rootID)
	if err != nil {
		return "", err
	}

	allDone := true
	for _, d := range descendants {
		if d.Status != domain.StatusDone {
			allDone = false
			break
		}
	}
	if allDone {
		b, _ := json.Marshal(map[string]any{
			"status":          "all_done",
			"root_id":         rootID,
			"completed_count": len(descendants),
		})
		return string(b), nil
	}

	var inProgress, blocked []map[string]string
	for _, d := range descendants {
		if d.Status == domain.StatusInProgress {
			inProgress = append(inProgress, map[string]string{"id": d.ID, "name": d.Name})
		} else if d.Status == domain.StatusPending {
			blocked = append(blocked, map[string]string{"id": d.ID, "name": d.Name})
		}
	}
	if inProgress == nil {
		inProgress = []map[string]string{}
	}
	if blocked == nil {
		blocked = []map[string]string{}
	}

	b, _ := json.Marshal(map[string]any{
		"status":      "waiting",
		"in_progress": inProgress,
		"blocked":     blocked,
	})
	return string(b), nil
}

// findDeepestReady recursively finds the deepest ready task under parentID.
func (s *Service) findDeepestReady(parentID string) (*domain.Task, error) {
	ready, err := s.repo.GetReadyTasks(&parentID)
	if err != nil || len(ready) == 0 {
		return nil, err
	}
	candidate := ready[0]
	children, _ := s.repo.GetChildren(candidate.ID)
	if len(children) > 0 {
		deeper, err := s.findDeepestReady(candidate.ID)
		if err == nil && deeper != nil {
			return deeper, nil
		}
	}
	return candidate, nil
}

// Context returns completed sibling outputs as context for a task.
func (s *Service) Context(taskID string, maxChars int) (string, error) {
	task, err := s.repo.GetTask(taskID)
	if err != nil || task == nil {
		return "error:not found", nil
	}

	if task.ParentID == nil {
		return "No context available (root task).", nil
	}

	siblings, err := s.repo.GetChildren(*task.ParentID)
	if err != nil {
		return "", err
	}

	var contextEntries []string
	for _, sib := range siblings {
		if sib.ID == taskID {
			break
		}
		if sib.Status == domain.StatusDone && sib.AgentOutput != nil {
			contextEntries = append(contextEntries, "## "+sib.Name+"\n"+*sib.AgentOutput)
		}
	}

	if len(contextEntries) == 0 {
		return "No context from prior steps.", nil
	}

	result := strings.Join(contextEntries, "\n\n")
	if len(result) > maxChars {
		result = result[:maxChars] + "\n...(truncated)"
	}
	return result, nil
}

// Update updates mutable fields of a task.
func (s *Service) Update(taskID string, fields map[string]any) (string, error) {
	task, err := s.repo.GetTask(taskID)
	if err != nil || task == nil {
		return "error:not found", nil
	}
	if len(fields) == 0 {
		return "error:no fields to update", nil
	}
	if _, err := s.repo.UpdateTask(taskID, fields); err != nil {
		return "", err
	}
	return "ok", nil
}

// Reorder sets the position of a task.
func (s *Service) Reorder(taskID string, position int) (string, error) {
	if position < 0 {
		return "error:position must be non-negative", nil
	}
	task, err := s.repo.GetTask(taskID)
	if err != nil || task == nil {
		return "error:not found", nil
	}
	if _, err := s.repo.UpdateTask(taskID, map[string]any{"position": position}); err != nil {
		return "", err
	}
	return "ok", nil
}

// Cleanup deletes completed root task trees older than N days.
func (s *Service) Cleanup(days int) (string, error) {
	if days < 0 {
		return "error:days must be non-negative", nil
	}
	count, err := s.repo.CleanupDoneRoots(days)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("ok|deleted:%d", count), nil
}

// formatDuration formats a duration into human-readable form (matching Python's _format_duration).
func formatDuration(d time.Duration) string {
	total := int(d.Seconds())
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
