# Schema — Database / Pydantic Models

## Таблицы (PostgreSQL / SQLite)

### `users`
| Поле | Тип | Описание |
|------|-----|---------|
| `id` | uuid / serial | PK |
| `created_at` | timestamptz | дата создания |

## Pydantic Schemas

| Схема | Файл | Описание |
|-------|------|---------|
| `UserCreate` | `app/schemas.py` | создание пользователя |

## Миграции

- Инструмент: Alembic / SQL вручную
- Down-команды: записывать сюда перед каждой миграцией
