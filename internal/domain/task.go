package domain

import "encoding/json"

// TaskStatus represents the lifecycle state of a task.
type TaskStatus string

const (
	StatusPending    TaskStatus = "pending"
	StatusInProgress TaskStatus = "in_progress"
	StatusVerifying  TaskStatus = "verifying"
	StatusDone       TaskStatus = "done"
	StatusFailed     TaskStatus = "failed"
)

var statusIcons = map[TaskStatus]string{
	StatusPending:    "○",
	StatusInProgress: "◈",
	StatusVerifying:  "◇",
	StatusDone:       "◉",
	StatusFailed:     "✗",
}

var statusLabels = map[TaskStatus]string{
	StatusPending:    "pending",
	StatusInProgress: "in_progress",
	StatusVerifying:  "verifying",
	StatusDone:       "done ✓",
	StatusFailed:     "failed",
}

// Task is the core domain entity.
type Task struct {
	ID                   string
	Name                 string
	Description          string
	Status               TaskStatus
	ParentID             *string
	VerificationCriteria *string
	VerificationResult   *string
	Metadata             string // raw JSON, default "{}"
	CreatedAt            string // RFC3339 UTC
	StartedAt            *string
	CompletedAt          *string
	AgentOutput          *string
	ContextSummary       *string
	Position             *int
	IdempotencyKey       *string
	Children             []*Task // populated by tree builder only
}

// MetadataMap parses the Metadata JSON into a map.
func (t *Task) MetadataMap() map[string]any {
	var m map[string]any
	_ = json.Unmarshal([]byte(t.Metadata), &m)
	if m == nil {
		m = map[string]any{}
	}
	return m
}

// Icon returns the display icon for the task's status.
func (t *Task) Icon() string {
	if icon, ok := statusIcons[t.Status]; ok {
		return icon
	}
	return "?"
}

// Label returns the display label for the task's status.
func (t *Task) Label() string {
	if label, ok := statusLabels[t.Status]; ok {
		return label
	}
	return string(t.Status)
}
