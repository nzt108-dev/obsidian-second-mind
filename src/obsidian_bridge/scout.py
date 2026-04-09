"""Intelligence Layer — Session Analysis, Tech Radar, Dependency Watch.

v0.5.0: Three analyzers that make the vault proactive:
- SessionAnalyzer: finds repeating problems across session logs
- TechRadar: scans for new tools/MCP servers relevant to our stack
- DependencyChecker: checks project dependencies for updates
"""
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

import httpx

from obsidian_bridge.parser import scan_vault

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session Intelligence
# ---------------------------------------------------------------------------

# Regex patterns for extracting failure/issue info from session logs
FAILURE_HEADER = re.compile(
    r"###?\s*(What Failed|Issues?|What Failed / Issues?|Problems?|Errors?|Blockers?)\b",
    re.IGNORECASE,
)
WORKAROUND_PATTERN = re.compile(
    r"(?:workaround|fix(?:ed)?|solution|resolved|switched to|replaced with|instead of)\s*[:—–-]?\s*(.+)",
    re.IGNORECASE,
)
ERROR_PATTERN = re.compile(
    r"(?:error|fail(?:ed|ure)?|crash(?:ed)?|bug|broken|timeout|hang|stuck|froze)\b",
    re.IGNORECASE,
)
TOOL_MENTION = re.compile(
    r"(?:used|tried|installed|switched to|using)\s+(?:to\s+)?[`\"']?(\w[\w\-\.]+)[`\"']?",
    re.IGNORECASE,
)


@dataclass
class SessionIssue:
    """A single issue extracted from a session log."""
    project: str
    session_date: str
    issue_text: str
    workaround: str = ""
    category: str = ""  # "crash" | "config" | "api" | "build" | "tool" | "other"


