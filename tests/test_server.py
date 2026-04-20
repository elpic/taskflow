import json

from src import db
from src.server import (
    task_complete,
    task_context,
    task_create,
    task_current,
    task_delete,
    task_fail,
    task_get,
    task_history,
    task_list,
    task_move,
    task_next,
    task_reorder,
    task_reset,
    task_resume,
    task_search,
    task_start,
    task_stats,
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


class TestTaskDelete:
    async def test_delete_not_found(self):
        result = await task_delete("nonexistent")
        assert result == "error:not found"

    async def test_delete_leaf_task(self):
        task_id = await task_create("Leaf")
        result = await task_delete(task_id)
        assert result == "ok"
        tree = await task_list()
        assert "Leaf" not in tree

    async def test_delete_cascades_to_children(self):
        parent_id = await task_create("Parent")
        await task_create("Child A", parent_id=parent_id)
        await task_create("Child B", parent_id=parent_id)
        result = await task_delete(parent_id)
        assert result == "ok"
        tree = await task_list()
        assert tree == "No tasks found."

    async def test_cannot_delete_in_progress(self):
        task_id = await task_create("Active")
        await task_start(task_id)
        result = await task_delete(task_id)
        assert result == "error:cannot delete in-progress task"

    async def test_delete_clears_current_task(self):
        task_id = await task_create("Current")
        await task_start(task_id)
        await task_complete(task_id)
        result = await task_delete(task_id)
        assert result == "ok"
        current = await task_current()
        assert current == "No active task."

    async def test_delete_failed_task(self):
        task_id = await task_create("Failed")
        await task_start(task_id)
        await task_fail(task_id, "broken")
        result = await task_delete(task_id)
        assert result == "ok"


class TestTaskReorder:
    async def test_reorder_not_found(self):
        result = await task_reorder("nonexistent", 0)
        assert result == "error:not found"

    async def test_reorder_sets_position(self):
        task_id = await task_create("Task")
        result = await task_reorder(task_id, 5)
        assert result == "ok"

    async def test_reorder_affects_sibling_order(self):
        parent = await task_create("Parent")
        a = await task_create("A", parent_id=parent)
        b = await task_create("B", parent_id=parent)
        c = await task_create("C", parent_id=parent)
        # Reverse the order: C first, then B, then A
        await task_reorder(c, 0)
        await task_reorder(b, 1)
        await task_reorder(a, 2)
        result = await task_get(parent)
        # C should appear before B which appears before A
        c_pos = result.index("C")
        b_pos = result.index("B")
        a_pos = result.index("A")
        assert c_pos < b_pos < a_pos

    async def test_unpositioned_tasks_sort_after_positioned(self):
        parent = await task_create("Parent")
        await task_create("Unpositioned", parent_id=parent)
        positioned = await task_create("Positioned", parent_id=parent)
        await task_reorder(positioned, 0)
        result = await task_get(parent)
        pos_idx = result.index("Positioned")
        unpos_idx = result.index("Unpositioned")
        assert pos_idx < unpos_idx


class TestTaskSearch:
    async def test_search_empty_query(self):
        result = await task_search("")
        assert result == "error:empty query"

    async def test_search_no_matches(self):
        await task_create("Something Else")
        result = await task_search("nonexistent")
        assert result == "No matching tasks."

    async def test_search_matches_name(self):
        await task_create("Auth Feature")
        await task_create("Unrelated")
        result = await task_search("auth")
        assert "Auth Feature" in result
        assert "Unrelated" not in result

    async def test_search_matches_description(self):
        await task_create("Task", description="Implement authentication")
        result = await task_search("authentication")
        assert "Task" in result

    async def test_search_case_insensitive(self):
        await task_create("UPPERCASE TASK")
        result = await task_search("uppercase")
        assert "UPPERCASE TASK" in result

    async def test_search_shows_parent_info(self):
        parent = await task_create("Parent")
        await task_create("Child Task", parent_id=parent)
        result = await task_search("Child")
        assert "parent:" in result


class TestTaskMove:
    async def test_move_not_found(self):
        result = await task_move("nonexistent")
        assert result == "error:not found"

    async def test_move_to_new_parent(self):
        root_a = await task_create("Root A")
        root_b = await task_create("Root B")
        child = await task_create("Child", parent_id=root_a)
        result = await task_move(child, new_parent_id=root_b)
        assert result == "ok"
        # Child should now be under Root B
        details = await task_get(root_b)
        assert "Child" in details

    async def test_move_to_root(self):
        parent = await task_create("Parent")
        child = await task_create("Child", parent_id=parent)
        result = await task_move(child, new_parent_id=None)
        assert result == "ok"
        # Child should be a root now
        tree = await task_list()
        assert "Child" in tree

    async def test_move_cycle_detected(self):
        parent = await task_create("Parent")
        child = await task_create("Child", parent_id=parent)
        result = await task_move(parent, new_parent_id=child)
        assert result == "error:cycle detected"

    async def test_move_invalid_parent(self):
        task_id = await task_create("Task")
        result = await task_move(task_id, new_parent_id="nonexistent")
        assert result == "error:parent not found"

    async def test_move_deep_cycle_detected(self):
        a = await task_create("A")
        b = await task_create("B", parent_id=a)
        c = await task_create("C", parent_id=b)
        # Try to move A under C — should detect cycle
        result = await task_move(a, new_parent_id=c)
        assert result == "error:cycle detected"


class TestTaskDependencies:
    async def test_create_with_blocked_by(self):
        a_id = await task_create("Task A")
        b_id = await task_create("Task B", blocked_by=[a_id])
        assert "error" not in b_id
        # B exists and can be retrieved
        result = await task_get(b_id)
        assert "Task B" in result

    async def test_start_blocked_task_fails(self):
        a_id = await task_create("Task A")
        b_id = await task_create("Task B", blocked_by=[a_id])
        result = await task_start(b_id)
        assert result.startswith("error:blocked by")
        assert a_id in result

    async def test_start_after_blocker_done(self):
        a_id = await task_create("Task A")
        b_id = await task_create("Task B", blocked_by=[a_id])
        await task_complete(a_id)
        result = await task_start(b_id)
        assert result == "ok"

    async def test_blocked_by_failed_task_shows_status(self):
        a_id = await task_create("Task A")
        b_id = await task_create("Task B", blocked_by=[a_id])
        await task_start(a_id)
        await task_fail(a_id, "broke")
        result = await task_start(b_id)
        assert result.startswith("error:blocked by")
        assert "(failed)" in result

    async def test_list_ready_filter(self):
        # A and B are unblocked (no dependencies); C is blocked by A
        a_id = await task_create("Task A")
        b_id = await task_create("Task B")
        await task_create("Task C", blocked_by=[a_id])
        # Complete A so C becomes ready; start B so it's in_progress (not pending)
        await task_complete(a_id)
        await task_start(b_id)
        result = await task_list(ready=True)
        assert "Task C" in result
        # B is in_progress, not pending — should not appear
        assert "Task B" not in result
        # A is done — should not appear
        assert "Task A" not in result

    async def test_complete_returns_unblocked(self):
        a_id = await task_create("Task A")
        b_id = await task_create("Task B", blocked_by=[a_id])
        result = await task_complete(a_id)
        assert "|unblocked:" in result
        assert b_id in result

    async def test_cycle_detection(self):
        a_id = await task_create("Task A")
        await task_create("Task B", blocked_by=[a_id])
        # A→B→C chain; try to close the cycle: A blocked_by C
        c_id = await task_create("Task C", blocked_by=[a_id])
        from src import db

        result_error = None
        try:
            await db.add_dependencies(a_id, [c_id])
        except ValueError as e:
            result_error = str(e)
        assert result_error is not None
        assert "cycle" in result_error

    async def test_self_dependency_rejected(self):
        a_id = await task_create("Task A")
        from src import db

        result_error = None
        try:
            await db.add_dependencies(a_id, [a_id])
        except ValueError as e:
            result_error = str(e)
        assert result_error is not None
        assert "itself" in result_error

    async def test_get_shows_blocked_by(self):
        a_id = await task_create("Task A")
        b_id = await task_create("Task B", blocked_by=[a_id])
        result = await task_get(b_id)
        assert "Blocked by:" in result
        assert a_id in result

    async def test_workflow_auto_chains_steps(self):
        result = await task_create("My Workflow", task_type="simple")
        # result format: <root_id>|simple|<step1_id>:@agent,<step2_id>:@agent,...
        assert "|" in result
        parts = result.split("|")
        assert len(parts) == 3
        step_entries = parts[2].split(",")
        assert len(step_entries) >= 2
        # Extract the second step's ID
        second_step_id = step_entries[1].split(":")[0]
        # The second step must be blocked by the first step
        second_step_details = await task_get(second_step_id)
        assert "Blocked by:" in second_step_details


class TestTaskStats:
    async def test_stats_not_found(self):
        result = await task_stats("nonexistent")
        assert result == "error:not found"

    async def test_stats_pending_task(self):
        task_id = await task_create("Pending")
        result = await task_stats(task_id)
        assert "Stats: Pending" in result
        assert "pending" in result

    async def test_stats_completed_task(self):
        task_id = await task_create("Done")
        await task_start(task_id)
        await task_complete(task_id)
        result = await task_stats(task_id)
        assert "Duration:" in result

    async def test_stats_in_progress_task(self):
        task_id = await task_create("Active")
        await task_start(task_id)
        result = await task_stats(task_id)
        assert "Elapsed:" in result
        assert "in progress" in result

    async def test_stats_with_children(self):
        parent = await task_create("Parent")
        c1 = await task_create("Child 1", parent_id=parent)
        c2 = await task_create("Child 2", parent_id=parent)
        await task_complete(c1)
        await task_start(c2)
        await task_fail(c2, "broken")
        result = await task_stats(parent)
        assert "Children: 1/2 done, 1 failed" in result
        assert "Child 1" in result
        assert "Child 2" in result


class TestTaskResume:
    async def test_resume_no_active_work(self):
        # No tasks exist at all — should report no active work
        result = await task_resume()
        assert result == "No active work found."

    async def test_resume_finds_active_root(self):
        # Create root, start it; create child, start child — resume() should find root
        root_id = await task_create("Active Root")
        await task_start(root_id)
        child_id = await task_create("Active Child", parent_id=root_id)
        await task_start(child_id)
        result = await task_resume()
        assert "Resume: Active Root" in result
        assert "error" not in result

    async def test_resume_with_explicit_root_id(self):
        # Create root, start it — resume(root_id=id) should return a summary for it
        root_id = await task_create("Explicit Root")
        await task_start(root_id)
        result = await task_resume(root_id=root_id)
        assert "Resume: Explicit Root" in result
        assert "error" not in result

    async def test_resume_with_explicit_root_id_not_found(self):
        # Passing a non-existent root_id should return an error
        result = await task_resume(root_id="nonexistent")
        assert result == "error:not found"

    async def test_resume_with_non_root_id_errors(self):
        # Passing a child task id as root_id should return an error
        root_id = await task_create("Root")
        child_id = await task_create("Child", parent_id=root_id)
        result = await task_resume(root_id=child_id)
        assert result == "error:task is not a root task"

    async def test_resume_shows_current_task(self):
        # Create root with a workflow type so it has named steps; start a child step
        # — resume should show "Current:" with that step's name
        result = await task_create("My Feature", task_type="simple")
        root_id = result.split("|")[0]
        step_ids = [entry.split(":")[0] for entry in result.split("|")[2].split(",")]
        # Start the root then the first step
        await task_start(root_id)
        await task_start(step_ids[0])
        resume_result = await task_resume(root_id=root_id)
        assert "Current:" in resume_result
        # The current task name should appear in the output
        assert "(none)" not in resume_result.split("Current:")[1].split("\n")[0]

    async def test_resume_shows_next_ready(self):
        # Create root, create two chained steps, complete the first step
        # — resume should show "Next ready:" pointing at the second step
        root_id = await task_create("Pipeline Root")
        await task_start(root_id)
        step1_id = await task_create("Step One", parent_id=root_id)
        await task_create("Step Two", parent_id=root_id, blocked_by=[step1_id])
        # Complete step1 so step2 becomes unblocked/ready
        await task_start(step1_id)
        await task_complete(step1_id)
        result = await task_resume(root_id=root_id)
        assert "Next ready:" in result
        assert "Step Two" in result

    async def test_resume_shows_completed_context(self):
        # Create root, create child, complete child with output
        # — resume should include context from completed sibling steps
        root_id = await task_create("Context Root")
        await task_start(root_id)
        step1_id = await task_create("Design Step", parent_id=root_id)
        step2_id = await task_create(
            "Implement Step", parent_id=root_id, blocked_by=[step1_id]
        )
        # Complete step1 with agent output
        await task_start(step1_id)
        await task_complete(
            step1_id, output="Use hexagonal architecture with ports and adapters"
        )
        # Start step2 so it is in_progress
        await task_start(step2_id)
        result = await task_resume(root_id=root_id)
        assert "Context from completed steps:" in result
        assert "Design Step" in result
        assert "Use hexagonal architecture" in result


class TestTaskContext:
    async def test_context_not_found(self):
        result = await task_context("nonexistent")
        assert result == "error:not found"

    async def test_context_root_task(self):
        root = await task_create("Root")
        result = await task_context(root)
        assert "No context available" in result

    async def test_context_no_prior_steps(self):
        parent = await task_create("Parent")
        child = await task_create("First Child", parent_id=parent)
        result = await task_context(child)
        assert "No context from prior steps" in result

    async def test_context_returns_completed_sibling_output(self):
        parent = await task_create("Parent")
        step1 = await task_create("Step 1", parent_id=parent)
        step2 = await task_create("Step 2", parent_id=parent)
        await task_start(step1)
        await task_complete(step1, output="Architecture: hexagonal")
        result = await task_context(step2)
        assert "Step 1" in result
        assert "Architecture: hexagonal" in result

    async def test_context_excludes_incomplete_siblings(self):
        parent = await task_create("Parent")
        step1 = await task_create("Step 1", parent_id=parent)
        step2 = await task_create("Step 2", parent_id=parent)
        step3 = await task_create("Step 3", parent_id=parent)
        await task_start(step1)
        await task_complete(step1, output="Done")
        await task_start(step2)
        result = await task_context(step3)
        assert "Step 1" in result
        assert "Step 2" not in result

    async def test_context_truncation(self):
        parent = await task_create("Parent")
        step1 = await task_create("Step 1", parent_id=parent)
        step2 = await task_create("Step 2", parent_id=parent)
        await task_start(step1)
        await task_complete(step1, output="x" * 10000)
        result = await task_context(step2, max_chars=100)
        assert "...(truncated)" in result
        assert len(result) < 200


class TestTaskHistory:
    async def test_history_not_found(self):
        result = await task_history("nonexistent")
        assert result == "error:not found"

    async def test_history_no_events(self):
        # Manually create a task and do NOT log any events so the events table
        # is empty for that task_id (bypasses server.py which always logs "created").
        from src import db

        task = await db.create_task("Bare Task")
        result = await task_history(task.id)
        assert result == "No events found."

    async def test_history_after_create(self):
        task_id = await task_create("My Task")
        result = await task_history(task_id)
        assert "created" in result
        assert "My Task" in result

    async def test_history_after_lifecycle(self):
        task_id = await task_create("Lifecycle Task")
        await task_start(task_id)
        await task_complete(task_id)
        result = await task_history(task_id)
        lines = result.strip().splitlines()
        event_types = [line.split("] ")[1].split(":")[0] for line in lines]
        assert event_types == ["created", "started", "completed"]

    async def test_history_after_fail(self):
        task_id = await task_create("Failing Task")
        await task_start(task_id)
        await task_fail(task_id, "something broke")
        result = await task_history(task_id)
        assert "failed" in result
        assert "something broke" in result

    async def test_history_recursive(self):
        parent_id = await task_create("Parent Task")
        child_id = await task_create("Child Task", parent_id=parent_id)
        await task_start(child_id)
        await task_complete(child_id)
        result = await task_history(parent_id, recursive=True)
        assert "Parent Task" in result
        assert "Child Task" in result
        # Parent has "created"; child has "created", "started", "completed"
        assert result.count("created") >= 2
        assert "completed" in result

    async def test_history_after_delete(self):
        # Create a task so events exist, then delete it.
        # The CASCADE should remove events for the deleted task from task_events.
        from src import db

        task_id = await task_create("Soon Deleted")
        # Confirm the event exists before deletion
        events_before = await db.get_task_history(task_id)
        assert len(events_before) == 1
        assert events_before[0]["event_type"] == "created"

        await task_delete(task_id)

        # After deletion the task row is gone — verify via db directly
        # that no stale events remain (CASCADE should have cleaned them up).
        db_conn = await db.get_db()
        try:
            cursor = await db_conn.execute(
                "SELECT COUNT(*) as cnt FROM task_events WHERE task_id = ?",
                (task_id,),
            )
            row = await cursor.fetchone()
            assert row is not None
            assert row["cnt"] == 0
        finally:
            await db_conn.close()


class TestTaskNext:
    async def test_next_not_found(self):
        result = await task_next("nonexistent")
        assert result == "error:not found"

    async def test_next_returns_ready_step(self):
        # Create root with two chained steps; complete first step so second is ready
        root_id = await task_create("Root Task")
        step1_id = await task_create("Step One", parent_id=root_id)
        step2_id = await task_create(
            "Step Two", parent_id=root_id, blocked_by=[step1_id]
        )
        await task_complete(step1_id)

        result = await task_next(root_id)
        data = json.loads(result)

        assert data["status"] == "next"
        assert data["step_id"] == step2_id
        assert data["step_name"] == "Step Two"

    async def test_next_includes_agent(self):
        # task_type="simple" creates steps with agent assignments stored in metadata
        result = await task_create("My Feature", task_type="simple")
        root_id = result.split("|")[0]

        # The first step (Plan) has no agent — complete it so Execute step is next
        step_ids = [entry.split(":")[0] for entry in result.split("|")[2].split(",")]
        # step_ids[0]=Plan, step_ids[1]=Execute (developer), step_ids[2]=Verify
        await task_complete(step_ids[0])

        next_result = await task_next(root_id)
        data = json.loads(next_result)

        assert data["status"] == "next"
        # The Execute step has agent="developer"
        assert data["agent"] == "developer"

    async def test_next_includes_context(self):
        # Complete step1 with output; task_next for step2 includes context
        root_id = await task_create("Pipeline Root")
        step1_id = await task_create("Design Step", parent_id=root_id)
        step2_id = await task_create(
            "Implement Step", parent_id=root_id, blocked_by=[step1_id]
        )
        await task_start(step1_id)
        await task_complete(step1_id, output="Use hexagonal architecture")

        result = await task_next(root_id)
        data = json.loads(result)

        assert data["status"] == "next"
        assert data["step_id"] == step2_id
        assert len(data["context"]) == 1
        assert data["context"][0]["step"] == "Design Step"
        assert "hexagonal architecture" in data["context"][0]["output"]

    async def test_next_all_done(self):
        # All steps done → all_done
        root_id = await task_create("Finished Root")
        step_id = await task_create("Only Step", parent_id=root_id)
        await task_complete(step_id)

        result = await task_next(root_id)
        data = json.loads(result)

        assert data["status"] == "all_done"
        assert data["root_id"] == root_id
        assert data["completed_count"] == 1

    async def test_next_waiting(self):
        # Create root with one step; start the step — task_next should return waiting
        root_id = await task_create("Active Root")
        step_id = await task_create("In-Flight Step", parent_id=root_id)
        await task_start(step_id)

        result = await task_next(root_id)
        data = json.loads(result)

        assert data["status"] == "waiting"
        assert any(item["id"] == step_id for item in data["in_progress"])

    async def test_next_nested_workflow(self):
        # Nested: root → parent_step → deep_step. Finds deepest.
        root_id = await task_create("Root")
        parent_step_id = await task_create("Parent Step", parent_id=root_id)
        deep_step_id = await task_create("Deep Step", parent_id=parent_step_id)

        result = await task_next(root_id)
        data = json.loads(result)

        assert data["status"] == "next"
        # task_next finds the deepest ready task — which is the grandchild
        assert data["step_id"] == deep_step_id
        assert data["step_name"] == "Deep Step"
        # parent_path should include the intermediate parent's name
        assert "Parent Step" in data["parent_path"]

    async def test_task_create_stores_agent_in_metadata(self):
        # task_create with task_type should store "agent" key in each step's metadata
        result = await task_create("Typed Task", task_type="simple")
        # result format: <root_id>|simple|<step1_id>:@agent,...
        parts = result.split("|")
        step_entries = parts[2].split(",")

        # The Execute step (index 1) has agent="developer"
        execute_step_id = step_entries[1].split(":")[0]
        step_details = await task_get(execute_step_id)

        # Metadata section should contain the agent key
        assert "Metadata:" in step_details


class TestTaskReset:
    async def test_reset_not_found(self):
        result = await task_reset("nonexistent")
        assert result == "error:not found"

    async def test_reset_done_task(self):
        task_id = await task_create("Done Task")
        await task_complete(task_id)
        result = await task_reset(task_id)
        assert result == "ok"
        details = await task_get(task_id)
        assert "pending" in details

    async def test_reset_failed_task(self):
        task_id = await task_create("Failed Task")
        await task_start(task_id)
        await task_fail(task_id, "broken")
        result = await task_reset(task_id)
        assert result == "ok"
        details = await task_get(task_id)
        assert "pending" in details

    async def test_reset_pending_task_errors(self):
        task_id = await task_create("Pending Task")
        result = await task_reset(task_id)
        assert "error:can only reset" in result

    async def test_reset_in_progress_errors(self):
        task_id = await task_create("Active Task")
        await task_start(task_id)
        result = await task_reset(task_id)
        assert "error:can only reset" in result

    async def test_reset_recursive(self):
        parent = await task_create("Parent")
        child = await task_create("Child", parent_id=parent)
        await task_complete(child)
        await task_complete(parent)
        result = await task_reset(parent, recursive=True)
        assert result == "ok"
        parent_details = await task_get(parent)
        assert "pending" in parent_details
        child_details = await task_get(child)
        assert "pending" in child_details

    async def test_reset_clears_output(self):
        task_id = await task_create("Task")
        await task_start(task_id)
        await task_complete(task_id, output="Some output")
        await task_reset(task_id)
        details = await task_get(task_id)
        assert "Output:" not in details


class TestAdaptiveContextEngine:
    async def test_task_complete_stores_summary(self):
        task_id = await task_create("Task")
        await task_start(task_id)
        result = await task_complete(
            task_id,
            output="Detailed output from the agent run",
            summary="Concise summary for downstream",
        )
        assert result == "ok"
        details = await task_get(task_id)
        assert "Output: Detailed output from the agent run" in details
        assert "Summary: Concise summary for downstream" in details

    async def test_task_complete_summary_only(self):
        task_id = await task_create("Task")
        await task_start(task_id)
        result = await task_complete(task_id, summary="Summary without output")
        assert result == "ok"
        details = await task_get(task_id)
        assert "Summary: Summary without output" in details
        assert "Output:" not in details

    async def test_task_next_prefers_summary_over_truncated_output(self):
        root_id = await task_create("Pipeline Root")
        step1_id = await task_create("Design Step", parent_id=root_id)
        await task_create("Implement Step", parent_id=root_id, blocked_by=[step1_id])
        long_output = "x" * 600  # longer than 500-char truncation threshold
        summary_text = "Use ports-and-adapters architecture"
        await task_start(step1_id)
        await task_complete(step1_id, output=long_output, summary=summary_text)

        result = await task_next(root_id)
        data = json.loads(result)

        assert data["status"] == "next"
        assert len(data["context"]) == 1
        assert data["context"][0]["output"] == summary_text
        assert "x" * 10 not in data["context"][0]["output"]

    async def test_task_next_falls_back_to_truncated_when_no_summary(self):
        root_id = await task_create("Pipeline Root")
        step1_id = await task_create("Design Step", parent_id=root_id)
        await task_create("Implement Step", parent_id=root_id, blocked_by=[step1_id])
        long_output = "y" * 600  # longer than 500-char truncation threshold
        await task_start(step1_id)
        await task_complete(step1_id, output=long_output)

        result = await task_next(root_id)
        data = json.loads(result)

        assert data["status"] == "next"
        assert len(data["context"]) == 1
        context_output = data["context"][0]["output"]
        # Should be truncated to 500 chars plus ellipsis marker
        assert context_output == "y" * 500 + "…"

    async def test_task_resume_prefers_summary(self):
        root_id = await task_create("Resume Root")
        await task_start(root_id)
        step1_id = await task_create("Design Step", parent_id=root_id)
        step2_id = await task_create(
            "Implement Step", parent_id=root_id, blocked_by=[step1_id]
        )
        long_output = "z" * 600
        summary_text = "Hexagonal arch chosen"
        await task_start(step1_id)
        await task_complete(step1_id, output=long_output, summary=summary_text)
        await task_start(step2_id)

        result = await task_resume(root_id=root_id)

        assert "Context from completed steps:" in result
        assert summary_text in result
        # The raw long output should NOT appear (not even truncated)
        assert "z" * 10 not in result

    async def test_task_reset_clears_summary(self):
        task_id = await task_create("Task")
        await task_start(task_id)
        await task_complete(task_id, summary="Important context summary")
        details_before = await task_get(task_id)
        assert "Summary: Important context summary" in details_before

        await task_reset(task_id)
        details_after = await task_get(task_id)
        assert "Summary:" not in details_after

class TestParallelStepExecution:
    """Tests for the parallel step execution engine (depends_on DAG wiring)."""

    async def _complete_implement_steps_up_to(
        self, result: str, up_to_name: str
    ) -> dict[str, str]:
        """Complete implement workflow steps up through the named step.

        Uses db.update_task directly to force status=done, bypassing server-level
        verification subtask creation so we can control the DAG state precisely.

        Returns a mapping of step_name -> step_id for all steps.
        """
        from datetime import UTC, datetime

        from src.workflows import WORKFLOWS

        parts = result.split("|")
        step_entries = parts[2].split(",")
        step_names = [s.name for s in WORKFLOWS["implement"]]
        name_to_id: dict[str, str] = {}
        for i, entry in enumerate(step_entries):
            step_id = entry.split(":")[0]
            name_to_id[step_names[i]] = step_id

        # Force each step to done in linear order up to (and including) up_to_name
        now = datetime.now(UTC).isoformat()
        for name in step_names:
            step_id = name_to_id[name]
            await db.update_task(step_id, status="done", completed_at=now)
            if name == up_to_name:
                break

        return name_to_id

    async def test_task_create_parallel_readiness(self):
        """After completing Implement, three parallel steps become ready at once."""
        result = await task_create("Parallel Feature", task_type="implement")
        assert "|" in result, f"Expected workflow response, got: {result}"

        await self._complete_implement_steps_up_to(result, "Implement")
        root_id = result.split("|")[0]

        # get_ready_tasks scoped to the root's children returns all 3 parallel steps
        ready = await db.get_ready_tasks(parent_id=root_id)
        ready_names = {t.name for t in ready}

        assert "Create tests" in ready_names, f"Ready tasks: {ready_names}"
        assert "Documentation" in ready_names, f"Ready tasks: {ready_names}"
        assert "Containerization" in ready_names, f"Ready tasks: {ready_names}"
        assert len(ready_names) == 3, (
            f"Expected exactly 3 ready tasks, got: {ready_names}"
        )

        # task_next reports ONE ready step (the first ready it picks)
        next_result = await task_next(root_id)
        data = json.loads(next_result)
        assert data["status"] == "next"
        parallel_names = {"Create tests", "Documentation", "Containerization"}
        assert data["step_name"] in parallel_names

    async def test_task_create_linear_fallback(self):
        """bugfix workflow (no depends_on) creates a strictly sequential chain."""
        result = await task_create("A Bug", task_type="bugfix")
        assert "|" in result, f"Expected workflow response, got: {result}"

        root_id = result.split("|")[0]
        parts = result.split("|")
        step_entries = parts[2].split(",")
        first_step_id = step_entries[0].split(":")[0]
        second_step_id = step_entries[1].split(":")[0]

        # Before completing any step, only the first should be ready
        ready_before = await db.get_ready_tasks(parent_id=root_id)
        ready_ids_before = {t.id for t in ready_before}
        assert first_step_id in ready_ids_before
        assert second_step_id not in ready_ids_before, (
            "Second step should be blocked until first is done"
        )

        # Complete first step — only second should become ready (not all steps)
        await task_complete(first_step_id)
        ready_after = await db.get_ready_tasks(parent_id=root_id)
        ready_ids_after = {t.id for t in ready_after}
        assert second_step_id in ready_ids_after
        # Must not have all steps unblocked at once
        assert len(ready_ids_after) == 1, (
            f"Expected only 1 ready step after first, got: {ready_ids_after}"
        )

    async def test_task_create_fan_in_blocks_until_all_done(self):
        """Code review stays blocked until all three parallel steps are complete."""
        from datetime import UTC, datetime

        result = await task_create("Fan-In Feature", task_type="implement")
        assert "|" in result, f"Expected workflow response, got: {result}"

        root_id = result.split("|")[0]
        name_to_id = await self._complete_implement_steps_up_to(result, "Implement")

        now = datetime.now(UTC).isoformat()
        code_review_id = name_to_id["Code review"]

        # Complete only Create tests — Documentation and Containerization still pending
        await db.update_task(
            name_to_id["Create tests"], status="done", completed_at=now
        )
        ready = await db.get_ready_tasks(parent_id=root_id)
        ready_ids = {t.id for t in ready}
        assert code_review_id not in ready_ids, (
            "Code review must stay blocked while Documentation/Containerization pending"
        )

        # Complete Documentation — Containerization still pending
        await db.update_task(
            name_to_id["Documentation"], status="done", completed_at=now
        )
        ready = await db.get_ready_tasks(parent_id=root_id)
        ready_ids = {t.id for t in ready}
        assert code_review_id not in ready_ids, (
            "Code review must stay blocked while Containerization is still pending"
        )

        # Complete Containerization — now Code review should unblock
        await db.update_task(
            name_to_id["Containerization"], status="done", completed_at=now
        )
        ready = await db.get_ready_tasks(parent_id=root_id)
        ready_ids = {t.id for t in ready}
        assert code_review_id in ready_ids, (
            "Code review should be ready once all three parallel steps are done"
        )
