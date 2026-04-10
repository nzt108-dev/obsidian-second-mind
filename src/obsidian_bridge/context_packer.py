"""Context Packer — Package a project into a single file for AI.

Scans a project directory, intelligently filters files, and packs
everything into one structured markdown file optimized for LLM context.

Modes:
    full    — All source files, full content (~200k tokens)
    compact — Key files full, supporting compressed (~50k tokens)
    minimal — Only structure + key files heads (~10k tokens)

Usage via MCP:
    pack_context(project="architect-portfolio", mode="compact")
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────

# Always skip these directories
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", ".env",
    ".next", ".nuxt", "build", "dist", ".dart_tool", ".flutter-plugins",
    ".idea", ".vscode", ".gradle", "Pods", "ios/Pods",
    "coverage", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "egg-info", ".egg-info", ".tox", "htmlcov",
}

# Always skip these file patterns
SKIP_FILES = {
    ".DS_Store", "Thumbs.db", ".gitignore", ".gitattributes",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Pipfile.lock", "Cargo.lock",
    "pubspec.lock", "Podfile.lock",
}

# Skip these extensions
SKIP_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".webm",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".pyc", ".pyo", ".class", ".o", ".so", ".dylib",
    ".db", ".sqlite", ".sqlite3",
    ".map", ".min.js", ".min.css",
}

# High-priority files (always included in full)
HIGH_PRIORITY_PATTERNS = {
    # Config
    "package.json", "tsconfig.json", "pyproject.toml", "pubspec.yaml",
    "prisma/schema.prisma", ".env.example", "docker-compose.yml",
    "Dockerfile", "Makefile",
    # Architecture
    "README.md", "ARCHITECTURE.md",
    # Entry points
    "main.py", "app.py", "run.py", "index.ts", "index.js",
    "main.dart", "lib/main.dart",
}

# Medium-priority path patterns
MEDIUM_PRIORITY_PATTERNS = {
    "route", "api", "model", "schema", "service", "controller",
    "middleware", "config", "auth", "util", "helper", "lib",
    "screen", "page", "view", "component", "widget",
}

# Low-priority path patterns (compressed more aggressively)
LOW_PRIORITY_PATTERNS = {
    "test", "spec", "mock", "fixture", "migration",
    "style", "css", "theme", "asset",
}

# Stack detection
STACK_DETECTORS = {
    "package.json": "Node.js",
    "tsconfig.json": "TypeScript",
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "pubspec.yaml": "Flutter/Dart",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "Gemfile": "Ruby",
    "pom.xml": "Java/Maven",
    "build.gradle": "Java/Gradle",
}

# Mode token budgets (approximate)
MODE_BUDGETS = {
    "full": 200_000,
    "compact": 50_000,
    "minimal": 10_000,
}


# ─── Data Classes ─────────────────────────────────────────────────────

@dataclass
class PackedFile:
    """A file included in the context pack."""
    rel_path: str
    content: str
    size_lines: int
    priority: str       # high, medium, low
    compressed: bool    # Whether content was truncated
    token_estimate: int


@dataclass
class ProjectContext:
    """Complete packed context of a project."""
    name: str
    stack: list[str]
    total_files: int
    total_lines: int
    included_files: int
    tree: str
    files: list[PackedFile]
    token_estimate: int
    mode: str
    db_schema: str = ""


# ─── ProjectPacker ────────────────────────────────────────────────────

class ProjectPacker:
    """Pack a project into a single structured context."""

    def __init__(self, project_dir: Path, mode: str = "compact"):
        self.project_dir = project_dir
        self.name = project_dir.name
        self.mode = mode
        self.budget = MODE_BUDGETS.get(mode, MODE_BUDGETS["compact"])

    def pack(self) -> ProjectContext:
        """Pack the project and return structured context."""

        # 1. Detect stack
        stack = self._detect_stack()

        # 2. Discover files
        all_files = self._discover_files()

        # 3. Classify priority
        classified = self._classify(all_files)

        # 4. Generate tree
        tree = self._generate_tree(all_files)

        # 5. Extract DB schema
        db_schema = self._extract_db_schema()

        # 6. Pack files with budget
        packed = self._pack_files(classified)

        total_lines = sum(f.size_lines for f in packed)
        token_est = sum(f.token_estimate for f in packed)

        return ProjectContext(
            name=self.name,
            stack=stack,
            total_files=len(all_files),
            total_lines=total_lines,
            included_files=len(packed),
            tree=tree,
            files=packed,
            token_estimate=token_est,
            mode=self.mode,
            db_schema=db_schema,
        )

    def _detect_stack(self) -> list[str]:
        """Detect tech stack from config files."""
        stack = []
        for filename, tech in STACK_DETECTORS.items():
            if (self.project_dir / filename).exists():
                stack.append(tech)

        # Extra detection from package.json
        pkg_path = self.project_dir / "package.json"
        if pkg_path.exists():
            try:
                import json
                pkg = json.loads(pkg_path.read_text())
                deps = {
                    **pkg.get("dependencies", {}),
                    **pkg.get("devDependencies", {}),
                }
                if "next" in deps:
                    stack.append("Next.js")
                if "react" in deps:
                    stack.append("React")
                if "@prisma/client" in deps or "prisma" in deps:
                    stack.append("Prisma")
                if "tailwindcss" in deps:
                    stack.append("TailwindCSS")
            except Exception:
                pass

        return list(dict.fromkeys(stack))  # dedupe preserving order

    def _discover_files(self) -> list[Path]:
        """Discover all relevant source files."""
        files = []
        for path in sorted(self.project_dir.rglob("*")):
            if not path.is_file():
                continue

            # Skip directories
            parts = set(path.relative_to(self.project_dir).parts)
            if parts & SKIP_DIRS:
                continue

            # Skip files
            if path.name in SKIP_FILES:
                continue
            if path.suffix.lower() in SKIP_EXTS:
                continue

            files.append(path)

        return files

    def _classify(self, files: list[Path]) -> list[tuple[Path, str]]:
        """Classify files by priority: high, medium, low."""
        result = []
        for f in files:
            rel = str(f.relative_to(self.project_dir))

            if any(pat in rel for pat in HIGH_PRIORITY_PATTERNS):
                result.append((f, "high"))
            elif any(
                pat in rel.lower()
                for pat in LOW_PRIORITY_PATTERNS
            ):
                result.append((f, "low"))
            elif any(
                pat in rel.lower()
                for pat in MEDIUM_PRIORITY_PATTERNS
            ):
                result.append((f, "medium"))
            else:
                result.append((f, "medium"))

        # Sort: high first, then medium, then low
        priority_order = {"high": 0, "medium": 1, "low": 2}
        result.sort(key=lambda x: (priority_order[x[1]], str(x[0])))
        return result

    def _generate_tree(self, files: list[Path]) -> str:
        """Generate file tree string."""
        lines = [f"📁 {self.name}/"]

        # Group by first directory
        dirs: dict[str, list[str]] = {}
        root_files = []
        for f in files:
            rel = f.relative_to(self.project_dir)
            parts = rel.parts
            if len(parts) == 1:
                root_files.append(parts[0])
            else:
                top_dir = parts[0]
                rest = "/".join(parts[1:])
                if top_dir not in dirs:
                    dirs[top_dir] = []
                dirs[top_dir].append(rest)

        for rf in sorted(root_files):
            lines.append(f"├── {rf}")

        for d in sorted(dirs.keys()):
            child_count = len(dirs[d])
            lines.append(f"├── {d}/ ({child_count} files)")
            # Show first few children
            for child in dirs[d][:5]:
                lines.append(f"│   ├── {child}")
            if child_count > 5:
                lines.append(f"│   └── ... +{child_count - 5} more")

        return "\n".join(lines)

    def _extract_db_schema(self) -> str:
        """Extract database schema if available."""
        # Prisma
        schema_path = self.project_dir / "prisma" / "schema.prisma"
        if schema_path.exists():
            try:
                return schema_path.read_text(encoding="utf-8")
            except Exception:
                pass

        # Django models.py
        for models_file in self.project_dir.rglob("models.py"):
            if "node_modules" not in str(models_file):
                try:
                    return models_file.read_text(encoding="utf-8")[:3000]
                except Exception:
                    pass

        return ""

    def _pack_files(
        self, classified: list[tuple[Path, str]]
    ) -> list[PackedFile]:
        """Pack files within token budget."""
        packed = []
        tokens_used = 0

        for path, priority in classified:
            if tokens_used >= self.budget:
                break

            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            lines = content.split("\n")
            size_lines = len(lines)

            # Determine how much to include
            if self.mode == "minimal":
                if priority == "high":
                    content = _truncate(content, max_lines=50)
                elif priority == "medium":
                    content = _truncate(content, max_lines=20)
                else:
                    continue  # Skip low priority in minimal
            elif self.mode == "compact":
                if priority == "high":
                    content = content  # Full content
                elif priority == "medium":
                    content = _truncate(content, max_lines=100)
                else:
                    content = _truncate(content, max_lines=30)
            # else: full mode — include everything

            token_est = _estimate_tokens(content)
            compressed = len(content.split("\n")) < size_lines

            packed.append(PackedFile(
                rel_path=str(path.relative_to(self.project_dir)),
                content=content,
                size_lines=size_lines,
                priority=priority,
                compressed=compressed,
                token_estimate=token_est,
            ))
            tokens_used += token_est

        return packed

    def to_markdown(self, ctx: ProjectContext) -> str:
        """Convert packed context to markdown."""
        lines = [
            f"# 📦 Project Context: {ctx.name}",
            "",
            f"> Mode: **{ctx.mode}** | "
            f"Files: {ctx.included_files}/{ctx.total_files} | "
            f"~{ctx.token_estimate:,} tokens",
            "",
            "## Stack",
            "",
            ", ".join(ctx.stack) if ctx.stack else "Unknown",
            "",
            "## File Tree",
            "",
            "```",
            ctx.tree,
            "```",
            "",
        ]

        if ctx.db_schema:
            lines.extend([
                "## Database Schema",
                "",
                "```prisma",
                ctx.db_schema[:3000],
                "```",
                "",
            ])

        lines.extend(["## Source Files", ""])

        for f in ctx.files:
            ext = Path(f.rel_path).suffix.lstrip(".")
            lang = ext if ext else "text"
            compressed_tag = " *(compressed)*" if f.compressed else ""

            lines.extend([
                f"### `{f.rel_path}`{compressed_tag}",
                "",
                f"```{lang}",
                f"{f.content}",
                "```",
                "",
            ])

        lines.extend([
            "---",
            f"*Packed by Obsidian Second Mind v1.2 | {ctx.mode} mode*",
        ])

        return "\n".join(lines)


# ─── Helpers ──────────────────────────────────────────────────────────

def _truncate(content: str, max_lines: int = 50) -> str:
    """Truncate content keeping head and tail."""
    lines = content.split("\n")
    if len(lines) <= max_lines:
        return content

    head_lines = max_lines * 2 // 3
    tail_lines = max_lines - head_lines
    omitted = len(lines) - head_lines - tail_lines

    head = "\n".join(lines[:head_lines])
    tail = "\n".join(lines[-tail_lines:])

    return f"{head}\n\n... [{omitted} lines omitted] ...\n\n{tail}"


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token)."""
    return len(text) // 4
