from src.models import Task, TaskStatus


class TestTaskStatus:
    def test_enum_values(self):
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.IN_PROGRESS == "in_progress"
        assert TaskStatus.VERIFYING == "verifying"
        assert TaskStatus.DONE == "done"
        assert TaskStatus.FAILED == "failed"

    def test_all_statuses_present(self):
        statuses = {s.value for s in TaskStatus}
        assert statuses == {"pending", "in_progress", "verifying", "done", "failed"}

    def test_str_enum_is_string(self):
        assert isinstance(TaskStatus.PENDING, str)
        assert TaskStatus.IN_PROGRESS == "in_progress"

    def test_construct_from_string(self):
        assert TaskStatus("done") is TaskStatus.DONE
        assert TaskStatus("failed") is TaskStatus.FAILED


def _make_task(
    id: str = "abc12345",
    name: str = "Test task",
    description: str = "A description",
    status: TaskStatus = TaskStatus.PENDING,
    parent_id: str | None = None,
    verification_criteria: str | None = None,
    verification_result: str | None = None,
    metadata: str = "{}",
    created_at: str = "2024-01-01T00:00:00+00:00",
    started_at: str | None = None,
    completed_at: str | None = None,
    agent_output: str | None = None,
) -> Task:
    return Task(
        id=id,
        name=name,
        description=description,
        status=status,
        parent_id=parent_id,
        verification_criteria=verification_criteria,
        verification_result=verification_result,
        metadata=metadata,
        created_at=created_at,
        started_at=started_at,
        completed_at=completed_at,
        agent_output=agent_output,
    )


class TestTask:
    def test_task_creation_minimal(self):
        task = _make_task()
        assert task.id == "abc12345"
        assert task.name == "Test task"
        assert task.status == TaskStatus.PENDING
        assert task.parent_id is None
        assert task.children == []

    def test_task_children_default_is_empty_list(self):
        task = _make_task()
        assert task.children == []

    def test_task_with_parent(self):
        task = _make_task(parent_id="parent01")
        assert task.parent_id == "parent01"

    def test_task_with_verification_criteria(self):
        task = _make_task(verification_criteria="All tests pass")
        assert task.verification_criteria == "All tests pass"

    def test_task_status_assignment(self):
        task = _make_task(status=TaskStatus.IN_PROGRESS)
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.status == "in_progress"
