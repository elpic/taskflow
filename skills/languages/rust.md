---
name: taskflow-rust-standards
description: "Rust language standards and preferred tooling for all taskflow agents"
---

# Rust Standards

All agents MUST follow these conventions when working with Rust.

## Package Management
- **USE**: `cargo` (standard toolchain)
- `cargo add <crate>` to add dependencies
- `cargo remove <crate>` to remove
- Use workspace Cargo.toml for multi-crate projects

## Linting & Formatting
- `cargo fmt` to format (rustfmt)
- `cargo clippy` to lint — treat warnings as errors: `cargo clippy -- -D warnings`

## Testing
- `cargo test` for unit + integration tests
- Tests inline with `#[cfg(test)]` modules
- Integration tests in `tests/` directory

## Error Handling
- **USE**: `thiserror` for library error types
- **USE**: `anyhow` for application error handling
- Never `unwrap()` in library code — use `?` operator
- `unwrap()` acceptable in tests and examples only

## Async Runtime
- **USE**: `tokio` for async (unless project specifies otherwise)

## CLI
- **USE**: `clap` with derive macros for CLI parsing

## Key Patterns
- Prefer `&str` over `String` in function parameters
- Use `impl Trait` for return types when possible
- Prefer iterators over manual loops
- Use `derive` macros for common traits (Debug, Clone, PartialEq)
- Builder pattern for complex construction
