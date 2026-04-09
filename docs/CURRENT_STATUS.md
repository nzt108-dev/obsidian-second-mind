# Obsidian Second Mind — Current Status
> Last updated: 2026-04-08

## Version / Build Status
- **Version**: 0.5.0 "Intelligence Layer"
- **CI**: GitHub Actions (ruff + import check + pytest + CLI verify)
- **Lint**: ✅ All checks passed
- **Tests**: ✅ 18/18 passed (test_scout.py)

## What's Done
### Core (v0.1.0)
- Obsidian vault at ~/SecondMind/ — 19 projects, 53+ notes, 524+ chunks
- MCP server (stdio) — 14 tools
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

### Adaptive Brain (v0.4.0)
- **Knowledge Graph** — queryable graph from WikiLinks (26 nodes, 130 edges, hub detection)
- **Pattern Extractor** — auto-rules from decision outcomes (success/failure patterns)
- **Decay Scoring** — exponential decay in search (λ=0.005, fresh notes rank higher)
- **Enhanced Watcher** — auto-logging + index.md regen on vault changes

### Intelligence Layer (v0.5.0) ← NEW
- **Session Intelligence** — `analyze_sessions` tool: parses session logs, finds repeating problems, extracts workaround patterns, generates recommendations
- **Tech Radar** — `scout_tools` tool: scans npm registry and GitHub trending for new MCP servers, AI tools, devtools relevant to our stack
- **Dependency Watch** — `check_dependencies` tool: checks npm/pip/flutter deps against registries, classifies updates (major/minor/patch)
- **14 MCP tools** total (was 11)
- **httpx** added for async HTTP requests

### Infrastructure
- WikiLinks across 45/47 notes
- GitHub Actions CI
- Notion Documentation Hub
- Push workflow with portfolio sync
- Dashboard (HTML/JS)
- 18 unit tests (test_scout.py)

## Known Issues / Blockers
- YAML date parsing: tags like "2026-04-08" auto-parse as datetime.date — fixed with quoting
- MCP server needs restart after code changes
- Python environment: system Python (3.12) vs Xcode Python (3.9) need alignment

## What's Next
1. Add Outcome sections to all 10 decisions missing them
2. Dashboard v2 (graph visualization, health score)
3. Make `scout_tools` run periodically via watcher hooks
4. Add Community Pulse (Reddit/HN trending analysis)
5. Consider PyPI publish

## Key Files
- `src/obsidian_bridge/mcp_server.py` — MCP server (14 tools)
- `src/obsidian_bridge/scout.py` — Intelligence Layer (3 analyzers) ← NEW
- `src/obsidian_bridge/indexer.py` — Hybrid search + MMR
- `src/obsidian_bridge/linter.py` — Vault health checks
- `src/obsidian_bridge/graph.py` — Knowledge Graph
- `src/obsidian_bridge/patterns.py` — Pattern Extractor
- `src/obsidian_bridge/config.py` — All settings
- `tests/test_scout.py` — Unit tests for Intelligence Layer ← NEW
