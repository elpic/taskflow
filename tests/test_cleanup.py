"""Tests for the task_cleanup MCP tool and cleanup_done_roots db function."""

from datetime import UTC, datetime, timedelta

import pytest
import src.server as server_module
from src import db
from src.server import task_cleanup, task_complete, task_create, task_fail, task_start


@pytest.fixture(autouse=True)
def reset_hint_shown():
    """Reset the module-level _hint_shown flag before each test.

    task_create appends a first-run hint to the returned task ID the very first
    time it is called with an empty DB, polluting the ID string.  Resetting
    this flag ensures every test starts with a clean slate regardless of
    execution order.
    """
    server_module._hint_shown = True  # mark as already shown → no hint appended
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_old_done_root(name: str, days_old: int = 10) -> str:
    """Create a root task, complete it, then back-date completed_at by days_old.

    Uses the db layer directly to avoid the first-run hint being appended to the
    task ID returned by task_create (server._hint_shown is a module-level global
    that is not reset between tests).
    """
    task = await db.create_task(name)
    task_id = task.id
    old_ts = (datetime.now(UTC) - timedelta(days=days_old)).isoformat()
    await db.update_task(task_id, status="done", completed_at=old_ts)
    return task_id


async def _task_exists(task_id: str) -> bool:
    return (await db.get_task(task_id)) is not None


# ---------------------------------------------------------------------------
# TC001 -Cleanup with old done roots
# ---------------------------------------------------------------------------


class TestCleanupOldDoneRoots:
    async def test_old_done_root_is_deleted(self):
        task_id = await _make_old_done_root("Old Done Task", days_old=10)
        result = await task_cleanup(days=7)
        assert result == "ok|deleted:1"
        assert not await _task_exists(task_id)

    async def test_multiple_old_done_roots_all_deleted(self):
        id1 = await _make_old_done_root("Old A", days_old=10)
        id2 = await _make_old_done_root("Old B", days_old=15)
        result = await task_cleanup(days=7)
        assert result == "ok|deleted:2"
        assert not await _task_exists(id1)
        assert not await _task_exists(id2)

    async def test_returns_correct_deleted_count(self):
        await _make_old_done_root("X1", days_old=8)
        await _make_old_done_root("X2", days_old=9)
        await _make_old_done_root("X3", days_old=10)
        result = await task_cleanup(days=7)
        assert result == "ok|deleted:3"


# ---------------------------------------------------------------------------
# TC002 -Skip non-done root tasks
# ---------------------------------------------------------------------------


class TestSkipNonDoneRoots:
    async def test_pending_root_not_deleted(self):
        task_id = await task_create("Pending Root")
        result = await task_cleanup(days=0)
        assert result == "ok|deleted:0"
        assert await _task_exists(task_id)

    async def test_in_progress_root_not_deleted(self):
        task_id = await task_create("Active Root")
        await task_start(task_id)
        result = await task_cleanup(days=0)
        assert result == "ok|deleted:0"
        assert await _task_exists(task_id)

    async def test_failed_root_not_deleted(self):
        task_id = await task_create("Failed Root")
        await task_start(task_id)
        await task_fail(task_id, "something broke")
        result = await task_cleanup(days=0)
        assert result == "ok|deleted:0"
        assert await _task_exists(task_id)

    async def test_only_non_done_roots_present_returns_zero(self):
        await task_create("Pending A")
        await task_create("Pending B")
        result = await task_cleanup(days=7)
        assert result == "ok|deleted:0"


# ---------------------------------------------------------------------------
# TC003 -Skip recent done roots (completed within N days)
# ---------------------------------------------------------------------------


class TestSkipRecentDoneRoots:
    async def test_recently_completed_root_not_deleted(self):
        task_id = await task_create("Recent Done")
        await task_complete(task_id)  # completed_at = now
        result = await task_cleanup(days=7)
        assert result == "ok|deleted:0"
        assert await _task_exists(task_id)

    async def test_root_completed_just_under_cutoff_not_deleted(self):
        """Task completed 6 days ago survives 7-day cutoff."""
        task_id = await task_create("Six Days Old Task")
        await task_complete(task_id)
        # Set completed_at to 6 days ago — clearly within the 7-day window
        recent_ts = (datetime.now(UTC) - timedelta(days=6)).isoformat()
        conn = await db.get_db()
        await conn.execute(
            "UPDATE tasks SET completed_at = ? WHERE id = ?",
            (recent_ts, task_id),
        )
        await conn.commit()
        result = await task_cleanup(days=7)
        assert result == "ok|deleted:0"
        assert await _task_exists(task_id)

    async def test_root_older_than_cutoff_is_deleted(self):
        task_id = await _make_old_done_root("Old Enough", days_old=8)
        result = await task_cleanup(days=7)
        assert result == "ok|deleted:1"
        assert not await _task_exists(task_id)

    async def test_mix_recent_and_old_only_old_deleted(self):
        recent_id = await task_create("Recent")
        await task_complete(recent_id)  # now

        old_id = await _make_old_done_root("Old", days_old=10)

        result = await task_cleanup(days=7)
        assert result == "ok|deleted:1"
        assert await _task_exists(recent_id)
        assert not await _task_exists(old_id)


