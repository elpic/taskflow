"""Task type workflow definitions.

Each workflow is a list of steps. Each step has:
- name: step name
- description: what this step involves
- verification_criteria: optional criteria to verify before completing
- agent: optional specialist agent to delegate this step to
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class WorkflowStep:
    name: str
    description: str
    verification_criteria: str | None = None
    agent: str | None = None
    depends_on: list[str] | None = (
        None  # None = linear chain; [] = no deps; ["A","B"] = fan-in
    )


WORKFLOWS: dict[str, list[WorkflowStep]] = {
    "simple": [
        WorkflowStep(
            name="Plan",
            description="Analyze the task and plan the approach",
        ),
        WorkflowStep(
            name="Execute",
            description="Implement the planned approach",
            verification_criteria="Implementation matches the plan",
            agent="developer",
        ),
        WorkflowStep(
            name="Verify",
            description="Verify the implementation works correctly",
            verification_criteria="All acceptance criteria met",
            agent="qa-engineer",
        ),
    ],
    "implement": [
        WorkflowStep(
            name="Create branch",
            description="Create a feature branch from main. Ensure main is up to date first (git pull origin main). Branch naming: feat/<ticket-slug>",
            agent="git-workflow",
            depends_on=[],
        ),
        WorkflowStep(
            name="Design solution",
            description="Analyze requirements, explore the codebase, and design the architecture and approach",
            agent="tech-architect",
            depends_on=["Create branch"],
        ),
        WorkflowStep(
            name="Clarifying questions",
            description="Ask clarifying questions if requirements are ambiguous",
            depends_on=["Design solution"],
        ),
        WorkflowStep(
            name="Review acceptance criteria",
            description="Define and confirm acceptance criteria before implementation",
            agent="tech-architect",
            depends_on=["Clarifying questions"],
        ),
        WorkflowStep(
            name="Implement",
            description="Write the code to fulfill the requirements following the architect's design",
            verification_criteria="Code compiles/runs without errors",
            agent="developer",
            depends_on=["Review acceptance criteria"],
        ),
        WorkflowStep(
            name="Create tests",
            description="Write tests for each acceptance criteria",
            verification_criteria="All tests pass",
            agent="qa-engineer",
            depends_on=["Implement"],
        ),
        WorkflowStep(
            name="Documentation",
            description="Write README, API docs, usage examples, and inline docstrings. Include setup instructions, configuration, and architecture overview",
            verification_criteria="README exists with setup, usage, and API docs. All public functions have docstrings",
            agent="developer",
            depends_on=["Implement"],
        ),
        WorkflowStep(
            name="Containerization",
            description="Create Dockerfile, .dockerignore, and docker-compose.yml if applicable. Ensure the app builds and runs in a container",
            verification_criteria="docker build succeeds and docker run produces expected output",
            agent="devops-engineer",
            depends_on=["Implement"],
        ),
        WorkflowStep(
            name="Code review",
            description="Review the full implementation including code, tests, docs, and container config for quality, correctness, and security",
            verification_criteria="All acceptance criteria met, docs complete, container works, code quality is good",
            agent="code-reviewer",
            depends_on=["Create tests", "Documentation", "Containerization"],
        ),
        WorkflowStep(
            name="Commit and create PR",
            description="Stage all changes, commit with a descriptive conventional commit message, push the branch, and create a pull request with full description including summary, changes, and test results",
            verification_criteria="PR created with passing CI checks",
            agent="git-workflow",
            depends_on=["Code review"],
        ),
    ],
    "bugfix": [
        WorkflowStep(
            name="Create branch",
            description="Create a fix branch from main. Ensure main is up to date. Branch naming: fix/<bug-slug>",
            agent="git-workflow",
        ),
        WorkflowStep(
            name="Reproduce",
            description="Reproduce the bug consistently with clear steps",
            verification_criteria="Bug is reproducible with clear steps",
            agent="qa-engineer",
        ),
        WorkflowStep(
            name="Root cause analysis",
            description="Find the root cause of the bug by analyzing code and logs",
            agent="developer",
        ),
        WorkflowStep(
            name="Fix",
            description="Implement the fix for the root cause",
            verification_criteria="Fix addresses the root cause without side effects",
            agent="developer",
        ),
        WorkflowStep(
            name="Verify fix",
            description="Confirm the bug is fixed and write a regression test",
            verification_criteria="Bug no longer reproduces and regression test passes",
            agent="qa-engineer",
        ),
        WorkflowStep(
            name="Code review",
            description="Review the fix for quality and security implications",
            verification_criteria="Fix is clean and introduces no new vulnerabilities",
            agent="code-reviewer",
        ),
        WorkflowStep(
            name="Commit and create PR",
            description="Stage all changes, commit with a fix: conventional commit message, push the branch, and create a pull request",
            verification_criteria="PR created with passing CI checks",
            agent="git-workflow",
        ),
    ],
    "refactor": [
        WorkflowStep(
            name="Create branch",
            description="Create a refactor branch from main. Ensure main is up to date. Branch naming: refactor/<scope-slug>",
            agent="git-workflow",
        ),
        WorkflowStep(
            name="Analyze and plan",
            description="Understand the current code structure and design the refactoring approach",
            agent="tech-architect",
        ),
        WorkflowStep(
            name="Implement",
            description="Apply the refactoring changes following the plan",
            verification_criteria="Code compiles/runs without errors",
            agent="developer",
        ),
        WorkflowStep(
            name="Verify behavior unchanged",
            description="Confirm all existing behavior is preserved",
            verification_criteria="All tests pass and outputs match pre-refactor behavior",
            agent="qa-engineer",
        ),
        WorkflowStep(
            name="Code review",
            description="Review the refactored code for quality and correctness",
            verification_criteria="Refactoring improves code without changing behavior",
            agent="code-reviewer",
        ),
        WorkflowStep(
            name="Commit and create PR",
            description="Stage all changes, commit with a refactor: conventional commit message, push the branch, and create a pull request",
            verification_criteria="PR created with passing CI checks",
            agent="git-workflow",
        ),
    ],
    "research": [
        WorkflowStep(
            name="Define question",
            description="Clearly define the research question or problem",
        ),
        WorkflowStep(
            name="Explore options",
            description="Research and identify possible solutions or approaches",
            agent="tech-architect",
        ),
        WorkflowStep(
            name="Evaluate trade-offs",
            description="Compare options by pros, cons, complexity, and risk",
            agent="tech-architect",
        ),
        WorkflowStep(
            name="Document recommendation",
            description="Write up findings with a clear recommendation",
            verification_criteria="Recommendation is actionable with clear reasoning",
        ),
    ],
    "secure-implement": [
        WorkflowStep(
            name="Create branch",
            description="Create a feature branch from main. Ensure main is up to date. Branch naming: feat/<ticket-slug>",
            agent="git-workflow",
            depends_on=[],
        ),
        WorkflowStep(
            name="Design solution",
            description="Analyze requirements and design the architecture with security in mind",
            agent="tech-architect",
            depends_on=["Create branch"],
        ),
        WorkflowStep(
            name="Clarifying questions",
            description="Ask clarifying questions if requirements are ambiguous",
            depends_on=["Design solution"],
        ),
        WorkflowStep(
            name="Review acceptance criteria",
            description="Define and confirm acceptance criteria including security requirements",
            agent="tech-architect",
            depends_on=["Clarifying questions"],
        ),
        WorkflowStep(
            name="Implement",
            description="Write the code following the architect's design",
            verification_criteria="Code compiles/runs without errors",
            agent="developer",
            depends_on=["Review acceptance criteria"],
        ),
        WorkflowStep(
            name="Create tests",
            description="Write tests for each acceptance criteria",
            verification_criteria="All tests pass",
            agent="qa-engineer",
            depends_on=["Implement"],
        ),
        WorkflowStep(
            name="Security review",
            description="Review for vulnerabilities, injection risks, auth issues, and data exposure",
            verification_criteria="No security vulnerabilities found",
            agent="security-reviewer",
            depends_on=["Implement"],
        ),
        WorkflowStep(
            name="Code review",
            description="Final review for quality, correctness, and completeness",
            verification_criteria="All criteria met, code is production-ready",
            agent="code-reviewer",
            depends_on=["Create tests", "Security review"],
        ),
        WorkflowStep(
            name="Commit and create PR",
            description="Stage all changes, commit with a conventional commit message, push the branch, and create a pull request",
            verification_criteria="PR created with passing CI checks",
            agent="git-workflow",
            depends_on=["Code review"],
        ),
    ],
    "product": [
        WorkflowStep(
            name="Define product vision",
            description="Define the product vision, target users, core problem being solved, and high-level goals. Output: vision statement, target persona, core value proposition",
            agent="product-manager",
        ),
        WorkflowStep(
            name="Break into features",
            description="Decompose the product vision into discrete features and user stories. Each feature should be independently deliverable with clear user value. Output a structured list with name, description, and acceptance criteria for each",
            agent="product-manager",
        ),
        WorkflowStep(
            name="Prioritize backlog",
            description="Prioritize features using Impact/Effort matrix. Order the backlog so high-impact, low-effort items come first. Output a numbered priority list with [HIGH/MED/LOW] tags and rationale. IMPORTANT: after receiving the list, immediately task_create each feature as a child of the root task to persist the backlog in SQLite",
            agent="product-manager",
        ),
        WorkflowStep(
            name="Execute backlog",
            description="Work through the prioritized backlog. Each feature already exists as a taskflow task. For each in priority order: create child tasks under it with task_type=implement, then run the full pipeline (architect → developer → QA → docs → containerization → reviewer). Level-switch into each feature, complete it, switch back to backlog",
        ),
    ],
    "discover": [
        WorkflowStep(
            name="Scan project structure",
            description="Explore the project directory tree. Identify all source directories, config files, and key entry points. Map: root layout (src/, lib/, app/, flat), test directories, config file locations, documentation files, CI/CD configs, container files. Output a complete file tree with annotations",
            agent="Explore",
            depends_on=[],
        ),
        WorkflowStep(
            name="Detect languages and runtimes",
            description="Identify all programming languages used and their versions. Check: pyproject.toml (requires-python), package.json (engines.node), Cargo.toml (edition), go.mod (go version), tsconfig.json (target), .python-version, .nvmrc, .tool-versions, rust-toolchain.toml. Output: primary language, secondary languages, version constraints",
            agent="Explore",
            depends_on=["Scan project structure"],
        ),
        WorkflowStep(
            name="Detect package management",
            description="Identify the package manager and dependency strategy. Check: uv.lock/pyproject.toml (uv), poetry.lock (poetry), Pipfile (pipenv), requirements.txt (pip), package-lock.json (npm), pnpm-lock.yaml (pnpm), yarn.lock (yarn), Cargo.lock (cargo), go.sum (go mod). Identify: runtime deps, dev deps, dependency groups, lockfile strategy. Output: tool name, config file, install command, add command, run command",
            agent="Explore",
            depends_on=["Scan project structure"],
        ),
        WorkflowStep(
            name="Detect code quality tools",
            description="Identify linter, formatter, and type checker. Check config files: pyproject.toml [tool.ruff]/[tool.mypy]/[tool.black], .eslintrc/biome.json, rustfmt.toml/clippy.toml, .golangci-lint.yml. Check for: ruff vs flake8 vs pylint, black vs ruff format, mypy vs pyright vs ty, eslint vs biome, prettier vs biome. Identify exact commands used (check package.json scripts, Makefile, justfile, tox.ini). Output: tool name, config location, run command for each of lint/format/typecheck",
            agent="Explore",
            depends_on=["Scan project structure"],
        ),
        WorkflowStep(
            name="Detect testing setup",
            description="Identify test runner, test structure, and testing patterns. Check: pytest.ini/pyproject.toml [tool.pytest], jest.config/vitest.config, Cargo test config. Find test directories, test naming conventions (test_*.py vs *_test.py), fixtures, mocking patterns, coverage config. Check for: integration tests, e2e tests, test database setup. Output: test runner, test command, test directory, coverage command, testing patterns used",
            agent="Explore",
            depends_on=["Scan project structure"],
        ),
        WorkflowStep(
            name="Detect architecture and patterns",
            description="Analyze the codebase architecture and design patterns. Look for: hexagonal/clean/layered architecture, MVC/MVVM, microservices vs monolith, API style (REST/GraphQL/gRPC). Identify patterns: dependency injection, repository pattern, factory pattern, observer/pub-sub, CQRS, event sourcing. Check for: domain models, DTOs, service layers, middleware, error handling patterns, logging strategy. Analyze import structure to understand module boundaries. Output: architecture style, key patterns, module boundaries, error handling approach",
            agent="tech-architect",
            depends_on=["Detect languages and runtimes", "Detect package management"],
        ),
        WorkflowStep(
            name="Detect code conventions",
            description="Analyze naming conventions, code style, and project conventions. Check: variable naming (snake_case/camelCase/PascalCase), file naming, module organization, import ordering, docstring style (Google/NumPy/Sphinx), comment patterns, error message style, type annotation completeness, use of dataclasses vs dicts vs Pydantic. Check editorconfig, pre-commit hooks. Output: naming style, docstring format, line length, import style, type annotation coverage",
            agent="code-reviewer",
            depends_on=["Detect languages and runtimes"],
        ),
        WorkflowStep(
            name="Detect CI/CD and infrastructure",
            description="Identify CI/CD pipelines, deployment strategy, and infrastructure. Check: .github/workflows/, .gitlab-ci.yml, Jenkinsfile, .circleci/, bitbucket-pipelines.yml. Check for: Dockerfile, docker-compose.yml, .dockerignore, kubernetes manifests, terraform files, vercel.json, netlify.toml, fly.toml. Identify: build steps, test steps, deploy steps, environment management, secrets handling. Output: CI tool, pipeline stages, deployment target, container strategy",
            agent="devops-engineer",
            depends_on=["Detect code quality tools", "Detect testing setup"],
        ),
        WorkflowStep(
            name="Detect API and integrations",
            description="Identify APIs, external services, and integrations. Check for: API frameworks (FastAPI, Express, Gin, Actix), database connections (SQLAlchemy, Prisma, Diesel), message queues (Redis, RabbitMQ, Kafka), external APIs (REST clients, SDKs), auth providers (JWT, OAuth, session). Check environment variables for service URLs and API keys. Output: API framework, database, external services, auth strategy",
            agent="tech-architect",
            depends_on=["Detect architecture and patterns"],
        ),
        WorkflowStep(
            name="Review CI/CD pipeline",
            description="Review the detected CI/CD pipeline for completeness and best practices. Check: does it lint? does it test? does it type-check? does it build? does it deploy? Are there missing stages? Is caching configured for dependencies? Are secrets handled securely? Are branch protections in place? Compare against best practices for the detected CI tool. Output: list of improvements with priority (critical/recommended/nice-to-have)",
            agent="devops-reviewer",
            depends_on=["Detect CI/CD and infrastructure"],
        ),
        WorkflowStep(
            name="Improve CI/CD pipeline",
            description="Implement the critical and recommended improvements from the CI/CD review. Create or update workflow files (.github/workflows/, etc). Add missing stages (lint, type-check, test, build, deploy). Configure dependency caching. Add branch protection rules. Set up PR checks. If no CI/CD exists, create a complete pipeline from scratch based on detected tools",
            verification_criteria="CI pipeline has lint, type-check, test, and build stages. Pipeline runs successfully",
            agent="devops-engineer",
            depends_on=["Review CI/CD pipeline"],
        ),
        WorkflowStep(
            name="Generate project profile",
            description="Compile all findings into .taskflow/project.json. This file is the single source of truth for the project's tooling and conventions. It is read before every task to configure agents correctly. Write the JSON file with all detected information structured by category. Include the CI/CD improvements made",
            agent="developer",
            depends_on=[
                "Detect architecture and patterns",
                "Detect code conventions",
                "Improve CI/CD pipeline",
                "Detect API and integrations",
            ],
        ),
        WorkflowStep(
            name="Review project profile",
            description="Review the generated .taskflow/project.json for accuracy and completeness. Cross-check detected tools against actual config files. Verify commands work by running them. Flag any conflicts or ambiguities",
            verification_criteria="All detected tools verified, commands tested, no conflicts in profile",
            agent="code-reviewer",
            depends_on=["Generate project profile"],
        ),
    ],
    "setup": [
        WorkflowStep(
            name="Define project scope",
            description="Define the project: name, purpose, primary language, target platform. Determine if it's a library, CLI tool, web app, API, or service. Output: project name, type, language, target platform, key requirements",
            agent="tech-architect",
            depends_on=[],
        ),
        WorkflowStep(
            name="Initialize project",
            description="Create the project directory and initialize with the appropriate package manager (uv init, pnpm init, cargo init, go mod init). Create pyproject.toml/package.json/Cargo.toml with correct metadata. Set up .gitignore",
            agent="developer",
            depends_on=["Define project scope"],
        ),
        WorkflowStep(
            name="Set up code quality",
            description="Configure linter, formatter, and type checker. Add as dev dependencies. Create config in the project file (pyproject.toml [tool.ruff], biome.json, etc). Set up pre-commit hooks if applicable. Verify all tools run cleanly on the empty project",
            verification_criteria="Linter, formatter, and type checker all run without errors",
            agent="developer",
            depends_on=["Initialize project"],
        ),
        WorkflowStep(
            name="Set up testing",
            description="Configure the test runner. Add as dev dependency. Create tests/ directory with a sample test. Configure coverage. Verify test runner works",
            verification_criteria="Test runner executes and sample test passes",
            agent="qa-engineer",
            depends_on=["Initialize project"],
        ),
        WorkflowStep(
            name="Configure local permissions",
            description="Create .claude/settings.local.json with allowed tool permissions for the project's CLI commands (lint, format, type-check, test, build). Read the project profile or package config to determine which commands to allow. This enables autonomous operation without manual permission prompts",
            verification_criteria=".claude/settings.local.json exists with appropriate Bash tool permissions",
            agent="developer",
            depends_on=["Set up code quality", "Set up testing"],
        ),
        WorkflowStep(
            name="Create CI/CD pipeline",
            description="Create GitHub Actions workflow (or appropriate CI for the project). Include stages: lint, type-check, test, build. Configure dependency caching for the package manager. Set up PR checks. Add branch protection recommendations. Create .github/workflows/ci.yml",
            verification_criteria="CI workflow file is valid YAML and covers lint, type-check, test, build stages",
            agent="devops-engineer",
            depends_on=["Set up code quality", "Set up testing"],
        ),
        WorkflowStep(
            name="Set up containerization",
            description="Create Dockerfile with multi-stage build appropriate for the project type. Create .dockerignore. Create docker-compose.yml if the project has external dependencies (database, redis, etc). Verify docker build succeeds",
            verification_criteria="docker build succeeds",
            agent="devops-engineer",
            depends_on=["Initialize project"],
        ),
        WorkflowStep(
            name="Create documentation",
            description="Create README.md with: project description, prerequisites, setup instructions, development workflow (lint, test, format commands), architecture overview, contributing guidelines. Create CONTRIBUTING.md if applicable",
            verification_criteria="README has setup, development, and architecture sections",
            agent="developer",
            depends_on=["Create CI/CD pipeline", "Set up containerization"],
        ),
        WorkflowStep(
            name="Generate project profile",
            description="Generate .taskflow/project.json capturing all the project setup decisions: tools, commands, conventions, CI/CD config. This becomes the source of truth for all future taskflow operations on this project",
            agent="developer",
            depends_on=["Create documentation"],
        ),
        WorkflowStep(
            name="Review setup",
            description="Review the entire project setup: directory structure, configs, CI/CD, Docker, docs. Verify everything works end-to-end: install deps, run lint, run tests, build container. Flag any issues",
            verification_criteria="Full dev workflow works: install → lint → test → build → docker build",
            agent="devops-reviewer",
            depends_on=["Generate project profile"],
        ),
    ],
    "sprint": [
        WorkflowStep(
            name="Review backlog",
            description="Review the existing backlog of tasks. Query taskflow for pending tasks. Present the current state of the backlog to the product owner",
            agent="product-manager",
        ),
        WorkflowStep(
            name="Prioritize and select",
            description="Product owner prioritizes pending backlog items by impact/effort. Select which items to include in this sprint. Output an ordered list of items to execute",
            agent="product-manager",
        ),
        WorkflowStep(
            name="Execute sprint",
            description="Work through the selected items in priority order. For each item, create child tasks with task_type=implement and run the full pipeline. Track velocity and report at the end",
        ),
        WorkflowStep(
            name="Sprint retrospective",
            description="Review what was completed, what was blocked, what was learned. Store learnings in mempalace. Update backlog with any new items discovered during the sprint",
            agent="product-manager",
        ),
    ],
}


def validate_workflow(task_type: str) -> list[str]:
    """Validate a workflow's depends_on references. Returns list of errors."""
    steps = WORKFLOWS.get(task_type)
    if not steps:
        return [f"Unknown task_type: {task_type}"]

    errors = []
    step_names = {s.name for s in steps}

    for step in steps:
        if step.depends_on is not None:
            for dep in step.depends_on:
                if dep not in step_names:
                    errors.append(f"Step '{step.name}' depends_on unknown step '{dep}'")
                if dep == step.name:
                    errors.append(f"Step '{step.name}' depends on itself")

    # Cycle detection via topological sort (Kahn's algorithm)
    if not errors:
        in_degree: dict[str, int] = {s.name: 0 for s in steps}
        adj: dict[str, list[str]] = {s.name: [] for s in steps}
        for i, step in enumerate(steps):
            deps = (
                step.depends_on
                if step.depends_on is not None
                else ([steps[i - 1].name] if i > 0 else [])
            )
            for dep in deps:
                adj[dep].append(step.name)
                in_degree[step.name] += 1

        queue = [n for n, d in in_degree.items() if d == 0]
        visited = 0
        while queue:
            node = queue.pop(0)
            visited += 1
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited != len(steps):
            errors.append(f"Workflow '{task_type}' contains a cycle")

    return errors


