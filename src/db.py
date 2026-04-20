import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from .models import Task, TaskStatus

DB_PATH = Path(__file__).parent.parent / "data" / "taskflow.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    parent_id TEXT,
    verification_criteria TEXT,
    verification_result TEXT,
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    agent_output TEXT,
    context_summary TEXT,
    position INTEGER,
    idempotency_key TEXT,
    FOREIGN KEY (parent_id) REFERENCES tasks(id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

CREATE TABLE IF NOT EXISTS current_task (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    task_id TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

INSERT OR IGNORE INTO current_task (id, task_id) VALUES (1, NULL);

CREATE TABLE IF NOT EXISTS task_dependencies (
    task_id TEXT NOT NULL,
    blocked_by_id TEXT NOT NULL,
    PRIMARY KEY (task_id, blocked_by_id),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (blocked_by_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_deps_blocked_by ON task_dependencies(blocked_by_id);

CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    details TEXT DEFAULT '{}',
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_events_task ON task_events(task_id);
"""


_db: aiosqlite.Connection | None = None
_init_lock = asyncio.Lock()


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is not None:
        return _db
    async with _init_lock:
        if _db is not None:
            return _db
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(str(DB_PATH))
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        db.row_factory = aiosqlite.Row
        await db.executescript(SCHEMA)
        # Migrations: add columns if missing
        for col, sql in [
            ("agent_output", "ALTER TABLE tasks ADD COLUMN agent_output TEXT"),
            ("position", "ALTER TABLE tasks ADD COLUMN position INTEGER"),
            (
                "idempotency_key",
                "ALTER TABLE tasks ADD COLUMN idempotency_key TEXT",
            ),
            (
                "context_summary",
                "ALTER TABLE tasks ADD COLUMN context_summary TEXT",
            ),
        ]:
            try:
                await db.execute(f"SELECT {col} FROM tasks LIMIT 0")
            except Exception:
                await db.execute(sql)
        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_idempotency_key"
            " ON tasks(idempotency_key)"
        )
        # Migration: add task_dependencies table if missing
        try:
            await db.execute("SELECT 1 FROM task_dependencies LIMIT 0")
        except Exception:
            await db.execute(
                """CREATE TABLE IF NOT EXISTS task_dependencies (
                    task_id TEXT NOT NULL,
                    blocked_by_id TEXT NOT NULL,
                    PRIMARY KEY (task_id, blocked_by_id),
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (blocked_by_id) REFERENCES tasks(id)
                        ON DELETE CASCADE
                )"""
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_deps_blocked_by"
                " ON task_dependencies(blocked_by_id)"
            )
        # Migration: add task_events table if missing
        try:
            await db.execute("SELECT 1 FROM task_events LIMIT 0")
        except Exception:
            await db.execute(
                """CREATE TABLE IF NOT EXISTS task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    details TEXT DEFAULT '{}',
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                        ON DELETE CASCADE
                )"""
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_task ON task_events(task_id)"
            )
        await db.commit()
        _db = db
        return _db


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


def _row_to_task(row: aiosqlite.Row) -> Task:
    return Task(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        status=TaskStatus(row["status"]),
        parent_id=row["parent_id"],
        verification_criteria=row["verification_criteria"],
        verification_result=row["verification_result"],
        metadata=row["metadata"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        agent_output=row["agent_output"],
        context_summary=row["context_summary"],
        position=row["position"],
        idempotency_key=row["idempotency_key"],
    )


async def create_task(
    name: str,
    description: str = "",
    parent_id: str | None = None,
    verification_criteria: str | None = None,
    metadata: dict | None = None,
    idempotency_key: str | None = None,
) -> Task:
    task_id = str(uuid.uuid4())[:8]
    now = datetime.now(UTC).isoformat()
    meta_json = json.dumps(metadata or {})

    db = await get_db()
    if parent_id:
        cursor = await db.execute("SELECT id FROM tasks WHERE id = ?", (parent_id,))
        if not await cursor.fetchone():
            raise ValueError(f"Parent task '{parent_id}' not found")

    await db.execute(
        """INSERT INTO tasks (id, name, description, status, parent_id,
           verification_criteria, metadata, created_at, idempotency_key)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            task_id,
            name,
            description,
            TaskStatus.PENDING.value,
            parent_id,
            verification_criteria,
            meta_json,
            now,
            idempotency_key,
        ),
    )
    await db.commit()

    cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = await cursor.fetchone()
    if not row:
        raise RuntimeError(f"Failed to retrieve task '{task_id}' after insert")
    return _row_to_task(row)


async def get_task(task_id: str) -> Task | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = await cursor.fetchone()
    return _row_to_task(row) if row else None


async def get_children(task_id: str) -> list[Task]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM tasks WHERE parent_id = ?"
        " ORDER BY position ASC NULLS LAST, created_at ASC",
        (task_id,),
    )
    rows = await cursor.fetchall()
    return [_row_to_task(r) for r in rows]


