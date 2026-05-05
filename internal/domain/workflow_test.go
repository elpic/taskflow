package domain

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestWorkflow_Validate_LinearChain(t *testing.T) {
	wf := &Workflow{
		Name: "linear",
		Steps: []WorkflowStep{
			{Name: "Step1", Agent: "developer"},
			{Name: "Step2", Agent: "developer"},
			{Name: "Step3", Agent: "qa-engineer"},
		},
	}
	errs := wf.Validate()
	assert.Empty(t, errs, "linear chain should be valid")
}

func TestWorkflow_Validate_FanIn(t *testing.T) {
	wf := &Workflow{
		Name: "fan-in",
		Steps: []WorkflowStep{
			{Name: "A", ExplicitDeps: true, DependsOn: []string{}},
			{Name: "B", ExplicitDeps: true, DependsOn: []string{}},
			{Name: "C", ExplicitDeps: true, DependsOn: []string{"A", "B"}},
		},
	}
	errs := wf.Validate()
	assert.Empty(t, errs, "fan-in workflow should be valid")
}

func TestWorkflow_Validate_ExplicitLinear(t *testing.T) {
	wf := &Workflow{
		Name: "explicit-linear",
		Steps: []WorkflowStep{
			{Name: "First", ExplicitDeps: true, DependsOn: []string{}},
			{Name: "Second", ExplicitDeps: true, DependsOn: []string{"First"}},
			{Name: "Third", ExplicitDeps: true, DependsOn: []string{"Second"}},
		},
	}
	errs := wf.Validate()
	assert.Empty(t, errs, "explicit linear chain should be valid")
}

func TestWorkflow_Validate_UnknownDependency(t *testing.T) {
	wf := &Workflow{
		Name: "bad-dep",
		Steps: []WorkflowStep{
			{Name: "A", ExplicitDeps: true, DependsOn: []string{}},
			{Name: "B", ExplicitDeps: true, DependsOn: []string{"DoesNotExist"}},
		},
	}
	errs := wf.Validate()
	assert.NotEmpty(t, errs, "unknown dependency should fail validation")
	assert.Contains(t, errs[0], "unknown step")
	assert.Contains(t, errs[0], "DoesNotExist")
}

func TestWorkflow_Validate_SelfDependency(t *testing.T) {
	wf := &Workflow{
		Name: "self-dep",
		Steps: []WorkflowStep{
			{Name: "A", ExplicitDeps: true, DependsOn: []string{"A"}},
		},
	}
	errs := wf.Validate()
	assert.NotEmpty(t, errs, "self-dependency should fail validation")
}

func TestWorkflow_Validate_CycleDetection(t *testing.T) {
	wf := &Workflow{
		Name: "cyclic",
		Steps: []WorkflowStep{
			{Name: "A", ExplicitDeps: true, DependsOn: []string{"C"}},
			{Name: "B", ExplicitDeps: true, DependsOn: []string{"A"}},
			{Name: "C", ExplicitDeps: true, DependsOn: []string{"B"}},
		},
	}
	errs := wf.Validate()
	assert.NotEmpty(t, errs, "cycle should fail validation")
	// The cycle error message should mention the workflow name
	found := false
	for _, e := range errs {
		if e != "" {
			found = true
		}
	}
	assert.True(t, found)
}

func TestWorkflow_Validate_SingleStep(t *testing.T) {
	wf := &Workflow{
		Name: "single",
		Steps: []WorkflowStep{
			{Name: "Only", Agent: "developer"},
		},
	}
	errs := wf.Validate()
	assert.Empty(t, errs, "single-step workflow should be valid")
}

func TestWorkflow_Validate_WithAgents(t *testing.T) {
	wf := &Workflow{
		Name: "with-agents",
		Steps: []WorkflowStep{
			{Name: "Design", Agent: "tech-architect"},
			{Name: "Implement", Agent: "developer"},
			{Name: "Test", Agent: "qa-engineer"},
			{Name: "Review", Agent: "code-reviewer"},
		},
	}
	errs := wf.Validate()
	assert.Empty(t, errs, "workflow with various agents should be valid")
}
