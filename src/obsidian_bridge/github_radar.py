"""GitHub Radar — Automatic discovery of trending repos and developers.

Tracks trending GitHub repositories, monitors developers, and analyzes
repos for relevance to nzt108-dev tech stack.

Components:
    TrendingScanner  — Find repos with rapid star growth
    RepoAnalyzer     — Parse README, topics, stats for a specific repo
    DeveloperWatcher — Maintain a watch list, check for new activity

All data comes from GitHub REST API (free tier: 60 req/hr without token,
5000 req/hr with GITHUB_TOKEN). Zero LLM cost.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# GitHub API base
GITHUB_API = "https://api.github.com"

# Relevance keywords — repos matching these score higher
RELEVANT_TOPICS = {
    "ai": [
        "artificial-intelligence", "machine-learning", "llm", "gpt",
        "openai", "langchain", "rag", "embeddings", "vector-database",
        "ai-agent", "autonomous", "deep-learning", "transformer",
    ],
    "mcp": [
        "model-context-protocol", "mcp", "mcp-server", "mcp-client",
        "claude", "anthropic",
    ],
    "devtools": [
        "developer-tools", "cli", "devtools", "linter", "formatter",
        "code-generation", "ide", "vscode", "neovim",
        "automation", "ci-cd", "github-actions",
    ],
    "mobile": [
        "flutter", "dart", "ios", "android", "react-native",
        "mobile", "swift", "kotlin",
    ],
    "web": [
        "nextjs", "react", "typescript", "tailwindcss", "vercel",
        "prisma", "supabase", "firebase",
    ],
}

# Flatten for quick lookup
ALL_RELEVANT_KEYWORDS = set()
for _kw_list in RELEVANT_TOPICS.values():
    ALL_RELEVANT_KEYWORDS.update(_kw_list)


# ─── Data Classes ─────────────────────────────────────────────────────

@dataclass
class TrendingRepo:
    """A trending GitHub repository."""
    full_name: str          # owner/repo
    description: str
    url: str
    stars: int
    forks: int
    language: str
    topics: list[str]
    created_at: str
    pushed_at: str
    relevance_score: float = 0.0
    relevance_reason: str = ""


@dataclass
class DeveloperProfile:
    """A watched GitHub developer."""
    username: str
    name: str
    bio: str
    public_repos: int
    followers: int
    url: str
    recent_repos: list[dict] = field(default_factory=list)


@dataclass
class RepoAnalysis:
    """Detailed analysis of a GitHub repository."""
    full_name: str
    description: str
    url: str
    stars: int
    forks: int
    language: str
    topics: list[str]
    license: str
    readme_summary: str
    size_kb: int
    open_issues: int
    created_at: str
    updated_at: str
    relevance_score: float
    relevance_reason: str
    applicable_to: list[str]  # which of our projects could benefit


# ─── HTTP Client ──────────────────────────────────────────────────────

def _get_headers(token: Optional[str] = None) -> dict:
    """Build GitHub API headers."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "obsidian-second-mind/1.2",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_token() -> Optional[str]:
    """Try to find a GitHub token from env."""
    import os
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


# ─── TrendingScanner ─────────────────────────────────────────────────

