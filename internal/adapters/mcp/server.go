package mcp

import (
	"github.com/mark3labs/mcp-go/mcp"
	mcpserver "github.com/mark3labs/mcp-go/server"

	"github.com/elpic/taskflow/internal/app"
	"github.com/elpic/taskflow/pkg/version"
)

// BuildServer constructs and configures the MCP server with all tools registered.
func BuildServer(svc *app.Service, hint *app.HintOnce) *mcpserver.MCPServer {
	srv := mcpserver.NewMCPServer(
		"taskflow",
		version.Version,
		mcpserver.WithToolCapabilities(false),
	)

	RegisterTools(srv, svc, hint)
	return srv
}

// argString extracts a string argument from the tool request.
func argString(req mcp.CallToolRequest, key string) string {
	if v, ok := req.Params.Arguments[key]; ok {
		if s, ok := v.(string); ok {
			return s
		}
	}
	return ""
}

// argStringPtr extracts a pointer to string argument (nil if missing).
func argStringPtr(req mcp.CallToolRequest, key string) *string {
	if v, ok := req.Params.Arguments[key]; ok {
		if s, ok := v.(string); ok && s != "" {
			return &s
		}
	}
	return nil
}

// argBool extracts a boolean argument.
func argBool(req mcp.CallToolRequest, key string) bool {
	if v, ok := req.Params.Arguments[key]; ok {
		if b, ok := v.(bool); ok {
			return b
		}
	}
	return false
}

// argInt extracts an int argument.
func argInt(req mcp.CallToolRequest, key string, defaultVal int) int {
	if v, ok := req.Params.Arguments[key]; ok {
		switch n := v.(type) {
		case float64:
			return int(n)
		case int:
			return n
		}
	}
	return defaultVal
}

// argStringSlice extracts a []string argument.
func argStringSlice(req mcp.CallToolRequest, key string) []string {
	if v, ok := req.Params.Arguments[key]; ok {
		if arr, ok := v.([]any); ok {
			result := make([]string, 0, len(arr))
			for _, item := range arr {
				if s, ok := item.(string); ok {
					result = append(result, s)
				}
			}
			return result
		}
	}
	return nil
}

// text returns a successful tool result with the given text.
func text(s string) (*mcp.CallToolResult, error) {
	return mcp.NewToolResultText(s), nil
}
