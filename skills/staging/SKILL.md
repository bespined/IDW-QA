---
name: staging
description: "Preview staged pages, push content to Canvas with backup, or rollback to a previous version."
---

# Staging

> **Run**: `/staging`

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python scripts/idw_metrics.py --track skill_invoked --context '{"skill": "staging"}'
```
This records usage metrics for the pilot dashboard. Do not skip this step.

## HARD RULE — Stage Before Every Push

**ALL page HTML body changes must be staged and shown to the user before pushing to Canvas. No exceptions.**

This includes:
- Accessibility remediations (e.g., fixing alt text, heading hierarchy, color contrast)
- Formatting fixes (e.g., removing staging shells, aligning to a template)
- Structural corrections (e.g., wrapping images in `<p>`, removing inline styles)
- Copy edits or content updates of any size
- Bulk fixes across multiple pages

**The required sequence for every page body change:**
1. Write corrected HTML to `staging/{slug}.html`
2. Screenshot the staged page and show it in conversation
3. Wait for explicit user approval before proceeding
4. Push only after the user says "looks good", "push it", or equivalent

**Never push page HTML to Canvas in a single step** — even when the fix is trivial, obvious, or the user requested the change. Always stage → show → wait → push.

---

## Purpose

One skill for the entire publish workflow: preview staged content, push approved content to Canvas (with automatic backup), or rollback to a previous version.

## When to Use

- "Preview my staged pages" / "show me what it looks like" → **Preview mode**
- "Show me all pages in one view" / "unified preview" → **Unified Preview mode**
- "Push it" / "looks good, send to Canvas" → **Push mode**
- "Undo" / "rollback" / "revert" → **Rollback mode**
- "What's staged?" / "list staged pages" → **Status mode**

---

## Mode 1: Preview

Preview staged pages locally or on Canvas.

### Local Preview (Staged Content)

1. Run: `python scripts/staging_manager.py --list`
2. For each page (or user-specified page), open the staged HTML file via the local preview server (port 8111)
3. Screenshot into the conversation

### Canvas Preview (Live Content)

For previewing pages already on Canvas:

1. Resolve the page URL from user input (slug, module shorthand, keyword, or full URL)
2. Navigate browser to Canvas URL
3. Screenshot into conversation

**URL Resolution:**

| Input | Resolved URL |
|---|---|
| Page slug: `m1-overview` | `/courses/{id}/pages/m1-overview` |
| Module shorthand: `Module 3 quiz` | `/courses/{id}/pages/m3-knowledge-check` |
| Keyword: `modules` | `/courses/{id}/modules` |
| Full URL | Used as-is |

### Multi-Page Preview

For full module preview: resolve all page slugs from `course-config.json`, screenshot each (limit 7 per batch).

### Unified Preview (All Pages, One Document)

Renders every staged page vertically in a single scrollable HTML document — like Microsoft Word — with module/page annotations and a sticky sidebar TOC.

**When to use:** "Show me everything in one page", "unified preview", "I want to scroll through all pages"

**Generate:**

```bash
python scripts/unified_preview.py           # All staged pages
python scripts/unified_preview.py --open    # Generate and open in browser
python scripts/unified_preview.py --modules 1 3 5   # Only specific modules
python scripts/unified_preview.py --filter overview  # Only pages matching keyword
```

**Serves at:** `http://localhost:8111/_unified_preview.html` (when preview server is running)

**Features:**
- Sticky sidebar TOC with collapsible module groups and page filter search
- Each page annotated with: Module number, page type (color-coded), title, slug, published status, file size, last modified
- Scroll progress bar (ASU Gold)
- Active page highlighting in TOC as you scroll
- J/K keyboard shortcuts to jump between pages
- Print-friendly (sidebar and chrome hidden)
- Page type color coding: Overview (blue), Lesson (green), Knowledge Check (orange), Conclusion (maroon), etc.
- **Approval checkboxes** on each page — visual markers for review tracking
- **Read-only preview** — content is not editable in the browser; edits happen in Claude Code

