#!/bin/bash
# Populate Obsidian vault with project notes
VAULT=~/SecondMind

# ============================================================
# 1. FAITHLY — Christian Social Network
# ============================================================
mkdir -p "$VAULT/faithly"

cat > "$VAULT/faithly/prd.md" << 'EOF'
---
title: "Faithly — PRD"
type: prd
project: faithly
tags: [mobile, social-network, christian, flutter, firebase]
created: 2026-04-05
---

# Faithly — Product Requirements

## Обзор
Мобильная социальная сеть для христиан и церквей. iOS и Android приложение.

## Целевая аудитория
- Верующие христиане
- Церкви и служители
- Пасторы и лидеры общин

## Ключевые фичи
1. **Поиск церквей** — Находить церкви и служителей рядом
2. **Подписки** — Подписываться на людей и церкви
3. **Контент** — Публикации и молитвенные нужды
4. **Сообщество** — Участие в жизни общины
5. **События** — Церковные мероприятия, расписание служений
6. **Комментарии** — Обсуждения под постами
7. **Профили** — Персональные страницы и страницы церквей

## Метрики успеха
- DAU / MAU > 30%
- Средняя сессия > 5 мин
- Retention D7 > 40%
EOF

cat > "$VAULT/faithly/architecture.md" << 'EOF'
---
title: "Faithly — Architecture"
type: architecture
project: faithly
tags: [flutter, firebase, flutterflow, firestore]
created: 2026-04-05
---

# Faithly — Architecture

## Tech Stack

| Компонент | Технология |
|-----------|------------|
| Frontend | FlutterFlow (→ Flutter) |
| Auth | Firebase Authentication |
| Database | Firebase Firestore (real-time streams) |
| Storage | Firebase Cloud Storage |
| Notifications | Firebase Cloud Messaging |

## Ключевые модули
- **Auth Flow** — Email/Password, Google Sign-In
- **Feed** — Лента постов с real-time updates
- **Church Directory** — Каталог церквей с геолокацией
- **Events** — CRUD для событий, привязка к церкви
- **Comments** — Threaded comments на постах
- **Followers** — Follow/Unfollow система
- **Profile Posts** — Публикации на личной странице

## Архитектурные решения
- FlutterFlow как визуальный конструктор, с кастомными виджетами
- Firestore streams для real-time обновлений (не mock data)
- Firebase Security Rules для авторизации
- Cloud Functions для server-side логики

## Статус
- MVP фаза — основные фичи на real-time Firestore
- Events, Comments, Profile Posts, Followers — переведены на живые данные
EOF

# ============================================================
# 2. ARCHITECT-PORTFOLIO (nzt108.dev)
# ============================================================
mkdir -p "$VAULT/nzt108-dev"

cat > "$VAULT/nzt108-dev/prd.md" << 'EOF'
---
title: "nzt108.dev — PRD"
type: prd
project: nzt108-dev
tags: [portfolio, nextjs, landing, lead-generation]
created: 2026-04-05
---

# nzt108.dev — Product Requirements

## Обзор
Портфолио-сайт и хаб для лид-генерации. Кинематографический, высокооптимизированный.

## Цели
1. Lead generation через платную рекламу (Meta Ads)
2. Демонстрация проектов и навыков
3. SEO-рост через контент
4. Автономный агентский API для обновления портфолио

## Ключевые фичи
- Hero section с immersive scroll
- Каталог проектов с автоматическим обновлением
- UTM-трекинг для рекламных кампаний
- Meta Pixel интеграция (PageView, Lead, Contact)
- Microsoft Clarity для heatmaps
- Admin panel с аналитикой
- WhatsApp/Telegram CTA для связи
- API для агентского обновления (`/api/agent/*`)

## Метрики
- CTR лендинга > 3%
- Conversion rate (Lead) > 5%
- Page Speed Score > 90
EOF

