"""Auto Architect — generates architecture diagrams from project code.

v1.1.0: Scans project source files, detects layers and dependencies,
generates Mermaid diagrams stored in the vault.

No LLM required — uses Python AST + regex import parsing.
Lightweight: scans only import statements, not full code.
"""
import ast
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Layer Detection
# ---------------------------------------------------------------------------

# Heuristic patterns for detecting architectural layers
LAYER_PATTERNS: dict[str, list[str]] = {
    "api": [
        "route", "router", "endpoint", "controller", "handler",
        "api", "view", "views", "pages", "app",
    ],
    "service": [
        "service", "usecase", "use_case", "logic", "manager",
        "provider", "interactor", "command", "query",
    ],
    "model": [
        "model", "schema", "entity", "domain", "dto",
        "type", "types", "interface", "interfaces",
    ],
    "data": [
        "repository", "repo", "dao", "database", "db",
        "migration", "seed", "fixture", "prisma", "drizzle",
        "storage", "cache",
    ],
    "config": [
        "config", "setting", "env", "constant",
    ],
    "util": [
        "util", "utils", "helper", "helpers", "lib",
        "common", "shared", "core",
    ],
    "test": [
        "test", "spec", "fixture", "__test__", "__tests__",
    ],
    "ui": [
        "component", "widget", "screen", "page",
        "layout", "template", "ui",
    ],
}


def _detect_layer(file_path: str) -> str:
    """Detect architectural layer from file path."""
    path_lower = file_path.lower()
    parts = Path(path_lower).parts + (Path(path_lower).stem,)

    for layer, keywords in LAYER_PATTERNS.items():
        for kw in keywords:
            for part in parts:
                if kw in part:
                    return layer

    return "other"


# ---------------------------------------------------------------------------
# Import Parsers
# ---------------------------------------------------------------------------

