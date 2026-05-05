package app

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// createSimpleTask creates a plain task and returns its ID (no hint suffix).
func createSimpleTask(t *testing.T, svc *Service, name string) string {
	t.Helper()
	raw, err := svc.CreateTask(CreateTaskInput{Name: name}, consumedHint())
	require.NoError(t, err)
	return stripHint(raw)
}

// TestStart_Basic verifies a pending task transitions to in_progress.
func TestStart_Basic(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Task")

	result, err := svc.Start(id)
	require.NoError(t, err)
	assert.Equal(t, "ok", result)
}

func TestStart_NotFound(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Start("notfound")
	require.NoError(t, err)
	assert.Equal(t, "error:not found", result)
}

func TestStart_AlreadyInProgress(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Task")
	_, _ = svc.Start(id)

	result, err := svc.Start(id)
	require.NoError(t, err)
	assert.True(t, strings.HasPrefix(result, "error:"), "starting in_progress task should fail")
}

func TestStart_BlockedByPendingTask(t *testing.T) {
	svc := newTestService(t)
	blockerID := createSimpleTask(t, svc, "Blocker")
	blockedRaw, err := svc.CreateTask(CreateTaskInput{
		Name:      "Blocked",
		BlockedBy: []string{blockerID},
	}, consumedHint())
	require.NoError(t, err)
	blockedID := stripHint(blockedRaw)

	result, err := svc.Start(blockedID)
	require.NoError(t, err)
	assert.True(t, strings.HasPrefix(result, "error:blocked by"),
		"should be blocked; got: %s", result)
	assert.Contains(t, result, blockerID)
}

func TestStart_SetsCurrentTask(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Active Task")

	_, _ = svc.Start(id)
	current, err := svc.Current()
	require.NoError(t, err)
	assert.Contains(t, current, "Active Task")
}

// TestComplete_SimpleTask tests start → complete full cycle.
func TestComplete_SimpleTask(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Task")

	_, _ = svc.Start(id)
	result, err := svc.Complete(id, "", "")
	require.NoError(t, err)
	// Should be "ok" or "ok|unblocked:..."
	assert.True(t, result == "ok" || strings.HasPrefix(result, "ok|unblocked:"),
		"complete should return 'ok' or 'ok|unblocked:...'; got: %s", result)
}

func TestComplete_UnblocksDependent(t *testing.T) {
	svc := newTestService(t)
	blockerID := createSimpleTask(t, svc, "Blocker")
	blockedRaw, err := svc.CreateTask(CreateTaskInput{
		Name:      "Blocked",
		BlockedBy: []string{blockerID},
	}, consumedHint())
	require.NoError(t, err)
	blockedID := stripHint(blockedRaw)

	_, _ = svc.Start(blockerID)
	result, err := svc.Complete(blockerID, "", "")
	require.NoError(t, err)
	assert.True(t, strings.HasPrefix(result, "ok|unblocked:"),
		"completing blocker should unblock dependent; got: %s", result)
	assert.Contains(t, result, blockedID)
}

func TestComplete_WithVerificationCriteria_ReturnsVerifyPrefix(t *testing.T) {
	svc := newTestService(t)
	vc := "must pass all acceptance tests"
	raw, err := svc.CreateTask(CreateTaskInput{
		Name:                 "Task with Criteria",
		VerificationCriteria: &vc,
	}, consumedHint())
	require.NoError(t, err)
	taskID := stripHint(raw)

	_, _ = svc.Start(taskID)
	completeResult, err := svc.Complete(taskID, "", "")
	require.NoError(t, err)
	assert.True(t, strings.HasPrefix(completeResult, "verify:"),
		"completing task with verification criteria should return verify:<id>; got: %s", completeResult)

	// Extracted verify task ID should be an 8-char hex
	verifyID := strings.TrimPrefix(completeResult, "verify:")
	assert.Regexp(t, idPattern, verifyID)
}

func TestComplete_NotFound(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Complete("notfound", "", "")
	require.NoError(t, err)
	assert.Equal(t, "error:not found", result)
}

func TestComplete_ChildrenNotDone_Blocked(t *testing.T) {
	svc := newTestService(t)
	parent := createSimpleTask(t, svc, "Parent")
	_, _ = svc.CreateTask(CreateTaskInput{Name: "Child", ParentID: &parent}, consumedHint())

	_, _ = svc.Start(parent)
	result, err := svc.Complete(parent, "", "")
	require.NoError(t, err)
	assert.True(t, strings.HasPrefix(result, "error:"),
		"completing parent with pending child should fail; got: %s", result)
}

// TestFail tests the fail lifecycle operation.
func TestFail_PendingTask(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Task")

	result, err := svc.Fail(id, "something went wrong")
	require.NoError(t, err)
	assert.Equal(t, "ok", result)
}

func TestFail_InProgressTask(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Task")
	_, _ = svc.Start(id)

	result, err := svc.Fail(id, "timed out")
	require.NoError(t, err)
	assert.Equal(t, "ok", result)
}

