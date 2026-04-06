#!/bin/bash
# Enrich ALL remaining vault projects with detailed architecture notes
VAULT="$HOME/SecondMind"

# ── ai-content-fabric (exists, needs detail) ──
cat >> "$VAULT/ai-content-fabric/architecture.md" << 'EOF'


## Детальная архитектура

### Pipeline
```
Input (YouTube URL / Script)
    ↓
ElevenLabs TTS → Audio (.mp3)
    ↓
Vision Matching → B-roll keyframes from Pexels/Pixabay
    ↓
MoviePy Compositor → Video assembly
    ↓
FFmpeg Encoding → Final .mp4 (1080p)
```

### Компоненты
- **script_engine.py** — парсинг и подготовка скрипта
- **tts_service.py** — ElevenLabs API (голос, интонация, ударения)
- **vision_matcher.py** — подбор B-roll по ключевым словам + brightness filter
- **compositor.py** — MoviePy сборка видео (Ken Burns, transitions)
- **audio_mixer.py** — фоновая музыка, нормализация

### Ключевые решения
- FFmpeg для финального encoding (CRF 18, H.264)
- Brightness filter для исключения тёмных кадров
- Кеширование B-roll для повторного использования
EOF
echo "✅ ai-content-fabric enriched"

# ── social-leads-parser (exists, needs detail) ──
cat >> "$VAULT/social-leads-parser/architecture.md" << 'EOF'


## Детальная архитектура

### System Overview
```
Scraper Workers (async)
    ↓
FastAPI Backend
    ↓
PostgreSQL (leads DB)
    ↓
Export API (CSV/JSON)
```

