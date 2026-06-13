"""MCP tool definitions and handlers for capture & recall operations.

Tools: get_wakeup_context, save_insight, ingest_source, auto_radar_scan
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Callable

from mcp.types import TextContent, Tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[Tool] = [
    Tool(
        name="get_wakeup_context",
        description="Get compact wake-up context (~200 tokens) with critical facts: "
                    "active projects, recent decisions, inbox items, blockers. "
                    "Call this FIRST when starting a new session for instant context.",
        inputSchema={
            "type": "object",
            "properties": {
                "focus_project": {
                    "type": "string",
                    "description": "Optional: prioritize this project in the summary",
                },
            },
        },
    ),
    Tool(
        name="save_insight",
        description="Save a valuable search answer or synthesis back into the wiki. "
                    "Use when a query produces insights worth preserving permanently. "
                    "Creates a compounding knowledge loop: sources → wiki → queries → insights → wiki.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project slug for the insight",
                },
                "title": {
                    "type": "string",
                    "description": "Title for the insight note",
                },
                "content": {
                    "type": "string",
                    "description": "The insight or synthesis to save",
                },
                "source_query": {
                    "type": "string",
                    "description": "The search query that led to this insight",
                },
                "note_type": {
                    "type": "string",
                    "enum": ["synthesis", "research", "concept"],
                    "default": "synthesis",
                    "description": "Type of insight note (default: synthesis)",
                },
            },
            "required": ["project", "title", "content"],
        },
    ),
    Tool(
        name="ingest_source",
        description="Cascade ingest: process a new source (text, URL, note) and "
                    "automatically update ALL related wiki pages. Creates primary note, "
                    "adds cross-references to related pages, creates concept stubs for "
                    "new entities. A single ingest can touch 5-15 wiki pages.",
        inputSchema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Source content (text, article, idea, etc.)",
                },
                "source_type": {
                    "type": "string",
                    "enum": ["text", "url", "note"],
                    "default": "text",
                    "description": "Type of source being ingested",
                },
                "project": {
                    "type": "string",
                    "default": "inbox",
                    "description": "Target project (default: inbox)",
                },
                "title": {
                    "type": "string",
                    "description": "Optional title for the note",
                },
                "url": {
                    "type": "string",
                    "description": "URL if source_type is 'url'",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags for the note",
                },
            },
            "required": ["content"],
        },
    ),
    Tool(
        name="auto_radar_scan",
        description="Run automated Tech Radar scan with diff tracking. Compares with "
                    "previous scan, saves diff report to vault, and optionally sends "
                    "Telegram alert if important new tools are found.",
        inputSchema={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["mcp", "ai", "devtools", "all"],
                    "default": "all",
                    "description": "Category to scan",
                },
                "notify": {
                    "type": "boolean",
                    "default": True,
                    "description": "Send Telegram alert for important findings (default: true)",
                },
            },
        },
    ),
]

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def handle_get_wakeup_context(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path, _append_to_log
    from obsidian_bridge.config import get_settings
    from obsidian_bridge.wakeup import WakeupContext
    vault = _get_vault_path()
    settings = get_settings()
    wakeup = WakeupContext(
        vault_path=vault,
        project_base_dirs=settings.project_base_dirs,
    )
    context = wakeup.generate(
        focus_project=arguments.get("focus_project", ""),
    )
    _append_to_log(vault, "wakeup_context")
    return [TextContent(type="text", text=context)]


async def handle_save_insight(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path, _get_index, _append_to_log, _regenerate_index
    from obsidian_bridge.parser import parse_note
    vault = _get_vault_path()
    project = arguments["project"]
    title = arguments["title"]
    content = arguments["content"]
    source_query = arguments.get("source_query", "")
    note_type = arguments.get("note_type", "synthesis")

    # Enrich content with write-back metadata
    enriched = content
    if source_query:
        enriched = f"> 🔄 Write-back from query: *{source_query}*\n\n{content}"

    # Create project directory if needed
    project_dir = vault / project
    project_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    filename = title.lower().replace(" ", "-").replace("/", "-")
    filename = "".join(c for c in filename if c.isalnum() or c in "-_")
    file_path = project_dir / f"{filename}.md"

    today = date.today().isoformat()
    tags = ["write-back", "insight"]
    if source_query:
        tags.append("query-derived")
    tags_yaml = "".join(f'  - "{tag}"\n' for tag in tags)

    fm_content = (
        f"---\n"
        f"project: {project}\n"
        f"type: {note_type}\n"
        f"tags:\n"
        f"{tags_yaml}"
        f"priority: medium\n"
        f"created: {today}\n"
        f"updated: {today}\n"
        f"source_query: \"{source_query}\"\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"{enriched}\n"
    )

    file_path.write_text(fm_content, encoding="utf-8")

    # Re-index
    index = _get_index()
    note = parse_note(file_path, vault)
    if note:
        index.index_notes([note])

    _append_to_log(vault, "write-back", project, title, note_type, tags,
                   details=f"Query: {source_query}" if source_query else "")
    _regenerate_index(vault)

    return [TextContent(type="text", text=f"✅ Insight saved: {file_path.relative_to(vault)}")]


async def handle_ingest_source(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path, _get_index, _regenerate_index
    from obsidian_bridge.ingest import IngestPipeline, IngestSource
    from obsidian_bridge.fact_extractor import FactExtractor
    vault = _get_vault_path()
    content = arguments["content"]
    source_type = arguments.get("source_type", "text")
    project = arguments.get("project", "inbox")
    title = arguments.get("title", "")
    url = arguments.get("url", "")
    tags = arguments.get("tags", [])

    source = IngestSource(
        content=content,
        source_type=source_type,
        project=project,
        title=title,
        url=url,
        tags=tags,
    )

    index = _get_index()
    pipeline = IngestPipeline(vault_path=vault, index=index)
    report = pipeline.ingest(source)

    # v0.8.0: Auto-extract temporal facts
    try:
        extractor = FactExtractor(vault)
        fact_report = extractor.extract_and_apply(
            text=content,
            project=project,
            source_note=report.primary_note,
        )
    except Exception as e:
        logger.warning(f"Auto fact extraction during ingest failed: {e}")
        fact_report = None

    # Re-generate index.md
    _regenerate_index(vault)

    result = report.to_markdown()
    if fact_report and fact_report.facts_added:
        result += "\n" + fact_report.to_markdown()

    return [TextContent(type="text", text=result)]


async def handle_auto_radar_scan(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path
    from obsidian_bridge.config import get_settings
    from obsidian_bridge.auto_radar import AutoRadar, notify_telegram as radar_notify
    vault = _get_vault_path()
    category = arguments.get("category", "all")
    should_notify = arguments.get("notify", True)

    auto_radar = AutoRadar(vault)
    diff = await auto_radar.run_scan(category)

    # Send Telegram notification if enabled and there are findings
    notification_status = ""
    if should_notify and diff.has_important_changes:
        settings = get_settings()
        if settings.telegram_bot_token and settings.telegram_allowed_users:
            sent = await radar_notify(
                diff=diff,
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_allowed_users[0],
            )
            notification_status = "\n\n📱 Telegram alert sent!" if sent else "\n\n⚠️ Telegram alert failed."

    result = diff.to_markdown() + notification_status
    return [TextContent(type="text", text=result)]


HANDLERS: dict[str, Callable] = {
    "get_wakeup_context": handle_get_wakeup_context,
    "save_insight": handle_save_insight,
    "ingest_source": handle_ingest_source,
    "auto_radar_scan": handle_auto_radar_scan,
}