# ---------------------------------------------------------------------------
# TC004 -Skip roots with non-done descendants (safety guard)
# ---------------------------------------------------------------------------


class TestSkipRootsWithNonDoneDescendants:
    async def test_done_root_with_pending_child_not_deleted(self):
        root_id = await task_create("Done Root")
        child_id = await task_create("Pending Child", parent_id=root_id)
        # Mark root done with old timestamp but leave child pending
        await task_complete(root_id)
        old_ts = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        conn = await db.get_db()
        await conn.execute(
            "UPDATE tasks SET completed_at = ? WHERE id = ?",
            (old_ts, root_id),
        )
        await conn.commit()
        result = await task_cleanup(days=7)
        assert result == "ok|deleted:0"
        assert await _task_exists(root_id)
        assert await _task_exists(child_id)

    async def test_done_root_with_in_progress_child_not_deleted(self):
        root_id = await task_create("Done Root")
        child_id = await task_create("Active Child", parent_id=root_id)
        await task_start(child_id)
        await task_complete(root_id)
        old_ts = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        conn = await db.get_db()
        await conn.execute(
            "UPDATE tasks SET completed_at = ? WHERE id = ?",
            (old_ts, root_id),
        )
        await conn.commit()
        result = await task_cleanup(days=7)
        assert result == "ok|deleted:0"
        assert await _task_exists(root_id)
        assert await _task_exists(child_id)

    async def test_done_root_with_failed_child_not_deleted(self):
        root_id = await task_create("Done Root")
        child_id = await task_create("Failed Child", parent_id=root_id)
        await task_start(child_id)
        await task_fail(child_id, "broke")
        await task_complete(root_id)
        old_ts = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        conn = await db.get_db()
        await conn.execute(
            "UPDATE tasks SET completed_at = ? WHERE id = ?",
            (old_ts, root_id),
        )
        await conn.commit()
        result = await task_cleanup(days=7)
        assert result == "ok|deleted:0"
        assert await _task_exists(root_id)

    async def test_done_root_with_all_done_children_is_deleted(self):
        root_id = await task_create("Done Root")
        child1 = await task_create("Child A", parent_id=root_id)
        child2 = await task_create("Child B", parent_id=root_id)
        await task_complete(child1)
        await task_complete(child2)
        await task_complete(root_id)
        old_ts = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        conn = await db.get_db()
        await conn.execute(
            "UPDATE tasks SET completed_at = ? WHERE id = ?",
            (old_ts, root_id),
        )
        await conn.commit()
        result = await task_cleanup(days=7)
        assert result == "ok|deleted:1"
        assert not await _task_exists(root_id)
        assert not await _task_exists(child1)
        assert not await _task_exists(child2)

    async def test_deeply_nested_non_done_descendant_blocks_deletion(self):
        root_id = await task_create("Root")
        mid_id = await task_create("Mid", parent_id=root_id)
        leaf_id = await task_create("Leaf (pending)", parent_id=mid_id)
        await task_complete(mid_id)
        await task_complete(root_id)
        old_ts = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        conn = await db.get_db()
        await conn.execute(
            "UPDATE tasks SET completed_at = ? WHERE id = ?",
            (old_ts, root_id),
        )
        await conn.commit()
        result = await task_cleanup(days=7)
        assert result == "ok|deleted:0"
        assert await _task_exists(root_id)
        assert await _task_exists(leaf_id)


# ---------------------------------------------------------------------------
# TC005 -Custom days parameter
# ---------------------------------------------------------------------------


class TestCustomDaysParameter:
    async def test_days_zero_deletes_all_done_roots(self):
        id1 = await _make_old_done_root("Done A", days_old=1)
        id2 = await _make_old_done_root("Done B", days_old=1)
        result = await task_cleanup(days=0)
        assert result == "ok|deleted:2"
        assert not await _task_exists(id1)
        assert not await _task_exists(id2)

    async def test_days_30_skips_task_completed_15_days_ago(self):
        task_id = await _make_old_done_root("Somewhat Old", days_old=15)
        result = await task_cleanup(days=30)
        assert result == "ok|deleted:0"
        assert await _task_exists(task_id)

    async def test_days_1_deletes_task_completed_2_days_ago(self):
        task_id = await _make_old_done_root("Two Days Old", days_old=2)
        result = await task_cleanup(days=1)
        assert result == "ok|deleted:1"
        assert not await _task_exists(task_id)

    async def test_default_days_is_7(self):
        """Calling task_cleanup() with no args uses the default of 7 days."""
        old_id = await _make_old_done_root("Old Default", days_old=8)
        recent_id = await task_create("Recent")
        await task_complete(recent_id)
        result = await task_cleanup()
        assert result == "ok|deleted:1"
        assert not await _task_exists(old_id)
        assert await _task_exists(recent_id)


# ---------------------------------------------------------------------------
# TC006 -Cascade deletion of subtasks and events
# ---------------------------------------------------------------------------


