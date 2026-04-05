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

    model_config = {"env_prefix": "OBSIDIAN_BRIDGE_", "env_file": ".env"}


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