cat > "$VAULT/nzt108-dev/architecture.md" << 'EOF'
---
title: "nzt108.dev — Architecture"
type: architecture
project: nzt108-dev
tags: [nextjs, tailwind, turso, prisma, gsap, vercel]
created: 2026-04-05
---

# nzt108.dev — Architecture

## Tech Stack

| Компонент | Технология |
|-----------|------------|
| Framework | Next.js 15 (App Router, Turbopack) |
| Styling | Tailwind CSS v4, GSAP 3 (ScrollTrigger) |
| Database | Turso (LibSQL) + Prisma ORM |
| Hosting | Vercel (автодеплой с main) |
| Aesthetic | Dark Brutalist Signal |

## Ключевые модули
- **Hero** — 100dvh cinematic section с immersive scroll
- **Projects** — Каталог проектов из БД
- **Admin** — `/admin/*` — управление проектами, аналитика, UTM
- **Agent API** — `/api/agent/projects`, `/api/agent/activity`
- **Tracking** — Meta Pixel, Clarity, UTM engine

## Архитектурные решения
- SVG noise filter (`<feTurbulence>`) для текстуры
- GSAP-powered micro-interactions
- Mobile-first responsive design
- API ключ для агентского доступа (`PORTFOLIO_API_KEY`)
- Turso для edge-оптимизированной БД

## Деплоймент
- Vercel: автодеплой с GitHub main
- Domain: nzt108.dev
EOF

# ============================================================
# 3. AI-CONTENT-FABRIC
# ============================================================
mkdir -p "$VAULT/ai-content-fabric"

cat > "$VAULT/ai-content-fabric/prd.md" << 'EOF'
---
title: "AI Content Fabric — PRD"
type: prd
project: ai-content-fabric
tags: [ai, video, telegram-bot, python, content]
created: 2026-04-05
---

# AI Content Fabric — Product Requirements

## Обзор
Полуавтоматический AI-конвейер генерации Shorts/Reels с Telegram-ботом управления.

## Режимы
1. **SaaS-режим** — Новость + YouTube URL → AI-скрипт → видео с B-roll
2. **Влог-режим** — Своё видео + мысли → AI-скрипт → видео с субтитрами
3. **Cinema-режим** — Автоматическая генерация кинематографических видео

## Ключевые компоненты
- 🎙 **Озвучка**: ElevenLabs (multilingual v2)
- 📝 **Субтитры**: Динамические, по словам (Whisper + Pillow)
- 🎬 **Монтаж**: MoviePy — crop, transitions, overlays
- 🤖 **Сценарист**: OpenRouter (GPT-4o / Claude / DeepSeek)
- 🔍 **B-roll**: Vision-matching для подбора подходящих кадров

## Метрики
- Время генерации видео < 5 мин
- Качество озвучки — natural sounding
- Автоматический brightness filter для B-roll
EOF

cat > "$VAULT/ai-content-fabric/architecture.md" << 'EOF'
---
title: "AI Content Fabric — Architecture"
type: architecture
project: ai-content-fabric
tags: [python, moviepy, elevenlabs, whisper, openrouter]
created: 2026-04-05
---

# AI Content Fabric — Architecture

## Tech Stack

| Компонент | Технология |
|-----------|------------|
| Язык | Python 3.12 |
| AI Сценарист | OpenRouter (GPT-4o, Claude, DeepSeek) |
| Озвучка | ElevenLabs API (multilingual v2) |
| Субтитры | Whisper (STT) + Pillow (рендер) |
| Монтаж | MoviePy 2.x |
| Управление | Telegram Bot (python-telegram-bot) |
| B-roll | YouTube + Vision matching |

## Pipeline
```
Input (news/video) → AI Script → TTS (ElevenLabs) → 
  → Whisper (word timestamps) → B-roll matching →
  → MoviePy assembly → Dynamic subtitles → Output video
```

## Ключевые решения
- Brightness filter для фильтрации тёмных B-roll кадров
- Word-level субтитры для engagement
- Stress marks correction для правильного произношения
- SFX removal из финального рендера
EOF

