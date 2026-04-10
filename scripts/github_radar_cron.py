#!/usr/bin/env python3
"""GitHub Radar — Daily cron job.

Scans GitHub trending repos + checks watched developers.
Saves report to vault and optionally sends to Telegram.

Usage:
    # Full daily scan (cron)
    python scripts/github_radar_cron.py

    # Only trending
    python scripts/github_radar_cron.py --trending-only

    # Only check watched devs
    python scripts/github_radar_cron.py --watch-only

    # Custom topic
    python scripts/github_radar_cron.py --topic mcp
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

# Add project to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from obsidian_bridge.github_radar import (
    DeveloperWatcher,
    RepoAnalyzer,
    TrendingScanner,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

VAULT_PATH = Path.home() / "SecondMind"
TOPICS = ["ai", "mcp", "devtools"]


def scan_trending(topics: list[str] | None = None) -> str:
    """Scan trending repos across topics."""
    topics = topics or TOPICS
    scanner = TrendingScanner()
    all_lines = [
        f"# 🔍 GitHub Radar — Daily Report",
        f"> {date.today()}",
        "",
    ]

    total_found = 0
    for topic in topics:
        repos = scanner.scan(topic=topic, days=7, min_stars=50, max_results=10)
        if repos:
            total_found += len(repos)
            all_lines.append(f"## Topic: {topic.upper()}")
            all_lines.append("")
            high = [r for r in repos if r.relevance_score >= 0.5]
            if high:
                for r in high[:5]:
                    all_lines.append(
                        f"- ⭐ **{r.stars:,}** [{r.full_name}]({r.url}) "
                        f"— {r.description[:80]} "
                        f"(rel: {r.relevance_score:.0%})"
                    )
                all_lines.append("")
            else:
                all_lines.append(f"No high-relevance repos for {topic}")
                all_lines.append("")

    all_lines.insert(2, f"> Found {total_found} repos across {len(topics)} topics")
    return "\n".join(all_lines)


def check_watched_devs() -> str:
    """Check watched developers for new activity."""
    watcher = DeveloperWatcher(vault_path=VAULT_PATH)
    watchlist = watcher._load_watchlist()

    if not watchlist:
        return ""

    lines = [
        "",
        "## 👀 Watched Developers",
        "",
    ]

    for entry in watchlist:
        username = entry["username"]
        profile = watcher.check(username)
        if profile and profile.recent_repos:
            recent = profile.recent_repos[0]
            lines.append(
                f"- **@{username}** ({profile.followers:,} followers) — "
                f"latest: [{recent['name']}]({recent['url']}) "
                f"⭐ {recent['stars']} ({recent['updated']})"
            )
        elif profile:
            lines.append(f"- **@{username}** — no recent public activity")

    lines.append("")
    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    """Send report to Telegram bot (if configured)."""
    import os
    token = os.environ.get("OBSIDIAN_BRIDGE_TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("OBSIDIAN_BRIDGE_TELEGRAM_OWNER_ID")

    if not token or not chat_id:
        logger.info("Telegram not configured, skipping notification")
        return False

    try:
        import httpx
        # Truncate for Telegram (4096 char limit)
        if len(text) > 4000:
            text = text[:3950] + "\n\n... (truncated, see vault for full report)"

        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Telegram send failed: {e}")
        return False


def save_to_vault(report: str) -> Path:
    """Save report to vault inbox."""
    filename = f"github-radar-{date.today()}.md"
    path = VAULT_PATH / "inbox" / filename

    # Add frontmatter
    full = (
        "---\n"
        "type: research\n"
        f"updated: {date.today()}\n"
        "tags: [github-radar, trending, automated]\n"
        "---\n\n"
        + report
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(full, encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser(description="GitHub Radar daily scan")
    parser.add_argument("--trending-only", action="store_true",
                        help="Only scan trending repos")
    parser.add_argument("--watch-only", action="store_true",
                        help="Only check watched developers")
    parser.add_argument("--topic", type=str, default=None,
                        help="Single topic to scan (ai/mcp/devtools)")
    parser.add_argument("--no-telegram", action="store_true",
                        help="Don't send Telegram notification")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print report but don't save")
    args = parser.parse_args()

    logger.info("🔍 GitHub Radar — Starting daily scan...")

    report_parts = []

    # Trending
    if not args.watch_only:
        topics = [args.topic] if args.topic else TOPICS
        logger.info(f"  Scanning trending: {topics}")
        trending = scan_trending(topics)
        report_parts.append(trending)

    # Watched devs
    if not args.trending_only:
        logger.info("  Checking watched developers...")
        watched = check_watched_devs()
        if watched:
            report_parts.append(watched)

    report = "\n".join(report_parts)

    if args.dry_run:
        print(report)
        return

    # Save to vault
    path = save_to_vault(report)
    logger.info(f"  ✅ Saved to {path}")

    # Telegram
    if not args.no_telegram:
        sent = send_telegram(report)
        if sent:
            logger.info("  ✅ Telegram notification sent")

    logger.info("🎉 Done!")


if __name__ == "__main__":
    main()
