package domain

import (
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func makeTask(id, name string, status TaskStatus, parentID *string) *Task {
	return &Task{
		ID:       id,
		Name:     name,
		Status:   status,
		ParentID: parentID,
		Metadata: "{}",
	}
}

func ptr(s string) *string { return &s }

func TestRenderTree_Empty(t *testing.T) {
	result := RenderTree(nil)
	assert.Equal(t, "No tasks found.", result)

	result = RenderTree([]*Task{})
	assert.Equal(t, "No tasks found.", result)
}

func TestRenderTree_SingleRoot(t *testing.T) {
	tasks := []*Task{
		makeTask("a1b2c3d4", "My Task", StatusPending, nil),
	}
	result := RenderTree(tasks)
	assert.Contains(t, result, "○")
	assert.Contains(t, result, "My Task")
	assert.Contains(t, result, "[pending]")
	// Root task has no connector prefix
	assert.False(t, strings.Contains(result, "├──"), "root should not have connector")
	assert.False(t, strings.Contains(result, "└──"), "root should not have connector")
}

func TestRenderTree_WithChildren(t *testing.T) {
	parentID := "root1234"
	tasks := []*Task{
		makeTask(parentID, "Root Task", StatusPending, nil),
		makeTask("child001", "Child One", StatusInProgress, &parentID),
		makeTask("child002", "Child Two", StatusPending, &parentID),
	}
	result := RenderTree(tasks)

	// Root renders with its icon
	assert.Contains(t, result, "○ Root Task [pending]")
	// Non-last child uses ├──
	assert.Contains(t, result, "├── ◈ Child One [in_progress]")
	// Last child uses └──
	assert.Contains(t, result, "└── ○ Child Two [pending]")
}

func TestRenderTree_StatusIcons(t *testing.T) {
	cases := []struct {
		status TaskStatus
		icon   string
		label  string
	}{
		{StatusPending, "○", "pending"},
		{StatusInProgress, "◈", "in_progress"},
		{StatusVerifying, "◇", "verifying"},
		{StatusDone, "◉", "done ✓"},
		{StatusFailed, "✗", "failed"},
	}
	for _, tc := range cases {
		t.Run(string(tc.status), func(t *testing.T) {
			tasks := []*Task{makeTask("id123456", "Task", tc.status, nil)}
			result := RenderTree(tasks)
			assert.Contains(t, result, tc.icon)
			assert.Contains(t, result, tc.label)
		})
	}
}

func TestRenderTree_MultipleRoots(t *testing.T) {
	tasks := []*Task{
		makeTask("root0001", "First Root", StatusPending, nil),
		makeTask("root0002", "Second Root", StatusDone, nil),
	}
	result := RenderTree(tasks)
	assert.Contains(t, result, "First Root")
	assert.Contains(t, result, "Second Root")
	// Two roots separated by blank line
	assert.Contains(t, result, "\n\n")
}

func TestRenderSubtree_NoChildren(t *testing.T) {
	task := makeTask("t1234567", "Lone Task", StatusInProgress, nil)
	result := RenderSubtree(task, nil)
	assert.Contains(t, result, "◈ Lone Task [in_progress]")
}

func TestRenderSubtree_WithChildren(t *testing.T) {
	parentID := "parent12"
	parent := makeTask(parentID, "Parent", StatusPending, nil)
	children := []*Task{
		makeTask("child001", "Child A", StatusDone, &parentID),
		makeTask("child002", "Child B", StatusFailed, &parentID),
	}
	result := RenderSubtree(parent, children)

	require.Contains(t, result, "Parent [pending]")
	assert.Contains(t, result, "├── ◉ Child A [done ✓]")
	assert.Contains(t, result, "└── ✗ Child B [failed]")
}

func TestRenderTree_ThreeLevels(t *testing.T) {
	grandparentID := "gp123456"
	parentID := "par12345"
	tasks := []*Task{
		makeTask(grandparentID, "Grandparent", StatusPending, nil),
		makeTask(parentID, "Parent", StatusInProgress, &grandparentID),
		makeTask("child001", "Child", StatusPending, &parentID),
	}
	result := RenderTree(tasks)

	assert.Contains(t, result, "Grandparent")
	assert.Contains(t, result, "Parent")
	assert.Contains(t, result, "Child")
	// Check indentation structure is present
	lines := strings.Split(result, "\n")
	assert.GreaterOrEqual(t, len(lines), 3)
}

func TestBuildTree_OrphansAsRoots(t *testing.T) {
	// Task whose parent doesn't exist in the list should become a root
	unknownParent := "unknown0"
	tasks := []*Task{
		makeTask("task0001", "Orphan", StatusPending, &unknownParent),
	}
	roots := BuildTree(tasks)
	assert.Len(t, roots, 1)
	assert.Equal(t, "task0001", roots[0].ID)
}
