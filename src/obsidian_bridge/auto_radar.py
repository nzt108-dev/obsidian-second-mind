"""Auto Radar — Automated Tech Radar with diff tracking & Telegram alerts.

v0.7.0: Runs scans periodically, compares with previous results,
saves diff report to vault, and sends Telegram alerts for important finds.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from obsidian_bridge.scout import TechRadar

logger = logging.getLogger(__name__)


@dataclass
class RadarDiff:
    """Diff between two radar scans."""
    scan_date: str = ""
    new_high_relevance: list[dict] = field(default_factory=list)
    new_medium_relevance: list[dict] = field(default_factory=list)
    removed_tools: list[dict] = field(default_factory=list)
    total_current: int = 0
    total_previous: int = 0

    @property
    def has_important_changes(self) -> bool:
        return len(self.new_high_relevance) > 0

    def to_markdown(self) -> str:
        lines = [
            f"# 📡 Tech Radar Diff — {self.scan_date}",
            "",
            f"**Current scan**: {self.total_current} tools",
            f"**Previous scan**: {self.total_previous} tools",
            f"**New high-relevance**: {len(self.new_high_relevance)}",
            f"**New medium-relevance**: {len(self.new_medium_relevance)}",
            "",
        ]

        if self.new_high_relevance:
            lines.extend(["## 🔴 New High Relevance", ""])
            for tool in self.new_high_relevance:
                lines.append(
                    f"- **[{tool['name']}]({tool.get('url', '')})** — "
                    f"{tool.get('description', '')[:100]}"
                )
            lines.append("")

        if self.new_medium_relevance:
            lines.extend(["## 🟡 New Medium Relevance", ""])
            for tool in self.new_medium_relevance:
                lines.append(
                    f"- **[{tool['name']}]({tool.get('url', '')})** — "
                    f"{tool.get('description', '')[:100]}"
                )
            lines.append("")

        if self.removed_tools:
            lines.extend([f"## ❌ No Longer Found ({len(self.removed_tools)})", ""])
            for tool in self.removed_tools[:5]:
                lines.append(f"- {tool['name']}")
            lines.append("")

        if not any([self.new_high_relevance, self.new_medium_relevance, self.removed_tools]):
            lines.append("*No significant changes since last scan.*")

        return "\n".join(lines)


class AutoRadar:
    """Automated Tech Radar with diff tracking and Telegram alerts.

    Usage:
        radar = AutoRadar(vault_path)
        diff = await radar.run_scan()
        if diff.has_important_changes:
            await radar.notify_telegram(diff, bot_token, chat_id)
    """

    def __init__(self, vault_path: Path):
        self.vault = vault_path
        self.radar = TechRadar(vault_path)
        self.radar_dir = vault_path / "_radar"
        self.radar_dir.mkdir(parents=True, exist_ok=True)

    async def run_scan(self, category: str = "all") -> RadarDiff:
        """Run scan, compare with previous, save diff report."""
        # 1. Load previous scan
        previous = self._load_latest()

        # 2. Run fresh scan
        current_report = await self.radar.scan(category)

        # 3. Compute diff
        diff = self._compute_diff(previous, current_report)

        # 4. Save results
        self._save_scan(current_report)
        self._save_diff_report(diff)

        # 5. Create vault note if there are important findings
        if diff.has_important_changes:
            self._create_vault_note(diff)

        return diff

    def _load_latest(self) -> dict | None:
        """Load the most recent scan data."""
        latest_path = self.radar_dir / "latest.json"
        if not latest_path.exists():
            return None

        try:
            return json.loads(latest_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load previous scan: {e}")
            return None

    def _save_scan(self, report) -> None:
        """Save current scan as latest.json for future diffing."""
        data = {
            "scan_date": report.scan_date,
            "tools_found": report.tools_found,
            "high_relevance": report.high_relevance,
            "medium_relevance": report.medium_relevance,
            "low_relevance": report.low_relevance,
        }

        latest_path = self.radar_dir / "latest.json"
        latest_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Also save timestamped copy
        archive_path = self.radar_dir / f"scan-{report.scan_date}.json"
        archive_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info(f"Scan saved: {latest_path}")

    def _compute_diff(self, previous: dict | None, current) -> RadarDiff:
        """Compute diff between previous and current scan."""
        diff = RadarDiff(
            scan_date=current.scan_date,
            total_current=current.tools_found,
        )

        if previous is None:
            # First scan — everything is "new"
            diff.new_high_relevance = current.high_relevance
            diff.new_medium_relevance = current.medium_relevance
            diff.total_previous = 0
            return diff

        diff.total_previous = previous.get("tools_found", 0)

        # Find new tools (by name)
        prev_names = set()
        for bucket in ["high_relevance", "medium_relevance", "low_relevance"]:
            for tool in previous.get(bucket, []):
                prev_names.add(tool["name"])

        for tool in current.high_relevance:
            if tool["name"] not in prev_names:
                diff.new_high_relevance.append(tool)

        for tool in current.medium_relevance:
            if tool["name"] not in prev_names:
                diff.new_medium_relevance.append(tool)

        # Find removed tools
        curr_names = set()
        for tool in current.high_relevance + current.medium_relevance + current.low_relevance:
            curr_names.add(tool["name"])

        for bucket in ["high_relevance", "medium_relevance"]:
            for tool in previous.get(bucket, []):
                if tool["name"] not in curr_names:
                    diff.removed_tools.append(tool)

        return diff

    def _save_diff_report(self, diff: RadarDiff) -> None:
        """Save diff report as markdown."""
        report_path = self.radar_dir / f"diff-{diff.scan_date}.md"
        report_path.write_text(diff.to_markdown(), encoding="utf-8")
        logger.info(f"Diff report: {report_path}")

    def _create_vault_note(self, diff: RadarDiff) -> None:
        """Create a research note in vault for important findings."""
        today = date.today().isoformat()
        note_dir = self.vault / "_global"
        note_dir.mkdir(parents=True, exist_ok=True)

        file_path = note_dir / f"radar-{today}.md"
        content = (
            f"---\n"
            f"project: _global\n"
            f"type: research\n"
            f"tags:\n"
            f'  - "radar"\n'
            f'  - "auto-generated"\n'
            f"priority: medium\n"
            f"created: {today}\n"
            f"updated: {today}\n"
            f"---\n\n"
            f"{diff.to_markdown()}\n"
        )

        file_path.write_text(content, encoding="utf-8")
        logger.info(f"Vault note created: {file_path}")


# ---------------------------------------------------------------------------
# Telegram Notification
# ---------------------------------------------------------------------------

async def notify_telegram(
    diff: RadarDiff,
    bot_token: str,
    chat_id: int | str,
) -> bool:
    """Send Telegram alert for important radar findings.

    Only sends if there are new high-relevance tools.
    Returns True if message was sent.
    """
    if not diff.has_important_changes:
        return False

    if not bot_token or not chat_id:
        logger.warning("Telegram credentials not set, skipping notification")
        return False

    import httpx

    # Build message
    lines = [f"🔭 <b>Tech Radar Alert</b> — {diff.scan_date}\n"]
    lines.append(f"Найдено <b>{len(diff.new_high_relevance)}</b> новых важных инструментов:\n")

    for tool in diff.new_high_relevance[:5]:
        name = tool["name"].replace("<", "&lt;").replace(">", "&gt;")
        desc = tool.get("description", "")[:80].replace("<", "&lt;").replace(">", "&gt;")
        url = tool.get("url", "")
        if url:
            lines.append(f"🔴 <a href=\"{url}\">{name}</a> — {desc}")
        else:
            lines.append(f"🔴 <b>{name}</b> — {desc}")

    if diff.new_medium_relevance:
        lines.append(f"\n🟡 + {len(diff.new_medium_relevance)} medium-relevance tools")

    msg = "\n".join(lines)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": msg,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            if resp.status_code == 200:
                logger.info(f"Telegram alert sent to {chat_id}")
                return True
            else:
                logger.error(f"Telegram alert failed: {resp.status_code} {resp.text}")
                return False
    except Exception as e:
        logger.error(f"Telegram notification error: {e}")
        return False
