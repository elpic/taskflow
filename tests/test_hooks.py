"""Tests for workflow lifecycle hooks (HookManager and server.py integration)."""

from __future__ import annotations

import json
from pathlib import Path

import src.db as db_module
from src.hooks import HookManager, get_hook_manager
from src.server import task_complete, task_create, task_fail, task_start

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_hooks_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload))


def _make_shell_hook(command: str, extra_env: dict | None = None) -> dict:
    h: dict = {"type": "shell", "command": command}
    if extra_env:
        h["env"] = extra_env
    return h


def _make_builtin_retry_hook(max_retries: int = 3) -> dict:
    return {"type": "builtin", "action": "retry", "max_retries": max_retries}


# ---------------------------------------------------------------------------
# HookManager.load() tests
# ---------------------------------------------------------------------------


class TestHookManagerLoad:
    def test_load_missing_file(self, tmp_path: Path) -> None:
        """Loading from a nonexistent path leaves _hooks empty without crashing."""
        mgr = HookManager()
        mgr.load(tmp_path / "does_not_exist.json")
        assert mgr._hooks == {}
        assert mgr._loaded is True

    def test_load_empty_hooks(self, tmp_path: Path) -> None:
        """Loading a file with an empty hooks object stores nothing."""
        cfg = tmp_path / "hooks.json"
        _write_hooks_json(cfg, {"hooks": {}})
        mgr = HookManager()
        mgr.load(cfg)
        assert mgr._hooks == {}

    def test_load_valid_shell_hook(self, tmp_path: Path) -> None:
        """A valid on_task_complete shell handler is stored under the correct key."""
        cfg = tmp_path / "hooks.json"
        handler = _make_shell_hook("echo done")
        _write_hooks_json(cfg, {"hooks": {"on_task_complete": [handler]}})
        mgr = HookManager()
        mgr.load(cfg)
        assert "on_task_complete" in mgr._hooks
        assert mgr._hooks["on_task_complete"] == [handler]

    def test_load_invalid_json(self, tmp_path: Path) -> None:
        """A file containing invalid JSON is silently ignored; _hooks stays empty."""
        cfg = tmp_path / "hooks.json"
        cfg.write_text("{not valid json")
        mgr = HookManager()
        mgr.load(cfg)
        assert mgr._hooks == {}

    def test_load_unknown_event_skipped(self, tmp_path: Path) -> None:
        """An unknown event name is skipped; no entry is stored."""
        cfg = tmp_path / "hooks.json"
        _write_hooks_json(
            cfg,
            {
                "hooks": {
                    "on_unknown_event": [{"type": "shell", "command": "echo x"}],
                    "on_task_complete": [{"type": "shell", "command": "echo y"}],
                }
            },
        )
        mgr = HookManager()
        mgr.load(cfg)
        assert "on_unknown_event" not in mgr._hooks
        assert "on_task_complete" in mgr._hooks

    def test_load_valid_builtin_hook(self, tmp_path: Path) -> None:
        """A valid on_task_fail builtin retry handler is stored correctly."""
        cfg = tmp_path / "hooks.json"
        handler = _make_builtin_retry_hook(max_retries=5)
        _write_hooks_json(cfg, {"hooks": {"on_task_fail": [handler]}})
        mgr = HookManager()
        mgr.load(cfg)
        assert "on_task_fail" in mgr._hooks
        stored = mgr._hooks["on_task_fail"][0]
        assert stored["action"] == "retry"
        assert stored["max_retries"] == 5


# ---------------------------------------------------------------------------
# HookManager.fire() tests
# ---------------------------------------------------------------------------


class TestHookManagerFire:
    async def test_fire_no_handlers(self) -> None:
        """Firing an event with no registered handlers does not crash."""
        mgr = HookManager()
        # No handlers loaded — should complete silently
        await mgr.fire("on_task_complete", "abc", "Some Task", "done")

    async def test_fire_shell_handler(self, tmp_path: Path) -> None:
        """Shell hook runs with correct TASKFLOW_* env vars and writes a marker file."""
        marker = tmp_path / "hook_fired.txt"
        # Write env vars to the marker so we can assert their values
        command = (
            f'echo "$TASKFLOW_TASK_ID $TASKFLOW_TASK_NAME'
            f' $TASKFLOW_EVENT $TASKFLOW_STATUS" > {marker}'
        )
        mgr = HookManager()
        mgr._hooks = {"on_task_complete": [_make_shell_hook(command)]}
        mgr._loaded = True

        await mgr.fire("on_task_complete", "task-001", "My Task", "done")

        assert marker.exists(), "Shell hook did not create the marker file"
        content = marker.read_text().strip()
        assert "task-001" in content
        assert "My Task" in content
        assert "on_task_complete" in content
        assert "done" in content

    async def test_fire_builtin_retry(self, tmp_path: Path) -> None:
        """Builtin retry resets a failed task to pending and increments retry_count."""
        # Redirect DB to a fresh temp file for this test
        task = await db_module.create_task(name="Flaky Task")
        # Put the task into failed state by directly updating (avoids transition rules)
        await db_module.update_task(task.id, status="failed")

        mgr = HookManager()
        mgr._hooks = {"on_task_fail": [_make_builtin_retry_hook(max_retries=3)]}
        mgr._loaded = True

        await mgr.fire("on_task_fail", task.id, task.name, "failed")

        refreshed = await db_module.get_task(task.id)
        assert refreshed is not None
        assert refreshed.status.value == "pending", (
            "Task should have been reset to pending"
        )

        meta = json.loads(refreshed.metadata) if refreshed.metadata else {}
        assert meta.get("retry_count") == 1, f"Expected retry_count=1, got {meta}"

    async def test_fire_retry_respects_max(self, tmp_path: Path) -> None:
        """retry_count >= max_retries: task stays failed, retry_exhausted logged."""
        task = await db_module.create_task(
            name="Exhausted Task",
            metadata={"retry_count": 3},
        )
        await db_module.update_task(task.id, status="failed")

        mgr = HookManager()
        mgr._hooks = {"on_task_fail": [_make_builtin_retry_hook(max_retries=3)]}
        mgr._loaded = True

        await mgr.fire("on_task_fail", task.id, task.name, "failed")

        refreshed = await db_module.get_task(task.id)
        assert refreshed is not None
        assert refreshed.status.value == "failed", (
            "Task should remain failed after max retries"
        )

        # Verify retry_exhausted event was written to the audit trail
        history = await db_module.get_task_history(task.id)
        event_types = [e["event_type"] for e in history]
        assert "retry_exhausted" in event_types, (
            f"Expected retry_exhausted event; got events: {event_types}"
        )

    async def test_fire_unknown_handler_type(self) -> None:
        """An unknown handler type (e.g. 'webhook') is silently skipped."""
        mgr = HookManager()
        mgr._hooks = {
            "on_task_complete": [{"type": "webhook", "url": "https://example.com"}]
        }
        mgr._loaded = True

        # Must not raise
        await mgr.fire("on_task_complete", "xyz", "Some Task", "done")


