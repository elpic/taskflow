"""Load custom workflow definitions from YAML files."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

import yaml

from .workflows import WorkflowStep

logger = logging.getLogger(__name__)


def load_custom_workflows(
    directory: Path,
) -> dict[str, list[WorkflowStep]]:
    """Load custom workflow definitions from YAML files in directory.

    Returns a dict mapping workflow type name to list of WorkflowStep.
    Invalid files are logged as warnings and skipped.
    """
    workflows: dict[str, list[WorkflowStep]] = {}

    if not directory.is_dir():
        return workflows

    for path in sorted(directory.glob("*.y*ml")):
        if path.suffix not in (".yaml", ".yml"):
            continue
        try:
            workflow_name, steps = _parse_workflow_file(path)
            _validate_steps(workflow_name, steps)
            workflows[workflow_name] = steps
        except (yaml.YAMLError, ValueError, KeyError, TypeError) as e:
            logger.warning("Skipping invalid workflow %s: %s", path.name, e)

    return workflows


def _parse_workflow_file(path: Path) -> tuple[str, list[WorkflowStep]]:
    """Parse a single YAML workflow file into a name and list of WorkflowStep."""
    with open(path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Root must be a YAML mapping")

    name = data.get("name")
    if not name or not isinstance(name, str):
        raise ValueError("'name' field is required and must be a string")

    raw_steps = data.get("steps")
    if not raw_steps or not isinstance(raw_steps, list):
        raise ValueError("'steps' field is required and must be a non-empty list")

    steps = []
    for i, step_data in enumerate(raw_steps):
        if not isinstance(step_data, dict):
            raise ValueError(f"Step {i} must be a mapping")

        step_data_str: dict[str, Any] = cast(dict[str, Any], step_data)
        step_name = step_data_str.get("name")
        if not step_name or not isinstance(step_name, str):
            raise ValueError(f"Step {i}: 'name' is required")

        description = step_data_str.get("description", "")
        if not isinstance(description, str):
            raise ValueError(f"Step '{step_name}': 'description' must be a string")

        steps.append(
            WorkflowStep(
                name=step_name,
                description=description,
                verification_criteria=step_data_str.get("verification_criteria"),
                agent=step_data_str.get("agent"),
            )
        )

    return name, steps


def _validate_steps(workflow_name: str, steps: list[WorkflowStep]) -> None:
    """Validate step list: unique names, non-empty."""
    if not steps:
        raise ValueError(f"Workflow '{workflow_name}' has no steps")

    seen_names: set[str] = set()
    for step in steps:
        if step.name in seen_names:
            raise ValueError(
                f"Workflow '{workflow_name}': duplicate step name '{step.name}'"
            )
        seen_names.add(step.name)
