#!/usr/bin/env python3
"""Create Notion Documentation Hub for Obsidian Second Mind."""
import json
import urllib.request
import os

# Load API key
env_path = os.path.expanduser("~/.gemini/antigravity/shared/.env")
with open(env_path) as f:
    for line in f:
        if line.startswith("NOTION_API_KEY="):
            API_KEY = line.strip().split("=", 1)[1]
            break

PARENT_ID = "33a6bf31-9f72-8136-9f64-c4a9ccdc5e80"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

def create_page(title, emoji, children):
    data = {
        "parent": {"page_id": PARENT_ID},
        "icon": {"type": "emoji", "emoji": emoji},
        "properties": {"title": [{"text": {"content": title}}]},
        "children": children,
    }
    req = urllib.request.Request(
        "https://api.notion.com/v1/pages",
        data=json.dumps(data).encode(),
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
        print(f"  ✅ {title} → {result['id']}")
        return result["id"]

def h2(text):
    return {"object":"block","type":"heading_2","heading_2":{"rich_text":[{"text":{"content":text}}]}}

def h3(text):
    return {"object":"block","type":"heading_3","heading_3":{"rich_text":[{"text":{"content":text}}]}}

def p(text):
    return {"object":"block","type":"paragraph","paragraph":{"rich_text":[{"text":{"content":text}}]}}

def bullet(text):
    return {"object":"block","type":"bulleted_list_item","bulleted_list_item":{"rich_text":[{"text":{"content":text}}]}}

def divider():
    return {"object":"block","type":"divider","divider":{}}

# ── 1. PRD ──
print("Creating pages...")
create_page("PRD — Product Requirements", "📋", [
    h2("Цель проекта"),
    p("MCP-сервер, превращающий Obsidian vault в Second Mind для AI-агентов. Семантический поиск по проектам, архитектуре, стандартам кодирования."),
    h2("Целевая аудитория"),
    bullet("Разработчики, использующие AI-агентов (Antigravity, Cursor, Windsurf)"),
    bullet("Команды, документирующие архитектуру в Obsidian"),
    h2("Ключевые фичи"),
    bullet("✅ Semantic search через ChromaDB + sentence-transformers"),
    bullet("✅ MCP Server: 7 tools, 3 resources"),
    bullet("✅ CLI: serve, index, search, watch, list-projects, add-project, status"),
    bullet("✅ File watcher daemon — авто-обновление индекса"),
    bullet("✅ Markdown parser: frontmatter, WikiLinks, inline tags"),
    bullet("✅ Mission Control dashboard интегрирован в nzt108.dev/admin"),
    h2("Технологический стек"),
    bullet("Python 3.11+, ChromaDB, sentence-transformers (all-MiniLM-L6-v2)"),
    bullet("MCP SDK, Watchdog, Click, Pydantic"),
    h2("Метрики успеха"),
    bullet("16+ проектов задокументированы в vault (28 заметок, 116 chunks)"),
    bullet("AI-агент использует контекст из vault в каждой сессии"),
    bullet("Сокращение времени на повторные объяснения контекста"),
])

# ── 2. FSD ──
create_page("FSD — Functional Specification", "🏗️", [
    h2("Архитектура"),
    p("Модульная Python-система: Parser → Indexer → MCP Server. Данные хранятся в ChromaDB (векторная БД), vault — в ~/SecondMind."),
    h2("Компоненты"),
    h3("parser.py — Markdown Parser"),
    bullet("Парсит YAML frontmatter"),
    bullet("Извлекает WikiLinks [[target]] и embeds ![[target]]"),
    bullet("Извлекает inline tags (#tag)"),
    h3("indexer.py — ChromaDB Indexer"),
    bullet("Чанкинг по заголовкам (H1, H2, H3)"),
    bullet("Эмбеддинги через sentence-transformers"),
    bullet("Метаданные: project, type, tags, path"),
    h3("mcp_server.py — MCP Server"),
    bullet("7 tools: search_vault, get_project_context, get_global_rules, get_note, list_projects, create_note, rebuild_index"),
    bullet("3 resources: vault://projects, vault://global, vault://status"),
    h3("cli.py — CLI Interface"),
    bullet("Commands: serve, index, search, watch, list-projects, add-project, status"),
    h3("watcher.py — File Watcher"),
    bullet("Watchdog-based daemon с debouncing"),
    bullet("Автоматически переиндексирует при изменении .md файлов"),
    h2("API — MCP Tools"),
    bullet("search_vault(query, project?, n_results?) → semantic search"),
    bullet("get_project_context(project) → полный контекст проекта"),
    bullet("get_global_rules() → глобальные стандарты"),
    bullet("list_projects() → список проектов с кол-вом заметок"),
    bullet("create_note(project, title, type, content) → создать заметку"),
])

# ── 3. User Flow Map ──
create_page("User Flow Map", "🗺️", [
    h2("Flow 1: AI-агент получает контекст проекта"),
    bullet("1. Пользователь открывает проект в IDE"),
    bullet("2. AI-агент вызывает get_project_context('faithly')"),
    bullet("3. MCP сервер читает vault → возвращает PRD + Architecture + Guidelines"),
    bullet("4. AI-агент использует контекст для кодирования"),
    divider(),
    h2("Flow 2: Семантический поиск"),
    bullet("1. AI-агент вызывает search_vault('authentication flow')"),
    bullet("2. ChromaDB ищет похожие chunks по эмбеддингам"),
    bullet("3. Возвращает top-N релевантных фрагментов с метаданными"),
    divider(),
    h2("Flow 3: Авто-индексация"),
    bullet("1. Пользователь редактирует заметку в Obsidian"),
    bullet("2. Watcher daemon детектирует изменение"),
    bullet("3. Debounce 2с → переиндексирует изменённый файл"),
    bullet("4. Следующий search уже видит обновлённые данные"),
    divider(),
    h2("Flow 4: Создание заметки через AI"),
    bullet("1. AI-агент принимает архитектурное решение"),
    bullet("2. Вызывает create_note(project, title, 'decision', content)"),
    bullet("3. Заметка сохраняется в vault + индексируется"),
    bullet("4. Доступна для будущих сессий"),
])

# ── 4. State Machines ──
create_page("State Machines (FSM)", "⚙️", [
    h2("MCP Server States"),
    bullet("IDLE → запущен, ожидает запросов"),
    bullet("SEARCHING → обрабатывает search_vault запрос"),
    bullet("INDEXING → rebuild_index вызван"),
    bullet("ERROR → ошибка ChromaDB/файловой системы → auto-retry"),
    divider(),
    h2("Watcher Daemon States"),
    bullet("WATCHING → мониторит файловую систему"),
    bullet("DEBOUNCING → изменение обнаружено, ждёт 2с"),
    bullet("REINDEXING → переиндексирует изменённые файлы"),
    bullet("WATCHING → после переиндексации"),
    divider(),
    h2("Note Lifecycle"),
    bullet("CREATED → заметка создана (create_note или вручную)"),
    bullet("INDEXED → чанки загружены в ChromaDB"),
    bullet("MODIFIED → файл изменён, watcher обнаружил"),
    bullet("RE-INDEXED → обновлённые чанки в ChromaDB"),
    bullet("DELETED → файл удалён → чанки удалены из индекса"),
])

# ── 5. Test Matrix ──
create_page("Test Matrix", "🧪", [
    h2("Core Functionality"),
    bullet("✅ Markdown parsing — frontmatter, WikiLinks, tags"),
    bullet("✅ Chunking — split by headings, metadata preserved"),
    bullet("✅ ChromaDB indexing — 116 chunks indexed"),
    bullet("✅ Semantic search — returns relevant results"),
    bullet("✅ MCP server — all 7 tools respond correctly"),
    h2("Integration Tests"),
    bullet("✅ CLI → Indexer → ChromaDB pipeline"),
    bullet("✅ MCP Server → IDE connection (Antigravity)"),
    bullet("✅ Watcher → auto-reindex on file change"),
    bullet("✅ Mission Control → portfolio DB sync"),
    h2("Edge Cases"),
    bullet("⬜ Empty vault — graceful handling"),
    bullet("⬜ Corrupted frontmatter — parser resilience"),
    bullet("⬜ Large files (>10K lines) — chunking performance"),
    bullet("⬜ Concurrent access — multiple MCP clients"),
    h2("Performance"),
    bullet("✅ Index 39 notes → <5 seconds"),
    bullet("⬜ Search latency benchmark (<500ms target)"),
    bullet("⬜ Memory usage with large vaults"),
])

print("\n✅ All 5 pages created successfully!")
