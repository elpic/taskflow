package app

import (
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/elpic/taskflow/internal/adapters/sqlite"
	"github.com/elpic/taskflow/internal/adapters/workflows"
)

// TestTaskTypes_ContainsBuiltinTypes verifies task_types returns known workflow types.
func TestTaskTypes_ContainsBuiltinTypes(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.TaskTypes(consumedHint())
	require.NoError(t, err)

	assert.Contains(t, result, "simple")
	assert.Contains(t, result, "implement")
	assert.Contains(t, result, "bugfix")
	assert.Contains(t, result, "refactor")
	assert.Contains(t, result, "research")
}

func TestTaskTypes_ShowsStepNames(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.TaskTypes(consumedHint())
	require.NoError(t, err)

	// simple workflow should show: simple: Plan → Execute → Verify
	assert.Contains(t, result, "Plan")
	assert.Contains(t, result, "Execute")
	assert.Contains(t, result, "Verify")
}

func TestTaskTypes_FirstRunHint(t *testing.T) {
	svc := newTestService(t)
	hint := newHint()

	// Empty DB — hint should appear
	result, err := svc.TaskTypes(hint)
	require.NoError(t, err)
	assert.Contains(t, result, "Hint:", "task_types on empty DB should show hint")

	// Second call — hint should not repeat
	result2, err := svc.TaskTypes(hint)
	require.NoError(t, err)
	assert.NotContains(t, result2, "Hint:", "hint should only appear once per session")
}

func TestTaskTypes_NoHintWhenTasksExist(t *testing.T) {
	svc := newTestService(t)
	// Pre-populate DB
	_, _ = svc.CreateTask(CreateTaskInput{Name: "Existing Task"}, consumedHint())

	hint := newHint()
	result, err := svc.TaskTypes(hint)
	require.NoError(t, err)
	assert.NotContains(t, result, "Hint:", "hint should not appear when DB has tasks")
}

// TestCleanup_NoOldTasks verifies cleanup returns "ok|deleted:0" when nothing to clean.
func TestCleanup_NoOldTasks(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Cleanup(30)
	require.NoError(t, err)
	assert.Equal(t, "ok|deleted:0", result)
}

func TestCleanup_DeletesOldDoneRoot(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "test.db")
	db, err := sqlite.Open(dbPath)
	require.NoError(t, err)
	t.Cleanup(func() { db.Close() })
	require.NoError(t, sqlite.Initialize(db))

	repo := sqlite.NewRepository(db)

	// Create a task and mark it done with an old timestamp
	task, err := repo.CreateTask("Old Done Task", "", nil, nil, nil, nil)
	require.NoError(t, err)

	oldTime := time.Now().UTC().Add(-60 * 24 * time.Hour).Format("2006-01-02T15:04:05.999999-07:00")
	_, err = repo.UpdateTask(task.ID, map[string]any{
		"status":       "done",
		"completed_at": oldTime,
	})
	require.NoError(t, err)

	wfSource, err := workflows.NewSource("")
	require.NoError(t, err)
	svc := NewService(repo, wfSource, nopHooks{}, nopLogger{})

	result, err := svc.Cleanup(30)
	require.NoError(t, err)
	assert.Equal(t, "ok|deleted:1", result, "old done root should be deleted")
}

func TestCleanup_NegativeDays_ReturnsError(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Cleanup(-1)
	require.NoError(t, err)
	assert.Equal(t, "error:days must be non-negative", result)
}

func TestCleanup_DoesNotDeleteRecentTask(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "test.db")
	db, err := sqlite.Open(dbPath)
	require.NoError(t, err)
	t.Cleanup(func() { db.Close() })
	require.NoError(t, sqlite.Initialize(db))
	repo := sqlite.NewRepository(db)

	task, err := repo.CreateTask("Recent Done Task", "", nil, nil, nil, nil)
	require.NoError(t, err)

	// Recent completion
	recent := time.Now().UTC().Add(-1 * time.Hour).Format("2006-01-02T15:04:05.999999-07:00")
	_, err = repo.UpdateTask(task.ID, map[string]any{
		"status":       "done",
		"completed_at": recent,
	})
	require.NoError(t, err)

	wfSource, err := workflows.NewSource("")
	require.NoError(t, err)
	svc := NewService(repo, wfSource, nopHooks{}, nopLogger{})

	result, err := svc.Cleanup(30)
	require.NoError(t, err)
	assert.Equal(t, "ok|deleted:0", result, "recent done task should not be cleaned up")
}

// TestAnalytics_UnknownQuery verifies error format.
func TestAnalytics_UnknownQuery(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Analytics("unknown_query", 30)
	require.NoError(t, err)
	assert.True(t, strings.HasPrefix(result, "error:"), "unknown analytics query should return error")
	assert.Contains(t, result, "unknown_query")
}

func TestAnalytics_WorkflowSummary_Empty(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Analytics("workflow_summary", 30)
	require.NoError(t, err)
	// Empty DB returns "No data for the specified period."
	assert.Contains(t, result, "No data")
}

func TestAnalytics_StepBottlenecks_Empty(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Analytics("step_bottlenecks", 30)
	require.NoError(t, err)
	assert.Contains(t, result, "No data")
}

func TestAnalytics_AgentPerformance_Empty(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Analytics("agent_performance", 30)
	require.NoError(t, err)
	assert.Contains(t, result, "No data")
}

func TestAnalytics_Velocity_Empty(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Analytics("velocity", 30)
	require.NoError(t, err)
	assert.Contains(t, result, "No data")
}

// TestResume tests the task_resume query.
func TestResume_NoActiveWork(t *testing.T) {
	svc := newTestService(t)
	result, err := svc.Resume(nil)
	require.NoError(t, err)
	assert.Equal(t, "No active work found.", result)
}

func TestResume_WithActiveWorkflow(t *testing.T) {
	svc := newTestService(t)
	rootID, stepEntries := createWorkflow(t, svc, "Active Project", "simple")
	planID := getStepID(stepEntries[0])

	// Start Plan step to have in-progress work
	_, _ = svc.Start(planID)

	resumeResult, err := svc.Resume(&rootID)
	require.NoError(t, err)
	assert.Contains(t, resumeResult, "Resume: Active Project")
	assert.Contains(t, resumeResult, "Plan")
}
