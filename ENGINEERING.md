# IDW QA (SCOUT ULTRA) — Engineering Guide

> This document is for engineers who will maintain, debug, or extend the system.
> For user-facing setup, see `SETUP.md`. For plugin instructions, see `CLAUDE.md`.
> For implementation history and decisions, see `PLANNING.md`.

---

## 1. System Architecture

### Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| AI Engine | Claude Code (Claude Opus 4.6) | Runs audit skills, evaluates C-criteria, orchestrates workflows |
| Deterministic Engine | Python 3.9+ (`criterion_evaluator.py`) | Evaluates all B-criteria consistently |
| Backend / DB | Supabase (PostgreSQL + Auth + Storage) | Source of truth for sessions, findings, feedback, events |
| Frontend | Next.js 14 + Tailwind (Vercel) | Review app for verdicts, admin, change requests |
| Reporting | Python (`audit_report.py`) | HTML/XLSX reports with per-criterion detail |
| Analytics Output | Airtable | One row per course, faculty-facing, filterable by school/program |
| Course Data | Canvas LMS REST API | Read course structure, pages, assignments, quizzes |

### Data Flow

```
Canvas LMS ──→ criterion_evaluator.py ──→ audit_report.py ──→ Supabase
                (fetches pages,            (generates HTML,     (stores sessions,
                 evaluates B-criteria)      pushes findings)     findings, feedback)
                                                                      │
                                                                      ▼
                                                              Vercel Review App
                                                              (IDs verdict findings,
                                                               ID Assistants validate)
                                                                      │
                                                                      ▼
                                                                  Supabase
                                                              (stores verdicts)
                                                                      │
                                                                      ▼
                                                                  Airtable
                                                              (one row per course,
                                                               faculty reporting)
```

### Repository Structure

**Plugin repo** (`IDW-QA/`):
```
├── CLAUDE.md              # Plugin instructions (Claude reads this)
├── PLANNING.md            # Implementation history + decisions
├── ENGINEERING.md          # THIS FILE
├── TROUBLESHOOTING.md      # Common errors and fixes
├── SETUP.md               # User setup guide
├── config/
│   ├── standards.yaml     # 25 standards, 173 criteria (124 B + 49 C)
│   └── standards_enrichment.yaml  # AI evaluation context cards
├── scripts/               # 36 Python scripts
├── skills/                # 21 Claude Code skill definitions
├── migrations/            # 8 Supabase SQL migrations
├── templates/             # HTML/XLSX templates
├── standards/             # Reference docs (design, a11y, assessment)
└── reports/               # Generated audit reports (gitignored)
```

**Review app repo** (`idw-review-app/`):
```
├── src/app/
│   ├── page.tsx           # Sessions list (home page)
│   ├── session/[id]/      # Session detail + finding cards
│   ├── dashboard/         # RLHF feedback dashboard
│   ├── admin/             # Admin panel
│   ├── login/             # Auth
│   └── api/               # 6 server-side API routes
├── src/components/
│   ├── FindingCard.tsx     # Finding verdict card (700+ lines)
│   ├── StandardGroup.tsx   # Groups findings by standard
│   ├── Modal.tsx           # Alert + Confirm modals
│   └── AuthGuard.tsx       # Role-based auth wrapper
└── src/lib/
    ├── supabase.ts         # Supabase client + TypeScript types
    └── auth.ts             # Auth helpers
```

---

## 2. Database Schema

### Tables

**`audit_sessions`** — One row per audit run
```sql
id              UUID PRIMARY KEY
course_id       TEXT            -- Canvas course ID
course_name     TEXT
course_code     TEXT
term            TEXT
auditor_id      TEXT            -- Who ran the audit
run_date        TIMESTAMPTZ
overall_score   INTEGER         -- 0-100
standards_score INTEGER         -- Readiness (Col B) score
qa_score        INTEGER         -- Design (Col C) score or legacy QA score
a11y_score      INTEGER         -- Accessibility score (Standards 22-23)
readiness_score INTEGER
report_html_url TEXT            -- Supabase storage URL
audit_purpose   TEXT            -- 'self_audit' | 'recurring' | 'qa_review'
audit_round     INTEGER         -- Increment on re-audits
status          TEXT            -- 'in_progress' | 'complete' | 'pending_qa_review' | 'revisions_required' | 'qa_approved'
assigned_to     UUID            -- Which ID Assistant reviews this session
submitted_by    UUID
plugin_version  TEXT
airtable_synced_at TIMESTAMPTZ  -- NULL = not yet synced
```

