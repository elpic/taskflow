"""Tests for custom workflow loading from YAML files."""

import textwrap
from pathlib import Path

import pytest
from src.workflow_loader import (
    _parse_workflow_file,
    _validate_steps,
    load_custom_workflows,
)
from src.workflows import WorkflowStep


@pytest.fixture
def workflow_dir(tmp_path: Path) -> Path:
    return tmp_path


def write_yaml(directory: Path, filename: str, content: str) -> Path:
    path = directory / filename
    path.write_text(textwrap.dedent(content))
    return path


class TestLoadCustomWorkflows:
    def test_returns_empty_dict_when_directory_missing(self, tmp_path: Path):
        result = load_custom_workflows(tmp_path / "nonexistent")
        assert result == {}

    def test_returns_empty_dict_for_empty_directory(self, workflow_dir: Path):
        result = load_custom_workflows(workflow_dir)
        assert result == {}

    def test_loads_valid_yaml_workflow(self, workflow_dir: Path):
        write_yaml(
            workflow_dir,
            "deploy.yaml",
            """\
            name: deploy
            steps:
              - name: Build
                description: Compile the project
              - name: Push
                description: Push image to registry
            """,
        )
        result = load_custom_workflows(workflow_dir)
        assert "deploy" in result
        assert len(result["deploy"]) == 2
        assert result["deploy"][0].name == "Build"

    def test_loads_yml_extension(self, workflow_dir: Path):
        write_yaml(
            workflow_dir,
            "release.yml",
            """\
            name: release
            steps:
              - name: Tag
                description: Create git tag
            """,
        )
        result = load_custom_workflows(workflow_dir)
        assert "release" in result

    def test_skips_invalid_file_and_continues(self, workflow_dir: Path):
        write_yaml(workflow_dir, "bad.yaml", "not_a_mapping: [1, 2, 3]\n- item")
        write_yaml(
            workflow_dir,
            "good.yaml",
            """\
            name: good
            steps:
              - name: Step one
                description: Do something
            """,
        )
        result = load_custom_workflows(workflow_dir)
        assert "good" in result
        assert "bad" not in result

    def test_multiple_workflows_loaded(self, workflow_dir: Path):
        for name in ("alpha", "beta", "gamma"):
            write_yaml(
                workflow_dir,
                f"{name}.yaml",
                f"""\
                name: {name}
                steps:
                  - name: Only step
                    description: Does the thing
                """,
            )
        result = load_custom_workflows(workflow_dir)
        assert set(result.keys()) == {"alpha", "beta", "gamma"}

    def test_step_fields_mapped_correctly(self, workflow_dir: Path):
        write_yaml(
            workflow_dir,
            "full.yaml",
            """\
            name: full
            steps:
              - name: Deploy
                description: Deploy to production
                verification_criteria: Health check passes
                agent: devops-engineer
            """,
        )
        result = load_custom_workflows(workflow_dir)
        step = result["full"][0]
        assert step.name == "Deploy"
        assert step.description == "Deploy to production"
        assert step.verification_criteria == "Health check passes"
        assert step.agent == "devops-engineer"

    def test_optional_fields_default_to_none(self, workflow_dir: Path):
        write_yaml(
            workflow_dir,
            "minimal.yaml",
            """\
            name: minimal
            steps:
              - name: Only step
                description: Does the thing
            """,
        )
        result = load_custom_workflows(workflow_dir)
        step = result["minimal"][0]
        assert step.verification_criteria is None
        assert step.agent is None

    def test_description_defaults_to_empty_string_when_absent(self, workflow_dir: Path):
        write_yaml(
            workflow_dir,
            "nodesc.yaml",
            """\
            name: nodesc
            steps:
              - name: Step A
            """,
        )
        result = load_custom_workflows(workflow_dir)
        assert result["nodesc"][0].description == ""


class TestParseWorkflowFile:
    def test_raises_on_non_mapping_root(self, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text("- item1\n- item2\n")
        with pytest.raises(ValueError, match="Root must be a YAML mapping"):
            _parse_workflow_file(path)

    def test_raises_when_name_missing(self, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text("steps:\n  - name: Step\n    description: D\n")
        with pytest.raises(ValueError, match="'name' field is required"):
            _parse_workflow_file(path)

    def test_raises_when_steps_missing(self, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text("name: mywf\n")
        with pytest.raises(ValueError, match="'steps' field is required"):
            _parse_workflow_file(path)

    def test_raises_when_steps_empty_list(self, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text("name: mywf\nsteps: []\n")
        with pytest.raises(ValueError, match="'steps' field is required"):
            _parse_workflow_file(path)

    def test_raises_when_step_not_mapping(self, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text("name: mywf\nsteps:\n  - just a string\n")
        with pytest.raises(ValueError, match="Step 0 must be a mapping"):
            _parse_workflow_file(path)

    def test_raises_when_step_name_missing(self, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text("name: mywf\nsteps:\n  - description: No name here\n")
        with pytest.raises(ValueError, match="Step 0: 'name' is required"):
            _parse_workflow_file(path)

    def test_raises_when_description_not_string(self, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text("name: mywf\nsteps:\n  - name: Step\n    description: 42\n")
        with pytest.raises(ValueError, match="'description' must be a string"):
            _parse_workflow_file(path)

    def test_returns_name_and_steps(self, tmp_path: Path):
        path = tmp_path / "ok.yaml"
        path.write_text("name: mywf\nsteps:\n  - name: Step\n    description: Desc\n")
        name, steps = _parse_workflow_file(path)
        assert name == "mywf"
        assert len(steps) == 1
        assert isinstance(steps[0], WorkflowStep)


class TestValidateSteps:
    def test_raises_on_empty_steps(self):
        with pytest.raises(ValueError, match="has no steps"):
            _validate_steps("mywf", [])

    def test_raises_on_duplicate_step_names(self):
        steps = [
            WorkflowStep(name="Step", description="First"),
            WorkflowStep(name="Step", description="Duplicate"),
        ]
        with pytest.raises(ValueError, match="duplicate step name 'Step'"):
            _validate_steps("mywf", steps)

    def test_passes_for_unique_steps(self):
        steps = [
            WorkflowStep(name="Step A", description="First"),
            WorkflowStep(name="Step B", description="Second"),
        ]
        _validate_steps("mywf", steps)  # should not raise
