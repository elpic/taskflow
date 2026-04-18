"""Task type workflow definitions.

Each workflow is a list of steps. Each step has:
- name: step name
- description: what this step involves
- verification_criteria: optional criteria to verify before completing
- agent: optional specialist agent to delegate this step to
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class WorkflowStep:
    name: str
    description: str
    verification_criteria: Optional[str] = None
    agent: Optional[str] = None


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
            name="Design solution",
            description="Analyze requirements, explore the codebase, and design the architecture and approach",
            agent="tech-architect",
        ),
        WorkflowStep(
            name="Clarifying questions",
            description="Ask clarifying questions if requirements are ambiguous",
        ),
        WorkflowStep(
            name="Review acceptance criteria",
            description="Define and confirm acceptance criteria before implementation",
            agent="tech-architect",
        ),
        WorkflowStep(
            name="Implement",
            description="Write the code to fulfill the requirements following the architect's design",
            verification_criteria="Code compiles/runs without errors",
            agent="developer",
        ),
        WorkflowStep(
            name="Create tests",
            description="Write tests for each acceptance criteria",
            verification_criteria="All tests pass",
            agent="qa-engineer",
        ),
        WorkflowStep(
            name="Documentation",
            description="Write README, API docs, usage examples, and inline docstrings. Include setup instructions, configuration, and architecture overview",
            verification_criteria="README exists with setup, usage, and API docs. All public functions have docstrings",
            agent="developer",
        ),
        WorkflowStep(
            name="Containerization",
            description="Create Dockerfile, .dockerignore, and docker-compose.yml if applicable. Ensure the app builds and runs in a container",
            verification_criteria="docker build succeeds and docker run produces expected output",
            agent="devops-engineer",
        ),
        WorkflowStep(
            name="Code review",
            description="Review the full implementation including code, tests, docs, and container config for quality, correctness, and security",
            verification_criteria="All acceptance criteria met, docs complete, container works, code quality is good",
            agent="code-reviewer",
        ),
    ],
    "bugfix": [
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
    ],
    "refactor": [
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
            name="Design solution",
            description="Analyze requirements and design the architecture with security in mind",
            agent="tech-architect",
        ),
        WorkflowStep(
            name="Clarifying questions",
            description="Ask clarifying questions if requirements are ambiguous",
        ),
        WorkflowStep(
            name="Review acceptance criteria",
            description="Define and confirm acceptance criteria including security requirements",
            agent="tech-architect",
        ),
        WorkflowStep(
            name="Implement",
            description="Write the code following the architect's design",
            verification_criteria="Code compiles/runs without errors",
            agent="developer",
        ),
        WorkflowStep(
            name="Create tests",
            description="Write tests for each acceptance criteria",
            verification_criteria="All tests pass",
            agent="qa-engineer",
        ),
        WorkflowStep(
            name="Security review",
            description="Review for vulnerabilities, injection risks, auth issues, and data exposure",
            verification_criteria="No security vulnerabilities found",
            agent="security-reviewer",
        ),
        WorkflowStep(
            name="Code review",
            description="Final review for quality, correctness, and completeness",
            verification_criteria="All criteria met, code is production-ready",
            agent="code-reviewer",
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
        ),
        WorkflowStep(
            name="Detect languages and runtimes",
            description="Identify all programming languages used and their versions. Check: pyproject.toml (requires-python), package.json (engines.node), Cargo.toml (edition), go.mod (go version), tsconfig.json (target), .python-version, .nvmrc, .tool-versions, rust-toolchain.toml. Output: primary language, secondary languages, version constraints",
            agent="Explore",
        ),
        WorkflowStep(
            name="Detect package management",
            description="Identify the package manager and dependency strategy. Check: uv.lock/pyproject.toml (uv), poetry.lock (poetry), Pipfile (pipenv), requirements.txt (pip), package-lock.json (npm), pnpm-lock.yaml (pnpm), yarn.lock (yarn), Cargo.lock (cargo), go.sum (go mod). Identify: runtime deps, dev deps, dependency groups, lockfile strategy. Output: tool name, config file, install command, add command, run command",
            agent="Explore",
        ),
        WorkflowStep(
            name="Detect code quality tools",
            description="Identify linter, formatter, and type checker. Check config files: pyproject.toml [tool.ruff]/[tool.mypy]/[tool.black], .eslintrc/biome.json, rustfmt.toml/clippy.toml, .golangci-lint.yml. Check for: ruff vs flake8 vs pylint, black vs ruff format, mypy vs pyright vs ty, eslint vs biome, prettier vs biome. Identify exact commands used (check package.json scripts, Makefile, justfile, tox.ini). Output: tool name, config location, run command for each of lint/format/typecheck",
            agent="Explore",
        ),
        WorkflowStep(
            name="Detect testing setup",
            description="Identify test runner, test structure, and testing patterns. Check: pytest.ini/pyproject.toml [tool.pytest], jest.config/vitest.config, Cargo test config. Find test directories, test naming conventions (test_*.py vs *_test.py), fixtures, mocking patterns, coverage config. Check for: integration tests, e2e tests, test database setup. Output: test runner, test command, test directory, coverage command, testing patterns used",
            agent="Explore",
        ),
        WorkflowStep(
            name="Detect architecture and patterns",
            description="Analyze the codebase architecture and design patterns. Look for: hexagonal/clean/layered architecture, MVC/MVVM, microservices vs monolith, API style (REST/GraphQL/gRPC). Identify patterns: dependency injection, repository pattern, factory pattern, observer/pub-sub, CQRS, event sourcing. Check for: domain models, DTOs, service layers, middleware, error handling patterns, logging strategy. Analyze import structure to understand module boundaries. Output: architecture style, key patterns, module boundaries, error handling approach",
            agent="tech-architect",
        ),
        WorkflowStep(
            name="Detect code conventions",
            description="Analyze naming conventions, code style, and project conventions. Check: variable naming (snake_case/camelCase/PascalCase), file naming, module organization, import ordering, docstring style (Google/NumPy/Sphinx), comment patterns, error message style, type annotation completeness, use of dataclasses vs dicts vs Pydantic. Check editorconfig, pre-commit hooks. Output: naming style, docstring format, line length, import style, type annotation coverage",
            agent="code-reviewer",
        ),
        WorkflowStep(
            name="Detect CI/CD and infrastructure",
            description="Identify CI/CD pipelines, deployment strategy, and infrastructure. Check: .github/workflows/, .gitlab-ci.yml, Jenkinsfile, .circleci/, bitbucket-pipelines.yml. Check for: Dockerfile, docker-compose.yml, .dockerignore, kubernetes manifests, terraform files, vercel.json, netlify.toml, fly.toml. Identify: build steps, test steps, deploy steps, environment management, secrets handling. Output: CI tool, pipeline stages, deployment target, container strategy",
            agent="devops-engineer",
        ),
        WorkflowStep(
            name="Detect API and integrations",
            description="Identify APIs, external services, and integrations. Check for: API frameworks (FastAPI, Express, Gin, Actix), database connections (SQLAlchemy, Prisma, Diesel), message queues (Redis, RabbitMQ, Kafka), external APIs (REST clients, SDKs), auth providers (JWT, OAuth, session). Check environment variables for service URLs and API keys. Output: API framework, database, external services, auth strategy",
            agent="tech-architect",
        ),
        WorkflowStep(
            name="Review CI/CD pipeline",
            description="Review the detected CI/CD pipeline for completeness and best practices. Check: does it lint? does it test? does it type-check? does it build? does it deploy? Are there missing stages? Is caching configured for dependencies? Are secrets handled securely? Are branch protections in place? Compare against best practices for the detected CI tool. Output: list of improvements with priority (critical/recommended/nice-to-have)",
            agent="devops-reviewer",
        ),
        WorkflowStep(
            name="Improve CI/CD pipeline",
            description="Implement the critical and recommended improvements from the CI/CD review. Create or update workflow files (.github/workflows/, etc). Add missing stages (lint, type-check, test, build, deploy). Configure dependency caching. Add branch protection rules. Set up PR checks. If no CI/CD exists, create a complete pipeline from scratch based on detected tools",
            verification_criteria="CI pipeline has lint, type-check, test, and build stages. Pipeline runs successfully",
            agent="devops-engineer",
        ),
        WorkflowStep(
            name="Generate project profile",
            description="Compile all findings into .taskflow/project.json. This file is the single source of truth for the project's tooling and conventions. It is read before every task to configure agents correctly. Write the JSON file with all detected information structured by category. Include the CI/CD improvements made",
            agent="developer",
        ),
        WorkflowStep(
            name="Review project profile",
            description="Review the generated .taskflow/project.json for accuracy and completeness. Cross-check detected tools against actual config files. Verify commands work by running them. Flag any conflicts or ambiguities",
            verification_criteria="All detected tools verified, commands tested, no conflicts in profile",
            agent="code-reviewer",
        ),
    ],
    "setup": [
        WorkflowStep(
            name="Define project scope",
            description="Define the project: name, purpose, primary language, target platform. Determine if it's a library, CLI tool, web app, API, or service. Output: project name, type, language, target platform, key requirements",
            agent="tech-architect",
        ),
        WorkflowStep(
            name="Initialize project",
            description="Create the project directory and initialize with the appropriate package manager (uv init, pnpm init, cargo init, go mod init). Create pyproject.toml/package.json/Cargo.toml with correct metadata. Set up .gitignore",
            agent="developer",
        ),
        WorkflowStep(
            name="Set up code quality",
            description="Configure linter, formatter, and type checker. Add as dev dependencies. Create config in the project file (pyproject.toml [tool.ruff], biome.json, etc). Set up pre-commit hooks if applicable. Verify all tools run cleanly on the empty project",
            verification_criteria="Linter, formatter, and type checker all run without errors",
            agent="developer",
        ),
        WorkflowStep(
            name="Set up testing",
            description="Configure the test runner. Add as dev dependency. Create tests/ directory with a sample test. Configure coverage. Verify test runner works",
            verification_criteria="Test runner executes and sample test passes",
            agent="qa-engineer",
        ),
        WorkflowStep(
            name="Create CI/CD pipeline",
            description="Create GitHub Actions workflow (or appropriate CI for the project). Include stages: lint, type-check, test, build. Configure dependency caching for the package manager. Set up PR checks. Add branch protection recommendations. Create .github/workflows/ci.yml",
            verification_criteria="CI workflow file is valid YAML and covers lint, type-check, test, build stages",
            agent="devops-engineer",
        ),
        WorkflowStep(
            name="Set up containerization",
            description="Create Dockerfile with multi-stage build appropriate for the project type. Create .dockerignore. Create docker-compose.yml if the project has external dependencies (database, redis, etc). Verify docker build succeeds",
            verification_criteria="docker build succeeds",
            agent="devops-engineer",
        ),
        WorkflowStep(
            name="Create documentation",
            description="Create README.md with: project description, prerequisites, setup instructions, development workflow (lint, test, format commands), architecture overview, contributing guidelines. Create CONTRIBUTING.md if applicable",
            verification_criteria="README has setup, development, and architecture sections",
            agent="developer",
        ),
        WorkflowStep(
            name="Generate project profile",
            description="Generate .taskflow/project.json capturing all the project setup decisions: tools, commands, conventions, CI/CD config. This becomes the source of truth for all future taskflow operations on this project",
            agent="developer",
        ),
        WorkflowStep(
            name="Review setup",
            description="Review the entire project setup: directory structure, configs, CI/CD, Docker, docs. Verify everything works end-to-end: install deps, run lint, run tests, build container. Flag any issues",
            verification_criteria="Full dev workflow works: install → lint → test → build → docker build",
            agent="devops-reviewer",
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


def get_workflow(task_type: str) -> list[WorkflowStep]:
    return WORKFLOWS.get(task_type, WORKFLOWS["simple"])


def list_types() -> list[str]:
    return list(WORKFLOWS.keys())
