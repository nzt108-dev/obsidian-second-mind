# Obsidian Second Mind — Roadmap v0.4.0 "Adaptive Brain"

> Цель: закрыть оставшиеся 5 разрывов с AI-мозгом. Превратить пассивную базу знаний в самообучающуюся систему.

---

## 1. 📉 Decay Scoring — Relevance по свежести

**Что**: Каждый чанк получает decay-коэффициент на основе даты `updated`.  
Свежие заметки ранжируются выше. Старые постепенно теряют вес.

**Формула**: `decay_score = base_score × e^(-λ × days_since_update)`  
- λ = 0.005 (полупериод ~139 дней)
- Настраиваемый через `config.py`

**Файлы**:
- `indexer.py` — добавить decay в scoring pipeline (Stage 7)
- `config.py` — `decay_enabled: bool`, `decay_lambda: float`
- `models.py` — `Chunk.metadata` + поле `updated_date`

**Сложность**: 🟢 Легко (2-3 часа)

---

## 2. 🕸️ Queryable Knowledge Graph — программный граф

**Что**: Построить граф из WikiLinks, доступный через MCP tool `query_graph`.  
Не просто визуальный (Obsidian), а программный — agent может спросить:
- "Какие проекты связаны с Supabase?"
- "Покажи все связи для brieftube"
- "Найди кластеры похожих проектов"

**Архитектура**:
```
WikiLinks из markdown → NetworkX граф в памяти
                      → MCP tool: query_graph(node, depth, direction)
                      → Ответ: связи, соседи, степень связности
```

**Новый MCP tool**:
```python
Tool(
    name="query_graph",
    description="Query the knowledge graph. Find connections between notes, 
                 hub pages, clusters, and paths between concepts.",
    inputSchema={
        "properties": {
            "node": {"type": "string", "description": "Note stem or concept name"},
            "query_type": {
                "type": "string",
                "enum": ["neighbors", "path", "hubs", "clusters", "stats"],
            },
            "depth": {"type": "integer", "default": 2},
        },
        "required": ["query_type"],
    },
)
```

**Файлы**:
- `graph.py` — **NEW** — NetworkX граф, построение из WikiLinks, queries
- `mcp_server.py` — новый tool `query_graph`
- `pyproject.toml` — зависимость `networkx`

**Сложность**: 🟡 Средне (4-5 часов)

---

## 3. 🧠 Auto-Rules — извлечение паттернов из Outcomes

**Что**: Анализировать Outcome секции в decision notes.  
Извлекать паттерны: "когда мы делали X, результат был Y".  
Формировать автоматические правила/guidelines.

**Логика**:
1. Найти все decision notes с Outcome
2. Классифицировать: success / partial / failed
3. Из failed → извлечь anti-patterns (что НЕ делать)
4. Из success → извлечь best practices
5. Сохранить как `_global/auto-rules.md` с перекрёстными ссылками

**Новый MCP tool**:
```python
Tool(
    name="extract_patterns",
    description="Analyze decision outcomes across projects. Extract success patterns 
                 and anti-patterns. Generate auto-rules from accumulated experience.",
    inputSchema={
        "properties": {
            "project": {"type": "string", "description": "Optional: filter by project"},
            "min_decisions": {"type": "integer", "default": 3},
        },
    },
)
```

**Файлы**:
- `patterns.py` — **NEW** — анализ outcomes, extraction, rule generation
- `mcp_server.py` — tool `extract_patterns`

**Сложность**: 🔴 Сложно (6-8 часов, нужен LLM для анализа)

> **Заметка**: Для полноценного auto-rules нужен LLM вызов (OpenAI/Claude API).  
> Простая версия — regex/heuristic extraction — реализуема без API.

---

## 4. 🔔 Watchdog Hooks — авто-триггеры при изменениях

**Что**: У нас уже есть `watcher.py` (watchdog).  
Расширить его: при изменении vault файлов автоматически:
- Re-index изменённых заметок
- Обновить index.md
- Rebuild граф
- Запустить lint на изменённых файлах

**Текущий `watcher.py`**: наблюдает за файлами, но не выполняет действий.

**Новые хуки**:
| Триггер | Действие |
|---------|----------|
| Файл создан | Index + update index.md + log |
| Файл изменён | Re-index + update graph |
| Файл удалён | Remove from index + update index.md |
| Каждые 24ч | Auto-lint + decay recalc |

**Файлы**:
- `watcher.py` — расширить обработчики событий
- `config.py` — `auto_lint_interval_hours: int = 24`

**Сложность**: 🟡 Средне (3-4 часа)

---

## 5. 📊 Enhanced Dashboard — визуализация графа и health

**Что**: Расширить существующий dashboard:
- Визуализация knowledge graph (D3.js force-directed)
- Lint health score (% здоровых заметок)
- Decay heatmap (свежесть заметок)
- Activity timeline из log.md

**Файлы**:
- `dashboard/index.html` — новые табы/секции
- `dashboard/app.js` — графы, charts
- `dashboard_data.py` — API endpoints для графа и lint

**Сложность**: 🟡 Средне (4-5 часов)

---

## Приоритет и порядок

| # | Фича | Приоритет | Зависимости | Estimated |
|---|------|-----------|-------------|-----------|
| 1 | Decay Scoring | 🟢 P1 | Нет | 2-3ч |
| 2 | Watchdog Hooks | 🟡 P2 | Decay (#1) | 3-4ч |
| 3 | Knowledge Graph | 🟡 P2 | Нет | 4-5ч |
| 4 | Dashboard v2 | 🟡 P3 | Graph (#3) | 4-5ч |
| 5 | Auto-Rules | 🔴 P4 | Outcome data | 6-8ч |

**Total estimate**: ~20-25 часов

---

## Метрики успеха v0.4.0

- [ ] Decay scoring влияет на ранжирование (свежие заметки выше)
- [ ] `query_graph` возвращает связи и кластеры
- [ ] Watchdog автоматически re-index'ит при изменениях
- [ ] Dashboard показывает граф и health score
- [ ] Минимум 5 auto-rules извлечено из decisions
- [ ] Все 17/17 параметров ✅ в сравнении с AI-мозгом
