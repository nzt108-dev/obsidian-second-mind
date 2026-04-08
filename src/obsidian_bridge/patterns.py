"""Pattern Extractor — analyze decision outcomes and generate auto-rules.

v0.4.0: Scans decision notes for Outcome sections, classifies results,
and extracts patterns (success best-practices, failure anti-patterns).
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from obsidian_bridge.parser import scan_vault

logger = logging.getLogger(__name__)

OUTCOME_PATTERN = re.compile(
    r"##\s*Outcome.*?\n(.*?)(?=\n##\s|\Z)",
    re.DOTALL | re.IGNORECASE,
)
STATUS_PATTERN = re.compile(
    r"\*?\*?Status\*?\*?\s*[:：]\s*(success|partial|failed|unknown)",
    re.IGNORECASE,
)
LESSONS_PATTERN = re.compile(
    r"\*?\*?Lessons?\s*learned?\*?\*?\s*[:：]\s*(.*?)(?=\n\*?\*?|\Z)",
    re.DOTALL | re.IGNORECASE,
)


@dataclass
class DecisionOutcome:
    """A parsed decision outcome."""
    project: str
    title: str
    path: str
    status: str  # success, partial, failed, unknown
    outcome_text: str
    lessons: str = ""
    date: Optional[str] = None


@dataclass
class PatternReport:
    """Extracted patterns from decision outcomes."""
    total_decisions: int = 0
    with_outcomes: int = 0
    without_outcomes: int = 0
    success_count: int = 0
    partial_count: int = 0
    failed_count: int = 0
    success_patterns: list[dict] = field(default_factory=list)
    failure_patterns: list[dict] = field(default_factory=list)
    missing_outcomes: list[dict] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Format report as markdown."""
        lines = [
            "# 🧠 Pattern Analysis Report",
            "",
            "## 📊 Summary",
            f"- Total decisions: **{self.total_decisions}**",
            f"- With outcomes: **{self.with_outcomes}** ({self._pct(self.with_outcomes)}%)",
            f"- Without outcomes: **{self.without_outcomes}** ({self._pct(self.without_outcomes)}%)",
            f"- ✅ Success: {self.success_count} | ⚠️ Partial: {self.partial_count} | ❌ Failed: {self.failed_count}",
            "",
        ]

        if self.success_patterns:
            lines.extend([
                "## ✅ Success Patterns (Best Practices)",
                "",
            ])
            for p in self.success_patterns:
                lines.append(f"### {p['project']} — {p['title']}")
                lines.append(f"> {p['outcome'][:200]}")
                if p.get("lessons"):
                    lines.append(f"- 💡 **Lesson**: {p['lessons'][:200]}")
                lines.append("")

        if self.failure_patterns:
            lines.extend([
                "## ❌ Failure Anti-Patterns",
                "",
            ])
            for p in self.failure_patterns:
                lines.append(f"### {p['project']} — {p['title']}")
                lines.append(f"> {p['outcome'][:200]}")
                if p.get("lessons"):
                    lines.append(f"- ⚠️ **Avoid**: {p['lessons'][:200]}")
                lines.append("")

        if self.missing_outcomes:
            lines.extend([
                "## 📝 Decisions Missing Outcomes",
                "",
            ])
            for m in self.missing_outcomes[:10]:
                lines.append(f"- **{m['project']}** — [{m['title']}]({m['path']})")
            if len(self.missing_outcomes) > 10:
                lines.append(f"- ... and {len(self.missing_outcomes) - 10} more")
            lines.append("")

        return "\n".join(lines)

    def _pct(self, n: int) -> int:
        return round(n / self.total_decisions * 100) if self.total_decisions > 0 else 0

    def to_auto_rules(self) -> str:
        """Generate auto-rules markdown from patterns."""
        lines = [
            "---",
            "project: _global",
            "type: guidelines",
            "tags:",
            '  - "auto-generated"',
            '  - "patterns"',
            f"created: {date.today().isoformat()}",
            f"updated: {date.today().isoformat()}",
            "---",
            "",
            "# Auto-Generated Rules (from Decision Outcomes)",
            "",
            f"> Generated from {self.with_outcomes} decision outcomes on {date.today().isoformat()}",
            "",
        ]

        if self.success_patterns:
            lines.extend(["## ✅ DO (Success Patterns)", ""])
            for i, p in enumerate(self.success_patterns, 1):
                lessons = p.get("lessons", p["outcome"][:150])
                lines.append(f"{i}. **{p['project']}**: {lessons}")
            lines.append("")

        if self.failure_patterns:
            lines.extend(["## ❌ DON'T (Anti-Patterns)", ""])
            for i, p in enumerate(self.failure_patterns, 1):
                lessons = p.get("lessons", p["outcome"][:150])
                lines.append(f"{i}. **{p['project']}**: {lessons}")
            lines.append("")

        return "\n".join(lines)


class PatternExtractor:
    """Extract patterns from decision outcomes across the vault."""

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path

    def analyze(self, project: Optional[str] = None) -> PatternReport:
        """Analyze all decisions and extract patterns."""
        report = PatternReport()

        notes = scan_vault(self.vault_path)
        if project:
            notes = [n for n in notes if n.project == project]

        # Filter to decision notes
        decisions = [n for n in notes if n.note_type == "decision"]
        report.total_decisions = len(decisions)

        for note in decisions:
            outcome_match = OUTCOME_PATTERN.search(note.content)

            if not outcome_match:
                report.without_outcomes += 1
                report.missing_outcomes.append({
                    "project": note.project,
                    "title": note.title,
                    "path": str(note.path),
                })
                continue

            report.with_outcomes += 1
            outcome_text = outcome_match.group(1).strip()

            # Extract status
            status_match = STATUS_PATTERN.search(outcome_text)
            status = status_match.group(1).lower() if status_match else "unknown"

            # Extract lessons
            lessons_match = LESSONS_PATTERN.search(outcome_text)
            lessons = lessons_match.group(1).strip() if lessons_match else ""

            outcome = DecisionOutcome(
                project=note.project,
                title=note.title,
                path=str(note.path),
                status=status,
                outcome_text=outcome_text,
                lessons=lessons,
            )

            pattern_entry = {
                "project": outcome.project,
                "title": outcome.title,
                "outcome": outcome.outcome_text,
                "lessons": outcome.lessons,
                "path": outcome.path,
            }

            if status == "success":
                report.success_count += 1
                report.success_patterns.append(pattern_entry)
            elif status == "failed":
                report.failed_count += 1
                report.failure_patterns.append(pattern_entry)
            elif status == "partial":
                report.partial_count += 1
                # Partial goes to both lists with appropriate context
                report.success_patterns.append(pattern_entry)

        return report

    def generate_auto_rules(self, project: Optional[str] = None) -> str:
        """Analyze decisions and save auto-rules to vault."""
        report = self.analyze(project)

        if report.with_outcomes == 0:
            return "No decision outcomes found. Add Outcome sections to decision notes first."

        rules_content = report.to_auto_rules()
        rules_path = self.vault_path / "_global" / "auto-rules.md"
        rules_path.write_text(rules_content, encoding="utf-8")

        logger.info(f"Auto-rules generated: {len(report.success_patterns)} DO, {len(report.failure_patterns)} DON'T")
        return rules_content
