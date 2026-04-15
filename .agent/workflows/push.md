---
description: Full push workflow — commit, push, update docs, log to vault. Use when user writes /push.
---
// turbo-all

# /push — Full Push: Commit + Push + Docs + Vault

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
  title="Session <YYYY-MM-DD>: <brief description>",
  note_type="note",
  content="## What was done\n<list>\n\n## Key decisions\n<if any>\n\n## Next steps\n<list>",
  tags=["session", "push"]
)
```
   - If architectural decisions were made → also create a `decision` note
   - If architecture changed → update `architecture.md` via `create_note()`

8. **Update architecture map in vault** (MCP tool):
```
scan_architecture(project="<project-slug>")
```
   - Updates `<project>/architecture-map.md` in vault
   - Contains: modules, dependencies, Mermaid diagram
   - Runs automatically, no confirmation needed

9. (Optional) Log activity to your portfolio/dashboard:
```bash
# Load your API key from wherever you store it
# source $HOME/Projects/your-portfolio/.env
# curl -s -X POST https://your-site.dev/api/agent/activity \
#   -H "Authorization: Bearer $YOUR_API_KEY" \
#   -H "Content-Type: application/json" \
#   -d '{
#     "projectSlug": "<project-slug>",
#     "type": "push",
#     "title": "<commit message>",
#     "details": "<what was done>"
#   }'
```
   - Skip this step if you don't have a portfolio API