### Компоненты
- **scrapers/** — модули для разных соцсетей (Instagram, Facebook Groups, LinkedIn)
- **enricher.py** — обогащение лидов (email, phone, company)
- **deduplicator.py** — дедупликация по email/phone/name
- **export.py** — экспорт в CSV, JSON, Google Sheets

### Модель данных
- **Lead** — name, email, phone, source, tags, score, created_at
- **Campaign** — name, source_config, filters, status
- **ExportJob** — campaign_id, format, status, file_url
EOF
echo "✅ social-leads-parser enriched"

# ── zillow-parser (exists, needs detail) ──
cat >> "$VAULT/zillow-parser/architecture.md" << 'EOF'


## Детальная архитектура

### System Overview
```
Zillow API / Scraper
    ↓
FastAPI + Data Pipeline
    ↓
PostgreSQL (properties DB)
    ↓
Deal Scoring Engine
    ↓
Flutter App (FlipRadar) / API
```

### Компоненты
- **scraper.py** — Zillow data extraction
- **deal_scorer.py** — ARV, rehab cost estimation, profit calc
- **pipeline.py** — ETL: fetch → clean → score → store
- **api/routes.py** — REST API for Flutter app

### Deal Scoring Formula
```
Score = (ARV - PurchasePrice - RehabCost - ClosingCosts) / ARV * 100
- Score > 30% → Hot Deal 🔥
- Score > 20% → Good Deal ✅
- Score > 10% → Marginal ⚠️
- Score < 10% → Skip ❌
```
EOF
echo "✅ zillow-parser enriched"

# ── my-remote-office (exists, needs detail) ──
cat >> "$VAULT/my-remote-office/architecture.md" << 'EOF'


## Детальная архитектура

### System Overview
```
Telegram Bot (aiogram 3.x)
    ↓
Task Manager Service
    ↓
SQLite / PostgreSQL
    ↓
Scheduler (APScheduler)
```

### Компоненты
- **bot.py** — Telegram bot handlers
- **task_service.py** — CRUD для задач
- **scheduler.py** — напоминания, дедлайны
- **report_generator.py** — daily/weekly отчёты

### Модель данных
- **Task** — title, description, assignee, status, priority, due_date
- **Project** — name, tasks[], members[]
- **TimeEntry** — task_id, user_id, started_at, duration
EOF
echo "✅ my-remote-office enriched"

# ── architect-portfolio (NEW) ──
cat > "$VAULT/architect-portfolio/architecture.md" << 'EOF'
---
title: architect-portfolio — Architecture
type: architecture
project: architect-portfolio
tags:
- nextjs
- typescript
- prisma
- turso
- vercel
created: 2026-04-06
updated: 2026-04-06
---

# architect-portfolio — Architecture

## Обзор
Портфолио + лид-генерация + админ-панель + Mission Control.
Это тот же проект что nzt108-dev, но с точки зрения кода.

## Детальная архитектура

### Stack
```
Next.js 15 (App Router, RSC)
    ↓
Prisma ORM (schema-first)
    ↓
Turso (LibSQL cloud DB)
    ↓
Vercel (auto-deploy from main)
```

### Модули
- **Public** — /, /projects, /services, /contact (SSR + animations)
- **Admin** — /admin/projects, /admin/workspaces (Mission Control), /admin/leads, /admin/crm
- **Agent API** — /api/agent/projects, /api/agent/activity (для AI-агента)
- **Analytics** — /api/analytics/pageview, FB Pixel, MS Clarity

### DB Schema (Prisma)
- Project (25 projects, Mission Control fields)
- ActivityLog, CrmTask
- ContactSubmission (CRM leads + pipeline)
- PageView (analytics)
- Article, Topic (SEO blog)
- Skill, SocialLink, SiteSetting

### Ключевые решения
- TailwindCSS + CSS custom properties
- Server Components by default
- Agent API с Bearer token для автоматизации
- Mission Control dashboard с real-time git sync


## Связанные заметки
- [[prd|Требования (PRD)]]
- [[_global/coding-standards|Стандарты кодирования]]
- [[_global/tech-stack|Технологический стек]]
- [[_global/design-principles|Принципы дизайна]]
EOF
echo "✅ architect-portfolio architecture CREATED"

# ── astro-psiholog (NEW) ──
cat > "$VAULT/astro-psiholog/architecture.md" << 'EOF'
---
title: Astro Psiholog — Architecture
type: architecture
project: astro-psiholog
tags:
- flutter
- dart
- ai
- openrouter
created: 2026-04-06
updated: 2026-04-06
---

# Astro Psiholog — Architecture

## Обзор
Flutter AI-приложение для астро-психологических консультаций.

## Детальная архитектура

### Stack
```
Flutter App (iOS/Android)
    ↓
OpenRouter API (GPT-4 / Claude)
    ↓
Local Storage (Hive/SharedPreferences)
```

### Компоненты
- **natal_chart_service.dart** — расчёт натальной карты
- **ai_interpreter.dart** — AI-интерпретация через OpenRouter
- **profile_manager.dart** — хранение профилей пользователей
- **chat_screen.dart** — UI для диалога с AI

### Модель данных
- **UserProfile** — name, birthDate, birthTime, birthPlace
- **NatalChart** — sun, moon, ascendant, planets[], houses[]
- **Consultation** — question, answer, chart_context, created_at


## Связанные заметки
- [[prd|Требования (PRD)]]
- [[_global/coding-standards|Стандарты кодирования]]
- [[_global/design-principles|Принципы дизайна]]
EOF
echo "✅ astro-psiholog architecture CREATED"

# ── content-fabric-saas (NEW) ──
cat > "$VAULT/content-fabric-saas/architecture.md" << 'EOF'
---
title: Content Fabric SaaS — Architecture
type: architecture
project: content-fabric-saas
tags:
- flutter
- supabase
- ai
- saas
created: 2026-04-06
updated: 2026-04-06
---

# Content Fabric SaaS — Architecture

## Обзор
SaaS платформа для генерации контента. Decision-First Content Factory.

## Детальная архитектура

### Stack
```
Flutter Web + Mobile
    ↓
Supabase (Auth, DB, Storage, Edge Functions)
    ↓
AI Pipeline (OpenRouter)
    ↓
CDN (media delivery)
```

### Компоненты
- **content_generator/** — AI pipeline для генерации текста/видео
- **template_engine/** — шаблоны для разных типов контента
- **subscription/** — Stripe billing, тарифные планы
- **dashboard/** — аналитика использования

### Модель данных
- **Workspace** — name, owner_id, plan, usage_quota
- **ContentJob** — workspace_id, type, prompt, status, output_url
- **Template** — name, category, prompt_template, variables[]


## Связанные заметки
- [[prd|Требования (PRD)]]
- [[_global/coding-standards|Стандарты кодирования]]
EOF
echo "✅ content-fabric-saas architecture CREATED"

# ── dance-studio-website (NEW) ──
cat > "$VAULT/dance-studio-website/architecture.md" << 'EOF'
---
title: Dance Studio Website — Architecture
type: architecture
project: dance-studio-website
tags:
- html
- css
- javascript
- static
created: 2026-04-06
updated: 2026-04-06
---

# Dance Studio Website — Architecture

## Обзор
Статический сайт для студии танцев Dance Now Studio.

## Детальная архитектура

### Stack
```
HTML5 + CSS3 + Vanilla JS
    ↓
GitHub Pages (hosting)
```

### Страницы
- **index.html** — лендинг с Hero, расписание, преподаватели
- **schedule.html** — расписание занятий (таблица)
- **teachers.html** — карточки преподавателей
- **contact.html** — форма обратной связи

### Особенности
- Mobile-first responsive design
- CSS Grid + Flexbox layout
- Smooth scroll animations (IntersectionObserver)
- No dependencies, pure vanilla


## Связанные заметки
- [[prd|Требования (PRD)]]
- [[_global/design-principles|Принципы дизайна]]
EOF
echo "✅ dance-studio-website architecture CREATED"

# ── norcal-deals (NEW) ──
cat > "$VAULT/norcal-deals/architecture.md" << 'EOF'
---
title: NorCal Deals (FlipRadar) — Architecture
type: architecture
project: norcal-deals
tags:
- flutter
- dart
- real-estate
created: 2026-04-06
updated: 2026-04-06
---

# FlipRadar — Architecture

## Обзор
Flutter мобильное приложение для поиска выгодных сделок с недвижимостью в NorCal.

## Детальная архитектура

### Stack
```
Flutter App (iOS/Android)
    ↓
REST API (zillow-parser backend)
    ↓
PostgreSQL (properties DB)
```

### Компоненты
- **deal_list_screen.dart** — лента сделок с фильтрами
- **deal_detail_screen.dart** — детали объекта + scoring
- **map_screen.dart** — карта Google Maps с маркерами
- **saved_deals_screen.dart** — избранные сделки
- **notification_service.dart** — push уведомления о новых hot deals

### Модель данных
- **Property** — address, price, arv, rehab_cost, score, photos[]
- **SavedDeal** — user_id, property_id, notes, saved_at
- **Alert** — user_id, filters (min_score, area, price_range)


## Связанные заметки
- [[prd|Требования (PRD)]]
- [[zillow-parser/architecture|Zillow Parser Backend]]
- [[_global/coding-standards|Стандарты кодирования]]
EOF
echo "✅ norcal-deals architecture CREATED"

# ── sendler-bot (NEW) ──
cat > "$VAULT/sendler-bot/architecture.md" << 'EOF'
---
title: Sendler Bot (Codex Swarm) — Architecture
type: architecture
project: sendler-bot
tags:
- python
- telegram
- multi-agent
created: 2026-04-06
updated: 2026-04-06
---

# Codex Swarm — Architecture

## Обзор
Multi-agent Telegram рассыльщик. Управление несколькими ботами/аккаунтами для массовой рассылки.

## Детальная архитектура

### Stack
```
Orchestrator (Python)
    ↓
Agent Pool (Telegram bots/usernames)
    ↓
Redis (task queue, rate limiting)
    ↓
PostgreSQL (contacts, campaigns, logs)
```

### Компоненты
- **orchestrator.py** — распределение задач между агентами
- **agent.py** — единичный Telegram агент (Telethon/Pyrogram)
- **campaign_manager.py** — создание и управление рассылками
- **rate_limiter.py** — антиблокировка (delays, rotation)
- **contact_manager.py** — импорт/экспорт контактов

### Модель данных
- **Campaign** — name, message_template, contact_list_id, status, stats
- **Agent** — phone, session_file, status (active/banned/cooldown)
- **Contact** — username, phone, tags[], last_contacted
- **DeliveryLog** — campaign_id, agent_id, contact_id, status, error


## Связанные заметки
- [[prd|Требования (PRD)]]
- [[_global/coding-standards|Стандарты кодирования]]
EOF
echo "✅ sendler-bot architecture CREATED"

# ── yt-saas-frontend (NEW) ──
cat > "$VAULT/yt-saas-frontend/architecture.md" << 'EOF'
---
title: YT SaaS Frontend — Architecture
type: architecture
project: yt-saas-frontend
tags:
- nextjs
- typescript
- react
- admin
created: 2026-04-06
updated: 2026-04-06
---

# YT SaaS Frontend — Architecture

## Обзор
Next.js админ-панель для YouTube SaaS. Dashboard для управления каналами, видео, аналитикой.

## Детальная архитектура

### Stack
```
Next.js (App Router)
    ↓
REST API (youtube-parser backend)
    ↓
Supabase Auth
```

### Страницы
- **/dashboard** — обзор: каналов, видео, последние summaries
- **/channels** — список отслеживаемых каналов
- **/channels/[id]** — детали канала + видео
- **/videos/[id]** — summary, thread, newsletter, flashcards
- **/settings** — настройки аккаунта, API keys

