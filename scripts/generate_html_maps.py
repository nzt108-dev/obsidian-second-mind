#!/usr/bin/env python3
"""Generate DATA FLOW diagrams (state-machine style) for ALL projects.

Analyzes each project to find:
- API routes / endpoints
- Database models / operations
- External services (Telegram, OpenAI, Stripe, etc.)
- Entry points (pages, CLI, bots)

Then generates Mermaid flowcharts showing how data moves through the system.
"""
import re
import json
import sys
from pathlib import Path
from datetime import date
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from obsidian_bridge.architect import ProjectScanner

PROJECTS_DIR = Path.home() / "Projects"


@dataclass
class ProjectAnalysis:
    name: str
    tech_stack: list[str] = field(default_factory=list)
    api_routes: list[dict] = field(default_factory=list)
    pages: list[str] = field(default_factory=list)
    db_models: list[str] = field(default_factory=list)
    db_type: str = ""
    external_services: list[dict] = field(default_factory=list)
    entry_points: list[dict] = field(default_factory=list)
    total_modules: int = 0
    total_lines: int = 0
    total_deps: int = 0


def analyze_project(project_dir: Path) -> ProjectAnalysis:
    """Deep-analyze a project to extract data flow information."""
    name = project_dir.name
    analysis = ProjectAnalysis(name=name)

    # Run architecture scan for basic stats
    scanner = ProjectScanner(project_dir, name)
    arch = scanner.scan()
    analysis.total_modules = len(arch.modules)
    analysis.total_lines = sum(m.size_lines for m in arch.modules)
    analysis.total_deps = len(arch.edges)

    # Detect tech stack
    _detect_stack(project_dir, analysis)

    # Detect API routes
    _detect_api_routes(project_dir, analysis)

    # Detect pages / entry points
    _detect_pages(project_dir, analysis)

    # Detect database
    _detect_database(project_dir, analysis)

    # Detect external services
    _detect_external_services(project_dir, analysis)

    return analysis


def _detect_stack(project_dir: Path, a: ProjectAnalysis):
    """Detect tech stack from config files."""
    checks = [
        ("pubspec.yaml", "Flutter / Dart"),
        ("package.json", None),  # handled separately
        ("pyproject.toml", "Python"),
        ("requirements.txt", "Python"),
        ("Cargo.toml", "Rust"),
        ("go.mod", "Go"),
    ]
    for fname, tech in checks:
        f = project_dir / fname
        if f.exists():
            if tech:
                a.tech_stack.append(tech)
            elif fname == "package.json":
                try:
                    pkg = json.loads(f.read_text())
                    deps = {
                        **pkg.get("dependencies", {}),
                        **pkg.get("devDependencies", {}),
                    }
                    if "next" in deps:
                        a.tech_stack.append("Next.js")
                    elif "react" in deps:
                        a.tech_stack.append("React")
                    elif "vue" in deps:
                        a.tech_stack.append("Vue")
                    elif "express" in deps:
                        a.tech_stack.append("Express")

                    if "typescript" in deps:
                        a.tech_stack.append("TypeScript")
                    else:
                        a.tech_stack.append("JavaScript")

                    if "prisma" in deps or "@prisma/client" in deps:
                        a.tech_stack.append("Prisma")
                    if "tailwindcss" in deps:
                        a.tech_stack.append("TailwindCSS")
                except Exception:
                    a.tech_stack.append("Node.js")

    if (project_dir / "Dockerfile").exists():
        a.tech_stack.append("Docker")


def _detect_api_routes(project_dir: Path, a: ProjectAnalysis):
    """Find API routes / endpoints."""
    # Next.js API routes
    api_dir = project_dir / "app" / "api"
    if api_dir.exists():
        for route_file in api_dir.rglob("route.ts"):
            rel = str(route_file.relative_to(project_dir / "app"))
            endpoint = "/" + rel.replace("/route.ts", "").replace("[", ":").replace("]", "")
            methods = _extract_http_methods(route_file)
            a.api_routes.append({"path": endpoint, "methods": methods})
        for route_file in api_dir.rglob("route.js"):
            rel = str(route_file.relative_to(project_dir / "app"))
            endpoint = "/" + rel.replace("/route.js", "").replace("[", ":").replace("]", "")
            methods = _extract_http_methods(route_file)
            a.api_routes.append({"path": endpoint, "methods": methods})

    # Flask / FastAPI
    for py_file in project_dir.rglob("*.py"):
        if "node_modules" in str(py_file) or ".venv" in str(py_file):
            continue
        try:
            content = py_file.read_text(errors="ignore")
        except Exception:
            continue
        # Flask routes
        for m in re.finditer(
            r'@\w+\.(route|get|post|put|delete)\(["\']([^"\']+)', content
        ):
            a.api_routes.append(
                {"path": m.group(2), "methods": [m.group(1).upper()]}
            )
        # FastAPI routes
        for m in re.finditer(
            r'@\w+\.(get|post|put|delete)\(["\']([^"\']+)', content
        ):
            a.api_routes.append(
                {"path": m.group(2), "methods": [m.group(1).upper()]}
            )

    # Dart / Flutter won't have traditional API routes, skip


