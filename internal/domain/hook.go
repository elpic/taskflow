package domain

// HookEvent constants for lifecycle events.
const (
	HookOnTaskComplete    = "on_task_complete"
	HookOnTaskFail        = "on_task_fail"
	HookOnWorkflowComplete = "on_workflow_complete"
)

// HookHandler describes a single hook handler loaded from config.
type HookHandler struct {
	Type      string // "shell" or "builtin"
	Command   string // for shell handlers
	Action    string // for builtin handlers
	MaxRetries int   // for builtin retry action
	Env       map[string]string
}

// HookConfig holds the parsed hooks.json configuration.
type HookConfig struct {
	Hooks map[string][]HookHandler
}

// HookRunner fires lifecycle hook events.
type HookRunner interface {
	Fire(event, taskID, taskName, status string) error
}
