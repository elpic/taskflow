package app

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// createWorkflow creates a typed workflow task and returns rootID and raw step entries.
func createWorkflow(t *testing.T, svc *Service, name, taskType string) (rootID string, stepEntries []string) {
	t.Helper()
	raw, err := svc.CreateTask(CreateTaskInput{Name: name, TaskType: &taskType}, consumedHint())
	require.NoError(t, err)
	result := stripHint(raw)
	parts := strings.SplitN(result, "|", 3)
	require.Len(t, parts, 3)
	return parts[0], strings.Split(parts[2], ",")
}

func getStepID(entry string) string {
	return strings.Split(entry, ":")[0]
}

// TestNext_AfterPlanComplete verifies task_next returns Execute step.
func TestNext_SimpleWorkflow_ReturnsFirstStep(t *testing.T) {
	svc := newTestService(t)
	rootID, _ := createWorkflow(t, svc, "My Feature", "simple")

	nextResult, err := svc.Next(rootID)
	require.NoError(t, err)

	var next map[string]any
	require.NoError(t, json.Unmarshal([]byte(nextResult), &next))
	assert.Equal(t, "next", next["status"])
	assert.Equal(t, "Plan", next["step_name"])
}

func TestNext_AfterPlanComplete_ReturnsExecute(t *testing.T) {
	svc := newTestService(t)
	rootID, stepEntries := createWorkflow(t, svc, "Feature", "simple")
	planID := getStepID(stepEntries[0])

	// Start and complete Plan
	_, _ = svc.Start(planID)
	_, _ = svc.Complete(planID, "plan output", "")

	// Now ask for next
	nextResult, err := svc.Next(rootID)
	require.NoError(t, err)

	var next struct {
		Status   string `json:"status"`
		StepName string `json:"step_name"`
		Agent    string `json:"agent"`
	}
	require.NoError(t, json.Unmarshal([]byte(nextResult), &next))
	assert.Equal(t, "next", next.Status)
	assert.Equal(t, "Execute", next.StepName)
	assert.Equal(t, "developer", next.Agent)
}

func TestNext_AllDone_ReturnsAllDone(t *testing.T) {
	svc := newTestService(t)
	rootID, stepEntries := createWorkflow(t, svc, "Feature", "simple")

	// Complete all steps in order, handling verification sub-flows
	for _, entry := range stepEntries {
		stepID := getStepID(entry)
		_, _ = svc.Start(stepID)
		completeResult, _ := svc.Complete(stepID, "", "")
		if strings.HasPrefix(completeResult, "verify:") {
			verifyID := strings.TrimPrefix(completeResult, "verify:")
			_, _ = svc.Start(verifyID)
			_, _ = svc.Complete(verifyID, "", "")
			// Complete the original step (now verifying with child done)
			_, _ = svc.Complete(stepID, "", "")
		}
	}

	nextResult, err := svc.Next(rootID)
	require.NoError(t, err)

	var resp map[string]any
	require.NoError(t, json.Unmarshal([]byte(nextResult), &resp))
	assert.Equal(t, "all_done", resp["status"], "all steps done should return all_done")
}

func TestNext_InProgressBlocking_ReturnsWaiting(t *testing.T) {
	svc := newTestService(t)
	rootID, stepEntries := createWorkflow(t, svc, "Feature", "simple")
	planID := getStepID(stepEntries[0])

	// Start Plan but don't complete it — Execute is still blocked
	_, _ = svc.Start(planID)

	nextResult, err := svc.Next(rootID)
	require.NoError(t, err)

	var resp map[string]any
	require.NoError(t, json.Unmarshal([]byte(nextResult), &resp))
	// Plan is in_progress, Execute is pending — status should be "waiting"
	assert.Equal(t, "waiting", resp["status"], "in-progress blocking step should return waiting; got: %v", resp)
}

func TestNext_NotFound(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Next("notfound")
	require.NoError(t, err)
	assert.Equal(t, "error:not found", result)
}

func TestNext_ResponseHasRequiredFields(t *testing.T) {
	svc := newTestService(t)
	rootID, _ := createWorkflow(t, svc, "Feature", "simple")

	nextResult, err := svc.Next(rootID)
	require.NoError(t, err)

	var resp map[string]any
	require.NoError(t, json.Unmarshal([]byte(nextResult), &resp))
	assert.Contains(t, resp, "status")
	assert.Contains(t, resp, "step_id")
	assert.Contains(t, resp, "step_name")
	assert.Contains(t, resp, "agent")
	assert.Contains(t, resp, "description")
	assert.Contains(t, resp, "parent_path")
	assert.Contains(t, resp, "context")
}

// TestList verifies task_list returns rendered tree.
func TestList_Empty(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.List(nil, nil, false)
	require.NoError(t, err)
	assert.Equal(t, "No tasks found.", result)
}

