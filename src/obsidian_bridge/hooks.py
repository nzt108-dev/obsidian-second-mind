"""Agent Memory — Auto-save hooks and session continuity.

v0.9.0: Ensures AI agents never lose context between sessions.

Three mechanisms:
1. Session Save — periodic or on-demand snapshot of current work
2. Emergency Save — fast context dump before session termination
3. Wake-up Cache — precomputed context for instant session start

No LLM required — scans git, vault, and project files.
"""
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class SessionSnapshot:
    """Snapshot of current session state."""
    timestamp: str = ""
    project: str = ""
    summary: str = ""
    files_changed: list[str] = field(default_factory=list)
    git_status: str = ""
    git_branch: str = ""
    recent_commits: list[str] = field(default_factory=list)
    uncommitted_changes: list[str] = field(default_factory=list)
    active_decisions: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "project": self.project,
            "summary": self.summary,
            "files_changed": self.files_changed,
            "git_status": self.git_status,
            "git_branch": self.git_branch,
            "recent_commits": self.recent_commits,
            "uncommitted_changes": self.uncommitted_changes,
            "active_decisions": self.active_decisions,
            "blockers": self.blockers,
            "next_steps": self.next_steps,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SessionSnapshot":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})

    def to_markdown(self) -> str:
        """Format as readable markdown."""
        lines = [
            f"## 🧠 Session Snapshot — {self.timestamp}",
            "",
        ]

        if self.project:
            lines.append(f"**Project**: `{self.project}`")
        if self.summary:
            lines.append(f"**Summary**: {self.summary}")
        if self.git_branch:
            lines.append(f"**Branch**: `{self.git_branch}`")
        lines.append("")

        if self.recent_commits:
            lines.append("### Recent Commits")
            for c in self.recent_commits[:10]:
                lines.append(f"- `{c}`")
            lines.append("")

        if self.uncommitted_changes:
            lines.append("### Uncommitted Changes")
            for f in self.uncommitted_changes:
                lines.append(f"- {f}")
            lines.append("")

        if self.files_changed:
            lines.append("### Files Changed This Session")
            for f in self.files_changed[:20]:
                lines.append(f"- `{f}`")
            lines.append("")

        if self.active_decisions:
            lines.append("### Active Decisions")
            for d in self.active_decisions:
                lines.append(f"- {d}")
            lines.append("")

        if self.blockers:
            lines.append("### ⚠️ Blockers")
            for b in self.blockers:
                lines.append(f"- {b}")
            lines.append("")

        if self.next_steps:
            lines.append("### ➡️ Next Steps")
            for s in self.next_steps:
                lines.append(f"- {s}")
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Git Helpers
# ---------------------------------------------------------------------------

def _run_git(project_dir: Path, *args: str) -> str:
    """Run git command and return stdout."""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=str(project_dir),
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _get_git_info(project_dir: Path) -> dict:
    """Get git status, branch, recent commits, uncommitted files."""
    if not (project_dir / ".git").exists():
        return {}

    branch = _run_git(project_dir, "branch", "--show-current")
    status = _run_git(project_dir, "status", "--short")
    log = _run_git(project_dir, "log", "--oneline", "-10")
    diff_stat = _run_git(project_dir, "diff", "--stat", "--name-only")

    uncommitted = []
    for line in status.split("\n"):
        line = line.strip()
        if line:
            uncommitted.append(line)

    recent_commits = []
    for line in log.split("\n"):
        line = line.strip()
        if line:
            recent_commits.append(line)

    files_changed = []
    for line in diff_stat.split("\n"):
        line = line.strip()
        if line:
            files_changed.append(line)

    return {
        "branch": branch,
        "status": status,
        "recent_commits": recent_commits,
        "uncommitted": uncommitted,
        "files_changed": files_changed,
    }


# ---------------------------------------------------------------------------
# Session Hooks
# ---------------------------------------------------------------------------

