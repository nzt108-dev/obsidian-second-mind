"""Tests for the Intelligence Layer (scout.py)."""
import pytest
from pathlib import Path

from obsidian_bridge.scout import (
    SessionAnalyzer,
    TechRadar,
    RadarReport,
    DependencyChecker,
    DepReport,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_vault(tmp_path):
    """Create a temporary vault with session notes."""
    # Create project with session note
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()

    session_note = project_dir / "session-2026-04-01.md"
    session_note.write_text(
        "---\n"
        "project: test-project\n"
        "type: note\n"
        "tags:\n"
        '  - "session"\n'
        "created: 2026-04-01\n"
        "updated: 2026-04-01\n"
        "---\n\n"
        "# Session 2026-04-01\n\n"
        "## What Was Done\n"
        "- Implemented login flow\n"
        "- Added Firebase auth\n\n"
        "### What Failed / Issues\n"
        "- Firebase init crashed on iOS simulator — workaround: clean build folder\n"
        "- Browser tool couldn't open pages — used manual verification\n"
        "- API timeout on first request — switched to longer timeout\n"
    )

    # Another session with overlapping issues
    session_note2 = project_dir / "session-2026-04-05.md"
    session_note2.write_text(
        "---\n"
        "project: test-project\n"
        "type: note\n"
        "tags:\n"
        '  - "session"\n'
        "created: 2026-04-05\n"
        "updated: 2026-04-05\n"
        "---\n\n"
        "# Session 2026-04-05\n\n"
        "## What Was Done\n"
        "- Updated dependencies\n\n"
        "### What Failed\n"
        "- Firebase init crashed again after update — workaround: clean build\n"
        "- Build failed due to missing dependency\n"
    )

    # Another project
    project2_dir = tmp_path / "another-project"
    project2_dir.mkdir()

    session_note3 = project2_dir / "session-2026-04-03.md"
    session_note3.write_text(
        "---\n"
        "project: another-project\n"
        "type: note\n"
        "tags:\n"
        '  - "session"\n'
        "created: 2026-04-03\n"
        "updated: 2026-04-03\n"
        "---\n\n"
        "# Session 2026-04-03\n\n"
        "## What Was Done\n"
        "- Set up CI/CD\n\n"
        "### Issues\n"
        "- Firebase init crashed — same issue as test-project\n"
    )

    return tmp_path


@pytest.fixture
def npm_project(tmp_path):
    """Create a temporary npm project."""
    project_dir = tmp_path / "web-app"
    project_dir.mkdir()

    pkg = project_dir / "package.json"
    pkg.write_text(
        '{\n'
        '  "name": "web-app",\n'
        '  "dependencies": {\n'
        '    "react": "^18.2.0",\n'
        '    "next": "^14.0.0"\n'
        '  },\n'
        '  "devDependencies": {\n'
        '    "typescript": "^5.3.0"\n'
        '  }\n'
        '}\n'
    )

    return tmp_path


@pytest.fixture
def pip_project(tmp_path):
    """Create a temporary Python project."""
    project_dir = tmp_path / "py-app"
    project_dir.mkdir()

    pyproject = project_dir / "pyproject.toml"
    pyproject.write_text(
        '[project]\n'
        'name = "py-app"\n'
        'dependencies = [\n'
        '    "fastapi>=0.100.0",\n'
        '    "httpx>=0.25.0",\n'
        ']\n'
    )

    return tmp_path


# ---------------------------------------------------------------------------
# Session Analyzer Tests
# ---------------------------------------------------------------------------

class TestSessionAnalyzer:

    def test_analyze_finds_issues(self, tmp_vault):
        analyzer = SessionAnalyzer(tmp_vault)
        report = analyzer.analyze()

        assert report.total_issues > 0

    def test_analyze_finds_repeating_issues(self, tmp_vault):
        analyzer = SessionAnalyzer(tmp_vault)
        report = analyzer.analyze()

        # Firebase init crash appears in multiple sessions
        assert len(report.repeating_issues) >= 1

    def test_analyze_categorizes_issues(self, tmp_vault):
        analyzer = SessionAnalyzer(tmp_vault)
        report = analyzer.analyze()

        assert len(report.top_problem_areas) > 0
        categories = [a["category"] for a in report.top_problem_areas]
        assert len(categories) > 0

    def test_analyze_extracts_workarounds(self, tmp_vault):
        analyzer = SessionAnalyzer(tmp_vault)
        report = analyzer.analyze()

        assert len(report.workaround_patterns) > 0

    def test_analyze_generates_recommendations(self, tmp_vault):
        analyzer = SessionAnalyzer(tmp_vault)
        report = analyzer.analyze()

        assert len(report.recommendations) > 0

    def test_analyze_filter_by_project(self, tmp_vault):
        analyzer = SessionAnalyzer(tmp_vault)
        report = analyzer.analyze(project="test-project")

        # Should only contain issues from test-project
        for issue in report.workaround_patterns:
            assert issue["project"] == "test-project"

    def test_report_to_markdown(self, tmp_vault):
        analyzer = SessionAnalyzer(tmp_vault)
        report = analyzer.analyze()
        md = report.to_markdown()

        assert "Session Intelligence Report" in md
        assert "Summary" in md

    def test_empty_vault(self, tmp_path):
        analyzer = SessionAnalyzer(tmp_path)
        report = analyzer.analyze()

        assert report.total_sessions == 0
        assert report.total_issues == 0

    def test_categorize_issue(self, tmp_vault):
        analyzer = SessionAnalyzer(tmp_vault)

        assert analyzer._categorize_issue("Firebase init crashed") == "crash"
        assert analyzer._categorize_issue("API timeout error") == "api"
        assert analyzer._categorize_issue("Build failed") == "build"
        assert analyzer._categorize_issue("Browser tool broken") == "tool"
        assert analyzer._categorize_issue("Something random happened") == "other"


# ---------------------------------------------------------------------------
# Tech Radar Tests
# ---------------------------------------------------------------------------

class TestTechRadar:

    def test_score_relevance_high(self, tmp_path):
        radar = TechRadar(tmp_path)
        from obsidian_bridge.scout import ToolInfo

        tool = ToolInfo(
            name="awesome-mcp-server",
            description="A Model Context Protocol server for Flutter projects",
            url="https://github.com/test/test",
            category="mcp",
        )
        assert radar._score_relevance(tool) == "high"

    def test_score_relevance_medium(self, tmp_path):
        radar = TechRadar(tmp_path)
        from obsidian_bridge.scout import ToolInfo

        tool = ToolInfo(
            name="tailwind-helper",
            description="CSS tailwind utility for web projects",
            url="https://github.com/test/test",
            category="devtools",
        )
        assert radar._score_relevance(tool) == "medium"

    def test_score_relevance_low(self, tmp_path):
        radar = TechRadar(tmp_path)
        from obsidian_bridge.scout import ToolInfo

        tool = ToolInfo(
            name="random-game-engine",
            description="A 3D game rendering engine for Unity",
            url="https://github.com/test/test",
            category="other",
        )
        assert radar._score_relevance(tool) == "low"

    def test_radar_report_markdown(self):
        report = RadarReport(
            scan_date="2026-04-08",
            tools_found=3,
            high_relevance=[{
                "name": "test-mcp",
                "description": "A test MCP server",
                "url": "https://test.com",
                "stars": 100,
                "category": "mcp",
                "source": "github",
            }],
            medium_relevance=[],
            low_relevance=[],
        )
        md = report.to_markdown()

        assert "Tech Radar Report" in md
        assert "test-mcp" in md
        assert "High Relevance" in md


# ---------------------------------------------------------------------------
# Dependency Checker Tests
# ---------------------------------------------------------------------------

class TestDependencyChecker:

    def test_resolve_project_path(self, npm_project):
        checker = DependencyChecker(
            vault_path=Path("/tmp"),
            project_paths={"web-app": str(npm_project / "web-app")},
        )
        path = checker._resolve_project_path("web-app")
        assert path is not None
        assert path.exists()

    def test_resolve_unknown_project(self, tmp_path):
        checker = DependencyChecker(vault_path=tmp_path)
        path = checker._resolve_project_path("nonexistent-project-xyz")
        assert path is None

    def test_clean_version(self):
        assert DependencyChecker._clean_version("^1.2.3") == "1.2.3"
        assert DependencyChecker._clean_version("~1.2.3") == "1.2.3"
        assert DependencyChecker._clean_version(">=1.2.3") == "1.2.3"
        assert DependencyChecker._clean_version("1.2.3") == "1.2.3"

    def test_classify_update(self):
        assert DependencyChecker._classify_update("1.0.0", "2.0.0") == "major"
        assert DependencyChecker._classify_update("1.0.0", "1.1.0") == "minor"
        assert DependencyChecker._classify_update("1.0.0", "1.0.1") == "patch"
        assert DependencyChecker._classify_update("abc", "def") == "unknown"

    def test_dep_report_markdown(self):
        report = DepReport(
            project="test-app",
            package_manager="npm",
            total_deps=10,
            up_to_date=7,
            outdated=[
                {"name": "react", "current": "18.2.0", "latest": "19.0.0", "update_type": "major"},
                {"name": "next", "current": "14.0.0", "latest": "14.1.0", "update_type": "minor"},
            ],
        )
        md = report.to_markdown()

        assert "test-app" in md
        assert "npm" in md
        assert "react" in md
        assert "Major Updates" in md
        assert "Minor Updates" in md