func TestFail_DoneTask_ReturnsError(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Task")
	_, _ = svc.Start(id)
	_, _ = svc.Complete(id, "", "")

	result, err := svc.Fail(id, "too late")
	require.NoError(t, err)
	assert.True(t, strings.HasPrefix(result, "error:"), "failing a done task should error; got: %s", result)
}

func TestFail_NotFound(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Fail("notfound", "reason")
	require.NoError(t, err)
	assert.Equal(t, "error:not found", result)
}

// TestReset tests the reset lifecycle operation.
func TestReset_DoneTask(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Task")
	_, _ = svc.Start(id)
	_, _ = svc.Complete(id, "", "")

	result, err := svc.Reset(id, false)
	require.NoError(t, err)
	assert.Equal(t, "ok", result)
}

func TestReset_FailedTask(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Task")
	_, _ = svc.Fail(id, "failed")

	result, err := svc.Reset(id, false)
	require.NoError(t, err)
	assert.Equal(t, "ok", result)
}

func TestReset_PendingTask_ReturnsError(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Task")

	result, err := svc.Reset(id, false)
	require.NoError(t, err)
	assert.True(t, strings.HasPrefix(result, "error:"),
		"resetting a pending task should fail; got: %s", result)
}

func TestReset_StatusBackToPending(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Task")
	_, _ = svc.Start(id)
	_, _ = svc.Complete(id, "", "")

	_, _ = svc.Reset(id, false)

	// Now should be startable again
	result, err := svc.Start(id)
	require.NoError(t, err)
	assert.Equal(t, "ok", result)
}

func TestReset_Recursive(t *testing.T) {
	svc := newTestService(t)
	parent := createSimpleTask(t, svc, "Parent")
	child, _ := svc.CreateTask(CreateTaskInput{Name: "Child", ParentID: &parent}, consumedHint())
	childID := stripHint(child)

	// Complete child, then parent
	_, _ = svc.Start(childID)
	_, _ = svc.Complete(childID, "", "")
	_, _ = svc.Start(parent)
	_, _ = svc.Complete(parent, "", "")

	result, err := svc.Reset(parent, true)
	require.NoError(t, err)
	assert.Equal(t, "ok", result)
}

func TestReset_NotFound(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Reset("notfound", false)
	require.NoError(t, err)
	assert.Equal(t, "error:not found", result)
}

// TestDelete tests task deletion.
func TestDelete_BasicTask(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "To Delete")

	result, err := svc.Delete(id)
	require.NoError(t, err)
	assert.Equal(t, "ok", result)
}

func TestDelete_InProgressTask_ReturnsError(t *testing.T) {
	svc := newTestService(t)
	id := createSimpleTask(t, svc, "Active")
	_, _ = svc.Start(id)

	result, err := svc.Delete(id)
	require.NoError(t, err)
	assert.True(t, strings.HasPrefix(result, "error:"),
		"deleting in-progress task should fail; got: %s", result)
}

func TestDelete_NotFound(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Delete("notfound")
	require.NoError(t, err)
	assert.Equal(t, "error:not found", result)
}

// TestMove tests task movement.
func TestMove_ToNewParent(t *testing.T) {
	svc := newTestService(t)
	parent1 := createSimpleTask(t, svc, "Parent1")
	parent2 := createSimpleTask(t, svc, "Parent2")
	childRaw, _ := svc.CreateTask(CreateTaskInput{Name: "Child", ParentID: &parent1}, consumedHint())
	child := stripHint(childRaw)

	result, err := svc.Move(child, &parent2)
	require.NoError(t, err)
	assert.Equal(t, "ok", result)
}

func TestMove_NotFound(t *testing.T) {
	svc := newTestService(t)
	parent := "nonexistent"
	result, err := svc.Move("alsonotfound", &parent)
	require.NoError(t, err)
	assert.Equal(t, "error:not found", result)
}

// completeStep starts and completes a step, handling the verify sub-task if one is created.
// When Complete returns "verify:<id>", it creates a child verify task that must be completed
// before calling Complete on the original step again to push it from verifying → done.
func completeStep(t *testing.T, svc *Service, stepID string) {
	t.Helper()
	_, _ = svc.Start(stepID)
	r, err := svc.Complete(stepID, "", "")
	require.NoError(t, err)
	if strings.HasPrefix(r, "verify:") {
		verifyID := strings.TrimPrefix(r, "verify:")
		_, _ = svc.Start(verifyID)
		_, err = svc.Complete(verifyID, "", "")
		require.NoError(t, err)
		// Re-complete the original step now that verify child is done
		_, err = svc.Complete(stepID, "", "")
		require.NoError(t, err)
	}
}

