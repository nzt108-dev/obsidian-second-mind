#!/usr/bin/env python3
"""Enrich vault PRD files with dashboard metadata."""
import yaml
from pathlib import Path

VAULT = Path.home() / "SecondMind"
PROJECTS_DIR = Path.home() / "Projects"

PROJECTS = [
    {
        "project": "brieftube",
        "status": "active",
        "stack": ["Flutter", "Python", "FastAPI"],
        "services": ["Supabase", "Docker", "VPS", "OpenRouter"],
        "path": str(PROJECTS_DIR / "youtube-parser"),
        "github": "nzt108-dev/channel-watch",
        "description": "iOS приложение для YouTube AI-саммари, 7 форматов контента",
        "category": "mobile",
    },
    {
        "project": "faithly",
        "status": "active",
        "stack": ["Flutter", "Dart"],
        "services": ["Firebase", "Firestore", "Cloud Storage", "FCM"],
        "path": str(PROJECTS_DIR / "Faithly"),
        "github": "nzt108-dev/faithly",
        "description": "Социальная сеть для христиан и церквей",
        "category": "mobile",
    },
    {
        "project": "botseller",
        "status": "active",
        "stack": ["Python", "FastAPI", "PostgreSQL", "Celery"],
        "services": ["Docker", "VPS", "Telegram API", "Redis"],
        "path": str(PROJECTS_DIR / "botseller_saas"),
        "github": "nzt108-dev/botseller-saas",
        "description": "Multi-tenant SaaS для Telegram ботов-продажников",
        "category": "saas",
    },
    {
        "project": "nzt108-dev",
        "status": "active",
        "stack": ["Next.js 15", "TypeScript", "React"],
        "services": ["Vercel", "Turso", "GitHub"],
        "path": str(PROJECTS_DIR / "architect-portfolio"),
        "github": "nzt108-dev/architect-portfolio",
        "description": "Портфолио-сайт разработчика",
        "category": "web",
    },
    {
        "project": "ai-content-fabric",
        "status": "active",
        "stack": ["Python", "MoviePy", "ElevenLabs"],
        "services": ["Docker", "VPS", "YouTube API", "ElevenLabs"],
        "path": str(PROJECTS_DIR / "ai-content-fabric"),
        "github": "nzt108-dev/ai-content-fabric",
        "description": "AI pipeline генерации видеоконтента",
        "category": "saas",
    },
    {
        "project": "social-leads-parser",
        "status": "paused",
        "stack": ["Python", "FastAPI"],
        "services": ["Docker", "VPS"],
        "path": str(PROJECTS_DIR / "social-leads-parser"),
        "github": "nzt108-dev/social-leads-parser",
        "description": "Парсер лидов из социальных сетей",
        "category": "web",
    },
    {
        "project": "youtube-parser",
        "status": "active",
        "stack": ["Flutter", "Python", "FastAPI"],
        "services": ["Supabase", "Docker", "VPS", "YouTube API"],
        "path": str(PROJECTS_DIR / "youtube-parser"),
        "github": "nzt108-dev/channel-watch",
        "description": "Channel Watch бэкенд — парсинг YouTube каналов",
        "category": "web",
    },
    {
        "project": "zillow-parser",
        "status": "paused",
        "stack": ["Python", "FastAPI"],
        "services": ["Docker", "VPS", "Zillow API"],
        "path": str(PROJECTS_DIR / "zillow-parser"),
        "github": "nzt108-dev/zillow-parser",
        "description": "NorCal Deal Engine — парсер недвижимости",
        "category": "web",
    },
    {
        "project": "norcal-deals",
        "status": "paused",
        "stack": ["Flutter", "Dart"],
        "services": ["Supabase"],
        "path": str(PROJECTS_DIR / "norcal_deals"),
        "github": "nzt108-dev/norcal-deals",
        "description": "FlipRadar — приложение для поиска сделок с недвижимостью",
        "category": "mobile",
    },
    {
        "project": "dance-studio-website",
        "status": "done",
        "stack": ["HTML", "CSS", "JavaScript"],
        "services": ["GitHub Pages"],
        "path": str(PROJECTS_DIR / "dance-studio-website"),
        "github": "nzt108-dev/dance-studio-website",
        "description": "Статический сайт для студии танцев",
        "category": "web",
    },
    {
        "project": "content-fabric-saas",
        "status": "idea",
        "stack": ["Flutter", "Supabase"],
        "services": ["Supabase", "Vercel"],
        "path": str(PROJECTS_DIR / "content-fabric-saas"),
        "github": "nzt108-dev/content-fabric-saas",
        "description": "SaaS для генерации контента",
        "category": "saas",
    },
    {
        "project": "astro-psiholog",
        "status": "paused",
        "stack": ["Flutter", "Dart"],
        "services": ["Firebase"],
        "path": str(PROJECTS_DIR / "Astro-psiholog"),
        "github": "nzt108-dev/astro-psiholog",
        "description": "AI-приложение для астро-психологии",
        "category": "mobile",
    },
    {
        "project": "my-remote-office",
        "status": "paused",
        "stack": ["Python"],
        "services": ["Telegram API"],
        "path": str(PROJECTS_DIR / "my-remote-office"),
        "github": "nzt108-dev/my-remote-office",
        "description": "Telegram бот для управления задачами",
        "category": "telegram",
    },
    {
        "project": "zillow-landing",
        "status": "done",
        "stack": ["Next.js", "TypeScript"],
        "services": ["Vercel"],
        "path": str(PROJECTS_DIR / "zillow-landing"),
        "github": "nzt108-dev/zillow-landing",
        "description": "Лендинг для NorCal Deals",
        "category": "web",
    },
    {
        "project": "sendler-bot",
        "status": "idea",
        "stack": ["Python"],
        "services": ["Telegram API"],
        "path": str(PROJECTS_DIR / "sendler_bot"),
        "github": "nzt108-dev/sendler-bot",
        "description": "Codex Swarm multi-agent рассыльщик",
        "category": "telegram",
    },
    {
        "project": "yt-saas-frontend",
        "status": "paused",
        "stack": ["Next.js", "TypeScript", "React"],
        "services": ["Vercel"],
        "path": str(PROJECTS_DIR / "yt-saas-frontend"),
        "github": "nzt108-dev/yt-saas-frontend",
        "description": "Админ-панель для YouTube SaaS",
        "category": "web",
    },
    {
        "project": "architect-portfolio",
        "status": "active",
        "stack": ["Next.js 15", "TypeScript", "React"],
        "services": ["Vercel", "Turso", "GitHub"],
        "path": str(PROJECTS_DIR / "architect-portfolio"),
        "github": "nzt108-dev/architect-portfolio",
        "description": "Портфолио (тот же что nzt108-dev)",
        "category": "web",
    },
]


