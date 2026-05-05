package domain

// WorkflowStep describes one step in a workflow.
type WorkflowStep struct {
	Name                 string
	Description          string
	VerificationCriteria string
	Agent                string
	// DependsOn is nil for linear chaining, empty slice for no deps,
	// or a list of step names this step depends on.
	DependsOn []string
	// dependsOnSet is set to true when DependsOn was explicitly specified (even if empty).
	ExplicitDeps bool
}

// Workflow is a named sequence of steps.
type Workflow struct {
	Name  string
	Steps []WorkflowStep
}

// Validate checks depends_on references and detects cycles.
// Returns a list of error strings (empty = valid).
func (w *Workflow) Validate() []string {
	var errors []string
	stepNames := make(map[string]bool, len(w.Steps))
	for _, s := range w.Steps {
		stepNames[s.Name] = true
	}

	for _, step := range w.Steps {
		if step.ExplicitDeps {
			for _, dep := range step.DependsOn {
				if !stepNames[dep] {
					errors = append(errors, "step '"+step.Name+"' depends_on unknown step '"+dep+"'")
				}
				if dep == step.Name {
					errors = append(errors, "step '"+step.Name+"' depends on itself")
				}
			}
		}
	}

	if len(errors) > 0 {
		return errors
	}

	// Kahn's algorithm for cycle detection
	inDegree := make(map[string]int, len(w.Steps))
	adj := make(map[string][]string, len(w.Steps))
	for i := range w.Steps {
		inDegree[w.Steps[i].Name] = 0
		adj[w.Steps[i].Name] = nil
	}

	for i, step := range w.Steps {
		var deps []string
		if step.ExplicitDeps {
			deps = step.DependsOn
		} else if i > 0 {
			deps = []string{w.Steps[i-1].Name}
		}
		for _, dep := range deps {
			adj[dep] = append(adj[dep], step.Name)
			inDegree[step.Name]++
		}
	}

	queue := make([]string, 0)
	for name, deg := range inDegree {
		if deg == 0 {
			queue = append(queue, name)
		}
	}

	visited := 0
	for len(queue) > 0 {
		node := queue[0]
		queue = queue[1:]
		visited++
		for _, neighbor := range adj[node] {
			inDegree[neighbor]--
			if inDegree[neighbor] == 0 {
				queue = append(queue, neighbor)
			}
		}
	}

	if visited != len(w.Steps) {
		errors = append(errors, "workflow '"+w.Name+"' contains a cycle")
	}

	return errors
}
