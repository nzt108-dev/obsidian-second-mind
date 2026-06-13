# Env Variables — obsidian-second-mind

Все переменные читаются через `pydantic_settings` с префиксом `OBSIDIAN_BRIDGE_`.
Можно задавать в `.env` или экспортировать в shell.

## Vault / Core

| Переменная | По умолчанию | Описание |
|-----------|-------------|---------|
| `OBSIDIAN_BRIDGE_VAULT_PATH` | `~/SecondMind` | Путь к Obsidian vault |
| `OBSIDIAN_BRIDGE_CHROMA_PATH` | `~/.obsidian-bridge/chroma` | ChromaDB persistent storage |
| `OBSIDIAN_BRIDGE_HOST` | `127.0.0.1` | MCP server host |
| `OBSIDIAN_BRIDGE_PORT` | `9108` | MCP server port |

## Search / Index

| Переменная | По умолчанию | Описание |
|-----------|-------------|---------|
| `OBSIDIAN_BRIDGE_CHUNK_SIZE` | `500` | Chunk size in characters |
| `OBSIDIAN_BRIDGE_CHUNK_OVERLAP` | `50` | Chunk overlap |
| `OBSIDIAN_BRIDGE_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model |
| `OBSIDIAN_BRIDGE_HYBRID_SEARCH` | `true` | Hybrid search (vector+BM25) |
| `OBSIDIAN_BRIDGE_RERANKING` | `true` | Cross-Encoder reranking |
| `OBSIDIAN_BRIDGE_MMR_DIVERSITY` | `true` | MMR diversity reranking |

## Telegram Bot

| Переменная | По умолчанию | Описание |
|-----------|-------------|---------|
| `OBSIDIAN_BRIDGE_TELEGRAM_BOT_TOKEN` | `""` | Token from @BotFather. Required for `obsidian-bridge bot` |
| `OBSIDIAN_BRIDGE_TELEGRAM_ALLOWED_USERS` | `[]` | Whitelist user IDs. Empty = deny all |
| `OBSIDIAN_BRIDGE_TELEGRAM_DEFAULT_PROJECT` | `inbox` | Default project for captured notes |
| `OBSIDIAN_BRIDGE_TELEGRAM_OWNER_ID` | — | Owner ID for Telegram notifications |

## Backup (v0.7.0)

| Переменная | По умолчанию | Обязателен | Описание |
|-----------|-------------|-----------|---------|
| `OBSIDIAN_BRIDGE_BACKUP_RCLONE_REMOTE` | `""` | **да** | rclone crypt-remote name, напр. `gdrive-crypt:`. Backup fail-closed если пусто |
| `OBSIDIAN_BRIDGE_BACKUP_DIR` | `obsidian-backups` | нет | Папка на remote для архивов |
| `OBSIDIAN_BRIDGE_BACKUP_KEEP_DAILY` | `7` | нет | Сколько ежедневных архивов хранить на remote |

## GitHub Radar

| Переменная | По умолчанию | Описание |
|-----------|-------------|---------|
| `OBSIDIAN_BRIDGE_GITHUB_TOKEN` | — | GitHub token (повышает API лимит) |
