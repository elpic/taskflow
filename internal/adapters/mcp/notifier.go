package mcp

import "log/slog"

// sessionLogger implements domain.Logger using the standard slog package.
type sessionLogger struct{}

// NewSessionLogger returns a domain.Logger backed by slog.
func NewSessionLogger() *sessionLogger { return &sessionLogger{} }

func (sessionLogger) Info(msg string)  { slog.Info(msg) }
func (sessionLogger) Warn(msg string)  { slog.Warn(msg) }
func (sessionLogger) Error(msg string) { slog.Error(msg) }
