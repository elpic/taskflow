package hooks

import (
	"encoding/json"
	"fmt"

	"github.com/elpic/taskflow/internal/domain"
)

// handleRetry auto-retries a failed task by resetting it.
func handleRetry(handler domain.HookHandler, taskID, taskName string, repo domain.TaskRepository) error {
	maxRetries := handler.MaxRetries
	if maxRetries == 0 {
		maxRetries = 3
	}

	task, err := repo.GetTask(taskID)
	if err != nil || task == nil {
		return nil
	}

	// Track retry count in metadata
	var meta map[string]any
	if task.Metadata != "" {
		_ = json.Unmarshal([]byte(task.Metadata), &meta)
	}
	if meta == nil {
		meta = map[string]any{}
	}

	retryCount := 0
	if v, ok := meta["retry_count"].(float64); ok {
		retryCount = int(v)
	}

	if retryCount >= maxRetries {
		_ = repo.LogEvent(taskID, domain.EventRetryExhausted, map[string]any{
			"retry_count": retryCount,
			"max_retries": maxRetries,
		})
		return nil
	}

	// Reset the task and increment retry count
	if err := repo.ResetTask(taskID); err != nil {
		return fmt.Errorf("resetting task for retry: %w", err)
	}
	meta["retry_count"] = retryCount + 1
	metaJSON, _ := json.Marshal(meta)
	if _, err := repo.UpdateTask(taskID, map[string]any{"metadata": string(metaJSON)}); err != nil {
		return fmt.Errorf("updating metadata for retry: %w", err)
	}
	_ = repo.LogEvent(taskID, domain.EventRetried, map[string]any{
		"retry_count": retryCount + 1,
		"max_retries": maxRetries,
	})
	_ = taskName // suppress unused warning
	return nil
}
