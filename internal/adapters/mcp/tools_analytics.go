package mcp

import (
	"context"

	"github.com/mark3labs/mcp-go/mcp"
	mcpserver "github.com/mark3labs/mcp-go/server"

	"github.com/elpic/taskflow/internal/app"
)

func registerAnalyticsTools(srv *mcpserver.MCPServer, svc *app.Service, hint *app.HintOnce) {
	// task_types
	srv.AddTool(mcp.NewTool("task_types",
		mcp.WithDescription("List all available task types and their workflow steps."),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := svc.TaskTypes(hint)
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})

	// task_analytics
	srv.AddTool(mcp.NewTool("task_analytics",
		mcp.WithDescription("Get aggregate workflow analytics."),
		mcp.WithString("query",
			mcp.Required(),
			mcp.Description("Type of analytics — workflow_summary, step_bottlenecks, agent_performance, or velocity"),
		),
		mcp.WithNumber("days",
			mcp.Description("Number of days to analyze (default 30)"),
		),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		days := argInt(req, "days", 30)
		result, err := svc.Analytics(argString(req, "query"), days)
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})

	// task_cleanup
	srv.AddTool(mcp.NewTool("task_cleanup",
		mcp.WithDescription("Delete completed root task trees older than N days."),
		mcp.WithNumber("days",
			mcp.Description("Minimum age in days for deletion (default 7)"),
		),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		days := argInt(req, "days", 7)
		result, err := svc.Cleanup(days)
		if err != nil {
			return mcp.NewToolResultText("error:" + err.Error()), nil
		}
		return mcp.NewToolResultText(result), nil
	})
}

// RegisterTools registers all 21 MCP tools on the server.
func RegisterTools(srv *mcpserver.MCPServer, svc *app.Service, hint *app.HintOnce) {
	registerCreateTool(srv, svc, hint)
	registerLifecycleTools(srv, svc)
	registerQueryTools(srv, svc)
	registerAnalyticsTools(srv, svc, hint)
}
