package app

import "sync"

const firstRunHint = "\n\n---\n" +
	"💡 Hint: Create tasks with task_type to auto-generate workflow steps:\n" +
	"  task_create(name=\"Fix login bug\", task_type=\"bugfix\")\n\n" +
	"Available types: simple, implement, bugfix, refactor, research, " +
	"secure-implement, product, sprint, discover, setup\n" +
	"Use task_types() for full workflow details."

// HintOnce manages the first-run hint shown once per session.
type HintOnce struct {
	once sync.Once
	used bool
}

// Consume marks the hint as used and returns it if this is the first call.
// If dbWasEmpty is false, returns empty string (hint only shows when DB was empty).
func (h *HintOnce) Consume(dbWasEmpty bool) string {
	result := ""
	h.once.Do(func() {
		h.used = true
		if dbWasEmpty {
			result = firstRunHint
		}
	})
	return result
}