@dataclass
class SessionReport:
    """Analysis report from session logs."""
    total_sessions: int = 0
    total_issues: int = 0
    repeating_issues: list[dict] = field(default_factory=list)
    top_problem_areas: list[dict] = field(default_factory=list)
    workaround_patterns: list[dict] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Format report as markdown."""
        lines = [
            "# 🧠 Session Intelligence Report",
            "",
            "## 📊 Summary",
            f"- Sessions analyzed: **{self.total_sessions}**",
            f"- Total issues found: **{self.total_issues}**",
            f"- Repeating patterns: **{len(self.repeating_issues)}**",
            "",
        ]

        if self.repeating_issues:
            lines.extend(["## 🔄 Repeating Issues", ""])
            for issue in self.repeating_issues:
                lines.append(
                    f"### {issue['pattern']} (×{issue['count']})"
                )
                lines.append(f"> Projects: {', '.join(issue['projects'])}")
                if issue.get("workarounds"):
                    lines.append(f"- 🔧 Common fix: {issue['workarounds'][0]}")
                lines.append("")

        if self.top_problem_areas:
            lines.extend(["## 🎯 Top Problem Areas", ""])
            for area in self.top_problem_areas:
                lines.append(
                    f"- **{area['category']}** — {area['count']} occurrences"
                    f" ({area['pct']}%)"
                )
            lines.append("")

        if self.workaround_patterns:
            lines.extend(["## 🔧 Reusable Workarounds", ""])
            for wp in self.workaround_patterns:
                lines.append(f"- **{wp['issue']}** → {wp['workaround']}")
            lines.append("")

        if self.recommendations:
            lines.extend(["## 💡 Recommendations", ""])
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        return "\n".join(lines)


class SessionAnalyzer:
    """Analyzes session logs to find repeating problems and patterns."""

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path

    def analyze(self, project: Optional[str] = None) -> SessionReport:
        """Analyze vault session notes for patterns."""
        report = SessionReport()
        issues: list[SessionIssue] = []

        # 1. Scan vault for session notes
        notes = scan_vault(self.vault_path)
        if project:
            notes = [n for n in notes if n.project == project]

        session_notes = [
            n for n in notes
            if n.note_type == "note" and any(
                t in ["session", "log"] for t in n.tags
            )
        ]
        report.total_sessions = len(session_notes)

        # 2. Also check for session logs in project directories
        for proj_dir in self.vault_path.iterdir():
            if not proj_dir.is_dir() or proj_dir.name.startswith((".", "_")):
                continue
            if project and proj_dir.name != project:
                continue

            # Look for notes with "Session" in title or "What Failed" sections
            for md_file in proj_dir.glob("*.md"):
                note_content = md_file.read_text(encoding="utf-8")
                if FAILURE_HEADER.search(note_content):
                    extracted = self._extract_issues(
                        note_content, proj_dir.name, md_file.stem
                    )
                    issues.extend(extracted)

        # 3. Extract issues from session notes
        for note in session_notes:
            extracted = self._extract_issues(
                note.content, note.project, note.title
            )
            issues.extend(extracted)

        report.total_issues = len(issues)

        # 4. Find repeating patterns
        report.repeating_issues = self._find_repeating(issues)

        # 5. Categorize problem areas
        report.top_problem_areas = self._categorize_issues(issues)

        # 6. Extract reusable workarounds
        report.workaround_patterns = self._extract_workarounds(issues)

        # 7. Generate recommendations
        report.recommendations = self._generate_recommendations(report)

        return report

    def _extract_issues(
        self, content: str, project: str, source: str
    ) -> list[SessionIssue]:
        """Extract individual issues from session content."""
        issues = []

        # Find "What Failed" sections
        sections = FAILURE_HEADER.split(content)
        for i, section in enumerate(sections):
            if i == 0:
                continue  # Before first failure header

            # Extract bullet points from the failure section
            # Take text until next ## header
            section_text = section.split("\n##")[0] if "\n##" in section else section
            for line in section_text.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Clean markdown bullets
                clean = re.sub(r"^[-*•]\s*", "", line).strip()
                if len(clean) < 10:
                    continue

                # Extract workaround if present
                workaround = ""
                wa_match = WORKAROUND_PATTERN.search(clean)
                if wa_match:
                    workaround = wa_match.group(1).strip()

                # Categorize
                category = self._categorize_issue(clean)

                issues.append(SessionIssue(
                    project=project,
                    session_date=source,
                    issue_text=clean,
                    workaround=workaround,
                    category=category,
                ))

        return issues

    def _categorize_issue(self, text: str) -> str:
        """Categorize an issue by its text content."""
        text_lower = text.lower()
        if any(w in text_lower for w in ["crash", "panic", "fatal", "segfault"]):
            return "crash"
        if any(w in text_lower for w in ["config", "env", ".env", "environment", "settings"]):
            return "config"
        if any(w in text_lower for w in ["api", "endpoint", "request", "response", "cors"]):
            return "api"
        if any(w in text_lower for w in ["build", "compile", "webpack", "vite", "flutter build"]):
            return "build"
        if any(w in text_lower for w in ["browser", "tool", "cursor", "terminal", "command"]):
            return "tool"
        if any(w in text_lower for w in ["timeout", "slow", "hang", "stuck", "freeze"]):
            return "performance"
        if any(w in text_lower for w in ["firebase", "supabase", "database", "prisma", "migration"]):
            return "database"
        if any(w in text_lower for w in ["auth", "login", "token", "permission"]):
            return "auth"
        return "other"

    def _find_repeating(self, issues: list[SessionIssue]) -> list[dict]:
        """Find issues that repeat across sessions/projects."""
        # Normalize issue texts for comparison
        normalized: dict[str, list[SessionIssue]] = {}

        for issue in issues:
            # Create a simplified key from the issue text
            key = self._normalize_issue_text(issue.issue_text)
            if key not in normalized:
                normalized[key] = []
            normalized[key].append(issue)

        # Filter to repeating patterns (count > 1)
        repeating = []
        for pattern, instances in normalized.items():
            if len(instances) >= 2:
                projects = list(set(i.project for i in instances))
                workarounds = [
                    i.workaround for i in instances if i.workaround
                ]
                repeating.append({
                    "pattern": pattern,
                    "count": len(instances),
                    "projects": projects,
                    "workarounds": workarounds,
                    "category": instances[0].category,
                })

        # Sort by count descending
        repeating.sort(key=lambda x: x["count"], reverse=True)
        return repeating[:10]  # Top 10

    def _normalize_issue_text(self, text: str) -> str:
        """Normalize issue text for pattern matching."""
        # Remove specific file paths, hashes, timestamps
        text = re.sub(r"[a-f0-9]{7,}", "<hash>", text)
        text = re.sub(r"/[\w\-./]+\.\w+", "<path>", text)
        text = re.sub(r"\d{4}-\d{2}-\d{2}", "<date>", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        # Truncate to first 80 chars for grouping
        return text[:80] if len(text) > 80 else text

    def _categorize_issues(self, issues: list[SessionIssue]) -> list[dict]:
        """Group issues by category with percentages."""
        if not issues:
            return []

        counter = Counter(i.category for i in issues)
        total = len(issues)

        return [
            {
                "category": cat,
                "count": count,
                "pct": round(count / total * 100),
            }
            for cat, count in counter.most_common(8)
        ]

    def _extract_workarounds(self, issues: list[SessionIssue]) -> list[dict]:
        """Extract reusable workaround patterns."""
        workarounds = []
        seen = set()

        for issue in issues:
            if issue.workaround and issue.workaround not in seen:
                seen.add(issue.workaround)
                workarounds.append({
                    "issue": issue.issue_text[:100],
                    "workaround": issue.workaround,
                    "project": issue.project,
                    "category": issue.category,
                })

        return workarounds[:10]  # Top 10

    def _generate_recommendations(self, report: SessionReport) -> list[str]:
        """Generate actionable recommendations from analysis."""
        recs = []

        if report.repeating_issues:
            top = report.repeating_issues[0]
            recs.append(
                f"Create a guidelines note for '{top['pattern']}' "
                f"— this issue appeared {top['count']} times across "
                f"{', '.join(top['projects'])}"
            )

        if report.top_problem_areas:
            top_area = report.top_problem_areas[0]
            if top_area["pct"] > 30:
                recs.append(
                    f"Category '{top_area['category']}' accounts for "
                    f"{top_area['pct']}% of all issues — consider "
                    f"investing in better tooling or templates for this area"
                )

        if report.workaround_patterns:
            recs.append(
                f"Document {len(report.workaround_patterns)} proven workarounds "
                f"as project guidelines to prevent repeated debugging"
            )

        if report.total_sessions > 0 and report.total_issues == 0:
            recs.append(
                "No issues found — either sessions are going smoothly or "
                "issues aren't being documented in 'What Failed' sections"
            )

        return recs


# ---------------------------------------------------------------------------
# Tech Radar
# ---------------------------------------------------------------------------

@dataclass
class ToolInfo:
    """Information about a discovered tool."""
    name: str
    description: str
    url: str
    stars: int = 0
    category: str = ""  # "mcp" | "ai" | "devtools" | "framework"
    relevance: str = "low"  # "low" | "medium" | "high"
    source: str = ""  # "github" | "npm" | "awesome-list"


@dataclass
class RadarReport:
    """Tech Radar scan results."""
    scan_date: str = ""
    tools_found: int = 0
    high_relevance: list[dict] = field(default_factory=list)
    medium_relevance: list[dict] = field(default_factory=list)
    low_relevance: list[dict] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Format radar report as markdown."""
        lines = [
            "# 🔭 Tech Radar Report",
            f"> Scanned on {self.scan_date}",
            "",
            f"## Summary: {self.tools_found} tools found",
            "",
        ]

        if self.high_relevance:
            lines.extend(["## 🟢 High Relevance", ""])
            for tool in self.high_relevance:
                stars_str = f" ⭐ {tool.get('stars', 0)}" if tool.get("stars") else ""
                lines.append(
                    f"### [{tool['name']}]({tool['url']}){stars_str}"
                )
                lines.append(f"> {tool['description']}")
                lines.append(f"- Category: `{tool['category']}`")
                lines.append("")

        if self.medium_relevance:
            lines.extend(["## 🟡 Medium Relevance", ""])
            for tool in self.medium_relevance:
                lines.append(
                    f"- **[{tool['name']}]({tool['url']})** — {tool['description'][:100]}"
                )
            lines.append("")

        if self.low_relevance:
            lines.extend([f"## ⚪ Low Relevance ({len(self.low_relevance)} tools)", ""])
            for tool in self.low_relevance[:5]:
                lines.append(
                    f"- [{tool['name']}]({tool['url']}) — {tool['description'][:80]}"
                )
            if len(self.low_relevance) > 5:
                lines.append(f"- ... and {len(self.low_relevance) - 5} more")
            lines.append("")

        return "\n".join(lines)


