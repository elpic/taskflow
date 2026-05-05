package app

import (
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/require"

	"github.com/elpic/taskflow/internal/adapters/sqlite"
	"github.com/elpic/taskflow/internal/adapters/workflows"
)

// nopHooks implements domain.HookRunner with no-op behavior.
type nopHooks struct{}

func (nopHooks) Fire(event, taskID, taskName, status string) error { return nil }

// nopLogger implements domain.Logger with no-op behavior.
type nopLogger struct{}

func (nopLogger) Info(msg string)  {}
func (nopLogger) Warn(msg string)  {}
func (nopLogger) Error(msg string) {}

// newTestService builds a full Service backed by a real SQLite DB in a temp dir.
func newTestService(t *testing.T) *Service {
	t.Helper()
	dbPath := filepath.Join(t.TempDir(), "test.db")
	db, err := sqlite.Open(dbPath)
	require.NoError(t, err)
	t.Cleanup(func() { db.Close() })
	require.NoError(t, sqlite.Initialize(db))
	repo := sqlite.NewRepository(db)
	wfSource, err := workflows.NewSource("") // empty custom dir = builtin only
	require.NoError(t, err)
	return NewService(repo, wfSource, nopHooks{}, nopLogger{})
}

// newHint returns a fresh HintOnce for test use.
func newHint() *HintOnce {
	return &HintOnce{}
}

// consumedHint returns a HintOnce that has already been consumed (will never show hint).
func consumedHint() *HintOnce {
	h := &HintOnce{}
	// Consume it with dbWasEmpty=false so it never fires
	h.Consume(false)
	return h
}

// stripHint removes the first-run hint suffix from a result string (everything from \n\n--- onward).
func stripHint(s string) string {
	if idx := indexString(s, "\n\n---"); idx >= 0 {
		return s[:idx]
	}
	return s
}

func indexString(s, substr string) int {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return i
		}
	}
	return -1
}
