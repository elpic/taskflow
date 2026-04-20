from pathlib import Path

import pytest
import src.workflows as wf_module
from src.workflows import (
    WORKFLOWS,
    WorkflowStep,
    get_workflow,
    list_types,
    set_custom_workflows_dir,
    validate_all_workflows,
    validate_workflow,
)


@pytest.fixture(autouse=True)
def reset_custom_workflows():
    """Ensure custom workflows state is clean before and after each test."""
    # Reset to a nonexistent directory so no custom workflows load during tests
    original_dir = wf_module._custom_dir
    original_cache = wf_module._custom_workflows
    set_custom_workflows_dir(Path("/nonexistent/__test__"))
    yield
    wf_module._custom_dir = original_dir
    wf_module._custom_workflows = original_cache


class TestGetWorkflow:
    def test_simple_workflow_returns_steps(self):
        steps = get_workflow("simple")
        assert len(steps) > 0
        assert all(isinstance(s, WorkflowStep) for s in steps)

    def test_implement_workflow_returns_steps(self):
        steps = get_workflow("implement")
        assert len(steps) > 0

    def test_unknown_type_falls_back_to_simple(self):
        steps = get_workflow("nonexistent_type")
        simple_steps = get_workflow("simple")
        assert steps == simple_steps

    def test_bugfix_workflow_has_reproduce_step(self):
        steps = get_workflow("bugfix")
        names = [s.name for s in steps]
        assert "Reproduce" in names

    def test_refactor_workflow_has_verify_unchanged_step(self):
        steps = get_workflow("refactor")
        names = [s.name for s in steps]
        assert any("unchanged" in n.lower() or "Verify" in n for n in names)

    def test_implement_workflow_has_qa_engineer_step(self):
        steps = get_workflow("implement")
        agents = [s.agent for s in steps if s.agent]
        assert "qa-engineer" in agents

    def test_implement_workflow_has_code_reviewer_step(self):
        steps = get_workflow("implement")
        agents = [s.agent for s in steps if s.agent]
        assert "code-reviewer" in agents


class TestListTypes:
    def test_list_types_returns_list(self):
        types = list_types()
        assert isinstance(types, list)
        assert len(types) > 0

    def test_list_types_contains_core_workflows(self):
        types = list_types()
        for expected in ("simple", "implement", "bugfix", "refactor", "research"):
            assert expected in types

    def test_list_types_matches_workflows_keys(self):
        assert set(list_types()) == set(WORKFLOWS.keys())


class TestWorkflowStepStructure:
    @pytest.mark.parametrize("workflow_type", list(WORKFLOWS.keys()))
    def test_every_step_has_name(self, workflow_type):
        for step in WORKFLOWS[workflow_type]:
            assert step.name, f"Step in {workflow_type} is missing a name"

    @pytest.mark.parametrize("workflow_type", list(WORKFLOWS.keys()))
    def test_every_step_has_description(self, workflow_type):
        for step in WORKFLOWS[workflow_type]:
            assert step.description, (
                f"Step '{step.name}' in {workflow_type} is missing a description"
            )

    def test_workflow_step_agent_is_string_or_none(self):
        for steps in WORKFLOWS.values():
            for step in steps:
                assert step.agent is None or isinstance(step.agent, str)

    def test_workflow_step_verification_criteria_is_string_or_none(self):
        for steps in WORKFLOWS.values():
            for step in steps:
                assert step.verification_criteria is None or isinstance(
                    step.verification_criteria, str
                )

    def test_workflow_step_has_depends_on_field(self):
        step = WorkflowStep(name="Step A", description="Do something")
        assert step.depends_on is None

    def test_workflow_step_explicit_depends_on(self):
        step = WorkflowStep(
            name="Step B", description="Depends on A", depends_on=["Step A"]
        )
        assert step.depends_on == ["Step A"]