def _extract_http_methods(route_file: Path) -> list[str]:
    """Extract HTTP methods from a Next.js route file."""
    methods = []
    try:
        content = route_file.read_text(errors="ignore")
    except Exception:
        return ["GET"]
    for method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
        if f"export async function {method}" in content or \
           f"export function {method}" in content:
            methods.append(method)
    return methods or ["GET"]


def _detect_pages(project_dir: Path, a: ProjectAnalysis):
    """Find UI pages / entry points."""
    # Next.js pages
    app_dir = project_dir / "app"
    if app_dir.exists():
        for page_file in app_dir.rglob("page.tsx"):
            rel = str(page_file.relative_to(app_dir))
            path = "/" + rel.replace("/page.tsx", "").replace("[", ":").replace("]", "")
            if path == "/":
                path = "/"
            if "/api/" not in path:
                a.pages.append(path)
        for page_file in app_dir.rglob("page.jsx"):
            rel = str(page_file.relative_to(app_dir))
            path = "/" + rel.replace("/page.jsx", "").replace("[", ":").replace("]", "")
            if "/api/" not in path:
                a.pages.append(path)

    # Flask / Python templates
    templates = project_dir / "templates"
    if templates.exists():
        for tmpl in templates.rglob("*.html"):
            name = tmpl.stem
            a.pages.append(f"/{name}")

    # Flutter screens
    screens_dir = project_dir / "lib" / "screens"
    if not screens_dir.exists():
        screens_dir = project_dir / "lib" / "pages"
    if not screens_dir.exists():
        screens_dir = project_dir / "lib" / "views"
    if screens_dir.exists():
        for screen in screens_dir.rglob("*.dart"):
            name = screen.stem.replace("_screen", "").replace("_page", "")
            a.pages.append(name)

    # Bot entry points
    for py_file in [project_dir / "bot.py", project_dir / "main.py"]:
        if py_file.exists():
            a.entry_points.append(
                {"type": "bot", "file": py_file.name}
            )


def _detect_database(project_dir: Path, a: ProjectAnalysis):
    """Detect database type and models."""
    # Prisma
    schema = project_dir / "prisma" / "schema.prisma"
    if schema.exists():
        a.db_type = "Prisma + "
        try:
            content = schema.read_text()
            # Detect provider
            prov = re.search(r'provider\s*=\s*"(\w+)"', content)
            if prov:
                providers = {
                    "sqlite": "SQLite",
                    "postgresql": "PostgreSQL",
                    "mysql": "MySQL",
                    "libsql": "Turso (LibSQL)",
                }
                a.db_type += providers.get(prov.group(1), prov.group(1))
            for m in re.finditer(r"^model\s+(\w+)", content, re.MULTILINE):
                a.db_models.append(m.group(1))
        except Exception:
            pass
        return

    # SQLAlchemy / Django
    for py_file in project_dir.rglob("models.py"):
        if "node_modules" in str(py_file) or ".venv" in str(py_file):
            continue
        a.db_type = "SQLAlchemy"
        try:
            content = py_file.read_text(errors="ignore")
            for m in re.finditer(
                r"class\s+(\w+)\(.*(?:Base|Model|db\.Model)", content
            ):
                a.db_models.append(m.group(1))
        except Exception:
            pass

    # Raw SQLite
    for f in project_dir.rglob("*.db"):
        if "node_modules" not in str(f):
            a.db_type = "SQLite"
            break
    for py_file in project_dir.rglob("*.py"):
        if "node_modules" in str(py_file) or ".venv" in str(py_file):
            continue
        try:
            if "sqlite3" in py_file.read_text(errors="ignore")[:500]:
                a.db_type = a.db_type or "SQLite"
                break
        except Exception:
            pass


