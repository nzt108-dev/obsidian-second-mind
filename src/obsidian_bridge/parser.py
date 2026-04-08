"""Markdown parser for Obsidian vault notes."""
import hashlib
import re
from pathlib import Path
from typing import Optional

import frontmatter

from obsidian_bridge.models import Note


# Patterns for Obsidian-specific syntax
WIKILINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
EMBED_PATTERN = re.compile(r"!\[\[([^\]]+)\]\]")
TAG_INLINE_PATTERN = re.compile(r"(?:^|\s)#([a-zA-Z0-9_-]+)", re.MULTILINE)


def _compute_checksum(content: str) -> str:
    """Compute MD5 checksum of file content."""
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def _extract_title(path: Path, content: str) -> str:
    """Extract title from first H1 heading or filename."""
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# ") and not line.startswith("##"):
            return line[2:].strip()
    return path.stem.replace("-", " ").replace("_", " ").title()


def _extract_inline_tags(content: str) -> list[str]:
    """Extract inline #tags from markdown content."""
    return list(set(TAG_INLINE_PATTERN.findall(content)))


def _resolve_wikilinks(content: str) -> str:
    """Convert [[wikilinks]] to plain text for embedding."""
    def replace_link(match):
        display = match.group(2) or match.group(1)
        return display
    return WIKILINK_PATTERN.sub(replace_link, content)


def _clean_for_embedding(content: str) -> str:
    """Clean markdown content for embedding (remove noise, keep substance)."""
    content = _resolve_wikilinks(content)
    content = EMBED_PATTERN.sub("", content)  # Remove embeds
    # Remove excessive whitespace
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def parse_note(file_path: Path, vault_path: Path) -> Optional[Note]:
    """Parse a single markdown file into a Note object.

    Args:
        file_path: Absolute path to the .md file.
        vault_path: Root path of the Obsidian vault.

    Returns:
        A Note object, or None if the file cannot be parsed.
    """
    try:
        raw_content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    # Parse frontmatter
    post = frontmatter.loads(raw_content)
    fm = post.metadata

    # Extract tags from frontmatter + inline
    fm_tags = fm.get("tags", [])
    if isinstance(fm_tags, str):
        fm_tags = [t.strip() for t in fm_tags.split(",")]
    inline_tags = _extract_inline_tags(post.content)
    all_tags = list(set(str(t) for t in fm_tags + inline_tags))

    # Determine project from frontmatter or folder structure
    project = fm.get("project", "")
    if not project:
        relative = file_path.relative_to(vault_path)
        parts = relative.parts
        if len(parts) > 1 and not parts[0].startswith("_"):
            project = parts[0]

    # Clean content for embedding
    clean_content = _clean_for_embedding(post.content)

    return Note(
        path=file_path.relative_to(vault_path),
        title=_extract_title(file_path, post.content),
        content=clean_content,
        raw_content=raw_content,
        project=project,
        note_type=fm.get("type", "note"),
        tags=all_tags,
        priority=fm.get("priority", "medium"),
        created=fm.get("created"),
        updated=fm.get("updated"),
        checksum=_compute_checksum(raw_content),
        metadata=fm,
    )


def scan_vault(vault_path: Path, filter_tags: Optional[list[str]] = None) -> list[Note]:
    """Recursively scan the vault and parse all markdown files.

    Args:
        vault_path: Root path of the Obsidian vault.
        filter_tags: If provided, only return notes matching these tags.
                    If None, return all notes.

    Returns:
        List of parsed Note objects.
    """
    if not vault_path.exists():
        raise FileNotFoundError(f"Vault path does not exist: {vault_path}")

    notes: list[Note] = []

    for md_file in sorted(vault_path.rglob("*.md")):
        # Skip hidden directories and templates
        parts = md_file.relative_to(vault_path).parts
        if any(p.startswith(".") for p in parts):
            continue
        if "_templates" in parts:
            continue

        note = parse_note(md_file, vault_path)
        if note is None:
            continue

        # Apply tag filter
        if filter_tags:
            note_tags_lower = {t.lower() for t in note.tags}
            filter_lower = {t.lower() for t in filter_tags}
            if not note_tags_lower.intersection(filter_lower):
                # Also check note_type as implicit tag
                if note.note_type.lower() not in filter_lower:
                    continue

        notes.append(note)

    return notes


def get_projects(vault_path: Path) -> list[str]:
    """List all project directories in the vault."""
    projects = []
    for item in sorted(vault_path.iterdir()):
        if item.is_dir() and not item.name.startswith((".", "_")):
            projects.append(item.name)
    return projects


def get_project_notes(vault_path: Path, project: str) -> list[Note]:
    """Get all notes for a specific project."""
    project_dir = vault_path / project
    if not project_dir.exists():
        return []

    notes = []
    for md_file in sorted(project_dir.rglob("*.md")):
        note = parse_note(md_file, vault_path)
        if note:
            notes.append(note)
    return notes
