"""The index has one owner: the chroma server. Several writer processes go through it.

2026-10-05: MCP servers of every session, the inbox router and the CLI each opened
their own embedded PersistentClient on the same directory, and the index ended up
so corrupted that count() segfaulted.
"""
import multiprocessing as mp
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from obsidian_bridge.config import Settings
from obsidian_bridge.models import Note
from obsidian_bridge.parser import parse_note

CHROMA_BIN = Path(sys.executable).parent / "chroma"
WRITERS = 3
NOTES_PER_WRITER = 15


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def chroma_server(tmp_path):
    if not CHROMA_BIN.exists():
        pytest.skip("chroma CLI is not installed in this venv")
    port = _free_port()
    proc = subprocess.Popen(
        [str(CHROMA_BIN), "run", "--host", "127.0.0.1", "--port", str(port),
         "--path", str(tmp_path / "chroma")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{url}/api/v2/heartbeat", timeout=1)
            break
        except OSError:
            time.sleep(0.3)
    else:
        proc.kill()
        pytest.fail("chroma server did not start")
    yield url, tmp_path
    proc.terminate()
    proc.wait(timeout=10)


def _writer(url: str, vault: str, writer_id: int) -> None:
    from obsidian_bridge.indexer import VaultIndex

    settings = Settings(vault_path=Path(vault), chroma_url=url, reranking=False)
    index = VaultIndex(settings)
    for i in range(NOTES_PER_WRITER):
        index.index_notes([Note(
            path=Path(f"w{writer_id}/note-{i}.md"),
            title=f"Writer {writer_id} note {i}",
            content=f"Writer {writer_id} wrote note number {i} about topic {i % 4}.",
            raw_content="",
            project=f"w{writer_id}",
        )])


def test_parallel_writers_do_not_corrupt_index(chroma_server):
    url, tmp = chroma_server
    ctx = mp.get_context("spawn")
    procs = [ctx.Process(target=_writer, args=(url, str(tmp), w)) for w in range(WRITERS)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=300)
    assert [p.exitcode for p in procs] == [0] * WRITERS

    from obsidian_bridge.indexer import VaultIndex

    index = VaultIndex(Settings(vault_path=tmp, chroma_url=url, reranking=False))
    sources = {m["source"] for m in index._get_all(["metadatas"])["metadatas"]}
    assert len(sources) == WRITERS * NOTES_PER_WRITER
    assert index.count >= WRITERS * NOTES_PER_WRITER
    assert index.search("Writer 2 note 7", n_results=3)


def test_unreachable_server_fails_loudly_without_embedded_fallback(tmp_path):
    from obsidian_bridge.indexer import VaultIndex

    settings = Settings(vault_path=tmp_path, chroma_path=tmp_path / "chroma",
                        chroma_url=f"http://127.0.0.1:{_free_port()}", reranking=False)
    with pytest.raises(RuntimeError, match="unreachable"):
        VaultIndex(settings)
    assert not (tmp_path / "chroma").exists()


def test_broken_frontmatter_keeps_the_note(tmp_path):
    note_file = tmp_path / "botseller" / "broken.md"
    note_file.parent.mkdir()
    note_file.write_text(
        "---\ntitle: BotSeller: релиз 2.0\nproject: botseller\n---\n\n# Релиз\n\nТекст заметки.\n",
        encoding="utf-8",
    )
    note = parse_note(note_file, tmp_path)
    assert note is not None
    assert "Текст заметки" in note.content
    assert "title:" not in note.content
    assert note.project == "botseller"  # from the folder, since the header is unreadable

