import pytest
from src.workflows import WORKFLOWS, WorkflowStep, get_workflow, list_types


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
