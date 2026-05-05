package app

import (
	"fmt"
	"strings"

	"github.com/elpic/taskflow/internal/domain"
)

// CreateTaskInput holds the inputs for task creation.
type CreateTaskInput struct {
	Name                 string
	Description          string
	ParentID             *string
	VerificationCriteria *string
	TaskType             *string
	IdempotencyKey       *string
	BlockedBy            []string
}

// CreateTaskResult holds the MCP-wire response for task_create.
type CreateTaskResult struct {
	Response string
}

// CreateTask creates a task and optionally expands a workflow type.
// Returns the MCP wire-format response string.
func (s *Service) CreateTask(input CreateTaskInput, hint *HintOnce) (string, error) {
	// Idempotency check
	if input.IdempotencyKey != nil && *input.IdempotencyKey != "" {
		existing, err := s.repo.FindByIdempotencyKey(*input.IdempotencyKey)
		if err == nil && existing != nil {
			return existing.ID, nil
		}
	}

	// Validate task_type before touching the DB
	var workflow *domain.Workflow
	if input.TaskType != nil && *input.TaskType != "" {
		wf, err := s.workflows.GetWorkflow(*input.TaskType)
		if err != nil {
			return "error:" + err.Error(), nil
		}
		workflow = wf
	}

	// Snapshot emptiness before insert
	hasTasksBefore, err := s.repo.HasTasks()
	if err != nil {
		return "", fmt.Errorf("checking tasks: %w", err)
	}
	dbWasEmpty := !hasTasksBefore

	// Create root task
	task, err := s.repo.CreateTask(
		input.Name,
		input.Description,
		input.ParentID,
		input.VerificationCriteria,
		nil,
		input.IdempotencyKey,
	)
	if err != nil {
		return "error:" + err.Error(), nil
	}

	// Wire dependencies for the root task
	if len(input.BlockedBy) > 0 {
		if err := s.repo.AddDependencies(task.ID, input.BlockedBy); err != nil {
			_ = s.repo.DeleteTask(task.ID)
			return "error:" + err.Error(), nil
		}
	}

	// Log creation event
	_ = s.repo.LogEvent(task.ID, domain.EventCreated, map[string]any{
		"name":      task.Name,
		"parent_id": input.ParentID,
	})

	// Expand workflow if requested
	if workflow != nil {
		stepInfo, err := s.expandWorkflow(task.ID, *input.TaskType, workflow)
		if err != nil {
			_ = s.repo.DeleteTask(task.ID)
			return "error:" + err.Error(), nil
		}
		hintStr := hint.Consume(dbWasEmpty)
		return task.ID + "|" + *input.TaskType + "|" + strings.Join(stepInfo, ",") + hintStr, nil
	}

	hintStr := hint.Consume(dbWasEmpty)
	return task.ID + hintStr, nil
}

// expandWorkflow creates subtasks for all steps in a workflow.
// Returns step info strings like "<id>:@<agent>" and any error.
func (s *Service) expandWorkflow(rootID, taskType string, workflow *domain.Workflow) ([]string, error) {
	stepInfo := make([]string, 0, len(workflow.Steps))
	nameToID := make(map[string]string, len(workflow.Steps))

	// First pass: create all step tasks
	for _, step := range workflow.Steps {
		meta := map[string]any{"agent": step.Agent}
		if step.Agent == "" {
			meta["agent"] = "self"
		}

		vc := (*string)(nil)
		if step.VerificationCriteria != "" {
			vc = &step.VerificationCriteria
		}

		stepTask, err := s.repo.CreateTask(
			step.Name,
			step.Description,
			&rootID,
			vc,
			meta,
			nil,
		)
		if err != nil {
			return nil, fmt.Errorf("creating step '%s': %w", step.Name, err)
		}
		nameToID[step.Name] = stepTask.ID

		agentTag := "@" + step.Agent
		if step.Agent == "" {
			agentTag = "@self"
		}
		stepInfo = append(stepInfo, stepTask.ID+":"+agentTag)
	}

	// Second pass: wire dependencies
	for i, step := range workflow.Steps {
		stepID := nameToID[step.Name]
		if step.ExplicitDeps {
			// Explicit dependencies from depends_on
			if len(step.DependsOn) > 0 {
				depIDs := make([]string, 0, len(step.DependsOn))
				for _, depName := range step.DependsOn {
					depID, ok := nameToID[depName]
					if !ok {
						return nil, fmt.Errorf("workflow '%s' step '%s' depends_on unknown step '%s'",
							taskType, step.Name, depName)
					}
					depIDs = append(depIDs, depID)
				}
				if err := s.repo.AddDependencies(stepID, depIDs); err != nil {
					return nil, fmt.Errorf("adding deps for step '%s': %w", step.Name, err)
				}
			}
			// depends_on: [] means no deps, intentionally no linking
		} else {
			// Linear chain: depends on previous step
			if i > 0 {
				prevID := nameToID[workflow.Steps[i-1].Name]
				if err := s.repo.AddDependencies(stepID, []string{prevID}); err != nil {
					return nil, fmt.Errorf("adding linear dep for step '%s': %w", step.Name, err)
				}
			}
		}
	}

	return stepInfo, nil
}