# ============================================================
# 4. BOTSELLER
# ============================================================
mkdir -p "$VAULT/botseller"

cat > "$VAULT/botseller/prd.md" << 'EOF'
---
title: "BotSeller — PRD"
type: prd
project: botseller
tags: [telegram, bot, ecommerce, digital-goods, python]
created: 2026-04-05
---

# BotSeller — Product Requirements

## Обзор
Telegram-бот для продажи цифровых товаров. Monorepo с MVP и SaaS версиями.

## Версии
1. **MVP** (`/mvp`) — Single-tenant бот для одного магазина
2. **SaaS** (`/saas`) — Multi-tenant платформа (в разработке)

## Ключевые фичи
- Каталог цифровых товаров в Telegram
- Оплата и автоматическая доставка
- Broadcast рассылки подписчикам
- Админ-панель управления
- Landing page для привлечения клиентов

## Деплоймент
- Docker + docker-compose
- Railway (prod)
- Alembic миграции для БД
EOF

cat > "$VAULT/botseller/architecture.md" << 'EOF'
---
title: "BotSeller — Architecture"
type: architecture
project: botseller
tags: [python, telegram, docker, railway, postgresql]
created: 2026-04-05
---

# BotSeller — Architecture

## Tech Stack

| Компонент | Технология |
|-----------|------------|
| Язык | Python 3.x |
| Bot | python-telegram-bot / aiogram |
| Database | PostgreSQL + Alembic |
| Queue | Celery |
| Deploy | Docker → Railway |
| Landing | HTML/CSS |

## Структура monorepo
```
botseller/
├── mvp/              # Single-tenant бот
├── saas/             # Multi-tenant платформа
├── landing/          # Лендинг страница
├── alembic/          # Миграции БД
└── docker-compose.yml
```

## Ключевые решения
- Monorepo для MVP и SaaS в одном репозитории
- Celery для фоновых задач (рассылки)
- Railway для простого деплоя
- Playwright тесты для broadcasts
EOF

# ============================================================
# 5. SOCIAL-LEADS-PARSER
# ============================================================
mkdir -p "$VAULT/social-leads-parser"

cat > "$VAULT/social-leads-parser/prd.md" << 'EOF'
---
title: "Social Leads Parser — PRD"
type: prd
project: social-leads-parser
tags: [leads, parser, fastapi, telegram, facebook, reddit]
created: 2026-04-05
---

# Social Leads Parser — Product Requirements

## Обзор
Система лид-генерации и фильтрации из социальных платформ — Telegram, Facebook, Reddit, Nextdoor.

## Ключевые фичи
1. **Campaign Management** — Кампании с ключевыми словами, минус-словами, AI-промптами
2. **Source Tracking** — Привязка каналов/групп к кампаниям
3. **6-Step Filtering Pipeline** — blacklist → minus-words → keywords → dedup → AI validation → save
4. **Lead Management** — Статусы лидов (new → in_progress → success/rejected)
5. **Blacklist** — Блокировка авторов
6. **Statistics** — Статистика по статусам лидов

## Метрики
- Precision фильтрации > 80%
- False positive rate < 10%
EOF

cat > "$VAULT/social-leads-parser/architecture.md" << 'EOF'
---
title: "Social Leads Parser — Architecture"
type: architecture
project: social-leads-parser
tags: [fastapi, sqlalchemy, sqlite, python, docker]
created: 2026-04-05
---

# Social Leads Parser — Architecture

## Tech Stack

| Компонент | Технология |
|-----------|------------|
| Backend | FastAPI + SQLAlchemy 2.0 |
| Database | SQLite |
| API Docs | Swagger UI (auto-generated) |
| Deploy | Docker + docker-compose |
| Templates | Jinja2 (HTML UI) |

## Filtering Pipeline
```
Message → Blacklist check → Minus-words filter →
  → Keywords match → Deduplication → AI Validation →
  → Save as Lead
```

