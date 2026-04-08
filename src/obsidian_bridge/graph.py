"""Knowledge Graph — queryable graph built from WikiLinks.

v0.4.0: Builds a NetworkX graph from vault WikiLinks.
Supports neighbor queries, path finding, hub detection, and cluster analysis.
"""
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from obsidian_bridge.parser import scan_vault

logger = logging.getLogger(__name__)

WIKILINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


@dataclass
class GraphStats:
    """Graph statistics."""
    nodes: int = 0
    edges: int = 0
    density: float = 0.0
    components: int = 0
    avg_degree: float = 0.0
    hubs: list[dict] = field(default_factory=list)


class KnowledgeGraph:
    """Queryable knowledge graph built from vault WikiLinks."""

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self._nodes: dict[str, dict] = {}  # stem -> {path, project, type, title}
        self._edges: list[tuple[str, str]] = []  # (source_stem, target_stem)
        self._adjacency: dict[str, set[str]] = {}  # stem -> set of connected stems
        self._reverse_adjacency: dict[str, set[str]] = {}  # stem -> set of inbound stems
        self._built = False

    def build(self):
        """Build the graph from vault WikiLinks."""
        notes = scan_vault(self.vault_path)

        # Register all nodes
        all_stems: set[str] = set()
        for note in notes:
            stem = note.path.stem.lower()
            all_stems.add(stem)
            self._nodes[stem] = {
                "path": str(note.path),
                "project": note.project,
                "type": note.note_type,
                "title": note.title,
                "tags": [str(t) for t in note.tags],
            }
            self._adjacency.setdefault(stem, set())
            self._reverse_adjacency.setdefault(stem, set())

        # Build edges from WikiLinks
        for note in notes:
            source = note.path.stem.lower()
            links = WIKILINK_PATTERN.findall(note.raw_content)
            for link_target in links:
                parts = link_target.split("/")
                target = parts[-1].lower().replace(".md", "")
                if target in all_stems and target != source:
                    self._edges.append((source, target))
                    self._adjacency[source].add(target)
                    self._reverse_adjacency.setdefault(target, set()).add(source)

        self._built = True
        logger.info(f"Knowledge graph built: {len(self._nodes)} nodes, {len(self._edges)} edges")

    def get_stats(self) -> GraphStats:
        """Get graph statistics."""
        if not self._built:
            self.build()

        n = len(self._nodes)
        e = len(self._edges)
        max_edges = n * (n - 1) if n > 1 else 1

        # Find connected components (BFS)
        visited: set[str] = set()
        components = 0
        for node in self._nodes:
            if node not in visited:
                components += 1
                queue = [node]
                while queue:
                    current = queue.pop(0)
                    if current in visited:
                        continue
                    visited.add(current)
                    neighbors = self._adjacency.get(current, set()) | self._reverse_adjacency.get(current, set())
                    queue.extend(neighbors - visited)

        # Hub detection (top by degree)
        degrees = {
            node: len(self._adjacency.get(node, set())) + len(self._reverse_adjacency.get(node, set()))
            for node in self._nodes
        }
        top_hubs = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:10]
        hubs = [
            {"node": stem, "degree": deg, "title": self._nodes[stem]["title"], "project": self._nodes[stem]["project"]}
            for stem, deg in top_hubs if deg > 0
        ]

        return GraphStats(
            nodes=n,
            edges=e,
            density=round(e / max_edges, 4) if max_edges > 0 else 0,
            components=components,
            avg_degree=round(sum(degrees.values()) / n, 2) if n > 0 else 0,
            hubs=hubs,
        )

    def query_neighbors(self, node: str, depth: int = 1) -> dict:
        """Get neighbors of a node up to N hops."""
        if not self._built:
            self.build()

        node_lower = node.lower()
        # Try to find the node by stem or partial match
        matched = self._find_node(node_lower)
        if not matched:
            return {"error": f"Node '{node}' not found", "suggestions": self._suggest_nodes(node_lower)}

        result = {"node": matched, "info": self._nodes.get(matched, {}), "layers": []}

        visited = {matched}
        current_layer = {matched}

        for d in range(depth):
            next_layer: set[str] = set()
            for n in current_layer:
                outbound = self._adjacency.get(n, set())
                inbound = self._reverse_adjacency.get(n, set())
                next_layer |= (outbound | inbound) - visited

            if not next_layer:
                break

            layer_info = []
            for neighbor in sorted(next_layer):
                info = self._nodes.get(neighbor, {})
                direction = []
                if neighbor in self._adjacency.get(matched, set()):
                    direction.append("→")
                if neighbor in self._reverse_adjacency.get(matched, set()):
                    direction.append("←")
                layer_info.append({
                    "node": neighbor,
                    "title": info.get("title", neighbor),
                    "project": info.get("project", ""),
                    "type": info.get("type", ""),
                    "direction": " ".join(direction) if d == 0 else "indirect",
                })

            result["layers"].append({"depth": d + 1, "count": len(layer_info), "nodes": layer_info})
            visited |= next_layer
            current_layer = next_layer

        return result

    def find_path(self, source: str, target: str) -> dict:
        """Find shortest path between two nodes (BFS)."""
        if not self._built:
            self.build()

        src = self._find_node(source.lower())
        tgt = self._find_node(target.lower())

        if not src:
            return {"error": f"Source '{source}' not found"}
        if not tgt:
            return {"error": f"Target '{target}' not found"}

        # BFS
        queue = [(src, [src])]
        visited = {src}

        while queue:
            current, path = queue.pop(0)
            if current == tgt:
                return {
                    "found": True,
                    "length": len(path) - 1,
                    "path": [
                        {"node": n, "title": self._nodes.get(n, {}).get("title", n)}
                        for n in path
                    ],
                }

            neighbors = self._adjacency.get(current, set()) | self._reverse_adjacency.get(current, set())
            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return {"found": False, "message": f"No path between '{source}' and '{target}'"}

    def get_clusters(self) -> dict:
        """Find clusters (connected components) grouped by project."""
        if not self._built:
            self.build()

        # Group by project
        project_nodes: dict[str, list[dict]] = {}
        for stem, info in self._nodes.items():
            proj = info.get("project", "unknown")
            project_nodes.setdefault(proj, []).append({
                "node": stem,
                "title": info["title"],
                "type": info["type"],
                "connections": len(self._adjacency.get(stem, set())) + len(self._reverse_adjacency.get(stem, set())),
            })

        # Sort within clusters by connections
        clusters = []
        for project, nodes in sorted(project_nodes.items()):
            nodes.sort(key=lambda x: x["connections"], reverse=True)
            total_connections = sum(n["connections"] for n in nodes)
            clusters.append({
                "project": project,
                "node_count": len(nodes),
                "total_connections": total_connections,
                "nodes": nodes[:5],  # Top 5 per cluster
            })

        clusters.sort(key=lambda c: c["total_connections"], reverse=True)
        return {"clusters": clusters, "total_clusters": len(clusters)}

    def _find_node(self, query: str) -> Optional[str]:
        """Find a node by exact stem match or partial match."""
        if query in self._nodes:
            return query
        # Partial match
        for stem in self._nodes:
            if query in stem or stem in query:
                return stem
        return None

    def _suggest_nodes(self, query: str, limit: int = 5) -> list[str]:
        """Suggest similar node names."""
        scored = []
        query_tokens = set(query.split("-"))
        for stem in self._nodes:
            stem_tokens = set(stem.split("-"))
            overlap = len(query_tokens & stem_tokens)
            if overlap > 0:
                scored.append((stem, overlap))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scored[:limit]]

    def to_markdown(self) -> str:
        """Export graph stats as markdown."""
        stats = self.get_stats()
        lines = [
            "# 🕸️ Knowledge Graph Stats",
            "",
            f"- **Nodes**: {stats.nodes}",
            f"- **Edges**: {stats.edges}",
            f"- **Density**: {stats.density}",
            f"- **Components**: {stats.components}",
            f"- **Avg Degree**: {stats.avg_degree}",
            "",
            "## Top Hubs",
            "",
        ]
        for hub in stats.hubs:
            lines.append(f"- **{hub['title']}** ({hub['project']}) — {hub['degree']} connections")

        return "\n".join(lines)
