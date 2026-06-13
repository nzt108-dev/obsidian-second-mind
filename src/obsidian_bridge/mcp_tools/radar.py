"""MCP tool definitions and handlers for GitHub radar and context packing.

Tools: scan_architecture, scan_github_trending, watch_developer, analyze_repo,
       pack_context
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
        name="scan_architecture",
        description="Scan a project's source code and generate an architecture map with "
                    "Mermaid dependency diagrams. Saves the map to vault as architecture-map.md. "
                    "Uses AST parsing — fast, no LLM needed.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project slug to scan (must exist on local filesystem)",
                },
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="scan_github_trending",
        description="Scan GitHub for trending repositories with rapid star growth. "
                    "Filters by topic (ai/mcp/devtools/mobile/web/all) and scores relevance "
                    "to our tech stack. Zero cost — uses GitHub REST API.",
        inputSchema={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic filter: 'ai', 'mcp', 'devtools', 'mobile', 'web', or 'all'",
                    "default": "all",
                },
                "days": {
                    "type": "integer",
                    "description": "Look back N days (default: 7)",
                    "default": 7,
                },
                "min_stars": {
                    "type": "integer",
                    "description": "Minimum stars threshold (default: 50)",
                    "default": 50,
                },
            },
        },
    ),
    Tool(
        name="watch_developer",
        description="Manage GitHub developer watch list. Add developers to track, "
                    "list watched developers, or check a developer's recent activity.",
        inputSchema={
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "GitHub username (e.g. 'karpathy')",
                },
                "action": {
                    "type": "string",
                    "description": "Action: 'add', 'remove', 'list', or 'check'",
                    "default": "check",
                },
                "category": {
                    "type": "string",
                    "description": "Category for 'add' action (e.g. 'ai', 'devtools')",
                    "default": "general",
                },
            },
        },
    ),
    Tool(
        name="analyze_repo",
        description="Analyze a specific GitHub repository in detail. Returns stars, "
                    "README summary, topics, relevance score, and which of our projects "
                    "could benefit from it.",
        inputSchema={
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/name' format (e.g. 'anthropics/courses')",
                },
            },
            "required": ["repo"],
        },
    ),
    Tool(
        name="pack_context",
        description="Pack an entire project's source code into a single structured markdown file "
                    "optimized for AI context. Modes: 'full' (~200k tokens), 'compact' (~50k), "
                    "'minimal' (~10k). Saves to vault.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project slug to pack (must exist on local filesystem)",
                },
                "mode": {
                    "type": "string",
                    "description": "Packing mode: 'full', 'compact', or 'minimal' (default: compact)",
                    "default": "compact",
                },
            },
            "required": ["project"],
        },
    ),
]

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def handle_scan_architecture(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path, _append_to_log, _regenerate_index
    from obsidian_bridge.config import get_settings
    from obsidian_bridge.architect import scan_and_save as _scan_architecture
    vault = _get_vault_path()
    project = arguments["project"]
    settings = get_settings()
    result = _scan_architecture(
        vault_path=vault,
        project=project,
        project_base_dirs=settings.project_base_dirs,
    )
    _append_to_log(vault, "scan_architecture", project=project)
    _regenerate_index(vault)
    return [TextContent(type="text", text=result)]


async def handle_scan_github_trending(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path, _append_to_log
    from obsidian_bridge.github_radar import TrendingScanner
    vault = _get_vault_path()
    scanner = TrendingScanner()
    topic = arguments.get("topic", "all")
    repos = scanner.scan(
        topic=topic,
        days=arguments.get("days", 7),
        min_stars=arguments.get("min_stars", 50),
    )
    report = scanner.to_markdown(repos, topic)
    _append_to_log(vault, "scan_github_trending", project="_global")
    return [TextContent(type="text", text=report)]


async def handle_watch_developer(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path
    from obsidian_bridge.github_radar import DeveloperWatcher
    vault = _get_vault_path()
    watcher = DeveloperWatcher(vault_path=vault)
    action = arguments.get("action", "check")
    username = arguments.get("username", "")

    if action == "add":
        if not username:
            return [TextContent(type="text", text="❌ username is required for 'add'")]
        result = watcher.add(username, arguments.get("category", "general"))
    elif action == "remove":
        if not username:
            return [TextContent(type="text", text="❌ username is required for 'remove'")]
        result = watcher.remove(username)
    elif action == "list":
        result = watcher.list_watched()
    elif action == "check":
        if not username:
            return [TextContent(type="text", text="❌ username is required for 'check'")]
        profile = watcher.check(username)
        if not profile:
            return [TextContent(type="text", text=f"❌ Could not fetch @{username}")]
        result = watcher.check_to_markdown(profile)
    else:
        result = f"❌ Unknown action: {action}. Use: add, remove, list, check"

    return [TextContent(type="text", text=result)]


async def handle_analyze_repo(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.github_radar import RepoAnalyzer
    analyzer = RepoAnalyzer()
    repo_name = arguments["repo"]
    analysis = analyzer.analyze(repo_name)
    if not analysis:
        return [TextContent(type="text", text=f"❌ Could not analyze {repo_name}")]
    report = analyzer.to_markdown(analysis)
    return [TextContent(type="text", text=report)]


async def handle_pack_context(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path, _append_to_log
    from obsidian_bridge.config import get_settings
    from obsidian_bridge.context_packer import ProjectPacker
    vault = _get_vault_path()
    project = arguments["project"]
    mode = arguments.get("mode", "compact")
    settings = get_settings()

    # Find project directory
    project_dir = None
    for base in settings.project_base_dirs:
        candidate = Path(base) / project
        if candidate.is_dir():
            project_dir = candidate
            break
    if not project_dir:
        return [TextContent(type="text", text=f"❌ Project '{project}' not found")]

    packer = ProjectPacker(project_dir, mode=mode)
    ctx = packer.pack()
    output = packer.to_markdown(ctx)

    # Save to vault
    out_path = vault / project / "context-pack.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output, encoding="utf-8")

    summary = (
        f"📦 Packed {project} ({mode} mode)\n"
        f"Files: {ctx.included_files}/{ctx.total_files} | "
        f"~{ctx.token_estimate:,} tokens\n"
        f"Saved to: {project}/context-pack.md"
    )
    _append_to_log(vault, "pack_context", project=project)
    return [TextContent(type="text", text=summary)]


HANDLERS: dict[str, Callable] = {
    "scan_architecture": handle_scan_architecture,
    "scan_github_trending": handle_scan_github_trending,
    "watch_developer": handle_watch_developer,
    "analyze_repo": handle_analyze_repo,
    "pack_context": handle_pack_context,
}
