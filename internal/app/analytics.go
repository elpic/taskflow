package app

import (
	"fmt"
	"strings"
)

// AnalyticsRepository is implemented by the SQLite repository to provide
// aggregate workflow metrics. The app.Service uses a type assertion to
// check whether the injected repository supports analytics.
type AnalyticsRepository interface {
	WorkflowSummary(days int) (string, error)
	StepBottlenecks(days int) (string, error)
	AgentPerformance(days int) (string, error)
	Velocity(days int) (string, error)
}

// Analytics dispatches analytics queries to the repository.
func (s *Service) Analytics(query string, days int) (string, error) {
	ar, ok := s.repo.(AnalyticsRepository)
	if !ok {
		return "error:analytics not supported by repository", nil
	}
	switch query {
	case "workflow_summary":
		return ar.WorkflowSummary(days)
	case "step_bottlenecks":
		return ar.StepBottlenecks(days)
	case "agent_performance":
		return ar.AgentPerformance(days)
	case "velocity":
		return ar.Velocity(days)
	default:
		return fmt.Sprintf("error:unknown query '%s'. Valid: agent_performance, step_bottlenecks, velocity, workflow_summary", query), nil
	}
}

// TaskTypes returns the list of workflow types and their steps.
func (s *Service) TaskTypes(hint *HintOnce) (string, error) {
	types := s.workflows.ListTypes()

	var lines []string
	for _, typeName := range types {
		wf, err := s.workflows.GetWorkflow(typeName)
		if err != nil {
			continue
		}
		stepNames := make([]string, len(wf.Steps))
		for i, step := range wf.Steps {
			stepNames[i] = step.Name
		}
		lines = append(lines, typeName+": "+strings.Join(stepNames, " → "))
	}

	result := strings.Join(lines, "\n")

	// The hint check for task_types queries the DB to see if it was empty.
	hasTasksBefore, err := s.repo.HasTasks()
	if err != nil {
		return result, nil
	}
	hintStr := hint.Consume(!hasTasksBefore)
	return result + hintStr, nil
}

