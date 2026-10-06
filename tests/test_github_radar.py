"""Tests for GitHub Radar module."""
import importlib.util
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from obsidian_bridge.github_radar import (
    SCAN_ATTEMPTS,
    DeveloperWatcher,
    RadarScanError,
    TrendingRepo,
    TrendingScanner,
    _extract_readme_summary,
    _find_applicable_projects,
    _get_json_with_retry,
    _score_relevance,
)


def _load_cron_module():
    """Load scripts/github_radar_cron.py as a module (it is not a package)."""
    path = Path(__file__).parent.parent / "scripts" / "github_radar_cron.py"
    spec = importlib.util.spec_from_file_location("github_radar_cron", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestScoreRelevance(unittest.TestCase):
    """Test relevance scoring."""

    def test_high_relevance_mcp(self):
        score, reason = _score_relevance(
            "MCP server for filesystem access", ["mcp", "model-context-protocol"], "Python"
        )
        self.assertGreaterEqual(score, 0.6)
        self.assertIn("MCP", reason)

    def test_high_relevance_ai(self):
        score, reason = _score_relevance(
            "AI agent framework using LLM and RAG", ["ai-agent", "llm", "rag"], "Python"
        )
        self.assertGreaterEqual(score, 0.5)

    def test_medium_relevance(self):
        score, reason = _score_relevance(
            "CLI tool for developers", ["devtools", "cli"], "TypeScript"
        )
        self.assertGreater(score, 0.0)

    def test_low_relevance(self):
        score, reason = _score_relevance(
            "Minecraft server plugin", ["minecraft", "gaming"], "Java"
        )
        self.assertLessEqual(score, 0.1)

    def test_language_bonus(self):
        score_py, _ = _score_relevance("Generic tool", [], "Python")
        score_java, _ = _score_relevance("Generic tool", [], "Java")
        self.assertGreater(score_py, score_java)


class TestExtractReadmeSummary(unittest.TestCase):
    """Test README parsing."""

    def test_basic_readme(self):
        readme = """# My Project

This is an awesome tool for developers that helps automate tasks.

## Installation

pip install my-project
"""
        summary = _extract_readme_summary(readme)
        self.assertIn("awesome tool", summary)

    def test_empty_readme(self):
        self.assertEqual(_extract_readme_summary(""), "")
        self.assertEqual(_extract_readme_summary(None), "")

    def test_badges_skipped(self):
        readme = """# Project
![badge](https://img.shields.io/badge)
![another](https://img.shields.io/another)

Real description of the project here.
"""
        summary = _extract_readme_summary(readme)
        self.assertIn("Real description", summary)

    def test_truncation(self):
        readme = "# Title\n\n" + "A" * 1000
        summary = _extract_readme_summary(readme, max_chars=100)
        self.assertLessEqual(len(summary), 100)


class TestFindApplicableProjects(unittest.TestCase):
    """Test project matching."""

    def test_mcp_matches_second_mind(self):
        result = _find_applicable_projects("MCP server", ["mcp"], "Python")
        self.assertIn("obsidian-second-mind", result)

    def test_telegram_matches_botseller(self):
        result = _find_applicable_projects("Telegram bot framework", ["telegram", "bot"], "Python")
        self.assertIn("botseller", result)

    def test_no_match(self):
        result = _find_applicable_projects("Minecraft mod", ["gaming"], "Java")
        self.assertEqual(result, [])


class TestTrendingScanner(unittest.TestCase):
    """Test trending scanner."""

    def test_to_markdown_empty(self):
        scanner = TrendingScanner()
        md = scanner.to_markdown([], "ai")
        self.assertIn("No trending repos", md)

    def test_to_markdown_with_repos(self):
        repos = [
            TrendingRepo(
                full_name="test/repo",
                description="Test repo",
                url="https://github.com/test/repo",
                stars=1000,
                forks=100,
                language="Python",
                topics=["ai"],
                created_at="2026-01-01",
                pushed_at="2026-04-09",
                relevance_score=0.8,
                relevance_reason="ai related",
            )
        ]
        md = scanner = TrendingScanner()
        md = scanner.to_markdown(repos, "ai")
        self.assertIn("test/repo", md)
        self.assertIn("High Relevance", md)


class TestScanRetry(unittest.TestCase):
    """Latch for 2026-08-01: two silent 'Found 0 repos' days were API failures."""

    def _client_mock(self, *, responses):
        """Build a fake httpx.Client whose .get() replays `responses`."""
        client = MagicMock()
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        client.get = MagicMock(side_effect=responses)
        return MagicMock(return_value=client)

    def test_retries_then_succeeds(self):
        ok = MagicMock()
        ok.raise_for_status = MagicMock()
        ok.json = MagicMock(return_value={"items": []})
        factory = self._client_mock(
            responses=[httpx.ConnectTimeout("boom"), ok]
        )
        with patch("obsidian_bridge.github_radar.httpx.Client", factory), \
                patch("obsidian_bridge.github_radar.time.sleep"):
            data = _get_json_with_retry("https://x", {}, {})
        self.assertEqual(data, {"items": []})

    def test_raises_after_all_attempts(self):
        factory = self._client_mock(
            responses=[httpx.ConnectTimeout("boom")] * SCAN_ATTEMPTS
        )
        with patch("obsidian_bridge.github_radar.httpx.Client", factory), \
                patch("obsidian_bridge.github_radar.time.sleep"):
            with self.assertRaises(RadarScanError):
                _get_json_with_retry("https://x", {}, {})

    def test_rate_limit_is_retried_not_swallowed(self):
        rate_limited = MagicMock()
        rate_limited.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "403", request=MagicMock(), response=MagicMock()
            )
        )
        factory = self._client_mock(responses=[rate_limited] * SCAN_ATTEMPTS)
        with patch("obsidian_bridge.github_radar.httpx.Client", factory), \
                patch("obsidian_bridge.github_radar.time.sleep"):
            with self.assertRaises(RadarScanError):
                _get_json_with_retry("https://x", {}, {})
        self.assertEqual(rate_limited.raise_for_status.call_count, SCAN_ATTEMPTS)

    def test_scan_propagates_error_instead_of_empty_list(self):
        scanner = TrendingScanner()
        with patch(
            "obsidian_bridge.github_radar._get_json_with_retry",
            side_effect=RadarScanError("down"),
        ):
            with self.assertRaises(RadarScanError):
                scanner.scan(topic="ai")