**`audit_findings`** — One row per criterion evaluated
```sql
id                  UUID PRIMARY KEY
session_id          UUID → audit_sessions
finding_type        TEXT            -- 'design' | 'accessibility' | 'readiness'
standard_id         TEXT            -- '01' through '25'
criterion_id        TEXT            -- 'B-04.1', 'C-01.3', etc.
page_title          TEXT            -- Standard name (for grouping in review app)
ai_verdict          TEXT            -- 'met' | 'not_met' | 'partially_met' | 'n/a'
ai_reasoning        TEXT            -- Criterion question text
content_excerpt     TEXT            -- Actual evidence (page names, element details)
confidence_tier     TEXT            -- 'high' | 'medium' | 'low'
reviewer_tier       TEXT            -- 'id_assistant' (Col B) | 'id' (Col C)
canvas_link         TEXT            -- Direct URL to Canvas page
remediation_requested BOOLEAN      -- TRUE = in fix queue
```

**`finding_feedback`** — Human verdicts on findings (multiple rows per finding = history)
```sql
id                UUID PRIMARY KEY
finding_id        UUID → audit_findings
reviewer_name     TEXT
reviewer_tier     TEXT            -- 'id_assistant' | 'id' | 'admin'
decision          TEXT            -- 'correct' | 'incorrect' | 'not_applicable'
corrected_finding TEXT            -- If incorrect, what's the right answer
correction_note   TEXT            -- Why the AI was wrong
reviewed_at       TIMESTAMPTZ
original_decision TEXT            -- Set when admin overrides
overridden_by     UUID
override_reason   TEXT
```

**`remediation_events`** — What was fixed, when, how
```sql
id              UUID PRIMARY KEY
finding_id      UUID → audit_findings
remediated_by   UUID → testers
skill_used      TEXT            -- 'bulk-edit', 'quiz', 'manual', etc.
description     TEXT            -- 'Added alt text to 96 images'
created_at      TIMESTAMPTZ
```

**`testers`** — All system users
```sql
id          UUID PRIMARY KEY
name        TEXT
email       TEXT UNIQUE
role        TEXT            -- 'id' | 'id_assistant' | 'admin'
is_active   BOOLEAN
```

**`tester_course_assignments`** — ID Assistants assigned to courses
```sql
id          UUID PRIMARY KEY
tester_id   UUID → testers
course_id   TEXT
course_name TEXT
assigned_by UUID → testers
status      TEXT            -- 'assigned' | 'in_progress' | 'completed'
```

**`error_reports`** — Bug reports from users
```sql
id          UUID PRIMARY KEY
reported_by UUID → testers
error_type  TEXT            -- 'bug' | 'wrong_finding' | 'crash' | 'other'
description TEXT
context     JSONB
status      TEXT            -- 'open' | 'acknowledged' | 'resolved'
```

**`change_requests`** — Post-sync edit requests from ID Assistants
```sql
id              UUID PRIMARY KEY
session_id      UUID → audit_sessions
finding_id      UUID → audit_findings
requested_by    UUID → testers
reason          TEXT
status          TEXT        -- 'pending' | 'resolved' | 'dismissed'
resolution_note TEXT
```

### Key Relationships
```
audit_sessions  1 ──→ N  audit_findings
audit_findings  1 ──→ N  finding_feedback  (history preserved, latest wins)
audit_findings  1 ──→ N  remediation_events
audit_sessions  N ──→ 1  testers (assigned_to)
```

### RLS Policies
- `testers`, `tester_course_assignments`, `error_reports`: service_role full access
- `audit_findings`: anon can SELECT + UPDATE (for remediation_requested toggle)
- `remediation_events`: service_role full, anon SELECT
- `change_requests`: service_role full, anon SELECT + INSERT

---

## 3. Vercel API Routes

### Auth Layer

All routes authenticate callers server-side via shared helpers in `src/lib/server/`:

- **`route-auth.ts`** — SSR cookie auth using `@supabase/ssr` `createServerClient`. Reads auth from request cookies (set by `createBrowserClient` in `src/lib/supabase.ts`). Looks up the tester record by email from the `testers` table.
  - `getAuthUser(req)` → returns `ServerAuthUser | null`
  - `requireSignedInUser(req)` → returns auth or 401
  - `requireRole(req, roles[])` → returns auth or 401/403
  - `requireAdminUser(req)` → shorthand for `requireRole(req, ["admin"])`
  - `isAuthError(result)` → type guard for NextResponse