### Компоненты
- **ChannelCard** — карточка канала (subscribers, videos count)
- **VideoSummary** — отображение AI-generated summary
- **AnalyticsChart** — графики (Recharts)
- **SideNav** — навигация


## Связанные заметки
- [[prd|Требования (PRD)]]
- [[youtube-parser/architecture|YouTube Parser Backend]]
- [[_global/coding-standards|Стандарты кодирования]]
EOF
echo "✅ yt-saas-frontend architecture CREATED"

# ── zillow-landing (NEW) ──
cat > "$VAULT/zillow-landing/architecture.md" << 'EOF'
---
title: Zillow Landing — Architecture
type: architecture
project: zillow-landing
tags:
- nextjs
- typescript
- landing
created: 2026-04-06
updated: 2026-04-06
---

# Zillow Landing — Architecture

## Обзор
Лендинг для NorCal Deals — привлечение инвесторов в недвижимость.

## Детальная архитектура

### Stack
```
Next.js (SSG)
    ↓
Vercel (hosting)
```

### Секции лендинга
- **Hero** — заголовок + CTA
- **How It Works** — 3 шага
- **Featured Deals** — примеры сделок
- **Testimonials** — отзывы
- **Pricing** — тарифные планы
- **Contact/CTA** — форма заявки

### Особенности
- SEO-optimized (meta tags, structured data)
- GSAP animations
- Mobile-first responsive
- UTM tracking для рекламных кампаний


## Связанные заметки
- [[prd|Требования (PRD)]]
- [[norcal-deals/architecture|FlipRadar App]]
- [[zillow-parser/architecture|Zillow Parser Backend]]
- [[_global/design-principles|Принципы дизайна]]
EOF
echo "✅ zillow-landing architecture CREATED"

echo ""
echo "=== ALL 11 PROJECTS ENRICHED ==="
