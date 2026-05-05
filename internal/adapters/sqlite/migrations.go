package sqlite

import (
	"database/sql"
	"fmt"
	"time"
)

const latestVersion = 1

type migrationFn func(tx *sql.Tx) error

type migration struct {
	version     int
	description string
	apply       migrationFn
}

var migrations = []migration{
	{
		version:     1,
		description: "baseline: absorb ad-hoc migrations",
		apply:       m001Baseline,
	},
}

// m001Baseline mirrors Python's _m001_baseline migration.
func m001Baseline(tx *sql.Tx) error {
	// Add columns if missing (idempotent probe-and-apply)
	columnsToAdd := []struct {
		col string
		sql string
	}{
		{"agent_output", "ALTER TABLE tasks ADD COLUMN agent_output TEXT"},
		{"position", "ALTER TABLE tasks ADD COLUMN position INTEGER"},
		{"idempotency_key", "ALTER TABLE tasks ADD COLUMN idempotency_key TEXT"},
		{"context_summary", "ALTER TABLE tasks ADD COLUMN context_summary TEXT"},
	}

	for _, c := range columnsToAdd {
		_, err := tx.Exec(fmt.Sprintf("SELECT %s FROM tasks LIMIT 0", c.col))
		if err != nil {
			if _, addErr := tx.Exec(c.sql); addErr != nil {
				return fmt.Errorf("adding column %s: %w", c.col, addErr)
			}
		}
	}

	// Create tables if missing
	if _, err := tx.Exec(`
		CREATE TABLE IF NOT EXISTS task_dependencies (
			task_id TEXT NOT NULL,
			blocked_by_id TEXT NOT NULL,
			PRIMARY KEY (task_id, blocked_by_id),
			FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
			FOREIGN KEY (blocked_by_id) REFERENCES tasks(id) ON DELETE CASCADE
		)
	`); err != nil {
		return fmt.Errorf("creating task_dependencies: %w", err)
	}

	if _, err := tx.Exec(`
		CREATE TABLE IF NOT EXISTS task_events (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			task_id TEXT NOT NULL,
			event_type TEXT NOT NULL,
			timestamp TEXT NOT NULL,
			details TEXT DEFAULT '{}',
			FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
		)
	`); err != nil {
		return fmt.Errorf("creating task_events: %w", err)
	}

	// Create indexes if missing
	for _, idx := range []string{
		"CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_idempotency_key ON tasks(idempotency_key)",
		"CREATE INDEX IF NOT EXISTS idx_deps_blocked_by ON task_dependencies(blocked_by_id)",
		"CREATE INDEX IF NOT EXISTS idx_events_task ON task_events(task_id)",
	} {
		if _, err := tx.Exec(idx); err != nil {
			return fmt.Errorf("creating index: %w", err)
		}
	}

	return nil
}

// getCurrentVersion returns the current schema version or (nil, nil) if schema_version doesn't exist.
func getCurrentVersion(db *sql.DB) (*int, error) {
	var v int
	err := db.QueryRow("SELECT MAX(version) FROM schema_version").Scan(&v)
	if err != nil {
		// table doesn't exist or no rows
		return nil, nil //nolint:nilerr
	}
	return &v, nil
}

func stampVersion(db *sql.DB, version int) error {
	now := time.Now().UTC().Format("2006-01-02T15:04:05")
	_, err := db.Exec(
		"INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
		version, now,
	)
	return err
}

func stampVersionTx(tx *sql.Tx, version int) error {
	now := time.Now().UTC().Format("2006-01-02T15:04:05")
	_, err := tx.Exec(
		"INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
		version, now,
	)
	return err
}

// tableExists checks if a table exists in SQLite.
func tableExists(db *sql.DB, name string) (bool, error) {
	var count int
	err := db.QueryRow(
		"SELECT COUNT(1) FROM sqlite_master WHERE type='table' AND name=?",
		name,
	).Scan(&count)
	return count > 0, err
}

// Initialize applies schema and migrations on a fresh or existing database.
func Initialize(db *sql.DB) error {
	version, err := getCurrentVersion(db)
	if err != nil {
		return fmt.Errorf("getting schema version: %w", err)
	}

	if version == nil {
		// No schema_version table
		hasTasks, err := tableExists(db, "tasks")
		if err != nil {
			return fmt.Errorf("checking tables: %w", err)
		}
		if !hasTasks {
			// Fresh install: run full schema DDL, stamp latest version
			if _, err := db.Exec(schemaSQL); err != nil {
				return fmt.Errorf("applying schema: %w", err)
			}
			if err := stampVersion(db, latestVersion); err != nil {
				return fmt.Errorf("stamping version: %w", err)
			}
			return nil
		}
		// Pre-migration existing DB: create schema_version and migrate
		if _, err := db.Exec(`CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL, applied_at TEXT NOT NULL)`); err != nil {
			return fmt.Errorf("creating schema_version: %w", err)
		}
		if err := stampVersion(db, 0); err != nil {
			return fmt.Errorf("stamping initial version: %w", err)
		}
		return applyPendingMigrations(db, 0)
	}

	return applyPendingMigrations(db, *version)
}

// applyPendingMigrations applies all migrations newer than current version.
func applyPendingMigrations(db *sql.DB, currentVersion int) error {
	for _, m := range migrations {
		if m.version <= currentVersion {
			continue
		}
		tx, err := db.Begin()
		if err != nil {
			return fmt.Errorf("beginning migration tx v%d: %w", m.version, err)
		}
		if err := m.apply(tx); err != nil {
			_ = tx.Rollback()
			return fmt.Errorf("migration v%d %q: %w", m.version, m.description, err)
		}
		if err := stampVersionTx(tx, m.version); err != nil {
			_ = tx.Rollback()
			return fmt.Errorf("stamping migration v%d: %w", m.version, err)
		}
		if err := tx.Commit(); err != nil {
			return fmt.Errorf("committing migration v%d: %w", m.version, err)
		}
	}
	return nil
}