class TestCascadeDeletion:
    async def test_subtasks_deleted_with_root(self):
        root_id = await task_create("Root")
        child1 = await task_create("Child 1", parent_id=root_id)
        child2 = await task_create("Child 2", parent_id=root_id)
        grandchild = await task_create("Grandchild", parent_id=child1)
        await task_complete(grandchild)
        await task_complete(child1)
        await task_complete(child2)
        await task_complete(root_id)
        old_ts = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        conn = await db.get_db()
        await conn.execute(
            "UPDATE tasks SET completed_at = ? WHERE id = ?",
            (old_ts, root_id),
        )
        await conn.commit()
        result = await task_cleanup(days=7)
        assert result == "ok|deleted:1"
        assert not await _task_exists(root_id)
        assert not await _task_exists(child1)
        assert not await _task_exists(child2)
        assert not await _task_exists(grandchild)

    async def test_events_cascade_deleted(self):
        root_id = await task_create("Root With Events")
        child_id = await task_create("Child With Events", parent_id=root_id)
        await task_complete(child_id)
        await task_complete(root_id)
        old_ts = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        conn = await db.get_db()
        await conn.execute(
            "UPDATE tasks SET completed_at = ? WHERE id = ?",
            (old_ts, root_id),
        )
        await conn.commit()
        await task_cleanup(days=7)
        # Verify that events for both root and child are gone
        conn = await db.get_db()
        for tid in (root_id, child_id):
            cursor = await conn.execute(
                "SELECT COUNT(*) as cnt FROM task_events WHERE task_id = ?",
                (tid,),
            )
            row = await cursor.fetchone()
            assert row is not None
            assert row["cnt"] == 0, f"Stale events found for task {tid}"

    async def test_dependencies_cascade_deleted(self):
        root_id = await task_create("Root With Deps")
        step1 = await task_create("Step 1", parent_id=root_id)
        step2 = await task_create("Step 2", parent_id=root_id, blocked_by=[step1])
        await task_complete(step1)
        await task_complete(step2)
        await task_complete(root_id)
        old_ts = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        conn = await db.get_db()
        await conn.execute(
            "UPDATE tasks SET completed_at = ? WHERE id = ?",
            (old_ts, root_id),
        )
        await conn.commit()
        await task_cleanup(days=7)
        conn = await db.get_db()
        cursor = await conn.execute(
            "SELECT COUNT(*) as cnt FROM task_dependencies WHERE task_id = ?",
            (step2,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["cnt"] == 0


# ---------------------------------------------------------------------------
# TC007 -Negative days rejected
# ---------------------------------------------------------------------------


class TestNegativeDaysRejected:
    async def test_negative_days_returns_error(self):
        result = await task_cleanup(days=-1)
        assert result == "error:days must be non-negative"

    async def test_negative_days_does_not_delete_anything(self):
        task_id = await _make_old_done_root("Should Survive", days_old=10)
        result = await task_cleanup(days=-1)
        assert result.startswith("error:")
        assert await _task_exists(task_id)

    async def test_large_negative_days_returns_error(self):
        result = await task_cleanup(days=-999)
        assert result == "error:days must be non-negative"


# ---------------------------------------------------------------------------
# TC008 -Empty DB
# ---------------------------------------------------------------------------


class TestEmptyDb:
    async def test_cleanup_empty_db_returns_zero(self):
        result = await task_cleanup(days=7)
        assert result == "ok|deleted:0"

    async def test_cleanup_empty_db_with_days_zero(self):
        result = await task_cleanup(days=0)
        assert result == "ok|deleted:0"


# ---------------------------------------------------------------------------
# TC009 -Non-root done tasks preserved
# ---------------------------------------------------------------------------


class TestNonRootDoneTasksPreserved:
    async def test_done_child_under_pending_root_not_touched(self):
        root_id = await task_create("Pending Root")
        child_id = await task_create("Done Child", parent_id=root_id)
        await task_complete(child_id)
        # Back-date the child's completed_at to be very old
        old_ts = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        conn = await db.get_db()
        await conn.execute(
            "UPDATE tasks SET completed_at = ? WHERE id = ?",
            (old_ts, child_id),
        )
        await conn.commit()
        result = await task_cleanup(days=0)
        # Root is pending → not a candidate; child is not a root → not affected
        assert result == "ok|deleted:0"
        assert await _task_exists(root_id)
        assert await _task_exists(child_id)

    async def test_cleanup_only_targets_root_tasks(self):
        """
        Two trees: one fully done root (old) that qualifies, and a pending root
        with a done child that is very old. Only the qualifying root is deleted.
        """
        old_done_root = await _make_old_done_root("Qualifies", days_old=10)

        pending_root = await task_create("Pending Root")
        done_child = await task_create("Old Done Child", parent_id=pending_root)
        await task_complete(done_child)
        very_old_ts = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        conn = await db.get_db()
        await conn.execute(
            "UPDATE tasks SET completed_at = ? WHERE id = ?",
            (very_old_ts, done_child),
        )
        await conn.commit()

        result = await task_cleanup(days=7)
        assert result == "ok|deleted:1"
        assert not await _task_exists(old_done_root)
        assert await _task_exists(pending_root)
        assert await _task_exists(done_child)
