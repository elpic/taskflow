import pytest
from src.db import (
    create_task,
    get_all_tasks,
    get_children,
    get_current_task_id,
    get_task,
    set_current_task,
    update_task,
)
from src.models import TaskStatus


class TestCreateTask:
    async def test_create_task_returns_task(self):
        task = await create_task("My Task")
        assert task.id is not None
        assert task.name == "My Task"
        assert task.status == TaskStatus.PENDING

    async def test_create_task_with_description(self):
        task = await create_task("Task", description="A description")
        assert task.description == "A description"

    async def test_create_task_with_verification_criteria(self):
        task = await create_task("Task", verification_criteria="All tests pass")
        assert task.verification_criteria == "All tests pass"

    async def test_create_task_with_parent(self):
        parent = await create_task("Parent")
        child = await create_task("Child", parent_id=parent.id)
        assert child.parent_id == parent.id

    async def test_create_task_with_invalid_parent_raises(self):
        with pytest.raises(ValueError, match="not found"):
            await create_task("Child", parent_id="nonexistent")

    async def test_create_task_stores_in_db(self):
        task = await create_task("Persisted Task")
        retrieved = await get_task(task.id)
        assert retrieved is not None
        assert retrieved.id == task.id
        assert retrieved.name == "Persisted Task"


class TestGetTask:
    async def test_get_task_returns_none_for_missing(self):
        result = await get_task("doesnotexist")
        assert result is None

    async def test_get_task_returns_correct_task(self):
        task = await create_task("Find Me")
        retrieved = await get_task(task.id)
        assert retrieved is not None
        assert retrieved.name == "Find Me"
        assert retrieved.id == task.id


class TestGetChildren:
    async def test_get_children_empty(self):
        parent = await create_task("Parent")
        children = await get_children(parent.id)
        assert children == []

    async def test_get_children_returns_correct_children(self):
        parent = await create_task("Parent")
        child1 = await create_task("Child 1", parent_id=parent.id)
        child2 = await create_task("Child 2", parent_id=parent.id)
        children = await get_children(parent.id)
        child_ids = {c.id for c in children}
        assert child1.id in child_ids
        assert child2.id in child_ids

    async def test_get_children_does_not_return_grandchildren(self):
        parent = await create_task("Parent")
        child = await create_task("Child", parent_id=parent.id)
        await create_task("Grandchild", parent_id=child.id)
        children = await get_children(parent.id)
        assert len(children) == 1
        assert children[0].id == child.id


class TestGetAllTasks:
    async def test_get_all_tasks_empty_db(self):
        tasks = await get_all_tasks()
        assert tasks == []

    async def test_get_all_tasks_returns_all(self):
        await create_task("Task A")
        await create_task("Task B")
        tasks = await get_all_tasks()
        names = {t.name for t in tasks}
        assert "Task A" in names
        assert "Task B" in names


class TestUpdateTask:
    async def test_update_task_name(self):
        task = await create_task("Original")
        updated = await update_task(task.id, name="Updated")
        assert updated.name == "Updated"

    async def test_update_task_status(self):
        task = await create_task("Task")
        updated = await update_task(task.id, status=TaskStatus.IN_PROGRESS.value)
        assert updated.status == TaskStatus.IN_PROGRESS

    async def test_update_task_description(self):
        task = await create_task("Task")
        updated = await update_task(task.id, description="New description")
        assert updated.description == "New description"

    async def test_update_with_no_changes_returns_task(self):
        task = await create_task("Unchanged")
        # Passing only fields not in the allowed set — returns existing task
        result = await update_task(task.id)
        assert result.id == task.id
        assert result.name == "Unchanged"


class TestCurrentTask:
    async def test_get_current_task_id_initially_none(self):
        current = await get_current_task_id()
        assert current is None

    async def test_set_and_get_current_task(self):
        task = await create_task("Active Task")
        await set_current_task(task.id)
        current = await get_current_task_id()
        assert current == task.id

    async def test_set_current_task_to_none(self):
        task = await create_task("Task")
        await set_current_task(task.id)
        await set_current_task(None)
        current = await get_current_task_id()
        assert current is None
