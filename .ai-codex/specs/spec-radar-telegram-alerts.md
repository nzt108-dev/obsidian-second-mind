# Spec: GitHub Radar — рабочие Telegram-уведомления

> Файл: `.ai-codex/specs/spec-radar-telegram-alerts.md`
> Приоритет: HIGH (быстрая победа, ~30 мин)

---

## Что делает (поведение, не реализация)

- Ежедневный GitHub Radar (LaunchAgent, 10:00) после сканирования **отправляет в Telegram** сводку находок (трендовые репо + активность watched-разработчиков), а не молча пишет только в `inbox/`.
- Если находок нет — уведомление не шлётся (не спамить).
- Если Telegram не настроен — работает как раньше (тихо в inbox), без падения.

## Кто использует / когда вызывается

- **cron** через LaunchAgent `~/Library/LaunchAgents/dev.nzt108.github-radar.plist` → `scripts/github_radar_cron.py`.

## Проблема (текущее состояние, подтверждено)

- `scripts/github_radar_cron.py:113-114` читает `OBSIDIAN_BRIDGE_TELEGRAM_BOT_TOKEN` и `OBSIDIAN_BRIDGE_TELEGRAM_OWNER_ID` из `os.environ`.
- LaunchAgent **не наследует** `.env` проекта → переменные пусты → в логе `/tmp/github-radar.log`: `Telegram not configured, skipping notification`.
- Алерты не приходили ни разу с момента создания.

## Решение (рекомендуемое)

Заставить `github_radar_cron.py` загружать `.env` проекта через `python-dotenv` (уже в зависимостях), **а не** дублировать секреты в plist. Один источник секретов = `.env`.

```python
# в начале github_radar_cron.py, после определения PROJECT_ROOT:
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
```

Альтернатива (отклонена): прописать `<key>EnvironmentVariables</key>` в plist — дублирует токен в ещё одном файле, рассинхрон при ротации токена.

## Входные данные

| Параметр | Тип | Обязателен | Описание |
|----------|-----|-----------|----------|
| `OBSIDIAN_BRIDGE_TELEGRAM_BOT_TOKEN` | env | да (для алертов) | из `.env` |
| `OBSIDIAN_BRIDGE_TELEGRAM_OWNER_ID` | env | да (для алертов) | chat_id получателя |

## Выходные данные / результат

- Telegram-сообщение владельцу со списком находок (parse_mode=HTML, **с `html.escape()`** для названий репо/юзеров — см. фикс инъекций в `telegram_bot.py`).
- Запись в `inbox/github-radar-YYYY-MM-DD.md` (как сейчас).

## Edge cases — явно обработать

- [ ] `.env` отсутствует → не падать, работать без алертов (текущее поведение)
- [ ] Токен есть, `OWNER_ID` нет → лог-варнинг, не падать
- [ ] Telegram API недоступен → лог-ошибка, inbox всё равно записан
- [ ] 0 находок → уведомление НЕ отправляется
- [ ] Названия репо с `<`, `>`, `&` → `html.escape()` перед вставкой в HTML

## Что НЕ входит (scope boundary)

- Не менять логику сканирования GitHub
- Не добавлять интерактивные кнопки/команды в уведомление
- Не трогать plist (решение через dotenv)

## Definition of Done

- [ ] `python3 scripts/github_radar_cron.py` вручную с заполненным `.env` → приходит Telegram-сообщение
- [ ] Без `.env` → отрабатывает в inbox без ошибок
- [ ] Edge cases обработаны
- [ ] `.ai-codex/components.md` отмечает рабочий канал алертов

## Затронутые модули

- `scripts/github_radar_cron.py` (загрузка .env + html.escape в формировании сообщения)
- проверить функцию отправки уведомления (использует `httpx` к Telegram Bot API)