# Python: use AST
def _parse_python_imports(file_path: Path) -> list[str]:
    """Extract import targets from a Python file using AST.

    Returns both top-level package AND leaf module names for better
    internal edge matching. E.g. 'from obsidian_bridge.parser import X'
    yields ['obsidian_bridge', 'parser'].
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                imports.append(parts[0])
                if len(parts) > 1:
                    imports.append(parts[-1])  # leaf module
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                parts = node.module.split(".")
                imports.append(parts[0])
                if len(parts) > 1:
                    imports.append(parts[-1])  # leaf module
    return imports


# TypeScript/JavaScript: regex
_TS_IMPORT = re.compile(
    r"""(?:import\s+.*?from\s+['"]([^'"]+)['"]|"""
    r"""require\s*\(\s*['"]([^'"]+)['"]\s*\))""",
    re.MULTILINE,
)


def _parse_ts_imports(file_path: Path) -> list[str]:
    """Extract import targets from a TS/JS file using regex."""
    try:
        source = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    imports = []
    for match in _TS_IMPORT.finditer(source):
        target = match.group(1) or match.group(2)
        if target:
            # Normalize: ./foo/bar → foo/bar, @scope/pkg → @scope/pkg
            clean = target.lstrip("./")
            if clean:
                imports.append(clean.split("/")[0])
    return imports


# Dart/Flutter: regex
_DART_IMPORT = re.compile(r"import\s+['\"]([^'\"]+)['\"]", re.MULTILINE)


def _parse_dart_imports(file_path: Path) -> list[str]:
    """Extract import targets from a Dart file using regex."""
    try:
        source = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    imports = []
    for match in _DART_IMPORT.finditer(source):
        target = match.group(1)
        if target.startswith("package:"):
            # package:my_app/models/user.dart → my_app
            pkg = target.replace("package:", "").split("/")[0]
            imports.append(pkg)
        elif not target.startswith("dart:"):
            imports.append(target.split("/")[0])
    return imports


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ModuleInfo:
    """Information about a single source module."""
    path: str          # Relative path from project root
    name: str          # Module name (stem)
    layer: str         # Detected layer
    language: str      # python, typescript, dart
    imports: list[str] = field(default_factory=list)
    size_lines: int = 0


@dataclass
class ArchEdge:
    """A dependency edge between two modules."""
    source: str   # source module path
    target: str   # target module path
    weight: int = 1  # number of imports


@dataclass
class ArchitectureMap:
    """Complete architecture map for a project."""
    project: str
    modules: list[ModuleInfo] = field(default_factory=list)
    edges: list[ArchEdge] = field(default_factory=list)
    layers: dict[str, list[str]] = field(default_factory=dict)
    external_deps: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    def to_mermaid(self) -> str:
        """Generate Mermaid flowchart diagram."""
        lines = ["graph TD"]

        # Layer subgraphs
        layer_order = ["ui", "api", "service", "model", "data", "config", "util"]
        layer_labels = {
            "ui": "🖥️ UI Layer",
            "api": "🔌 API Layer",
            "service": "⚙️ Service Layer",
            "model": "📋 Model Layer",
            "data": "💾 Data Layer",
            "config": "🔧 Config",
            "util": "🛠️ Utils",
            "other": "📁 Other",
        }

        # Group modules by layer
        layer_modules: dict[str, list[ModuleInfo]] = {}
        for mod in self.modules:
            layer_modules.setdefault(mod.layer, []).append(mod)

        # Emit subgraphs
        for layer in layer_order + ["other"]:
            mods = layer_modules.get(layer, [])
            if not mods:
                continue
            label = layer_labels.get(layer, layer)
            lines.append(f"    subgraph {layer}[\"{label}\"]")
            for mod in sorted(mods, key=lambda m: m.name):
                node_id = _safe_id(mod.path)
                size_badge = f" ({mod.size_lines}L)" if mod.size_lines > 0 else ""
                lines.append(f"        {node_id}[\"{mod.name}{size_badge}\"]")
            lines.append("    end")

        # Emit edges
        known_paths = {mod.path for mod in self.modules}
        for edge in self.edges:
            if edge.source in known_paths and edge.target in known_paths:
                src_id = _safe_id(edge.source)
                tgt_id = _safe_id(edge.target)
                lines.append(f"    {src_id} --> {tgt_id}")

        # Styling
        lines.append("")
        layer_colors = {
            "api": "#4CAF50", "service": "#2196F3", "model": "#FF9800",
            "data": "#9C27B0", "config": "#607D8B", "util": "#795548",
            "ui": "#E91E63", "other": "#9E9E9E",
        }
        for layer, color in layer_colors.items():
            mods = layer_modules.get(layer, [])
            if mods:
                ids = ",".join(_safe_id(m.path) for m in mods)
                lines.append(f"    style {ids} fill:{color},color:#fff")

        return "\n".join(lines)

    def to_markdown(self) -> str:
        """Generate full architecture map as Markdown."""
        lines = [
            f"# 🗺️ Architecture Map — {self.project}",
            f"> Auto-generated on {date.today().isoformat()}",
            "",
        ]

        # Stats
        lines.append("## 📊 Stats")
        lines.append(f"- **Modules**: {len(self.modules)}")
        lines.append(f"- **Dependencies**: {len(self.edges)}")
        lines.append(f"- **Layers**: {len(self.layers)}")
        if self.external_deps:
            lines.append(f"- **External deps**: {len(self.external_deps)}")
        lines.append("")

        # Layer summary
        lines.append("## 🏗️ Layer Summary")
        lines.append("")
        lines.append("| Layer | Modules | Files |")
        lines.append("|-------|---------|-------|")
        for layer, paths in sorted(self.layers.items()):
            names = ", ".join(Path(p).stem for p in paths[:5])
            if len(paths) > 5:
                names += f" +{len(paths) - 5} more"
            lines.append(f"| {layer} | {len(paths)} | {names} |")
        lines.append("")

        # Mermaid diagram
        lines.append("## 🔗 Dependency Graph")
        lines.append("")
        lines.append("```mermaid")
        lines.append(self.to_mermaid())
        lines.append("```")
        lines.append("")

        # Module details
        lines.append("## 📁 Modules")
        lines.append("")
        for mod in sorted(self.modules, key=lambda m: (m.layer, m.name)):
            lines.append(f"- **{mod.name}** (`{mod.path}`) — {mod.layer}")
            if mod.imports:
                internal = [i for i in mod.imports if i != mod.name][:5]
                if internal:
                    lines.append(f"  - imports: {', '.join(internal)}")
        lines.append("")

        # External dependencies
        if self.external_deps:
            lines.append("## 📦 External Dependencies")
            lines.append("")
            for dep in sorted(self.external_deps):
                lines.append(f"- `{dep}`")
            lines.append("")

        return "\n".join(lines)


def _safe_id(path: str) -> str:
    """Convert file path to a safe Mermaid node ID."""
    return re.sub(r"[^a-zA-Z0-9]", "_", path).strip("_")


# ---------------------------------------------------------------------------
# Project Scanner
# ---------------------------------------------------------------------------

# Files/dirs to always skip
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".dart_tool", "build",
    ".next", ".nuxt", "dist", "coverage", ".venv", "venv",
    ".eggs", "*.egg-info", ".mypy_cache", ".ruff_cache",
    ".pytest_cache", ".gradle", "ios", "android", "macos", "linux", "windows",
    "web", ".idea", ".vscode",
}

LANG_EXTENSIONS = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".dart": "dart",
}


class ProjectScanner:
    """Scan a project and build its architecture map."""

    def __init__(self, project_dir: Path, project_name: str = ""):
        self.project_dir = project_dir.resolve()
        self.project_name = project_name or project_dir.name

    def scan(self, max_files: int = 200) -> ArchitectureMap:
        """Scan project and return architecture map."""
        arch = ArchitectureMap(project=self.project_name)
        modules: dict[str, ModuleInfo] = {}

        # 1. Discover source files
        source_files = self._discover_files(max_files)
        if not source_files:
            logger.warning(f"No source files found in {self.project_dir}")
            return arch

        # 2. Parse each file
        for file_path in source_files:
            rel_path = str(file_path.relative_to(self.project_dir))
            ext = file_path.suffix
            lang = LANG_EXTENSIONS.get(ext, "")

            # Parse imports
            if lang == "python":
                imports = _parse_python_imports(file_path)
            elif lang in ("typescript", "javascript"):
                imports = _parse_ts_imports(file_path)
            elif lang == "dart":
                imports = _parse_dart_imports(file_path)
            else:
                continue

            # Count lines (fast)
            try:
                line_count = sum(1 for _ in file_path.open(encoding="utf-8"))
            except OSError:
                line_count = 0

            mod = ModuleInfo(
                path=rel_path,
                name=file_path.stem,
                layer=_detect_layer(rel_path),
                language=lang,
                imports=imports,
                size_lines=line_count,
            )
            modules[rel_path] = mod

        arch.modules = list(modules.values())

        # 3. Build edges (internal dependencies)
        stem_to_path: dict[str, str] = {}
        for path, mod in modules.items():
            stem_to_path[mod.name] = path

        external_deps: set[str] = set()
        seen_edges: set[tuple[str, str]] = set()

        for mod in arch.modules:
            for imp in mod.imports:
                if imp in stem_to_path:
                    target_path = stem_to_path[imp]
                    if target_path != mod.path:
                        # Avoid duplicate edges
                        edge_key = (mod.path, target_path)
                        if edge_key not in seen_edges:
                            arch.edges.append(ArchEdge(
                                source=mod.path,
                                target=target_path,
                            ))
                            seen_edges.add(edge_key)
                else:
                    external_deps.add(imp)

        arch.external_deps = sorted(external_deps)

        # 4. Group by layers
        for mod in arch.modules:
            arch.layers.setdefault(mod.layer, []).append(mod.path)

        # 5. Stats
        arch.stats = {
            "total_modules": len(arch.modules),
            "total_edges": len(arch.edges),
            "total_layers": len(arch.layers),
            "total_lines": sum(m.size_lines for m in arch.modules),
        }

        logger.info(
            f"Architecture scan: {arch.stats['total_modules']} modules, "
            f"{arch.stats['total_edges']} deps, "
            f"{arch.stats['total_lines']} lines"
        )
        return arch

    def _discover_files(self, max_files: int) -> list[Path]:
        """Find all source files in the project."""
        files: list[Path] = []

        for path in sorted(self.project_dir.rglob("*")):
            if len(files) >= max_files:
                break
            if not path.is_file():
                continue
            if path.suffix not in LANG_EXTENSIONS:
                continue

            # Skip excluded directories
            rel_parts = path.relative_to(self.project_dir).parts
            if any(p in SKIP_DIRS or p.startswith(".") for p in rel_parts[:-1]):
                continue

            files.append(path)

        return files


# ---------------------------------------------------------------------------
# Vault Integration
# ---------------------------------------------------------------------------

def scan_and_save(
    vault_path: Path,
    project: str,
    project_base_dirs: list[str],
) -> str:
    """Scan project, generate architecture map, save to vault.

    Returns the Markdown content of the architecture map.
    """
    # Find project directory
    project_dir = None
    for base in project_base_dirs:
        candidate = Path(base) / project
        if candidate.exists():
            project_dir = candidate
            break

    if not project_dir:
        # Fallback
        for base in [Path.home() / "Projects", Path.home() / "Developer"]:
            candidate = base / project
            if candidate.exists():
                project_dir = candidate
                break

    if not project_dir:
        return f"❌ Project directory not found: {project}"

    # Scan
    scanner = ProjectScanner(project_dir, project)
    arch = scanner.scan()

    if not arch.modules:
        return f"❌ No source files found in {project_dir}"

    # Generate markdown
    md_content = arch.to_markdown()

    # Save to vault
    vault_dir = vault_path / project
    vault_dir.mkdir(parents=True, exist_ok=True)
    map_path = vault_dir / "architecture-map.md"

    today = date.today().isoformat()
    full_content = (
        f"---\n"
        f"project: {project}\n"
        f"type: architecture\n"
        f"tags:\n"
        f'  - "auto-generated"\n'
        f'  - "architecture-map"\n'
        f"priority: high\n"
        f"created: {today}\n"
        f"updated: {today}\n"
        f"source: auto-architect\n"
        f"---\n\n"
        f"{md_content}\n"
    )

    map_path.write_text(full_content, encoding="utf-8")
    logger.info(f"Architecture map saved: {map_path.relative_to(vault_path)}")

    return md_content
