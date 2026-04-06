"""MCP Server for Obsidian Second Mind.

Exposes vault content as tools and resources for AI coding agents.
"""
import json
import logging
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    TextContent,
    Tool,
)

from obsidian_bridge.config import get_settings
from obsidian_bridge.indexer import VaultIndex
from obsidian_bridge.parser import get_project_notes, get_projects, parse_note, scan_vault

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

app = Server("obsidian-second-mind")


def _get_index() -> VaultIndex:
    """Lazy-init the vault index."""
    if not hasattr(_get_index, "_instance"):
        settings = get_settings()
        _get_index._instance = VaultIndex(settings)
    return _get_index._instance


def _get_vault_path() -> Path:
    return get_settings().vault_path


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@app.list_resources()
async def list_resources() -> list[Resource]:
    vault = _get_vault_path()
    projects = get_projects(vault)

    resources = [
        Resource(
            uri="vault://global",
            name="Global Rules & Standards",
            description="Global coding standards, tech stack, and design principles",
            mimeType="text/markdown",
        ),
        Resource(
            uri="vault://projects",
            name="All Projects",
            description="List of all projects in the vault",
            mimeType="application/json",
        ),
    ]

    for project in projects:
        resources.append(Resource(
            uri=f"vault://project/{project}",
            name=f"Project: {project}",
            description=f"All notes for project '{project}'",
            mimeType="text/markdown",
        ))

    return resources


@app.read_resource()
async def read_resource(uri: str) -> str:
    vault = _get_vault_path()

    if uri == "vault://global":
        global_dir = vault / "_global"
        if not global_dir.exists():
            return "No global notes found."
        notes = []
        for md in sorted(global_dir.rglob("*.md")):
            note = parse_note(md, vault)
            if note:
                notes.append(f"# {note.title}\n\n{note.content}")
        return "\n\n---\n\n".join(notes)

    elif uri == "vault://projects":
        projects = get_projects(vault)
        result = {"projects": []}
        for p in projects:
            notes = get_project_notes(vault, p)
            result["projects"].append({
                "name": p,
                "notes_count": len(notes),
                "types": list(set(n.note_type for n in notes)),
            })
        return json.dumps(result, indent=2)

    elif uri.startswith("vault://project/"):
        project = uri.replace("vault://project/", "")
        notes = get_project_notes(vault, project)
        if not notes:
            return f"No notes found for project '{project}'."
        parts = []
        for note in notes:
            parts.append(f"## {note.title}\n**Type**: {note.note_type} | **Tags**: {', '.join(note.tags)}\n\n{note.content}")
        return "\n\n---\n\n".join(parts)

    return f"Unknown resource: {uri}"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
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
            description="Create a new note in the vault. Use this to document architecture decisions, add project guidelines, or save important context for future sessions.",
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
                        "description": "Type of note: prd, architecture, guidelines, api, decision, note",
                        "enum": ["prd", "architecture", "guidelines", "api", "decision", "note"],
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
            name="rebuild_index",
            description="Rebuild the vector search index. Use after manually editing vault files.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    vault = _get_vault_path()

    if name == "search_vault":
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

    elif name == "get_project_context":
        project = arguments["project"]
        notes = get_project_notes(vault, project)
        if not notes:
            return [TextContent(type="text", text=f"No notes found for project '{project}'.")]

        # Sort: prd first, then architecture, then rest
        type_order = {"prd": 0, "architecture": 1, "guidelines": 2, "api": 3, "decision": 4}
        notes.sort(key=lambda n: type_order.get(n.note_type, 99))

        parts = [f"# Project Context: {project}\n"]
        for note in notes:
            parts.append(f"## {note.title} ({note.note_type})\n\n{note.content}")

        return [TextContent(type="text", text="\n\n---\n\n".join(parts))]

    elif name == "get_global_rules":
        global_dir = vault / "_global"
        if not global_dir.exists():
            return [TextContent(type="text", text="No global rules found.")]
        notes = []
        for md in sorted(global_dir.rglob("*.md")):
            note = parse_note(md, vault)
            if note:
                notes.append(f"## {note.title}\n\n{note.content}")
        return [TextContent(type="text", text="\n\n---\n\n".join(notes))]

    elif name == "list_projects":
        projects = get_projects(vault)
        lines = ["# Projects in Vault\n"]
        for p in projects:
            notes = get_project_notes(vault, p)
            types = ", ".join(sorted(set(n.note_type for n in notes)))
            lines.append(f"- **{p}** — {len(notes)} notes ({types})")
        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "get_note":
        note_path = vault / arguments["path"]
        if not note_path.exists():
            return [TextContent(type="text", text=f"Note not found: {arguments['path']}")]
        note = parse_note(note_path, vault)
        if not note:
            return [TextContent(type="text", text="Failed to parse note.")]
        return [TextContent(type="text", text=f"# {note.title}\n\n{note.content}")]

    elif name == "create_note":
        project = arguments["project"]
        title = arguments["title"]
        note_type = arguments["note_type"]
        content = arguments["content"]
        tags = arguments.get("tags", [])

        # Create project directory if needed
        project_dir = vault / project
        project_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        filename = title.lower().replace(" ", "-").replace("/", "-")
        filename = "".join(c for c in filename if c.isalnum() or c in "-_")
        file_path = project_dir / f"{filename}.md"

        # Build frontmatter
        from datetime import date
        today = date.today().isoformat()
        fm_content = (
            f"---\n"
            f"project: {project}\n"
            f"type: {note_type}\n"
            f"tags:\n"
            + "".join(f"  - {tag}\n" for tag in tags)
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

        return [TextContent(type="text", text=f"✅ Note created: {file_path.relative_to(vault)}")]

    elif name == "rebuild_index":
        index = _get_index()
        index.clear()
        notes = scan_vault(vault)
        stats = index.index_notes(notes)
        return [TextContent(
            type="text",
            text=(
                f"✅ Index rebuilt:\n"
                f"- Notes indexed: {stats['added']}\n"
                f"- Total chunks: {stats['total_chunks']}\n"
            ),
        )]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def run_server():
    """Run the MCP server via stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main():
    """CLI entry point for the MCP server."""
    import asyncio
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
