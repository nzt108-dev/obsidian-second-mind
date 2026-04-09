"""Knowledge Graph — queryable graph built from WikiLinks.

v0.4.0: Builds a NetworkX graph from vault WikiLinks.
Supports neighbor queries, path finding, hub detection, and cluster analysis.
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from obsidian_bridge.parser import scan_vault, WIKILINK_PATTERN_SIMPLE

logger = logging.getLogger(__name__)



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
            links = WIKILINK_PATTERN_SIMPLE.findall(note.raw_content)
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


# ---------------------------------------------------------------------------
# v0.8.0: Temporal Knowledge Graph — Facts with time validity
# ---------------------------------------------------------------------------

@dataclass
class TemporalFact:
    """A fact with temporal validity.

    Example: brieftube uses_auth clerk (valid from 2026-04-05, still valid)
    """
    subject: str          # "brieftube"
    predicate: str        # "uses_auth"
    object: str           # "clerk"
    valid_from: str = ""  # "2026-04-05"
    valid_to: str = ""    # "" = still valid
    source_note: str = "" # path to the note that established this fact
    confidence: float = 1.0  # 0.0-1.0

    @property
    def is_active(self) -> bool:
        """Check if fact is currently valid."""
        if not self.valid_to:
            return True
        from datetime import date as _date
        try:
            return _date.fromisoformat(self.valid_to) >= _date.today()
        except ValueError:
            return True

    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "source_note": self.source_note,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TemporalFact":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class Contradiction:
    """A contradiction between two facts."""
    old_fact: TemporalFact
    new_fact: TemporalFact
    severity: str = "warning"  # "info", "warning", "critical"
    message: str = ""
    auto_resolved: bool = False

    def to_dict(self) -> dict:
        return {
            "old": self.old_fact.to_dict(),
            "new": self.new_fact.to_dict(),
            "severity": self.severity,
            "message": self.message,
            "auto_resolved": self.auto_resolved,
        }


class TemporalKnowledgeGraph:
    """Knowledge graph with temporal facts.

    Extends the base KG with time-aware fact management.
    Facts have validity windows — "what was true when?"

    Storage: facts.json in vault/_graph/ directory.

    Usage:
        tkg = TemporalKnowledgeGraph(vault_path)
        tkg.add_fact("brieftube", "uses_auth", "clerk", source_note="decisions.md")
        tkg.invalidate("brieftube", "uses_auth", "auth0")  # old fact
        facts = tkg.query_entity("brieftube")  # only active facts
        timeline = tkg.timeline("brieftube")  # full chronological history
    """

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self._graph_dir = vault_path / "_graph"
        self._graph_dir.mkdir(parents=True, exist_ok=True)
        self._facts_path = self._graph_dir / "facts.json"
        self._facts: list[TemporalFact] = []
        self._load()

    def _load(self):
        """Load facts from disk."""
        if not self._facts_path.exists():
            self._facts = []
            return

        try:
            import json
            data = json.loads(self._facts_path.read_text(encoding="utf-8"))
            self._facts = [TemporalFact.from_dict(f) for f in data]
            logger.info(f"Loaded {len(self._facts)} temporal facts")
        except Exception as e:
            logger.warning(f"Failed to load facts: {e}")
            self._facts = []

    def _persist(self):
        """Save facts to disk."""
        import json
        data = [f.to_dict() for f in self._facts]
        self._facts_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @property
    def fact_count(self) -> int:
        return len(self._facts)

    @property
    def active_fact_count(self) -> int:
        return sum(1 for f in self._facts if f.is_active)

    def add_fact(
        self,
        subject: str,
        predicate: str,
        obj: str,
        valid_from: str = "",
        source_note: str = "",
        confidence: float = 1.0,
    ) -> tuple[TemporalFact, list[Contradiction]]:
        """Add a temporal fact. Returns (fact, contradictions).

        Automatically checks for contradictions with existing facts.
        """
        from datetime import date as _date

        if not valid_from:
            valid_from = _date.today().isoformat()

        fact = TemporalFact(
            subject=subject.lower(),
            predicate=predicate.lower(),
            object=obj.lower(),
            valid_from=valid_from,
            source_note=source_note,
            confidence=confidence,
        )

        # Check for contradictions
        detector = ContradictionDetector(self)
        contradictions = detector.check(fact)

        # Auto-resolve: if new fact contradicts old ones, invalidate the old ones
        for c in contradictions:
            if c.old_fact.is_active:
                self.invalidate(
                    c.old_fact.subject,
                    c.old_fact.predicate,
                    c.old_fact.object,
                    ended=valid_from,
                )
                c.auto_resolved = True

        self._facts.append(fact)
        self._persist()

        logger.info(
            f"Fact added: {subject} {predicate} {obj} "
            f"(from={valid_from}, contradictions={len(contradictions)})"
        )

        return fact, contradictions

    def invalidate(
        self,
        subject: str,
        predicate: str,
        obj: str,
        ended: str = "",
    ) -> bool:
        """Mark a fact as no longer valid. Returns True if found and invalidated."""
        from datetime import date as _date

        if not ended:
            ended = _date.today().isoformat()

        subject = subject.lower()
        predicate = predicate.lower()
        obj = obj.lower()

        found = False
        for fact in self._facts:
            if (fact.subject == subject
                    and fact.predicate == predicate
                    and fact.object == obj
                    and not fact.valid_to):
                fact.valid_to = ended
                found = True
                logger.info(f"Fact invalidated: {subject} {predicate} {obj}")

        if found:
            self._persist()

        return found

    def query_entity(self, entity: str, as_of: str = "") -> list[TemporalFact]:
        """Query facts about entity, optionally at a specific date.

        Returns only facts valid at the given date (or today if not specified).
        """
        from datetime import date as _date

        if not as_of:
            as_of = _date.today().isoformat()

        entity = entity.lower()
        results = []

        for fact in self._facts:
            if fact.subject != entity and fact.object != entity:
                continue

            # Check temporal validity
            if fact.valid_from and fact.valid_from > as_of:
                continue  # Not yet valid at this date
            if fact.valid_to and fact.valid_to < as_of:
                continue  # Already expired at this date

            results.append(fact)

        return results

    def timeline(self, entity: str) -> list[TemporalFact]:
        """Get chronological history of ALL facts about an entity (including expired)."""
        entity = entity.lower()
        facts = [
            f for f in self._facts
            if f.subject == entity or f.object == entity
        ]
        return sorted(facts, key=lambda f: f.valid_from or "0000")

    def get_all_active(self) -> list[TemporalFact]:
        """Get all currently active facts."""
        return [f for f in self._facts if f.is_active]

    def search_facts(self, query: str) -> list[TemporalFact]:
        """Search facts by keyword match on subject/predicate/object."""
        query = query.lower()
        return [
            f for f in self._facts
            if query in f.subject or query in f.predicate or query in f.object
        ]

    def get_stats(self) -> dict:
        """Get temporal KG statistics."""
        subjects = set()
        predicates = set()
        for f in self._facts:
            subjects.add(f.subject)
            predicates.add(f.predicate)

        return {
            "total_facts": len(self._facts),
            "active_facts": self.active_fact_count,
            "expired_facts": len(self._facts) - self.active_fact_count,
            "unique_subjects": len(subjects),
            "unique_predicates": len(predicates),
            "subjects": sorted(subjects),
            "predicates": sorted(predicates),
        }

    def to_markdown(self) -> str:
        """Export temporal KG as markdown."""
        stats = self.get_stats()
        lines = [
            "# ⏱️ Temporal Knowledge Graph",
            "",
            f"**Total facts**: {stats['total_facts']}",
            f"**Active**: {stats['active_facts']} | "
            f"**Expired**: {stats['expired_facts']}",
            f"**Subjects**: {', '.join(stats['subjects'][:10])}",
            f"**Predicates**: {', '.join(stats['predicates'][:10])}",
            "",
        ]

        # Show active facts grouped by subject
        active = self.get_all_active()
        if active:
            lines.append("## Active Facts")
            lines.append("")
            by_subject: dict[str, list[TemporalFact]] = {}
            for f in active:
                by_subject.setdefault(f.subject, []).append(f)

            for subject, facts in sorted(by_subject.items()):
                lines.append(f"### {subject}")
                for f in facts:
                    lines.append(
                        f"- {f.predicate}: **{f.object}** "
                        f"(since {f.valid_from})"
                    )
                lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# v0.8.0: Contradiction Detection
# ---------------------------------------------------------------------------

class ContradictionDetector:
    """Check new facts against existing knowledge graph for contradictions.

    Detects:
    - Same subject+predicate, different object (e.g. "uses PostgreSQL" vs "uses SQLite")
    - Overlapping temporal ranges for mutually exclusive facts
    """

    def __init__(self, tkg: TemporalKnowledgeGraph):
        self.tkg = tkg

    def check(self, new_fact: TemporalFact) -> list[Contradiction]:
        """Check if a new fact contradicts existing active facts."""
        contradictions = []

        for old in self.tkg._facts:
            if not old.is_active:
                continue

            # Same subject + predicate but different object = contradiction
            if (old.subject == new_fact.subject
                    and old.predicate == new_fact.predicate
                    and old.object != new_fact.object):

                severity = self._assess_severity(old, new_fact)
                contradictions.append(Contradiction(
                    old_fact=old,
                    new_fact=new_fact,
                    severity=severity,
                    message=(
                        f"Conflict: {old.subject} {old.predicate} "
                        f"was '{old.object}' (since {old.valid_from}), "
                        f"now '{new_fact.object}'"
                    ),
                ))

        return contradictions

    def check_all(self) -> list[Contradiction]:
        """Find ALL contradictions in the knowledge graph."""
        contradictions = []
        active = self.tkg.get_all_active()

        checked_pairs: set[tuple[int, int]] = set()
        for i, a in enumerate(active):
            for j, b in enumerate(active):
                if i >= j:
                    continue
                pair = (i, j)
                if pair in checked_pairs:
                    continue
                checked_pairs.add(pair)

                if (a.subject == b.subject
                        and a.predicate == b.predicate
                        and a.object != b.object):
                    severity = self._assess_severity(a, b)
                    contradictions.append(Contradiction(
                        old_fact=a,
                        new_fact=b,
                        severity=severity,
                        message=(
                            f"Conflict: {a.subject} {a.predicate} = "
                            f"'{a.object}' vs '{b.object}'"
                        ),
                    ))

        return contradictions

    @staticmethod
    def _assess_severity(old: TemporalFact, new: TemporalFact) -> str:
        """Assess contradiction severity."""
        # High confidence facts contradicting = critical
        if old.confidence >= 0.9 and new.confidence >= 0.9:
            return "critical"
        # Tech stack changes = warning
        tech_predicates = {"uses", "uses_auth", "uses_db", "uses_framework", "deploys_to"}
        if old.predicate in tech_predicates:
            return "warning"
        return "info"

    def to_markdown(self, contradictions: list[Contradiction] | None = None) -> str:
        """Format contradictions as markdown report."""
        if contradictions is None:
            contradictions = self.check_all()

        if not contradictions:
            return "✅ No contradictions found in the knowledge graph."

        lines = [
            "# 🔴 Contradiction Report",
            "",
            f"**Found**: {len(contradictions)} contradictions",
            "",
        ]

        # Group by severity
        by_severity: dict[str, list[Contradiction]] = {}
        for c in contradictions:
            by_severity.setdefault(c.severity, []).append(c)

        severity_icons = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
        for severity in ["critical", "warning", "info"]:
            items = by_severity.get(severity, [])
            if not items:
                continue
            icon = severity_icons.get(severity, "•")
            lines.append(f"## {icon} {severity.capitalize()} ({len(items)})")
            lines.append("")
            for c in items:
                resolved = " ✅ auto-resolved" if c.auto_resolved else ""
                lines.append(f"- {c.message}{resolved}")
                if c.old_fact.source_note:
                    lines.append(f"  Source: `{c.old_fact.source_note}`")
            lines.append("")

        return "\n".join(lines)

