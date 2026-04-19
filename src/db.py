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
    position INTEGER,
    idempotency_key TEXT,
    FOREIGN KEY (parent_id) REFERENCES tasks(id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_idempotency_key ON tasks(idempotency_key);

CREATE TABLE IF NOT EXISTS current_task (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    task_id TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

INSERT OR IGNORE INTO current_task (id, task_id) VALUES (1, NULL);
"""


_initialized = False
_init_lock = asyncio.Lock()


async def get_db() -> aiosqlite.Connection:
    global _initialized
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    db.row_factory = aiosqlite.Row
    if not _initialized:
        async with _init_lock:
            if not _initialized:
                await db.executescript(SCHEMA)
                # Migrations: add columns if missing
                for col, sql in [
                    ("agent_output", "ALTER TABLE tasks ADD COLUMN agent_output TEXT"),
                    ("position", "ALTER TABLE tasks ADD COLUMN position INTEGER"),
                    (
                        "idempotency_key",
                        "ALTER TABLE tasks ADD COLUMN idempotency_key TEXT",
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
                await db.commit()
                _initialized = True
    return db


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
    try:
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
    finally:
        await db.close()


async def get_task(task_id: str) -> Task | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        return _row_to_task(row) if row else None
    finally:
        await db.close()


async def get_children(task_id: str) -> list[Task]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE parent_id = ?"
            " ORDER BY position ASC NULLS LAST, created_at ASC",
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [_row_to_task(r) for r in rows]
    finally:
        await db.close()


async def get_all_tasks() -> list[Task]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM tasks ORDER BY created_at")
        rows = await cursor.fetchall()
        return [_row_to_task(r) for r in rows]
    finally:
        await db.close()


async def search_tasks(query: str) -> list[Task]:
    pattern = f"%{query}%"
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM tasks"
            " WHERE name LIKE ? COLLATE NOCASE"
            " OR description LIKE ? COLLATE NOCASE"
            " ORDER BY created_at",
            (pattern, pattern),
        )
        rows = await cursor.fetchall()
        return [_row_to_task(r) for r in rows]
    finally:
        await db.close()


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
    try:
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [_row_to_task(r) for r in rows]
    finally:
        await db.close()


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
    try:
        await db.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
        await db.commit()
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        if not row:
            raise ValueError(f"Task '{task_id}' not found")
        return _row_to_task(row)
    finally:
        await db.close()


async def move_task(task_id: str, new_parent_id: str | None) -> None:
    db = await get_db()
    try:
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
    finally:
        await db.close()


async def find_task_by_idempotency_key(key: str) -> Task | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE idempotency_key = ?",
            (key,),
        )
        row = await cursor.fetchone()
        return _row_to_task(row) if row else None
    finally:
        await db.close()


async def delete_task(task_id: str) -> None:
    db = await get_db()
    try:
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
    finally:
        await db.close()


async def set_current_task(task_id: str | None):
    db = await get_db()
    try:
        await db.execute("UPDATE current_task SET task_id = ? WHERE id = 1", (task_id,))
        await db.commit()
    finally:
        await db.close()


async def get_current_task_id() -> str | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT task_id FROM current_task WHERE id = 1")
        row = await cursor.fetchone()
        return row["task_id"] if row else None
    finally:
        await db.close()