class TestValidateWorkflows:
    def test_validate_all_workflows_pass(self):
        errors = validate_all_workflows()
        assert errors == {}, f"Unexpected workflow errors: {errors}"

    def test_validate_workflow_detects_unknown_reference(self):
        bad_steps = [
            WorkflowStep(name="Start", description="First step", depends_on=[]),
            WorkflowStep(
                name="Finish",
                description="Second step",
                depends_on=["Nonexistent Step"],
            ),
        ]
        WORKFLOWS["_test_unknown_ref"] = bad_steps
        try:
            errors = validate_workflow("_test_unknown_ref")
        finally:
            del WORKFLOWS["_test_unknown_ref"]
        assert len(errors) > 0
        assert any("Nonexistent Step" in e for e in errors)

    def test_validate_workflow_detects_self_dependency(self):
        bad_steps = [
            WorkflowStep(
                name="Self Loop",
                description="Depends on itself",
                depends_on=["Self Loop"],
            ),
        ]
        WORKFLOWS["_test_self_dep"] = bad_steps
        try:
            errors = validate_workflow("_test_self_dep")
        finally:
            del WORKFLOWS["_test_self_dep"]
        assert len(errors) > 0
        assert any("itself" in e or "Self Loop" in e for e in errors)

    def test_validate_workflow_detects_cycle(self):
        cyclic_steps = [
            WorkflowStep(name="Step A", description="A", depends_on=["Step B"]),
            WorkflowStep(name="Step B", description="B", depends_on=["Step A"]),
        ]
        WORKFLOWS["_test_cycle"] = cyclic_steps
        try:
            errors = validate_workflow("_test_cycle")
        finally:
            del WORKFLOWS["_test_cycle"]
        assert len(errors) > 0
        assert any("cycle" in e.lower() for e in errors)


class TestImplementWorkflowParallelStructure:
    def test_implement_workflow_has_parallel_steps(self):
        steps = {s.name: s for s in WORKFLOWS["implement"]}
        parallel_step_names = ["Create tests", "Documentation", "Containerization"]
        for name in parallel_step_names:
            assert name in steps, f"Step '{name}' not found in implement workflow"
            assert steps[name].depends_on == ["Implement"], (
                f"Step '{name}' should depend only on ['Implement'], "
                f"got {steps[name].depends_on}"
            )

    def test_implement_workflow_code_review_fans_in(self):
        steps = {s.name: s for s in WORKFLOWS["implement"]}
        assert "Code review" in steps
        code_review_deps = steps["Code review"].depends_on
        assert code_review_deps is not None
        assert "Create tests" in code_review_deps
        assert "Documentation" in code_review_deps
        assert "Containerization" in code_review_deps


class TestCustomWorkflows:
    def test_custom_workflow_loaded_from_directory(self, tmp_path: Path):
        yaml_content = (
            "name: custom-deploy\n"
            "steps:\n"
            "  - name: Build\n"
            "    description: Build the artifact\n"
            "  - name: Deploy\n"
            "    description: Deploy to environment\n"
        )
        (tmp_path / "deploy.yaml").write_text(yaml_content)
        set_custom_workflows_dir(tmp_path)

        steps = get_workflow("custom-deploy")
        assert len(steps) == 2
        assert steps[0].name == "Build"

    def test_custom_type_appears_in_list_types(self, tmp_path: Path):
        (tmp_path / "ml.yaml").write_text(
            "name: ml-train\nsteps:\n  - name: Train\n    description: Train model\n"
        )
        set_custom_workflows_dir(tmp_path)

        types = list_types()
        assert "ml-train" in types

    def test_builtin_types_still_present_with_custom_dir(self, tmp_path: Path):
        set_custom_workflows_dir(tmp_path)
        types = list_types()
        for expected in ("simple", "implement", "bugfix"):
            assert expected in types

    def test_custom_type_overrides_builtin_name(self, tmp_path: Path):
        """A custom workflow named 'simple' replaces the built-in simple workflow."""
        (tmp_path / "override.yaml").write_text(
            "name: simple\nsteps:\n  - name: Custom step\n    description: Override\n"
        )
        set_custom_workflows_dir(tmp_path)

        steps = get_workflow("simple")
        assert steps[0].name == "Custom step"

    def test_unknown_type_still_falls_back_to_simple(self, tmp_path: Path):
        set_custom_workflows_dir(tmp_path)
        steps = get_workflow("totally-unknown-type")
        simple_steps = WORKFLOWS["simple"]
        assert steps == simple_steps

    def test_set_custom_workflows_dir_invalidates_cache(self, tmp_path: Path):
        dir_a = tmp_path / "a"
        dir_a.mkdir()
        dir_b = tmp_path / "b"
        dir_b.mkdir()

        (dir_a / "wf.yaml").write_text(
            "name: wf-a\nsteps:\n  - name: Step A\n    description: From A\n"
        )
        (dir_b / "wf.yaml").write_text(
            "name: wf-b\nsteps:\n  - name: Step B\n    description: From B\n"
        )

        set_custom_workflows_dir(dir_a)
        assert "wf-a" in list_types()
        assert "wf-b" not in list_types()

        set_custom_workflows_dir(dir_b)
        assert "wf-b" in list_types()
        assert "wf-a" not in list_types()
