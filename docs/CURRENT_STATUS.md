# Obsidian Second Mind — Current Status
> Last updated: 2026-06-12

## Version / Build Status
- **Version**: 1.2.0
- **Status**: ✅ All systems operational
- **ruff**: 0 ошибок
- **pytest**: 51/51 passed (включая 18 новых тестов graph + hooks)
- **MCP Server**: 30 tools, dispatch dict архитектура
- **Backup**: ✅ gdrive-crypt, LaunchAgent daily 03:00

## What's Done

### Core System (v0.1–v1.0)
- MCP server с 30 tools (vector + BM25 + hybrid search, reranking, MMR)
- Temporal Knowledge Graph (filelock + atomic write)
- Session snapshots (filelock + atomic write)
- Vault parser + linter + pattern extraction
- Telegram bot (text, URLs, voice/Whisper, photos/OCR, .md/.txt files)

### Security & Data Integrity (v1.1.0)
- fail-closed на пустой TELEGRAM_ALLOWED_USERS
- html.escape на всех динамических данных в Telegram
- delete_note() в indexer — нет stale ChromaDB chunks
- filelock + atomic tmp→replace в graph.py и hooks.py

### Radar & Alerts (v1.2.0)
- GitHub Radar Telegram HTML-отчёт (structured data, не просто markdown)
- python-dotenv в cron — токены загружаются без shell inheritance
- Тесты: test_graph.py (9), test_hooks.py (9) — filelock, atomic, concurrent

### MCP Architecture Refactor (v1.2.0)
- mcp_server.py: 1640 → 375 строк
- Dispatch dict: `HANDLERS[name](args)` вместо 30-ветки elif
- mcp_tools/: notes, maintenance, scout_tools, capture, temporal, memory, radar

### Encrypted Cloud Backup (v1.2.0)
- backup.py — tar.gz (исключает ChromaDB, .lock, .tmp) → rclone crypt → Google Drive
- fail-closed: без crypt-remote — отказывается стартовать
- Ротация: 7 daily remote + 3 локальных
- LaunchAgent dev.nzt108.obsidian-backup.plist, daily 03:00
- Первый бэкап: 787 KB ✅

## Known Issues / Blockers
- README: раздел «Backup & Restore» не написан (низкий приоритет)

## What's Next
- Написать README раздел Backup & Restore (инструкция настройки rclone crypt)
- Multi-vault support (v1.3.0)
- ChromaDB тесты (отдельный спек)

## Key Files
- `src/obsidian_bridge/mcp_server.py` — точка входа MCP (375 строк)
- `src/obsidian_bridge/mcp_tools/` — 7 модулей, 30 tools
- `src/obsidian_bridge/backup.py` — зашифрованный бэкап
- `src/obsidian_bridge/hooks.py` — session snapshots (filelock)
- `src/obsidian_bridge/graph.py` — Temporal KG (filelock)
- `src/obsidian_bridge/telegram_bot.py` — Telegram capture bot
- `tests/test_graph.py`, `tests/test_hooks.py` — 18 новых тестов
