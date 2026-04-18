from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TaskStatus(str, Enum):
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
    parent_id: Optional[str]
    verification_criteria: Optional[str]
    verification_result: Optional[str]
    metadata: str
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    children: list["Task"] = field(default_factory=list)
