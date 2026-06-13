"""MCP tool definitions and handlers for intelligence/scout operations.

Tools: analyze_sessions, scout_tools, check_dependencies
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from mcp.types import TextContent, Tool

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[Tool] = [
    Tool(
        name="analyze_sessions",
        description="Analyze session logs across projects to find repeating problems, common failure patterns, and reusable workarounds. Use this to identify areas that need better tooling or documentation.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Optional: analyze only this project's sessions",
                },
            },
        },
    ),
    Tool(
        name="scout_tools",
        description="Scan the internet for new tools, MCP servers, and developer utilities relevant to our tech stack. Categories: 'mcp', 'ai', 'devtools', 'all'.",
        inputSchema={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Category to scan: 'mcp', 'ai', 'devtools', or 'all'",
                    "enum": ["mcp", "ai", "devtools", "all"],
                    "default": "all",
                },
            },
        },
    ),
    Tool(
        name="check_dependencies",
        description="Check a project's dependencies (npm/pip/flutter) for outdated packages and security patches. Requires the project to exist on local filesystem.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project slug to check dependencies for",
                },
            },
            "required": ["project"],
        },
    ),
]

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def handle_analyze_sessions(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path, _append_to_log
    from obsidian_bridge.scout import SessionAnalyzer
    vault = _get_vault_path()
    analyzer = SessionAnalyzer(vault)
    project = arguments.get("project")
    report = analyzer.analyze(project)
    _append_to_log(
        vault, "analyze_sessions",
        project=project or "all",
        details=f"{report.total_sessions} sessions, {report.total_issues} issues, "
                f"{len(report.repeating_issues)} repeating patterns",
    )
    return [TextContent(type="text", text=report.to_markdown())]


async def handle_scout_tools(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path, _append_to_log
    from obsidian_bridge.scout import TechRadar
    vault = _get_vault_path()
    radar = TechRadar(vault)
    category = arguments.get("category", "all")
    report = await radar.scan(category)
    _append_to_log(
        vault, "scout_tools",
        details=f"category={category}, found={report.tools_found}",
    )
    return [TextContent(type="text", text=report.to_markdown())]


async def handle_check_dependencies(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path, _append_to_log
    from obsidian_bridge.config import get_settings
    from obsidian_bridge.scout import DependencyChecker
    vault = _get_vault_path()
    project = arguments["project"]
    settings = get_settings()
    # Build project path mapping from base dirs
    project_paths = {}
    for base_dir in settings.project_base_dirs:
        base = Path(base_dir)
        if base.exists():
            for d in base.iterdir():
                if d.is_dir():
                    project_paths[d.name] = str(d)

    checker = DependencyChecker(vault, project_paths)
    report = await checker.check(project)
    _append_to_log(
        vault, "check_dependencies",
        project=project,
        details=f"manager={report.package_manager}, "
                f"total={report.total_deps}, outdated={len(report.outdated)}",
    )
    return [TextContent(type="text", text=report.to_markdown())]


HANDLERS: dict[str, Callable] = {
    "analyze_sessions": handle_analyze_sessions,
    "scout_tools": handle_scout_tools,
    "check_dependencies": handle_check_dependencies,
}