def _detect_external_services(project_dir: Path, a: ProjectAnalysis):
    """Detect external service integrations by grepping source files."""
    patterns = {
        "Telegram Bot": [r"telegram", r"sendMessage", r"TELEGRAM_BOT_TOKEN"],
        "OpenAI": [r"openai", r"chat\.completions", r"OPENAI_API_KEY"],
        "Stripe": [r"stripe", r"STRIPE_SECRET"],
        "Twilio": [r"twilio"],
        "SendGrid": [r"sendgrid", r"SENDGRID_API_KEY"],
        "Firebase": [r"firebase", r"firestore"],
        "Supabase": [r"supabase", r"SUPABASE_URL"],
        "Redis": [r"redis", r"REDIS_URL"],
        "S3 / AWS": [r"aws-sdk", r"boto3", r"S3_BUCKET"],
        "Google Maps": [r"maps\.googleapis", r"GOOGLE_MAPS"],
        "RSS Parser": [r"rss-parser", r"feedparser"],
        "Vercel": [r"vercel"],
        "Notion API": [r"notion\.com/v1", r"NOTION_API_KEY"],
    }

    all_source = ""
    exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".dart"}
    count = 0
    for src_file in project_dir.rglob("*"):
        if count > 200:
            break
        if src_file.suffix not in exts:
            continue
        if any(skip in str(src_file) for skip in [
            "node_modules", ".venv", ".next", "build", ".dart_tool"
        ]):
            continue
        try:
            all_source += src_file.read_text(errors="ignore")[:2000]
            count += 1
        except Exception:
            pass

    for service, regexes in patterns.items():
        for pattern in regexes:
            if re.search(pattern, all_source, re.IGNORECASE):
                a.external_services.append({"name": service})
                break


# ═══════════════════════════════════════════════════
# HTML GENERATION
# ═══════════════════════════════════════════════════