async def get_all_tasks() -> list[Task]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM tasks ORDER BY created_at")
    rows = await cursor.fetchall()
    return [_row_to_task(r) for r in rows]


async def search_tasks(query: str) -> list[Task]:
    pattern = f"%{query}%"
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM tasks"
        " WHERE name LIKE ? COLLATE NOCASE"
        " OR description LIKE ? COLLATE NOCASE"
        " ORDER BY created_at",
        (pattern, pattern),
    )
    rows = await cursor.fetchall()
    return [_row_to_task(r) for r in rows]


async def get_tasks_filtered(
    status: str | None = None,
    parent_id: str | None = None,
) -> list[Task]:
    conditions = []
    params: list[str] = []

    if status:
        conditions.append("status = ?")
        params.append(status)
    if parent_id:
        conditions.append("parent_id = ?")
        params.append(parent_id)

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = (
        f"SELECT * FROM tasks{where} ORDER BY position ASC NULLS LAST, created_at ASC"
    )

    db = await get_db()
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [_row_to_task(r) for r in rows]


async def update_task(task_id: str, **fields) -> Task:
    allowed = {
        "name",
        "description",
        "status",
        "verification_criteria",
        "verification_result",
        "metadata",
        "started_at",
        "completed_at",
        "agent_output",
        "context_summary",
        "position",
    }
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        task = await get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found")
        return task

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    values.append(task_id)

    db = await get_db()
    await db.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
    await db.commit()
    cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = await cursor.fetchone()
    if not row:
        raise ValueError(f"Task '{task_id}' not found")
    return _row_to_task(row)


async def reset_task(task_id: str) -> None:
    """Reset a task to pending with cleared timing and output fields."""
    db = await get_db()
    await db.execute(
        """UPDATE tasks SET
            status = ?,
            started_at = NULL,
            completed_at = NULL,
            agent_output = NULL,
            context_summary = NULL,
            verification_result = NULL
           WHERE id = ?""",
        (TaskStatus.PENDING.value, task_id),
    )
    await db.commit()


async def move_task(task_id: str, new_parent_id: str | None) -> None:
    db = await get_db()
    # Cycle detection: walk up from new_parent to root
    if new_parent_id:
        current = new_parent_id
        while current:
            if current == task_id:
                raise ValueError("cycle detected")
            cursor = await db.execute(
                "SELECT parent_id FROM tasks WHERE id = ?", (current,)
            )
            row = await cursor.fetchone()
            current = row["parent_id"] if row else None

    await db.execute(
        "UPDATE tasks SET parent_id = ? WHERE id = ?",
        (new_parent_id, task_id),
    )
    await db.commit()


async def find_task_by_idempotency_key(key: str) -> Task | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM tasks WHERE idempotency_key = ?",
        (key,),
    )
    row = await cursor.fetchone()
    return _row_to_task(row) if row else None


