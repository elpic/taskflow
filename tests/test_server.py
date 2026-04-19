from src.server import (
    task_complete,
    task_create,
    task_current,
    task_fail,
    task_get,
    task_list,
    task_start,
    task_update,
)


class TestTaskList:
    async def test_task_list_empty(self):
        result = await task_list()
        assert result == "No tasks found."

    async def test_task_list_single_task(self):
        await task_create("My Task")
        result = await task_list()
        assert "My Task" in result
        assert "pending" in result

    async def test_task_list_nested_tasks(self):
        root_id = await task_create("Root")
        await task_create("Child", parent_id=root_id)
        result = await task_list()
        assert "Root" in result
        assert "Child" in result
        assert "└──" in result

    async def test_task_list_shows_status_icons(self):
        task_id = await task_create("Started")
        await task_start(task_id)
        result = await task_list()
        assert "in_progress" in result

    async def test_task_list_multiple_roots(self):
        await task_create("Root A")
        await task_create("Root B")
        result = await task_list()
        assert "Root A" in result
        assert "Root B" in result

    async def test_task_list_shows_all_statuses(self):
        await task_create("Pending Task")
        t2 = await task_create("Started Task")
        t3 = await task_create("Failed Task")
        await task_start(t2)
        await task_start(t3)
        await task_fail(t3, "broken")
        result = await task_list()
        assert "pending" in result
        assert "in_progress" in result
        assert "failed" in result

    async def test_task_list_with_completed_task(self):
        task_id = await task_create("Done Task")
        await task_complete(task_id)
        result = await task_list()
        assert "done" in result


class TestTaskGet:
    async def test_task_get_not_found(self):
        result = await task_get("nonexistent")
        assert result == "error:not found"

    async def test_task_get_returns_task_details(self):
        task_id = await task_create("My Task", description="A test task")
        result = await task_get(task_id)
        assert "My Task" in result
        assert "pending" in result
        assert "Description: A test task" in result

    async def test_task_get_with_children(self):
        parent_id = await task_create("Parent")
        await task_create("Child A", parent_id=parent_id)
        await task_create("Child B", parent_id=parent_id)
        result = await task_get(parent_id)
        assert "Parent" in result
        assert "Child A" in result
        assert "Child B" in result

    async def test_task_get_without_children(self):
        task_id = await task_create("Leaf Task")
        result = await task_get(task_id)
        assert "Leaf Task" in result
        assert "└──" not in result

    async def test_task_get_shows_verification_criteria(self):
        task_id = await task_create(
            "Verified Task", verification_criteria="All tests pass"
        )
        result = await task_get(task_id)
        assert "Criteria: All tests pass" in result

    async def test_task_get_hides_empty_metadata(self):
        task_id = await task_create("Simple Task")
        result = await task_get(task_id)
        assert "Metadata" not in result


class TestTaskCurrent:
    async def test_task_current_no_active(self):
        result = await task_current()
        assert result == "No active task."

    async def test_task_current_returns_active_task(self):
        task_id = await task_create("Active Task")
        await task_start(task_id)
        result = await task_current()
        assert "Active Task" in result
        assert "in_progress" in result

    async def test_task_current_shows_parent_breadcrumb(self):
        root_id = await task_create("Root Project")
        child_id = await task_create("Sub Task", parent_id=root_id)
        await task_start(child_id)
        result = await task_current()
        assert "Context: Root Project" in result
        assert "Sub Task" in result

    async def test_task_current_shows_deep_breadcrumb(self):
        root_id = await task_create("Project")
        mid_id = await task_create("Feature", parent_id=root_id)
        leaf_id = await task_create("Step", parent_id=mid_id)
        await task_start(leaf_id)
        result = await task_current()
        assert "Context: Project > Feature" in result
        assert "Step" in result

    async def test_task_current_with_children(self):
        parent_id = await task_create("Parent")
        await task_create("Child", parent_id=parent_id)
        await task_start(parent_id)
        result = await task_current()
        assert "Parent" in result
        assert "Child" in result


class TestTaskUpdate:
    async def test_task_update_not_found(self):
        result = await task_update("nonexistent", name="New Name")
        assert result == "error:not found"

    async def test_task_update_name(self):
        task_id = await task_create("Original")
        result = await task_update(task_id, name="Updated")
        assert result == "ok"
        details = await task_get(task_id)
        assert "Updated" in details

    async def test_task_update_description(self):
        task_id = await task_create("Task")
        result = await task_update(task_id, description="New description")
        assert result == "ok"
        details = await task_get(task_id)
        assert "New description" in details

    async def test_task_update_multiple_fields(self):
        task_id = await task_create("Task")
        result = await task_update(task_id, name="New Name", description="New desc")
        assert result == "ok"
        details = await task_get(task_id)
        assert "New Name" in details
        assert "New desc" in details

    async def test_task_update_no_fields_errors(self):
        task_id = await task_create("Task")
        result = await task_update(task_id)
        assert result == "error:no fields to update"

    async def test_task_update_verification_criteria(self):
        task_id = await task_create("Task")
        result = await task_update(task_id, verification_criteria="Must pass")
        assert result == "ok"
        details = await task_get(task_id)
        assert "Must pass" in details
