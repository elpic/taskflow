from src.models import Task, TaskStatus
from src.tree import (
    STATUS_ICONS,
    STATUS_LABELS,
    build_tree,
    render_subtree,
    render_tree,
)


def make_task(
    task_id: str,
    name: str,
    status: TaskStatus = TaskStatus.PENDING,
    parent_id: str | None = None,
) -> Task:
    return Task(
        id=task_id,
        name=name,
        description="",
        status=status,
        parent_id=parent_id,
        verification_criteria=None,
        verification_result=None,
        metadata="{}",
        created_at="2024-01-01T00:00:00+00:00",
        started_at=None,
        completed_at=None,
    )


class TestStatusMappings:
    def test_all_statuses_have_icons(self):
        for status in TaskStatus:
            assert status in STATUS_ICONS

    def test_all_statuses_have_labels(self):
        for status in TaskStatus:
            assert status in STATUS_LABELS

    def test_done_label_contains_checkmark(self):
        assert "✓" in STATUS_LABELS[TaskStatus.DONE]


class TestBuildTree:
    def test_flat_list_returns_all_as_roots(self):
        tasks = [
            make_task("1", "A"),
            make_task("2", "B"),
            make_task("3", "C"),
        ]
        roots = build_tree(tasks)
        assert len(roots) == 3

    def test_parent_child_relationship(self):
        parent = make_task("p1", "Parent")
        child = make_task("c1", "Child", parent_id="p1")
        roots = build_tree([parent, child])
        assert len(roots) == 1
        assert roots[0].id == "p1"
        assert len(roots[0].children) == 1
        assert roots[0].children[0].id == "c1"

    def test_multiple_children(self):
        parent = make_task("p1", "Parent")
        child1 = make_task("c1", "Child 1", parent_id="p1")
        child2 = make_task("c2", "Child 2", parent_id="p1")
        roots = build_tree([parent, child1, child2])
        assert len(roots) == 1
        assert len(roots[0].children) == 2

    def test_orphan_with_missing_parent_becomes_root(self):
        # A task whose parent_id doesn't exist in the list becomes a root
        orphan = make_task("o1", "Orphan", parent_id="nonexistent")
        roots = build_tree([orphan])
        assert len(roots) == 1
        assert roots[0].id == "o1"

    def test_build_tree_clears_existing_children(self):
        parent = make_task("p1", "Parent")
        parent.children = [make_task("stale", "Stale")]
        child = make_task("c1", "Real Child", parent_id="p1")
        roots = build_tree([parent, child])
        assert len(roots[0].children) == 1
        assert roots[0].children[0].id == "c1"

    def test_empty_list_returns_empty(self):
        assert build_tree([]) == []


class TestRenderTree:
    def test_empty_returns_no_tasks_message(self):
        result = render_tree([])
        assert "No tasks" in result

    def test_single_task_contains_name(self):
        tasks = [make_task("1", "My Task")]
        result = render_tree(tasks)
        assert "My Task" in result

    def test_status_icon_appears(self):
        tasks = [make_task("1", "A Task", status=TaskStatus.DONE)]
        result = render_tree(tasks)
        assert STATUS_ICONS[TaskStatus.DONE] in result

    def test_status_label_appears(self):
        tasks = [make_task("1", "A Task", status=TaskStatus.IN_PROGRESS)]
        result = render_tree(tasks)
        assert "in_progress" in result

    def test_nested_task_shows_connector(self):
        parent = make_task("p1", "Parent")
        child = make_task("c1", "Child", parent_id="p1")
        result = render_tree([parent, child])
        assert "└──" in result or "├──" in result
        assert "Child" in result

    def test_multiple_roots_separated(self):
        tasks = [make_task("1", "Root A"), make_task("2", "Root B")]
        result = render_tree(tasks)
        assert "Root A" in result
        assert "Root B" in result


class TestRenderSubtree:
    def test_renders_task_with_children(self):
        parent = make_task("p1", "Parent")
        child = make_task("c1", "Child")
        result = render_subtree(parent, [child])
        assert "Parent" in result
        assert "Child" in result

    def test_empty_children(self):
        task = make_task("t1", "Solo")
        result = render_subtree(task, [])
        assert "Solo" in result
