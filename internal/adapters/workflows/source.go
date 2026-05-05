package workflows

import (
	"embed"
	"fmt"
	"io/fs"
	"sort"
	"strings"
	"sync"

	"gopkg.in/yaml.v3"

	"github.com/elpic/taskflow/internal/domain"
)

//go:embed builtin/*.yaml
var builtinFS embed.FS

// Source implements domain.WorkflowSource, combining builtin and custom workflows.
type Source struct {
	mu       sync.RWMutex
	builtin  map[string]*domain.Workflow
	custom   map[string]*domain.Workflow
	customDir string
}

// NewSource creates a workflow Source and loads all builtin workflows.
func NewSource(customDir string) (*Source, error) {
	s := &Source{
		customDir: customDir,
	}
	if err := s.loadBuiltin(); err != nil {
		return nil, fmt.Errorf("loading builtin workflows: %w", err)
	}
	s.custom = make(map[string]*domain.Workflow)
	s.loadCustomDir()
	return s, nil
}

// GetWorkflow returns a workflow by type name.
func (s *Source) GetWorkflow(taskType string) (*domain.Workflow, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if wf, ok := s.custom[taskType]; ok {
		return wf, nil
	}
	if wf, ok := s.builtin[taskType]; ok {
		return wf, nil
	}
	valid := s.listTypesLocked()
	return nil, fmt.Errorf("invalid task_type '%s'. Valid types: %s", taskType, strings.Join(valid, ", "))
}

// ListTypes returns all available workflow type names (builtin first, then custom).
func (s *Source) ListTypes() []string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.listTypesLocked()
}

func (s *Source) listTypesLocked() []string {
	// Return builtins in their canonical order
	builtinOrder := []string{
		"simple", "implement", "bugfix", "refactor", "research",
		"secure-implement", "product", "discover", "setup", "sprint",
	}
	seen := make(map[string]bool)
	result := make([]string, 0)
	for _, name := range builtinOrder {
		if _, ok := s.builtin[name]; ok {
			result = append(result, name)
			seen[name] = true
		}
	}
	// Add custom workflows not already in builtin
	custom := make([]string, 0, len(s.custom))
	for name := range s.custom {
		if !seen[name] {
			custom = append(custom, name)
		}
	}
	sort.Strings(custom)
	result = append(result, custom...)
	return result
}

// rawWorkflow is the YAML deserialization target.
type rawWorkflow struct {
	Name  string    `yaml:"name"`
	Steps []rawStep `yaml:"steps"`
}

type rawStep struct {
	Name                 string   `yaml:"name"`
	Description          string   `yaml:"description"`
	VerificationCriteria string   `yaml:"verification_criteria"`
	Agent                string   `yaml:"agent"`
	DependsOn            *[]string `yaml:"depends_on"` // pointer to distinguish nil vs []
}

func (s *Source) loadBuiltin() error {
	s.builtin = make(map[string]*domain.Workflow)

	entries, err := fs.ReadDir(builtinFS, "builtin")
	if err != nil {
		return fmt.Errorf("reading builtin dir: %w", err)
	}

	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		name := entry.Name()
		if !strings.HasSuffix(name, ".yaml") && !strings.HasSuffix(name, ".yml") {
			continue
		}

		data, err := builtinFS.ReadFile("builtin/" + name)
		if err != nil {
			return fmt.Errorf("reading %s: %w", name, err)
		}

		wf, err := parseWorkflow(data)
		if err != nil {
			return fmt.Errorf("parsing %s: %w", name, err)
		}

		// Validate
		if errs := wf.Validate(); len(errs) > 0 {
			return fmt.Errorf("builtin workflow %s is invalid: %s", name, strings.Join(errs, "; "))
		}

		s.builtin[wf.Name] = wf
	}
	return nil
}

func (s *Source) loadCustomDir() {
	if s.customDir == "" {
		return
	}

	entries, err := customFS_ReadDir(s.customDir)
	if err != nil {
		return // directory doesn't exist or not accessible
	}

	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		name := entry.Name()
		if !strings.HasSuffix(name, ".yaml") && !strings.HasSuffix(name, ".yml") {
			continue
		}

		data, err := readFile(s.customDir, name)
		if err != nil {
			continue // skip invalid
		}

		wf, err := parseWorkflow(data)
		if err != nil {
			continue
		}

		if errs := wf.Validate(); len(errs) > 0 {
			continue
		}

		s.custom[wf.Name] = wf
	}
}

// parseWorkflow parses YAML bytes into a domain.Workflow.
func parseWorkflow(data []byte) (*domain.Workflow, error) {
	var raw rawWorkflow
	if err := yaml.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("yaml unmarshal: %w", err)
	}
	if raw.Name == "" {
		return nil, fmt.Errorf("workflow missing 'name' field")
	}
	if len(raw.Steps) == 0 {
		return nil, fmt.Errorf("workflow '%s' has no steps", raw.Name)
	}

	steps := make([]domain.WorkflowStep, len(raw.Steps))
	for i, rs := range raw.Steps {
		if rs.Name == "" {
			return nil, fmt.Errorf("step %d missing 'name'", i)
		}
		step := domain.WorkflowStep{
			Name:                 rs.Name,
			Description:          rs.Description,
			VerificationCriteria: rs.VerificationCriteria,
			Agent:                rs.Agent,
		}
		if rs.DependsOn != nil {
			step.ExplicitDeps = true
			step.DependsOn = *rs.DependsOn
		}
		steps[i] = step
	}

	return &domain.Workflow{
		Name:  raw.Name,
		Steps: steps,
	}, nil
}
