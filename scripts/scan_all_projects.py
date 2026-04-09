#!/usr/bin/env python3
"""Generate architecture maps for ALL projects in ~/Projects.

Usage:
    python scripts/scan_all_projects.py              # Scan all
    python scripts/scan_all_projects.py architect-portfolio  # Scan one

Generates:
    - {project}/architecture-map.md in the vault (Mermaid)
    - {project}/data-flow-map.html in each project dir (interactive HTML)
"""
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from obsidian_bridge.config import get_settings
from obsidian_bridge.architect import ProjectScanner, scan_and_save

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

PROJECTS_DIR = Path.home() / "Projects"
SKIP_PROJECTS = {".DS_Store"}


def scan_project(project_name: str, vault_path: Path):
    """Scan one project and save architecture map to vault."""
    project_dir = PROJECTS_DIR / project_name
    if not project_dir.is_dir():
        return

    logger.info(f"\n{'='*50}")
    logger.info(f"🔍 Scanning: {project_name}")
    logger.info(f"{'='*50}")

    scanner = ProjectScanner(project_dir, project_name)
    arch = scanner.scan()

    if not arch.modules:
        logger.info(f"   ⏭️  No source files found, skipping")
        return

    # Save to vault
    result = scan_and_save(
        vault_path=vault_path,
        project=project_name,
        project_base_dirs=[str(PROJECTS_DIR)],
    )

    logger.info(f"   ✅ {len(arch.modules)} modules, "
                f"{len(arch.edges)} deps, "
                f"{arch.stats.get('total_lines', 0)} lines")
    logger.info(f"   📄 Saved to vault: {project_name}/architecture-map.md")


def main():
    settings = get_settings()
    vault_path = Path(settings.vault_path)

    # Specific project or all?
    if len(sys.argv) > 1:
        projects = [sys.argv[1]]
    else:
        projects = sorted([
            p.name for p in PROJECTS_DIR.iterdir()
            if p.is_dir() and p.name not in SKIP_PROJECTS
        ])

    logger.info(f"🗺️  Architecture Scanner — {len(projects)} projects")
    logger.info(f"   Vault: {vault_path}")
    logger.info(f"   Projects: {PROJECTS_DIR}")

    scanned = 0
    for project in projects:
        try:
            scan_project(project, vault_path)
            scanned += 1
        except Exception as e:
            logger.error(f"   ❌ Error scanning {project}: {e}")

    logger.info(f"\n{'='*50}")
    logger.info(f"🎉 Done! Scanned {scanned}/{len(projects)} projects")
    logger.info(f"   Architecture maps saved to vault")


if __name__ == "__main__":
    main()
