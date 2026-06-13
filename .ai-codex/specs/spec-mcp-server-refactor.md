# Spec: Распил mcp_server.py (god-module → dispatch + tool-модули)

> Файл: `.ai-codex/specs/spec-mcp-server-refactor.md`
> Приоритет: MEDIUM (тормозит развитие, не баг)

---

## Что делает (поведение, не реализация)

- `mcp_server.py` (1640 строк) разбивается так, чтобы добавление нового MCP-tool не требовало правок в гигантском файле и 600-строчной `elif`-цепи.
- **Поведение для пользователя/агента НЕ меняется** — все 30 tools работают идентично, те же имена, те же схемы, те же результаты. Это чистый рефакторинг.

## Текущее состояние (подтверждено)

- `list_tools()` — строки 337-935 (~600 строк определений схем 30 tools).
- `call_tool()` — строки 935-1626, **`if/elif` на 30 веток** (`name == "search_vault"` … `elif name == "pack_context"`).
- Любой новый tool = правка в двух местах одного файла, риск конфликтов, тяжело читать.

## Решение (рекомендуемое направление — финальное за разработчиком)

1. **Dispatch dict вместо elif-цепи**: `TOOL_HANDLERS: dict[str, Callable]` — `call_tool` ищет хендлер по имени, единый fallback на неизвестный tool.
2. **Группировка по категориям** (уже видны в коде) в отдельные модули `mcp_tools/`:
   - `notes.py` — search_vault, get_project_context, get_global_rules, list_projects, get_note, create_note, update_note
   - `maintenance.py` — lint_vault, rebuild_index, query_graph, extract_patterns
   - `scout.py` — analyze_sessions, scout_tools, check_dependencies
   - `capture.py` — get_wakeup_context, save_insight, ingest_source, auto_radar_scan
   - `temporal.py` — kg_add_fact, kg_invalidate, kg_timeline, kg_check_contradictions
   - `memory.py` — save_session, load_session, get_enhanced_wakeup
   - `radar.py` — scan_architecture, scan_github_trending, watch_developer, analyze_repo, pack_context
3. Каждый модуль экспортирует свои `Tool(...)` определения + хендлеры; `mcp_server.py` их собирает.

## Входные / выходные данные

- Не меняются. Контракт MCP остаётся бит-в-бит идентичным.

## Edge cases — явно обработать

- [ ] Неизвестное имя tool → тот же ответ-ошибка, что сейчас
- [ ] Порядок tools в `list_tools()` сохранён (или явно не важен — проверить, что клиенты не зависят от порядка)
- [ ] Все импорты-циклы исключены (модули tools не импортируют mcp_server)
- [ ] `cli.py`, `watcher.py` импортируют `_regenerate_index`, `_append_to_log` из mcp_server — **сохранить эти публичные функции доступными** (или перенести в utils и обновить импорты)

## Что НЕ входит (scope boundary)

- НЕ менять логику ни одного tool
- НЕ добавлять/удалять tools
- НЕ менять схемы входных параметров
- НЕ трогать `list_resources`/`read_resource`

## Definition of Done

- [ ] `call_tool` — без `elif`-цепи, через dispatch
- [ ] Tools разнесены по `mcp_tools/` модулям
- [ ] Все 30 tools отвечают идентично (golden-тест: до/после на наборе вызовов)
- [ ] `ruff check .` чисто, `pytest -q` зелёный
- [ ] MCP-сервер стартует, Claude Code видит все 30 tools
- [ ] `_regenerate_index`/`_append_to_log` импорты в watcher/cli не сломаны
- [ ] `.ai-codex/lib.md` обновлён под новую структуру

## Риск / стоп-сигнал

- ⚠️ Это рефакторинг >5 файлов. Делать в отдельной ветке, golden-тест ДО начала (записать выводы всех 30 tools на тестовом vault), сверять после.

## Затронутые модули

- `src/obsidian_bridge/mcp_server.py` (распил)
- новый пакет `src/obsidian_bridge/mcp_tools/`
- `watcher.py`, `cli.py` (проверить импорты)
