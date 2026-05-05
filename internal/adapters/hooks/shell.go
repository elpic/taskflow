package hooks

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"time"

	"github.com/elpic/taskflow/internal/domain"
)

const shellTimeout = 30 * time.Second

// execShell runs a shell command with TASKFLOW_* environment variables.
func execShell(handler domain.HookHandler, taskID, taskName, event, status string) error {
	if handler.Command == "" {
		return nil
	}

	env := os.Environ()
	env = append(env,
		"TASKFLOW_TASK_ID="+taskID,
		"TASKFLOW_TASK_NAME="+taskName,
		"TASKFLOW_EVENT="+event,
		"TASKFLOW_STATUS="+status,
	)
	for k, v := range handler.Env {
		env = append(env, fmt.Sprintf("%s=%s", k, v))
	}

	ctx, cancel := context.WithTimeout(context.Background(), shellTimeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, "sh", "-c", handler.Command)
	cmd.Env = env
	cmd.Stdout = nil
	cmd.Stderr = nil

	if err := cmd.Run(); err != nil {
		if ctx.Err() == context.DeadlineExceeded {
			return fmt.Errorf("shell hook timed out after %s: %s", shellTimeout, handler.Command)
		}
		return fmt.Errorf("shell hook failed: %w", err)
	}
	return nil
}
