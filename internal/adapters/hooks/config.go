package hooks

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/elpic/taskflow/internal/domain"
)

// rawConfig is the deserialization target for hooks.json.
type rawConfig struct {
	Hooks map[string][]rawHandler `json:"hooks"`
}

type rawHandler struct {
	Type       string            `json:"type"`
	Command    string            `json:"command"`
	Action     string            `json:"action"`
	MaxRetries int               `json:"max_retries"`
	Env        map[string]string `json:"env"`
}

// LoadConfig loads hook configuration from a JSON file.
// Returns an empty config if the file doesn't exist.
func LoadConfig(path string) (*domain.HookConfig, error) {
	data, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return &domain.HookConfig{Hooks: map[string][]domain.HookHandler{}}, nil
	}
	if err != nil {
		return nil, fmt.Errorf("reading hooks file: %w", err)
	}

	var raw rawConfig
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("parsing hooks file: %w", err)
	}

	validEvents := map[string]bool{
		domain.HookOnTaskComplete:     true,
		domain.HookOnTaskFail:         true,
		domain.HookOnWorkflowComplete: true,
	}

	config := &domain.HookConfig{
		Hooks: make(map[string][]domain.HookHandler),
	}

	for eventName, rawHandlers := range raw.Hooks {
		if !validEvents[eventName] {
			continue // skip unknown events (log-and-ignore like Python)
		}
		handlers := make([]domain.HookHandler, 0, len(rawHandlers))
		for _, rh := range rawHandlers {
			h := domain.HookHandler{
				Type:       rh.Type,
				Command:    rh.Command,
				Action:     rh.Action,
				MaxRetries: rh.MaxRetries,
				Env:        rh.Env,
			}
			if h.MaxRetries == 0 && rh.Action == "retry" {
				h.MaxRetries = 3 // default
			}
			handlers = append(handlers, h)
		}
		config.Hooks[eventName] = handlers
	}

	return config, nil
}
