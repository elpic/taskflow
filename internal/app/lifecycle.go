package app

import (
	"fmt"
	"strings"

	"github.com/elpic/taskflow/internal/domain"
)

// Start transitions a task to in_progress and sets it as the current task.
func (s *Service) Start(taskID string) (string, error) {
	task, err := s.repo.GetTask(taskID)
	if err != nil || task == nil {
		return "error:not found", nil
	}

	if err := domain.ValidateTransition(task.Status, domain.StatusInProgress); err != nil {
		return "error:" + err.Error(), nil
	}

	// Check blockers
	blockers, err := s.repo.GetBlockers(taskID)
	if err != nil {
		return "", err
	}
	var blocking []string
	for _, b := range blockers {
		if b.Status != domain.StatusDone {
			suffix := ""
			if b.Status == domain.StatusFailed {
				suffix = " (failed)"
			}
			blocking = append(blocking, b.ID+suffix)
		}
	}
	if len(blocking) > 0 {
		return "error:blocked by " + strings.Join(blocking, ","), nil
	}

	fields := domain.ComputeStartFields()
	if _, err := s.repo.UpdateTask(taskID, fields); err != nil {
		return "", err
	}
	if err := s.repo.SetCurrentTask(&taskID); err != nil {
		return "", err
	}
	_ = s.repo.LogEvent(taskID, domain.EventStarted, nil)
	return "ok", nil
}

// Complete transitions a task toward done (may create verify subtask).
func (s *Service) Complete(taskID, output, summary string) (string, error) {
	task, err := s.repo.GetTask(taskID)
	if err != nil || task == nil {
		return "error:not found", nil
	}

	children, err := s.repo.GetChildren(taskID)
	if err != nil {
		return "", err
	}

	var verifyChildren []*domain.Task
	var nonVerifyChildren []*domain.Task
	for _, c := range children {
		if strings.HasPrefix(c.Name, "Verify: ") {
			verifyChildren = append(verifyChildren, c)
		} else {
			nonVerifyChildren = append(nonVerifyChildren, c)
		}
	}

	// Validate completion preconditions before modifying state
	if task.VerificationCriteria != nil && *task.VerificationCriteria != "" && len(verifyChildren) == 0 {
		for _, c := range nonVerifyChildren {
			if c.Status != domain.StatusDone {
				return "error:children not done", nil
			}
		}
	}

	if task.Status == domain.StatusVerifying && len(verifyChildren) > 0 {
		allDone := true
		for _, c := range verifyChildren {
			if c.Status != domain.StatusDone {
				allDone = false
				break
			}
		}
		if !allDone {
			return "error:verification not done", nil
		}
	}

	if task.Status != domain.StatusPending && task.Status != domain.StatusInProgress && task.Status != domain.StatusVerifying {
		if err := domain.ValidateTransition(task.Status, domain.StatusDone); err != nil {
			return "error:" + err.Error(), nil
		}
	}

	// All preconditions passed — now modify state
	updateFields := map[string]any{}
	if output != "" {
		updateFields["agent_output"] = output
	}
	if summary != "" {
		updateFields["context_summary"] = summary
	}
	if len(updateFields) > 0 {
		if _, err := s.repo.UpdateTask(taskID, updateFields); err != nil {
			return "", err
		}
	}

	// Auto-start if still pending
	if task.Status == domain.StatusPending {
		startFields := domain.ComputeStartFields()
		if task, err = s.repo.UpdateTask(taskID, startFields); err != nil {
			return "", err
		}
	}

	// Create verification subtask if criteria exist and none created yet
	if task.VerificationCriteria != nil && *task.VerificationCriteria != "" && len(verifyChildren) == 0 {
		verifyName := "Verify: " + task.Name
		verifyTask, err := s.repo.CreateTask(
			verifyName,
			*task.VerificationCriteria,
			&taskID,
			nil,
			nil,
			nil,
		)
		if err != nil {
			return "", err
		}
		if _, err := s.repo.UpdateTask(taskID, map[string]any{"status": string(domain.StatusVerifying)}); err != nil {
			return "", err
		}
		return "verify:" + verifyTask.ID, nil
	}

	// Handle verifying state with verify children done
	if task.Status == domain.StatusVerifying && len(verifyChildren) > 0 {
		now := domain.NowUTC()
		if _, err := s.repo.UpdateTask(taskID, map[string]any{
			"status":       string(domain.StatusDone),
			"completed_at": now,
		}); err != nil {
			return "", err
		}
		details := map[string]any{}
		if output != "" {
			snippet := output
			if len(snippet) > 200 {
				snippet = snippet[:200]
			}
			details["output_snippet"] = snippet
		}
		if len(details) == 0 {
			details = nil
		}
		_ = s.repo.LogEvent(taskID, domain.EventCompleted, details)
		_ = s.hooks.Fire(domain.HookOnTaskComplete, taskID, task.Name, "done")
		_ = s.checkWorkflowComplete(task)
		return s.appendUnblocked(taskID, "ok")
	}

	// Normal path
	fields, err := domain.ComputeCompleteFieldsFull(task, children)
	if err != nil {
		return "error:" + err.Error(), nil
	}
	if err := domain.ValidateTransition(task.Status, domain.TaskStatus(fields["status"].(string))); err != nil {
		return "error:" + err.Error(), nil
	}

	if _, err := s.repo.UpdateTask(taskID, fields); err != nil {
		return "", err
	}

	if fields["status"] == string(domain.StatusDone) {
		details := map[string]any{}
		if output != "" {
			snippet := output
			if len(snippet) > 200 {
				snippet = snippet[:200]
			}
			details["output_snippet"] = snippet
		}
		if len(details) == 0 {
			details = nil
		}
		_ = s.repo.LogEvent(taskID, domain.EventCompleted, details)
		_ = s.hooks.Fire(domain.HookOnTaskComplete, taskID, task.Name, "done")
		_ = s.checkWorkflowComplete(task)
		return s.appendUnblocked(taskID, "ok")
	}
	return "ok", nil
}

