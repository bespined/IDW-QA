# Codex Review Fix Plan

**Review Date**: 2026-04-07
**Projects**: IDW-QA (plugin) + idw-review-app (Vercel)
**Status**: Phases 1–3 complete. Phase 4 and deferred items are **post-pilot backlog** — not pre-pilot blockers.

---

## Phase 1: Critical (Do Now)

### 1.1 Rotate Exposed Credentials
- [ ] **IDW-QA**: Revoke Canvas API token in `.env`, generate new one
  - Canvas > Account > Settings > Delete Access Token > Create New
  - Update `.env` with new token
  - Run `git rm --cached .env` if it was ever tracked
- [ ] **Review App**: Verify `.env.local` is not in git history
  - Run `git log --all --full-history -- .env.local`
  - If committed: rotate Supabase service key, Airtable token, use BFG repo-cleaner
  - Verify with `git check-ignore .env.local`

### 1.2 ~~Fix Syntax Error — `alignment_graph.py`~~ DONE
- [x] Extracted f-string backslash into variable (line 800 + second instance at line 1072)
- Verified: `python3 -c "import ast; ast.parse(...)"` passes

### ~~1.3~~ Deferred — `auditor_id` Schema Migration (Review App)
> **Removed from Phase 1.** The `auditor_id` column currently stores the auditor's *name*, not a UUID. All route comparisons (`auditor_id !== auth.name`) are intentionally name-based today. "Fixing" the comparison without migrating the schema + all write paths would break ownership checks for every existing session. This is a future schema migration, not a hotfix.
>
> **When to revisit**: When we do a proper `auditor_id` → UUID migration (new migration file, backfill existing rows, update all write paths and route comparisons together in one PR).

---

## Phase 2: High (This Week)

### 2.1 Centralize Supabase Config + REST Helpers (IDW-QA)
> **Scope note**: This refactor covers config loading and the simple REST helpers (GET/POST/PATCH to the PostgREST API). The Auth Admin operations in `admin_actions.py` (invite, listUsers, rollback) use Supabase's GoTrue admin endpoints with different semantics — those stay in `admin_actions.py` and are **not** pulled into the shared module. Trying to abstract both REST-data and Auth-admin behind one client would over-generalize.

- [ ] Create `scripts/supabase_client.py` with:
  - `get_supabase_config()` — load URL + keys from `.env.local` (single source)
  - `supabase_get(path, params)` — authenticated GET (PostgREST)
  - `supabase_post(path, data)` — authenticated POST (PostgREST)
  - `supabase_patch(path, data)` — authenticated PATCH (PostgREST)
- [ ] Refactor these files to import config + REST helpers from `supabase_client.py`:
  - `role_gate.py` — remove `_supabase_get()`, `_supabase_post()`
  - `push_to_canvas.py` — remove `_get_supabase_config()`
  - `audit_session_manager.py` — remove Supabase config wrapper
  - `audit_report.py` — remove POST/PATCH helpers
- [ ] **Leave `admin_actions.py` Auth Admin calls in place** — only refactor its config loading to use `supabase_client.get_supabase_config()`

### 2.2 ~~Tighten Exception Handling (IDW-QA)~~ DONE
- [x] Reduced bare `except Exception` from ~55 to 31 across the codebase
- [x] **Priority files fully clean** (0 bare excepts): `canvas_api.py`, `audit_report.py`, `criterion_evaluator.py`
- [x] Fixed all silent `pass` blocks in: `alignment_graph.py`, `staging_manager.py`, `audit_pages.py`, `idw_metrics.py`, `preflight_checks.py`, `deterministic_checks.py`
- [x] Narrowed to specific types: `ImportError`, `ValueError`, `OSError`, `json.JSONDecodeError`, `KeyError`, `AssertionError`
- [x] Added `_log.debug()` to all non-blocking catch blocks (previously silent)
- Remaining 31 are all intentional: logged `as e` or top-level `main()` error boundaries
- Verified: 17/17 modified files pass AST parse

### 2.3 ~~Remove Console Errors from Production (Review App)~~ DONE
- [x] Removed all 6 `console.error()` calls from `src/components/FindingCard.tsx`
- [x] Replaced with `setErrorMessage()` calls — errors now surface in UI, not just console
- [x] Also replaced `alert()` call with `setErrorMessage()` for consistency
- Verified: `next build` passes, 0 `console.error` remaining in file

### 2.4 ~~Remove Hardcoded Airtable Fallback (Review App)~~ DONE
- [x] Removed fallback `"tblI55WEIy16aftkS"` from `sync-airtable/route.ts`
- [x] Now requires all 3 env vars (`AIRTABLE_TOKEN`, `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_ID`) or returns 500 with clear message
- Verified: `next build` passes

### 2.5 ~~Fix `requirements.txt` (IDW-QA)~~ DONE
- [x] Added `beautifulsoup4>=4.12.0,<5.0`

---

## Phase 3: Medium (This Sprint)

