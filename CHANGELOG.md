# Changelog

All notable changes to Obsidian Second Mind.

## [1.0.0] — 2026-04-09 — Ultimate Brain

### Added
- Complete README with architecture diagram, full API reference
- PyPI-ready packaging with proper classifiers and URLs
- CHANGELOG.md

### Changed
- Version bump to 1.0.0 (stable release)
- Development Status: Alpha → Beta

---

## [0.9.0] — 2026-04-09 — Agent Memory

### Added
- `hooks.py` — Session save/load with git state capture
- Emergency save — fast context dump before session loss
- Enhanced wake-up — standard + session memory + Temporal KG
- Pre-computed wake-up cache (`_memory/wakeup-cache.json`)
- MCP tools: `save_session`, `load_session`, `get_enhanced_wakeup`
- CLI commands: `save`, `emergency-save`

---

## [0.8.0] — 2026-04-09 — Temporal Brain

### Added
- Temporal Knowledge Graph with `valid_from`/`valid_to` windows
- Contradiction detection engine
- Auto fact extraction from notes (regex-based, no LLM)
- MCP tools: `kg_add_fact`, `kg_invalidate`, `kg_timeline`, `kg_check_contradictions`

---

## [0.7.0] — 2026-04-09 — Cascade Intelligence

### Added
- Cascade Ingest pipeline — one source → N wiki updates
- Auto Radar — tech stack diff tracking with Telegram alerts
- Entity extraction and cross-referencing
- MCP tools: `ingest_source`, `auto_radar_scan`
- CLI commands: `ingest`, `radar`

---

## [0.6.0] — 2026-04-09 — Capture & Recall

### Added
- Telegram Capture Bot (text, URLs, voice, images)
- Wake-up Context generator (~200 tokens)
- `save_insight` tool for compounding knowledge loop
- LaunchAgent for auto-start on macOS login
- CLI command: `bot`

---

## [0.5.0] — 2026-04-08 — Intelligence Layer

### Added
- Session Analyzer — finds repeating problems across logs
- Tech Radar — scans for new relevant tools
- Dependency Checker — outdated packages and security
- MCP tools: `analyze_sessions`, `scout_tools`, `check_dependencies`

---

## [0.4.0] — 2026-04-08 — Adaptive Brain

### Added
- Decay-based search scoring (boosts recent + high-priority)
- WikiLink knowledge graph with traversal queries
- Pattern extraction from decision outcomes
- MCP tools: `query_graph`, `extract_patterns`

---

## [0.3.0] — Karpathy Wiki

### Added
- `index.md` auto-generated vault catalog
- `log.md` chronological operation log
- Vault linter (orphans, stale notes, broken links)
- MCP tool: `lint_vault`

---

## [0.2.0] — Hybrid Search

### Added
- BM25 keyword search alongside vector search
- RRF (Reciprocal Rank Fusion) for combining results
- Cross-encoder reranking for precision
- `update_note` tool

---

## [0.1.0] — Foundation

### Added
- Vault parser with YAML frontmatter extraction
- Semantic search via ChromaDB + sentence-transformers
- MCP server (stdio mode)
- File watcher for auto-indexing
- CLI: `serve`, `index`, `search`, `watch`, `status`
