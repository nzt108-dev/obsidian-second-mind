# Obsidian Second Mind — Current Status
> Last updated: 2026-04-07

## Version / Build Status
- **Version**: 0.3.0 "Wiki Pattern"
- **CI**: GitHub Actions (ruff + import check + pytest + CLI verify)
- **Lint**: ✅ All checks passed

## What's Done
### Core (v0.1.0)
- Obsidian vault at ~/SecondMind/ — 19 projects, 53+ notes, 524+ chunks
- MCP server (stdio) — 9 tools
- Parser: frontmatter + WikiLinks + inline tags
- Indexer: ChromaDB + sentence-transformers

### Hybrid Search (v0.2.0)
- BM25 keyword index (rank-bm25)
- RRF fusion (vector + keyword)
- Cross-Encoder reranking

### Karpathy Wiki Pattern (v0.3.0)
- **Linter** — 6 health checks (orphans, stale, broken links, missing concepts, TODOs, frontmatter)
- **MMR diversity** — near-duplicate detection + Maximal Marginal Relevance
- **New tools**: update_note, lint_vault
- **New note types**: concept, comparison, synthesis, research
- **Auto-generated**: index.md (vault catalog) + log.md (operation log)
- **Wiki Schema**: _global/wiki-schema.md (vault conventions)

### Infrastructure
- WikiLinks across 45/47 notes
- GitHub Actions CI
- Notion Documentation Hub
- Push workflow with portfolio sync
- Dashboard (HTML/JS)

## Known Issues / Blockers
- YAML date parsing: tags like "2026-04-08" auto-parse as datetime.date — fixed with quoting
- MCP server needs restart after code changes

## What's Next (v0.4.0 "Adaptive Brain")
1. Decay Scoring — свежие заметки ранжируются выше
2. Watchdog Hooks — авто re-index при изменениях
3. Queryable Knowledge Graph — NetworkX + MCP tool
4. Dashboard v2 — визуализация графа + health score
5. Auto-Rules — паттерны из decision outcomes

## Key Files
- `src/obsidian_bridge/mcp_server.py` — MCP server (9 tools)
- `src/obsidian_bridge/indexer.py` — Hybrid search + MMR
- `src/obsidian_bridge/linter.py` — Vault health checks
- `src/obsidian_bridge/config.py` — All settings
- `docs/ROADMAP_v0.4.0.md` — Next version roadmap
