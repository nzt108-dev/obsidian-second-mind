#!/usr/bin/env python3
"""Sync all project data from Obsidian vault to nzt108.dev portfolio API."""
import json
import os
import subprocess
import urllib.request
import yaml
from pathlib import Path

VAULT = Path.home() / "SecondMind"
PROJECTS_DIR = Path.home() / "Projects"

# Load API key
env_path = Path.home() / "Projects" / "architect-portfolio" / ".env"
API_KEY = ""
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.startswith("PORTFOLIO_API_KEY="):
            API_KEY = line.split("=", 1)[1].strip().strip('"')
            break

API_URL = "https://nzt108.dev/api/agent/projects"


def git_info(path: str) -> dict:
    """Get last commit info from a project directory."""
    if not Path(path).exists():
        return {}
    try:
        def run(args):
            r = subprocess.run(["git"] + args, cwd=path, capture_output=True, text=True, timeout=5)
            return r.stdout.strip() if r.returncode == 0 else None

        return {
            "lastCommitHash": run(["log", "-1", "--format=%h"]) or "",
            "lastCommitMsg": run(["log", "-1", "--format=%s"]) or "",
            "lastCommitDate": run(["log", "-1", "--format=%ci"]) or "",
        }
    except Exception:
        return {}


def parse_frontmatter(filepath: Path) -> dict:
    content = filepath.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except Exception:
        return {}


def sync_project(fm: dict) -> None:
    """Push one project to the portfolio API."""
    slug = fm.get("project", "")
    if not slug:
        return

    local_path = fm.get("path", "")
    github = fm.get("github", "")
    git = git_info(local_path) if local_path else {}

    payload = {
        "title": fm.get("title", slug).replace("— PRD", "").replace("— prd", "").strip(),
        "slug": slug,
        "description": fm.get("description", ""),
        "category": fm.get("category", "web"),
        "status": fm.get("status", "active"),
        "stack": fm.get("stack", []),
        "services": fm.get("services", []),
        "localPath": local_path,
        "githubUrl": f"https://github.com/{github}" if github else None,
        "featured": fm.get("status") == "active",  # Active projects are featured
        **git,
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read().decode())
        action = result.get("action", "?")
        print(f"  {'✅' if action == 'created' else '🔄'} {slug} — {action}")
    except Exception as e:
        err = e.read().decode() if hasattr(e, "read") else str(e)
        print(f"  ❌ {slug} — {err[:120]}")


def main():
    if not API_KEY:
        print("❌ PORTFOLIO_API_KEY not found in .env")
        return

    print("🚀 Syncing projects to nzt108.dev...\n")

    count = 0
    for project_dir in sorted(VAULT.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith("_"):
            continue

        prd = project_dir / "prd.md"
        if not prd.exists():
            continue

        fm = parse_frontmatter(prd)
        if not fm:
            continue

        sync_project(fm)
        count += 1

    print(f"\n✅ Synced {count} projects")


if __name__ == "__main__":
    main()
