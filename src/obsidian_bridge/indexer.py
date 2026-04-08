"""Indexer module — chunks notes and stores embeddings in ChromaDB.

v0.3.0: Hybrid RAG — Vector + BM25 keyword search + RRF fusion + Cross-Encoder reranking
         + MMR diversity + near-duplicate detection.
"""
import logging
import re

import chromadb
from chromadb.config import Settings as ChromaSettings
from rank_bm25 import BM25Okapi

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
# BM25 Keyword Index
# ---------------------------------------------------------------------------

_TOKENIZE_PATTERN = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9_\-\.]+")


def _tokenize(text: str) -> list[str]:
    """Tokenize text for BM25. Handles English, Russian, technical terms."""
    return _TOKENIZE_PATTERN.findall(text.lower())


class BM25Index:
    """In-memory BM25 keyword index over document chunks."""

    def __init__(self):
        self._doc_ids: list[str] = []
        self._doc_texts: list[str] = []
        self._doc_metadata: list[dict] = []
        self._bm25: BM25Okapi | None = None

    @property
    def count(self) -> int:
        return len(self._doc_ids)

    def build(self, doc_ids: list[str], documents: list[str], metadatas: list[dict]):
        """Build BM25 index from document list."""
        self._doc_ids = doc_ids
        self._doc_texts = documents
        self._doc_metadata = metadatas

        tokenized_corpus = [_tokenize(doc) for doc in documents]
        self._bm25 = BM25Okapi(tokenized_corpus)
        logger.info(f"BM25 index built: {len(doc_ids)} documents")

    def search(
        self,
        query: str,
        n_results: int = 10,
        project: str | None = None,
    ) -> list[dict]:
        """BM25 keyword search. Returns list of {doc_id, text, metadata, score}."""
        if self._bm25 is None or not self._doc_ids:
            return []

        tokenized_query = _tokenize(query)
        if not tokenized_query:
            return []

        scores = self._bm25.get_scores(tokenized_query)

        # Pair scores with indices, filter by project if needed
        scored = []
        for idx, score in enumerate(scores):
            if score <= 0:
                continue
            if project and self._doc_metadata[idx].get("project") != project:
                continue
            scored.append((idx, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in scored[:n_results]:
            results.append({
                "doc_id": self._doc_ids[idx],
                "text": self._doc_texts[idx],
                "metadata": self._doc_metadata[idx],
                "score": float(score),
            })

        return results


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def reciprocal_rank_fusion(
    vector_results: list[dict],
    bm25_results: list[dict],
    vector_weight: float = 1.0,
    bm25_weight: float = 1.0,
    k: int = 60,
    n_results: int = 10,
) -> list[dict]:
    """Merge vector and BM25 results using Reciprocal Rank Fusion.

    RRF score = sum(weight / (k + rank)) across both result lists.
    k=60 is the standard constant that prevents high-ranked items from dominating.

    Returns merged list sorted by RRF score, deduplicated by doc text.
    """
    # Use text as key for dedup (doc_ids may differ between vector and BM25)
    scored: dict[str, dict] = {}  # text -> {data, rrf_score}

    for rank, item in enumerate(vector_results):
        text = item["text"]
        rrf = vector_weight / (k + rank + 1)
        if text in scored:
            scored[text]["rrf_score"] += rrf
        else:
            scored[text] = {
                "text": text,
                "source": item.get("source", item.get("metadata", {}).get("source", "")),
                "project": item.get("project", item.get("metadata", {}).get("project", "")),
                "type": item.get("type", item.get("metadata", {}).get("type", "")),
                "tags": item.get("tags", item.get("metadata", {}).get("tags", "")),
                "section": item.get("section", item.get("metadata", {}).get("section", "")),
                "rrf_score": rrf,
                "vector_rank": rank + 1,
                "bm25_rank": None,
            }

    for rank, item in enumerate(bm25_results):
        text = item["text"]
        rrf = bm25_weight / (k + rank + 1)
        if text in scored:
            scored[text]["rrf_score"] += rrf
            scored[text]["bm25_rank"] = rank + 1
        else:
            meta = item.get("metadata", {})
            tags = meta.get("tags", "")
            scored[text] = {
                "text": text,
                "source": meta.get("source", ""),
                "project": meta.get("project", ""),
                "type": meta.get("type", ""),
                "tags": tags,
                "section": meta.get("section", ""),
                "rrf_score": rrf,
                "vector_rank": None,
                "bm25_rank": rank + 1,
            }

    # Sort by RRF score descending
    merged = sorted(scored.values(), key=lambda x: x["rrf_score"], reverse=True)

    return merged[:n_results]


# ---------------------------------------------------------------------------
# Cross-Encoder Reranker
# ---------------------------------------------------------------------------

class Reranker:
    """Cross-Encoder reranker for precise relevance scoring."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self._model_name = model_name
        self._model = None

    def _load_model(self):
        """Lazy-load the model on first use."""
        if self._model is None:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading reranker model: {self._model_name}")
            self._model = CrossEncoder(self._model_name)
            logger.info("Reranker model loaded")

    def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int = 5,
    ) -> list[dict]:
        """Rerank candidates using cross-encoder. Returns top_k with rerank_score."""
        if not candidates:
            return []

        self._load_model()

        pairs = [[query, c["text"]] for c in candidates]
        scores = self._model.predict(pairs)

        for candidate, score in zip(candidates, scores):
            candidate["rerank_score"] = float(score)

        # Sort by rerank score (higher = more relevant)
        reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)

        return reranked[:top_k]


# ---------------------------------------------------------------------------
# Near-Duplicate Detection
# ---------------------------------------------------------------------------

def _jaccard_similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
    """Jaccard similarity between two token sets."""
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def deduplicate_results(
    results: list[dict],
    threshold: float = 0.85,
) -> list[dict]:
    """Remove near-duplicate results based on Jaccard token similarity.

    Two results with Jaccard similarity >= threshold are considered duplicates.
    Keeps the first (higher-scored) version.
    """
    if not results:
        return []

    deduped = []
    seen_token_sets: list[set[str]] = []

    for result in results:
        tokens = set(_tokenize(result["text"]))
        is_dup = False
        for seen in seen_token_sets:
            if _jaccard_similarity(tokens, seen) >= threshold:
                is_dup = True
                break
        if not is_dup:
            deduped.append(result)
            seen_token_sets.append(tokens)

    if len(results) != len(deduped):
        logger.info(f"Dedup: {len(results)} -> {len(deduped)} results (removed {len(results) - len(deduped)} near-duplicates)")

    return deduped


# ---------------------------------------------------------------------------
# MMR (Maximal Marginal Relevance) Diversity
# ---------------------------------------------------------------------------

def mmr_diversify(
    results: list[dict],
    lambda_param: float = 0.7,
    top_k: int = 5,
) -> list[dict]:
    """Maximal Marginal Relevance: balance relevance with diversity.

    Prevents returning 10 copies of your loudest thought.
    Uses Jaccard similarity on tokens for O(n²) but fast at small scale.

    lambda_param: 0.0 = full diversity, 1.0 = full relevance.
    """
    if len(results) <= top_k:
        return results

    # Pre-tokenize all results
    token_sets = [set(_tokenize(r["text"])) for r in results]

    # Get relevance scores (use rerank_score, rrf_score, or score)
    def _get_score(r: dict) -> float:
        return r.get("rerank_score", r.get("rrf_score", r.get("score", 0)))

    # Normalize scores to [0, 1]
    scores = [_get_score(r) for r in results]
    max_score = max(scores) if scores else 1.0
    min_score = min(scores) if scores else 0.0
    score_range = max_score - min_score if max_score != min_score else 1.0
    norm_scores = [(s - min_score) / score_range for s in scores]

    selected_indices: list[int] = []
    remaining_indices = list(range(len(results)))

    # Always pick the most relevant first
    best_idx = max(remaining_indices, key=lambda i: norm_scores[i])
    selected_indices.append(best_idx)
    remaining_indices.remove(best_idx)

    while len(selected_indices) < top_k and remaining_indices:
        best_mmr_score = -float("inf")
        best_candidate = remaining_indices[0]

        for cand_idx in remaining_indices:
            # Relevance component
            relevance = norm_scores[cand_idx]

            # Diversity component: max similarity to any already selected
            max_sim = 0.0
            for sel_idx in selected_indices:
                sim = _jaccard_similarity(token_sets[cand_idx], token_sets[sel_idx])
                max_sim = max(max_sim, sim)

            # MMR score
            mmr_score = lambda_param * relevance - (1.0 - lambda_param) * max_sim

            if mmr_score > best_mmr_score:
                best_mmr_score = mmr_score
                best_candidate = cand_idx

        selected_indices.append(best_candidate)
        remaining_indices.remove(best_candidate)

    return [results[i] for i in selected_indices]


# ---------------------------------------------------------------------------
# ChromaDB + Hybrid Index
# ---------------------------------------------------------------------------

class VaultIndex:
    """Manages the ChromaDB vector index + BM25 keyword index for the vault.

    v0.2.0: Hybrid search pipeline:
    1. ChromaDB vector search (semantic similarity)
    2. BM25 keyword search (exact term matching)
    3. RRF fusion (merge + deduplicate)
    4. Cross-Encoder reranking (optional, precise relevance)
    """

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

        # BM25 index (in-memory, rebuilt from ChromaDB on init)
        self._bm25_index = BM25Index()
        self._rebuild_bm25()

        # Reranker (lazy-loaded)
        self._reranker: Reranker | None = None
        if settings.reranking:
            self._reranker = Reranker(settings.rerank_model)

    def _rebuild_bm25(self):
        """Rebuild BM25 index from current ChromaDB contents."""
        count = self._collection.count()
        if count == 0:
            logger.info("ChromaDB empty, skipping BM25 build")
            return

        all_data = self._collection.get(include=["documents", "metadatas"])
        if all_data and all_data["ids"]:
            self._bm25_index.build(
                doc_ids=all_data["ids"],
                documents=all_data["documents"],
                metadatas=all_data["metadatas"],
            )

    @property
    def count(self) -> int:
        """Number of chunks in the index."""
        return self._collection.count()

    def index_notes(self, notes: list[Note]) -> dict:
        """Index a list of notes into ChromaDB + BM25.

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

            # Check if already indexed
            existing = self._collection.get(
                where={"source": str(note.path)},
                include=[],
            )

            if existing and existing["ids"]:
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

        # Rebuild BM25 after indexing
        self._rebuild_bm25()

        return stats

    def search(
        self,
        query: str,
        n_results: int = 10,
        project: str | None = None,
        note_type: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict]:
        """Hybrid search across the vault.

        Pipeline:
        1. Vector search (ChromaDB) — semantic similarity
        2. BM25 search — keyword matching (if hybrid enabled)
        3. RRF fusion — merge results
        4. Cross-Encoder reranking — precise relevance (if enabled)

        Returns list of {text, source, project, type, tags, score, search_method}.
        """
        use_hybrid = self.settings.hybrid_search and self._bm25_index.count > 0
        use_reranking = self.settings.reranking and self._reranker is not None

        # How many candidates to fetch (over-fetch for reranking)
        fetch_n = n_results * self.settings.retrieval_multiplier if use_reranking else n_results
        if use_hybrid:
            # Each source fetches fetch_n, then merged
            fetch_per_source = fetch_n
        else:
            fetch_per_source = fetch_n

        # --- Stage 1: Vector search (ChromaDB) ---
        vector_results = self._vector_search(query, fetch_per_source, project, note_type)

        if not use_hybrid:
            # Pure vector mode (original behavior)
            results = self._format_results(vector_results, tags, "vector")
            if use_reranking and results:
                results = self._reranker.rerank(query, results, top_k=n_results)
                for r in results:
                    r["search_method"] = "vector+rerank"
            return results[:n_results]

        # --- Stage 2: BM25 keyword search ---
        bm25_results = self._bm25_index.search(query, n_results=fetch_per_source, project=project)

        # --- Stage 3: RRF Fusion ---
        fused = reciprocal_rank_fusion(
            vector_results=vector_results,
            bm25_results=bm25_results,
            vector_weight=self.settings.vector_weight,
            bm25_weight=self.settings.bm25_weight,
            n_results=fetch_n,
        )

        # Apply tag filter if specified
        if tags:
            fused = [
                r for r in fused
                if set(str(r.get("tags", "")).split(",")).intersection(set(tags))
            ]

        # Set search method info
        for r in fused:
            methods = []
            if r.get("vector_rank"):
                methods.append(f"vec#{r['vector_rank']}")
            if r.get("bm25_rank"):
                methods.append(f"bm25#{r['bm25_rank']}")
            r["search_method"] = "+".join(methods) if methods else "hybrid"

        # --- Stage 4: Cross-Encoder Reranking ---
        if use_reranking and fused:
            fused = self._reranker.rerank(query, fused, top_k=max(n_results * 2, len(fused)))
            for r in fused:
                r["search_method"] += "+rerank"

        # --- Stage 5: Near-duplicate detection ---
        fused = deduplicate_results(fused, threshold=self.settings.dedup_threshold)

        # --- Stage 6: MMR Diversity ---
        use_mmr = self.settings.mmr_diversity
        if use_mmr and len(fused) > n_results:
            fused = mmr_diversify(
                fused,
                lambda_param=self.settings.mmr_lambda,
                top_k=n_results,
            )
            for r in fused:
                r["search_method"] = r.get("search_method", "") + "+mmr"

        # Format final output
        output = []
        for r in fused[:n_results]:
            tags_val = r.get("tags", "")
            if isinstance(tags_val, str):
                tags_list = tags_val.split(",") if tags_val else []
            else:
                tags_list = tags_val

            output.append({
                "text": r["text"],
                "source": r.get("source", ""),
                "project": r.get("project", ""),
                "type": r.get("type", ""),
                "tags": tags_list,
                "section": r.get("section", ""),
                "score": round(r.get("rerank_score", r.get("rrf_score", 0)), 4),
                "search_method": r.get("search_method", "hybrid"),
            })

        return output

    def _vector_search(
        self,
        query: str,
        n_results: int,
        project: str | None = None,
        note_type: str | None = None,
    ) -> list[dict]:
        """Raw vector search via ChromaDB."""
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
            output.append({
                "text": doc,
                "source": meta.get("source", ""),
                "project": meta.get("project", ""),
                "type": meta.get("type", ""),
                "tags": meta.get("tags", ""),
                "section": meta.get("section", ""),
                "score": round(1 - dist, 4),
            })

        return output

    def _format_results(
        self,
        raw: list[dict],
        tags: list[str] | None,
        method: str,
    ) -> list[dict]:
        """Format raw vector results with tag filtering."""
        output = []
        for r in raw:
            if tags:
                chunk_tags = set(str(r.get("tags", "")).split(","))
                if not chunk_tags.intersection(set(tags)):
                    continue
            tags_val = r.get("tags", "")
            output.append({
                "text": r["text"],
                "source": r.get("source", ""),
                "project": r.get("project", ""),
                "type": r.get("type", ""),
                "tags": tags_val.split(",") if isinstance(tags_val, str) else tags_val,
                "section": r.get("section", ""),
                "score": r.get("score", 0),
                "search_method": method,
            })
        return output

    def clear(self):
        """Delete all data from the index."""
        self._client.delete_collection(self.COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._bm25_index = BM25Index()

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
            "hybrid_search": self.settings.hybrid_search,
            "reranking": self.settings.reranking,
            "bm25_docs": self._bm25_index.count,
        }