func TestList_SingleTask(t *testing.T) {
	svc := newTestService(t)
	_ = createSimpleTask(t, svc, "My Task")
	result, err := svc.List(nil, nil, false)
	require.NoError(t, err)
	assert.Contains(t, result, "My Task")
	assert.Contains(t, result, "[pending]")
}

func TestList_FilterByStatus(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Active Task")
	_, _ = svc.Start(id)
	_ = createSimpleTask(t, svc, "Pending Task")

	status := "in_progress"
	result, err := svc.List(&status, nil, false)
	require.NoError(t, err)
	assert.Contains(t, result, "Active Task")
	assert.NotContains(t, result, "Pending Task")
}

func TestList_InvalidStatus(t *testing.T) {
	svc := newTestService(t)
	status := "invalid_status"
	result, err := svc.List(&status, nil, false)
	require.NoError(t, err)
	assert.True(t, strings.HasPrefix(result, "error:"), "invalid status should return error")
}

func TestList_ReadyTasksOnly(t *testing.T) {
	svc := newTestService(t)
	blockerID := createSimpleTask(t, svc, "Blocker")
	blockedRaw, err := svc.CreateTask(CreateTaskInput{
		Name:      "Blocked",
		BlockedBy: []string{blockerID},
	}, consumedHint())
	require.NoError(t, err)
	_ = blockedRaw

	result, err := svc.List(nil, nil, true)
	require.NoError(t, err)
	assert.Contains(t, result, "Blocker")
	assert.NotContains(t, result, "Blocked")
}

// TestSearch verifies task_search behavior.
func TestSearch_FindsByName(t *testing.T) {
	svc := newTestService(t)
	_, _ = svc.CreateTask(CreateTaskInput{Name: "Fix login bug"}, consumedHint())
	_, _ = svc.CreateTask(CreateTaskInput{Name: "Add unit tests"}, consumedHint())

	result, err := svc.Search("login")
	require.NoError(t, err)
	assert.Contains(t, result, "Fix login bug")
	assert.NotContains(t, result, "Add unit tests")
}

func TestSearch_FindsByDescription(t *testing.T) {
	svc := newTestService(t)
	_, _ = svc.CreateTask(CreateTaskInput{
		Name:        "Task A",
		Description: "authentication flow improvements",
	}, consumedHint())

	result, err := svc.Search("authentication")
	require.NoError(t, err)
	assert.Contains(t, result, "Task A")
}

func TestSearch_NoResults(t *testing.T) {
	svc := newTestService(t)
	_, _ = svc.CreateTask(CreateTaskInput{Name: "Task"}, consumedHint())

	result, err := svc.Search("nonexistent")
	require.NoError(t, err)
	assert.Equal(t, "No matching tasks.", result)
}

func TestSearch_EmptyQuery(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Search("")
	require.NoError(t, err)
	assert.Equal(t, "error:empty query", result)
}

func TestSearch_ResultFormat(t *testing.T) {
	svc := newTestService(t)
	_, _ = svc.CreateTask(CreateTaskInput{Name: "My Task"}, consumedHint())

	result, err := svc.Search("My Task")
	require.NoError(t, err)
	// Format: [<id>] <name> [<status>]
	assert.Contains(t, result, "[")
	assert.Contains(t, result, "] My Task [")
	assert.Contains(t, result, "pending")
}

// TestGet verifies task_get returns subtree + metadata.
func TestGet_BasicTask(t *testing.T) {
	svc := newTestService(t)
	rootID, _ := createWorkflow(t, svc, "Feature", "simple")

	getResult, err := svc.Get(rootID)
	require.NoError(t, err)
	assert.Contains(t, getResult, "Feature")
	// Should show children (Plan, Execute, Verify)
	assert.Contains(t, getResult, "Plan")
	assert.Contains(t, getResult, "Execute")
	assert.Contains(t, getResult, "Verify")
}

func TestGet_WithDescription(t *testing.T) {
	svc := newTestService(t)
	raw, err := svc.CreateTask(CreateTaskInput{
		Name:        "My Task",
		Description: "A great feature",
	}, consumedHint())
	require.NoError(t, err)
	taskID := stripHint(raw)

	getResult, err := svc.Get(taskID)
	require.NoError(t, err)
	assert.Contains(t, getResult, "Description: A great feature")
}

func TestGet_NotFound(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Get("notfound")
	require.NoError(t, err)
	assert.Equal(t, "error:not found", result)
}