def validate_all_workflows() -> dict[str, list[str]]:
    """Validate all built-in workflows. Returns {task_type: [errors]} for any with issues."""
    results = {}
    for task_type in WORKFLOWS:
        errors = validate_workflow(task_type)
        if errors:
            results[task_type] = errors
    return results


_errors = validate_all_workflows()
assert not _errors, f"Built-in workflow integrity failure: {_errors}"

_custom_workflows: dict[str, list[WorkflowStep]] | None = None
_custom_dir: Path | None = None


def set_custom_workflows_dir(directory: Path) -> None:
    """Set the directory to load custom workflows from. Call before get_workflow."""
    global _custom_dir, _custom_workflows
    _custom_dir = directory
    _custom_workflows = None  # Force reload on next access


def _get_custom_workflows() -> dict[str, list[WorkflowStep]]:
    """Load and cache custom workflows from the configured directory."""
    global _custom_workflows
    if _custom_workflows is not None:
        return _custom_workflows
    if _custom_dir is None:
        _custom_workflows = {}
        return _custom_workflows
    from .workflow_loader import load_custom_workflows

    _custom_workflows = load_custom_workflows(_custom_dir)
    return _custom_workflows


def get_workflow(task_type: str) -> list[WorkflowStep]:
    custom = _get_custom_workflows()
    if task_type in custom:
        return custom[task_type]
    return WORKFLOWS.get(task_type, WORKFLOWS["simple"])


def list_types() -> list[str]:
    custom = _get_custom_workflows()
    all_types = list(WORKFLOWS.keys())
    for name in custom:
        if name not in WORKFLOWS:
            all_types.append(name)
    return all_types
