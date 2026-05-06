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
	"github.com/elpic/taskflow/pkg/version"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintf(os.Stderr, "taskflow-mcp: %v\n", err)
		os.Exit(1)
	}
}

func run() error {
	if len(os.Args) > 1 && os.Args[1] == "--version" {
		fmt.Println(version.Version)
		return nil
	}

	// Database path: ./data/taskflow.db (relative to the project root where Claude Code launches this binary)
	dbPath := filepath.Join("data", "taskflow.db")

	if len(os.Args) > 1 && os.Args[1] == "--ui-state" {
		db, err := sqlite.Open(dbPath)
		if err != nil {
			return fmt.Errorf("opening database: %w", err)
		}
		defer db.Close()
		if err := sqlite.Initialize(db); err != nil {
			return fmt.Errorf("initializing database: %w", err)
		}
		repo := sqlite.NewRepository(db)
		customWorkflowDir := filepath.Join(".taskflow", "workflows")
		wfSource, err := workflows.NewSource(customWorkflowDir)
		if err != nil {
			return fmt.Errorf("loading workflows: %w", err)
		}
		hookRunner := hooks.NewRunner(nil, repo)
		logger := mcpadapter.NewSessionLogger()
		svc := app.NewService(repo, wfSource, hookRunner, logger)
		result, err := svc.UIState()
		if err != nil {
			return fmt.Errorf("ui-state: %w", err)
		}
		fmt.Println(result)
		return nil
	}

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
