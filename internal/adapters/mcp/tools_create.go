package mcp

import (
	"context"

	"github.com/mark3labs/mcp-go/mcp"
	mcpserver "github.com/mark3labs/mcp-go/server"

	"github.com/elpic/taskflow/internal/app"
)

// registerCreateTool registers the task_create tool.
func registerCreateTool(srv *mcpserver.MCPServer, svc *app.Service, hint *app.HintOnce) {
	tool := mcp.NewTool("task_create",
		mcp.WithDescription("Create a new task. If task_type is specified, auto-generates workflow subtasks."),
		mcp.WithString("name",
			mcp.Required(),
			mcp.Description("Task name"),
		),
		mcp.WithString("description",
			mcp.Description("What needs to be done"),
		),
		mcp.WithString("parent_id",
			mcp.Description("Parent task ID for nesting"),
		),
		mcp.WithString("verification_criteria",
			mcp.Description("What to check before marking done"),
		),
		mcp.WithString("task_type",
			mcp.Description("Workflow type (simple, implement, bugfix, refactor, research, secure-implement, product, sprint, discover, setup)"),
		),
		mcp.WithString("idempotency_key",
			mcp.Description("If provided and a task with this key exists, return the existing task"),
		),
		mcp.WithArray("blocked_by",
			mcp.Description("List of task IDs that must be DONE before this task can start"),
		),
	)

	srv.AddTool(tool, func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		input := app.CreateTaskInput{
			Name:                 argString(req, "name"),
			Description:          argString(req, "description"),
			ParentID:             argStringPtr(req, "parent_id"),
			VerificationCriteria: argStringPtr(req, "verification_criteria"),
			TaskType:             argStringPtr(req, "task_type"),
			IdempotencyKey:       argStringPtr(req, "idempotency_key"),
			BlockedBy:            argStringSlice(req, "blocked_by"),
		}
		result, err := svc.CreateTask(input, hint)
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})
}
