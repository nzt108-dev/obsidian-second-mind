"""Dashboard data generator — reads vault PRD files and git info to build project JSON."""
import json
import subprocess
import yaml
from pathlib import Path
from typing import Any

from .config import get_settings


def _run_git(project_path: str, args: list[str]) -> str | None:
    """Run a git command in the project directory, return stdout or None."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _parse_frontmatter(filepath: Path) -> dict[str, Any]:
    """Parse YAML frontmatter from a markdown file."""
    content = filepath.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def _extract_whats_next(filepath: Path, max_items: int = 3) -> list[str]:
    """Extract top N items from 'What's Next' section of a PRD."""
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")
    in_section = False
    items = []
    for line in lines:
        if "what's next" in line.lower() or "what to do" in line.lower():
            in_section = True
            continue
        if in_section:
            stripped = line.strip()
            if stripped.startswith(("#", "##")):
                break
            if stripped and (stripped[0].isdigit() or stripped.startswith("-")):
                # Clean up: remove leading number/dash/dot
                clean = stripped.lstrip("0123456789.-) ").strip()
                if clean:
                    items.append(clean)
                    if len(items) >= max_items:
                        break
    return items


def generate_projects_data() -> list[dict[str, Any]]:
    """Generate full project data from vault PRDs + git info."""
    settings = get_settings()
    vault = settings.vault_path
    projects = []

    # Find all project directories in vault (skip _global, _inbox, _templates)
    for project_dir in sorted(vault.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith("_"):
            continue

        prd_path = project_dir / "prd.md"
        if not prd_path.exists():
            continue

        fm = _parse_frontmatter(prd_path)
        if not fm:
            continue

        project_name = fm.get("project", project_dir.name)
        local_path = fm.get("path", "")
        github = fm.get("github", "")

        # Git info
        last_commit_msg = None
        last_commit_date = None
        last_commit_hash = None
        if local_path and Path(local_path).exists():
            last_commit_msg = _run_git(local_path, ["log", "-1", "--format=%s"])
            last_commit_date = _run_git(local_path, ["log", "-1", "--format=%ci"])
            last_commit_hash = _run_git(local_path, ["log", "-1", "--format=%h"])

        projects.append({
            "id": project_name,
            "title": fm.get("title", project_name),
            "description": fm.get("description", ""),
            "status": fm.get("status", "unknown"),
            "category": fm.get("category", "other"),
            "stack": fm.get("stack", []),
            "services": fm.get("services", []),
            "tags": fm.get("tags", []),
            "path": local_path,
            "github": github,
            "github_url": f"https://github.com/{github}" if github else "",
            "whats_next": _extract_whats_next(prd_path),
            "last_commit": {
                "message": last_commit_msg,
                "date": last_commit_date,
                "hash": last_commit_hash,
            } if last_commit_msg else None,
        })

    return projects


def generate_json(output_path: Path | None = None) -> str:
    """Generate and optionally save projects JSON."""
    data = generate_projects_data()
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    if output_path:
        output_path.write_text(json_str, encoding="utf-8")
    return json_str