# Stack keywords for relevance scoring
STACK_KEYWORDS = {
    "high": [
        "mcp", "model context protocol", "obsidian", "knowledge base",
        "second brain", "flutter", "dart", "fastapi", "python",
        "next.js", "nextjs", "react", "typescript", "vercel",
        "prisma", "turso", "sqlite", "chromadb",
        "ai agent", "coding assistant", "llm",
    ],
    "medium": [
        "tailwind", "css", "firebase", "supabase",
        "telegram bot", "discord bot", "web scraping",
        "ci/cd", "github actions", "docker",
        "vector database", "embeddings", "rag",
    ],
}


class TechRadar:
    """Scans for new tools and technologies relevant to our stack."""

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path

    async def scan(self, category: str = "all") -> RadarReport:
        """Scan for new tools. Categories: 'mcp', 'ai', 'devtools', 'all'."""
        report = RadarReport(scan_date=date.today().isoformat())
        tools: list[ToolInfo] = []

        async with httpx.AsyncClient(timeout=15.0) as client:
            if category in ("all", "mcp"):
                tools.extend(await self._scan_mcp_servers(client))

            if category in ("all", "ai"):
                tools.extend(await self._scan_github_trending(client, "ai"))

            if category in ("all", "devtools"):
                tools.extend(await self._scan_github_trending(client, "devtools"))

        # Score relevance
        for tool in tools:
            tool.relevance = self._score_relevance(tool)

        # Sort into buckets
        for tool in tools:
            tool_dict = {
                "name": tool.name,
                "description": tool.description,
                "url": tool.url,
                "stars": tool.stars,
                "category": tool.category,
                "source": tool.source,
            }
            if tool.relevance == "high":
                report.high_relevance.append(tool_dict)
            elif tool.relevance == "medium":
                report.medium_relevance.append(tool_dict)
            else:
                report.low_relevance.append(tool_dict)

        report.tools_found = len(tools)
        return report

    async def _scan_mcp_servers(self, client: httpx.AsyncClient) -> list[ToolInfo]:
        """Scan npm for MCP server packages."""
        tools = []
        try:
            # Search npm for MCP packages
            resp = await client.get(
                "https://registry.npmjs.org/-/v1/search",
                params={"text": "mcp server", "size": 20},
            )
            if resp.status_code == 200:
                data = resp.json()
                for pkg in data.get("objects", []):
                    p = pkg.get("package", {})
                    tools.append(ToolInfo(
                        name=p.get("name", ""),
                        description=p.get("description", "")[:200],
                        url=p.get("links", {}).get("npm", f"https://www.npmjs.com/package/{p.get('name', '')}"),
                        category="mcp",
                        source="npm",
                    ))
        except Exception as e:
            logger.warning(f"Failed to scan npm: {e}")

        return tools

    async def _scan_github_trending(
        self, client: httpx.AsyncClient, topic: str
    ) -> list[ToolInfo]:
        """Scan GitHub for trending repos in a topic area."""
        tools = []
        queries = {
            "ai": "ai coding agent tool",
            "devtools": "developer tools mcp server",
        }
        query = queries.get(topic, topic)

        try:
            resp = await client.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": f"{query} created:>{date.today().replace(day=1).isoformat()}",
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 15,
                },
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                for repo in data.get("items", []):
                    tools.append(ToolInfo(
                        name=repo.get("full_name", ""),
                        description=repo.get("description", "")[:200] if repo.get("description") else "",
                        url=repo.get("html_url", ""),
                        stars=repo.get("stargazers_count", 0),
                        category=topic,
                        source="github",
                    ))
        except Exception as e:
            logger.warning(f"Failed to scan GitHub: {e}")

        return tools

    def _score_relevance(self, tool: ToolInfo) -> str:
        """Score a tool's relevance to our stack."""
        text = f"{tool.name} {tool.description}".lower()

        for keyword in STACK_KEYWORDS["high"]:
            if keyword in text:
                return "high"

        for keyword in STACK_KEYWORDS["medium"]:
            if keyword in text:
                return "medium"

        return "low"


