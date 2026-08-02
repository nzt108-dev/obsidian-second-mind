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

# Load .env so cron jobs (LaunchAgent) can read tokens without shell inheritance
from dotenv import load_dotenv  # noqa: E402
load_dotenv(PROJECT_ROOT / ".env")

from obsidian_bridge.github_radar import (  # noqa: E402
    DeveloperWatcher,
    RadarScanError,
    TrendingScanner,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

VAULT_PATH = Path.home() / "SecondMind"
TOPICS = ["ai", "mcp", "devtools"]

# Run-ledger (standards/automation-loops.md §3) — one JSON line per run
RUN_LOG = Path.home() / ".claude" / "logs" / "github-radar.jsonl"
# Reports older than this move out of inbox into the radar archive
KEEP_IN_INBOX_DAYS = 7
ARCHIVE_DIR = VAULT_PATH / "_radar" / "archive"


def scan_trending(topics: list[str] | None = None) -> tuple[str, dict, list[str]]:
    """Scan trending repos across topics.

    Returns (markdown_report, structured, errors) where structured maps
    topic → [repos] and errors lists topics whose API call failed outright.
    """
    topics = topics or TOPICS
    scanner = TrendingScanner()
    all_lines = [
        "# 🔍 GitHub Radar — Daily Report",
        f"> {date.today()}",
        "",
    ]

    total_found = 0
    structured: dict = {}
    errors: list[str] = []

    for topic in topics:
        try:
            repos = scanner.scan(topic=topic, days=7, min_stars=50, max_results=10)
        except RadarScanError as e:
            logger.error(f"  ❌ topic '{topic}': {e}")
            errors.append(f"{topic}: {e}")
            continue
        if repos:
            total_found += len(repos)
            structured[topic] = repos
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
    return "\n".join(all_lines), structured, errors


def check_watched_devs() -> tuple[str, list[dict], list[str]]:
    """Check watched developers for new activity.

    Returns (markdown_report, list of {username, repo, url, stars, updated},
    errors). A None profile means the API call failed — it is an error, not
    "this developer has been quiet".
    """
    watcher = DeveloperWatcher(vault_path=VAULT_PATH)
    watchlist = watcher._load_watchlist()

    if not watchlist:
        return "", [], []

    lines = [
        "",
        "## 👀 Watched Developers",
        "",
    ]
    structured: list[dict] = []
    errors: list[str] = []

    for entry in watchlist:
        username = entry["username"]
        profile = watcher.check(username)
        if profile is None:
            errors.append(f"@{username}: profile check failed")
            continue
        if profile and profile.recent_repos:
            recent = profile.recent_repos[0]
            lines.append(
                f"- **@{username}** ({profile.followers:,} followers) — "
                f"latest: [{recent['name']}]({recent['url']}) "
                f"⭐ {recent['stars']} ({recent['updated']})"
            )
            structured.append({
                "username": username,
                "repo": recent["name"],
                "url": recent["url"],
                "stars": recent["stars"],
                "updated": recent["updated"],
            })
        elif profile:
            lines.append(f"- **@{username}** — no recent public activity")

    lines.append("")
    return "\n".join(lines), structured, errors


def build_telegram_html(
    repos_by_topic: dict,
    watched: list[dict],
    total_found: int,
) -> str:
    """Build a short HTML-formatted Telegram message from structured scan results."""
    import html
    today = date.today()
    lines = [
        f"<b>🔍 GitHub Radar — {today}</b>",
        f"Found <b>{total_found}</b> repos\n",
    ]

    for topic, repos in repos_by_topic.items():
        high = [r for r in repos if r.relevance_score >= 0.5]
        if high:
            lines.append(f"<b>{html.escape(topic.upper())}</b>")
            for r in high[:3]:
                name = html.escape(r.full_name)
                desc = html.escape((r.description or "")[:70])
                lines.append(
                    f'⭐ {r.stars:,} <a href="{r.url}">{name}</a>'
                    + (f" — {desc}" if desc else "")
                )
            lines.append("")

    if watched:
        lines.append("<b>👀 Watched Devs</b>")
        for d in watched[:5]:
            uname = html.escape(d["username"])
            repo = html.escape(d["repo"])
            lines.append(
                f'@{uname} → <a href="{d["url"]}">{repo}</a> ⭐ {d["stars"]}'
            )

    return "\n".join(lines)


def send_telegram(html_text: str) -> bool:
    """Send HTML-formatted report to Telegram (if configured)."""
    import os
    token = os.environ.get("OBSIDIAN_BRIDGE_TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("OBSIDIAN_BRIDGE_TELEGRAM_OWNER_ID")

    if not token or not chat_id:
        logger.info("Telegram not configured, skipping notification")
        return False

    try:
        import httpx
        if len(html_text) > 4000:
            html_text = html_text[:3950] + "\n\n<i>... см. vault для полного отчёта</i>"

        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": html_text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning(f"Telegram API error {resp.status_code}: {resp.text[:200]}")
            return False
        return True
    except Exception as e:
        logger.warning(f"Telegram send failed: {e}")
        return False


def write_run_log(outcome: str, findings: int, error: str = "") -> None:
    """Append one line to the run-ledger. Never breaks the job."""
    import json
    from datetime import datetime, timezone

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "job": "github-radar",
        "outcome": outcome,
        "error": error,
        "findings": findings,
        "escalations": 1 if outcome == "failure" else 0,
    }
    try:
        RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
        with RUN_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.warning(f"Run-log write failed: {e}")


def archive_old_reports(keep_days: int = KEEP_IN_INBOX_DAYS) -> int:
    """Move radar reports older than keep_days out of inbox into _radar/archive."""
    from datetime import timedelta

    inbox = VAULT_PATH / "inbox"
    if not inbox.exists():
        return 0

    cutoff = date.today() - timedelta(days=keep_days)
    moved = 0
    for path in inbox.glob("github-radar-*.md"):
        try:
            report_date = date.fromisoformat(path.stem.replace("github-radar-", ""))
        except ValueError:
            continue
        if report_date >= cutoff:
            continue
        try:
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            path.rename(ARCHIVE_DIR / path.name)
            moved += 1
        except OSError as e:
            logger.warning(f"Archive failed for {path.name}: {e}")
    return moved


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
    repos_by_topic: dict = {}
    watched_structured: list[dict] = []
    total_found = 0
    scan_errors: list[str] = []
    watch_errors: list[str] = []

    # Trending
    if not args.watch_only:
        topics = [args.topic] if args.topic else TOPICS
        logger.info(f"  Scanning trending: {topics}")
        trending_md, repos_by_topic, scan_errors = scan_trending(topics)
        total_found = sum(len(v) for v in repos_by_topic.values())
        report_parts.append(trending_md)

    # Watched devs
    if not args.trending_only:
        logger.info("  Checking watched developers...")
        watched_md, watched_structured, watch_errors = check_watched_devs()
        if watched_md:
            report_parts.append(watched_md)
    if watch_errors:
        report_parts.append(
            "\n> ⚠️ Часть наблюдаемых разработчиков не опрошена: "
            + "; ".join(watch_errors)
        )

    report = "\n".join(report_parts)
    all_errors = scan_errors + watch_errors

    if args.dry_run:
        print(report)
        if all_errors:
            logger.error(f"  ❌ {len(all_errors)} failure(s): {'; '.join(all_errors)}")
        return

    # Trending failed → no vault report at all (a "Found 0 repos" note would read
    # as a quiet day and hide the outage). Alert, log it, exit non-zero so the
    # heartbeat wrapper skips its ping and healthchecks escalates.
    if scan_errors:
        err_text = "; ".join(all_errors)
        logger.error(f"  ❌ Scan failed: {err_text}")
        if not args.no_telegram:
            send_telegram(
                f"<b>⚠️ GitHub Radar — сбой {date.today()}</b>\n"
                f"Не опрошено тем: {len(scan_errors)}\n"
                f"<code>{err_text[:500]}</code>\n"
                "Отчёт за день НЕ сохранён."
            )
        write_run_log("failure", findings=0, error=err_text)
        sys.exit(1)

    # Save to vault
    path = save_to_vault(report)
    logger.info(f"  ✅ Saved to {path}")

    # Watchlist-only failures: report is still valid, but the gap must be visible.
    if watch_errors:
        err_text = "; ".join(watch_errors)
        logger.warning(f"  ⚠️ Watchlist degraded: {err_text}")
        if not args.no_telegram:
            send_telegram(
                f"<b>⚠️ GitHub Radar {date.today()}</b> — тренды собраны, "
                f"watchlist частично не опрошен:\n<code>{err_text[:300]}</code>"
            )

    archived = archive_old_reports()
    if archived:
        logger.info(f"  🗄  Archived {archived} old report(s) → {ARCHIVE_DIR}")

    # Telegram — skip if nothing found (no spam on empty scans)
    if not args.no_telegram:
        if total_found == 0 and not watched_structured:
            logger.info("  No findings — skipping Telegram notification")
        else:
            html_msg = build_telegram_html(repos_by_topic, watched_structured, total_found)
            sent = send_telegram(html_msg)
            if sent:
                logger.info("  ✅ Telegram notification sent")

    write_run_log(
        "noop" if total_found == 0 and not watched_structured else "success",
        findings=total_found,
        error="; ".join(watch_errors),
    )
    logger.info("🎉 Done!")


if __name__ == "__main__":
    main()
