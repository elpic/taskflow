package hooks

import (
	"github.com/elpic/taskflow/internal/domain"
)

// Runner implements domain.HookRunner.
type Runner struct {
	config *domain.HookConfig
	repo   domain.TaskRepository
}

// NewRunner creates a hook runner with the given config and repository.
func NewRunner(config *domain.HookConfig, repo domain.TaskRepository) *Runner {
	return &Runner{config: config, repo: repo}
}

// Fire executes all handlers for an event. Errors are logged, never propagated.
func (r *Runner) Fire(event, taskID, taskName, status string) error {
	if r.config == nil {
		return nil
	}
	handlers, ok := r.config.Hooks[event]
	if !ok {
		return nil
	}

	for _, handler := range handlers {
		switch handler.Type {
		case "shell":
			// Errors are logged and ignored per Python behavior
			_ = execShell(handler, taskID, taskName, event, status)
		case "builtin":
			if handler.Action == "retry" {
				_ = handleRetry(handler, taskID, taskName, r.repo)
			}
		}
	}
	return nil
}
