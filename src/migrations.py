from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import aiosqlite


@dataclass
class MigrationStep:
    """A numbered, idempotent schema migration."""

    version: int
    description: str
    apply: Callable[[aiosqlite.Connection], Awaitable[None]]


async def get_current_version(db: aiosqlite.Connection) -> int | None:
    """Return current schema version, or None if schema_version table missing."""
    try:
        cursor = await db.execute("SELECT MAX(version) FROM schema_version")
        row = await cursor.fetchone()
        return row[0] if row and row[0] is not None else 0
    except aiosqlite.OperationalError:
        return None


async def stamp_version(db: aiosqlite.Connection, version: int) -> None:
    """Record that the DB is at the given version."""
    await db.execute(
        "INSERT INTO schema_version (version, applied_at) VALUES (?, datetime('now'))",
        (version,),
    )


async def apply_pending_migrations(db: aiosqlite.Connection) -> None:
    """Apply all migrations newer than current version."""
    current = await get_current_version(db)
    if current is None:
        current = 0
    for migration in MIGRATIONS:
        if migration.version > current:
            await migration.apply(db)
            await stamp_version(db, migration.version)
            await db.commit()


# --- Migration functions ---


async def _m001_baseline(db: aiosqlite.Connection) -> None:
    """Baseline: absorb all ad-hoc migrations into version 1."""
    # Add columns if missing (idempotent probe-and-apply)
    columns_to_add = [
        ("agent_output", "ALTER TABLE tasks ADD COLUMN agent_output TEXT"),
        ("position", "ALTER TABLE tasks ADD COLUMN position INTEGER"),
        ("idempotency_key", "ALTER TABLE tasks ADD COLUMN idempotency_key TEXT"),
        ("context_summary", "ALTER TABLE tasks ADD COLUMN context_summary TEXT"),
    ]
    for col, sql in columns_to_add:
        try:
            await db.execute(f"SELECT {col} FROM tasks LIMIT 0")
        except Exception:
            await db.execute(sql)

    # Create tables if missing
    await db.execute("""
        CREATE TABLE IF NOT EXISTS task_dependencies (
            task_id TEXT NOT NULL,
            blocked_by_id TEXT NOT NULL,
            PRIMARY KEY (task_id, blocked_by_id),
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (blocked_by_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS task_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            details TEXT DEFAULT '{}',
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
    """)

    # Create indexes if missing
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_idempotency_key"
        " ON tasks(idempotency_key)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_deps_blocked_by"
        " ON task_dependencies(blocked_by_id)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_task ON task_events(task_id)"
    )


MIGRATIONS = [
    MigrationStep(
        version=1,
        description="baseline: absorb ad-hoc migrations",
        apply=_m001_baseline,
    ),
]

LATEST_VERSION = MIGRATIONS[-1].version
