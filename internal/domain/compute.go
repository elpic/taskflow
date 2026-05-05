package domain

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"
)

// NowUTC returns the current time formatted to match Python's datetime.now(UTC).isoformat().
// Python produces e.g. "2024-01-15T10:30:00.123456+00:00"
func NowUTC() string {
	return time.Now().UTC().Format("2006-01-02T15:04:05.999999-07:00")
}

// ComputeStartFields returns the field updates for starting a task.
func ComputeStartFields() map[string]any {
	now := NowUTC()
	return map[string]any{
		"status":     string(StatusInProgress),
		"started_at": now,
	}
}

// ComputeCompleteFieldsFull mirrors Python's compute_complete_fields exactly.
// Returns field updates for completing a task, or an error if preconditions aren't met.
func ComputeCompleteFieldsFull(task *Task, children []*Task) (map[string]any, error) {
	var incomplete []*Task
	for _, c := range children {
		if c.Status != StatusDone {
			incomplete = append(incomplete, c)
		}
	}
	if len(incomplete) > 0 {
		names := make([]string, len(incomplete))
		for i, c := range incomplete {
			names[i] = fmt.Sprintf("'%s' (%s)", c.Name, c.Status)
		}
		return nil, fmt.Errorf("Cannot complete '%s': %d child task(s) not done: %s",
			task.Name, len(incomplete), strings.Join(names, ", "))
	}

	if task.VerificationCriteria != nil && *task.VerificationCriteria != "" {
		return map[string]any{
			"status": string(StatusVerifying),
		}, nil
	}

	now := NowUTC()
	return map[string]any{
		"status":       string(StatusDone),
		"completed_at": now,
	}, nil
}

// ComputeVerifyFields returns field updates for a verification result.
func ComputeVerifyFields(passed bool, details string) map[string]any {
	result, _ := json.Marshal(map[string]any{"passed": passed, "details": details})
	if passed {
		now := NowUTC()
		return map[string]any{
			"status":              string(StatusDone),
			"verification_result": string(result),
			"completed_at":        now,
		}
	}
	return map[string]any{
		"status":              string(StatusInProgress),
		"verification_result": string(result),
	}
}

// ComputeFailFields returns field updates for a failed task.
func ComputeFailFields(reason string) map[string]any {
	result, _ := json.Marshal(map[string]any{"passed": false, "details": reason})
	return map[string]any{
		"status":              string(StatusFailed),
		"verification_result": string(result),
	}
}