class SessionHooks:
    """Automated session context saving.

    Usage:
        hooks = SessionHooks(vault_path, project_base_dirs)

        # On-demand save (called by MCP tool or /save command)
        snapshot = hooks.save_session("brieftube")

        # Emergency save (minimal, fast — before context loss)
        snapshot = hooks.emergency_save("brieftube")

        # Load last session (for wake-up)
        snapshot = hooks.load_last_session("brieftube")
    """

    def __init__(self, vault_path: Path, project_base_dirs: list[str] | None = None,
                 max_snapshots: int = 50):
        self.vault = vault_path
        self.project_base_dirs = project_base_dirs or []
        self.max_snapshots = max_snapshots
        self._memory_dir = vault_path / "_memory"
        self._memory_dir.mkdir(parents=True, exist_ok=True)

    def save_session(
        self,
        project: str,
        summary: str = "",
        next_steps: list[str] | None = None,
        blockers: list[str] | None = None,
    ) -> SessionSnapshot:
        """Full session save — captures git state, decisions, context.

        Called by:
        - MCP tool `save_session`
        - CLI command `obsidian-bridge save`
        - /save workflow step
        """
        now = datetime.now()
        snapshot = SessionSnapshot(
            timestamp=now.strftime("%Y-%m-%d %H:%M"),
            project=project,
            summary=summary,
            next_steps=next_steps or [],
            blockers=blockers or [],
        )

        # 1. Get git info from project directory
        project_dir = self._find_project_dir(project)
        if project_dir:
            git_info = _get_git_info(project_dir)
            snapshot.git_branch = git_info.get("branch", "")
            snapshot.git_status = git_info.get("status", "")
            snapshot.recent_commits = git_info.get("recent_commits", [])
            snapshot.uncommitted_changes = git_info.get("uncommitted", [])
            snapshot.files_changed = git_info.get("files_changed", [])

        # 2. Get recent decisions from vault
        snapshot.active_decisions = self._get_recent_decisions(project)

        # 3. Persist as JSON (for machine reading)
        self._save_snapshot_json(project, snapshot)

        # 4. Persist as Markdown note (for human reading + vault search)
        self._save_snapshot_note(project, snapshot, now)

        # 5. Update wake-up cache
        self._update_wakeup_cache(project, snapshot)

        # 6. Prune old snapshots to prevent unbounded growth
        self._prune_old_snapshots(project)

        logger.info(f"Session saved: {project} at {snapshot.timestamp}")
        return snapshot

    def emergency_save(self, project: str) -> SessionSnapshot:
        """Fast emergency save — minimal data, no vault scan.

        Called before context loss (e.g., IDE crash, session timeout).
        Only captures git status and uncommitted changes.
        """
        now = datetime.now()
        snapshot = SessionSnapshot(
            timestamp=now.strftime("%Y-%m-%d %H:%M"),
            project=project,
            summary="⚠️ Emergency save — session interrupted",
        )

        project_dir = self._find_project_dir(project)
        if project_dir:
            git_info = _get_git_info(project_dir)
            snapshot.git_branch = git_info.get("branch", "")
            snapshot.git_status = git_info.get("status", "")
            snapshot.uncommitted_changes = git_info.get("uncommitted", [])
            snapshot.recent_commits = git_info.get("recent_commits", [])[:5]

        self._save_snapshot_json(project, snapshot)
        logger.warning(f"Emergency save: {project} at {snapshot.timestamp}")
        return snapshot

    def load_last_session(self, project: str) -> SessionSnapshot | None:
        """Load the most recent session snapshot for a project.

        Used by wake-up context generator to provide instant recall.
        """
        # Try project-specific snapshot first
        snapshot_path = self._memory_dir / f"{project}-latest.json"
        if not snapshot_path.exists():
            return None

        try:
            data = json.loads(snapshot_path.read_text(encoding="utf-8"))
            return SessionSnapshot.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to load session for {project}: {e}")
            return None

    def list_sessions(self, project: str = "", limit: int = 10) -> list[dict]:
        """List saved session snapshots."""
        sessions = []

        pattern = f"{project}-*.json" if project else "*.json"
        for path in sorted(self._memory_dir.glob(pattern), reverse=True):
            if path.name.endswith("-latest.json"):
                continue  # Skip latest pointers
            if path.name.startswith("wakeup-"):
                continue  # Skip cache files
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sessions.append({
                    "file": path.name,
                    "timestamp": data.get("timestamp", ""),
                    "project": data.get("project", ""),
                    "summary": data.get("summary", "")[:80],
                })
            except Exception:
                continue

            if len(sessions) >= limit:
                break

        return sessions

    # --- Internal ---

    def _find_project_dir(self, project: str) -> Path | None:
        """Find the project directory on local filesystem."""
        for base in self.project_base_dirs:
            candidate = Path(base) / project
            if candidate.exists():
                return candidate

        # Fallback: try common locations
        for base in [Path.home() / "Projects", Path.home() / "Developer"]:
            candidate = base / project
            if candidate.exists():
                return candidate

        return None

    def _get_recent_decisions(self, project: str, days: int = 14) -> list[str]:
        """Get recent decisions from vault notes."""
        from datetime import timedelta
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        decisions = []

        project_dir = self.vault / project
        if not project_dir.exists():
            return decisions

        for md_file in project_dir.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                if "type: decision" not in content[:500]:
                    continue

                # Extract created date
                for line in content.split("\n")[:10]:
                    if line.startswith("created:"):
                        created = line.split(":", 1)[1].strip()
                        if created >= cutoff:
                            # Get title
                            for tline in content.split("\n"):
                                if tline.startswith("# "):
                                    decisions.append(tline[2:].strip()[:80])
                                    break
                        break
            except Exception:
                continue

        return decisions[:5]

    def _save_snapshot_json(self, project: str, snapshot: SessionSnapshot):
        """Save snapshot as JSON for machine reading."""
        # Timestamped archive
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        archive_path = self._memory_dir / f"{project}-{ts}.json"
        archive_path.write_text(
            json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Latest (overwrite)
        latest_path = self._memory_dir / f"{project}-latest.json"
        latest_path.write_text(
            json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _save_snapshot_note(self, project: str, snapshot: SessionSnapshot, now: datetime):
        """Save snapshot as a vault note for search + discovery."""
        today = date.today().isoformat()
        note_dir = self.vault / project
        note_dir.mkdir(parents=True, exist_ok=True)

        filename = f"session-{now.strftime('%Y%m%d-%H%M')}.md"
        file_path = note_dir / filename

        content = (
            f"---\n"
            f"project: {project}\n"
            f"type: note\n"
            f"tags:\n"
            f'  - "session"\n'
            f'  - "auto-saved"\n'
            f"priority: low\n"
            f"created: {today}\n"
            f"updated: {today}\n"
            f"source: agent-memory\n"
            f"---\n\n"
            f"{snapshot.to_markdown()}\n"
        )

        file_path.write_text(content, encoding="utf-8")
        logger.info(f"Session note: {file_path.relative_to(self.vault)}")

    def _update_wakeup_cache(self, project: str, snapshot: SessionSnapshot):
        """Update pre-computed wake-up context cache.

        Stored in _memory/wakeup-cache.json for instant loading.
        """
        cache_path = self._memory_dir / "wakeup-cache.json"

        # Load existing cache
        cache: dict = {}
        if cache_path.exists():
            try:
                cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                cache = {}

        # Update project entry
        cache[project] = {
            "last_session": snapshot.timestamp,
            "summary": snapshot.summary,
            "branch": snapshot.git_branch,
            "uncommitted": len(snapshot.uncommitted_changes),
            "recent_commits": snapshot.recent_commits[:3],
            "decisions": snapshot.active_decisions[:3],
            "blockers": snapshot.blockers[:3],
            "next_steps": snapshot.next_steps[:3],
        }

        cache["_updated"] = datetime.now().isoformat()

        cache_path.write_text(
            json.dumps(cache, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"Wake-up cache updated for {project}")

    def _prune_old_snapshots(self, project: str):
        """Remove old session archives beyond max_snapshots limit.

        Keeps the N most recent snapshots per project to prevent
        unbounded growth of _memory/ directory.
        """
        pattern = f"{project}-*.json"
        archives = sorted(
            (f for f in self._memory_dir.glob(pattern)
             if not f.name.endswith("-latest.json")
             and not f.name.startswith("wakeup-")),
            reverse=True,  # newest first
        )

        if len(archives) <= self.max_snapshots:
            return

        # Remove oldest files
        for old_file in archives[self.max_snapshots:]:
            try:
                old_file.unlink()
                logger.debug(f"Pruned old snapshot: {old_file.name}")
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Enhanced Wake-up Context (with session memory)
# ---------------------------------------------------------------------------

def generate_enhanced_wakeup(
    vault_path: Path,
    project: str = "",
    project_base_dirs: list[str] | None = None,
) -> str:
    """Generate enhanced wake-up context with session memory.

    Combines:
    - Standard wake-up (projects, inbox, decisions)
    - Last session snapshot (git state, next steps, blockers)
    - Temporal KG summary (active facts for project)
    """
    from obsidian_bridge.wakeup import WakeupContext

    # 1. Standard wake-up
    wakeup = WakeupContext(vault_path, project_base_dirs or [])
    base_context = wakeup.generate(focus_project=project)

    # 2. Session memory
    hooks = SessionHooks(vault_path, project_base_dirs or [])
    sections = [base_context]

    if project:
        last = hooks.load_last_session(project)
        if last:
            memory_lines = [
                "",
                f"📌 **Last session**: {last.timestamp}",
            ]
            if last.summary:
                memory_lines.append(f"  {last.summary}")
            if last.git_branch:
                memory_lines.append(f"  Branch: `{last.git_branch}`")
            if last.uncommitted_changes:
                memory_lines.append(f"  ⚠️ {len(last.uncommitted_changes)} uncommitted changes!")
            if last.next_steps:
                memory_lines.append("  **Next:**")
                for step in last.next_steps[:3]:
                    memory_lines.append(f"  → {step}")
            if last.blockers:
                memory_lines.append("  **Blockers:**")
                for b in last.blockers[:2]:
                    memory_lines.append(f"  ⛔ {b}")

            sections.append("\n".join(memory_lines))

    # 3. Temporal KG snapshot (if available)
    try:
        from obsidian_bridge.graph import TemporalKnowledgeGraph
        tkg = TemporalKnowledgeGraph(vault_path)
        if project and tkg.active_fact_count > 0:
            active = tkg.query_entity(project)
            if active:
                kg_lines = ["", "🧠 **Active stack:**"]
                for fact in active[:6]:
                    kg_lines.append(f"  • {fact.predicate}: `{fact.object}`")
                sections.append("\n".join(kg_lines))
    except Exception:
        pass

    return "\n".join(sections)
