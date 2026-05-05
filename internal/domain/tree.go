package domain

import "strings"

// BuildTree builds a tree structure from a flat task list.
// Returns root nodes with Children populated.
func BuildTree(tasks []*Task) []*Task {
	byID := make(map[string]*Task, len(tasks))
	for _, t := range tasks {
		t.Children = nil
		byID[t.ID] = t
	}

	var roots []*Task
	for _, t := range tasks {
		if t.ParentID != nil && byID[*t.ParentID] != nil {
			parent := byID[*t.ParentID]
			parent.Children = append(parent.Children, t)
		} else {
			roots = append(roots, t)
		}
	}
	return roots
}

// renderTask renders a single task and its children as a tree string.
func renderTask(task *Task, prefix string, isLast bool, isRoot bool) string {
	icon := task.Icon()
	label := task.Label()

	var connector, childPrefix string
	if isRoot {
		connector = ""
		childPrefix = ""
	} else if isLast {
		connector = "└── "
		childPrefix = "    "
	} else {
		connector = "├── "
		childPrefix = "│   "
	}

	line := prefix + connector + icon + " " + task.Name + " [" + label + "]"
	lines := []string{line}

	for i, child := range task.Children {
		isChildLast := i == len(task.Children)-1
		lines = append(lines, renderTask(child, prefix+childPrefix, isChildLast, false))
	}

	return strings.Join(lines, "\n")
}

// RenderTree renders a full task tree from a flat list.
func RenderTree(tasks []*Task) string {
	if len(tasks) == 0 {
		return "No tasks found."
	}

	roots := BuildTree(tasks)
	parts := make([]string, 0, len(roots))
	for _, root := range roots {
		parts = append(parts, renderTask(root, "", true, true))
	}
	return strings.Join(parts, "\n\n")
}

// RenderSubtree renders a single task with its direct children.
func RenderSubtree(task *Task, children []*Task) string {
	task.Children = children
	return renderTask(task, "", true, true)
}
