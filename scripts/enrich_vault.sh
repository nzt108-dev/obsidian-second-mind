#!/usr/bin/env bash
# Enrich vault PRD files with dashboard metadata
# Adds: status, stack, services, path, github, description

VAULT="/Users/nzt108/SecondMind"
PROJECTS_DIR="/Users/nzt108/Projects"

enrich_prd() {
  local project="$1"
  local status="$2"
  local stack="$3"       # comma-separated
  local services="$4"    # comma-separated
  local path="$5"
  local github="$6"
  local description="$7"
  local category="$8"

  local prd="$VAULT/$project/prd.md"
  if [ ! -f "$prd" ]; then
    echo "SKIP: $prd not found"
    return
  fi

  # Check if already enriched
  if grep -q "^status:" "$prd"; then
    echo "SKIP: $project already enriched"
    return
  fi

  # Build new frontmatter fields (insert before closing ---)
  local new_fields="status: $status
stack: [$stack]
services: [$services]
category: $category
description: \"$description\"
path: \"$path\"
github: \"$github\""

  # Insert before the closing --- (line 2 of ---)
  # Find line number of second ---
  local close_line=$(awk '/^---$/{n++; if(n==2) {print NR; exit}}' "$prd")
  
  if [ -z "$close_line" ]; then
    echo "ERROR: No closing --- in $prd"
    return
  fi

  # Insert new fields before closing ---
  sed -i '' "${close_line}i\\
${new_fields}
" "$prd"

  echo "OK: $project enriched"
}

# === ENRICH ALL PROJECTS ===

enrich_prd "brieftube" \
  "active" \
  "Flutter, Python, FastAPI" \
  "Supabase, Docker, VPS, OpenRouter" \
  "$PROJECTS_DIR/youtube-parser" \
  "nzt108-dev/channel-watch" \
  "iOS приложение для YouTube AI-саммари, 7 форматов контента" \
  "mobile"

enrich_prd "faithly" \
  "active" \
  "Flutter, Dart" \
  "Firebase, Firestore, Cloud Storage, FCM" \
  "$PROJECTS_DIR/Faithly" \
  "nzt108-dev/faithly" \
  "Социальная сеть для христиан и церквей" \
  "mobile"

enrich_prd "botseller" \
  "active" \
  "Python, FastAPI, PostgreSQL, Celery" \
  "Docker, VPS, Telegram API, Redis" \
  "$PROJECTS_DIR/botseller_saas" \
  "nzt108-dev/botseller-saas" \
  "Multi-tenant SaaS для Telegram ботов-продажников" \
  "saas"

enrich_prd "nzt108-dev" \
  "active" \
  "Next.js 15, TypeScript, React" \
  "Vercel, Turso, GitHub" \
  "$PROJECTS_DIR/architect-portfolio" \
  "nzt108-dev/architect-portfolio" \
  "Портфолио-сайт разработчика" \
  "web"

enrich_prd "ai-content-fabric" \
  "active" \
  "Python, MoviePy, ElevenLabs" \
  "Docker, VPS, YouTube API, ElevenLabs" \
  "$PROJECTS_DIR/ai-content-fabric" \
  "nzt108-dev/ai-content-fabric" \
  "AI pipeline генерации видеоконтента" \
  "saas"

enrich_prd "social-leads-parser" \
  "paused" \
  "Python, FastAPI" \
  "Docker, VPS" \
  "$PROJECTS_DIR/social-leads-parser" \
  "nzt108-dev/social-leads-parser" \
  "Парсер лидов из социальных сетей" \
  "web"

enrich_prd "youtube-parser" \
  "active" \
  "Flutter, Python, FastAPI" \
  "Supabase, Docker, VPS, YouTube API" \
  "$PROJECTS_DIR/youtube-parser" \
  "nzt108-dev/channel-watch" \
  "Channel Watch бэкенд — парсинг YouTube каналов" \
  "web"

enrich_prd "zillow-parser" \
  "paused" \
  "Python, FastAPI" \
  "Docker, VPS, Zillow API" \
  "$PROJECTS_DIR/zillow-parser" \
  "nzt108-dev/zillow-parser" \
  "NorCal Deal Engine — парсер недвижимости" \
  "web"

enrich_prd "norcal-deals" \
  "paused" \
  "Flutter, Dart" \
  "Supabase" \
  "$PROJECTS_DIR/norcal_deals" \
  "nzt108-dev/norcal-deals" \
  "FlipRadar — мобильное приложение для поиска сделок с недвижимостью" \
  "mobile"

enrich_prd "dance-studio-website" \
  "done" \
  "HTML, CSS, JavaScript" \
  "GitHub Pages" \
  "$PROJECTS_DIR/dance-studio-website" \
  "nzt108-dev/dance-studio-website" \
  "Статический сайт для студии танцев" \
  "web"

enrich_prd "content-fabric-saas" \
  "idea" \
  "Flutter, Supabase" \
  "Supabase, Vercel" \
  "$PROJECTS_DIR/content-fabric-saas" \
  "nzt108-dev/content-fabric-saas" \
  "SaaS для генерации контента (Flutter + Supabase)" \
  "saas"

enrich_prd "astro-psiholog" \
  "paused" \
  "Flutter, Dart" \
  "Firebase" \
  "$PROJECTS_DIR/Astro-psiholog" \
  "nzt108-dev/astro-psiholog" \
  "AI-приложение для астрологии и психологии" \
  "mobile"

enrich_prd "my-remote-office" \
  "paused" \
  "Python" \
  "Telegram API" \
  "$PROJECTS_DIR/my-remote-office" \
  "nzt108-dev/my-remote-office" \
  "Telegram бот для управления задачами" \
  "telegram"

enrich_prd "zillow-landing" \
  "done" \
  "Next.js, TypeScript" \
  "Vercel" \
  "$PROJECTS_DIR/zillow-landing" \
  "nzt108-dev/zillow-landing" \
  "Лендинг для NorCal Deals" \
  "web"

enrich_prd "sendler-bot" \
  "idea" \
  "Python" \
  "Telegram API" \
  "$PROJECTS_DIR/sendler_bot" \
  "nzt108-dev/sendler-bot" \
  "Codex Swarm multi-agent Telegram рассыльщик" \
  "telegram"

enrich_prd "yt-saas-frontend" \
  "paused" \
  "Next.js, TypeScript, React" \
  "Vercel" \
  "$PROJECTS_DIR/yt-saas-frontend" \
  "nzt108-dev/yt-saas-frontend" \
  "Админ-панель для YouTube SaaS" \
  "web"

enrich_prd "architect-portfolio" \
  "active" \
  "Next.js 15, TypeScript, React" \
  "Vercel, Turso, GitHub" \
  "$PROJECTS_DIR/architect-portfolio" \
  "nzt108-dev/architect-portfolio" \
  "Портфолио (тот же что nzt108-dev)" \
  "web"

echo ""
echo "=== Enrichment complete ==="