def generate_html(a: ProjectAnalysis) -> str:
    """Build full HTML with Mermaid data flow diagrams."""
    today = date.today().isoformat()

    # ── Build Mermaid: Main State Machine ──
    main_diagram = _build_main_flow(a)

    # ── Build Mermaid: API Routes flow ──
    api_diagram = _build_api_flow(a)

    # ── Build Mermaid: Database schema ──
    db_diagram = _build_db_diagram(a)

    # ── Summary table ──
    summary_table = _build_summary_table(a)

    # ── Services cards ──
    services_html = _build_services_cards(a)

    # ── Pages list ──
    pages_html = ""
    for p in sorted(set(a.pages))[:20]:
        pages_html += f'<div class="page-chip">{p}</div>\n'

    stack_html = " • ".join(a.tech_stack) if a.tech_stack else "Unknown"

    return f'''<!DOCTYPE html>
<html lang="ru"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🔄 {a.name} — Data Flow Map</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0e17;color:#c9d1d9;font-family:'Inter',sans-serif;line-height:1.7}}

.header{{background:linear-gradient(135deg,#0d1117,#161b22);border-bottom:1px solid rgba(88,166,255,.15);padding:32px 24px;text-align:center}}
.header h1{{font-size:28px;font-weight:800;background:linear-gradient(135deg,#58a6ff,#a371f7);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px}}
.header .sub{{color:#8b949e;font-size:13px}}
.header .stack{{margin-top:8px;color:#a371f7;font-size:12px;font-weight:500}}
.stats{{display:flex;justify-content:center;gap:12px;margin-top:16px;flex-wrap:wrap}}
.stat{{background:rgba(88,166,255,.06);border:1px solid rgba(88,166,255,.15);padding:6px 16px;border-radius:8px;font-size:12px;color:#8b949e}}
.stat strong{{color:#58a6ff;font-size:16px;font-weight:700;margin-right:3px}}

.container{{max-width:1000px;margin:0 auto;padding:32px 20px}}

.section{{margin-bottom:48px}}
.section-head{{display:flex;align-items:center;gap:12px;margin-bottom:16px}}
.section-icon{{width:40px;height:40px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0}}
.section-head h2{{font-size:18px;font-weight:700;color:#e6edf3}}

.diagram-card{{background:rgba(22,27,34,.5);border:1px solid #30363d;border-radius:14px;padding:24px;margin-bottom:16px;overflow-x:auto}}

.callout{{border-radius:8px;padding:12px 16px;margin:12px 0;font-size:12px;line-height:1.6;border-left:3px solid}}
.callout-info{{background:rgba(88,166,255,.05);border-color:#58a6ff}}
.callout-warn{{background:rgba(210,153,34,.05);border-color:#d29922}}
.callout b{{color:#e6edf3}}

table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:rgba(88,166,255,.06);padding:8px 12px;text-align:left;color:#58a6ff;font-weight:600;border-bottom:2px solid #30363d;font-size:11px;text-transform:uppercase;letter-spacing:.5px}}
td{{padding:8px 12px;border-bottom:1px solid #21262d}}
tr:hover td{{background:rgba(88,166,255,.03)}}
code{{background:rgba(88,166,255,.1);padding:1px 5px;border-radius:3px;font-size:11px;color:#79c0ff;font-family:'SF Mono',monospace}}

.services-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}}
.svc-card{{background:rgba(22,27,34,.6);border:1px solid #30363d;border-radius:10px;padding:14px 16px}}
.svc-card .svc-name{{font-weight:600;font-size:13px;color:#e6edf3}}
.svc-card .svc-type{{font-size:11px;color:#8b949e;margin-top:2px}}

.pages-grid{{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}}
.page-chip{{background:rgba(88,166,255,.06);border:1px solid #30363d;padding:4px 12px;border-radius:6px;font-size:11px;color:#79c0ff}}

hr{{border:none;height:1px;background:linear-gradient(90deg,transparent,#30363d 20%,#30363d 80%,transparent);margin:40px 0}}
.footer{{text-align:center;padding:24px;color:#484f58;font-size:11px;border-top:1px solid #21262d}}
</style>
</head><body>

<div class="header">
    <h1>🔄 {a.name}</h1>
    <div class="sub">Data Flow Map • {today}</div>
    <div class="stack">{stack_html}</div>
    <div class="stats">
        <div class="stat"><strong>{a.total_modules}</strong>модулей</div>
        <div class="stat"><strong>{len(a.api_routes)}</strong>API routes</div>
        <div class="stat"><strong>{len(a.db_models)}</strong>таблиц</div>
        <div class="stat"><strong>{len(a.external_services)}</strong>сервисов</div>
        <div class="stat"><strong>{a.total_lines:,}</strong>строк</div>
    </div>
</div>

<div class="container">

<!-- ═══ MAIN FLOW ═══ -->
<div class="section">
    <div class="section-head">
        <div class="section-icon" style="background:rgba(88,166,255,.1)">🔄</div>
        <h2>Общий поток данных</h2>
    </div>
    <div class="callout callout-info">
        <b>Как читать:</b> Стрелки показывают направление движения данных. Каждый блок — это компонент системы. Цвета: 🔵 пользователь, 🟢 API, 🟣 база данных, 🟠 внешний сервис.
    </div>
    <div class="diagram-card">
        <div class="mermaid">{main_diagram}</div>
    </div>
</div>

<hr>

<!-- ═══ API ROUTES ═══ -->
{"" if not a.api_routes else f"""
<div class="section">
    <div class="section-head">
        <div class="section-icon" style="background:rgba(46,160,67,.1)">🔌</div>
        <h2>API Endpoints ({len(a.api_routes)} routes)</h2>
    </div>
    <div class="diagram-card">
        <div class="mermaid">{api_diagram}</div>
    </div>
    {summary_table}
</div>
<hr>
"""}

<!-- ═══ DATABASE ═══ -->
{"" if not a.db_models else f"""
<div class="section">
    <div class="section-head">
        <div class="section-icon" style="background:rgba(156,39,176,.1)">🗄️</div>
        <h2>База данных ({a.db_type})</h2>
    </div>
    <div class="callout callout-info">
        <b>{a.db_type}</b> — {len(a.db_models)} таблиц/моделей: {", ".join(a.db_models[:10])}
    </div>
    <div class="diagram-card">
        <div class="mermaid">{db_diagram}</div>
    </div>
</div>
<hr>
"""}

<!-- ═══ EXTERNAL SERVICES ═══ -->
{"" if not a.external_services else f"""
<div class="section">
    <div class="section-head">
        <div class="section-icon" style="background:rgba(255,152,0,.1)">🌍</div>
        <h2>Внешние сервисы</h2>
    </div>
    {services_html}
</div>
<hr>
"""}

<!-- ═══ PAGES ═══ -->
{"" if not a.pages else f"""
<div class="section">
    <div class="section-head">
        <div class="section-icon" style="background:rgba(233,30,99,.1)">📄</div>
        <h2>Страницы / Экраны ({len(set(a.pages))})</h2>
    </div>
    <div class="pages-grid">{pages_html}</div>
</div>
"""}

</div>
<div class="footer">Auto-generated by Obsidian Second Mind v1.1 • scan_architecture</div>

<script>
mermaid.initialize({{
    theme:'dark', securityLevel:'loose',
    flowchart:{{htmlLabels:true,curve:'basis'}},
    themeVariables:{{
        primaryColor:'#1f2937',primaryTextColor:'#c9d1d9',
        primaryBorderColor:'#30363d',lineColor:'#58a6ff',
        fontFamily:'Inter, sans-serif'
    }}
}});
</script>
</body></html>'''