class TrendingScanner:
    """Find trending repositories on GitHub."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or _get_token()
        self.headers = _get_headers(self.token)

    def scan(
        self,
        topic: str = "all",
        days: int = 7,
        min_stars: int = 50,
        max_results: int = 20,
    ) -> list[TrendingRepo]:
        """Scan GitHub for trending repos.

        Uses /search/repositories with created:>DATE sort:stars
        to find repos gaining traction recently.
        """
        since = (date.today() - timedelta(days=days)).isoformat()

        # Build query
        q_parts = [f"created:>{since}", f"stars:>={min_stars}"]
        if topic != "all" and topic in RELEVANT_TOPICS:
            # Add topic keywords as search terms
            keywords = RELEVANT_TOPICS[topic][:5]
            topic_q = " OR ".join(keywords)
            q_parts.append(f"({topic_q})")

        query = " ".join(q_parts)

        url = f"{GITHUB_API}/search/repositories"
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": min(max_results, 30),
        }

        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(url, headers=self.headers, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            logger.error(f"GitHub API error: {e}")
            return []

        repos = []
        for item in data.get("items", [])[:max_results]:
            repo = TrendingRepo(
                full_name=item["full_name"],
                description=item.get("description") or "",
                url=item["html_url"],
                stars=item["stargazers_count"],
                forks=item["forks_count"],
                language=item.get("language") or "Unknown",
                topics=item.get("topics", []),
                created_at=item.get("created_at", ""),
                pushed_at=item.get("pushed_at", ""),
            )
            repo.relevance_score, repo.relevance_reason = _score_relevance(
                repo.description, repo.topics, repo.language
            )
            repos.append(repo)

        # Sort by relevance, then stars
        repos.sort(key=lambda r: (-r.relevance_score, -r.stars))
        return repos

    def to_markdown(self, repos: list[TrendingRepo], topic: str = "all") -> str:
        """Convert results to a markdown report."""
        lines = [
            "# 🔍 GitHub Radar — Trending Repos",
            f"> Scanned on {date.today()} | Topic: {topic} | Found: {len(repos)}",
            "",
        ]
        if not repos:
            lines.append("No trending repos found matching criteria.")
            return "\n".join(lines)

        # High relevance
        high = [r for r in repos if r.relevance_score >= 0.6]
        medium = [r for r in repos if 0.3 <= r.relevance_score < 0.6]
        low = [r for r in repos if r.relevance_score < 0.3]

        if high:
            lines.append("## 🟢 High Relevance\n")
            for r in high:
                lines.extend(_format_repo_md(r))

        if medium:
            lines.append("## 🟡 Medium Relevance\n")
            for r in medium:
                lines.extend(_format_repo_md(r))

        if low:
            lines.append("## ⚪ Other\n")
            for r in low[:5]:  # limit low-relevance
                lines.extend(_format_repo_md(r))

        return "\n".join(lines)


# ─── RepoAnalyzer ────────────────────────────────────────────────────

class RepoAnalyzer:
    """Analyze a specific GitHub repository in detail."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or _get_token()
        self.headers = _get_headers(self.token)

    def analyze(self, repo_full_name: str) -> Optional[RepoAnalysis]:
        """Analyze owner/repo and return detailed analysis."""
        url = f"{GITHUB_API}/repos/{repo_full_name}"

        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(url, headers=self.headers)
                resp.raise_for_status()
                data = resp.json()

                # Fetch README
                readme_url = f"{GITHUB_API}/repos/{repo_full_name}/readme"
                readme_resp = client.get(readme_url, headers=self.headers)
                readme_text = ""
                if readme_resp.status_code == 200:
                    import base64
                    content = readme_resp.json().get("content", "")
                    try:
                        readme_text = base64.b64decode(content).decode(
                            "utf-8", errors="ignore"
                        )
                    except Exception:
                        readme_text = ""
        except httpx.HTTPError as e:
            logger.error(f"GitHub API error for {repo_full_name}: {e}")
            return None

        # Parse README summary
        readme_summary = _extract_readme_summary(readme_text)

        # Score relevance
        topics = data.get("topics", [])
        description = data.get("description") or ""
        language = data.get("language") or "Unknown"
        score, reason = _score_relevance(description, topics, language)

        # Determine which of our projects could benefit
        applicable = _find_applicable_projects(description, topics, language)

        license_name = ""
        lic = data.get("license")
        if lic and isinstance(lic, dict):
            license_name = lic.get("spdx_id") or lic.get("name") or ""

        return RepoAnalysis(
            full_name=data["full_name"],
            description=description,
            url=data["html_url"],
            stars=data["stargazers_count"],
            forks=data["forks_count"],
            language=language,
            topics=topics,
            license=license_name,
            readme_summary=readme_summary,
            size_kb=data.get("size", 0),
            open_issues=data.get("open_issues_count", 0),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            relevance_score=score,
            relevance_reason=reason,
            applicable_to=applicable,
        )

    def to_markdown(self, analysis: RepoAnalysis) -> str:
        """Convert analysis to markdown."""
        lines = [
            f"# 🔬 Repo Analysis: {analysis.full_name}",
            "",
            f"**{analysis.description}**",
            "",
            "| Stat | Value |",
            "|------|-------|",
            f"| ⭐ Stars | {analysis.stars:,} |",
            f"| 🍴 Forks | {analysis.forks:,} |",
            f"| 🔤 Language | {analysis.language} |",
            f"| 📄 License | {analysis.license or 'None'} |",
            f"| 📦 Size | {analysis.size_kb:,} KB |",
            f"| 🐛 Issues | {analysis.open_issues} |",
            f"| 📅 Created | {analysis.created_at[:10]} |",
            f"| 🔄 Updated | {analysis.updated_at[:10]} |",
            "",
            f"**Topics:** {', '.join(analysis.topics) if analysis.topics else 'None'}",
            "",
            f"**Relevance:** {analysis.relevance_score:.0%} — {analysis.relevance_reason}",
            "",
        ]
        if analysis.applicable_to:
            lines.append(f"**Applicable to our projects:** {', '.join(analysis.applicable_to)}")
            lines.append("")

        if analysis.readme_summary:
            lines.extend([
                "## README Summary",
                "",
                analysis.readme_summary,
                "",
            ])

        lines.append(f"🔗 [{analysis.full_name}]({analysis.url})")
        return "\n".join(lines)


