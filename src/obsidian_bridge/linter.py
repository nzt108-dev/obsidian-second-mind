"""Vault Linter — health-check for the wiki.

Implements the 'lint' operation from Karpathy's LLM Wiki pattern.
Finds: orphan pages, stale notes, broken WikiLinks, missing concept pages,
empty sections, and incomplete frontmatter.
"""
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from obsidian_bridge.parser import scan_vault, WIKILINK_PATTERN_SIMPLE


TODO_PATTERN = re.compile(r"(?:TODO|FIXME|HACK|XXX|WIP)\b", re.IGNORECASE)
CONCEPT_MENTION_PATTERN = re.compile(
    r"\b(Supabase|ChromaDB|Flutter|Next\.js|Firebase|Vercel|Docker|Redis|PostgreSQL"
    r"|OpenAI|Claude|Stripe|Telegram|FastAPI|SQLite|Prisma|Turso|LibSQL"
    r"|BM25|RRF|MMR|RAG|MCP|GraphQL|REST API|WebSocket|OAuth|JWT"
    r"|React|TypeScript|Python|Dart|SwiftUI)\b",
    re.IGNORECASE,
)


@dataclass
class LintIssue:
    """A single lint issue found in the vault."""

    severity: str  # critical, warning, info
    category: str  # orphan, stale, broken_link, missing_concept, empty_section, frontmatter
    file: str  # relative path
    message: str
    suggestion: str = ""


@dataclass
class LintReport:
    """Complete lint report for the vault."""

    issues: list[LintIssue] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "info")

    def to_markdown(self) -> str:
        """Format report as markdown."""
        lines = ["# 🔍 Vault Lint Report", ""]

        # Summary
        total = len(self.issues)
        lines.append(f"**Total issues: {total}** — "
                      f"🔴 Critical: {self.critical_count} | "
                      f"🟡 Warning: {self.warning_count} | "
                      f"🔵 Info: {self.info_count}")
        lines.append("")

        if not self.issues:
            lines.append("✅ No issues found. Vault is healthy!")
            return "\n".join(lines)

        # Group by category
        categories = {}
        for issue in self.issues:
            categories.setdefault(issue.category, []).append(issue)

        category_labels = {
            "orphan": "🔗 Orphan Pages (no inbound links)",
            "stale": "📅 Stale Notes",
            "broken_link": "💔 Broken WikiLinks",
            "missing_concept": "📝 Missing Concept Pages",
            "empty_section": "⚠️ Empty/TODO Sections",
            "frontmatter": "📋 Incomplete Frontmatter",
        }

        for cat, issues in categories.items():
            label = category_labels.get(cat, cat)
            lines.append(f"## {label} ({len(issues)})")
            lines.append("")
            for issue in issues:
                icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(issue.severity, "⚪")
                lines.append(f"- {icon} **{issue.file}** — {issue.message}")
                if issue.suggestion:
                    lines.append(f"  - 💡 {issue.suggestion}")
            lines.append("")

        # Stats
        if self.stats:
            lines.append("## 📊 Stats")
            for k, v in self.stats.items():
                lines.append(f"- {k}: {v}")

        return "\n".join(lines)


