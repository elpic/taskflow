import json
from datetime import datetime, timezone

from .models import Task, TaskStatus


class TransitionError(Exception):
    pass


VALID_TRANSITIONS = {
    TaskStatus.PENDING: {TaskStatus.IN_PROGRESS, TaskStatus.FAILED},
    TaskStatus.IN_PROGRESS: {TaskStatus.VERIFYING, TaskStatus.DONE, TaskStatus.FAILED},
    TaskStatus.VERIFYING: {TaskStatus.DONE, TaskStatus.IN_PROGRESS, TaskStatus.FAILED},
    TaskStatus.DONE: set(),
    TaskStatus.FAILED: {TaskStatus.IN_PROGRESS},
}


def validate_transition(current: TaskStatus, target: TaskStatus) -> None:
    if target not in VALID_TRANSITIONS.get(current, set()):
        raise TransitionError(
            f"Cannot transition from '{current.value}' to '{target.value}'. "
            f"Valid transitions: {', '.join(s.value for s in VALID_TRANSITIONS[current]) or 'none'}"
        )


def compute_start_fields() -> dict:
    return {
        "status": TaskStatus.IN_PROGRESS.value,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


def compute_complete_fields(task: Task, children: list[Task]) -> dict:
    incomplete = [c for c in children if c.status != TaskStatus.DONE]
    if incomplete:
        names = ", ".join(f"'{c.name}' ({c.status.value})" for c in incomplete)
        raise TransitionError(
            f"Cannot complete '{task.name}': {len(incomplete)} child task(s) not done: {names}"
        )

    if task.verification_criteria:
        return {"status": TaskStatus.VERIFYING.value}

    return {
        "status": TaskStatus.DONE.value,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def compute_verify_fields(passed: bool, details: str = "") -> dict:
    result = json.dumps({"passed": passed, "details": details})

    if passed:
        return {
            "status": TaskStatus.DONE.value,
            "verification_result": result,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

    return {
        "status": TaskStatus.IN_PROGRESS.value,
        "verification_result": result,
    }


def compute_fail_fields(reason: str) -> dict:
    result = json.dumps({"passed": False, "details": reason})
    return {
        "status": TaskStatus.FAILED.value,
        "verification_result": result,
    }