def enrich_prd(info: dict) -> None:
    project = info["project"]
    prd_path = VAULT / project / "prd.md"

    if not prd_path.exists():
        print(f"SKIP: {prd_path} not found")
        return

    content = prd_path.read_text(encoding="utf-8")

    # Parse existing frontmatter
    if not content.startswith("---"):
        print(f"SKIP: {project} — no frontmatter")
        return

    parts = content.split("---", 2)
    if len(parts) < 3:
        print(f"SKIP: {project} — malformed frontmatter")
        return

    fm = yaml.safe_load(parts[1]) or {}

    # Already enriched?
    if "status" in fm and "stack" in fm:
        print(f"SKIP: {project} already enriched")
        return

    # Add new fields
    fm["status"] = info["status"]
    fm["stack"] = info["stack"]
    fm["services"] = info["services"]
    fm["category"] = info["category"]
    fm["description"] = info["description"]
    fm["path"] = info["path"]
    fm["github"] = info["github"]

    # Rebuild file
    new_fm = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
    new_content = f"---\n{new_fm}---\n{parts[2]}"
    prd_path.write_text(new_content, encoding="utf-8")
    print(f"OK: {project} enriched")


if __name__ == "__main__":
    for p in PROJECTS:
        enrich_prd(p)
    print(f"\n=== Enrichment complete ({len(PROJECTS)} projects) ===")