class TestCronFailureHandling(unittest.TestCase):
    """Cron must tell 'empty day' apart from 'API broken'."""

    @classmethod
    def setUpClass(cls):
        cls.cron = _load_cron_module()

    def test_failed_topic_reported_as_error(self):
        with patch.object(
            self.cron.TrendingScanner,
            "scan",
            side_effect=self.cron.RadarScanError("down"),
        ):
            _md, structured, errors = self.cron.scan_trending(["ai", "mcp"])
        self.assertEqual(structured, {})
        self.assertEqual(len(errors), 2)
        self.assertIn("ai:", errors[0])

    def test_empty_result_is_not_an_error(self):
        with patch.object(self.cron.TrendingScanner, "scan", return_value=[]):
            _md, structured, errors = self.cron.scan_trending(["ai"])
        self.assertEqual(structured, {})
        self.assertEqual(errors, [])

    def test_failed_profile_check_is_error_not_silence(self):
        watcher = MagicMock()
        watcher._load_watchlist.return_value = [{"username": "karpathy"}]
        watcher.check.return_value = None  # API call failed
        with patch.object(self.cron, "DeveloperWatcher", return_value=watcher):
            _md, structured, errors = self.cron.check_watched_devs()
        self.assertEqual(structured, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("karpathy", errors[0])

    def test_run_log_appends_line(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "logs" / "github-radar.jsonl"
            with patch.object(self.cron, "RUN_LOG", log):
                self.cron.write_run_log("failure", findings=0, error="down")
            entry = json.loads(log.read_text(encoding="utf-8").strip())
        self.assertEqual(entry["outcome"], "failure")
        self.assertEqual(entry["escalations"], 1)

    def test_archive_moves_only_old_reports(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            inbox = vault / "inbox"
            inbox.mkdir()
            old = inbox / f"github-radar-{date.today() - timedelta(days=30)}.md"
            fresh = inbox / f"github-radar-{date.today()}.md"
            unrelated = inbox / "note.md"
            for f in (old, fresh, unrelated):
                f.write_text("x", encoding="utf-8")

            with patch.object(self.cron, "VAULT_PATH", vault), \
                    patch.object(self.cron, "ARCHIVE_DIR", vault / "_radar" / "archive"):
                moved = self.cron.archive_old_reports(keep_days=7)

            self.assertEqual(moved, 1)
            self.assertFalse(old.exists())
            self.assertTrue(fresh.exists())
            self.assertTrue(unrelated.exists())
            self.assertTrue((vault / "_radar" / "archive" / old.name).exists())


class TestDeveloperWatcher(unittest.TestCase):
    """Test watch list management."""

    def setUp(self):
        self.vault_path = Path("/tmp/test_vault_radar")
        self.vault_path.mkdir(parents=True, exist_ok=True)
        self.watcher = DeveloperWatcher(vault_path=self.vault_path)

    def tearDown(self):
        import shutil
        if self.vault_path.exists():
            shutil.rmtree(self.vault_path)

    def test_add_developer(self):
        result = self.watcher.add("testuser", "ai")
        self.assertIn("Added", result)
        self.assertIn("testuser", result)

    def test_add_duplicate(self):
        self.watcher.add("testuser", "ai")
        result = self.watcher.add("testuser", "devtools")
        self.assertIn("already", result)

    def test_list_empty(self):
        result = self.watcher.list_watched()
        self.assertIn("empty", result.lower())

    def test_list_with_entries(self):
        self.watcher.add("user1", "ai")
        self.watcher.add("user2", "devtools")
        result = self.watcher.list_watched()
        self.assertIn("user1", result)
        self.assertIn("user2", result)

    def test_remove(self):
        self.watcher.add("testuser", "ai")
        result = self.watcher.remove("testuser")
        self.assertIn("Removed", result)
        listing = self.watcher.list_watched()
        self.assertNotIn("testuser", listing)

    def test_remove_nonexistent(self):
        result = self.watcher.remove("nonexistent")
        self.assertIn("not found", result)


if __name__ == "__main__":
    unittest.main()


class TestWeeklyNewOnly(unittest.TestCase):
    """06.10.2026: daily walls of ~30 links piled up unread in inbox."""

    @classmethod
    def setUpClass(cls):
        cls.cron = _load_cron_module()

    def _repo(self, name, rel, stars=100):
        r = MagicMock()
        r.full_name, r.relevance_score, r.stars = name, rel, stars
        r.url, r.description = f"https://github.com/{name}", "d"
        return r

    def test_pick_new_skips_seen_low_relevance_and_duplicates(self):
        by_topic = {
            "ai": [self._repo("a/seen", 0.9), self._repo("a/low", 0.2), self._repo("a/new", 0.7)],
            "mcp": [self._repo("a/new", 0.7), self._repo("b/best", 0.95)],
        }
        picked = self.cron.pick_new(by_topic, seen={"a/seen"})
        self.assertEqual([r.full_name for _t, r in picked], ["b/best", "a/new"])

    def test_pick_new_caps_at_top_n(self):
        by_topic = {"ai": [self._repo(f"o/r{i}", 0.5 + i / 100) for i in range(12)]}
        picked = self.cron.pick_new(by_topic, seen=set(), top_n=5)
        self.assertEqual(len(picked), 5)
        self.assertEqual(picked[0][1].full_name, "o/r11")

    def test_seen_roundtrip(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "seen.json"
            self.assertEqual(self.cron.load_seen(path), set())
            self.cron.save_seen({"x/y", "https://github.com/u/r"}, path)
            self.assertEqual(self.cron.load_seen(path), {"x/y", "https://github.com/u/r"})
