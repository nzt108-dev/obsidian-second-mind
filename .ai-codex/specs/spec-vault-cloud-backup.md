# Spec: Зашифрованный облачный бэкап vault

> Файл: `.ai-codex/specs/spec-vault-cloud-backup.md`
> Приоритет: HIGH (vault содержит крипто-мнемоники, локального бэкапа нет)
> Связано: `adr/adr-001-backup-rclone-crypt.md`

---

## Что делает (поведение, не реализация)

- Ежедневно создаёт **компактный зашифрованный** снимок vault (`~/SecondMind`) и отправляет его в облако (Google Drive).
- Бэкапит **только источники истины** (текст + JSON-память), НЕ ChromaDB-индекс — индекс реиндексируется из текста командой `obsidian-bridge index`. Это и даёт «мало места».
- Хранит ротацию (несколько последних точек), чтобы случайная порча/удаление вчера можно было откатить.
- Команда восстановления: скачать → расшифровать → распаковать → реиндексировать.

## Кто использует / когда вызывается

- **cron** через новый LaunchAgent `dev.nzt108.obsidian-backup.plist` (раз в сутки, напр. 03:00).
- **вручную**: `obsidian-bridge backup` (разовый прогон) и `obsidian-bridge backup --restore <дата>` (восстановление).

## Что бэкапить / что исключить (критично)

**Включить:**
- все `*.md` в `~/SecondMind/` (659 файлов, ~3.4M)
- `_graph/` (facts.json — temporal KG)
- `_memory/*.json` (снапшоты сессий)
- `_global/`, `inbox/`, `.obsidian/` (настройки vault — лёгкие)

**Исключить:**
- ChromaDB-индекс `~/.obsidian-bridge/chroma` (вне vault, реиндексируется — не бэкапить)
- `*.lock`, `*.tmp` (служебные filelock-файлы)
- бинарный мусор, если появится

## Решение (см. ADR-001)

`tar` (с исключениями) → `gzip` → **`rclone` с `crypt`-remote** → Google Drive.
Шифрование **обязательно** (в vault есть `botseller/tron-wallet-mnemonics...md`). Ключ rclone crypt хранится только локально (`~/.config/rclone/rclone.conf`, chmod 600) — в облаке лежит зашифрованный непрозрачный blob.

Поток:
```
tar czf → secondmind-YYYY-MM-DD.tar.gz (~600KB–1MB)
  → rclone copy в crypt-remote (gdrive-crypt:obsidian-backups/)
  → ротация: rclone удаляет старше N точек
```

## Входные данные

| Параметр | Тип | Обязателен | Описание |
|----------|-----|-----------|----------|
| vault_path | env/config | да | `~/SecondMind` |
| rclone remote | config | да | имя crypt-remote, напр. `gdrive-crypt:` |
| backup dir | const | да | `obsidian-backups/` в облаке |
| keep_daily / keep_weekly | int | нет | ротация (дефолт: 7 daily + 4 weekly) |
| `--restore <дата>` | CLI flag | нет | режим восстановления |

## Выходные данные / результат

- В облаке: `gdrive-crypt:obsidian-backups/secondmind-YYYY-MM-DD.tar.gz` (зашифрован).
- Лог: `/tmp/obsidian-backup.log` — что забэкаплено, размер, успех/ошибка.
- Опционально: Telegram-уведомление при ошибке бэкапа (тишина при успехе).

## Edge cases — явно обработать

- [x] **rclone не установлен** → понятная ошибка с `brew install rclone` + инструкция настройки crypt-remote, не молчаливый провал
- [x] **rclone remote не настроен** → проверка `rclone listremotes` перед стартом, внятная ошибка
- [x] **Нет сети / Google Drive недоступен** → tar.gz сохранён локально (`~/.obsidian-bridge/backups/`), отправка повторится следующим запуском; лог-ошибка
- [x] **Конкурентная запись в vault во время tar** (бот пишет заметку) → tar может поймать частичный файл; приемлемо (текст, не транзакция) — но НЕ бэкапить `.tmp`/`.lock`
- [x] **Vault пуст / путь не существует** → не создавать пустой архив, лог-варнинг
- [x] **Шифрование не настроено, а в vault есть мнемоники** → backup БЕЗ crypt-remote должен **отказываться стартовать** (fail-closed), чтобы мнемоники не улетели в plaintext
- [x] **Восстановление**: после распаковки напомнить запустить `obsidian-bridge index` (ChromaDB не в архиве)
- [x] **Локальная ротация** `~/.obsidian-bridge/backups/` — не дать расти бесконечно (keep last 3 локально)

## Что НЕ входит (scope boundary)

- НЕ бэкапить ChromaDB-индекс (реиндексируется)
- НЕ делать realtime/continuous backup — только ежедневный снимок
- НЕ версионировать через git (см. ADR-001, отклонено)
- НЕ синхронизировать обратно (облако → vault) автоматически — restore только вручную
- НЕ поддерживать несколько облаков в первой версии (только то, что настроено в rclone)

## Performance criteria

| Метрика | Цель | Критично |
|---------|------|---------|
| Размер архива | < 1.5 MB (текст gzip) | да — «мало места» |
| Время бэкапа | < 30 сек | нет |
| Влияние на работу | фоновый cron, незаметно | да |

## Definition of Done

- [x] `obsidian-bridge backup` создаёт зашифрованный архив в Google Drive
- [x] Архив **не содержит** ChromaDB, `.lock`, `.tmp`
- [x] Размер архива < 1.5 MB
- [x] **fail-closed**: без crypt-remote backup отказывается стартовать
- [x] `obsidian-bridge backup --restore <дата>` скачивает + расшифровывает + распаковывает + подсказывает реиндекс
- [x] Ротация работает (старые точки удаляются)
- [x] LaunchAgent `dev.nzt108.obsidian-backup.plist` создан, ежедневно
- [x] Все edge cases обработаны
- [ ] README: раздел «Backup & Restore» с инструкцией одноразовой настройки rclone crypt (отложено)
- [x] `.ai-codex/components.md` + `env.md` обновлены

## Затронутые модули

- новый `src/obsidian_bridge/backup.py` (tar + исключения + rclone-обёртка + restore)
- `cli.py` (команда `backup` + флаг `--restore`)
- `config.py` (rclone remote name, backup dir, ротация)
- новый `~/Library/LaunchAgents/dev.nzt108.obsidian-backup.plist`
- README (раздел настройки)
