# Lib — Services, Utils

## Сервисы (app/services/)

| Сервис | Файл | Описание |
|--------|------|---------|

## Утилиты (app/utils/)

| Функция | Файл | Описание |
|---------|------|---------|

## Dependencies (app/dependencies.py)

| Dependency | Описание |
|-----------|---------|
| `get_db` | сессия БД |
| `get_current_user` | текущий пользователь |

## Celery Tasks (если есть)

| Task | Файл | Описание |
|------|------|---------|

---

## Inbox Auto-Router (`src/obsidian_bridge/inbox_router.py`)

Rule-based (no-LLM) классификация входящих captures → проект. Спека: `specs/spec-inbox-auto-router.md`.

| Функция | Описание |
|---------|---------|
| `classify(text, title, known_projects) -> RouteDecision` | Главная. Правила: R2 spec-заголовок (`ТЗ: <Name>` / `Проект называется <Name>` / `Project: <Name>`) → проект (новый если неизвестен); R1 упоминание известного проекта → в него; R3 иначе → `inbox`. |
| `_match_known_project` | R1: whole-word матч, игнор имён < 4 симв. и служебных корзин `_GENERIC_BUCKETS`, tie → inbox. |
| `_slugify_project` | Имя проекта → vault-safe slug (ASCII). Пустая строка если не-ASCII. |
| `RouteDecision` | dataclass: `project, note_type, reason, is_new_project`. |

**Интеграция:**
- `telegram_bot.handle_message` → авто-роутинг каждого входящего без явного `@project`; при матче — сохранение через `IngestPipeline` (`_cascade_ingest`) с cross-refs/concept stubs.
- CLI `obsidian-bridge process-inbox [--apply] [-n N]` → разовый разбор накопленного `inbox/`. Dry-run по умолчанию; `--apply` переносит и удаляет оригиналы.