async def delete_task(task_id: str) -> None:
    db = await get_db()
    # Recursively collect all descendant IDs
    to_delete = [task_id]
    queue = [task_id]
    while queue:
        current = queue.pop(0)
        cursor = await db.execute(
            "SELECT id FROM tasks WHERE parent_id = ?", (current,)
        )
        rows = await cursor.fetchall()
        for row in rows:
            to_delete.append(row["id"])
            queue.append(row["id"])

    # Clear current_task if it's being deleted
    cursor = await db.execute("SELECT task_id FROM current_task WHERE id = 1")
    row = await cursor.fetchone()
    if row and row["task_id"] in to_delete:
        await db.execute("UPDATE current_task SET task_id = NULL WHERE id = 1")

    # Delete in reverse order (children first) to satisfy FK constraints
    for tid in reversed(to_delete):
        await db.execute("DELETE FROM tasks WHERE id = ?", (tid,))
    await db.commit()


async def set_current_task(task_id: str | None):
    db = await get_db()
    await db.execute("UPDATE current_task SET task_id = ? WHERE id = 1", (task_id,))
    await db.commit()


async def get_current_task_id() -> str | None:
    db = await get_db()
    cursor = await db.execute("SELECT task_id FROM current_task WHERE id = 1")
    row = await cursor.fetchone()
    return row["task_id"] if row else None


async def add_dependencies(task_id: str, blocked_by_ids: list[str]) -> None:
    """Add dependency edges: task_id is blocked by each id in blocked_by_ids.

    Raises ValueError for self-dependency, missing tasks, non-pending task,
    or cycle detection.
    """
    if not blocked_by_ids:
        return

    db = await get_db()
    # Validate that task_id exists and is PENDING
    cursor = await db.execute("SELECT id, status FROM tasks WHERE id = ?", (task_id,))
    row = await cursor.fetchone()
    if not row:
        raise ValueError(f"task '{task_id}' not found")
    if row["status"] != TaskStatus.PENDING.value:
        raise ValueError("can only add dependencies to pending tasks")

    # Validate all blocked_by_ids exist; reject self-dependency
    for bid in blocked_by_ids:
        if bid == task_id:
            raise ValueError("task cannot depend on itself")
        cursor = await db.execute("SELECT id FROM tasks WHERE id = ?", (bid,))
        if not await cursor.fetchone():
            raise ValueError(f"blocker task '{bid}' not found")

    # Cycle detection: BFS from each blocked_by_id through existing
    # dependency edges. If we can reach task_id, adding this edge
    # would create a cycle.
    for bid in blocked_by_ids:
        visited: set[str] = set()
        queue = [bid]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            if current == task_id:
                raise ValueError("cycle detected")
            # Follow edges: tasks that current is blocked by
            cursor = await db.execute(
                "SELECT blocked_by_id FROM task_dependencies WHERE task_id = ?",
                (current,),
            )
            rows = await cursor.fetchall()
            queue.extend(r["blocked_by_id"] for r in rows)

    for bid in blocked_by_ids:
        await db.execute(
            "INSERT OR IGNORE INTO task_dependencies (task_id, blocked_by_id)"
            " VALUES (?, ?)",
            (task_id, bid),
        )
    await db.commit()


async def get_blockers(task_id: str) -> list[Task]:
    """Return tasks that task_id is blocked by."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT t.* FROM tasks t
           JOIN task_dependencies d ON t.id = d.blocked_by_id
           WHERE d.task_id = ?
           ORDER BY t.created_at""",
        (task_id,),
    )
    rows = await cursor.fetchall()
    return [_row_to_task(r) for r in rows]


async def get_dependents(task_id: str) -> list[Task]:
    """Return tasks that are blocked by task_id."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT t.* FROM tasks t
           JOIN task_dependencies d ON t.id = d.task_id
           WHERE d.blocked_by_id = ?
           ORDER BY t.created_at""",
        (task_id,),
    )
    rows = await cursor.fetchall()
    return [_row_to_task(r) for r in rows]


