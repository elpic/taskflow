"""Workflow lifecycle hooks — event-driven automation."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from pathlib import Path

from . import db

logger = logging.getLogger(__name__)

# Valid event names
VALID_EVENTS = {"on_task_complete", "on_task_fail", "on_workflow_complete"}

# Timeout for shell hook execution
SHELL_TIMEOUT = 30


class HookManager:
    """Manages lifecycle hooks loaded from a JSON config file."""

    def __init__(self) -> None:
        self._hooks: dict[str, list[dict]] = {}
        self._loaded = False

    def load(self, path: Path) -> None:
        """Load hooks from a JSON file. Invalid files are logged and ignored."""
        self._hooks = {}
        self._loaded = True

        if not path.is_file():
            return

        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load hooks from %s: %s", path, e)
            return

        if not isinstance(data, dict):
            logger.warning("Hooks file %s: root must be a JSON object", path)
            return

        hooks_data = data.get("hooks", {})
        if not isinstance(hooks_data, dict):
            logger.warning("Hooks file %s: 'hooks' must be a JSON object", path)
            return

        for event_name, handlers in hooks_data.items():
            if event_name not in VALID_EVENTS:
                logger.warning("Unknown hook event: %s", event_name)
                continue
            if not isinstance(handlers, list):
                logger.warning("Handlers for %s must be a list", event_name)
                continue
            self._hooks[event_name] = handlers

    async def fire(
        self,
        event: str,
        task_id: str,
        task_name: str,
        status: str,
    ) -> None:
        """Fire all handlers for an event. Errors are logged, never raised."""
        handlers = self._hooks.get(event, [])
        for handler in handlers:
            try:
                handler_type = handler.get("type", "")
                if handler_type == "shell":
                    await self._run_shell(handler, task_id, task_name, event, status)
                elif handler_type == "builtin":
                    await self._run_builtin(handler, task_id, task_name, event)
                else:
                    logger.warning("Unknown handler type: %s", handler_type)
            except Exception:
                logger.exception("Hook error for event %s on task %s", event, task_id)
                # Log to task events for audit trail
                with contextlib.suppress(Exception):
                    await db.log_event(
                        task_id,
                        "hook_error",
                        {
                            "event": event,
                            "handler_type": handler.get("type", "unknown"),
                        },
                    )

    async def _run_shell(
        self,
        handler: dict,
        task_id: str,
        task_name: str,
        event: str,
        status: str,
    ) -> None:
        """Run a shell command with TASKFLOW_* environment variables."""
        command = handler.get("command", "")
        if not command:
            return

        env = {
            **os.environ,
            "TASKFLOW_TASK_ID": task_id,
            "TASKFLOW_TASK_NAME": task_name,
            "TASKFLOW_EVENT": event,
            "TASKFLOW_STATUS": status,
        }
        # Merge any extra env vars from handler config
        extra_env = handler.get("env", {})
        if isinstance(extra_env, dict):
            env.update({k: str(v) for k, v in extra_env.items()})

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                env=env,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=SHELL_TIMEOUT)
        except TimeoutError:
            logger.warning("Shell hook timed out after %ds: %s", SHELL_TIMEOUT, command)
            proc.kill()
        except OSError as e:
            logger.warning("Shell hook failed: %s — %s", command, e)

    async def _run_builtin(
        self,
        handler: dict,
        task_id: str,
        task_name: str,
        event: str,
    ) -> None:
        """Run a built-in hook action."""
        action = handler.get("action", "")

        if action == "retry":
            await self._handle_retry(handler, task_id, task_name)
        else:
            logger.warning("Unknown builtin action: %s", action)

    async def _handle_retry(
        self,
        handler: dict,
        task_id: str,
        task_name: str,
    ) -> None:
        """Auto-retry a failed task by resetting it."""
        max_retries = handler.get("max_retries", 3)

        task = await db.get_task(task_id)
        if not task:
            return

        # Track retry count in metadata
        try:
            meta = json.loads(task.metadata) if task.metadata else {}
        except (json.JSONDecodeError, TypeError):
            meta = {}

        retry_count = meta.get("retry_count", 0)
        if retry_count >= max_retries:
            logger.info(
                "Task %s reached max retries (%d), not retrying",
                task_name,
                max_retries,
            )
            await db.log_event(
                task_id,
                "retry_exhausted",
                {"retry_count": retry_count, "max_retries": max_retries},
            )
            return

        # Reset the task and increment retry count
        await db.reset_task(task_id)
        meta["retry_count"] = retry_count + 1
        await db.update_task(task_id, metadata=json.dumps(meta))
        await db.log_event(
            task_id,
            "retried",
            {"retry_count": retry_count + 1, "max_retries": max_retries},
        )
        logger.info(
            "Retried task %s (attempt %d/%d)",
            task_name,
            retry_count + 1,
            max_retries,
        )


# Module-level singleton
_hook_manager = HookManager()


def get_hook_manager() -> HookManager:
    """Get the singleton HookManager instance."""
    return _hook_manager


def init_hooks(hooks_path: Path) -> None:
    """Initialize the hook manager with a config file path."""
    _hook_manager.load(hooks_path)
