"""Cascade Ingest Pipeline for Obsidian Second Mind.

v0.7.0: One source cascades into multiple wiki updates.
Inspired by Karpathy: "A single source might touch 10-15 wiki pages."

No LLM required — uses semantic search + regex entity extraction.
When called by Gemini in IDE, the LLM can enrich the process.
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import frontmatter as fm_lib

from obsidian_bridge.parser import get_projects, parse_note, WIKILINK_PATTERN_SIMPLE

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class IngestSource:
    """Input for the ingest pipeline."""
    content: str
    source_type: str = "text"  # "text", "url", "note"
    project: str = "inbox"
    title: str = ""
    url: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class IngestAction:
    """A single action performed during ingest."""
    action: str  # "created", "updated", "cross-referenced"
    path: str
    detail: str = ""


@dataclass
class IngestReport:
    """Results of a cascade ingest operation."""
    primary_note: str = ""
    actions: list[IngestAction] = field(default_factory=list)
    entities_found: list[str] = field(default_factory=list)
    cross_references_added: int = 0

    def to_markdown(self) -> str:
        lines = [
            "# 📥 Ingest Report",
            "",
            f"**Primary**: `{self.primary_note}`",
            f"**Actions**: {len(self.actions)}",
            f"**Entities**: {len(self.entities_found)}",
            f"**Cross-refs**: {self.cross_references_added}",
            "",
        ]

        if self.actions:
            lines.append("## Actions")
            for a in self.actions:
                icon = {"created": "✅", "updated": "📝", "cross-referenced": "🔗"}.get(
                    a.action, "•"
                )
                lines.append(f"{icon} **{a.action}**: `{a.path}` — {a.detail}")

        if self.entities_found:
            lines.append("")
            lines.append(f"## Entities: {', '.join(self.entities_found[:20])}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entity Extraction (regex-based, no LLM)
# ---------------------------------------------------------------------------

# Known tech terms — import canonical list from fact_extractor
try:
    from obsidian_bridge.fact_extractor import KNOWN_TECH as TECH_ENTITIES
except ImportError:
    TECH_ENTITIES = set()  # fallback if fact_extractor not available

# Pattern for WikiLink references [[Page Name]]
WIKILINK_PATTERN = WIKILINK_PATTERN_SIMPLE

# Pattern for project slugs (lowercase-with-dashes)
PROJECT_SLUG_PATTERN = re.compile(r"\b([a-z][a-z0-9\-]{2,30})\b")


def extract_entities(text: str, known_projects: list[str] | None = None) -> list[str]:
    """Extract entities from text using regex + known dictionaries.

    Returns unique entity names found in the text.
    No LLM needed — uses curated tech dictionary + vault project names.
    """
    text_lower = text.lower()
    entities = set()

    # 1. Match known tech terms
    for tech in TECH_ENTITIES:
        if tech in text_lower:
            entities.add(tech)

    # 2. Match known project names
    if known_projects:
        for project in known_projects:
            if project.lower() in text_lower:
                entities.add(project)

    # 3. Extract WikiLinks
    for match in WIKILINK_PATTERN.finditer(text):
        entities.add(match.group(1).strip())

    return sorted(entities)


# ---------------------------------------------------------------------------
# Cascade Ingest Pipeline
# ---------------------------------------------------------------------------

class IngestPipeline:
    """Cascade ingest: one source → many wiki updates.

    Pipeline steps:
    1. Create primary note from source
    2. Search for related existing pages (semantic search)
    3. Add cross-references to related pages
    4. Extract entities, check for missing concept pages
    5. Auto-update index.md + log.md
    """

    def __init__(self, vault_path: Path, index=None):
        self.vault = vault_path
        self.index = index  # VaultIndex (optional, for semantic search)

    def ingest(self, source: IngestSource) -> IngestReport:
        """Process a source and cascade updates across the wiki.

        Can be called without VaultIndex — will skip semantic search step.
        """
        report = IngestReport()
        today = date.today().isoformat()

        # --- Step 1: Create the primary note ---
        primary_path = self._create_primary_note(source, today)
        report.primary_note = str(primary_path.relative_to(self.vault))
        report.actions.append(IngestAction(
            action="created",
            path=report.primary_note,
            detail=f"Primary {source.source_type} note",
        ))

        # --- Step 2: Find related pages (semantic search) ---
        related = []
        if self.index and hasattr(self.index, "search"):
            try:
                search_text = source.title or source.content[:200]
                related = self.index.search(search_text, n_results=10, project=source.project)
                # Filter to high relevance only
                related = [r for r in related if r.get("score", 0) > 0.3]
            except Exception as e:
                logger.warning(f"Semantic search during ingest failed: {e}")

        # --- Step 3: Add cross-references to related pages ---
        for match in related[:5]:  # Limit to top-5 most relevant
            updated = self._add_cross_reference(
                target_source=match["source"],
                ref_title=source.title or "Untitled",
                ref_path=report.primary_note,
                today=today,
            )
            if updated:
                report.cross_references_added += 1
                report.actions.append(IngestAction(
                    action="cross-referenced",
                    path=match["source"],
                    detail=f"Added reference to {report.primary_note}",
                ))

        # --- Step 4: Extract entities, create missing concept pages ---
        known_projects = get_projects(self.vault)
        entities = extract_entities(source.content, known_projects)
        report.entities_found = entities

        for entity in entities:
            # Check if a concept page exists for this entity
            if not self._concept_exists(entity):
                concept_path = self._create_concept_stub(entity, source, today)
                if concept_path:
                    report.actions.append(IngestAction(
                        action="created",
                        path=str(concept_path.relative_to(self.vault)),
                        detail=f"Concept stub for '{entity}'",
                    ))

        # --- Step 5: Log ---
        self._log_ingest(source, report)

        return report

    def _create_primary_note(self, source: IngestSource, today: str) -> Path:
        """Create the main note from source."""
        project_dir = self.vault / source.project
        project_dir.mkdir(parents=True, exist_ok=True)

        title = source.title or source.content[:80].rstrip(".")
        slug = re.sub(r"[^\w\s-]", "", title.lower())
        slug = re.sub(r"[\s_]+", "-", slug).strip("-")[:60] or "untitled"
        filename = f"{slug}.md"
        file_path = project_dir / filename

        # Ensure uniqueness
        counter = 1
        while file_path.exists():
            file_path = project_dir / f"{slug}-{counter}.md"
            counter += 1

        # Determine note type
        note_type = "research" if source.source_type == "url" else "note"

        # Build content
        content_parts = []
        if source.url:
            content_parts.append(f"**Source**: [{source.url}]({source.url})\n")
        content_parts.append(source.content)
        content_parts.append(f"\n> 📥 Ingested via cascade pipeline | {today}")

        tags = list(set(["ingest"] + source.tags))
        tags_yaml = "".join(f'  - "{tag}"\n' for tag in tags)

        fm_content = (
            f"---\n"
            f"project: {source.project}\n"
            f"type: {note_type}\n"
            f"tags:\n"
            f"{tags_yaml}"
            f"priority: medium\n"
            f"created: {today}\n"
            f"updated: {today}\n"
            f"source_type: {source.source_type}\n"
            f"---\n\n"
            f"# {title}\n\n"
            + "\n".join(content_parts) + "\n"
        )

        file_path.write_text(fm_content, encoding="utf-8")
        logger.info(f"Primary note created: {file_path.relative_to(self.vault)}")

        # Re-index if index available
        if self.index:
            try:
                note = parse_note(file_path, self.vault)
                if note:
                    self.index.index_notes([note])
            except Exception as e:
                logger.warning(f"Re-indexing failed: {e}")

        return file_path

    def _add_cross_reference(
        self,
        target_source: str,
        ref_title: str,
        ref_path: str,
        today: str,
    ) -> bool:
        """Append a cross-reference to an existing note."""
        target_path = self.vault / target_source
        if not target_path.exists():
            return False

        try:
            raw = target_path.read_text(encoding="utf-8")

            # Check if reference already exists
            if ref_path in raw:
                return False

            # Append cross-reference section
            ref_block = (
                f"\n\n---\n"
                f"### 🔗 Related (auto-linked {today})\n"
                f"- [[{ref_title}]] — see `{ref_path}`\n"
            )

            # Use frontmatter lib to preserve metadata
            post = fm_lib.loads(raw)
            post.content = post.content.rstrip() + ref_block
            post.metadata["updated"] = today
            target_path.write_text(fm_lib.dumps(post), encoding="utf-8")

            logger.info(f"Cross-ref added: {target_source} → {ref_path}")
            return True
        except Exception as e:
            logger.warning(f"Failed to add cross-ref to {target_source}: {e}")
            return False

    def _concept_exists(self, entity: str) -> bool:
        """Check if a concept page exists for this entity."""
        slug = entity.lower().replace(" ", "-")

        # Check all project dirs + _global
        for d in self.vault.iterdir():
            if not d.is_dir() or d.name.startswith("."):
                continue
            # Check for exact filename match
            for pattern in [f"{slug}.md", f"concept-{slug}.md", f"{slug}-concept.md"]:
                if (d / pattern).exists():
                    return True
            # Check if mentioned in any concept-type note
            for md in d.glob("*.md"):
                if slug in md.stem.lower():
                    return True

        return False

    def _create_concept_stub(
        self,
        entity: str,
        source: IngestSource,
        today: str,
    ) -> Path | None:
        """Create a minimal concept page for a new entity.

        Only creates for entities that seem significant (tech terms, projects).
        Returns None if entity is too generic.
        """
        # Only create concept stubs for tech entities or project names
        entity_lower = entity.lower()
        if entity_lower not in TECH_ENTITIES and len(entity) < 3:
            return None

        # Don't create concepts for things already in project dirs
        if entity_lower in [p.lower() for p in get_projects(self.vault)]:
            return None

        # Create in _global/concepts/
        concepts_dir = self.vault / "_global" / "concepts"
        concepts_dir.mkdir(parents=True, exist_ok=True)

        slug = entity_lower.replace(" ", "-")
        file_path = concepts_dir / f"{slug}.md"

        if file_path.exists():
            return None  # Already exists

        fm_content = (
            f"---\n"
            f"project: _global\n"
            f"type: concept\n"
            f"tags:\n"
            f'  - "concept"\n'
            f'  - "auto-generated"\n'
            f"priority: low\n"
            f"created: {today}\n"
            f"updated: {today}\n"
            f"---\n\n"
            f"# {entity}\n\n"
            f"(Auto-generated concept stub — enrich during next session)\n\n"
            f"## References\n"
            f"- First mentioned in: `{source.project}/{source.title or 'untitled'}`\n"
        )

        file_path.write_text(fm_content, encoding="utf-8")
        logger.info(f"Concept stub created: {file_path.relative_to(self.vault)}")
        return file_path

    def _log_ingest(self, source: IngestSource, report: IngestReport):
        """Log ingest operation to vault log."""
        log_path = self.vault / "log.md"
        if not log_path.exists():
            log_path.write_text(
                "# 📋 Vault Log\n> Chronological record of vault operations.\n\n",
                encoding="utf-8",
            )

        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        entry = (
            f"## [{now}] cascade_ingest | {source.project} | {source.title or 'untitled'}\n"
            f"Type: {source.source_type} | Actions: {len(report.actions)} | "
            f"Entities: {len(report.entities_found)} | "
            f"Cross-refs: {report.cross_references_added}\n\n"
        )

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
