from dataclasses import dataclass, field
from enum import StrEnum


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VERIFYING = "verifying"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Task:
    id: str
    name: str
    description: str
    status: TaskStatus
    parent_id: str | None
    verification_criteria: str | None
    verification_result: str | None
    metadata: str
    created_at: str
    started_at: str | None
    completed_at: str | None
    agent_output: str | None = None
    position: int | None = None
    idempotency_key: str | None = None
    children: list["Task"] = field(default_factory=list)