# ---------------------------------------------------------------------------
# Dependency Watch
# ---------------------------------------------------------------------------

@dataclass
class DepStatus:
    """Status of a single dependency."""
    name: str
    current: str
    latest: str = ""
    update_type: str = ""  # "patch" | "minor" | "major" | "unknown"
    has_security: bool = False


@dataclass
class DepReport:
    """Dependency check report for a project."""
    project: str = ""
    package_manager: str = ""  # "npm" | "pip" | "flutter"
    total_deps: int = 0
    outdated: list[dict] = field(default_factory=list)
    up_to_date: int = 0
    security_patches: list[dict] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Format dependency report as markdown."""
        lines = [
            f"# 📦 Dependency Report: {self.project}",
            f"> Package manager: `{self.package_manager}`",
            "",
            "## Summary",
            f"- Total dependencies: **{self.total_deps}**",
            f"- Up to date: **{self.up_to_date}**",
            f"- Outdated: **{len(self.outdated)}**",
        ]

        if self.security_patches:
            lines.append(f"- ⚠️ Security patches available: **{len(self.security_patches)}**")

        lines.append("")

        if self.security_patches:
            lines.extend(["## ⚠️ Security Patches", ""])
            for dep in self.security_patches:
                lines.append(
                    f"- **{dep['name']}**: {dep['current']} → {dep['latest']}"
                )
            lines.append("")

        if self.outdated:
            lines.extend(["## 📋 Outdated Dependencies", ""])
            # Group by update type
            major = [d for d in self.outdated if d.get("update_type") == "major"]
            minor = [d for d in self.outdated if d.get("update_type") == "minor"]
            patch = [d for d in self.outdated if d.get("update_type") == "patch"]
            other = [d for d in self.outdated if d.get("update_type") not in ("major", "minor", "patch")]

            if major:
                lines.append("### 🔴 Major Updates (breaking changes possible)")
                for d in major:
                    lines.append(f"- **{d['name']}**: `{d['current']}` → `{d['latest']}`")
                lines.append("")

            if minor:
                lines.append("### 🟡 Minor Updates")
                for d in minor:
                    lines.append(f"- **{d['name']}**: `{d['current']}` → `{d['latest']}`")
                lines.append("")

            if patch:
                lines.append("### 🟢 Patch Updates")
                for d in patch:
                    lines.append(f"- **{d['name']}**: `{d['current']}` → `{d['latest']}`")
                lines.append("")

            if other:
                lines.append("### ❓ Unknown")
                for d in other:
                    lines.append(f"- **{d['name']}**: `{d['current']}` → `{d['latest']}`")
                lines.append("")

        return "\n".join(lines)


class DependencyChecker:
    """Checks project dependencies for updates and security patches."""

    # Map project slugs to their local filesystem paths
    # This is populated from vault notes that have localPath info

    def __init__(self, vault_path: Path, project_paths: Optional[dict[str, str]] = None):
        self.vault_path = vault_path
        self.project_paths = project_paths or {}

    async def check(self, project: str) -> DepReport:
        """Check dependencies for a project."""
        report = DepReport(project=project)

        # Find project path
        project_path = self._resolve_project_path(project)
        if not project_path:
            report.package_manager = "unknown"
            return report

        # Detect package manager and check
        if (project_path / "package.json").exists():
            report.package_manager = "npm"
            await self._check_npm(project_path, report)
        elif (project_path / "pyproject.toml").exists():
            report.package_manager = "pip"
            await self._check_pip(project_path, report)
        elif (project_path / "requirements.txt").exists():
            report.package_manager = "pip"
            await self._check_pip(project_path, report)
        elif (project_path / "pubspec.yaml").exists():
            report.package_manager = "flutter"
            await self._check_flutter(project_path, report)
        else:
            report.package_manager = "unknown"

        return report

    def _resolve_project_path(self, project: str) -> Optional[Path]:
        """Resolve project slug to filesystem path."""
        # Check explicit mapping
        if project in self.project_paths:
            p = Path(self.project_paths[project])
            if p.exists():
                return p

        # Try common locations
        common_bases = [
            Path.home() / "Projects",
            Path.home() / "projects",
            Path.home() / "Developer",
        ]
        for base in common_bases:
            candidate = base / project
            if candidate.exists():
                return candidate

        return None

    async def _check_npm(self, project_path: Path, report: DepReport):
        """Check npm dependencies against registry."""
        pkg_file = project_path / "package.json"
        try:
            pkg_data = json.loads(pkg_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to read package.json: {e}")
            return

        deps = {}
        deps.update(pkg_data.get("dependencies", {}))
        deps.update(pkg_data.get("devDependencies", {}))
        report.total_deps = len(deps)

        async with httpx.AsyncClient(timeout=10.0) as client:
            for name, version_spec in deps.items():
                current = self._clean_version(version_spec)
                try:
                    resp = await client.get(
                        f"https://registry.npmjs.org/{name}/latest"
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        latest = data.get("version", "")
                        if latest and latest != current:
                            update_type = self._classify_update(current, latest)
                            dep_info = {
                                "name": name,
                                "current": current,
                                "latest": latest,
                                "update_type": update_type,
                            }
                            report.outdated.append(dep_info)
                        else:
                            report.up_to_date += 1
                except Exception:
                    pass  # Skip failed lookups

    async def _check_pip(self, project_path: Path, report: DepReport):
        """Check Python dependencies against PyPI."""
        deps: dict[str, str] = {}

        # Try pyproject.toml first
        pyproject = project_path / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8")
            # Simple regex-based parsing for dependencies
            in_deps = False
            for line in content.split("\n"):
                if line.strip() == "dependencies = [":
                    in_deps = True
                    continue
                if in_deps:
                    if line.strip() == "]":
                        break
                    # Parse "package>=1.0.0"
                    match = re.match(r'\s*"([^"]+)"', line)
                    if match:
                        dep_str = match.group(1)
                        parts = re.split(r"[><=~!]+", dep_str, maxsplit=1)
                        name = parts[0].strip()
                        version = parts[1].strip() if len(parts) > 1 else ""
                        # Remove extras like [cli]
                        name = re.sub(r"\[.*\]", "", name)
                        deps[name] = version

        # Try requirements.txt
        req_file = project_path / "requirements.txt"
        if req_file.exists() and not deps:
            for line in req_file.read_text(encoding="utf-8").split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = re.split(r"[><=~!]+", line, maxsplit=1)
                name = parts[0].strip()
                version = parts[1].strip() if len(parts) > 1 else ""
                deps[name] = version

        report.total_deps = len(deps)

        async with httpx.AsyncClient(timeout=10.0) as client:
            for name, current in deps.items():
                try:
                    resp = await client.get(
                        f"https://pypi.org/pypi/{name}/json"
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        latest = data.get("info", {}).get("version", "")
                        if latest and current and latest != current:
                            update_type = self._classify_update(current, latest)
                            report.outdated.append({
                                "name": name,
                                "current": current,
                                "latest": latest,
                                "update_type": update_type,
                            })
                        else:
                            report.up_to_date += 1
                except Exception:
                    pass

    async def _check_flutter(self, project_path: Path, report: DepReport):
        """Check Flutter/Dart dependencies against pub.dev."""
        pubspec = project_path / "pubspec.yaml"
        if not pubspec.exists():
            return

        content = pubspec.read_text(encoding="utf-8")
        deps: dict[str, str] = {}

        in_deps = False
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped in ("dependencies:", "dev_dependencies:"):
                in_deps = True
                continue
            if in_deps and not line.startswith(" ") and not line.startswith("\t"):
                in_deps = False
                continue
            if in_deps:
                match = re.match(r"\s+(\w[\w_]*)\s*:\s*\^?([0-9][^\s#]*)", line)
                if match:
                    deps[match.group(1)] = match.group(2)

        report.total_deps = len(deps)

        async with httpx.AsyncClient(timeout=10.0) as client:
            for name, current in deps.items():
                try:
                    resp = await client.get(
                        f"https://pub.dev/api/packages/{name}"
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        latest = data.get("latest", {}).get("version", "")
                        if latest and latest != current:
                            update_type = self._classify_update(current, latest)
                            report.outdated.append({
                                "name": name,
                                "current": current,
                                "latest": latest,
                                "update_type": update_type,
                            })
                        else:
                            report.up_to_date += 1
                except Exception:
                    pass

    @staticmethod
    def _clean_version(version_spec: str) -> str:
        """Clean version specifier like ^1.2.3 or ~1.2.3 to 1.2.3."""
        return re.sub(r"^[^0-9]*", "", version_spec)

    @staticmethod
    def _classify_update(current: str, latest: str) -> str:
        """Classify update as major, minor, or patch."""
        try:
            c_parts = [int(x) for x in current.split(".")[:3]]
            l_parts = [int(x) for x in latest.split(".")[:3]]

            # Pad to 3 parts
            while len(c_parts) < 3:
                c_parts.append(0)
            while len(l_parts) < 3:
                l_parts.append(0)

            if l_parts[0] > c_parts[0]:
                return "major"
            if l_parts[1] > c_parts[1]:
                return "minor"
            if l_parts[2] > c_parts[2]:
                return "patch"
            return "unknown"
        except (ValueError, IndexError):
            return "unknown"