# ─── DeveloperWatcher ─────────────────────────────────────────────────

class DeveloperWatcher:
    """Watch GitHub developers for new activity."""

    WATCHLIST_PATH = "_global/github-watchlist.md"

    def __init__(self, vault_path: Path, token: Optional[str] = None):
        self.vault_path = vault_path
        self.token = token or _get_token()
        self.headers = _get_headers(self.token)

    def add(self, username: str, category: str = "general") -> str:
        """Add a developer to the watch list."""
        watchlist = self._load_watchlist()

        # Check if already exists
        for entry in watchlist:
            if entry["username"].lower() == username.lower():
                return f"⚠️ {username} already in watch list (category: {entry['category']})"

        watchlist.append({
            "username": username,
            "category": category,
            "added": date.today().isoformat(),
        })
        self._save_watchlist(watchlist)
        return f"✅ Added @{username} to watch list (category: {category})"

    def remove(self, username: str) -> str:
        """Remove a developer from the watch list."""
        watchlist = self._load_watchlist()
        before = len(watchlist)
        watchlist = [
            e for e in watchlist
            if e["username"].lower() != username.lower()
        ]
        if len(watchlist) == before:
            return f"⚠️ @{username} not found in watch list"
        self._save_watchlist(watchlist)
        return f"✅ Removed @{username} from watch list"

    def list_watched(self) -> str:
        """List all watched developers."""
        watchlist = self._load_watchlist()
        if not watchlist:
            return "Watch list is empty. Add developers with watch_developer(username, action='add')"

        lines = [
            "# 👀 GitHub Watch List",
            "",
            "| # | Username | Category | Added |",
            "|---|----------|----------|-------|",
        ]
        for i, entry in enumerate(watchlist, 1):
            lines.append(
                f"| {i} | [@{entry['username']}]"
                f"(https://github.com/{entry['username']}) | "
                f"{entry['category']} | {entry['added']} |"
            )
        return "\n".join(lines)

    def check(self, username: str) -> Optional[DeveloperProfile]:
        """Check a developer's recent activity."""
        try:
            with httpx.Client(timeout=15) as client:
                # Get profile
                resp = client.get(
                    f"{GITHUB_API}/users/{username}",
                    headers=self.headers,
                )
                resp.raise_for_status()
                user = resp.json()

                # Get recent repos (sorted by updated)
                repos_resp = client.get(
                    f"{GITHUB_API}/users/{username}/repos",
                    headers=self.headers,
                    params={"sort": "updated", "per_page": 10},
                )
                repos_resp.raise_for_status()
                repos_data = repos_resp.json()

        except httpx.HTTPError as e:
            logger.error(f"GitHub API error for @{username}: {e}")
            return None

        recent_repos = []
        for r in repos_data[:10]:
            recent_repos.append({
                "name": r["full_name"],
                "description": r.get("description") or "",
                "stars": r["stargazers_count"],
                "language": r.get("language") or "",
                "updated": r.get("pushed_at", "")[:10],
                "url": r["html_url"],
            })

        return DeveloperProfile(
            username=user["login"],
            name=user.get("name") or user["login"],
            bio=user.get("bio") or "",
            public_repos=user.get("public_repos", 0),
            followers=user.get("followers", 0),
            url=user["html_url"],
            recent_repos=recent_repos,
        )

    def check_to_markdown(self, profile: DeveloperProfile) -> str:
        """Convert developer profile to markdown."""
        lines = [
            f"# 👤 @{profile.username}",
            "",
            f"**{profile.name}** — {profile.bio}" if profile.bio else f"**{profile.name}**",
            "",
            "| Stat | Value |",
            "|------|-------|",
            f"| Repos | {profile.public_repos} |",
            f"| Followers | {profile.followers:,} |",
            f"| Profile | [{profile.username}]({profile.url}) |",
            "",
            "## Recent Activity",
            "",
            "| Repo | ⭐ | Language | Updated |",
            "|------|----|----------|---------|",
        ]
        for r in profile.recent_repos:
            lines.append(
                f"| [{r['name']}]({r['url']}) | "
                f"{r['stars']} | {r['language']} | {r['updated']} |"
            )
        return "\n".join(lines)

    def _load_watchlist(self) -> list[dict]:
        """Load watch list from vault."""
        path = self.vault_path / self.WATCHLIST_PATH
        if not path.exists():
            return []

        content = path.read_text(encoding="utf-8")
        entries = []
        for line in content.split("\n"):
            # Parse table rows: | # | @username | category | date |
            m = re.match(
                r"\|\s*\d+\s*\|\s*\[@?(\w+)\].*?\|\s*(\w+)\s*\|\s*([\d-]+)\s*\|",
                line,
            )
            if m:
                entries.append({
                    "username": m.group(1),
                    "category": m.group(2),
                    "added": m.group(3),
                })
        return entries

    def _save_watchlist(self, watchlist: list[dict]):
        """Save watch list to vault as markdown table."""
        lines = [
            "---",
            "type: guidelines",
            f"updated: {datetime.now(timezone.utc).isoformat()}",
            "tags: [github, watchlist]",
            "---",
            "",
            "# 👀 GitHub Watch List",
            "",
            "Developers being monitored for new repos and activity.",
            "",
            "| # | Username | Category | Added |",
            "|---|----------|----------|-------|",
        ]
        for i, entry in enumerate(watchlist, 1):
            lines.append(
                f"| {i} | [@{entry['username']}]"
                f"(https://github.com/{entry['username']}) | "
                f"{entry['category']} | {entry['added']} |"
            )

        path = self.vault_path / self.WATCHLIST_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")


