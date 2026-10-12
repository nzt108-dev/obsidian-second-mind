"""An empty `tags:` in frontmatter must not break the vault scan.

2026-10-12: create_note without tags wrote a bare `tags:` line, YAML read it as None,
and parse_note crashed on `None + list`. The crash happened in _regenerate_index after
the note was already written, so every create_note / update_note / save_insight
returned an error while actually saving.
"""
import asyncio

import frontmatter

from obsidian_bridge.parser import get_project_notes, parse_note


def _write(path, header: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{header}---\n\n# Title\n\nBody #inline\n", encoding="utf-8")


def test_bare_tags_line_parses_as_no_tags(tmp_path):
    note_path = tmp_path / "proj" / "a.md"
    _write(note_path, "project: proj\ntype: decision\ntags:\n")

    note = parse_note(note_path, tmp_path)

    assert note is not None
    assert note.tags == ["inline"]


def test_one_bad_note_does_not_break_project_scan(tmp_path):
    _write(tmp_path / "proj" / "bad.md", "project: proj\ntags:\n")
    _write(tmp_path / "proj" / "good.md", "project: proj\ntags:\n  - \"x\"\n")

    paths = {n.path for n in get_project_notes(tmp_path, "proj")}

    assert len(paths) == 2


def test_create_note_without_tags_writes_a_list(tmp_path, monkeypatch):
    from obsidian_bridge import mcp_server
    from obsidian_bridge.mcp_tools import notes

    monkeypatch.setattr(mcp_server, "_get_vault_path", lambda: tmp_path)
    monkeypatch.setattr(mcp_server, "_reindex_note", lambda *a, **k: "")

    result = asyncio.run(notes.handle_create_note(
        {"project": "proj", "title": "No tags", "note_type": "note", "content": "Body"}
    ))

    assert result[0].text.startswith("✅")
    post = frontmatter.loads((tmp_path / "proj" / "no-tags.md").read_text(encoding="utf-8"))
    assert post.metadata["tags"] == []