// TestComplete_ImplementFanIn verifies that completing all three parallel branches
// (Create tests, Documentation, Containerization) unblocks the Code review step.
func TestComplete_ImplementFanIn(t *testing.T) {
	svc := newTestService(t)
	taskType := "implement"
	raw, err := svc.CreateTask(CreateTaskInput{
		Name:     "Fan-in Feature",
		TaskType: &taskType,
	}, consumedHint())
	require.NoError(t, err)
	result := stripHint(raw)

	parts := strings.SplitN(result, "|", 3)
	require.Len(t, parts, 3)
	rootID := parts[0]

	// Map step names to IDs. Get output first line format: "○ <Name> [<status>]"
	stepsByName := map[string]string{}
	for _, entry := range strings.Split(parts[2], ",") {
		colonIdx := strings.Index(entry, ":")
		require.Greater(t, colonIdx, 0)
		stepID := entry[:colonIdx]
		got, ferr := svc.Get(stepID)
		require.NoError(t, ferr)
		firstLine := strings.SplitN(got, "\n", 2)[0]
		// Format: "○ Name [status]" — strip icon prefix and trailing " [...]"
		if bracketIdx := strings.LastIndex(firstLine, " ["); bracketIdx >= 0 {
			nameWithPrefix := firstLine[:bracketIdx]
			if spaceIdx := strings.Index(nameWithPrefix, " "); spaceIdx >= 0 {
				name := strings.TrimSpace(nameWithPrefix[spaceIdx+1:])
				stepsByName[name] = stepID
			}
		}
	}

	require.Contains(t, stepsByName, "Create branch", "implement workflow must have Create branch step")
	require.Contains(t, stepsByName, "Create tests", "implement workflow must have Create tests step")
	require.Contains(t, stepsByName, "Documentation", "implement workflow must have Documentation step")
	require.Contains(t, stepsByName, "Containerization", "implement workflow must have Containerization step")
	require.Contains(t, stepsByName, "Code review", "implement workflow must have Code review step")

	// Complete linear prefix steps; Implement has a verification sub-task so use completeStep.
	linearSteps := []string{
		"Create branch",
		"Design solution",
		"Clarifying questions",
		"Review acceptance criteria",
		"Implement",
	}
	for _, name := range linearSteps {
		id, ok := stepsByName[name]
		require.True(t, ok, "missing linear step %q", name)
		completeStep(t, svc, id)
	}

	// After Implement is fully done (including its verify sub-task), the three parallel
	// branches are unblocked but not yet complete. task_next should return one of them,
	// NOT Code review.
	nextResult, err := svc.Next(rootID)
	require.NoError(t, err)
	var next struct {
		Status   string `json:"status"`
		StepName string `json:"step_name"`
	}
	require.NoError(t, json.Unmarshal([]byte(nextResult), &next))
	assert.Equal(t, "next", next.Status)
	assert.NotEqual(t, "Code review", next.StepName,
		"Code review must not appear while parallel branches are incomplete; got: %s", next.StepName)

	// Complete the three parallel branches (each has a verify sub-task too).
	for _, name := range []string{"Create tests", "Documentation", "Containerization"} {
		completeStep(t, svc, stepsByName[name])
	}

	// Now task_next must surface Code review — all three fan-in deps are satisfied.
	nextResult2, err := svc.Next(rootID)
	require.NoError(t, err)
	var next2 struct {
		Status   string `json:"status"`
		StepName string `json:"step_name"`
		Agent    string `json:"agent"`
	}
	require.NoError(t, json.Unmarshal([]byte(nextResult2), &next2))
	assert.Equal(t, "next", next2.Status)
	assert.Equal(t, "Code review", next2.StepName,
		"Code review should be unblocked after all three parallel branches complete")
	assert.Equal(t, "code-reviewer", next2.Agent)
}

// TestComplete_FullLifecycle_WorkflowExpansion tests the full simple workflow lifecycle.
func TestComplete_FullLifecycle_WorkflowExpansion(t *testing.T) {
	svc := newTestService(t)
	taskType := "simple"
	raw, err := svc.CreateTask(CreateTaskInput{
		Name:     "Complete Workflow",
		TaskType: &taskType,
	}, consumedHint())
	require.NoError(t, err)
	result := stripHint(raw)

	parts := strings.SplitN(result, "|", 3)
	require.Len(t, parts, 3)

	// Parse step IDs: <id>:@<agent>,...
	stepEntries := strings.Split(parts[2], ",")
	require.Len(t, stepEntries, 3)

	getStepID := func(entry string) string {
		return strings.Split(entry, ":")[0]
	}

	planID := getStepID(stepEntries[0])    // @self
	executeID := getStepID(stepEntries[1]) // @developer

	// Start and complete Plan step
	startR, _ := svc.Start(planID)
	assert.Equal(t, "ok", startR)

	completeR, err := svc.Complete(planID, "", "")
	require.NoError(t, err)
	// Completing Plan should unblock Execute
	assert.True(t, completeR == "ok" || strings.HasPrefix(completeR, "ok|unblocked:"),
		"complete Plan should succeed; got: %s", completeR)

	// Now Execute should be startable
	startExec, err := svc.Start(executeID)
	require.NoError(t, err)
	assert.Equal(t, "ok", startExec, "Execute step should now be startable")
}
