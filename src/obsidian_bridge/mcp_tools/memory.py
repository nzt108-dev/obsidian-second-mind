"""MCP tool definitions and handlers for agent memory operations.

Tools: save_session, load_session, get_enhanced_wakeup
"""
from __future__ import annotations

from typing import Callable

from mcp.types import TextContent, Tool

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[Tool] = [
    Tool(
        name="save_session",
        description="Save current session context to vault for future recall. "
                    "Captures git state, uncommitted changes, recent commits, decisions, "
                    "and next steps. Creates both JSON snapshot and vault note. "
                    "Call this at the END of a session or before context loss.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project slug to save session for",
                },
                "summary": {
                    "type": "string",
                    "description": "Brief summary of what was done this session",
                },
                "next_steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Prioritized list of what to do next session",
                },
                "blockers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Known blockers or issues",
                },
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="load_session",
        description="Load the most recent session snapshot for a project. "
                    "Returns git state, what was done, uncommitted changes, "
                    "next steps, and blockers. Use at session START for instant recall.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project slug to load last session for",
                },
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="get_enhanced_wakeup",
        description="Enhanced wake-up context combining standard context, last session memory, "
                    "and temporal KG facts. Use this instead of get_wakeup_context for "
                    "richer session start with full memory recall.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Focus project for enhanced context",
                },
            },
        },
    ),
]

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def handle_save_session(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path
    from obsidian_bridge.config import get_settings
    from obsidian_bridge.hooks import SessionHooks
    vault = _get_vault_path()
    settings = get_settings()
    hooks = SessionHooks(vault, settings.project_base_dirs)
    snapshot = hooks.save_session(
        project=arguments["project"],
        summary=arguments.get("summary", ""),
        next_steps=arguments.get("next_steps"),
        blockers=arguments.get("blockers"),
    )

    result = (
        f"✅ Session saved for **{snapshot.project}** at {snapshot.timestamp}\n\n"
        f"{snapshot.to_markdown()}"
    )
    return [TextContent(type="text", text=result)]


async def handle_load_session(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path
    from obsidian_bridge.config import get_settings
    from obsidian_bridge.hooks import SessionHooks
    vault = _get_vault_path()
    settings = get_settings()
    hooks = SessionHooks(vault, settings.project_base_dirs)
    snapshot = hooks.load_last_session(arguments["project"])

    if not snapshot:
        return [TextContent(
            type="text",
            text=f"No saved session found for '{arguments['project']}'. "
                 f"This is the first session.",
        )]

    return [TextContent(type="text", text=snapshot.to_markdown())]


async def handle_get_enhanced_wakeup(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path
    from obsidian_bridge.config import get_settings
    from obsidian_bridge.hooks import generate_enhanced_wakeup
    vault = _get_vault_path()
    settings = get_settings()
    context = generate_enhanced_wakeup(
        vault_path=vault,
        project=arguments.get("project", ""),
        project_base_dirs=settings.project_base_dirs,
    )
    return [TextContent(type="text", text=context)]


HANDLERS: dict[str, Callable] = {
    "save_session": handle_save_session,
    "load_session": handle_load_session,
    "get_enhanced_wakeup": handle_get_enhanced_wakeup,
}
