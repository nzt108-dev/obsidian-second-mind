"""Wake-up Context Generator for Obsidian Second Mind.

v0.6.0: Generates a compact (~200 token) summary of critical facts
for AI agents to load at session start. Inspired by MemPalace L0+L1 layers.

No LLM needed — reads vault files and formats a concise summary.
"""
import logging
from datetime import date, timedelta
from pathlib import Path

from obsidian_bridge.parser import get_projects, get_project_notes, scan_vault

logger = logging.getLogger(__name__)


class WakeupContext:
    """Generate compact wake-up context for AI sessions.

    Scans the vault and produces ~200 tokens with:
    - Active projects and their tech stacks
    - Recent decisions (last 14 days)
    - Inbox items awaiting processing
    - Known blockers from CURRENT_STATUS.md files
    """

    def __init__(self, vault_path: Path, project_base_dirs: list[str] | None = None):
        self.vault = vault_path
        self.project_base_dirs = project_base_dirs or []

    def generate(self, focus_project: str = "") -> str:
        """Generate compact wake-up context.

        Args:
            focus_project: If set, prioritize this project's context.

        Returns:
            Compact markdown string (~200 tokens).
        """
        today = date.today().isoformat()
        sections = [f"🧠 **Wake-up Context** | {today}"]

        # 1. Projects overview
        projects_info = self._get_projects_summary(focus_project)
        if projects_info:
            sections.append(projects_info)

        # 2. Inbox items
        inbox_info = self._get_inbox_summary()
        if inbox_info:
            sections.append(inbox_info)

        # 3. Recent decisions
        decisions = self._get_recent_decisions(days=14)
        if decisions:
            sections.append(decisions)

        # 4. Blockers (from CURRENT_STATUS.md)
        blockers = self._get_blockers()
        if blockers:
            sections.append(blockers)

        return "\n".join(sections)

    def _get_projects_summary(self, focus: str = "") -> str:
        """Get compact projects overview."""
        projects = get_projects(self.vault)
        if not projects:
            return ""

        lines = ["**Projects:**"]
        for p in projects:
            if p.startswith("_"):
                continue  # Skip _global, _radar, etc.
            notes = get_project_notes(self.vault, p)
            note_count = len(notes)

            # Check for architecture note to get tech stack
            stack = ""
            for n in notes:
                if n.note_type == "architecture":
                    stack = self._extract_tech_stack(n.content)
                    break

            marker = "→ " if p == focus else "• "
            line = f"{marker}**{p}** ({note_count} notes)"
            if stack:
                line += f" — {stack}"
            lines.append(line)

        return "\n".join(lines)

    def _get_inbox_summary(self) -> str:
        """Count unprocessed inbox items."""
        inbox_dir = self.vault / "inbox"
        if not inbox_dir.exists():
            return ""

        items = list(inbox_dir.glob("*.md"))
        if not items:
            return ""

        # Count by type based on filename
        ideas = sum(1 for f in items if "idea" in f.stem.lower())
        links = sum(1 for f in items if "link" in f.stem.lower())
        decisions = sum(1 for f in items if "decision" in f.stem.lower())
        other = len(items) - ideas - links - decisions

        parts = []
        if ideas:
            parts.append(f"{ideas} ideas")
        if links:
            parts.append(f"{links} links")
        if decisions:
            parts.append(f"{decisions} decisions")
        if other:
            parts.append(f"{other} other")

        return f"📥 **Inbox**: {len(items)} items ({', '.join(parts)})"

    def _get_recent_decisions(self, days: int = 14) -> str:
        """Find recent decision notes."""
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        notes = scan_vault(self.vault)

        decisions = []
        for note in notes:
            if note.note_type != "decision":
                continue
            created = ""
            for tag in note.tags:
                tag_str = str(tag)
                # Try to find date in tags or created field
                if len(tag_str) == 10 and tag_str.startswith("20"):
                    created = tag_str
                    break
            # Fallback: check frontmatter created field
            if not created and hasattr(note, "raw_content"):
                for line in note.raw_content.split("\n"):
                    if line.startswith("created:"):
                        created = line.split(":", 1)[1].strip()
                        break

            if created and created >= cutoff:
                # Extract the decision text (first meaningful line after ## Decision)
                decision_text = self._extract_section(note.content, "Decision")
                if not decision_text:
                    decision_text = note.title
                decisions.append((created, note.project, decision_text[:80]))

        if not decisions:
            return ""

        decisions.sort(reverse=True)  # Most recent first
        lines = ["**Recent decisions:**"]
        for dt, proj, text in decisions[:5]:
            lines.append(f"• [{dt}] {proj}: {text}")
        return "\n".join(lines)

    def _get_blockers(self) -> str:
        """Extract blockers from CURRENT_STATUS.md files in project dirs."""
        blockers = []

        for base_dir in self.project_base_dirs:
            base = Path(base_dir)
            if not base.exists():
                continue

            for project_dir in base.iterdir():
                if not project_dir.is_dir():
                    continue
                status_file = project_dir / "docs" / "CURRENT_STATUS.md"
                if not status_file.exists():
                    continue

                try:
                    content = status_file.read_text(encoding="utf-8")
                    blocker_text = self._extract_section(content, "Known Issues")
                    if not blocker_text:
                        blocker_text = self._extract_section(content, "Blockers")
                    if blocker_text and blocker_text.strip() not in ("None", "—", "-", "N/A", ""):
                        blockers.append(f"• {project_dir.name}: {blocker_text[:80]}")
                except Exception:
                    continue

        if not blockers:
            return ""

        return "⚠️ **Blockers:**\n" + "\n".join(blockers[:3])

    @staticmethod
    def _extract_tech_stack(content: str) -> str:
        """Extract tech stack from architecture note content."""
        # Look for common patterns like "Stack: Flutter, Dart" or "## Tech Stack"
        for line in content.split("\n"):
            line = line.strip()
            if any(kw in line.lower() for kw in ["tech stack", "stack:", "framework:"]):
                # Clean up the line
                clean = line.lstrip("#").strip()
                if ":" in clean:
                    return clean.split(":", 1)[1].strip()[:50]
        return ""

    @staticmethod
    def _extract_section(content: str, heading: str) -> str:
        """Extract text under a specific heading."""
        in_section = False
        lines = []

        for line in content.split("\n"):
            if line.strip().lower().startswith(f"## {heading.lower()}") or \
               line.strip().lower().startswith(f"### {heading.lower()}"):
                in_section = True
                continue
            elif in_section:
                if line.startswith("##"):
                    break  # Next section
                stripped = line.strip()
                if stripped and not stripped.startswith(">"):
                    lines.append(stripped)

        return " ".join(lines[:3]).strip()
