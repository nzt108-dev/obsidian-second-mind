# Obsidian Second Mind — Current Status
> Last updated: 2026-04-09

## Version / Build Status
- **Version**: 0.8.0
- **Status**: ✅ All systems operational
- **ruff**: All checks passed
- **pytest**: 18/18 passed
- **Import chain**: No circular deps

## What's Done

### Core System (v0.1–v0.4)
- MCP server with 20+ tools
- Vector search (ChromaDB + sentence-transformers)
- Hybrid search (BM25 + vector + RRF fusion)
- Cross-encoder reranking
- MMR diversity
- Vault parser + linter
- Knowledge graph (WikiLinks)
- Pattern extraction
- Decay-based scoring
- File watcher daemon

### Intelligence Layer (v0.5)
- Session analyzer (repeating problems)
- Tech Radar (npm/GitHub scanning)
- Dependency checker

### Capture & Recall (v0.6)
- Telegram bot (text, URLs, voice/Whisper, photos/OCR)
- Wake-up context (~200 token summary)
- CLI: `bot` command

### Cascade Intelligence (v0.7)
- Cascade Ingest pipeline (1 source → N wiki updates)
- Auto Radar with diff tracking + Telegram alerts
- Entity extraction + concept stub generation
- CLI: `ingest`, `radar` commands

### Temporal Brain (v0.8)
- Temporal Knowledge Graph (facts with valid_from/valid_to)
- Contradiction detection + auto-resolution
- Auto fact extraction from notes (FactExtractor)
- 10 tech categories, 80+ technologies
- MCP tools: kg_add_fact, kg_invalidate, kg_timeline, kg_check_contradictions

## Known Issues / Blockers
- None critical
- Whisper/OCR require separate installs (`pip install openai-whisper`, `brew install tesseract`)

## What's Next
- **v0.9.0 — Agent Memory**: Auto-save hooks, emergency save, session continuity
- **v1.0.0 — Ultimate Brain**: Full integration, dashboard, self-maintenance

## Key Files
- `src/obsidian_bridge/mcp_server.py` — MCP server (1300+ lines, 20+ tools)
- `src/obsidian_bridge/graph.py` — Knowledge Graph + Temporal KG
- `src/obsidian_bridge/fact_extractor.py` — Auto fact extraction
- `src/obsidian_bridge/ingest.py` — Cascade Ingest pipeline
- `src/obsidian_bridge/telegram_bot.py` — Telegram capture bot
- `src/obsidian_bridge/auto_radar.py` — Auto Radar + diff
- `src/obsidian_bridge/wakeup.py` — Wake-up context generator