// checkWorkflowComplete fires the workflow complete hook if all siblings under a root are done.
func (s *Service) checkWorkflowComplete(task *domain.Task) error {
	if task.ParentID == nil {
		return nil
	}
	parent, err := s.repo.GetTask(*task.ParentID)
	if err != nil || parent == nil {
		return nil
	}
	if parent.ParentID != nil {
		return nil // Parent is not a root task
	}
	siblings, err := s.repo.GetChildren(*task.ParentID)
	if err != nil {
		return nil
	}
	for _, s := range siblings {
		if s.Status != domain.StatusDone {
			return nil
		}
	}
	_ = s.hooks.Fire(domain.HookOnWorkflowComplete, *task.ParentID, parent.Name, "done")
	return nil
}

// appendUnblocked appends |unblocked:<ids> to base if dependents become unblocked.
func (s *Service) appendUnblocked(completedTaskID, base string) (string, error) {
	dependents, err := s.repo.GetDependents(completedTaskID)
	if err != nil {
		return base, nil
	}
	var newly []string
	for _, dep := range dependents {
		if dep.Status != domain.StatusPending {
			continue
		}
		blockers, err := s.repo.GetBlockers(dep.ID)
		if err != nil {
			continue
		}
		allDone := true
		for _, b := range blockers {
			if b.Status != domain.StatusDone {
				allDone = false
				break
			}
		}
		if allDone {
			newly = append(newly, dep.ID)
		}
	}
	if len(newly) > 0 {
		return base + "|unblocked:" + strings.Join(newly, ","), nil
	}
	return base, nil
}

// Fail marks a task as failed.
func (s *Service) Fail(taskID, reason string) (string, error) {
	task, err := s.repo.GetTask(taskID)
	if err != nil || task == nil {
		return "error:not found", nil
	}

	if err := domain.ValidateTransition(task.Status, domain.StatusFailed); err != nil {
		return "error:" + err.Error(), nil
	}

	fields := domain.ComputeFailFields(reason)
	if _, err := s.repo.UpdateTask(taskID, fields); err != nil {
		return "", err
	}
	_ = s.repo.LogEvent(taskID, domain.EventFailed, map[string]any{"reason": reason})
	_ = s.hooks.Fire(domain.HookOnTaskFail, taskID, task.Name, "failed")
	return "ok", nil
}

// Reset resets a task back to pending.
func (s *Service) Reset(taskID string, recursive bool) (string, error) {
	task, err := s.repo.GetTask(taskID)
	if err != nil || task == nil {
		return "error:not found", nil
	}

	if task.Status != domain.StatusDone && task.Status != domain.StatusFailed {
		return fmt.Sprintf("error:can only reset done or failed tasks (current: %s)", task.Status), nil
	}

	idsToReset := []string{taskID}
	if recursive {
		descendants, err := s.repo.GetAllDescendants(taskID)
		if err != nil {
			return "", err
		}
		for _, d := range descendants {
			idsToReset = append(idsToReset, d.ID)
		}
	}

	for _, id := range idsToReset {
		if err := s.repo.ResetTask(id); err != nil {
			return "", err
		}
	}
	_ = s.repo.LogEvent(taskID, domain.EventReset, map[string]any{"recursive": recursive})
	return "ok", nil
}

// Delete deletes a task and all its descendants.
func (s *Service) Delete(taskID string) (string, error) {
	task, err := s.repo.GetTask(taskID)
	if err != nil || task == nil {
		return "error:not found", nil
	}

	if task.Status == domain.StatusInProgress {
		return "error:cannot delete in-progress task", nil
	}

	_ = s.repo.LogEvent(taskID, domain.EventDeleted, map[string]any{"name": task.Name})
	if err := s.repo.DeleteTask(taskID); err != nil {
		return "", err
	}
	return "ok", nil
}

// Move moves a task to a new parent.
func (s *Service) Move(taskID string, newParentID *string) (string, error) {
	task, err := s.repo.GetTask(taskID)
	if err != nil || task == nil {
		return "error:not found", nil
	}

	if newParentID != nil {
		parent, err := s.repo.GetTask(*newParentID)
		if err != nil || parent == nil {
			return "error:parent not found", nil
		}
	}

	oldParentID := task.ParentID
	if err := s.repo.MoveTask(taskID, newParentID); err != nil {
		return "error:" + err.Error(), nil
	}

	_ = s.repo.LogEvent(taskID, domain.EventMoved, map[string]any{
		"old_parent_id": oldParentID,
		"new_parent_id": newParentID,
	})
	return "ok", nil
}
