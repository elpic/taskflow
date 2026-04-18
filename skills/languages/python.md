---
name: taskflow-python-standards
description: "Python language standards and preferred tooling for all taskflow agents"
---

# Python Standards

All agents MUST follow these conventions when working with Python.

## Package Management
- **USE**: `uv` (NOT pip, NOT poetry, NOT pipenv)
- `uv init` to create projects
- `uv add <package>` to add dependencies (NOT `uv pip install`, NOT `pip install`)
- `uv remove <package>` to remove
- `uv sync` to install from lockfile
- `uv run <command>` to run in the virtual environment
- `pyproject.toml` for project config (NOT setup.py, NOT setup.cfg)

## Type Checking
- **USE**: `ty` (NOT mypy, NOT pyright)
- `uv run ty check` to type-check
- Use type hints on all function signatures

## Linting & Formatting
- **USE**: `ruff` (NOT flake8, NOT black, NOT isort)
- `uv run ruff check .` to lint
- `uv run ruff format .` to format
- Configure in `pyproject.toml` under `[tool.ruff]`

## Testing
- **USE**: `pytest` (NOT unittest)
- `uv run pytest` to run tests
- Tests in `tests/` directory
- Use `pytest-cov` for coverage when needed

## Python Version
- Target Python 3.12+ unless the project specifies otherwise
- Use modern syntax: `match/case`, `type X = ...`, `int | float` (not `Union`)

## Project Structure
- Use `pyproject.toml` as the single source of config
- Use `src/` layout for libraries, flat layout for simple tools
- `__init__.py` for packages
- `__main__.py` for `python -m` invocation

## Key Patterns
- Pure functions where possible
- Dataclasses for data structures (NOT dicts, NOT NamedTuples for complex types)
- `Enum` for fixed sets of values
- Context managers for resource management
- `pathlib.Path` instead of `os.path`
