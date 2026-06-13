"""MCP tool definitions and handlers for vault maintenance operations.

Tools: lint_vault, rebuild_index, query_graph, extract_patterns
"""
from __future__ import annotations

from typing import Callable

from mcp.types import TextContent, Tool

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[Tool] = [
    Tool(
        name="lint_vault",
        description="Health-check the wiki. Finds: orphan pages (no inbound links), stale notes not updated for 90+ days, broken WikiLinks, frequently mentioned concepts without their own page, TODO/FIXME markers, and incomplete frontmatter.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Optional: lint only this project. If omitted, lints entire vault.",
                },
            },
        },
    ),
    Tool(
        name="rebuild_index",
        description="Rebuild the vector search index and regenerate index.md. Use after manually editing vault files.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="query_graph",
        description="Query the knowledge graph built from WikiLinks. Find connections between notes, hub pages, shortest paths, and clusters. Use to understand how concepts relate across projects.",
        inputSchema={
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "Type of graph query",
                    "enum": ["neighbors", "path", "hubs", "clusters", "stats"],
                },
                "node": {
                    "type": "string",
                    "description": "Node name (note stem) for neighbors/path queries",
                },
                "target": {
                    "type": "string",
                    "description": "Target node for path queries",
                },
                "depth": {
                    "type": "integer",
                    "description": "Depth for neighbor traversal (default: 2)",
                    "default": 2,
                },
            },
            "required": ["query_type"],
        },
    ),
    Tool(
        name="extract_patterns",
        description="Analyze decision outcomes across projects. Extract success patterns (best practices) and failure anti-patterns. Optionally generate auto-rules file in _global/auto-rules.md.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Optional: filter by project",
                },
                "generate_rules": {
                    "type": "boolean",
                    "description": "Generate auto-rules.md in vault (default: false)",
                    "default": False,
                },
            },
        },
    ),
]

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def handle_lint_vault(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path, _append_to_log
    from obsidian_bridge.config import get_settings
    from obsidian_bridge.linter import VaultLinter
    vault = _get_vault_path()
    settings = get_settings()
    linter = VaultLinter(vault, stale_days=settings.lint_stale_days)
    report = linter.lint(project=arguments.get("project"))

    # Log the lint operation
    _append_to_log(
        vault, "lint",
        project=arguments.get("project", "all"),
        details=f"Found {len(report.issues)} issues "
                f"(critical: {report.critical_count}, "
                f"warning: {report.warning_count}, "
                f"info: {report.info_count})",
    )

    return [TextContent(type="text", text=report.to_markdown())]


async def handle_rebuild_index(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path, _get_index, _append_to_log, _regenerate_index
    from obsidian_bridge.parser import scan_vault
    vault = _get_vault_path()
    index = _get_index()
    index.clear()
    notes = scan_vault(vault)
    stats = index.index_notes(notes)

    # Regenerate meta-files
    _regenerate_index(vault)
    _append_to_log(
        vault, "rebuild_index",
        details=f"Notes: {stats['added']}, Chunks: {stats['total_chunks']}",
    )

    return [TextContent(
        type="text",
        text=(
            f"✅ Index rebuilt:\n"
            f"- Notes indexed: {stats['added']}\n"
            f"- Total chunks: {stats['total_chunks']}\n"
            f"- index.md regenerated\n"
            f"- log.md updated\n"
        ),
    )]


async def handle_query_graph(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path, _append_to_log
    from obsidian_bridge.graph import KnowledgeGraph
    vault = _get_vault_path()
    graph = KnowledgeGraph(vault)
    graph.build()
    query_type = arguments.get("query_type", "stats")

    if query_type == "stats":
        result = graph.to_markdown()
    elif query_type == "neighbors":
        node = arguments.get("node", "")
        if not node:
            return [TextContent(type="text", text="Node parameter required for neighbors query.")]
        data = graph.query_neighbors(node, depth=arguments.get("depth", 2))
        if "error" in data:
            result = f"❌ {data['error']}"
            if data.get("suggestions"):
                result += f"\n\nDid you mean: {', '.join(data['suggestions'])}?"
        else:
            lines = [f"# Neighbors of: {data['info'].get('title', node)}", ""]
            for layer in data.get("layers", []):
                lines.append(f"## Depth {layer['depth']} ({layer['count']} nodes)")
                for n in layer["nodes"]:
                    lines.append(f"- {n['direction']} **{n['title']}** ({n['project']}) `{n['type']}`")
                lines.append("")
            result = "\n".join(lines)
    elif query_type == "path":
        source = arguments.get("node", "")
        target = arguments.get("target", "")
        if not source or not target:
            return [TextContent(type="text", text="Both node and target required for path query.")]
        data = graph.find_path(source, target)
        if data.get("found"):
            path_str = " → ".join(p["title"] for p in data["path"])
            result = f"✅ Path found (length: {data['length']})\n\n{path_str}"
        else:
            result = f"❌ {data.get('message', data.get('error', 'No path found'))}"
    elif query_type == "hubs":
        stats = graph.get_stats()
        lines = ["# 🏛️ Hub Pages (Most Connected)", ""]
        for hub in stats.hubs:
            lines.append(f"- **{hub['title']}** ({hub['project']}) — {hub['degree']} connections")
        result = "\n".join(lines)
    elif query_type == "clusters":
        data = graph.get_clusters()
        lines = [f"# 🔮 Knowledge Clusters ({data['total_clusters']} projects)", ""]
        for cluster in data["clusters"]:
            lines.append(f"## {cluster['project']} ({cluster['node_count']} nodes, {cluster['total_connections']} connections)")
            for n in cluster["nodes"]:
                lines.append(f"- **{n['title']}** `{n['type']}` — {n['connections']} links")
            lines.append("")
        result = "\n".join(lines)
    else:
        result = f"Unknown query_type: {query_type}"

    _append_to_log(vault, "query_graph", details=f"type={query_type}")
    return [TextContent(type="text", text=result)]


async def handle_extract_patterns(arguments: dict) -> list[TextContent]:
    from obsidian_bridge.mcp_server import _get_vault_path, _append_to_log, _regenerate_index
    from obsidian_bridge.patterns import PatternExtractor
    vault = _get_vault_path()
    extractor = PatternExtractor(vault)
    project = arguments.get("project")
    generate_rules = arguments.get("generate_rules", False)

    if generate_rules:
        rules = extractor.generate_auto_rules(project)
        _append_to_log(vault, "extract_patterns", details="Generated auto-rules.md")
        _regenerate_index(vault)
        return [TextContent(type="text", text=f"✅ Auto-rules generated:\n\n{rules}")]
    else:
        report = extractor.analyze(project)
        _append_to_log(vault, "extract_patterns", details=f"{report.total_decisions} decisions analyzed")
        return [TextContent(type="text", text=report.to_markdown())]


HANDLERS: dict[str, Callable] = {
    "lint_vault": handle_lint_vault,
    "rebuild_index": handle_rebuild_index,
    "query_graph": handle_query_graph,
    "extract_patterns": handle_extract_patterns,
}
