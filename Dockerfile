# Stage 1: builder — install dependencies into an isolated venv
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build

# Copy only the dependency manifests first so Docker can cache this layer
COPY pyproject.toml uv.lock ./

# Install production dependencies only into the project venv
RUN uv sync --frozen --no-dev --no-install-project

# -------------------------------------------------------------------
# Stage 2: runtime — lean image with only what is needed to run
FROM python:3.12-slim AS runtime

# Create a non-root user for running the MCP server
RUN useradd --system --create-home --uid 1001 taskflow

WORKDIR /app

# Pull the populated venv from the builder stage
COPY --from=builder /build/.venv /app/.venv

# Copy application source
COPY run.py ./
COPY src/ ./src/

# Ensure the data directory exists and is owned by the runtime user.
# The SQLite database lives at data/taskflow.db (relative to /app).
# Mount a volume here in CI or local use to persist state across runs.
RUN mkdir -p /app/data && chown taskflow:taskflow /app/data

# Make the venv's Python the active interpreter without needing to
# activate the virtualenv explicitly.
ENV PATH="/app/.venv/bin:$PATH"

USER taskflow

# MCP stdio server — reads from stdin, writes to stdout.
# No ports are exposed; the container is invoked directly by the host.
ENTRYPOINT ["python", "run.py"]
