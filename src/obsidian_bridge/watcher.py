"""File watcher daemon — auto-updates index when vault files change."""
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
    """Handles file system events in the Obsidian vault."""

    def __init__(self, vault_path: Path, index: VaultIndex, debounce: float = 2.0):
        super().__init__()
        self.vault_path = vault_path
        self.index = index
        self.debounce = debounce
        self._pending: dict[str, float] = {}
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
        return True

    def _schedule_reindex(self, path: str):
        """Schedule a reindex with debounce."""
        with self._lock:
            self._pending[path] = time.time()
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce, self._process_pending)
            self._timer.start()

    def _process_pending(self):
        """Process all pending file changes."""
        with self._lock:
            paths = list(self._pending.keys())
            self._pending.clear()

        for path_str in paths:
            path = Path(path_str)
            if path.exists():
                note = parse_note(path, self.vault_path)
                if note:
                    stats = self.index.index_notes([note])
                    logger.info(f"Re-indexed: {path.name} ({stats['total_chunks']} chunks)")
            else:
                logger.info(f"File deleted: {path.name}")

    def on_modified(self, event: FileSystemEvent):
        if not event.is_directory and self._should_process(event.src_path):
            logger.debug(f"Modified: {event.src_path}")
            self._schedule_reindex(event.src_path)

    def on_created(self, event: FileSystemEvent):
        if not event.is_directory and self._should_process(event.src_path):
            logger.info(f"Created: {event.src_path}")
            self._schedule_reindex(event.src_path)

    def on_deleted(self, event: FileSystemEvent):
        if not event.is_directory and self._should_process(event.src_path):
            logger.info(f"Deleted: {event.src_path}")


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
