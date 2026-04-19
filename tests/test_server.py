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


class TestTaskListFiltering:
    async def test_filter_by_status(self):
        await task_create("Pending A")
        t2 = await task_create("Started B")
        await task_start(t2)
        result = await task_list(status="pending")
        assert "Pending A" in result
        assert "Started B" not in result

    async def test_filter_by_status_in_progress(self):
        await task_create("Pending")
        t2 = await task_create("Active")
        await task_start(t2)
        result = await task_list(status="in_progress")
        assert "Active" in result
        assert "Pending" not in result

    async def test_filter_by_parent_id(self):
        root = await task_create("Root")
        await task_create("Child A", parent_id=root)
        await task_create("Orphan")
        result = await task_list(parent_id=root)
        assert "Child A" in result
        assert "Orphan" not in result

    async def test_filter_invalid_status(self):
        result = await task_list(status="bogus")
        assert "error:invalid status" in result

    async def test_filter_invalid_parent(self):
        result = await task_list(parent_id="nonexistent")
        assert result == "error:not found"

    async def test_filter_combined(self):
        root = await task_create("Root")
        await task_create("Pending Child", parent_id=root)
        active_id = await task_create("Active Child", parent_id=root)
        await task_start(active_id)
        result = await task_list(status="pending", parent_id=root)
        assert "Pending Child" in result
        assert "Active Child" not in result

    async def test_no_filter_returns_all(self):
        await task_create("Task A")
        await task_create("Task B")
        result = await task_list()
        assert "Task A" in result
        assert "Task B" in result


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


class TestIdempotentCreation:
    async def test_first_creation_with_key(self):
        task_id = await task_create("Task A", idempotency_key="key-1")
        assert task_id  # returns an ID
        assert "error" not in task_id

    async def test_duplicate_key_returns_existing(self):
        id1 = await task_create("Task A", idempotency_key="key-dup")
        id2 = await task_create("Task A", idempotency_key="key-dup")
        assert id1 == id2

    async def test_different_keys_create_separate_tasks(self):
        id1 = await task_create("Task A", idempotency_key="key-a")
        id2 = await task_create("Task B", idempotency_key="key-b")
        assert id1 != id2

    async def test_no_key_always_creates(self):
        id1 = await task_create("Same Name")
        id2 = await task_create("Same Name")
        assert id1 != id2

    async def test_idempotent_with_task_type(self):
        result1 = await task_create(
            "Typed", task_type="simple", idempotency_key="key-typed"
        )
        result2 = await task_create(
            "Typed", task_type="simple", idempotency_key="key-typed"
        )
        # First call returns full workflow response, second returns just the ID
        root_id = result1.split("|")[0]
        assert result2 == root_id


class TestAgentOutput:
    async def test_complete_with_output(self):
        task_id = await task_create("Task")
        await task_start(task_id)
        result = await task_complete(task_id, output="Design: use hexagonal arch")
        assert result == "ok"
        details = await task_get(task_id)
        assert "Output: Design: use hexagonal arch" in details

    async def test_complete_without_output(self):
        task_id = await task_create("Task")
        result = await task_complete(task_id)
        assert result == "ok"
        details = await task_get(task_id)
        assert "Output:" not in details

    async def test_output_persists_on_get(self):
        task_id = await task_create("Task")
        await task_start(task_id)
        await task_complete(task_id, output="Test results: 42 passed")
        details = await task_get(task_id)
        assert "Test results: 42 passed" in details

    async def test_output_on_pending_task_auto_starts(self):
        task_id = await task_create("Task")
        result = await task_complete(task_id, output="Quick result")
        assert result == "ok"
        details = await task_get(task_id)
        assert "Quick result" in details
