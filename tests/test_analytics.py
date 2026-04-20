"""Tests for analytics module and task_analytics MCP tool."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import src.db as db_module
from src.analytics import (
    agent_performance,
    step_bottlenecks,
    velocity,
    workflow_summary,
)
from src.server import task_analytics, task_complete, task_create, task_fail, task_start

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_done_workflow(name: str = "Workflow") -> str:
    """Create a root task with one child step, complete both, return root id."""
    root_id = await task_create(name)
    child_id = await task_create("Step A", parent_id=root_id)
    await task_start(child_id)
    await task_complete(child_id)
    await task_start(root_id)
    await task_complete(root_id)
    return root_id


async def _backdate(task_id: str, days_ago: int) -> None:
    """Move a task's created_at/completed_at back in time for testing cutoffs."""
    conn = await db_module.get_db()
    past = (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()
    await conn.execute(
        "UPDATE tasks SET created_at = ?, completed_at = ? WHERE id = ?",
        (past, past, task_id),
    )
    await conn.commit()


# ---------------------------------------------------------------------------
# workflow_summary
# ---------------------------------------------------------------------------


class TestWorkflowSummary:
    async def test_no_data_returns_message(self):
        result = await workflow_summary(days=30)
        assert result == "No data for the specified period."

    async def test_root_without_children_excluded(self):
        await task_create("Lone root")
        result = await workflow_summary(days=30)
        assert result == "No data for the specified period."

    async def test_counts_workflow_with_children(self):
        await _make_done_workflow("W1")
        result = await workflow_summary(days=30)
        assert "Total workflows: 1" in result
        assert "Completed: 1" in result

    async def test_completion_rate_percentage(self):
        await _make_done_workflow("W1")
        root_id = await task_create("W2")
        await task_create("Step", parent_id=root_id)
        result = await workflow_summary(days=30)
        assert "Total workflows: 2" in result
        assert "Completed: 1 (50%)" in result

    async def test_failed_count_shown(self):
        root_id = await task_create("Failed W")
        await task_create("Step", parent_id=root_id)
        await task_start(root_id)
        await task_fail(root_id, "oops")
        result = await workflow_summary(days=30)
        assert "Failed: 1" in result

    async def test_respects_days_cutoff(self):
        root_id = await task_create("Old W")
        await task_create("Step", parent_id=root_id)
        await _backdate(root_id, days_ago=60)
        result = await workflow_summary(days=30)
        assert result == "No data for the specified period."

    async def test_duration_stats_shown_when_available(self):
        await _make_done_workflow("Timed")
        result = await workflow_summary(days=30)
        # At least the avg duration line should appear
        assert "Avg duration:" in result


# ---------------------------------------------------------------------------
# step_bottlenecks
# ---------------------------------------------------------------------------


class TestStepBottlenecks:
    async def test_no_data_returns_message(self):
        result = await step_bottlenecks(days=30)
        assert result == "No data for the specified period."

    async def test_root_tasks_excluded(self):
        # A root task (parent_id IS NULL) that is done should not appear
        root_id = await task_create("Root Only")
        await task_start(root_id)
        await task_complete(root_id)
        result = await step_bottlenecks(days=30)
        assert result == "No data for the specified period."

    async def test_completed_step_appears(self):
        root_id = await task_create("Parent")
        child_id = await task_create("Slow Step", parent_id=root_id)
        await task_start(child_id)
        await task_complete(child_id)
        result = await step_bottlenecks(days=30)
        assert "Slow Step" in result

    async def test_pending_step_excluded(self):
        root_id = await task_create("Parent")
        await task_create("Pending Step", parent_id=root_id)
        result = await step_bottlenecks(days=30)
        assert result == "No data for the specified period."

    async def test_header_present(self):
        root_id = await task_create("P")
        child_id = await task_create("S", parent_id=root_id)
        await task_start(child_id)
        await task_complete(child_id)
        result = await step_bottlenecks(days=30)
        assert "Step Bottlenecks" in result
        assert "Avg" in result
        assert "Max" in result

    async def test_respects_days_cutoff(self):
        root_id = await task_create("Parent")
        child_id = await task_create("Old Step", parent_id=root_id)
        await task_start(child_id)
        await task_complete(child_id)
        conn = await db_module.get_db()
        past = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        await conn.execute(
            "UPDATE tasks SET created_at = ? WHERE id = ?",
            (past, child_id),
        )
        await conn.commit()
        result = await step_bottlenecks(days=30)
        assert result == "No data for the specified period."


# ---------------------------------------------------------------------------
# agent_performance
# ---------------------------------------------------------------------------


class TestAgentPerformance:
    async def test_no_data_returns_message(self):
        result = await agent_performance(days=30)
        assert result == "No data for the specified period."

    async def test_agent_from_metadata_counted(self):
        root_id = await task_create("R")
        conn = await db_module.get_db()
        await conn.execute(
            "INSERT INTO tasks (id, name, status, parent_id, metadata, created_at)"
            " VALUES ('s1', 'Step', 'done', ?, ?, ?)",
            (
                root_id,
                json.dumps({"agent": "developer"}),
                datetime.now(UTC).isoformat(),
            ),
        )
        await conn.commit()
        result = await agent_performance(days=30)
        assert "developer" in result
        assert "100%" in result

    async def test_unknown_agent_for_missing_metadata(self):
        root_id = await task_create("R")
        conn = await db_module.get_db()
        await conn.execute(
            "INSERT INTO tasks (id, name, status, parent_id, metadata, created_at)"
            " VALUES ('s2', 'Step', 'done', ?, '{}', ?)",
            (root_id, datetime.now(UTC).isoformat()),
        )
        await conn.commit()
        result = await agent_performance(days=30)
        assert "unknown" in result

    async def test_failed_task_reduces_success_rate(self):
        root_id = await task_create("R")
        conn = await db_module.get_db()
        now = datetime.now(UTC).isoformat()
        meta = json.dumps({"agent": "qa-engineer"})
        await conn.execute(
            "INSERT INTO tasks (id, name, status, parent_id, metadata, created_at)"
            " VALUES ('s3', 'Step done', 'done', ?, ?, ?)",
            (root_id, meta, now),
        )
        await conn.execute(
            "INSERT INTO tasks (id, name, status, parent_id, metadata, created_at)"
            " VALUES ('s4', 'Step fail', 'failed', ?, ?, ?)",
            (root_id, meta, now),
        )
        await conn.commit()
        result = await agent_performance(days=30)
        assert "qa-engineer" in result
        assert "50%" in result

    async def test_header_present(self):
        root_id = await task_create("R")
        conn = await db_module.get_db()
        await conn.execute(
            "INSERT INTO tasks (id, name, status, parent_id, metadata, created_at)"
            " VALUES ('s5', 'Step', 'done', ?, '{}', ?)",
            (root_id, datetime.now(UTC).isoformat()),
        )
        await conn.commit()
        result = await agent_performance(days=30)
        assert "Agent Performance" in result
        assert "Success" in result


# ---------------------------------------------------------------------------
# velocity
# ---------------------------------------------------------------------------


class TestVelocity:
    async def test_no_data_returns_message(self):
        result = await velocity(days=30)
        assert result == "No data for the specified period."

    async def test_child_tasks_excluded(self):
        root_id = await task_create("R")
        child_id = await task_create("C", parent_id=root_id)
        await task_start(child_id)
        await task_complete(child_id)
        result = await velocity(days=30)
        assert result == "No data for the specified period."

    async def test_completed_root_counted(self):
        await _make_done_workflow("Done W")
        result = await velocity(days=30)
        assert "Velocity" in result
        assert "Avg:" in result

    async def test_weekly_grouping_shown(self):
        await _make_done_workflow("W1")
        result = await velocity(days=30)
        # Should contain a week key like 2026-W...
        assert "W" in result

    async def test_respects_days_cutoff(self):
        root_id = await task_create("Old W")
        await task_create("Step", parent_id=root_id)
        await task_start(root_id)
        await task_complete(root_id)
        conn = await db_module.get_db()
        past = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        await conn.execute(
            "UPDATE tasks SET completed_at = ? WHERE id = ?",
            (past, root_id),
        )
        await conn.commit()
        result = await velocity(days=30)
        assert result == "No data for the specified period."


# ---------------------------------------------------------------------------
# task_analytics tool
# ---------------------------------------------------------------------------


class TestTaskAnalyticsTool:
    async def test_unknown_query_returns_error(self):
        result = await task_analytics(query="nonsense")
        assert result.startswith("error:unknown query")
        assert "agent_performance" in result
        assert "step_bottlenecks" in result
        assert "velocity" in result
        assert "workflow_summary" in result

    async def test_workflow_summary_query(self):
        result = await task_analytics(query="workflow_summary")
        # Empty DB — should return no-data message
        assert "No data" in result

    async def test_step_bottlenecks_query(self):
        result = await task_analytics(query="step_bottlenecks")
        assert "No data" in result

    async def test_agent_performance_query(self):
        result = await task_analytics(query="agent_performance")
        assert "No data" in result

    async def test_velocity_query(self):
        result = await task_analytics(query="velocity")
        assert "No data" in result

    async def test_days_parameter_forwarded(self):
        await _make_done_workflow("Recent W")
        result = await task_analytics(query="workflow_summary", days=90)
        assert "Total workflows: 1" in result

    async def test_workflow_summary_with_data(self):
        await _make_done_workflow("My flow")
        result = await task_analytics(query="workflow_summary", days=30)
        assert "Total workflows: 1" in result
        assert "Completed: 1" in result
