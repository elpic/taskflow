---
name: taskflow-go-standards
description: "Go language standards and preferred tooling for all taskflow agents"
---

# Go Standards

All agents MUST follow these conventions when working with Go.

## Package Management
- Go modules (`go mod init`, `go mod tidy`)
- `go get <package>` to add dependencies

## Formatting & Linting
- `gofmt` / `goimports` for formatting (non-negotiable in Go)
- **USE**: `golangci-lint` for comprehensive linting
- `golangci-lint run` with default config

## Testing
- `go test ./...` to run all tests
- Table-driven tests (Go convention)
- `go test -race ./...` for race detection
- `go test -cover ./...` for coverage

## Error Handling
- Return `error` as last return value
- Wrap errors with `fmt.Errorf("context: %w", err)`
- Check errors immediately — never ignore with `_`
- Use `errors.Is` / `errors.As` for comparison

## Key Patterns
- Accept interfaces, return structs
- Small interfaces (1-2 methods)
- Package names: short, lowercase, no underscores
- Use `context.Context` as first parameter for cancellation
- Prefer composition over inheritance
- Use `sync.Once` for lazy initialization
