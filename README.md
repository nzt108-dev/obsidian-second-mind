# 🧠 Obsidian Second Mind

> Turn your Obsidian vault into a **Second Mind** for AI coding agents.

An MCP (Model Context Protocol) server that gives AI assistants in your IDE instant access to your Obsidian knowledge base — architecture decisions, coding guidelines, project requirements, and business logic.

## ✨ Features

- **🔌 MCP Server** — Direct integration with AI coding agents (ANTIGRAVITY, Cursor, Claude Desktop)
- **🔍 Semantic Search** — Find relevant notes by meaning, not just keywords (powered by ChromaDB + sentence-transformers)
- **📁 Project-Aware** — Organize knowledge by project, get context for the right codebase
- **👁️ File Watcher** — Auto-updates the search index when you edit notes in Obsidian
- **📝 Create Notes from IDE** — AI can save architecture decisions and guidelines back to your vault
- **⚡ Fully Local** — No cloud, no API keys, everything runs on your machine

## 🚀 Quick Start

### 1. Install

```bash
# Clone the repo
git clone https://github.com/nzt108-dev/obsidian-second-mind.git
cd obsidian-second-mind

# Create virtual environment and install
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Configure

```bash
# Copy example config
cp .env.example .env

# Edit .env and set your vault path
# OBSIDIAN_BRIDGE_VAULT_PATH=~/your-obsidian-vault
```

### 3. Build the index

```bash
obsidian-bridge index
```

### 4. Connect to your IDE

Add to your IDE's MCP config:

```json
{
  "mcpServers": {
    "obsidian-second-mind": {
      "command": "/path/to/obsidian-second-mind/.venv/bin/obsidian-bridge",
      "args": ["serve"]
    }
  }
}
```

## 🛠️ Available MCP Tools

| Tool | Description |
|------|-------------|
| `search_vault` | Semantic search across your entire vault |
| `get_project_context` | Full context for a project (PRD + Architecture + Rules) |
| `get_global_rules` | Global coding standards and design principles |
| `list_projects` | List all projects in the vault |
| `get_note` | Read a specific note |
| `create_note` | Create a new note from IDE |
| `rebuild_index` | Rebuild the search index |

## 📁 Recommended Vault Structure

```
~/SecondMind/
├── _global/           # Rules that apply to ALL projects
│   ├── coding-standards.md
│   ├── tech-stack.md
│   └── design-principles.md
├── _templates/        # Note templates
├── my-project/        # Per-project knowledge
│   ├── prd.md
│   ├── architecture.md
│   ├── api-rules.md
│   └── decisions/
└── _inbox/            # Quick unsorted notes
```

Each note should have YAML frontmatter:

```yaml
---
project: my-project
type: architecture    # prd | architecture | guidelines | api | decision
tags:
  - auth
  - flutter
priority: high
---
```

## 🖥️ CLI Commands

```bash
obsidian-bridge serve          # Start MCP server
obsidian-bridge index          # Build/rebuild search index
obsidian-bridge search "auth"  # Search from terminal
obsidian-bridge watch          # Auto-index on file changes
obsidian-bridge list-projects  # Show all projects
obsidian-bridge add-project x  # Create project structure
obsidian-bridge status         # Show vault & index stats
```

## 🧪 How It Works

1. **Parser** reads your `.md` files, extracts YAML frontmatter, resolves `[[wikilinks]]`
2. **Indexer** splits notes into chunks and creates embeddings using `sentence-transformers`
3. **ChromaDB** stores vectors locally for fast semantic search
4. **MCP Server** exposes tools that AI agents call directly from your IDE
5. **File Watcher** detects changes and re-indexes automatically

## 📄 License

MIT — see [LICENSE](LICENSE)

## 🤝 Contributing

PRs welcome! Please open an issue first to discuss what you'd like to change.
