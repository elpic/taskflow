package domain

// EventType constants for task audit events.
const (
	EventCreated         = "created"
	EventStarted         = "started"
	EventCompleted       = "completed"
	EventFailed          = "failed"
	EventReset           = "reset"
	EventDeleted         = "deleted"
	EventMoved           = "moved"
	EventRetried         = "retried"
	EventRetryExhausted  = "retry_exhausted"
	EventHookError       = "hook_error"
)

// Event represents a single entry in the task event log.
type Event struct {
	ID        int64
	TaskID    string
	EventType string
	Timestamp string
	Details   string // raw JSON
}