## Ключевые решения
- 6-step pipeline для максимальной точности
- SQLAlchemy 2.0 с async support
- AI validation через LLM для финальной проверки
EOF

# ============================================================
# 6. BRIEFTUBE (YouTube AI SaaS)
# ============================================================
# Already has notes, let's update with more detail
cat > "$VAULT/brieftube/guidelines.md" << 'EOF'
---
title: "BriefTube — Guidelines"
type: guidelines
project: brieftube
tags: [flutter, supabase, youtube, ai, ios]
created: 2026-04-05
---

# BriefTube — Development Guidelines

## Coding Standards
- Flutter/Dart — camelCase для переменных, PascalCase для классов
- Riverpod для state management
- GoRouter для навигации

## AI Content Quality
- Threads/Newsletters/Flashcards должны быть профессионального качества
- Prompt engineering для engagement и readability
- Не использовать generic phrases

## YouTube Integration
- Dedicated GoogleSignIn instance для channel connectivity
- Scoped auth — отдельный от основного auth flow
- YouTube Data API v3 для данных канала

## iOS Build
- `flutter build ipa` для сборки
- TestFlight для тестирования
- App Store submission checklist в docs/
EOF

# ============================================================
# 7. YOUTUBE-PARSER (Channel Watch)
# ============================================================
mkdir -p "$VAULT/youtube-parser"

cat > "$VAULT/youtube-parser/prd.md" << 'EOF'
---
title: "Channel Watch — PRD"
type: prd
project: youtube-parser
tags: [youtube, flutter, supabase, fastapi, ai]
created: 2026-04-05
---

# Channel Watch — Product Requirements

## Обзор
Мобильное приложение для отслеживания YouTube-контента с AI-саммари.

## Ключевые фичи
- Отслеживание YouTube каналов
- AI-суммаризация новых видео
- Push-уведомления о новом контенте
- Dashboard со статистикой каналов

## Tech Stack
| Компонент | Технология |
|-----------|------------|
| Mobile | Flutter (Dart) |
| Auth & DB | Supabase (PostgreSQL + Auth + RLS) |
| Backend | Python 3.12 + FastAPI + APScheduler |
| AI | OpenRouter (GPT-4, Gemini) |
| Deploy | Docker → Railway |
EOF

cat > "$VAULT/youtube-parser/architecture.md" << 'EOF'
---
title: "Channel Watch — Architecture"
type: architecture
project: youtube-parser
tags: [flutter, supabase, fastapi, docker, railway]
created: 2026-04-05
---

# Channel Watch — Architecture

## Структура
```
channel-watch/
├── app/          # Flutter mobile app
├── backend/      # Python FastAPI server
├── docs/         # PRD, архитектура
└── docker-compose.yml
```

## Backend Pipeline
```
APScheduler (cron) → YouTube API → Parse new videos →
  → AI Summarize (OpenRouter) → Save to Supabase →
  → Push notification to users
```

## Ключевые решения
- Supabase RLS для безопасности данных
- APScheduler для периодического парсинга
- OpenRouter для гибкого выбора AI-модели
- Docker multi-stage build для деплоя
EOF

# ============================================================
# 8. ZILLOW-PARSER (NorCal Deal Engine)
# ============================================================
mkdir -p "$VAULT/zillow-parser"

cat > "$VAULT/zillow-parser/prd.md" << 'EOF'
---
title: "NorCal Deal Engine — PRD"
type: prd
project: zillow-parser
tags: [real-estate, zillow, scraper, ai-vision, python]
created: 2026-04-05
---

# NorCal Deal Engine — Product Requirements

## Обзор
Автоматизированный pipeline для скрапинга Zillow, AI-анализа недвижимости и рассылки инвесторам.