async def find_active_root() -> "Task | None":
    """Find the most recent root task that has IN_PROGRESS work anywhere in its subtree.

    Uses a recursive CTE to walk the full subtree of each root task,
    returning the most recently created root with any in-progress work.
    """
    db = await get_db()
    cursor = await db.execute(
        """
        WITH RECURSIVE subtree(id, root_id) AS (
            SELECT id, id AS root_id FROM tasks WHERE parent_id IS NULL
            UNION ALL
            SELECT t.id, s.root_id
            FROM tasks t
            JOIN subtree s ON t.parent_id = s.id
        )
        SELECT t.* FROM tasks t
        WHERE t.parent_id IS NULL
          AND EXISTS (
              SELECT 1 FROM subtree s
              JOIN tasks d ON d.id = s.id
              WHERE s.root_id = t.id
                AND d.status = ?
          )
        ORDER BY t.created_at DESC
        LIMIT 1
        """,
        (TaskStatus.IN_PROGRESS.value,),
    )
    row = await cursor.fetchone()
    return _row_to_task(row) if row else None


async def log_event(
    task_id: str,
    event_type: str,
    details: dict | None = None,
) -> None:
    """Append an event to the audit trail for a task."""
    now = datetime.now(UTC).isoformat()
    details_json = json.dumps(details or {})
    db = await get_db()
    await db.execute(
        "INSERT INTO task_events (task_id, event_type, timestamp, details)"
        " VALUES (?, ?, ?, ?)",
        (task_id, event_type, now, details_json),
    )
    await db.commit()


async def get_task_history(
    task_id: str,
    recursive: bool = False,
) -> list[dict]:
    """Return the event log for a task, optionally including all descendants.

    Each entry is a dict with keys: event_type, timestamp, task_name, details.
    """
    db = await get_db()
    if recursive:
        # Collect all descendant IDs via BFS
        all_ids = [task_id]
        queue = [task_id]
        while queue:
            current = queue.pop(0)
            cursor = await db.execute(
                "SELECT id FROM tasks WHERE parent_id = ?", (current,)
            )
            rows = await cursor.fetchall()
            for row in rows:
                all_ids.append(row["id"])
                queue.append(row["id"])
        placeholders = ",".join("?" * len(all_ids))
        cursor = await db.execute(
            f"""SELECT e.event_type, e.timestamp, e.details, t.name AS task_name
                FROM task_events e
                JOIN tasks t ON t.id = e.task_id
                WHERE e.task_id IN ({placeholders})
                ORDER BY e.timestamp ASC""",
            all_ids,
        )
    else:
        cursor = await db.execute(
            """SELECT e.event_type, e.timestamp, e.details, t.name AS task_name
               FROM task_events e
               JOIN tasks t ON t.id = e.task_id
               WHERE e.task_id = ?
               ORDER BY e.timestamp ASC""",
            (task_id,),
        )
    rows = await cursor.fetchall()
    return [
        {
            "event_type": row["event_type"],
            "timestamp": row["timestamp"],
            "task_name": row["task_name"],
            "details": row["details"],
        }
        for row in rows
    ]


async def get_all_descendants(root_id: str) -> list[Task]:
    """Return all tasks in the subtree under root_id (not including root itself).

    Uses BFS via get_children to collect all descendants.
    """
    result: list[Task] = []
    queue = [root_id]
    while queue:
        current = queue.pop(0)
        children = await get_children(current)
        for child in children:
            result.append(child)
            queue.append(child.id)
    return result


async def get_ready_tasks(parent_id: str | None = None) -> list[Task]:
    """Return PENDING tasks whose blockers are all DONE.

    A task is ready if it has status=pending AND no row exists in
    task_dependencies where the blocked_by task is NOT done.
    """
    conditions = ["t.status = ?"]
    params: list[str] = [TaskStatus.PENDING.value]

    if parent_id is not None:
        conditions.append("t.parent_id = ?")
        params.append(parent_id)

    where = " AND ".join(conditions)
    query = f"""
        SELECT t.* FROM tasks t
        WHERE {where}
          AND NOT EXISTS (
              SELECT 1 FROM task_dependencies d
              JOIN tasks b ON b.id = d.blocked_by_id
              WHERE d.task_id = t.id
                AND b.status != ?
          )
        ORDER BY t.position ASC NULLS LAST, t.created_at ASC
    """
    params.append(TaskStatus.DONE.value)

    db = await get_db()
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [_row_to_task(r) for r in rows]
