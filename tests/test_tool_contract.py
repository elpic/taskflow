# Contract tests for the MCP tool API surface.
#
# These tests intentionally pin the tool names and parameter signatures so that
# any accidental addition, removal, or renaming of a tool or parameter causes an
# explicit, visible failure.  When a breaking change is *intentional*, update the
# expected values here as part of the same PR so reviewers see the delta clearly.

from src.server import mcp

# ---------------------------------------------------------------------------
# Contract constants
# ---------------------------------------------------------------------------

EXPECTED_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "task_analytics",
        "task_complete",
        "task_context",
        "task_create",
        "task_current",
        "task_delete",
        "task_fail",
        "task_get",
        "task_history",
        "task_list",
        "task_move",
        "task_next",
        "task_reorder",
        "task_reset",
        "task_resume",
        "task_search",
        "task_start",
        "task_stats",
        "task_types",
        "task_update",
    }
)

EXPECTED_TOOL_COUNT: int = len(EXPECTED_TOOL_NAMES)

EXPECTED_PARAMETERS: dict[str, frozenset[str]] = {
    "task_analytics": frozenset({"query", "days"}),
    "task_complete": frozenset({"task_id", "output", "summary"}),
    "task_context": frozenset({"task_id", "max_chars"}),
    "task_create": frozenset(
        {
            "name",
            "description",
            "parent_id",
            "verification_criteria",
            "task_type",
            "idempotency_key",
            "blocked_by",
        }
    ),
    "task_current": frozenset(),
    "task_delete": frozenset({"task_id"}),
    "task_fail": frozenset({"task_id", "reason"}),
    "task_get": frozenset({"task_id"}),
    "task_history": frozenset({"task_id", "recursive"}),
    "task_list": frozenset({"status", "parent_id", "ready"}),
    "task_move": frozenset({"task_id", "new_parent_id"}),
    "task_next": frozenset({"root_id"}),
    "task_reorder": frozenset({"task_id", "position"}),
    "task_reset": frozenset({"task_id", "recursive"}),
    "task_resume": frozenset({"root_id"}),
    "task_search": frozenset({"query"}),
    "task_start": frozenset({"task_id"}),
    "task_stats": frozenset({"task_id"}),
    "task_types": frozenset(),
    "task_update": frozenset(
        {"task_id", "name", "description", "verification_criteria", "metadata"}
    ),
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _registered_tools() -> list:
    """Return all registered Tool objects via the public API."""
    return mcp._tool_manager.list_tools()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_tool_count() -> None:
    """Quick sanity check: total number of registered tools must match contract."""
    actual = len(_registered_tools())
    assert actual == EXPECTED_TOOL_COUNT, (
        f"Tool count changed: expected {EXPECTED_TOOL_COUNT}, got {actual}. "
        "Update EXPECTED_TOOL_COUNT in test_tool_contract.py."
    )


def test_tool_names_match_contract() -> None:
    """Every tool name must be present in the contract — no more, no less."""
    actual = frozenset(t.name for t in _registered_tools())
    added = actual - EXPECTED_TOOL_NAMES
    removed = EXPECTED_TOOL_NAMES - actual

    messages: list[str] = []
    if added:
        messages.append(f"New tools not in contract: {sorted(added)}")
    if removed:
        messages.append(f"Tools removed from server: {sorted(removed)}")

    assert not messages, "\n".join(messages)


def test_tool_parameter_signatures() -> None:
    """Each tool's parameter names must exactly match the pinned contract."""
    tools = {t.name: t for t in _registered_tools()}
    mismatches: list[str] = []

    for tool_name, expected_params in EXPECTED_PARAMETERS.items():
        if tool_name not in tools:
            mismatches.append(f"{tool_name}: tool not found")
            continue

        tool = tools[tool_name]
        schema = tool.parameters or {}
        actual_params = frozenset(schema.get("properties", {}).keys())

        added = actual_params - expected_params
        removed = expected_params - actual_params

        if added or removed:
            parts: list[str] = []
            if added:
                parts.append(f"added={sorted(added)}")
            if removed:
                parts.append(f"removed={sorted(removed)}")
            mismatches.append(f"{tool_name}: {', '.join(parts)}")

    assert not mismatches, "Parameter signature drift detected:\n" + "\n".join(
        f"  - {m}" for m in mismatches
    )
