package mcp

import (
	"context"

	"github.com/mark3labs/mcp-go/mcp"
	mcpserver "github.com/mark3labs/mcp-go/server"

	"github.com/elpic/taskflow/internal/app"
)

func registerLifecycleTools(srv *mcpserver.MCPServer, svc *app.Service) {
	// task_start
	srv.AddTool(mcp.NewTool("task_start",
		mcp.WithDescription("Start a task. Sets it as current."),
		mcp.WithString("task_id", mcp.Required(), mcp.Description("The task ID to start")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := svc.Start(argString(req, "task_id"))
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})

	// task_complete
	srv.AddTool(mcp.NewTool("task_complete",
		mcp.WithDescription("Complete a task. Auto-creates verification subtask if criteria exist."),
		mcp.WithString("task_id", mcp.Required(), mcp.Description("The task ID to complete")),
		mcp.WithString("output", mcp.Description("Optional agent output to store")),
		mcp.WithString("summary", mcp.Description("Optional concise summary of the output")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := svc.Complete(
			argString(req, "task_id"),
			argString(req, "output"),
			argString(req, "summary"),
		)
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})

	// task_fail
	srv.AddTool(mcp.NewTool("task_fail",
		mcp.WithDescription("Mark a task as failed."),
		mcp.WithString("task_id", mcp.Required(), mcp.Description("The task ID to fail")),
		mcp.WithString("reason", mcp.Required(), mcp.Description("Reason for failure")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := svc.Fail(argString(req, "task_id"), argString(req, "reason"))
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})

	// task_reset
	srv.AddTool(mcp.NewTool("task_reset",
		mcp.WithDescription("Reset a task back to pending so it can be retried."),
		mcp.WithString("task_id", mcp.Required(), mcp.Description("The task ID to reset")),
		mcp.WithBoolean("recursive", mcp.Description("If True, also reset all descendant tasks")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := svc.Reset(argString(req, "task_id"), argBool(req, "recursive"))
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})

	// task_delete
	srv.AddTool(mcp.NewTool("task_delete",
		mcp.WithDescription("Delete a task and all its descendants."),
		mcp.WithString("task_id", mcp.Required(), mcp.Description("The task ID to delete")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := svc.Delete(argString(req, "task_id"))
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})

	// task_move
	srv.AddTool(mcp.NewTool("task_move",
		mcp.WithDescription("Move a task to a new parent (or make it a root task)."),
		mcp.WithString("task_id", mcp.Required(), mcp.Description("The task ID to move")),
		mcp.WithString("new_parent_id", mcp.Description("New parent ID, or omit to make it a root task")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := svc.Move(argString(req, "task_id"), argStringPtr(req, "new_parent_id"))
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})

	// task_update
	srv.AddTool(mcp.NewTool("task_update",
		mcp.WithDescription("Update a task's fields (not status — use task_start/complete/fail for that)."),
		mcp.WithString("task_id", mcp.Required(), mcp.Description("The task ID to update")),
		mcp.WithString("name", mcp.Description("New task name")),
		mcp.WithString("description", mcp.Description("New description")),
		mcp.WithString("verification_criteria", mcp.Description("New verification criteria")),
		mcp.WithString("metadata", mcp.Description("New metadata JSON string")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		fields := map[string]any{}
		if v := argString(req, "name"); v != "" {
			fields["name"] = v
		}
		if v := argString(req, "description"); v != "" {
			fields["description"] = v
		}
		if v := argString(req, "verification_criteria"); v != "" {
			fields["verification_criteria"] = v
		}
		if v := argString(req, "metadata"); v != "" {
			fields["metadata"] = v
		}
		result, err := svc.Update(argString(req, "task_id"), fields)
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})

	// task_reorder
	srv.AddTool(mcp.NewTool("task_reorder",
		mcp.WithDescription("Set the display/priority position of a task among its siblings."),
		mcp.WithString("task_id", mcp.Required(), mcp.Description("The task ID to reorder")),
		mcp.WithNumber("position", mcp.Required(), mcp.Description("Integer position (lower = higher priority, 0-based)")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := svc.Reorder(argString(req, "task_id"), argInt(req, "position", 0))
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})
}