- **`supabase-admin.ts`** — `getServiceSupabase()` returns a service-role client for DB writes. Server-only, never exposed to client.

Actor fields (`requested_by`, `resolved_by`, `remediated_by`, `submitted_by`, `assigned_by`) are derived from the authenticated tester server-side. Browser payloads for these fields are ignored.

### Route Reference

| Route | Method | Required Role | Purpose |
|---|---|---|---|
| `/api/admin/testers` | POST | admin | Create tester |
| `/api/admin/testers/[id]` | PATCH, DELETE | admin | Update/delete tester |
| `/api/admin/assignments` | POST | admin | Create course assignments |
| `/api/admin/assignments/[id]` | DELETE | admin | Remove assignment |
| `/api/admin/errors/[id]` | PATCH | admin | Resolve error report |
| `/api/session-assign` | GET, POST | admin | List IDAs / assign to session |
| `/api/change-requests` | GET | admin (global) or any auth (with session_id) | List change requests |
| `/api/change-requests` | POST | admin or id_assistant | Create change request |
| `/api/change-requests` | PATCH | admin | Resolve change request |
| `/api/sync-airtable` | POST | any auth (IDA: assigned + complete) | Sync findings to Airtable |
| `/api/findings/remediation` | PATCH | id or admin | Toggle `remediation_requested` |
| `/api/remediation-events` | GET | any auth | Fetch remediation events |
| `/api/remediation-events` | POST | id or admin | Record remediation event |
| `/api/session-complete` | POST | id only | Mark session complete, auto-approve Col C |

### Sync-Airtable Route Details
- Uses **hardcoded** rating + notes field name maps (no schema discovery)
- Discovers criterion column names from existing Airtable records
- Searches by `{Course Name}` formula to find/update existing row
- Generates standard-level notes from failing criteria evidence

---

## 4. Python Scripts Reference

### Core Audit Pipeline

**`criterion_evaluator.py`** — Deterministic B-criteria evaluation
```
--quick-check    Col B only, produces complete audit JSON
--full-audit     Col B evaluated + Col C marked needs_ai_review
--json           Raw criterion-level results
--summary        Standard-level counts
```
Key functions:
- `collect_course_data()` → fetches all Canvas data, parses HTML, computes aggregates
- `evaluate_b_criterion(cid, text, cd)` → keyword matching against course data, returns (status, evidence)
- `build_full_audit_json(cd, results, mode)` → assembles complete audit_report.py-compatible JSON
- `LOW_CONFIDENCE` set → 22 criterion IDs where evaluator gives defaults

**`audit_report.py`** — Report generation + Supabase push
```
--input FILE     Generate from saved JSON
--local-only     HTML only, no Supabase push
--demo           Sample data
--xlsx           Generate Excel report
--open           Open in browser after generation
```
Key functions:
- `generate_report(data)` → returns full HTML string (2000+ lines of f-string)
- `push_to_rlhf(data, html_path, xlsx_path)` → creates session + pushes findings to Supabase
- `_render_criteria_results(criteria)` → expandable per-criterion table in HTML
- `_build_remediation_html(sections, score)` → remediation roadmap section

**`airtable_sync.py`** — Supabase → Airtable sync
```
--session-id UUID    Sync one session
--course-id ID       Sync latest for a course
--pending            Sync all approved but unsynced
--dry-run            Preview without writing
```
Key functions:
- `build_airtable_row(session, findings, crit_map, ...)` → dict of Airtable field values
- `_generate_notes(findings, feedback_map)` → human-readable notes from failing criteria
- `_at_get_field_map(token, base_id)` → discovers column names from schema API

### Canvas Integration

**`canvas_api.py`** — Shared Canvas LMS API utilities (29 functions)
- `get_course(course_id)`, `get_pages()`, `get_page_body(slug)`
- `update_page(slug, body)`, `create_assignment(data)`
- `paginated_get(url)` → handles Canvas pagination
- All functions read `CANVAS_TOKEN` + `CANVAS_DOMAIN` from `.env`

**`push_to_canvas.py`** — Atomic push with backup + verification
```
--type page|assignment|quiz|discussion
--slug SLUG or --id ID
--html-file FILE
--finding-ids IDs     Record remediation events after push
--skill SKILL         Which skill performed the fix
```
Flow: backup → push → clear staging → verify → record remediation events

