"""Tests for VaultLinter (linter.py) — mixed date/datetime frontmatter."""
from datetime import date

from obsidian_bridge.linter import VaultLinter, _to_date


def _write_note(vault, project: str, name: str, updated_value: str) -> None:
    project_dir = vault / project
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / name).write_text(
        "---\n"
        f"project: {project}\n"
        "type: note\n"
        "tags: []\n"
        "priority: medium\n"
        f"created: {updated_value}\n"
        f"updated: {updated_value}\n"
        "---\n\n"
        "# Some note\n\nJust some content, nothing special here.\n",
        encoding="utf-8",
    )


class TestToDate:
    def test_plain_date_passthrough(self):
        assert _to_date(date(2026, 1, 1)) == date(2026, 1, 1)

    def test_datetime_normalized_to_date(self):
        from datetime import datetime
        assert _to_date(datetime(2026, 1, 1, 10, 30, 0)) == date(2026, 1, 1)

    def test_iso_string_parsed(self):
        assert _to_date("2026-01-01T10:30:00") == date(2026, 1, 1)

    def test_none_returns_none(self):
        assert _to_date(None) is None

    def test_garbage_string_returns_none(self):
        assert _to_date("not-a-date") is None


class TestVaultLinterStaleNotes:
    def test_lint_does_not_raise_on_mixed_date_and_datetime_frontmatter(self, tmp_path):
        """Regression: 'can't compare datetime.datetime to datetime.date'.

        A note whose frontmatter `updated` is a bare YAML date (parsed as
        `datetime.date`) alongside a note whose `updated` is a full
        timestamp (parsed as `datetime.datetime`) used to blow up lint_vault
        with a TypeError when both were compared against `date.today()`.
        """
        _write_note(tmp_path, "proj-a", "date-note.md", "2025-01-01")
        _write_note(tmp_path, "proj-b", "datetime-note.md", "2025-01-01T10:30:00")

        linter = VaultLinter(tmp_path, stale_days=90)
        report = linter.lint()  # must not raise

        stale_files = {i.file for i in report.issues if i.category == "stale"}
        assert "proj-a/date-note.md" in stale_files
        assert "proj-b/datetime-note.md" in stale_files

    def test_recent_datetime_note_is_not_flagged_stale(self, tmp_path):
        today_iso = date.today().isoformat() + "T09:00:00"
        _write_note(tmp_path, "proj-c", "fresh.md", today_iso)

        linter = VaultLinter(tmp_path, stale_days=90)
        report = linter.lint()

        stale_files = {i.file for i in report.issues if i.category == "stale"}
        assert "proj-c/fresh.md" not in stale_files
