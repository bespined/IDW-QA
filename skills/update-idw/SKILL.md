---
name: update-idw
description: "Pull the latest plugin code and show what changed. Any authenticated role."
---

# Update Plugin

> **Run**: `/update-idw`

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python3 scripts/idw_metrics.py --track skill_invoked --context '{"skill": "update-idw"}'
```

## Purpose

Pulls the latest IDW QA plugin code from the remote repository and shows what changed. Any authenticated user can run this — admin pushes a fix, tells the team "run `/update-idw`", and everyone gets it. If already on the latest version, nothing happens.

## Role Gate

This skill requires any authenticated role. Run:

```bash
python3 scripts/role_gate.py --check any
```

- If exit code is 0: proceed
- If exit code is 1: show the error and stop.

## Workflow

### 1. Pre-flight Check

Check for uncommitted changes that might conflict:

```bash
cd /Users/bespined/claude-plugins/IDW-QA && git status --porcelain
```

If there are uncommitted changes, warn the admin:

> **Warning: You have uncommitted local changes.** Pulling might cause merge conflicts.
> Files changed:
> - [list files]
>
> Options:
> 1. **Pull anyway** — git will try to merge
> 2. **Stash and pull** — save changes, pull, then reapply
> 3. **Cancel** — don't pull, keep current version

### 2. Show Current Version

```bash
cd /Users/bespined/claude-plugins/IDW-QA && git log --oneline -1
```

### 3. Pull Latest

```bash
cd /Users/bespined/claude-plugins/IDW-QA && git pull --rebase origin main
```

If pull fails due to conflicts:
- Show which files conflict
- Offer to abort the rebase: `git rebase --abort`
- Tell the admin to resolve manually

### 4. Show Changelog

After successful pull, show what changed:

```bash
cd /Users/bespined/claude-plugins/IDW-QA && git log --oneline HEAD@{1}..HEAD
```

Then categorize changes:

```bash
cd /Users/bespined/claude-plugins/IDW-QA && git diff --stat HEAD@{1}..HEAD
```

Present as:

> **Updated to `<commit hash>`**
>
> ### What changed:
> - **Skills**: [list modified skill files]
> - **Scripts**: [list modified scripts]
> - **Config**: [list modified config/standards files — **these affect audit quality**]
> - **Migrations**: [list new migration files — IMPORTANT: these need to be run!]
>
> ### Commits:
> - `abc1234` feat: add /assignments skill
> - `def5678` fix: dashboard view column names

**If `config/standards_enrichment.yaml` changed**, call that out explicitly:

> **Audit quality improvement**: The enrichment cards were updated based on RLHF disagreement analysis. Standards with previously low agreement rates have sharper criteria. Your next audit will produce more accurate findings.

**If any `skills/*.md` changed**, note:

> **Skills updated**: [list]. These changes take effect immediately — no restart needed.

### 5. Migration Alert

If any new migration files were added:

> **New database migration(s) detected:**
> - `migrations/004_update_dashboard_views.sql`
>
> These need to be run in the Supabase SQL Editor before the new features work.
> Want me to show the migration SQL?

### 6. Dependency Check

Check if any Python dependencies changed:

```bash
cd /Users/bespined/claude-plugins/IDW-QA && git diff HEAD@{1}..HEAD -- requirements.txt 2>/dev/null
```

If requirements.txt changed:
> **Python dependencies changed.** Run `pip install -r requirements.txt` to update.

## Error Handling

- Not a git repo: "The plugin directory isn't a git repository. It may have been installed differently."
- No remote: "No remote configured. Set one with `git remote add origin <url>`."
- Network error: "Can't reach the remote repository. Check your internet connection."
- Not on main branch: warn and ask before pulling.
