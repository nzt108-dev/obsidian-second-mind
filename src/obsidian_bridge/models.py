"""Data models for parsed Obsidian notes."""
from dataclasses import dataclass, field
from pathlib import Path
from datetime import date
from typing import Optional


@dataclass
class Note:
    """Represents a parsed Obsidian markdown note."""

    path: Path
    title: str
    content: str
    raw_content: str
    project: str = ""
    note_type: str = ""  # prd, architecture, guidelines, decision, api, note
    tags: list[str] = field(default_factory=list)
    priority: str = "medium"
    created: Optional[date] = None
    updated: Optional[date] = None
    checksum: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def relative_path(self) -> str:
        """Get path relative to vault root."""
        return str(self.path)

    @property
    def slug(self) -> str:
        """Get a URL-friendly slug."""
        return self.path.stem


@dataclass
class Chunk:
    """A chunk of text from a note, ready for embedding."""

    text: str
    source_path: str
    project: str
    note_type: str
    tags: list[str]
    section: str = ""
    chunk_index: int = 0

    @property
    def metadata(self) -> dict:
        """Metadata dict for ChromaDB."""
        return {
            "source": self.source_path,
            "project": self.project,
            "type": self.note_type,
            "tags": ",".join(self.tags),
            "section": self.section,
            "chunk_index": self.chunk_index,
        }

    @property
    def doc_id(self) -> str:
        """Unique document ID for ChromaDB."""
        return f"{self.source_path}::chunk_{self.chunk_index}"