## Ключевые фичи
1. **Market Data Integration** — Real-time ZIP code метрики (median $/sqft, days on market)
2. **Deal Scoring Engine** — Скоринг 0-100 (discount, spread, ROI, distress)
3. **Fast Lane (B2C)** — Instant flip alerts в Discord
4. **Slow Lane (B2B)** — Professional renovation proposals по Email
5. **AI Vision Analysis** — GPT-4o анализ фото для оценки ремонта
6. **Cost-Optimized Scraping** — Two-stage (Search $2/1k → Detail $3/1k)
7. **Deduplication** — SQLite для предотвращения дублей
8. **Distress Detection** — Keywords ("probate", "as-is", "must sell")
EOF

cat > "$VAULT/zillow-parser/architecture.md" << 'EOF'
---
title: "NorCal Deal Engine — Architecture"
type: architecture
project: zillow-parser
tags: [python, fastapi, sqlite, gpt4o-vision, zillow]
created: 2026-04-05
---

# NorCal Deal Engine — Architecture

## Pipeline
```
Search Scraper ($2/1000) → Pre-filter → Route:
  ├── Fast Lane → Discord alerts (fresh, high-score)
  └── Slow Lane → Email proposals (stale, with upside)
```

## Tech Stack
| Компонент | Технология |
|-----------|------------|
| Язык | Python |
| API | FastAPI |
| Database | SQLite |
| AI | GPT-4o Vision (анализ фото) |
| Scraping | Zillow API ($2-3/1k requests) |
| Alerts | Discord webhooks |
| Email | SMTP |
| Retry | Tenacity |

## Ключевые решения
- Two-stage scraping для оптимизации затрат
- AI Vision для оценки стоимости ремонта по фото
- Deal scoring algorithm (0-100) на основе нескольких факторов
- Cron runner для автоматического парсинга
EOF

# ============================================================
# 9. NORCAL-DEALS (FlipRadar) — Flutter app for zillow-parser
# ============================================================
mkdir -p "$VAULT/norcal-deals"

cat > "$VAULT/norcal-deals/prd.md" << 'EOF'
---
title: "FlipRadar — PRD"
type: prd
project: norcal-deals
tags: [flutter, real-estate, mobile, deals]
created: 2026-04-05
---

# FlipRadar — Product Requirements

## Обзор
Flutter мобильное приложение — фронтенд для NorCal Deal Engine.
Показывает выгодные сделки с недвижимостью инвесторам.

## Связь
- Backend: zillow-parser (NorCal Deal Engine)
- Данные: Zillow listings с AI-скорингом
EOF

# ============================================================
# 10. DANCE-STUDIO-WEBSITE
# ============================================================
mkdir -p "$VAULT/dance-studio-website"

cat > "$VAULT/dance-studio-website/prd.md" << 'EOF'
---
title: "Dance Studio Website — PRD"
type: prd
project: dance-studio-website
tags: [website, html, css, landing, client-work]
created: 2026-04-05
---

# Dance Studio Website

## Обзор
Сайт для студии танцев. Статический HTML/CSS сайт.

## Страницы
- Главная (index.html)
- О студии (about.html)
- Галерея (gallery.html)
- Тренеры (trainer.html)
- Расписание (styles.html)
- Контакты (contacts.html)
EOF

# ============================================================
# 11. CONTENT-FABRIC-SAAS
# ============================================================
mkdir -p "$VAULT/content-fabric-saas"

cat > "$VAULT/content-fabric-saas/prd.md" << 'EOF'
---
title: "Content Fabric SaaS — PRD"
type: prd
project: content-fabric-saas
tags: [flutter, supabase, ai, content, saas]
created: 2026-04-05
---

# Decision-First Content Factory — PRD

## Обзор
Decision-first контент-движок для билдеров. НЕ copywriting tool.

## Философия
Система ВСЕГДА:
1. Решает ЧТО сказать
2. Решает чего НЕ говорить
3. Решает ANGLE
4. Решает СТРАТЕГИЧЕСКУЮ ЦЕЛЬ
5. ТОЛЬКО ПОТОМ генерирует текст

