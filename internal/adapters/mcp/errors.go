package mcp

import (
	"strings"

	mcpgo "github.com/mark3labs/mcp-go/mcp"
)

// formatDomainError formats a domain error as an MCP tool result text.
// Business errors are returned as "error:<msg>" in the MCP text response —
// never as Go errors (which would be server errors, not tool errors).
func formatDomainError(err error) *mcpgo.CallToolResult {
	msg := err.Error()
	if !strings.HasPrefix(msg, "error:") {
		msg = "error:" + msg
	}
	return mcpgo.NewToolResultText(msg)
}
