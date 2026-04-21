"""Workflow analytics — aggregate metrics from task history."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from . import db


async def workflow_summary(days: int = 30) -> str:
    """Average duration, completion rate, and count by workflow type."""
    conn = await db.get_db()
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

    # Root tasks with children (typed workflows) created within the period
    # A "workflow type" can be inferred from root tasks that have children
    # with metadata containing agent assignments
    cursor = await conn.execute(
        """
        SELECT
            t.id, t.name, t.status, t.started_at, t.completed_at,
            COUNT(c.id) as step_count
        FROM tasks t
        LEFT JOIN tasks c ON c.parent_id = t.id
        WHERE t.parent_id IS NULL
          AND t.created_at >= ?
        GROUP BY t.id
        HAVING step_count > 0
        ORDER BY t.created_at DESC
        """,
        (cutoff,),
    )
    rows = list(await cursor.fetchall())

    if not rows:
        return "No data for the specified period."

    total = len(rows)
    done = sum(1 for r in rows if r["status"] == "done")
    failed = sum(1 for r in rows if r["status"] == "failed")

    durations = []
    for r in rows:
        if r["started_at"] and r["completed_at"]:
            start = datetime.fromisoformat(r["started_at"])
            end = datetime.fromisoformat(r["completed_at"])
            if start.tzinfo is None:
                start = start.replace(tzinfo=UTC)
            if end.tzinfo is None:
                end = end.replace(tzinfo=UTC)
            durations.append((end - start).total_seconds())

    avg_dur = sum(durations) / len(durations) if durations else 0

    lines = [f"Workflow Summary (last {days} days):", ""]
    lines.append(f"Total workflows: {total}")
    lines.append(f"Completed: {done} ({round(done * 100 / total)}%)")
    lines.append(f"Failed: {failed} ({round(failed * 100 / total)}%)")
    lines.append(f"In progress: {total - done - failed}")
    if durations:
        lines.append(f"Avg duration: {_format_duration(avg_dur)}")
        lines.append(f"Min duration: {_format_duration(min(durations))}")
        lines.append(f"Max duration: {_format_duration(max(durations))}")

    return "\n".join(lines)


async def step_bottlenecks(days: int = 30) -> str:
    """Top 10 slowest steps by average duration."""
    conn = await db.get_db()
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

    cursor = await conn.execute(
        """
        SELECT
            t.name,
            AVG(CAST(
                (julianday(t.completed_at) - julianday(t.started_at)) * 86400
            AS REAL)) as avg_seconds,
            MAX(CAST(
                (julianday(t.completed_at) - julianday(t.started_at)) * 86400
            AS REAL)) as max_seconds,
            COUNT(*) as count
        FROM tasks t
        WHERE t.parent_id IS NOT NULL
          AND t.status = 'done'
          AND t.started_at IS NOT NULL
          AND t.completed_at IS NOT NULL
          AND t.created_at >= ?
        GROUP BY t.name
        ORDER BY avg_seconds DESC
        LIMIT 10
        """,
        (cutoff,),
    )
    rows = await cursor.fetchall()

    if not rows:
        return "No data for the specified period."

    lines = [f"Step Bottlenecks (last {days} days):", ""]
    lines.append(f"{'#':<4}{'Step':<40}{'Avg':>10}{'Max':>10}{'Count':>7}")
    lines.append("-" * 71)
    for i, r in enumerate(rows, 1):
        avg = _format_duration(r["avg_seconds"]) if r["avg_seconds"] else "N/A"
        mx = _format_duration(r["max_seconds"]) if r["max_seconds"] else "N/A"
        name = r["name"][:38]
        lines.append(f"{i:<4}{name:<40}{avg:>10}{mx:>10}{r['count']:>7}")

    return "\n".join(lines)


async def agent_performance(days: int = 30) -> str:
    """Success rate grouped by agent."""
    conn = await db.get_db()
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

    cursor = await conn.execute(
        """
        SELECT
            t.metadata, t.status
        FROM tasks t
        WHERE t.parent_id IS NOT NULL
          AND t.status IN ('done', 'failed')
          AND t.created_at >= ?
        """,
        (cutoff,),
    )
    rows = await cursor.fetchall()

    if not rows:
        return "No data for the specified period."

    # Aggregate by agent from metadata
    agent_stats: dict[str, dict[str, int]] = {}
    for r in rows:
        try:
            meta = json.loads(r["metadata"]) if r["metadata"] else {}
        except (json.JSONDecodeError, TypeError):
            meta = {}
        agent = meta.get("agent", "unknown")
        if agent not in agent_stats:
            agent_stats[agent] = {"done": 0, "failed": 0}
        agent_stats[agent][r["status"]] += 1

    lines = [f"Agent Performance (last {days} days):", ""]
    lines.append(f"{'Agent':<25}{'Total':>7}{'Done':>7}{'Failed':>7}{'Success':>9}")
    lines.append("-" * 55)

    for agent in sorted(agent_stats.keys()):
        stats = agent_stats[agent]
        total = stats["done"] + stats["failed"]
        rate = f"{round(stats['done'] * 100 / total)}%" if total > 0 else "N/A"
        lines.append(
            f"{agent:<25}{total:>7}{stats['done']:>7}{stats['failed']:>7}{rate:>9}"
        )

    return "\n".join(lines)


async def velocity(days: int = 30) -> str:
    """Tasks completed per week over the specified period."""
    conn = await db.get_db()
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

    cursor = await conn.execute(
        """
        SELECT
            t.completed_at, t.status
        FROM tasks t
        WHERE t.parent_id IS NULL
          AND t.status IN ('done', 'failed')
          AND t.completed_at IS NOT NULL
          AND t.completed_at >= ?
        ORDER BY t.completed_at ASC
        """,
        (cutoff,),
    )
    rows = await cursor.fetchall()

    if not rows:
        return "No data for the specified period."

    # Bucket by ISO week
    weeks: dict[str, dict[str, int]] = {}
    for r in rows:
        completed = datetime.fromisoformat(r["completed_at"])
        week_key = completed.strftime("%G-W%V")
        if week_key not in weeks:
            weeks[week_key] = {"done": 0, "failed": 0}
        weeks[week_key][r["status"]] += 1

    lines = [f"Velocity (last {days} days):", ""]
    lines.append(f"{'Week':<12}{'Completed':>10}{'Failed':>10}")
    lines.append("-" * 32)
    for week in sorted(weeks.keys()):
        stats = weeks[week]
        lines.append(f"{week:<12}{stats['done']:>10}{stats['failed']:>10}")

    total_done = sum(w["done"] for w in weeks.values())
    total_weeks = len(weeks)
    if total_weeks > 0:
        lines.append("")
        lines.append(f"Avg: {total_done / total_weeks:.1f} workflows/week")

    return "\n".join(lines)


def _format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    minutes = total // 60
    secs = total % 60
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"
