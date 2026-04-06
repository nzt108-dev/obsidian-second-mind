---
description: Full push workflow — commit, push, update docs, log to portfolio. Use when user writes /push.
---
// turbo-all

# /push — Commit + Push + Docs + Portfolio

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
   - Add commit hash + message to current session's Git Commits section

5. Update `docs/CURRENT_STATUS.md`:
   - Update version, what's done, what's next

6. Commit docs:
```bash
git add docs/SESSION_LOG.md docs/CURRENT_STATUS.md
git commit -m "docs: update session log"
git push
```

7. Update project metadata in portfolio (Mission Control sync):
```bash
source /Users/nzt108/Projects/architect-portfolio/.env
COMMIT_HASH=$(git rev-parse --short HEAD)
COMMIT_MSG=$(git log -1 --pretty=%s)
COMMIT_DATE=$(git log -1 --pretty=%aI)
curl -s -X POST https://nzt108.dev/api/agent/projects \
  -H "Authorization: Bearer $PORTFOLIO_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"slug\": \"obsidian-second-mind\",
    \"lastCommitHash\": \"$COMMIT_HASH\",
    \"lastCommitMsg\": \"$COMMIT_MSG\",
    \"lastCommitDate\": \"$COMMIT_DATE\"
  }"
```

8. Log activity to portfolio:
```bash
source /Users/nzt108/Projects/architect-portfolio/.env
curl -s -X POST https://nzt108.dev/api/agent/activity \
  -H "Authorization: Bearer $PORTFOLIO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "projectSlug": "obsidian-second-mind",
    "type": "push",
    "title": "<commit message>",
    "details": "<what was done>"
  }'
```

## Skip portfolio if
- Project is not registered on portfolio (check with user)
- Project slug unknown (ask user)
