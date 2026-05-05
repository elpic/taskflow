package app

import (
	"regexp"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

var idPattern = regexp.MustCompile(`^[0-9a-f]{8}$`)

// ptr helper
func strPtr(s string) *string { return &s }

func TestCreateTask_SimpleNoType_ReturnsID(t *testing.T) {
	svc := newTestService(t)
	raw, err := svc.CreateTask(CreateTaskInput{Name: "My Task"}, consumedHint())
	require.NoError(t, err)
	result := stripHint(raw)
	assert.Regexp(t, idPattern, result, "simple task should return just an 8-char hex ID")
}

func TestCreateTask_WithSimpleType_ReturnsWorkflowFormat(t *testing.T) {
	svc := newTestService(t)
	taskType := "simple"
	raw, err := svc.CreateTask(CreateTaskInput{
		Name:     "Implement feature X",
		TaskType: &taskType,
	}, consumedHint())
	require.NoError(t, err)
	result := stripHint(raw)

	// Format: <id>|simple|<s1>:@self,<s2>:@developer,<s3>:@qa-engineer
	parts := strings.SplitN(result, "|", 3)
	require.Len(t, parts, 3, "workflow result should have 3 pipe-delimited parts")

	rootID := parts[0]
	assert.Regexp(t, idPattern, rootID, "root ID should be 8-char hex")
	assert.Equal(t, "simple", parts[1])

	// Validate step entries
	stepParts := strings.Split(parts[2], ",")
	assert.Len(t, stepParts, 3, "simple workflow should have 3 steps")
	for _, sp := range stepParts {
		assert.Contains(t, sp, ":@", "each step should have ':@<agent>' format")
		colonIdx := strings.Index(sp, ":")
		stepID := sp[:colonIdx]
		assert.Regexp(t, idPattern, stepID, "step ID should be 8-char hex")
	}

	// Check specific agents
	assert.Contains(t, parts[2], ":@self", "first step should be @self")
	assert.Contains(t, parts[2], ":@developer", "second step should be @developer")
	assert.Contains(t, parts[2], ":@qa-engineer", "third step should be @qa-engineer")
}

func TestCreateTask_WithImplementType_ReturnsMultiStepWorkflow(t *testing.T) {
	svc := newTestService(t)
	taskType := "implement"
	raw, err := svc.CreateTask(CreateTaskInput{
		Name:     "Build new API",
		TaskType: &taskType,
	}, consumedHint())
	require.NoError(t, err)
	result := stripHint(raw)

	parts := strings.SplitN(result, "|", 3)
	require.Len(t, parts, 3)
	assert.Equal(t, "implement", parts[1])

	stepParts := strings.Split(parts[2], ",")
	assert.Greater(t, len(stepParts), 3, "implement workflow should have many steps")
}

func TestCreateTask_InvalidType_ReturnsError(t *testing.T) {
	svc := newTestService(t)
	taskType := "foo"
	result, err := svc.CreateTask(CreateTaskInput{
		Name:     "Bad Task",
		TaskType: &taskType,
	}, consumedHint())
	require.NoError(t, err)
	assert.True(t, strings.HasPrefix(result, "error:"), "invalid type should return error: prefix")
	assert.Contains(t, result, "foo")
}

func TestCreateTask_Idempotency_SameIDOnSecondCall(t *testing.T) {
	svc := newTestService(t)
	key := "unique-key-42"
	raw1, err := svc.CreateTask(CreateTaskInput{
		Name:           "Task One",
		IdempotencyKey: &key,
	}, consumedHint())
	require.NoError(t, err)
	result1 := stripHint(raw1)
	assert.Regexp(t, idPattern, result1)

	raw2, err := svc.CreateTask(CreateTaskInput{
		Name:           "Task One Duplicate",
		IdempotencyKey: &key,
	}, consumedHint())
	require.NoError(t, err)
	result2 := stripHint(raw2)
	// Should return the same ID
	assert.Equal(t, result1, result2, "idempotent call should return same ID")
}

func TestCreateTask_BlockedBy_DependencyStored(t *testing.T) {
	svc := newTestService(t)

	// Create the blocker first
	blockerRaw, err := svc.CreateTask(CreateTaskInput{Name: "Blocker"}, consumedHint())
	require.NoError(t, err)
	blockerID := stripHint(blockerRaw)

	// Create task blocked by it
	blockedRaw, err := svc.CreateTask(CreateTaskInput{
		Name:      "Blocked Task",
		BlockedBy: []string{blockerID},
	}, consumedHint())
	require.NoError(t, err)
	blockedID := stripHint(blockedRaw)

	// Verify dependency: start should fail (blocker not done)
	startResult, err := svc.Start(blockedID)
	require.NoError(t, err)
	assert.True(t, strings.HasPrefix(startResult, "error:blocked by"),
		"should be blocked; got: %s", startResult)
}

func TestCreateTask_FirstRunHint_AppearsOnce(t *testing.T) {
	svc := newTestService(t)
	hint := newHint()

	// First task on empty DB: hint should appear
	result1, err := svc.CreateTask(CreateTaskInput{Name: "First Task"}, hint)
	require.NoError(t, err)
	assert.Contains(t, result1, "Hint:", "first task on empty DB should show hint")

	// Second call with same hint: should NOT appear again
	result2, err := svc.CreateTask(CreateTaskInput{Name: "Second Task"}, hint)
	require.NoError(t, err)
	assert.NotContains(t, result2, "Hint:", "hint should only appear once")
}

func TestCreateTask_FirstRunHint_NotShownOnNonEmptyDB(t *testing.T) {
	svc := newTestService(t)

	// Pre-populate DB using a consumed hint so the pre-populate doesn't show hint
	_, err := svc.CreateTask(CreateTaskInput{Name: "Existing"}, consumedHint())
	require.NoError(t, err)

	// New hint — but DB is not empty
	hint := newHint()
	result, err := svc.CreateTask(CreateTaskInput{Name: "New Task"}, hint)
	require.NoError(t, err)
	assert.NotContains(t, result, "Hint:", "hint should not appear when DB already has tasks")
}

func TestCreateTask_WithParentID(t *testing.T) {
	svc := newTestService(t)
	parentRaw, err := svc.CreateTask(CreateTaskInput{Name: "Parent"}, consumedHint())
	require.NoError(t, err)
	parentID := stripHint(parentRaw)

	childRaw, err := svc.CreateTask(CreateTaskInput{
		Name:     "Child",
		ParentID: &parentID,
	}, consumedHint())
	require.NoError(t, err)
	child := stripHint(childRaw)
	assert.Regexp(t, idPattern, child)
}

func TestCreateTask_AllBuiltinTypes(t *testing.T) {
	validTypes := []string{"simple", "implement", "bugfix", "refactor", "research"}
	for _, tt := range validTypes {
		t.Run(tt, func(t *testing.T) {
			svc := newTestService(t)
			taskType := tt
			raw, err := svc.CreateTask(CreateTaskInput{
				Name:     "Task for " + tt,
				TaskType: &taskType,
			}, consumedHint())
			require.NoError(t, err)
			result := stripHint(raw)
			assert.False(t, strings.HasPrefix(result, "error:"),
				"builtin type %s should succeed, got: %s", tt, result)
			assert.Contains(t, result, "|"+tt+"|")
		})
	}
}
