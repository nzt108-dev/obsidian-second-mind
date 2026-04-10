"""Tests for GitHub Radar module."""
import unittest
from pathlib import Path

from obsidian_bridge.github_radar import (
    DeveloperWatcher,
    TrendingRepo,
    TrendingScanner,
    _extract_readme_summary,
    _find_applicable_projects,
    _score_relevance,
)


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
