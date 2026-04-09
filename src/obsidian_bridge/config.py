"""Configuration management for Obsidian Bridge."""
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    vault_path: Path = Field(
        default=Path.home() / "SecondMind",
        description="Path to the Obsidian vault directory",
    )
    chroma_path: Path = Field(
        default=Path.home() / ".obsidian-bridge" / "chroma",
        description="Path to ChromaDB persistent storage",
    )
    host: str = Field(default="127.0.0.1", description="Server host")
    port: int = Field(default=9108, description="Server port")
    chunk_size: int = Field(default=500, description="Chunk size in characters")
    chunk_overlap: int = Field(default=50, description="Chunk overlap in characters")
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence-transformers model for embeddings",
    )
    filter_tags: list[str] = Field(
        default_factory=lambda: [
            "architecture", "prd", "guidelines", "api", "rules",
            "business-logic", "decision", "standards",
        ],
        description="Default tags to filter for context",
    )
    watch_debounce: float = Field(
        default=2.0,
        description="Debounce time in seconds for file watcher",
    )

    # --- Hybrid Search Settings ---
    hybrid_search: bool = Field(
        default=True,
        description="Enable hybrid search (vector + BM25 keyword). Disable for pure vector.",
    )
    reranking: bool = Field(
        default=True,
        description="Enable Cross-Encoder reranking of search results.",
    )
    rerank_model: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        description="Cross-encoder model for reranking.",
    )
    bm25_weight: float = Field(
        default=1.0,
        description="BM25 weight in RRF fusion (relative to vector weight).",
    )
    vector_weight: float = Field(
        default=1.0,
        description="Vector search weight in RRF fusion.",
    )
    retrieval_multiplier: int = Field(
        default=3,
        description="Over-fetch multiplier for hybrid retrieval (fetch N*multiplier, rerank to N).",
    )

    # --- MMR Diversity Settings ---
    mmr_diversity: bool = Field(
        default=True,
        description="Enable MMR diversity reranking to avoid returning near-duplicate results.",
    )
    mmr_lambda: float = Field(
        default=0.7,
        description="MMR lambda: 0.0 = full diversity, 1.0 = full relevance. 0.7 is a good balance.",
    )
    dedup_threshold: float = Field(
        default=0.85,
        description="Jaccard similarity threshold for near-duplicate detection (0-1).",
    )

    # --- Lint Settings ---
    lint_stale_days: int = Field(
        default=90,
        description="Notes not updated for this many days are flagged as stale.",
    )

    # --- Decay Settings ---
    decay_enabled: bool = Field(
        default=True,
        description="Enable freshness decay in search scoring. Fresh notes rank higher.",
    )
    decay_lambda: float = Field(
        default=0.005,
        description="Decay rate. 0.005 = half-life ~139 days. Higher = faster decay.",
    )

    # --- Scout / Intelligence Settings ---
    project_base_dirs: list[str] = Field(
        default_factory=lambda: [str(Path.home() / "Projects")],
        description="Base directories where projects live on local filesystem.",
    )
    scout_http_timeout: float = Field(
        default=15.0,
        description="HTTP timeout for Tech Radar and Dependency Watch requests.",
    )

    # --- Telegram Bot Settings (v0.6.0) ---
    telegram_bot_token: str = Field(
        default="",
        description="Telegram bot token from @BotFather. Required for capture bot.",
    )
    telegram_allowed_users: list[int] = Field(
        default_factory=list,
        description="Telegram user IDs allowed to use the bot. Empty = allow all.",
    )
    telegram_default_project: str = Field(
        default="inbox",
        description="Default project for notes captured without @project prefix.",
    )

    model_config = {"env_prefix": "OBSIDIAN_BRIDGE_", "env_file": ".env"}


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