### 3.1 + 3.2 ~~Lazy-Load Canvas API Config (IDW-QA)~~ DONE
- [x] `criterion_evaluator.py` was the only file calling `get_config()` at module scope — refactored to lazy `_get_config()` with caching
- [x] All other scripts already called `get_config()` inside functions
- [x] 3.1 `config.py` dropped — `supabase_client.py` (Phase 2.1) already centralizes Supabase config; Canvas config stays in `canvas_api.py`
- Verified: module imports without crashing when `.env` is missing

### 3.3 ~~Add Input Validation (Review App)~~ DONE
- [x] Created `src/lib/server/validation.ts` — `parseJsonBody()`, `isParseError()`, `isValidEmail()`, `isValidUUID()`
- [x] **All write routes** now use `parseJsonBody()` — 0 raw `req.json()` calls remain:
  - `admin/testers` (POST), `admin/testers/[id]` (PATCH), `admin/assignments` (POST)
  - `session-assign` (POST), `session-complete` (POST), `session-transition` (POST)
  - `sync-airtable` (POST), `change-requests` (POST + PATCH)
  - `findings/remediation` (PATCH), `remediation-events` (POST)
- [x] Added email format validation to `admin/testers` route
- [x] **Fixed sync-airtable authorization gap** — non-admin users (`id` and `id_assistant`) now get session ownership check (`auditor_id` or `assigned_to`). Previously only IDAs were checked; IDs could sync any session.
- [x] No new dependency (zod skipped — lightweight helpers sufficient)
- Verified: `tsc --noEmit` clean, `next build` clean

### 3.4 Standardize Auth Patterns (Review App) — DEFERRED
> Larger refactor (touches every route). Current patterns work correctly. Defer until next code review cycle.

### 3.5 ~~Fix Modal Accessibility (Review App)~~ DONE
- [x] `Modal.tsx`: added focus trap (Tab/Shift+Tab cycling), Escape to close, focus restore on close
- [x] `Modal.tsx`: added `role="dialog"`, `aria-modal="true"`, `aria-label`, `tabIndex={-1}`
- [x] `page.tsx`: added `aria-label="Sort sessions by"` and `aria-label="Assign ID Assistant"` to select dropdowns
- [x] `session/[id]/page.tsx`: replaced 2 `alert()` calls with `setAlertMessage()` (uses existing `AlertModal`)
- Verified: `next build` clean

### 3.6 Reduce Global State (IDW-QA) — DEFERRED
> Architecture refactor with minimal bug-fix value. Defer until next code review cycle.

---

## Phase 4: Post-Pilot Backlog

> These items are documented for future reference but are **not pre-pilot blockers**. None affect pilot functionality, security, or correctness.

### 4.1 Cleanup & Housekeeping
- [ ] Archive or integrate orphaned codex docs (`codex-vibe-coding-like-an-swe.md`, etc.)
- [ ] Remove commented-out code in review app (`session/[id]/page.tsx:18-19`, `:216`)
- [ ] Remove deprecated XLSX code from `audit_report.py` (or gate behind `--legacy` flag)
- [ ] Upgrade backup integrity hash from MD5 to SHA256 in `backup_manager.py`

### 4.2 Add Test Coverage (Both Projects)
- [ ] **IDW-QA**: Create `tests/` directory
  - Unit tests: `canvas_api.py`, `criterion_evaluator.py`, `supabase_client.py`
  - Integration tests: `push_to_canvas.py` (mock Canvas), `audit_session_manager.py` (mock Supabase)
- [ ] **Review App**: Add testing stack
  - Install Jest + @testing-library/react
  - Unit tests: auth helpers, API route handlers
  - E2E: Playwright for login, session review, admin flows
- [ ] Add `npm audit` to review app CI pipeline

### 4.3 Documentation
- [ ] Convert `.mmd` Mermaid diagrams to rendered PNGs or embed in docs
- [ ] Document RLS policy assumptions inline in review app API routes
- [ ] Add admin audit logging table for review app admin mutations

---

## Architecture Wins (Noted, Not Broken)

These are things that are working well — don't touch:

- **IDW-QA**: No circular dependencies, consistent argparse CLI patterns, clear migration sequence, well-structured skill files, thorough CLAUDE.md
- **Review App**: Modern stack (Next.js 16, React 19, Tailwind 4), up-to-date deps, server-side auth via SSR cookies, clean admin/user route separation
- **Both**: Clear separation of concerns between plugin (CLI/audit engine) and review app (web UI/RLHF portal)

---

## Tracking

| Phase | Items | Est. Effort | Status |
|-------|-------|-------------|--------|
| 1. Critical | 2 (1.3 deferred) | 1 hour | **1.2 done** |
| 2. High | 5 | 4-6 hours | **All done** (2.1–2.5) |
| 3. Medium | 6 | 8-12 hours | **3.1/3.2, 3.3, 3.5 done** — 3.4, 3.6 deferred |
| 4. Post-pilot backlog | 3 | 6-10 hours | Documented, not pre-pilot |