### Role & Auth

**`role_gate.py`** — Tester identity + role checking
```
--check ROLE     Exit 0 if authorized, 1 if not (admin|id|id_assistant|any)
--whoami         Print current tester info
--register       Create new tester (admin only)
```

### RLHF & Analytics

**`rlhf_analysis.py`** — Agreement rate analysis
```
--summary        Overall stats
--by-standard    Per-standard rates
--by-reviewer    Per-reviewer stats
--trends         Weekly trend
--corrections    List all incorrect findings with corrections
```

---

## 5. Review App Components

### FindingCard.tsx (700+ lines)
The most complex component. Handles 5 states:
1. **Unreviewed** — shows Correct/Incorrect/N/A buttons
2. **Reviewed** — shows verdict badge + Undo button
3. **Remediated** — shows "Remediated via /skill" + Agree/Disagree (ID Assistant)
4. **Locked** — after Airtable sync, view-only + Request Change button
5. **Admin review** — shows Agree/Disagree for admin overrides

Key props:
- `finding: AuditFinding` — the finding data
- `existingFeedback: FindingFeedback | null` — filtered by reviewer_tier for IDA
- `isRemediated: boolean` — has remediation_events
- `isAdminReview: boolean` — admin mode OR locked IDA mode
- `reviewerTier: "id_assistant" | "id"` — controls which buttons show

### StandardGroup.tsx
Groups FindingCards under a standard header. Shows:
- Standard ID, name, rating badge, met count
- Col B section ("Readiness Checks") + Col C section ("Design Checks")
- Collapsed by default if all Met, expanded if issues

### Session Page (`session/[id]/page.tsx`)
- Loads session + findings + feedback + remediation events + change requests
- Filters: status (All/Unreviewed/Reviewed/Correct/Incorrect/N/A), category (Design/Readiness/A11y), confidence (All/High/Medium/Low)
- Role-aware: IDA sees Col B only, no Design filter, no Needs Remediation checkbox
- Locked after Airtable sync for IDA

### Home Page (`page.tsx`)
- Admin: Needs Attention / All Sessions toggle
- Sort: Newest/Oldest/Course A-Z/Score
- Session cards: course name, scores, status badge, purpose badge, assign dropdown
- Change Requests queue (admin only, grouped by course)

---

## 6. Audit Flow (End-to-End)

### Quick Check (Col B only)
```
1. User runs /audit → picks Quick Check
2. Claude runs: python3 scripts/criterion_evaluator.py --quick-check > audit_results.json
3. Evaluator fetches ALL Canvas data (pages, quizzes, assignments, tabs, syllabus)
4. Evaluates 124 B-criteria deterministically (HTML parsing, keyword matching)
5. Builds complete audit JSON with scores, QA categories, a11y, readiness
6. Claude shows summary → asks: Just show results / Local report / Submit for review
7. If submit: python3 scripts/audit_report.py --input audit_results.json --open
8. audit_report.py generates HTML + pushes session + findings to Supabase
9. Session appears in Vercel review app with status: in_progress
```

### Deep Audit (Col B + C)
```
Steps 1-5 same as Quick Check but uses --full-audit
6. Claude reads JSON, evaluates 49 C-criteria using enrichment cards
7. Updates JSON with C-criteria verdicts
8. Same report prompt → submit to Supabase
```

### Review + Sync
```
1. ID reviews findings in Vercel → Correct/Incorrect/N/A
2. ID marks session Complete → Col C auto-approved, Col B → pending_qa_review
3. Admin assigns ID Assistant to session
4. ID Assistant validates Col B findings → Correct/Incorrect/N/A
5. ID Assistant marks Complete → syncs to Airtable
6. Session locked for ID Assistant (view-only + Request Change)
```

---

## 7. Configuration

### Environment Variables

**Plugin `.env`:**
```
CANVAS_TOKEN=<personal access token>
CANVAS_DOMAIN=canvas.asu.edu
CANVAS_COURSE_ID=<numeric>
CANVAS_ACTIVE_INSTANCE=prod
CANVAS_READ_ONLY=false
IDW_TESTER_ID=<UUID from testers table>
```

**Plugin `.env.local`:**
```
SUPABASE_URL=<project URL>
SUPABASE_ANON_KEY=<publishable key>
SUPABASE_SERVICE_KEY=<secret key>
AIRTABLE_TOKEN=<personal access token>
AIRTABLE_BASE_ID=<base ID>
AIRTABLE_TABLE_ID=<table ID>
```

