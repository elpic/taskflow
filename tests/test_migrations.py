"""Tests for schema auto-migration (src/migrations.py + src/db.py)."""

from __future__ import annotations

import aiosqlite
import pytest
import src.db as db_module
from src.db import _table_exists, get_db
from src.migrations import (
    LATEST_VERSION,
    MIGRATIONS,
    _m001_baseline,
    apply_pending_migrations,
    get_current_version,
    stamp_version,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Minimal tasks DDL — simulates a pre-migration DB.
_LEGACY_TASKS_DDL = """
CREATE TABLE tasks (
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
    completed_at TEXT
);
"""

_SCHEMA_VERSION_DDL = (
    "CREATE TABLE schema_version (version INTEGER NOT NULL, applied_at TEXT NOT NULL)"
)

_INSERT_VERSION = (
    "INSERT INTO schema_version (version, applied_at) VALUES (?, datetime('now'))"
)


async def _open_db(path) -> aiosqlite.Connection:
    """Open a bare aiosqlite connection (no get_db() singleton)."""
    db = await aiosqlite.connect(str(path))
    await db.execute("PRAGMA foreign_keys=ON")
    db.row_factory = aiosqlite.Row
    return db


# ---------------------------------------------------------------------------
# get_current_version
# ---------------------------------------------------------------------------


class TestGetCurrentVersion:
    async def test_returns_none_when_table_missing(self, tmp_path):
        """No schema_version table -> None."""
        db = await _open_db(tmp_path / "v.db")
        try:
            result = await get_current_version(db)
            assert result is None
        finally:
            await db.close()

    async def test_returns_zero_when_table_empty(self, tmp_path):
        """Empty schema_version -> 0 (MAX returns NULL)."""
        db = await _open_db(tmp_path / "v.db")
        try:
            await db.execute(_SCHEMA_VERSION_DDL)
            await db.commit()
            result = await get_current_version(db)
            assert result == 0
        finally:
            await db.close()

    async def test_returns_current_version(self, tmp_path):
        """Returns the max version stamped into the table."""
        db = await _open_db(tmp_path / "v.db")
        try:
            await db.execute(_SCHEMA_VERSION_DDL)
            await db.execute(_INSERT_VERSION, (1,))
            await db.commit()
            result = await get_current_version(db)
            assert result == 1
        finally:
            await db.close()

    async def test_returns_max_of_multiple_stamps(self, tmp_path):
        """When multiple versions are stamped, MAX is returned."""
        db = await _open_db(tmp_path / "v.db")
        try:
            await db.execute(_SCHEMA_VERSION_DDL)
            for v in (0, 1, 2):
                await db.execute(_INSERT_VERSION, (v,))
            await db.commit()
            result = await get_current_version(db)
            assert result == 2
        finally:
            await db.close()


# ---------------------------------------------------------------------------
# stamp_version
# ---------------------------------------------------------------------------


class TestStampVersion:
    async def test_inserts_row_with_correct_version(self, tmp_path):
        db = await _open_db(tmp_path / "s.db")
        try:
            await db.execute(_SCHEMA_VERSION_DDL)
            await stamp_version(db, 1)
            await db.commit()

            cursor = await db.execute("SELECT version FROM schema_version")
            rows = list(await cursor.fetchall())
            assert len(rows) == 1
            assert rows[0][0] == 1
        finally:
            await db.close()

    async def test_applied_at_is_populated(self, tmp_path):
        db = await _open_db(tmp_path / "s.db")
        try:
            await db.execute(_SCHEMA_VERSION_DDL)
            await stamp_version(db, 1)
            await db.commit()

            cursor = await db.execute("SELECT applied_at FROM schema_version")
            row = await cursor.fetchone()
            assert row is not None
            assert row[0]  # non-empty string
        finally:
            await db.close()

    async def test_creates_audit_trail(self, tmp_path):
        """Stamping twice creates two rows (audit trail)."""
        db = await _open_db(tmp_path / "s.db")
        try:
            await db.execute(_SCHEMA_VERSION_DDL)
            await stamp_version(db, 1)
            await stamp_version(db, 1)
            await db.commit()

            cursor = await db.execute("SELECT COUNT(*) FROM schema_version")
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == 2
        finally:
            await db.close()

    async def test_multiple_different_versions_stored(self, tmp_path):
        """Stamping v0 then v1 stores both rows."""
        db = await _open_db(tmp_path / "s.db")
        try:
            await db.execute(_SCHEMA_VERSION_DDL)
            await stamp_version(db, 0)
            await stamp_version(db, 1)
            await db.commit()

            cursor = await db.execute(
                "SELECT version FROM schema_version ORDER BY version"
            )
            rows = await cursor.fetchall()
            assert [r[0] for r in rows] == [0, 1]
        finally:
            await db.close()


# ---------------------------------------------------------------------------
# _m001_baseline (idempotency)
# ---------------------------------------------------------------------------


class TestM001Baseline:
    async def _make_legacy_db(self, path) -> aiosqlite.Connection:
        db = await _open_db(path)
        await db.executescript(_LEGACY_TASKS_DDL)
        await db.commit()
        return db

    async def test_adds_missing_columns(self, tmp_path):
        db = await self._make_legacy_db(tmp_path / "b.db")
        try:
            await _m001_baseline(db)
            await db.commit()

            cursor = await db.execute(
                "SELECT agent_output, position, "
                "idempotency_key, context_summary "
                "FROM tasks LIMIT 0"
            )
            assert cursor is not None
        finally:
            await db.close()

    async def test_creates_task_dependencies_table(self, tmp_path):
        db = await self._make_legacy_db(tmp_path / "b.db")
        try:
            await _m001_baseline(db)
            await db.commit()
            assert await _table_exists(db, "task_dependencies")
        finally:
            await db.close()

    async def test_creates_task_events_table(self, tmp_path):
        db = await self._make_legacy_db(tmp_path / "b.db")
        try:
            await _m001_baseline(db)
            await db.commit()
            assert await _table_exists(db, "task_events")
        finally:
            await db.close()

    async def test_idempotent_run_twice_no_error(self, tmp_path):
        """Running _m001_baseline twice must not raise."""
        db = await self._make_legacy_db(tmp_path / "b.db")
        try:
            await _m001_baseline(db)
            await db.commit()
            await _m001_baseline(db)
            await db.commit()
        finally:
            await db.close()

    async def test_idempotent_on_fully_migrated_schema(self, tmp_path):
        """Baseline on a complete schema must not error."""
        db = await _open_db(tmp_path / "b.db")
        try:
            await db.executescript(db_module.SCHEMA)
            await db.commit()
            await _m001_baseline(db)
            await db.commit()
        finally:
            await db.close()

    async def test_existing_data_preserved(self, tmp_path):
        """Rows present before migration are intact afterwards."""
        db = await self._make_legacy_db(tmp_path / "b.db")
        try:
            await db.execute(
                "INSERT INTO tasks (id, name, status, created_at)"
                " VALUES ('abc', 'Old Task', 'pending',"
                " '2024-01-01T00:00:00')"
            )
            await db.commit()

            await _m001_baseline(db)
            await db.commit()

            cursor = await db.execute("SELECT id, name FROM tasks WHERE id = 'abc'")
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "abc"
            assert row[1] == "Old Task"
        finally:
            await db.close()


# ---------------------------------------------------------------------------
# apply_pending_migrations
# ---------------------------------------------------------------------------


class TestApplyPendingMigrations:
    async def test_applies_migrations_above_current(self, tmp_path):
        """DB at v0 should have v1 migration applied."""
        db = await _open_db(tmp_path / "m.db")
        try:
            await db.executescript(_LEGACY_TASKS_DDL)
            await db.execute(_SCHEMA_VERSION_DDL)
            await stamp_version(db, 0)
            await db.commit()

            await apply_pending_migrations(db)

            version = await get_current_version(db)
            assert version == LATEST_VERSION
        finally:
            await db.close()

    async def test_skips_already_applied(self, tmp_path):
        """DB at LATEST_VERSION: no new stamps added."""
        db = await _open_db(tmp_path / "m.db")
        try:
            await db.executescript(db_module.SCHEMA)
            await stamp_version(db, LATEST_VERSION)
            await db.commit()

            cursor = await db.execute("SELECT COUNT(*) FROM schema_version")
            row_before = await cursor.fetchone()
            assert row_before is not None
            count_before = row_before[0]

            await apply_pending_migrations(db)

            cursor = await db.execute("SELECT COUNT(*) FROM schema_version")
            row_after = await cursor.fetchone()
            assert row_after is not None
            count_after = row_after[0]

            assert count_after == count_before
        finally:
            await db.close()

    async def test_handles_zero_version(self, tmp_path):
        """DB at v0 with schema_version: all migrations run."""
        db = await _open_db(tmp_path / "m.db")
        try:
            await db.executescript(_LEGACY_TASKS_DDL)
            await db.execute(_SCHEMA_VERSION_DDL)
            await db.commit()

            await apply_pending_migrations(db)

            version = await get_current_version(db)
            assert version == LATEST_VERSION
        finally:
            await db.close()

    async def test_version_bumped_after_migration(self, tmp_path):
        """After applying, version equals LATEST_VERSION."""
        db = await _open_db(tmp_path / "m.db")
        try:
            await db.executescript(_LEGACY_TASKS_DDL)
            await db.execute(_SCHEMA_VERSION_DDL)
            await stamp_version(db, 0)
            await db.commit()

            await apply_pending_migrations(db)

            assert await get_current_version(db) == LATEST_VERSION
        finally:
            await db.close()


# ---------------------------------------------------------------------------
# MIGRATIONS list / LATEST_VERSION constants
# ---------------------------------------------------------------------------


class TestMigrationsRegistry:
    def test_migrations_list_not_empty(self):
        assert len(MIGRATIONS) >= 1

    def test_latest_version_matches_last_migration(self):
        assert MIGRATIONS[-1].version == LATEST_VERSION

    def test_migration_versions_are_unique(self):
        versions = [m.version for m in MIGRATIONS]
        assert len(versions) == len(set(versions))

    def test_migration_versions_are_ascending(self):
        versions = [m.version for m in MIGRATIONS]
        assert versions == sorted(versions)

    def test_migration_step_has_description(self):
        for m in MIGRATIONS:
            assert isinstance(m.description, str)
            assert m.description.strip()

    def test_migration_step_is_callable(self):
        for m in MIGRATIONS:
            assert callable(m.apply)


# ---------------------------------------------------------------------------
# get_db() integration — full lifecycle tests via the singleton
# ---------------------------------------------------------------------------


class TestGetDbFreshInstall:
    async def test_schema_version_table_exists(self):
        """Fresh install: schema_version table is created."""
        db = await get_db()
        assert await _table_exists(db, "schema_version")

    async def test_stamped_at_latest_version(self):
        """Fresh install stamps LATEST_VERSION directly."""
        db = await get_db()
        version = await get_current_version(db)
        assert version == LATEST_VERSION

    async def test_tasks_table_exists(self):
        db = await get_db()
        assert await _table_exists(db, "tasks")

    async def test_task_dependencies_table_exists(self):
        db = await get_db()
        assert await _table_exists(db, "task_dependencies")

    async def test_task_events_table_exists(self):
        db = await get_db()
        assert await _table_exists(db, "task_events")


class TestGetDbPreMigrationEnrollment:
    """DB has tasks table but no schema_version."""

    @pytest.fixture(autouse=True)
    async def setup_legacy_db(self, tmp_path, monkeypatch):
        """Create a legacy DB, then point singleton at it."""
        legacy_path = tmp_path / "legacy.db"

        raw = await aiosqlite.connect(str(legacy_path))
        await raw.executescript(_LEGACY_TASKS_DDL)
        await raw.execute(
            "INSERT INTO tasks (id, name, status, created_at)"
            " VALUES ('t1', 'Legacy Task', 'pending',"
            " '2024-01-01T00:00:00')"
        )
        await raw.commit()
        await raw.close()

        monkeypatch.setattr(db_module, "DB_PATH", legacy_path)
        monkeypatch.setattr(db_module, "_db", None)
        yield
        await db_module.close_db()

    async def test_schema_version_table_created(self):
        db = await get_db()
        assert await _table_exists(db, "schema_version")

    async def test_enrolled_at_latest_version(self):
        db = await get_db()
        version = await get_current_version(db)
        assert version == LATEST_VERSION

    async def test_existing_data_not_lost(self):
        db = await get_db()
        cursor = await db.execute("SELECT id, name FROM tasks WHERE id = 't1'")
        row = await cursor.fetchone()
        assert row is not None
        assert row["name"] == "Legacy Task"

    async def test_new_columns_added(self):
        db = await get_db()
        cursor = await db.execute(
            "SELECT agent_output, position, "
            "idempotency_key, context_summary "
            "FROM tasks WHERE id = 't1'"
        )
        row = await cursor.fetchone()
        assert row is not None


class TestGetDbAlreadyEnrolled:
    """DB already at LATEST_VERSION — no migrations run."""

    @pytest.fixture(autouse=True)
    async def setup_enrolled_db(self, tmp_path, monkeypatch):
        enrolled_path = tmp_path / "enrolled.db"

        raw = await aiosqlite.connect(str(enrolled_path))
        raw.row_factory = aiosqlite.Row
        await raw.executescript(db_module.SCHEMA)
        await raw.execute(_INSERT_VERSION, (LATEST_VERSION,))
        await raw.commit()
        await raw.close()

        monkeypatch.setattr(db_module, "DB_PATH", enrolled_path)
        monkeypatch.setattr(db_module, "_db", None)
        yield
        await db_module.close_db()

    async def test_version_unchanged(self):
        db = await get_db()
        assert await get_current_version(db) == LATEST_VERSION

    async def test_no_extra_stamps_added(self):
        db = await get_db()
        cursor = await db.execute("SELECT COUNT(*) FROM schema_version")
        row = await cursor.fetchone()
        assert row is not None
        count = row[0]
        assert count == 1
