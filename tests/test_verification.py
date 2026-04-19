import json

import pytest
from src.models import Task, TaskStatus
from src.verification import (
    TransitionError,
    compute_complete_fields,
    compute_fail_fields,
    compute_start_fields,
    compute_verify_fields,
    validate_transition,
)


def make_task(
    status: TaskStatus = TaskStatus.PENDING,
    verification_criteria: str | None = None,
    name: str = "Task",
) -> Task:
    return Task(
        id="t1",
        name=name,
        description="",
        status=status,
        parent_id=None,
        verification_criteria=verification_criteria,
        verification_result=None,
        metadata="{}",
        created_at="2024-01-01T00:00:00+00:00",
        started_at=None,
        completed_at=None,
    )


class TestValidateTransition:
    def test_pending_to_in_progress_is_valid(self):
        validate_transition(TaskStatus.PENDING, TaskStatus.IN_PROGRESS)

    def test_in_progress_to_done_is_valid(self):
        validate_transition(TaskStatus.IN_PROGRESS, TaskStatus.DONE)

    def test_in_progress_to_verifying_is_valid(self):
        validate_transition(TaskStatus.IN_PROGRESS, TaskStatus.VERIFYING)

    def test_verifying_to_done_is_valid(self):
        validate_transition(TaskStatus.VERIFYING, TaskStatus.DONE)

    def test_verifying_to_in_progress_is_valid(self):
        validate_transition(TaskStatus.VERIFYING, TaskStatus.IN_PROGRESS)

    def test_failed_to_in_progress_is_valid(self):
        validate_transition(TaskStatus.FAILED, TaskStatus.IN_PROGRESS)

    def test_done_to_anything_raises(self):
        for target in TaskStatus:
            with pytest.raises(TransitionError):
                validate_transition(TaskStatus.DONE, target)

    def test_pending_to_done_raises(self):
        with pytest.raises(TransitionError, match="Cannot transition"):
            validate_transition(TaskStatus.PENDING, TaskStatus.DONE)

    def test_in_progress_to_pending_raises(self):
        with pytest.raises(TransitionError):
            validate_transition(TaskStatus.IN_PROGRESS, TaskStatus.PENDING)

    def test_error_message_mentions_valid_transitions(self):
        with pytest.raises(TransitionError, match="in_progress"):
            validate_transition(TaskStatus.PENDING, TaskStatus.DONE)


class TestComputeStartFields:
    def test_returns_in_progress_status(self):
        fields = compute_start_fields()
        assert fields["status"] == TaskStatus.IN_PROGRESS.value

    def test_returns_started_at(self):
        fields = compute_start_fields()
        assert "started_at" in fields
        assert fields["started_at"] is not None

    def test_started_at_is_iso_format(self):
        from datetime import datetime

        fields = compute_start_fields()
        # Should not raise
        datetime.fromisoformat(fields["started_at"])


class TestComputeCompleteFields:
    def test_no_criteria_no_children_returns_done(self):
        task = make_task(status=TaskStatus.IN_PROGRESS)
        fields = compute_complete_fields(task, [])
        assert fields["status"] == TaskStatus.DONE.value
        assert "completed_at" in fields

    def test_with_criteria_returns_verifying(self):
        task = make_task(
            status=TaskStatus.IN_PROGRESS,
            verification_criteria="All tests pass",
        )
        fields = compute_complete_fields(task, [])
        assert fields["status"] == TaskStatus.VERIFYING.value
        assert "completed_at" not in fields

    def test_incomplete_children_raises(self):
        task = make_task(status=TaskStatus.IN_PROGRESS)
        child = make_task(status=TaskStatus.PENDING, name="child")
        with pytest.raises(TransitionError, match="child task"):
            compute_complete_fields(task, [child])

    def test_all_done_children_allows_complete(self):
        task = make_task(status=TaskStatus.IN_PROGRESS)
        child = make_task(status=TaskStatus.DONE, name="child")
        fields = compute_complete_fields(task, [child])
        assert fields["status"] == TaskStatus.DONE.value

    def test_mixed_children_raises_with_incomplete_count(self):
        task = make_task(status=TaskStatus.IN_PROGRESS)
        done_child = make_task(status=TaskStatus.DONE, name="done_child")
        pending_child = make_task(status=TaskStatus.PENDING, name="pending_child")
        with pytest.raises(TransitionError, match="1 child"):
            compute_complete_fields(task, [done_child, pending_child])


class TestComputeVerifyFields:
    def test_passed_true_returns_done(self):
        fields = compute_verify_fields(passed=True, details="looks good")
        assert fields["status"] == TaskStatus.DONE.value
        assert "completed_at" in fields

    def test_passed_true_stores_result(self):
        fields = compute_verify_fields(passed=True, details="ok")
        result = json.loads(fields["verification_result"])
        assert result["passed"] is True
        assert result["details"] == "ok"

    def test_passed_false_returns_in_progress(self):
        fields = compute_verify_fields(passed=False, details="not ready")
        assert fields["status"] == TaskStatus.IN_PROGRESS.value
        assert "completed_at" not in fields

    def test_passed_false_stores_result(self):
        fields = compute_verify_fields(passed=False, details="needs work")
        result = json.loads(fields["verification_result"])
        assert result["passed"] is False
        assert result["details"] == "needs work"


class TestComputeFailFields:
    def test_returns_failed_status(self):
        fields = compute_fail_fields("timed out")
        assert fields["status"] == TaskStatus.FAILED.value

    def test_stores_reason_in_result(self):
        fields = compute_fail_fields("some error")
        result = json.loads(fields["verification_result"])
        assert result["passed"] is False
        assert result["details"] == "some error"

    def test_result_is_valid_json(self):
        fields = compute_fail_fields("crash")
        # Should not raise
        json.loads(fields["verification_result"])
