import src.server
from src.server import task_create, task_types


class TestMaybeHintDirectly:
    """Unit tests for _maybe_hint() behaviour via the module-level flag."""

    async def test_hint_shown_flag_starts_false(self, monkeypatch):
        monkeypatch.setattr(src.server, "_hint_shown", False)
        assert src.server._hint_shown is False

    async def test_maybe_hint_returns_hint_on_first_call_empty_db(self, monkeypatch):
        monkeypatch.setattr(src.server, "_hint_shown", False)
        hint = await src.server._maybe_hint()
        assert hint == src.server._FIRST_RUN_HINT

    async def test_maybe_hint_sets_flag_after_first_call(self, monkeypatch):
        monkeypatch.setattr(src.server, "_hint_shown", False)
        await src.server._maybe_hint()
        assert src.server._hint_shown is True

    async def test_maybe_hint_returns_empty_on_second_call(self, monkeypatch):
        monkeypatch.setattr(src.server, "_hint_shown", False)
        await src.server._maybe_hint()
        hint = await src.server._maybe_hint()
        assert hint == ""

    async def test_maybe_hint_returns_empty_when_flag_already_true(self, monkeypatch):
        monkeypatch.setattr(src.server, "_hint_shown", True)
        hint = await src.server._maybe_hint()
        assert hint == ""

    async def test_maybe_hint_returns_empty_when_tasks_exist(self, monkeypatch):
        monkeypatch.setattr(src.server, "_hint_shown", False)
        # Pre-create a task so DB is non-empty before calling _maybe_hint
        await task_create("Existing Task")
        # Reset flag so _maybe_hint proceeds to the DB check
        monkeypatch.setattr(src.server, "_hint_shown", False)
        hint = await src.server._maybe_hint()
        assert hint == ""


class TestTaskTypesHint:
    """task_types() must surface the hint exactly once for new users."""

    async def test_task_types_shows_hint_on_empty_db(self, monkeypatch):
        monkeypatch.setattr(src.server, "_hint_shown", False)
        result = await task_types()
        assert src.server._FIRST_RUN_HINT in result

    async def test_task_types_hint_not_repeated_on_second_call(self, monkeypatch):
        monkeypatch.setattr(src.server, "_hint_shown", False)
        await task_types()
        result = await task_types()
        assert src.server._FIRST_RUN_HINT not in result

    async def test_task_types_no_hint_when_flag_already_set(self, monkeypatch):
        monkeypatch.setattr(src.server, "_hint_shown", True)
        result = await task_types()
        assert src.server._FIRST_RUN_HINT not in result

    async def test_task_types_no_hint_for_returning_user(self, monkeypatch):
        monkeypatch.setattr(src.server, "_hint_shown", False)
        await task_create("Pre-existing Task")
        monkeypatch.setattr(src.server, "_hint_shown", False)
        result = await task_types()
        assert src.server._FIRST_RUN_HINT not in result

    async def test_task_types_still_returns_workflow_list(self, monkeypatch):
        monkeypatch.setattr(src.server, "_hint_shown", False)
        result = await task_types()
        # Hint is appended after the workflow list; the list itself must still be there
        assert "bugfix" in result
        assert "implement" in result


class TestTaskCreateHint:
    """task_create() must surface the hint exactly once for new users."""

    async def test_task_create_shows_hint_on_first_call_empty_db(self, monkeypatch):
        monkeypatch.setattr(src.server, "_hint_shown", False)
        result = await task_create("First Task")
        assert src.server._FIRST_RUN_HINT in result

    async def test_task_create_hint_not_repeated_on_second_call(self, monkeypatch):
        monkeypatch.setattr(src.server, "_hint_shown", False)
        await task_create("First Task")
        result = await task_create("Second Task")
        assert src.server._FIRST_RUN_HINT not in result

    async def test_task_create_no_hint_when_flag_already_set(self, monkeypatch):
        monkeypatch.setattr(src.server, "_hint_shown", True)
        result = await task_create("Any Task")
        assert src.server._FIRST_RUN_HINT not in result

    async def test_task_create_no_hint_for_returning_user(self, monkeypatch):
        # Simulate a returning user: a task already exists before the first call
        await task_create("Old Task")
        monkeypatch.setattr(src.server, "_hint_shown", False)
        result = await task_create("New Task")
        assert src.server._FIRST_RUN_HINT not in result

    async def test_task_create_still_returns_task_id(self, monkeypatch):
        monkeypatch.setattr(src.server, "_hint_shown", False)
        result = await task_create("My Task")
        # result = "<task_id><hint>"; strip hint and verify an ID remains
        task_id = result.replace(src.server._FIRST_RUN_HINT, "").strip()
        assert len(task_id) > 0
        assert "error" not in task_id

    async def test_task_create_with_task_type_shows_hint(self, monkeypatch):
        monkeypatch.setattr(src.server, "_hint_shown", False)
        result = await task_create("Fix bug", task_type="bugfix")
        assert src.server._FIRST_RUN_HINT in result

    async def test_task_create_with_task_type_hint_not_repeated(self, monkeypatch):
        monkeypatch.setattr(src.server, "_hint_shown", False)
        await task_create("Fix bug", task_type="bugfix")
        result = await task_create("Another bug", task_type="bugfix")
        assert src.server._FIRST_RUN_HINT not in result


class TestHintContent:
    """The hint text itself must contain the key guidance snippets."""

    def test_hint_contains_task_type_example(self):
        assert 'task_type="bugfix"' in src.server._FIRST_RUN_HINT

    def test_hint_lists_available_types(self):
        for workflow_type in ("simple", "implement", "bugfix", "refactor"):
            assert workflow_type in src.server._FIRST_RUN_HINT

    def test_hint_references_task_types_tool(self):
        assert "task_types()" in src.server._FIRST_RUN_HINT


class TestHintSessionIsolation:
    """Verify that monkeypatching the flag truly isolates tests from each other."""

    async def test_flag_is_reset_between_tests_a(self, monkeypatch):
        monkeypatch.setattr(src.server, "_hint_shown", False)
        result = await task_types()
        assert src.server._FIRST_RUN_HINT in result

    async def test_flag_is_reset_between_tests_b(self, monkeypatch):
        # If isolation works, this test also sees an empty-DB + False flag
        monkeypatch.setattr(src.server, "_hint_shown", False)
        result = await task_types()
        assert src.server._FIRST_RUN_HINT in result
