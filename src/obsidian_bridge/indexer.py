"""Indexer module — chunks notes and stores embeddings in ChromaDB."""
import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from obsidian_bridge.config import Settings
from obsidian_bridge.models import Chunk, Note

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _split_by_sections(content: str) -> list[tuple[str, str]]:
    """Split markdown content by headings. Returns (section_title, text) pairs."""
    lines = content.split("\n")
    sections: list[tuple[str, str]] = []
    current_section = ""
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("#"):
            if current_lines:
                sections.append((current_section, "\n".join(current_lines).strip()))
            current_section = line.lstrip("#").strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_section, "\n".join(current_lines).strip()))

    return sections


def chunk_note(note: Note, chunk_size: int = 500, chunk_overlap: int = 50) -> list[Chunk]:
    """Split a note into chunks suitable for embedding.

    Strategy:
    1. Split by markdown headings (sections)
    2. If a section is too long, split by chunk_size with overlap
    3. Prepend note title and project context to each chunk
    """
    chunks: list[Chunk] = []
    sections = _split_by_sections(note.content)
    chunk_index = 0

    context_prefix = f"[Project: {note.project}] [{note.note_type}] {note.title}\n\n"

    for section_title, section_text in sections:
        if not section_text.strip():
            continue

        full_text = context_prefix + section_text

        if len(full_text) <= chunk_size:
            chunks.append(Chunk(
                text=full_text,
                source_path=str(note.path),
                project=note.project,
                note_type=note.note_type,
                tags=note.tags,
                section=section_title,
                chunk_index=chunk_index,
            ))
            chunk_index += 1
        else:
            # Split long section into overlapping chunks
            start = 0
            text_to_split = full_text
            while start < len(text_to_split):
                end = start + chunk_size
                chunk_text = text_to_split[start:end]

                # Try to break at a sentence boundary
                if end < len(text_to_split):
                    last_period = chunk_text.rfind(". ")
                    last_newline = chunk_text.rfind("\n")
                    break_at = max(last_period, last_newline)
                    if break_at > chunk_size // 2:
                        chunk_text = text_to_split[start : start + break_at + 1]
                        end = start + break_at + 1

                if chunk_text.strip():
                    chunks.append(Chunk(
                        text=chunk_text.strip(),
                        source_path=str(note.path),
                        project=note.project,
                        note_type=note.note_type,
                        tags=note.tags,
                        section=section_title,
                        chunk_index=chunk_index,
                    ))
                    chunk_index += 1

                start = end - chunk_overlap

    return chunks


# ---------------------------------------------------------------------------
# ChromaDB Index
# ---------------------------------------------------------------------------

class VaultIndex:
    """Manages the ChromaDB vector index for the vault."""

    COLLECTION_NAME = "obsidian_vault"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.chroma_path = settings.chroma_path
        self.chroma_path.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=str(self.chroma_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def count(self) -> int:
        """Number of chunks in the index."""
        return self._collection.count()

    def index_notes(self, notes: list[Note]) -> dict:
        """Index a list of notes into ChromaDB.

        Returns dict with stats: {added, updated, skipped, total_chunks}.
        """
        stats = {"added": 0, "updated": 0, "skipped": 0, "total_chunks": 0}

        for note in notes:
            chunks = chunk_note(
                note,
                chunk_size=self.settings.chunk_size,
                chunk_overlap=self.settings.chunk_overlap,
            )
            stats["total_chunks"] += len(chunks)

            # Check if already indexed with same checksum
            existing = self._collection.get(
                where={"source": str(note.path)},
                include=[],
            )

            if existing and existing["ids"]:
                # Delete old chunks for this file
                self._collection.delete(ids=existing["ids"])
                stats["updated"] += 1
            else:
                stats["added"] += 1

            if not chunks:
                continue

            self._collection.add(
                ids=[c.doc_id for c in chunks],
                documents=[c.text for c in chunks],
                metadatas=[c.metadata for c in chunks],
            )

        return stats

    def search(
        self,
        query: str,
        n_results: int = 10,
        project: str | None = None,
        note_type: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict]:
        """Semantic search across the vault.

        Returns list of {text, source, project, type, tags, score}.
        """
        where_filter = {}
        if project:
            where_filter["project"] = project
        if note_type:
            where_filter["type"] = note_type

        results = self._collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter if where_filter else None,
            include=["documents", "metadatas", "distances"],
        )

        if not results or not results["documents"] or not results["documents"][0]:
            return []

        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            # Filter by tags if specified (post-filter since ChromaDB doesn't support array contains)
            if tags:
                chunk_tags = set(meta.get("tags", "").split(","))
                if not chunk_tags.intersection(set(tags)):
                    continue

            output.append({
                "text": doc,
                "source": meta.get("source", ""),
                "project": meta.get("project", ""),
                "type": meta.get("type", ""),
                "tags": meta.get("tags", "").split(","),
                "section": meta.get("section", ""),
                "score": round(1 - dist, 4),  # Convert distance to similarity
            })

        return output

    def clear(self):
        """Delete all data from the index."""
        self._client.delete_collection(self.COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def get_stats(self) -> dict:
        """Get index statistics."""
        all_meta = self._collection.get(include=["metadatas"])
        projects = set()
        types = set()
        sources = set()

        for meta in (all_meta.get("metadatas") or []):
            projects.add(meta.get("project", ""))
            types.add(meta.get("type", ""))
            sources.add(meta.get("source", ""))

        return {
            "total_chunks": self.count,
            "total_notes": len(sources),
            "projects": sorted(p for p in projects if p),
            "types": sorted(t for t in types if t),
        }