**Vercel env vars:**
```
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
SUPABASE_SERVICE_KEY
AIRTABLE_TOKEN
AIRTABLE_BASE_ID
```

### Standards Configuration

`config/standards.yaml` — 26 entries (25 standards + CRC), 173 criteria total
- `B-XX.Y` criteria → `reviewer_tier: id_assistant` → deterministic evaluation
- `C-XX.Y` criteria → `reviewer_tier: id` → AI evaluation with enrichment cards
- `excluded: true` → Standard 23 (Tool Accessibility) skipped by evaluator
- Low confidence set: 22 B-criteria where evaluator gives default answers

`config/standards_enrichment.yaml` — AI context for C-criteria evaluation
- `measurable_criteria`, `expectations`, `considerations`, `examples`, `research`
- Loaded by Claude during Deep Audit for each standard

---

## 8. Key Design Decisions

| Decision | Rationale |
|---|---|
| Python evaluator for B-criteria | LLM variability unacceptable for existence checks. Same course must = same results. |
| Vercel + Airtable (dual approach) | Vercel for workflow (interactive cards), Airtable for reporting (filterable by school/program). Neither is redundant. |
| One row per course in Airtable | Faculty sees latest state. History in Supabase. |
| Hardcoded Airtable field maps | Schema API discovery was unreliable on Vercel (env vars, timing). Hardcoded maps always work. |
| `--local-only` flag | IDs iterate many times during course dev. Report generation + Supabase push wasteful for each iteration. |
| Staging mandatory for ALL HTML | Prevents accidental Canvas pushes. Stage → preview → approve → push. No exceptions. |
| Split scores (Readiness/Design/A11y) | Quick Check only evaluates Col B. Showing a single "overall" score misleads when design isn't evaluated. |
| ID Assistant sees Col B only | Student workers validate readiness checks. Design quality requires ID expertise. |
| Decision history preserved | Every `finding_feedback` row kept (never deleted). Enables RLHF analysis + IDA accuracy tracking. |

---

## 9. Common Patterns

### Adding a New Criterion
1. Add to `config/standards.yaml` with `B-XX.Y` or `C-XX.Y` ID
2. If B-criterion: add evaluation logic in `criterion_evaluator.py` → `evaluate_b_criterion()`
3. If low confidence: add ID to `LOW_CONFIDENCE` set in evaluator
4. Airtable column must be created manually (table has 207 fields)
5. Run audit to verify

### Adding a New Skill
1. Create `skills/{name}/SKILL.md`
2. Add to CLAUDE.md skills table
3. Include metric tracking: `python3 scripts/idw_metrics.py --track skill_invoked`
4. Include role gate if needed: `python3 scripts/role_gate.py --check <role>`
5. If it modifies Canvas HTML: must reference staging workflow
6. If it fixes audit findings: must call `remediation_tracker.py --record`

### Adding a New API Route
1. Create `src/app/api/{name}/route.ts`
2. Use `getSupabase()` pattern (lazy init — never module-level `createClient`)
3. Add to CLAUDE.md API routes table
4. Add env vars to Vercel dashboard
5. Build test: `npx next build`

---

## 10. Deprecated & Legacy Code

**`deterministic_checks.py`** — Deprecated in place. Superseded by `criterion_evaluator.py` for all audit operations. File kept for reference and backward compatibility (still referenced in some docs). Do not call directly for new audits.

**`preflight.py` bug (fixed):** `CANVAS_ACTIVE_INSTANCE` was reset inside the `.env` parsing loop — only retained if it happened to be the last line. Fixed by moving `active = ""` outside the loop.

**`metrics_sync.py` credential source (fixed):** Was only reading `.env` (Canvas creds), missing `.env.local` (Supabase creds). Fixed to use `python-dotenv` loading both files, consistent with all other scripts.

## 11. Post-Pilot Cleanup Plan

See PLANNING.md for the full 7-step plan. Summary order:
1. **Test harness** — golden fixtures before any refactoring
2. **Config/env consistency** — shared config paths
3. **Centralize Supabase access** — one client layer
4. **Make mandatory scripts mandatory** — push_to_canvas.py drift
5. **Normalize audit/session semantics** — one source of truth
6. **Define public vs legacy** — retire orphaned scripts
7. **Refactor monoliths last** — `audit_report.py` always last