def _build_main_flow(a: ProjectAnalysis) -> str:
    """Build the main state-machine flowchart."""
    lines = ["flowchart TB"]

    # Entry points
    has_pages = bool(a.pages)
    has_api = bool(a.api_routes)
    has_bot = any(e["type"] == "bot" for e in a.entry_points)
    has_db = bool(a.db_models)
    has_ext = bool(a.external_services)

    # Users / Sources
    lines.append('    User["👤 Пользователь"]')
    if has_bot:
        lines.append('    Bot["🤖 Telegram Bot"]')

    # Pages layer
    if has_pages:
        page_list = sorted(set(a.pages))[:6]
        page_labels = "\\n".join(page_list[:4])
        if len(page_list) > 4:
            page_labels += f"\\n... +{len(set(a.pages)) - 4}"
        lines.append(f'    Pages["📄 Страницы\\n{page_labels}"]')
        lines.append('    User -->|"открывает"| Pages')

    # API layer
    if has_api:
        # Group routes
        groups = {}
        for r in a.api_routes:
            parts = r["path"].strip("/").split("/")
            group = parts[1] if len(parts) > 1 else parts[0]
            group = group.replace(":", "")
            if group not in groups:
                groups[group] = []
            groups[group].append(r)

        route_labels = []
        for g, routes in sorted(groups.items())[:6]:
            methods = set()
            for r in routes:
                methods.update(r["methods"])
            route_labels.append(f"{','.join(methods)} /{g}")
        api_label = "\\n".join(route_labels[:5])
        if len(groups) > 5:
            api_label += f"\\n... +{len(groups) - 5}"

        lines.append(f'    API["⚡ API Layer\\n{api_label}"]')
        if has_pages:
            lines.append('    Pages -->|"fetch / POST"| API')
        else:
            lines.append('    User -->|"запрос"| API')
        if has_bot:
            lines.append('    Bot -->|"webhook"| API')

    # Database
    if has_db:
        model_labels = "\\n".join(a.db_models[:5])
        if len(a.db_models) > 5:
            model_labels += f"\\n... +{len(a.db_models) - 5}"
        db_label = a.db_type.split("+")[0].strip() if a.db_type else "DB"
        lines.append(f'    DB[("💾 {db_label}\\n{model_labels}")]')
        if has_api:
            lines.append('    API -->|"query / save"| DB')
        elif has_pages:
            lines.append('    Pages -->|"query"| DB')

    # External services
    for i, svc in enumerate(a.external_services[:4]):
        sid = f"Ext{i}"
        lines.append(f'    {sid}["🌐 {svc["name"]}"]')
        if has_api:
            lines.append(f'    API -->|"call"| {sid}')

    # Response back
    if has_api and has_pages:
        lines.append('    API -->|"JSON response"| Pages')
        lines.append('    Pages -->|"renders"| User')
    elif has_api:
        lines.append('    API -->|"response"| User')

    # Styling
    lines.append('    style User fill:#58a6ff,color:#fff')
    if has_pages:
        lines.append('    style Pages fill:#E91E63,color:#fff')
    if has_api:
        lines.append('    style API fill:#2ea043,color:#fff')
    if has_db:
        lines.append('    style DB fill:#9C27B0,color:#fff')
    if has_bot:
        lines.append('    style Bot fill:#0088cc,color:#fff')
    for i in range(min(4, len(a.external_services))):
        lines.append(f'    style Ext{i} fill:#FF9800,color:#fff')

    return "\n".join(lines)


