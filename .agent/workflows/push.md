---
description: Full push workflow — commit, push, update docs, log to vault + portfolio. Use when user writes /push.
---
// turbo-all

# /push — Всё в одном: Commit + Push + Docs + Vault + Portfolio

## Steps

1. Check what changed:
```bash
git status
git diff --stat
```

2. Stage and commit all changes:
```bash
git add -A
git commit -m "<type>: <description>"
```
   - Types: `feat`, `fix`, `build`, `docs`, `refactor`, `chore`

3. Push to GitHub:
```bash
git push
```

4. Update `docs/SESSION_LOG.md`:
   - Add commit hash + message
   - What was done this session
   - Issues encountered
   - Next steps

5. Update `docs/CURRENT_STATUS.md`:
   - Update version, what's done, what's next, known issues

6. Commit docs:
```bash
git add docs/SESSION_LOG.md docs/CURRENT_STATUS.md
git commit -m "docs: update session log"
git push
```

7. **Log session to Obsidian vault** (MCP tool):
```
create_note(
  project="<project-slug>",
  title="Session <YYYY-MM-DD>: <краткое описание работы>",
  note_type="note",
  content="## Что сделано\n<список>\n\n## Ключевые решения\n<если были>\n\n## Что дальше\n<список>",
  tags=["session", "push"]
)
```
   - Если были архитектурные решения — дополнительно создай `decision` заметку
   - Если менялась архитектура — обнови `architecture.md` через `create_note()`

8. Update project metadata in portfolio (Mission Control sync):
```bash
source /Users/nzt108/Projects/architect-portfolio/.env
COMMIT_HASH=$(git rev-parse --short HEAD)
COMMIT_MSG=$(git log -1 --pretty=%s)
COMMIT_DATE=$(git log -1 --pretty=%aI)
curl -s -X POST https://nzt108.dev/api/agent/projects \
  -H "Authorization: Bearer $PORTFOLIO_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"slug\": \"<project-slug>\",
    \"title\": \"<Project Title>\",
    \"lastCommitHash\": \"$COMMIT_HASH\",
    \"lastCommitMsg\": \"$COMMIT_MSG\",
    \"lastCommitDate\": \"$COMMIT_DATE\"
  }"
```

9. Log activity to portfolio:
```bash
source /Users/nzt108/Projects/architect-portfolio/.env
curl -s -X POST https://nzt108.dev/api/agent/activity \
  -H "Authorization: Bearer $PORTFOLIO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "projectSlug": "<project-slug>",
    "type": "push",
    "title": "<commit message>",
    "details": "<what was done>"
  }'
```

## Skip portfolio if
- Project is not registered on portfolio (check with user)
- Project slug unknown (ask user)

10. **Update architecture map in vault** (MCP tool):
```
scan_architecture(project="<project-slug>")
```
   - Обновляет файл `<project>/architecture-map.md` в vault
   - Содержит: модули, зависимости, Mermaid диаграмму
   - Выполняется автоматически, без подтверждения