func TestGet_ShowsBlockedBy(t *testing.T) {
	svc := newTestService(t)
	blockerID := createSimpleTask(t, svc, "Blocker")
	blockedRaw, err := svc.CreateTask(CreateTaskInput{
		Name:      "Blocked Task",
		BlockedBy: []string{blockerID},
	}, consumedHint())
	require.NoError(t, err)
	blockedID := stripHint(blockedRaw)

	getResult, err := svc.Get(blockedID)
	require.NoError(t, err)
	assert.Contains(t, getResult, "Blocked by:")
	assert.Contains(t, getResult, blockerID)
}

// TestCurrent verifies task_current behavior.
func TestCurrent_NoActiveTask(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Current()
	require.NoError(t, err)
	assert.Equal(t, "No active task.", result)
}

func TestCurrent_WithActiveTask(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Active Task")
	_, _ = svc.Start(id)

	result, err := svc.Current()
	require.NoError(t, err)
	assert.Contains(t, result, "Active Task")
}

// TestStats tests the stats query.
func TestStats_BasicTask(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Task")

	result, err := svc.Stats(id)
	require.NoError(t, err)
	assert.Contains(t, result, "Task")
	assert.Contains(t, result, "pending")
}

func TestStats_NotFound(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Stats("notfound")
	require.NoError(t, err)
	assert.Equal(t, "error:not found", result)
}

// TestHistory tests the task_history query.
func TestHistory_Basic(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Task")
	_, _ = svc.Start(id)

	result, err := svc.History(id, false)
	require.NoError(t, err)
	// Should contain at least the created event
	assert.Contains(t, result, "created")
}

func TestHistory_NotFound(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.History("notfound", false)
	require.NoError(t, err)
	assert.Equal(t, "error:not found", result)
}

// TestUpdate tests task_update.
func TestUpdate_Name(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Old Name")

	result, err := svc.Update(id, map[string]any{"name": "New Name"})
	require.NoError(t, err)
	assert.Equal(t, "ok", result)
}

func TestUpdate_NoFields(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Task")

	result, err := svc.Update(id, map[string]any{})
	require.NoError(t, err)
	assert.Equal(t, "error:no fields to update", result)
}

func TestUpdate_NotFound(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Update("notfound", map[string]any{"name": "x"})
	require.NoError(t, err)
	assert.Equal(t, "error:not found", result)
}

// TestContext tests task_context.
func TestContext_RootTask(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Root")

	result, err := svc.Context(id, 1000)
	require.NoError(t, err)
	assert.Equal(t, "No context available (root task).", result)
}

func TestContext_NotFound(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Context("notfound", 1000)
	require.NoError(t, err)
	assert.Equal(t, "error:not found", result)
}

func TestContext_NoPriorSteps(t *testing.T) {
	svc := newTestService(t)
	parent := createSimpleTask(t, svc, "Parent")
	childRaw, _ := svc.CreateTask(CreateTaskInput{Name: "Child", ParentID: &parent}, consumedHint())
	child := stripHint(childRaw)

	result, err := svc.Context(child, 1000)
	require.NoError(t, err)
	assert.Equal(t, "No context from prior steps.", result)
}

// TestContext_IncludesPriorStepOutput verifies that completed sibling output
// actually appears in the context returned for the next sibling.
func TestContext_IncludesPriorStepOutput(t *testing.T) {
	svc := newTestService(t)
	rootID, stepEntries := createWorkflow(t, svc, "Feature", "simple")
	planID := getStepID(stepEntries[0])
	executeID := getStepID(stepEntries[1])

	// Complete Plan with explicit output
	_, _ = svc.Start(planID)
	_, err := svc.Complete(planID, "plan output: use hexagonal arch", "")
	require.NoError(t, err)

	// task_context on Execute should include Plan's output
	ctxResult, err := svc.Context(executeID, 1000)
	require.NoError(t, err)
	assert.Contains(t, ctxResult, "Plan", "context should name the prior step")
	assert.Contains(t, ctxResult, "plan output: use hexagonal arch", "context should include prior step's agent output")

	// task_next on rootID should also include Plan's output in the context field
	nextResult, err := svc.Next(rootID)
	require.NoError(t, err)
	var next struct {
		Status  string              `json:"status"`
		Context []map[string]string `json:"context"`
	}
	require.NoError(t, json.Unmarshal([]byte(nextResult), &next))
	require.Equal(t, "next", next.Status)
	require.NotEmpty(t, next.Context, "next response context should be non-empty after Plan completed with output")
	assert.Equal(t, "Plan", next.Context[0]["step"])
	assert.Contains(t, next.Context[0]["output"], "plan output: use hexagonal arch")
}

// TestReorder tests task_reorder.
func TestReorder_ValidPosition(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Task")

	result, err := svc.Reorder(id, 5)
	require.NoError(t, err)
	assert.Equal(t, "ok", result)
}

func TestReorder_NegativePosition(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Task")

	result, err := svc.Reorder(id, -1)
	require.NoError(t, err)
	assert.Equal(t, "error:position must be non-negative", result)
}