class VaultLinter:
    """Lint the vault for health issues."""

    def __init__(self, vault_path: Path, stale_days: int = 90):
        self.vault_path = vault_path
        self.stale_days = stale_days

    def lint(self, project: Optional[str] = None) -> LintReport:
        """Run all lint checks. Optionally filter by project."""
        report = LintReport()

        # Scan all notes
        all_notes = scan_vault(self.vault_path)
        if project:
            all_notes = [n for n in all_notes if n.project == project]

        if not all_notes:
            report.stats["total_notes"] = 0
            return report

        report.stats["total_notes"] = len(all_notes)
        report.stats["total_projects"] = len(set(n.project for n in all_notes if n.project))

        # Run checks
        report.issues.extend(self._find_orphan_pages(all_notes))
        report.issues.extend(self._find_stale_notes(all_notes))
        report.issues.extend(self._find_broken_wikilinks(all_notes))
        report.issues.extend(self._find_missing_concepts(all_notes))
        report.issues.extend(self._find_empty_sections(all_notes))
        report.issues.extend(self._check_frontmatter(all_notes))

        # Sort: critical first, then warning, then info
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        report.issues.sort(key=lambda i: severity_order.get(i.severity, 99))

        return report

    def _find_orphan_pages(self, notes: list) -> list[LintIssue]:
        """Find pages with zero inbound WikiLinks."""
        issues = []

        # Build a map of all note filenames (stem) -> path
        note_stems = {}
        for note in notes:
            stem = note.path.stem
            note_stems[stem.lower()] = str(note.path)

        # Count inbound links for each note
        inbound_count: Counter = Counter()
        for note in notes:
            links = WIKILINK_PATTERN_SIMPLE.findall(note.raw_content)
            for link_target in links:
                # Link target might be "project/note" or just "note"
                target_parts = link_target.split("/")
                target_stem = target_parts[-1].lower().replace(".md", "")
                if target_stem in note_stems:
                    inbound_count[note_stems[target_stem]] += 1

        # Find orphans (skip global rules and index/log files)
        skip_stems = {"index", "log", "wiki-schema"}
        for note in notes:
            stem = note.path.stem.lower()
            if stem in skip_stems:
                continue
            path_str = str(note.path)
            if path_str.startswith("_global"):
                continue  # Global rules are special
            if inbound_count.get(path_str, 0) == 0:
                issues.append(LintIssue(
                    severity="info",
                    category="orphan",
                    file=path_str,
                    message="No inbound WikiLinks — this page is isolated",
                    suggestion=f"Add [[{note.path.stem}]] link from related notes",
                ))

        return issues

    def _find_stale_notes(self, notes: list) -> list[LintIssue]:
        """Find notes not updated for N days."""
        issues = []
        cutoff = date.today() - timedelta(days=self.stale_days)

        for note in notes:
            updated = note.updated or note.created
            if updated and isinstance(updated, date) and updated < cutoff:
                days_ago = (date.today() - updated).days
                issues.append(LintIssue(
                    severity="warning",
                    category="stale",
                    file=str(note.path),
                    message=f"Not updated for {days_ago} days (since {updated})",
                    suggestion="Review and update, or mark as archived",
                ))

        return issues

    def _find_broken_wikilinks(self, notes: list) -> list[LintIssue]:
        """Find WikiLinks that point to non-existent files."""
        issues = []

        # Build set of all existing note stems
        existing_stems = set()
        for note in notes:
            existing_stems.add(note.path.stem.lower())

        for note in notes:
            links = WIKILINK_PATTERN_SIMPLE.findall(note.raw_content)
            for link_target in links:
                target_parts = link_target.split("/")
                target_stem = target_parts[-1].lower().replace(".md", "")
                if target_stem not in existing_stems:
                    issues.append(LintIssue(
                        severity="warning",
                        category="broken_link",
                        file=str(note.path),
                        message=f"Broken WikiLink: [[{link_target}]] — target not found",
                        suggestion="Create the page or fix the link",
                    ))

        return issues

    def _find_missing_concepts(self, notes: list) -> list[LintIssue]:
        """Find frequently mentioned concepts that lack their own page."""
        issues = []

        # Count concept mentions across all notes
        concept_counts: Counter = Counter()
        for note in notes:
            matches = CONCEPT_MENTION_PATTERN.findall(note.content)
            for match in matches:
                concept_counts[match.lower()] += 1

        # Check which concepts have their own page
        existing_stems = {note.path.stem.lower() for note in notes}
        existing_titles = {note.title.lower() for note in notes}

        for concept, count in concept_counts.most_common(20):
            if count < 3:
                break
            concept_lower = concept.lower()
            # Check if concept has its own page
            has_page = (
                concept_lower in existing_stems
                or f"concept-{concept_lower}" in existing_stems
                or any(concept_lower in t for t in existing_titles)
            )
            if not has_page:
                issues.append(LintIssue(
                    severity="info",
                    category="missing_concept",
                    file="(vault-wide)",
                    message=f'"{concept}" mentioned {count} times but has no concept page',
                    suggestion=f"Create a concept page: concept-{concept_lower}.md",
                ))

        return issues

    def _find_empty_sections(self, notes: list) -> list[LintIssue]:
        """Find notes with TODO/FIXME markers or empty sections."""
        issues = []

        for note in notes:
            todos = TODO_PATTERN.findall(note.content)
            if todos:
                issues.append(LintIssue(
                    severity="warning",
                    category="empty_section",
                    file=str(note.path),
                    message=f"Contains {len(todos)} TODO/FIXME markers",
                    suggestion="Complete or remove TODO items",
                ))

            # Check for empty headings (heading followed by another heading or end)
            lines = note.content.split("\n")
            for i, line in enumerate(lines):
                if line.startswith("#"):
                    # Check if next non-empty line is also a heading or EOF
                    next_content = ""
                    for j in range(i + 1, min(i + 5, len(lines))):
                        stripped = lines[j].strip()
                        if stripped:
                            next_content = stripped
                            break
                    if not next_content or next_content.startswith("#"):
                        heading = line.lstrip("#").strip()
                        if heading:  # Skip empty heading markers
                            issues.append(LintIssue(
                                severity="info",
                                category="empty_section",
                                file=str(note.path),
                                message=f'Empty section: "{heading}"',
                                suggestion="Add content or remove the heading",
                            ))

        return issues

    def _check_frontmatter(self, notes: list) -> list[LintIssue]:
        """Find notes with missing or incomplete frontmatter."""
        issues = []
        required_fields = {"project", "type"}
        recommended_fields = {"tags", "created", "updated"}

        for note in notes:
            if not note.metadata:
                issues.append(LintIssue(
                    severity="warning",
                    category="frontmatter",
                    file=str(note.path),
                    message="Missing frontmatter entirely",
                    suggestion="Add YAML frontmatter with project, type, tags",
                ))
                continue

            missing_required = required_fields - set(note.metadata.keys())
            if missing_required:
                issues.append(LintIssue(
                    severity="warning",
                    category="frontmatter",
                    file=str(note.path),
                    message=f"Missing required fields: {', '.join(sorted(missing_required))}",
                    suggestion="Add missing frontmatter fields",
                ))

            missing_recommended = recommended_fields - set(note.metadata.keys())
            if missing_recommended:
                issues.append(LintIssue(
                    severity="info",
                    category="frontmatter",
                    file=str(note.path),
                    message=f"Missing recommended fields: {', '.join(sorted(missing_recommended))}",
                ))

        return issues