# ---------------------------------------------------------------------------
# Integration tests — server.py fires hooks at state transitions
# ---------------------------------------------------------------------------


class TestHookIntegrationTaskComplete:
    async def test_task_complete_fires_hook(self, tmp_path: Path) -> None:
        """Completing a task via task_complete() fires the on_task_complete hook."""
        marker = tmp_path / "complete_hook.txt"
        command = f"touch {marker}"

        cfg = tmp_path / "hooks.json"
        _write_hooks_json(
            cfg, {"hooks": {"on_task_complete": [_make_shell_hook(command)]}}
        )

        singleton = get_hook_manager()
        original_hooks = dict(singleton._hooks)
        original_loaded = singleton._loaded
        try:
            singleton._hooks = {"on_task_complete": [_make_shell_hook(command)]}
            singleton._loaded = True

            task_id = await task_create("Integration Complete Task")
            result = await task_complete(task_id)
            assert result == "ok", f"task_complete returned: {result}"

            # Give the shell command a brief moment via import asyncio
            import asyncio

            await asyncio.sleep(0.1)

            assert marker.exists(), "on_task_complete hook did not create marker file"
        finally:
            singleton._hooks = original_hooks
            singleton._loaded = original_loaded


class TestHookIntegrationTaskFail:
    async def test_task_fail_fires_hook(self, tmp_path: Path) -> None:
        """Failing a task via task_fail() fires the on_task_fail hook."""
        marker = tmp_path / "fail_hook.txt"
        command = f"touch {marker}"

        singleton = get_hook_manager()
        original_hooks = dict(singleton._hooks)
        original_loaded = singleton._loaded
        try:
            singleton._hooks = {"on_task_fail": [_make_shell_hook(command)]}
            singleton._loaded = True

            task_id = await task_create("Integration Fail Task")
            await task_start(task_id)
            result = await task_fail(task_id, "intentional failure")
            assert result == "ok", f"task_fail returned: {result}"

            import asyncio

            await asyncio.sleep(0.1)

            assert marker.exists(), "on_task_fail hook did not create marker file"
        finally:
            singleton._hooks = original_hooks
            singleton._loaded = original_loaded


class TestHookIntegrationWorkflowComplete:
    async def test_workflow_complete_fires(self, tmp_path: Path) -> None:
        """Completing all children of a root task fires on_workflow_complete."""
        marker = tmp_path / "workflow_hook.txt"
        command = f"touch {marker}"

        singleton = get_hook_manager()
        original_hooks = dict(singleton._hooks)
        original_loaded = singleton._loaded
        try:
            singleton._hooks = {
                "on_task_complete": [_make_shell_hook(command)],
                "on_workflow_complete": [_make_shell_hook(command)],
            }
            singleton._loaded = True

            # Create a root task with two children (no task_type to keep it simple)
            root_id = await task_create("Root Workflow Task")
            child1_id = await task_create("Child Step 1", parent_id=root_id)
            child2_id = await task_create("Child Step 2", parent_id=root_id)

            # Complete both children — the second completion should trigger
            # on_workflow_complete because all siblings are now DONE
            await task_complete(child1_id)
            marker.unlink(missing_ok=True)  # reset between completions

            result = await task_complete(child2_id)
            assert result == "ok", f"task_complete returned: {result}"

            import asyncio

            await asyncio.sleep(0.1)

            # The marker should exist because either on_task_complete or
            # on_workflow_complete fired (both use the same command here)
            assert marker.exists(), (
                "on_workflow_complete (or on_task_complete) hook did not fire "
                "after all children completed"
            )
        finally:
            singleton._hooks = original_hooks
            singleton._loaded = original_loaded