def _build_api_flow(a: ProjectAnalysis) -> str:
    """Build API routes detail flowchart."""
    if not a.api_routes:
        return "flowchart LR\n    None['No API routes detected']"

    lines = ["flowchart LR"]
    lines.append('    Client["👤 Client"]')

    for i, route in enumerate(a.api_routes[:12]):
        rid = f"R{i}"
        methods = ",".join(route["methods"])
        path_short = route["path"]
        if len(path_short) > 30:
            path_short = "..." + path_short[-27:]
        lines.append(f'    {rid}["{methods}\\n{path_short}"]')
        lines.append(f'    Client --> {rid}')
        lines.append(f'    style {rid} fill:#2ea043,color:#fff')

    if len(a.api_routes) > 12:
        lines.append(
            f'    More["... +{len(a.api_routes) - 12} routes"]'
        )
        lines.append(f'    style More fill:#30363d,color:#8b949e')

    if a.db_models:
        lines.append(f'    DB[("💾 Database")]')
        for i in range(min(12, len(a.api_routes))):
            lines.append(f'    R{i} --> DB')
        lines.append(f'    style DB fill:#9C27B0,color:#fff')

    lines.append('    style Client fill:#58a6ff,color:#fff')
    return "\n".join(lines)


def _build_db_diagram(a: ProjectAnalysis) -> str:
    """Build ER-like diagram for database models."""
    if not a.db_models:
        return "flowchart LR\n    None['No database detected']"

    lines = ["flowchart LR"]
    for i, model in enumerate(a.db_models[:12]):
        mid = f"M{i}"
        lines.append(f'    {mid}["{model}"]')
        lines.append(f'    style {mid} fill:#9C27B0,color:#fff')

    # Try to link related models
    for i, m1 in enumerate(a.db_models[:12]):
        for j, m2 in enumerate(a.db_models[:12]):
            if i >= j:
                continue
            # Simple heuristic: if one name contains the other
            if m1.lower() in m2.lower() or m2.lower() in m1.lower():
                lines.append(f'    M{i} --- M{j}')

    return "\n".join(lines)


def _build_summary_table(a: ProjectAnalysis) -> str:
    """Build HTML summary table for routes."""
    if not a.api_routes:
        return ""
    rows = ""
    for r in a.api_routes[:20]:
        methods = ", ".join(r["methods"])
        rows += f"<tr><td>{methods}</td><td><code>{r['path']}</code></td></tr>\n"
    return f"""<table>
        <thead><tr><th>Methods</th><th>Endpoint</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>"""


def _build_services_cards(a: ProjectAnalysis) -> str:
    """Build services grid HTML."""
    if not a.external_services:
        return ""
    cards = ""
    icons = {
        "Telegram Bot": "📱", "OpenAI": "🧠", "Stripe": "💳",
        "Firebase": "🔥", "Redis": "⚡", "S3 / AWS": "☁️",
        "Vercel": "▲", "RSS Parser": "📡", "Notion API": "📝",
        "Google Maps": "🗺️", "Supabase": "💚",
    }
    for svc in a.external_services:
        icon = icons.get(svc["name"], "🔌")
        cards += f"""<div class="svc-card">
            <div class="svc-name">{icon} {svc["name"]}</div>
        </div>\n"""
    return f'<div class="services-grid">{cards}</div>'


def main():
    generated = 0
    for project_dir in sorted(PROJECTS_DIR.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith("."):
            continue

        a = analyze_project(project_dir)

        if a.total_modules < 2:
            print(f"⏭️  {a.name}: too small, skipping")
            continue

        html = generate_html(a)
        out = project_dir / "data-flow-map.html"
        out.write_text(html, encoding="utf-8")
        generated += 1
        print(
            f"✅ {a.name}: "
            f"{a.total_modules} modules, "
            f"{len(a.api_routes)} routes, "
            f"{len(a.db_models)} tables, "
            f"{len(a.external_services)} services"
        )

    print(f"\n🎉 Generated {generated} Data Flow Maps!")


if __name__ == "__main__":
    main()
