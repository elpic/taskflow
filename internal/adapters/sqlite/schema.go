package sqlite

// schemaSQL is the byte-compatible DDL matching the Python SCHEMA constant in src/db.py.
const schemaSQL = `
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
CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_idempotency_key
    ON tasks(idempotency_key) WHERE idempotency_key IS NOT NULL;

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

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL
);
`
