package mcp

import (
	"context"

	"github.com/mark3labs/mcp-go/mcp"
	mcpserver "github.com/mark3labs/mcp-go/server"

	"github.com/elpic/taskflow/internal/app"
)

func registerQueryTools(srv *mcpserver.MCPServer, svc *app.Service) {
	// task_get
	srv.AddTool(mcp.NewTool("task_get",
		mcp.WithDescription("Get a task's details and its direct children."),
		mcp.WithString("task_id", mcp.Required(), mcp.Description("The task ID to retrieve")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := svc.Get(argString(req, "task_id"))
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})

	// task_list
	srv.AddTool(mcp.NewTool("task_list",
		mcp.WithDescription("List tasks as a rendered tree, optionally filtered."),
		mcp.WithString("status", mcp.Description("Filter by status (pending, in_progress, verifying, done, failed)")),
		mcp.WithString("parent_id", mcp.Description("Show only the subtree under this task")),
		mcp.WithBoolean("ready", mcp.Description("If True, return only PENDING tasks whose blockers are all DONE")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := svc.List(argStringPtr(req, "status"), argStringPtr(req, "parent_id"), argBool(req, "ready"))
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})

	// task_search
	srv.AddTool(mcp.NewTool("task_search",
		mcp.WithDescription("Search tasks by name or description."),
		mcp.WithString("query", mcp.Required(), mcp.Description("Text to search for (case-insensitive)")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := svc.Search(argString(req, "query"))
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})

	// task_stats
	srv.AddTool(mcp.NewTool("task_stats",
		mcp.WithDescription("Get timing statistics for a task and its subtree."),
		mcp.WithString("task_id", mcp.Required(), mcp.Description("The root task ID to analyze")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := svc.Stats(argString(req, "task_id"))
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})

	// task_history
	srv.AddTool(mcp.NewTool("task_history",
		mcp.WithDescription("Return the audit trail of state changes for a task."),
		mcp.WithString("task_id", mcp.Required(), mcp.Description("The task to retrieve history for")),
		mcp.WithBoolean("recursive", mcp.Description("If True, include events for all descendant tasks")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := svc.History(argString(req, "task_id"), argBool(req, "recursive"))
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})

	// task_current
	srv.AddTool(mcp.NewTool("task_current",
		mcp.WithDescription("Get the currently active task and its context."),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := svc.Current()
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})

	// task_resume
	srv.AddTool(mcp.NewTool("task_resume",
		mcp.WithDescription("Resume a previous session by summarising active work for a root task."),
		mcp.WithString("root_id", mcp.Description("ID of the root task to resume. If omitted, uses the most recent active root.")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := svc.Resume(argStringPtr(req, "root_id"))
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})

	// task_next
	srv.AddTool(mcp.NewTool("task_next",
		mcp.WithDescription("Find the next actionable step under a root task."),
		mcp.WithString("root_id", mcp.Required(), mcp.Description("The root task ID to search under")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := svc.Next(argString(req, "root_id"))
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})

	// task_context
	srv.AddTool(mcp.NewTool("task_context",
		mcp.WithDescription("Get completed sibling outputs as context for a task."),
		mcp.WithString("task_id", mcp.Required(), mcp.Description("The task that needs context from prior steps")),
		mcp.WithNumber("max_chars", mcp.Description("Maximum total characters in response (default 5000)")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		maxChars := argInt(req, "max_chars", 5000)
		result, err := svc.Context(argString(req, "task_id"), maxChars)
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})
}
