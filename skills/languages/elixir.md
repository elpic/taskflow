---
name: taskflow-elixir-standards
description: "Elixir language standards and preferred tooling for all taskflow agents"
---

# Elixir Standards

All agents MUST follow these conventions when working with Elixir.

## Package Management
- **USE**: `Mix` (NOT Rebar3 directly, NOT manual hex fetching)
- `mix new <project>` to create a new project
- `mix new <project> --sup` to create a project with a supervision tree
- Add dependencies in `mix.exs` under `deps/0`
- `mix deps.get` to fetch dependencies
- `mix deps.update <package>` to update a specific dependency
- `mix.exs` and `mix.lock` both committed to version control

## Type Checking
- **USE**: `Dialyxir` (wraps Dialyzer) (NOT just specs without dialyzer, NOT Gradient)
- `mix dialyzer` to run type analysis
- Add to `mix.exs`:
  ```elixir
  {:dialyxir, "~> 1.0", only: [:dev], runtime: false}
  ```
- Use `@spec` typespecs on all public functions
- Use `@type` and `@typedoc` for custom types

## Linting & Formatting
- **USE**: `mix format` + `Credo` (NOT custom formatters, NOT just one of the two)
- `mix format` to format all files
- `mix format --check-formatted` to verify formatting (used in CI)
- `mix credo` to lint (static analysis)
- `mix credo --strict` for stricter rules
- `.credo.exs` at the repo root for Credo configuration
- `.formatter.exs` at the repo root for formatter configuration

## Testing
- **USE**: `ExUnit` (built-in, NOT external test frameworks)
- `mix test` to run tests
- `mix test test/path/to/file_test.exs` to run a single file
- `mix test --cover` for coverage report
- Tests in `test/` directory mirroring `lib/` structure
- Test filenames end with `_test.exs`
- Use `ExUnit.Case` with `async: true` where side-effect-free

## Version
- Target Elixir 1.17+ / OTP 27 unless the project specifies otherwise
- Specify in `.tool-versions` (asdf):
  ```
  elixir 1.17.x-otp-27
  erlang 27.x
  ```
- Use modern syntax: `dbg/1`, verified routes (Phoenix), `Kernel.then/2`, `tap/2`

## Project Structure
- `lib/` for production code
- `test/` for test code with `test/test_helper.exs`
- `mix.exs`, `mix.lock`, `.credo.exs`, `.formatter.exs` at repo root
- `config/` for environment config (`config.exs`, `dev.exs`, `prod.exs`, `test.exs`)

## Key Patterns
- Behaviours as ports for dependency injection (hexagonal architecture): `@behaviour MyPort`
- Pattern matching in function heads for control flow (NOT nested `if/case` blocks)
- `{:ok, value} | {:error, reason}` tuples for operations that can fail
- Processes and GenServers for stateful components and concurrency
- Pipelines (`|>`) for data transformation chains
- Pure functions in context-free modules; side effects isolated to boundary modules
