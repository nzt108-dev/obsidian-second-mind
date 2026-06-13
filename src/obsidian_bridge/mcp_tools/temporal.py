"""MCP tool definitions and handlers for temporal knowledge graph operations.

Tools: kg_add_fact, kg_invalidate, kg_timeline, kg_check_contradictions
"""
from __future__ import annotations

from typing import Callable

from mcp.types import TextContent, Tool

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[Tool] = [
    Tool(
        name="kg_add_fact",
        description="Add a temporal fact to the knowledge graph. Facts have validity windows "
                    "(valid_from/valid_to). Automatically detects contradictions with existing facts "
                    "and auto-resolves them by invalidating the old fact.",
        inputSchema={
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Entity the fact is about (e.g. 'brieftube')",
                },
                "predicate": {
                    "type": "string",
                    "description": "Relationship type (e.g. 'uses_auth', 'uses_db', 'deploys_to')",
                },
                "object": {
                    "type": "string",
                    "description": "Value (e.g. 'clerk', 'postgresql', 'vercel')",
                },
                "source_note": {
                    "type": "string",
                    "description": "Path to the note establishing this fact",
                },
                "valid_from": {
                    "type": "string",
                    "description": "Date when fact became true (YYYY-MM-DD, default: today)",
                },
            },
            "required": ["subject", "predicate", "object"],
        },
    ),
    Tool(
        name="kg_invalidate",
        description="Mark a fact as no longer valid. Use when a technology/approach has been replaced.",
        inputSchema={
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "predicate": {"type": "string"},
                "object": {"type": "string"},
                "ended": {
                    "type": "string",
                    "description": "Date when fact stopped being true (YYYY-MM-DD, default: today)",
                },
            },
            "required": ["subject", "predicate", "object"],
        },
    ),
    Tool(
        name="kg_timeline",
        description="Get chronological history of ALL facts about an entity, including expired ones. "
                    "Shows what was true when — tech stack evolution, decision history, etc.",
        inputSchema={
            "type": "object",
            "properties": {
                "entity": {
                    "type": "string",
                    "description": "Entity to get timeline for (e.g. 'brieftube')",
                },
                "as_of": {
                    "type": "string",
                    "description": "Optional: query facts valid at this date (YYYY-MM-DD)",
                },
            },
            "required": ["entity"],
        },
    ),
    Tool(
        name="kg_check_contradictions",
        description="Check the entire knowledge graph for contradictions — facts that conflict with each other. "
                    "Returns a report grouped by severity (critical/warning/info).",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
]

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def handle_kg_add_fact(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path
    from obsidian_bridge.graph import TemporalKnowledgeGraph, ContradictionDetector
    vault = _get_vault_path()
    subject = arguments["subject"]
    predicate = arguments["predicate"]
    obj = arguments["object"]
    source_note = arguments.get("source_note", "")
    valid_from = arguments.get("valid_from", "")

    tkg = TemporalKnowledgeGraph(vault)
    fact, contradictions = tkg.add_fact(
        subject=subject,
        predicate=predicate,
        obj=obj,
        valid_from=valid_from,
        source_note=source_note,
    )

    result = f"✅ Fact added: {subject} {predicate} {obj} (since {fact.valid_from})"
    if contradictions:
        detector = ContradictionDetector(tkg)
        result += "\n\n" + detector.to_markdown(contradictions)

    return [TextContent(type="text", text=result)]


async def handle_kg_invalidate(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path
    from obsidian_bridge.graph import TemporalKnowledgeGraph
    vault = _get_vault_path()
    subject = arguments["subject"]
    predicate = arguments["predicate"]
    obj = arguments["object"]
    ended = arguments.get("ended", "")

    tkg = TemporalKnowledgeGraph(vault)
    found = tkg.invalidate(subject, predicate, obj, ended)

    if found:
        return [TextContent(type="text", text=f"✅ Fact invalidated: {subject} {predicate} {obj}")]
    else:
        return [TextContent(type="text", text=f"⚠️ Fact not found: {subject} {predicate} {obj}")]


async def handle_kg_timeline(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path
    from obsidian_bridge.graph import TemporalKnowledgeGraph
    vault = _get_vault_path()
    entity = arguments["entity"]
    as_of = arguments.get("as_of", "")

    tkg = TemporalKnowledgeGraph(vault)

    if as_of:
        # Query facts at specific date
        facts = tkg.query_entity(entity, as_of)
        lines = [f"# ⏱️ Facts about '{entity}' as of {as_of}", ""]
        for f in facts:
            status = "✅" if f.is_active else "❌"
            lines.append(f"{status} {f.predicate}: **{f.object}** (since {f.valid_from})")
    else:
        # Full timeline
        facts = tkg.timeline(entity)
        lines = [f"# ⏱️ Timeline: {entity}", ""]
        for f in facts:
            end = f" → {f.valid_to}" if f.valid_to else " → now"
            status = "✅" if f.is_active else "❌"
            lines.append(f"{status} [{f.valid_from}{end}] {f.predicate}: **{f.object}**")
            if f.source_note:
                lines.append(f"  Source: `{f.source_note}`")

    if not facts:
        lines.append(f"No facts found for '{entity}'.")

    # Append stats
    lines.append("")
    lines.append(f"---\n{tkg.to_markdown()}")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_kg_check_contradictions(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path
    from obsidian_bridge.graph import TemporalKnowledgeGraph, ContradictionDetector
    vault = _get_vault_path()
    tkg = TemporalKnowledgeGraph(vault)
    detector = ContradictionDetector(tkg)
    report = detector.to_markdown()
    return [TextContent(type="text", text=report)]


HANDLERS: dict[str, Callable] = {
    "kg_add_fact": handle_kg_add_fact,
    "kg_invalidate": handle_kg_invalidate,
    "kg_timeline": handle_kg_timeline,
    "kg_check_contradictions": handle_kg_check_contradictions,
}
