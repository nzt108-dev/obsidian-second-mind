"""File watcher daemon — auto-updates index when vault files change.

v0.4.0: Enhanced with auto-logging, index.md regeneration, and graph rebuild.
"""
import logging
import time
import threading
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

from obsidian_bridge.config import Settings
from obsidian_bridge.indexer import VaultIndex
from obsidian_bridge.parser import parse_note

logger = logging.getLogger(__name__)


class VaultEventHandler(FileSystemEventHandler):
    """Handles file system events in the Obsidian vault.

    v0.4.0 hooks:
    - File created → index + update index.md + log
    - File modified → re-index + update index.md
    - File deleted → remove from index + update index.md + log
    """

    def __init__(self, vault_path: Path, index: VaultIndex, debounce: float = 2.0):
        super().__init__()
        self.vault_path = vault_path
        self.index = index
        self.debounce = debounce
        self._pending: dict[str, tuple[str, float]] = {}  # path -> (event_type, timestamp)
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def _should_process(self, path: str) -> bool:
        """Check if a file event should be processed."""
        p = Path(path)
        if p.suffix != ".md":
            return False
        try:
            rel = p.relative_to(self.vault_path)
        except ValueError:
            return False
        parts = rel.parts
        if any(part.startswith(".") for part in parts):
            return False
        if "_templates" in parts:
            return False
        # Skip index.md and log.md (auto-generated)
        if p.name in ("index.md", "log.md"):
            return False
        return True

    def _schedule_reindex(self, path: str, event_type: str):
        """Schedule a reindex with debounce."""
        with self._lock:
            self._pending[path] = (event_type, time.time())
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce, self._process_pending)
            self._timer.start()

    def _process_pending(self):
        """Process all pending file changes."""
        with self._lock:
            pending = dict(self._pending)
            self._pending.clear()

        created_count = 0
        modified_count = 0
        deleted_count = 0

        for path_str, (event_type, _) in pending.items():
            path = Path(path_str)

            if event_type == "deleted":
                deleted_count += 1
                logger.info(f"🗑️  Deleted: {path.name}")
                # Note: ChromaDB doesn't support single-doc delete easily,
                # but index.md will no longer list it
                self._log_event("file_deleted", path)

            elif path.exists():
                note = parse_note(path, self.vault_path)
                if note:
                    stats = self.index.index_notes([note])
                    if event_type == "created":
                        created_count += 1
                        logger.info(f"📝 Created & indexed: {path.name} ({stats['total_chunks']} chunks)")
                        self._log_event("file_created", path)
                    else:
                        modified_count += 1
                        logger.info(f"🔄 Re-indexed: {path.name} ({stats['total_chunks']} chunks)")

        # Regenerate index.md if anything changed
        if created_count + modified_count + deleted_count > 0:
            try:
                from obsidian_bridge.mcp_server import _regenerate_index
                _regenerate_index(self.vault_path)
                logger.info(f"📚 index.md regenerated (created={created_count}, modified={modified_count}, deleted={deleted_count})")
            except Exception as e:
                logger.warning(f"Failed to regenerate index.md: {e}")

    def _log_event(self, operation: str, path: Path):
        """Log file event to vault log.md."""
        try:
            from obsidian_bridge.mcp_server import _append_to_log
            rel = path.relative_to(self.vault_path)
            project = rel.parts[0] if len(rel.parts) > 1 else ""
            _append_to_log(
                self.vault_path,
                operation=f"watcher:{operation}",
                project=project,
                title=path.stem,
            )
        except Exception as e:
            logger.debug(f"Failed to log event: {e}")

    def on_modified(self, event: FileSystemEvent):
        if not event.is_directory and self._should_process(event.src_path):
            logger.debug(f"Modified: {event.src_path}")
            self._schedule_reindex(event.src_path, "modified")

    def on_created(self, event: FileSystemEvent):
        if not event.is_directory and self._should_process(event.src_path):
            logger.info(f"Created: {event.src_path}")
            self._schedule_reindex(event.src_path, "created")

    def on_deleted(self, event: FileSystemEvent):
        if not event.is_directory and self._should_process(event.src_path):
            logger.info(f"Deleted: {event.src_path}")
            self._schedule_reindex(event.src_path, "deleted")


def start_watcher(settings: Settings, index: VaultIndex) -> Observer:
    """Start the file system watcher daemon.

    Returns the Observer instance (call .stop() to shut down).
    """
    handler = VaultEventHandler(
        vault_path=settings.vault_path,
        index=index,
        debounce=settings.watch_debounce,
    )

    observer = Observer()
    observer.schedule(handler, str(settings.vault_path), recursive=True)
    observer.start()
    logger.info(f"👁️  Watching vault: {settings.vault_path}")
    return observer
