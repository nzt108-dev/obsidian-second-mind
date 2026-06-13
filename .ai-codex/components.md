# Components / Modules — obsidian-second-mind

## Core Modules (`src/obsidian_bridge/`)

| Модуль | Файл | Назначение |
|--------|------|-----------|
| MCP Server | `mcp_server.py` | 30 MCP tools (точка входа для Claude Code) |
| CLI | `cli.py` | Click CLI: serve, bot, index, watch, radar, backup, save… |
| Config | `config.py` | pydantic_settings, env prefix: OBSIDIAN_BRIDGE_ |
| Models | `models.py` | Note, Chunk dataclasses |
| Parser | `parser.py` | Frontmatter parsing, scan_vault |
| Indexer | `indexer.py` | ChromaDB + BM25 + hybrid search + MMR |
| Watcher | `watcher.py` | Watchdog file daemon |
| Graph | `graph.py` | WikiLink graph + TemporalKnowledgeGraph (facts.json) |
| Hooks | `hooks.py` | Session snapshots (save/load/wakeup-cache.json) |
| Wakeup | `wakeup.py` | Wake-up context generator |
| Ingest | `ingest.py` | Cascade ingest pipeline |
| FactExtractor | `fact_extractor.py` | Auto fact extraction (regex, LLM-free) |
| Linter | `linter.py` | Vault lint: orphans, stale, broken links |
| Patterns | `patterns.py` | Pattern extraction from notes |
| Scout | `scout.py` | Tech radar, session analysis, dependency checker |
| GithubRadar | `github_radar.py` | GitHub trending scanner + developer watchlist |
| ContextPacker | `context_packer.py` | Pack project into single file for LLM context |
| AutoRadar | `auto_radar.py` | Scheduled radar with diff tracking |
| Architect | `architect.py` | Architecture scanning (AST + module graph) |
| TelegramBot | `telegram_bot.py` | Telegram capture bot (text, URL, voice, photo, doc) |
| Dashboard | `dashboard_server.py` + `dashboard_data.py` | Local HTTP dashboard (127.0.0.1) |
| **Backup** | **`backup.py`** | **Encrypted cloud backup via rclone crypt (v0.7.0)** |

## Backup Module (`backup.py`) — v0.7.0

**`BackupConfig`** dataclass:
- `rclone_remote: str` — crypt-remote name (e.g. `gdrive-crypt:`)
- `backup_dir: str` — remote folder (default: `obsidian-backups`)
- `keep_daily: int` — rotation days (default: 7)
- `keep_weekly: int` — weekly copies (default: 4)
- `local_cache_dir: Path` — `~/.obsidian-bridge/backups` (last 3 copies)

**`BackupManager(vault_path, config)`** methods:
- `check_rclone()` — fail-closed: raises RuntimeError if remote empty
- `check_remote_configured()` — validates remote via `rclone listremotes`
- `create_archive(tmp_dir)` — tar.gz vault, excludes: `*.lock`, `*.tmp`, `__pycache__`, `*.pyc`
- `list_archive_contents(archive_path)` — for `--dry-run`
- `upload(archive_path)` — rclone copy → remote
- `rotate_remote()` — deletes remote archives older than keep_daily days
- `save_local_cache(archive_path)` — copies to local_cache_dir, keeps last 3
- `backup()` → dict — full cycle: check → tar → cache → upload → rotate
- `restore(date_str)` → Path — download + untar + reminder to reindex

## LaunchAgents (`~/Library/LaunchAgents/`)

| Label | Plist | Расписание |
|-------|-------|-----------|
| `dev.nzt108.obsidian-second-mind-bot` | `dev.nzt108.obsidian-second-mind-bot.plist` | RunAtLoad, KeepAlive |
| `dev.nzt108.github-radar` | `dev.nzt108.github-radar.plist` | Cron |
| `com.nzt108.obsidian-api` | `com.nzt108.obsidian-api.plist` | RunAtLoad |
| **`dev.nzt108.obsidian-backup`** | **`dev.nzt108.obsidian-backup.plist`** | **Daily 03:00** |
