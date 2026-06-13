# Spec: Тесты на ядро памяти (graph.py + hooks.py)

> Файл: `.ai-codex/specs/spec-core-memory-tests.md`
> Приоритет: HIGH (самые ценные данные системы без единого теста)

---

## Что делает (поведение, не реализация)

- Покрыть тестами два модуля, которые хранят **накопленную память системы**: `graph.py` (TemporalKnowledgeGraph — факты с историей) и `hooks.py` (SessionHooks — снапшоты сессий). Сейчас на оба = 0 тестов; молчаливая потеря данных не будет замечена.
- Тесты должны ловить регрессии в: записи на диск (особенно новый filelock + atomic write), разрешении противоречий, ротации, восстановлении.

## Кто использует / когда вызывается

- **CI** (`.github/workflows/ci.yml`) и `pytest` локально перед коммитом.

## Что покрыть — graph.py (`TemporalKnowledgeGraph`)

| Тест | Условие | Ожидаемый результат |
|------|---------|---------------------|
| `test_add_fact_creates_active_fact` | новый факт | `active_fact_count == 1`, `valid_to is None` |
| `test_invalidate_marks_fact_expired` | invalidate существующего | старый `valid_to` проставлен, не active |
| `test_contradiction_auto_resolves` | факт противоречит активному (subject+predicate, другой object) | старый → expired, новый → active |
| `test_timeline_includes_expired` | 2 факта (1 expired) | timeline возвращает оба в хронологии |
| `test_query_entity_active_only` | смешанные факты | возвращает только active |
| `test_persist_roundtrip` | add → новый инстанс из того же пути | факты загружены идентично |
| `test_persist_atomic_no_partial` | прерывание записи (мок) | `facts.json` не остаётся битым (atomic .tmp→replace) |
| `test_concurrent_persist_filelock` | два инстанса пишут | оба факта сохранены, нет потери (filelock) |

## Что покрыть — hooks.py (`SessionHooks`)

| Тест | Условие | Ожидаемый результат |
|------|---------|---------------------|
| `test_save_session_creates_snapshot` | save_session | JSON в `_memory/{project}-latest.json` + архив с timestamp |
| `test_load_session_returns_latest` | save → load | возвращает последний снапшот |
| `test_load_session_missing_project` | проект без снапшотов | graceful (None / понятное сообщение, не краш) |
| `test_emergency_save_minimal` | emergency_save | снапшот с git-статусом, без полного скана |
| `test_wakeup_cache_updated` | save_session | `wakeup-cache.json` содержит запись проекта |
| `test_wakeup_cache_atomic` | прерывание записи (мок) | кэш не остаётся битым |
| `test_concurrent_cache_write_filelock` | два save_session разных проектов параллельно | обе записи в кэше (filelock, нет затирания) |
| `test_prune_keeps_n_recent` | N+5 снапшотов | остаётся ровно N последних |

## Входные данные

| Параметр | Тип | Описание |
|----------|-----|----------|
| tmp vault | `tmp_path` fixture | изолированный vault per-test, не трогать `~/SecondMind` |

## Edge cases — явно обработать

- [ ] Все тесты на `tmp_path`, НИ ОДИН не пишет в реальный `~/SecondMind`
- [ ] Конкурентность — реальные потоки/процессы или мок filelock, проверить отсутствие потери
- [ ] Битый существующий JSON на входе → graceful (не краш, лог)
- [ ] timezone в датах фактов (если сравнение дат — зафиксировать ожидание)

## Что НЕ входит (scope boundary)

- Не тестировать ChromaDB/indexer (отдельная задача)
- Не тестировать MCP-обёртки tools (отдельная задача)
- Не рефакторить сам graph.py/hooks.py — только тесты (если тест вскроет баг — отдельным фиксом)

## Performance criteria

| Метрика | Цель | Критично |
|---------|------|---------|
| Время прогона новых тестов | < 2 сек | да (CI быстрый) |

## Definition of Done

- [ ] `tests/test_graph.py` и `tests/test_hooks.py` созданы
- [ ] Все таблицы выше покрыты (happy + edge)
- [ ] `pytest -q` зелёный, не трогает реальный vault
- [ ] filelock/atomic поведение покрыто (защита фиксов из коммита d667ec9)
- [ ] CI проходит

## Затронутые модули

- `tests/test_graph.py` (новый)
- `tests/test_hooks.py` (новый)
- читают: `src/obsidian_bridge/graph.py`, `src/obsidian_bridge/hooks.py`, `config.py` (для tmp Settings)