## Tech Stack
- Frontend: Flutter (iOS + Android)
- Backend: Supabase (Auth, PostgreSQL, Storage, Edge Functions)
- AI: OpenAI / Anthropic (via Edge Functions)
EOF

# ============================================================
# 12. ASTRO-PSIHOLOG
# ============================================================
mkdir -p "$VAULT/astro-psiholog"

cat > "$VAULT/astro-psiholog/prd.md" << 'EOF'
---
title: "Astro Psiholog — PRD"
type: prd
project: astro-psiholog
tags: [flutter, mobile, ai, astrology, psychology]
created: 2026-04-05
---

# Astro Psiholog — PRD

## Обзор
AI-powered astrology and psychology companion app. Flutter приложение.

## Tech Stack
- Frontend: Flutter
- Платформы: iOS, Android, Web
EOF

# ============================================================
# 13. MY-REMOTE-OFFICE
# ============================================================
mkdir -p "$VAULT/my-remote-office"

cat > "$VAULT/my-remote-office/prd.md" << 'EOF'
---
title: "My Remote Office — PRD"
type: prd
project: my-remote-office
tags: [telegram, bot, task-management, productivity]
created: 2026-04-05
---

# My Remote Office — PRD

## Обзор
Telegram-бот для управления задачами и продуктивностью.

## Модули
- **Task Bridge** — Управление задачами
- **Telegram Bridge** — Интеграция с Telegram
EOF

# ============================================================
# 14. ZILLOW-LANDING
# ============================================================
mkdir -p "$VAULT/zillow-landing"

cat > "$VAULT/zillow-landing/prd.md" << 'EOF'
---
title: "Zillow Landing — PRD"
type: prd
project: zillow-landing
tags: [nextjs, landing, real-estate]
created: 2026-04-05
---

# Zillow Landing — PRD

## Обзор
Landing page для NorCal Deal Engine. Next.js приложение.

## Связь
- Backend: zillow-parser
- Mobile: norcal-deals (FlipRadar)
EOF

# ============================================================
# 15. SENDLER-BOT (Codex Swarm)
# ============================================================
mkdir -p "$VAULT/sendler-bot"

cat > "$VAULT/sendler-bot/prd.md" << 'EOF'
---
title: "Codex Swarm — PRD"
type: prd
project: sendler-bot
tags: [ai, agents, codex, python, workflow]
created: 2026-04-05
---

# Codex Swarm

## Обзор
Multi-agent workflow система для OpenAI Codex. 
Превращает IDE + Codex plugin в предсказуемый мульти-агентный pipeline.

## Ключевые фичи
- JSON-defined agents
- Shared task backlog
- Commit rules для трассируемости
- Direct и branch_pr workflow modes
EOF

# ============================================================
# 16. YT-SAAS-FRONTEND
# ============================================================
mkdir -p "$VAULT/yt-saas-frontend"

cat > "$VAULT/yt-saas-frontend/prd.md" << 'EOF'
---
title: "YT SaaS Frontend — PRD"
type: prd
project: yt-saas-frontend
tags: [nextjs, admin, dashboard, typescript, shadcn]
created: 2026-04-05
---

# YT SaaS Frontend — PRD

## Обзор
Next.js admin dashboard template. Studio Admin с множественными дашбордами.

## Tech Stack
- Next.js 16, TypeScript, Tailwind CSS v4, Shadcn UI
- Theme presets (light/dark, цветовые схемы)
- Responsive, mobile-friendly
- Auth flows
- RBAC (planned)
EOF

echo "✅ All vault notes created successfully!"
echo ""
echo "Summary of notes created:"
find "$VAULT" -name "*.md" -not -path "*/_templates/*" | sort | while read f; do
  project=$(echo "$f" | sed "s|$VAULT/||" | cut -d/ -f1)
  note=$(basename "$f" .md)
  echo "  [$project] $note"
done
