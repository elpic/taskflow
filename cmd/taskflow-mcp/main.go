package main

import (
	"fmt"
	"log/slog"
	"os"
	"path/filepath"

	mcpserver "github.com/mark3labs/mcp-go/server"

	"github.com/elpic/taskflow/internal/adapters/hooks"
	mcpadapter "github.com/elpic/taskflow/internal/adapters/mcp"
	"github.com/elpic/taskflow/internal/adapters/sqlite"
	"github.com/elpic/taskflow/internal/adapters/workflows"
	"github.com/elpic/taskflow/internal/app"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintf(os.Stderr, "taskflow-mcp: %v\n", err)
		os.Exit(1)
	}
}

func run() error {
	// Database path: ./data/taskflow.db (relative to CWD, matching Python behavior)
	dbPath := filepath.Join("data", "taskflow.db")

	// Open SQLite connection
	db, err := sqlite.Open(dbPath)
	if err != nil {
		return fmt.Errorf("opening database: %w", err)
	}
	defer db.Close()

	// Initialize schema / run migrations
	if err := sqlite.Initialize(db); err != nil {
		return fmt.Errorf("initializing database: %w", err)
	}

	// Build repository
	repo := sqlite.NewRepository(db)

	// Load workflows (builtin + custom from .taskflow/workflows/)
	customWorkflowDir := filepath.Join(".taskflow", "workflows")
	wfSource, err := workflows.NewSource(customWorkflowDir)
	if err != nil {
		return fmt.Errorf("loading workflows: %w", err)
	}

	// Load hooks configuration
	hooksPath := filepath.Join(".taskflow", "hooks.json")
	hookConfig, err := hooks.LoadConfig(hooksPath)
	if err != nil {
		slog.Warn("failed to load hooks config", "err", err)
		// Continue without hooks — non-fatal
	}
	hookRunner := hooks.NewRunner(hookConfig, repo)

	// Build application service
	logger := mcpadapter.NewSessionLogger()
	svc := app.NewService(repo, wfSource, hookRunner, logger)
	hint := &app.HintOnce{}

	// Build MCP server
	srv := mcpadapter.BuildServer(svc, hint)

	// Start stdio transport
	return mcpserver.ServeStdio(srv)
}