**Review Workflow:**
1. Stage pages via `staging_manager.py`
2. Claude uses Claude Preview MCP to screenshot individual pages at `http://localhost:8111/{slug}.html`
3. Screenshots shown in conversation for user review
4. User approves or requests changes
5. Push approved pages via `/staging push` in Claude Code (backup → diff → push → clear)

**Unified Preview (optional bulk review):**
1. Run `python scripts/unified_preview.py` to generate scrollable document
2. Open via Claude Preview or browser at `http://localhost:8111/_unified_preview.html`
3. Scroll through pages, check approval boxes for visual tracking
4. "Copy Slugs" copies approved slugs to clipboard (for CLI use)
5. Approval is conversational — user tells Claude which pages to push

**Keyboard shortcuts:** `Space` = toggle approval on current page, `A` = select all, `D` = deselect all, `J`/`K` = navigate pages

**Output:** `staging/_unified_preview.html` (excluded from staging push — prefixed with `_`)

---

## Mode 2: Push

Push staged content to Canvas with diff review and automatic backup.

### Step 1 — List Staged Pages

Run: `python scripts/staging_manager.py --list`

### Step 2 — Show Diffs

For each staged page:
1. Get raw staged content: `python scripts/staging_manager.py --get-raw --slug <slug>`
2. Fetch current Canvas page: `canvas_api.get_page(config, slug)`
3. Generate diff: `diff_engine.unified_diff(current, staged)` + `diff_engine.diff_summary()`

Display summary table with line changes. Offer to show full diff for any page.

### Step 3 — Confirm

**Always display the target instance prominently before asking for confirmation:**

> Pushing to **[CANVAS_DOMAIN]** ([prod/dev])
> [N] pages ready to push:

If pushing **10 or more pages**, add a warning:
> "⚠ This is a large batch ([N] pages). Would you like to review the full list before pushing, or push all at once?"

User can:
- "Push all" → push everything
- "Push 1 and 3" → specific pages
- "Skip 2" → push all except
- "Cancel" → abort

### Step 4 — Backup + Push

For each page:
1. **Backup** current Canvas version before overwriting:
   - First, GET the current page body from Canvas via `canvas_api.get_page(config, slug)`
   - Save it to a temp file, then run:
   ```
   python scripts/backup_manager.py --save --course-id <id> --page-slug <slug> --html-file <tempfile> --diff-summary "<summary>"
   ```
   **IMPORTANT:** The flag is `--save` (not `--save-page`). This step MUST succeed before pushing.
2. **Push** staged HTML: `canvas_api.update_page(config, slug, staged_html)` (or create new page via POST)
3. **Clear** staged file: `python scripts/staging_manager.py --clear --slug <slug>`

### Step 5 — Report

Show push results with ✓ status per page, backup location, and rollback instructions.

---

## Mode 3: Rollback

Restore a Canvas page to a previous version from local backups.

### Step 1 — List Backups

Run: `python scripts/backup_manager.py --list --course-id <course_id>`

Display table with timestamp, page slug, changes, and size.

### Step 2 — Select Backup

User picks by number, page slug, or "latest [slug]".

### Step 3 — Show Diff

Compare backup HTML vs current Canvas HTML. Display unified diff.

### Step 4 — Backup Current + Restore

1. Save current version as a backup (so rollback is reversible)
2. Push backup HTML to Canvas
3. Confirm restoration

---

## Safety

- Every push creates a backup BEFORE overwriting
- Staged files only cleared after successful push
- Partial batch failures leave remaining files staged
- Rollbacks are reversible (current version backed up before restore)

## Error Handling

| Error | Resolution |
|---|---|
| No staged content | Direct to content skills |
| Canvas API error | Show error, keep staged file, retry |
| No backups found | Backups created by push operations |
| Auth redirect on preview | Ask user to log into Canvas in browser |
| DELETE returns already_removed | Safe to ignore — file was already pushed or cleaned |