# ─── Helpers ──────────────────────────────────────────────────────────

def _score_relevance(
    description: str, topics: list[str], language: str
) -> tuple[float, str]:
    """Score how relevant a repo is to our tech stack. Returns (score, reason)."""
    score = 0.0
    reasons = []

    desc_lower = (description or "").lower()
    all_text = desc_lower + " " + " ".join(topics)

    # Check topic keywords
    for category, keywords in RELEVANT_TOPICS.items():
        matches = [kw for kw in keywords if kw in all_text]
        if matches:
            score += 0.2 * min(len(matches), 3)
            reasons.append(f"{category}: {', '.join(matches[:3])}")

    # Language bonus
    our_languages = {"python", "typescript", "javascript", "dart"}
    if language and language.lower() in our_languages:
        score += 0.15
        reasons.append(f"language: {language}")

    # MCP bonus (extra relevant)
    if "mcp" in all_text or "model-context-protocol" in all_text:
        score += 0.3
        reasons.append("MCP related")

    score = min(score, 1.0)
    reason = "; ".join(reasons) if reasons else "no relevant signals"
    return round(score, 2), reason


def _find_applicable_projects(
    description: str, topics: list[str], language: str
) -> list[str]:
    """Determine which of our projects could benefit."""
    text = (description or "").lower() + " " + " ".join(topics)
    applicable = []

    checks = [
        ("obsidian-second-mind", ["vault", "obsidian", "knowledge", "mcp", "ai-agent"]),
        ("architect-portfolio", ["portfolio", "nextjs", "prisma", "admin", "dashboard"]),
        ("brieftube", ["youtube", "video", "summary", "ai", "flutter"]),
        ("fast-lending", ["landing", "saas", "template", "website"]),
        ("botseller", ["telegram", "bot", "chatbot", "messaging"]),
    ]
    for project, keywords in checks:
        if any(kw in text for kw in keywords):
            applicable.append(project)

    return applicable


def _extract_readme_summary(readme: str, max_chars: int = 500) -> str:
    """Extract the first meaningful paragraph from README."""
    if not readme:
        return ""

    lines = readme.split("\n")
    paragraphs = []
    current = []

    for line in lines:
        stripped = line.strip()
        # Skip badges, images, HTML
        if stripped.startswith("![") or stripped.startswith("<"):
            continue
        if stripped.startswith("# "):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if stripped.startswith("## "):
            if current:
                paragraphs.append(" ".join(current))
            break  # Stop at first H2
        if stripped:
            current.append(stripped)
        elif current:
            paragraphs.append(" ".join(current))
            current = []

    if current:
        paragraphs.append(" ".join(current))

    # Return first non-empty paragraph
    for p in paragraphs:
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", p)  # remove links
        cleaned = re.sub(r"[*_`]", "", cleaned)  # remove formatting
        if len(cleaned) > 20:
            return cleaned[:max_chars]

    return ""


def _format_repo_md(repo: TrendingRepo) -> list[str]:
    """Format a repo for markdown report."""
    return [
        f"### [{repo.full_name}]({repo.url})",
        f"> {repo.description}" if repo.description else "",
        f"- ⭐ **{repo.stars:,}** stars | 🔤 {repo.language}"
        + (f" | Topics: {', '.join(repo.topics[:5])}" if repo.topics else ""),
        f"- Relevance: {repo.relevance_score:.0%} — {repo.relevance_reason}",
        "",
    ]
