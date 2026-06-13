"""MCP tool definitions and handlers for notes operations.

Tools: search_vault, get_project_context, get_global_rules, list_projects,
       get_note, create_note, update_note
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Callable

from mcp.types import TextContent, Tool

logger = logging.getLogger(__name__)

# All supported note types (extended for Wiki Pattern)
NOTE_TYPES = [
    "prd", "architecture", "guidelines", "api", "decision", "note",
    "concept", "comparison", "synthesis", "research",
]

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[Tool] = [
    Tool(
        name="search_vault",
        description="Semantic search across the entire Obsidian vault. Use this to find relevant architecture decisions, guidelines, API rules, and business logic. Returns the most relevant chunks of text.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query, e.g. 'authentication flow' or 'UI design guidelines'",
                },
                "project": {
                    "type": "string",
                    "description": "Optional: filter by project slug (e.g. 'brieftube', 'faithly')",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_project_context",
        description="Get the full context for a specific project — PRD, architecture, rules, and guidelines. Use this when starting work on a project to understand its structure and rules.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project slug (e.g. 'brieftube', 'faithly')",
                },
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="get_global_rules",
        description="Get global coding standards, design principles, and tech stack that apply to ALL projects.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="list_projects",
        description="List all projects in the Obsidian vault with their note counts.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="get_note",
        description="Read a specific note by its path relative to the vault root.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the note, e.g. 'brieftube/architecture.md'",
                },
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="create_note",
        description="Create a new note in the vault. Use this to document architecture decisions, add project guidelines, save research findings, create concept pages, or record comparisons and syntheses.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project slug for the note",
                },
                "title": {
                    "type": "string",
                    "description": "Note title",
                },
                "note_type": {
                    "type": "string",
                    "description": "Type of note: prd, architecture, guidelines, api, decision, note, concept, comparison, synthesis, research",
                    "enum": NOTE_TYPES,
                },
                "content": {
                    "type": "string",
                    "description": "Markdown content of the note",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags for the note",
                },
            },
            "required": ["project", "title", "note_type", "content"],
        },
    ),
    Tool(
        name="update_note",
        description="Update an existing note in the vault. Use to add Outcome sections to decisions, update architecture docs, or append new information. Supports both appending and full replacement.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the note, e.g. 'brieftube/decisions.md'",
                },
                "append_content": {
                    "type": "string",
                    "description": "Content to append to the end of the note",
                },
                "replace_content": {
                    "type": "string",
                    "description": "Full replacement content (replaces entire body, keeps frontmatter)",
                },
            },
            "required": ["path"],
        },
    ),
]

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def handle_search_vault(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_index
    index = _get_index()
    results = index.search(
        query=arguments["query"],
        n_results=arguments.get("n_results", 5),
        project=arguments.get("project"),
    )
    if not results:
        return [TextContent(type="text", text="No relevant results found.")]

    output_parts = []
    for i, r in enumerate(results, 1):
        method = r.get('search_method', '')
        method_badge = f" [{method}]" if method else ""
        output_parts.append(
            f"### Result {i} (score: {r['score']}{method_badge}) — {r['source']}\n"
            f"**Project**: {r['project']} | **Type**: {r['type']}\n\n"
            f"{r['text']}"
        )
    return [TextContent(type="text", text="\n\n---\n\n".join(output_parts))]


async def handle_get_project_context(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path
    from obsidian_bridge.parser import get_project_notes
    vault = _get_vault_path()
    project = arguments["project"]
    notes = get_project_notes(vault, project)
    if not notes:
        return [TextContent(type="text", text=f"No notes found for project '{project}'.")]

    # Sort: prd first, then architecture, then rest
    type_order = {"prd": 0, "architecture": 1, "guidelines": 2, "api": 3,
                  "decision": 4, "concept": 5, "comparison": 6,
                  "synthesis": 7, "research": 8}
    notes.sort(key=lambda n: type_order.get(n.note_type, 99))

    parts = [f"# Project Context: {project}\n"]
    for note in notes:
        parts.append(f"## {note.title} ({note.note_type})\n\n{note.content}")

    return [TextContent(type="text", text="\n\n---\n\n".join(parts))]


async def handle_get_global_rules(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path
    from obsidian_bridge.parser import parse_note
    vault = _get_vault_path()
    global_dir = vault / "_global"
    if not global_dir.exists():
        return [TextContent(type="text", text="No global rules found.")]
    notes = []
    for md in sorted(global_dir.rglob("*.md")):
        note = parse_note(md, vault)
        if note:
            notes.append(f"## {note.title}\n\n{note.content}")
    return [TextContent(type="text", text="\n\n---\n\n".join(notes))]


async def handle_list_projects(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path
    from obsidian_bridge.parser import get_projects, get_project_notes
    vault = _get_vault_path()
    projects = get_projects(vault)
    lines = ["# Projects in Vault\n"]
    for p in projects:
        notes = get_project_notes(vault, p)
        types = ", ".join(sorted(set(n.note_type for n in notes)))
        lines.append(f"- **{p}** — {len(notes)} notes ({types})")
    return [TextContent(type="text", text="\n".join(lines))]


async def handle_get_note(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path
    from obsidian_bridge.parser import parse_note
    vault = _get_vault_path()
    note_path = (vault / arguments["path"]).resolve()
    if not note_path.is_relative_to(vault.resolve()):
        return [TextContent(type="text", text="❌ Path must be within vault.")]
    if not note_path.exists():
        return [TextContent(type="text", text=f"Note not found: {arguments['path']}")]
    note = parse_note(note_path, vault)
    if not note:
        return [TextContent(type="text", text="Failed to parse note.")]
    return [TextContent(type="text", text=f"# {note.title}\n\n{note.content}")]


async def handle_create_note(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path, _get_index, _append_to_log, _regenerate_index
    from obsidian_bridge.parser import parse_note
    from obsidian_bridge.fact_extractor import FactExtractor
    vault = _get_vault_path()
    project = arguments["project"]
    title = arguments["title"]
    note_type = arguments["note_type"]
    content = arguments["content"]
    tags = arguments.get("tags", [])

    # Create project directory if needed
    project_dir = vault / project
    project_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename (with collision protection)
    filename = title.lower().replace(" ", "-").replace("/", "-")
    filename = "".join(c for c in filename if c.isalnum() or c in "-_")
    file_path = project_dir / f"{filename}.md"
    counter = 1
    while file_path.exists():
        file_path = project_dir / f"{filename}-{counter}.md"
        counter += 1

    # Build frontmatter
    today = date.today().isoformat()
    fm_content = (
        f"---\n"
        f"project: {project}\n"
        f"type: {note_type}\n"
        f"tags:\n"
        + "".join(f"  - \"{tag}\"\n" for tag in tags)
        + f"priority: medium\n"
        f"created: {today}\n"
        f"updated: {today}\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"{content}\n"
    )

    file_path.write_text(fm_content, encoding="utf-8")

    # Re-index this note
    index = _get_index()
    note = parse_note(file_path, vault)
    if note:
        index.index_notes([note])

    # Auto-log and regenerate index (Karpathy pattern)
    _append_to_log(vault, "create_note", project, title, note_type, tags)
    _regenerate_index(vault)

    result = f"✅ Note created: {file_path.relative_to(vault)}"

    # v0.8.0: Auto-extract temporal facts from decisions and architecture notes
    if note_type in ("decision", "architecture", "note", "research"):
        try:
            extractor = FactExtractor(vault)
            fact_report = extractor.extract_and_apply(
                text=content,
                project=project,
                source_note=str(file_path.relative_to(vault)),
                valid_from=today,
            )
            if fact_report.facts_added:
                result += "\n\n" + fact_report.to_markdown()
        except Exception as e:
            logger.warning(f"Auto fact extraction failed: {e}")

    return [TextContent(type="text", text=result)]


async def handle_update_note(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path, _get_index, _append_to_log, _regenerate_index
    from obsidian_bridge.parser import parse_note
    vault = _get_vault_path()
    note_path = (vault / arguments["path"]).resolve()
    if not note_path.is_relative_to(vault.resolve()):
        return [TextContent(type="text", text="❌ Path must be within vault.")]
    if not note_path.exists():
        return [TextContent(type="text", text=f"Note not found: {arguments['path']}")]

    import frontmatter as fm_lib
    raw = note_path.read_text(encoding="utf-8")
    post = fm_lib.loads(raw)

    if "replace_content" in arguments and arguments["replace_content"]:
        post.content = arguments["replace_content"]
    elif "append_content" in arguments and arguments["append_content"]:
        post.content = post.content.rstrip() + "\n\n" + arguments["append_content"]
    else:
        return [TextContent(type="text", text="No content provided. Use append_content or replace_content.")]

    # Update 'updated' field in frontmatter
    post.metadata["updated"] = date.today().isoformat()
    note_path.write_text(fm_lib.dumps(post), encoding="utf-8")

    # Re-index
    index = _get_index()
    note = parse_note(note_path, vault)
    if note:
        index.index_notes([note])

    # Auto-log
    _append_to_log(vault, "update_note", details=f"Updated: {arguments['path']}")
    _regenerate_index(vault)

    return [TextContent(type="text", text=f"✅ Note updated: {arguments['path']}")]


HANDLERS: dict[str, Callable] = {
    "search_vault": handle_search_vault,
    "get_project_context": handle_get_project_context,
    "get_global_rules": handle_get_global_rules,
    "list_projects": handle_list_projects,
    "get_note": handle_get_note,
    "create_note": handle_create_note,
    "update_note": handle_update_note,
}
