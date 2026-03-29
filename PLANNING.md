# IDW QA — Pilot Implementation Plan

> This document is the single source of truth for building the IDW QA pilot system.
> Read this FIRST when resuming work after a conversation compaction or new session.
> Last updated: 2026-03-28

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Roles and Permissions](#2-roles-and-permissions)
3. [Workflows](#3-workflows)
4. [Reviewer Tier Mapping](#4-reviewer-tier-mapping)
5. [Data Model — Supabase Schema](#5-data-model--supabase-schema)
6. [Vercel App — Views and Features](#6-vercel-app--views-and-features)
7. [Audit Skill Updates](#7-audit-skill-updates)
8. [RLHF Feedback Loop](#8-rlhf-feedback-loop)
9. [Airtable Integration](#9-airtable-integration)
10. [Auth](#10-auth)
11. [Known Bugs](#11-known-bugs)
12. [Implementation Phases](#12-implementation-phases)
13. [Pilot Scope](#13-pilot-scope)
14. [Notifications](#14-notifications)
15. [Plugin Version Tracking](#15-plugin-version-tracking)
16. [Concurrency Rules](#16-concurrency-rules)
17. [Unresolved Questions](#17-unresolved-questions)
18. [Reference Files](#18-reference-files)

---

## 1. System Overview

Four components, three audiences:

| Component | Who uses it | Purpose |
|---|---|---|
| **Claude Code** (IDW QA plugin) | IDs, QA team | Run audits, remediate courses, stage/push content |
| **Vercel App** (idw-review-app) | IDs, IDAs, QA team, Admins | Review findings, verdict, track sessions, launch gate |
| **Supabase** | Backend (no direct user access) | Source of truth for all audit data, auth, RLHF |
| **Airtable** | QA team, IDs (read-only) | Reporting/archive layer, synced from Supabase |

### Data flow

```
Claude Code runs audit
    → findings → Supabase (immediately)
    → users review in Vercel app
    → every verdict click → Supabase (immediately, enables resume)
    → session complete (all findings verdicted) → batch sync to Airtable
    → nightly job catches incomplete sessions
```

Supabase is ALWAYS the source of truth. Airtable is a downstream read-only sync.

---

## 2. Roles and Permissions

| Role | Claude Code | Vercel App | What they do |
|---|---|---|---|
| **ID** (course builder) | Yes (own token) | Yes | Self-audit during course dev, remediate, submit for QA review |
| **IDA** (ID Assistant) | TBD (see [Q1](#17-unresolved-questions)) | Yes | Verdict Col B findings only, assigned specific courses |
| **Admin** (QA team + admins) | Yes (QA token) | Yes (/admin route) | Run recurring audits, review all findings (Col B + C), approve launch gate, manage testers, error queue, RLHF review |

**Note**: The `qa_team` role was merged into `admin` — there are now 3 roles, not 4. All QA team members are admins.

### Key role rules
- IDs can audit ANY course (use Canvas API to list their courses)
- IDAs are ASSIGNED courses via `tester_course_assignments` table
- IDAs are CS masters students, semester-long tenure, may not have ASU email on day one
- QA team = IDs who exclusively do QA work (not course building)
- Admin = QA team members with admin flag in testers table

---

## 3. Workflows

### Workflow A — New Course Development (launch-gated)

```
1. ID builds course
2. ID runs self-audit via Claude Code
   - audit_purpose = 'self_audit'
   - All 25 standards checked (deterministic + AI)
   - reviewer_tier assigned per finding
   - Evidence captured (content_excerpt + canvas_link)
3. Findings → Supabase
4. ID reviews findings in Vercel app
5. ID remediates via Claude Code (stage → preview → push)
6. Repeat 2-5 until satisfied
7. ID clicks "Submit for QA Review" in Vercel app
   - audit_sessions.status = 'pending_qa_review'
8. QA team sees course in "Pending Review" queue
9. QA team assigns IDAs to session
10. IDAs verdict Col B findings (agree/disagree/not_an_issue/N/A)
    - If disagree → corrected_finding text required
11. QA team IDs verdict ALL findings (Col B + Col C)
    - Can override IDA verdicts
12. Decision:
    - If revisions needed → status = 'revisions_required', audit_round++
      - ID sees feedback in Vercel app, goes back to step 2
    - If approved → launch_gate_approved = true, course launches
```

### Workflow C — Recurring Course Audit (NOT launch-gated)

```
1. QA team triggers audit via Claude Code (QA team's Canvas token)
   - audit_purpose = 'recurring'
2. Findings → Supabase
3. QA team assigns IDAs
4. IDAs verdict Col B findings in Vercel app
5. QA team IDs verdict ALL findings
6. Session complete → Airtable sync
7. Remediation is PASSIVE:
   - Findings visible in Airtable
   - Faculty/IDs fix if they have time
   - No gate, no required action
```

### Remediation rules
- **Active remediation** = new course dev only (launch-gated, required)
- **Passive remediation** = recurring audits (Airtable visible, optional)
- **All page HTML changes** go through staging (stage → screenshot → approve → push)
- **Metadata changes** (rename, due dates, attempts) = quick edits via API, no staging

---

## 4. Reviewer Tier Mapping

Source document: `/Users/bespined/Downloads/[QA + AI] Experience Stage_Review Item Lists.xlsx`

### Tier definitions

| Tier | Column | Count | Content type | Who sees | Who verdicts |
|---|---|---|---|---|---|
| `id_assistant` | Col B | 107 checks | Deterministic/existence | IDAs + IDs | IDAs first, IDs override |
| `id` | Col C | 42 checks | Qualitative/judgment | IDs only | QA team IDs only |

### How tiers map to standards.yaml

The existing `standards.yaml` already has `check_type` per criterion:
- `check_type: "deterministic"` → `reviewer_tier: "id_assistant"` (Col B)
- `check_type: "ai"` → `reviewer_tier: "id"` (Col C)
- `check_type: "hybrid"` → needs mapping: if the deterministic part is Col B, set `reviewer_tier: "id_assistant"` for the deterministic finding and `reviewer_tier: "id"` for the qualitative finding

### Standards breakdown (Col B / Col C check counts)

```
Standard 01 (Course-Level Alignment)*:      3B / 3C
Standard 02 (Module-Level Alignment)*:      2B / 2C
Standard 03 (Alignment Made Clear):         0B / 2C
Standard 04 (Consistent Layout):           46B / 1C
Standard 05 (Engaging Introductions):       0B / 0C
Standard 06 (Clear Workload)*:              5B / 5C
Standard 07 (Instructor Guide):             1B / 2C
Standard 08 (Assessments Align)*:           1B / 1C
Standard 09 (Clear Grading Criteria):       8B / 0C
Standard 10 (Varied Assessments):           2B / 2C
Standard 11 (Cognitive Skills):             0B / 2C
Standard 12 (Materials Align)*:             0B / 1C
Standard 13 (High-Quality Content):        14B / 2C
Standard 14 (Real-World Relevance):         0B / 0C
Standard 15 (Universally Designed Content): 0B / 1C
Standard 16 (Universally Designed Media):   1B / 1C
Standard 17 (Open Space for Questions):     4B / 1C
Standard 18 (Instructor-Created Media):     2B / 4C
Standard 19 (Active Learning):              0B / 5C
Standard 20 (Tool Integration):             4B / 3C
Standard 21 (Technical/Academic Support):   0B / 1C
Standard 22 (Material Accessibility)*:     11B / 1C
Standard 23 (Tool Accessibility)*:           0B / 0C
Standard 24 (Mobile/Offline):               1B / 0C
Standard 25 (Low-Cost Resources):           1B / 1C
                                    TOTAL: 106B / 42C
```

`*` = essential standard

### Action required
- Add `reviewer_tier` field to each criterion in `standards.yaml`
- Map each Col B item from the spreadsheet to a criterion_id
- Map each Col C item to a criterion_id
- For standards with 0B/0C (05, 14): no automated checks exist yet — determine if these are audit-time manual checks or not applicable
- Standard 23 (Tool Accessibility) is ESSENTIAL but has 0B/0C — needs checks added or explicit handling as a manual-only standard

---

## 5. Data Model — Supabase Schema

### Existing tables (need updates)

#### `audit_sessions`
```sql
-- EXISTING fields (keep as-is)
id, course_id, course_name, canvas_domain, created_at, updated_at

-- NEW fields to add
audit_purpose      TEXT NOT NULL DEFAULT 'self_audit'
                   -- 'self_audit' | 'qa_review' | 'recurring'
audit_round        INTEGER DEFAULT 1
                   -- increments when ID resubmits after revisions
previous_session_id UUID REFERENCES audit_sessions(id)
                   -- links to prior session in review chain
status             TEXT NOT NULL DEFAULT 'in_progress'
                   -- 'in_progress' | 'complete' | 'pending_qa_review'
                   -- | 'revisions_required' | 'qa_approved'
submitted_by       UUID REFERENCES testers(id)
                   -- who ran the audit
assigned_to        UUID[] -- array of IDA UUIDs assigned to review
launch_gate_approved BOOLEAN DEFAULT false
launch_gate_approved_by UUID REFERENCES testers(id)
launch_gate_approved_at TIMESTAMPTZ
airtable_synced_at TIMESTAMPTZ -- last sync timestamp
plugin_version     TEXT
                   -- semver or git hash of audit skill that generated findings
                   -- enables RLHF correlation with prompt/config changes
```

#### `audit_findings`
```sql
-- EXISTING fields (keep as-is)
id, session_id, standard_id, criterion_id, finding_text,
severity, created_at

-- NEW fields to add
reviewer_tier      TEXT NOT NULL DEFAULT 'id'
                   -- 'id_assistant' | 'id'
content_excerpt    TEXT
                   -- the actual text/HTML Claude flagged
canvas_link        TEXT
                   -- direct URL to the page/item in Canvas
page_slug          TEXT
                   -- Canvas page slug for reference
module_id          INTEGER
                   -- Canvas module ID
remediation_requested BOOLEAN DEFAULT false
                   -- set when fix queue item is created
```

#### `finding_feedback`
```sql
-- EXISTING fields (update decision enum)
id, finding_id, session_id, created_at

-- UPDATED fields
decision           TEXT NOT NULL
                   -- 'agree' | 'disagree' | 'not_an_issue' | 'not_applicable'
                   -- (was: 'approved' | 'rejected' | 'false_positive')

-- NEW fields
reviewer_id        UUID REFERENCES testers(id)
                   -- who submitted this verdict
corrected_finding  TEXT
                   -- what the reviewer says is actually true (required if disagree)
correction_note    TEXT
                   -- why the AI was wrong (optional)
reviewer_tier      TEXT
                   -- 'id_assistant' | 'id' — who submitted
original_decision  TEXT
                   -- the IDA's original verdict before ID override
                   -- 'agree' | 'disagree' | 'not_an_issue' | 'not_applicable'
                   -- NULL if not overridden
overridden_by      UUID REFERENCES testers(id)
                   -- if QA team ID overrides IDA verdict
overridden_at      TIMESTAMPTZ
override_reason    TEXT
```

### New tables

#### `testers`
```sql
CREATE TABLE testers (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,
  email           TEXT UNIQUE,          -- may be null for new hires without ASU email
  role            TEXT NOT NULL,        -- 'id' | 'id_assistant' | 'qa_team' | 'admin'
  password_hash   TEXT,                 -- for pilot auth (Supabase Auth handles hashing)
  is_active       BOOLEAN DEFAULT true,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

-- RLS: anon key = SELECT only on own row (by UUID)
-- service key = full CRUD (admin operations)
```

#### `tester_course_assignments`
```sql
CREATE TABLE tester_course_assignments (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tester_id       UUID REFERENCES testers(id) NOT NULL,
  course_id       TEXT NOT NULL,        -- Canvas course ID
  course_name     TEXT,
  canvas_domain   TEXT,
  assigned_by     UUID REFERENCES testers(id),
  assigned_at     TIMESTAMPTZ DEFAULT now(),
  completed_at    TIMESTAMPTZ,          -- when IDA finishes review
  status          TEXT DEFAULT 'assigned'
                  -- 'assigned' | 'in_progress' | 'completed'
);

-- NOTE: IDAs only. IDs are not assigned — they can audit any course.
```

#### `error_reports`
```sql
CREATE TABLE error_reports (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reported_by     UUID REFERENCES testers(id),
  error_type      TEXT NOT NULL,        -- 'bug' | 'wrong_finding' | 'crash' | 'other'
  description     TEXT NOT NULL,
  context         JSONB,                -- session_id, finding_id, skill, etc.
  status          TEXT DEFAULT 'open',  -- 'open' | 'acknowledged' | 'resolved'
  resolved_by     UUID REFERENCES testers(id),
  resolved_at     TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT now()
);
```

### RLS Policies (pilot)

```sql
-- testers: anon can SELECT own row, service key has full access
-- audit_sessions: authenticated users can SELECT/INSERT/UPDATE own sessions
-- audit_findings: authenticated users can SELECT; INSERT only via service key (audit script)
-- finding_feedback: authenticated users can INSERT own verdicts, SELECT all
-- tester_course_assignments: IDAs SELECT own rows; admins full CRUD
-- error_reports: authenticated INSERT; admin SELECT/UPDATE
```

---

## 6. Vercel App — Views and Features

Location: `/Users/bespined/Desktop/idw-review-app/`

### Authentication (pilot)
- Email + password via Supabase Auth
- QA admin pre-creates accounts in testers table
- Login returns UUID + role → session cookie → role-based routing
- No ASU SSO for pilot (new hires don't have ASU email for weeks)

### IDA View
- **Sees**: Only findings where `reviewer_tier = 'id_assistant'` (Col B)
- **Queue**: Courses assigned to them via `tester_course_assignments`
- **Finding card shows**:
  - Standard name + criterion text
  - `content_excerpt` (the actual text/HTML AI flagged) displayed inline
  - `canvas_link` (clickable, opens Canvas page in new tab)
  - AI's finding text
  - Verdict buttons: **Agree** / **Disagree** / **Not an Issue** / **N/A**
  - If Disagree → text field for `corrected_finding` (required)
  - Optional `correction_note` field
- **Resume**: Opening an in-progress session loads from Supabase, shows remaining un-verdicted findings
- **Session status**: progress bar showing verdicted / total

### ID View
- **Sees**: ALL findings (Col B + Col C)
- **Queue**: "My Courses" — self-audit sessions + QA feedback on submitted courses
- **Submit for QA Review** button (when self-audit is complete)
- **QA Feedback**: when `status = 'revisions_required'`, shows QA team's notes and which findings need attention
- **Fix Queue**: findings where `remediation_requested = true`

### QA Team View
- **Sees**: ALL findings + IDA verdicts
- **Queue**: "Pending Review" — courses with `status = 'pending_qa_review'`
- **Assign IDAs**: select from active IDAs, assign to session
- **Override**: can change IDA verdicts with reason
- **Launch gate**: approve/reject button → sets `launch_gate_approved`
- **Recurring audits**: list of sessions with `audit_purpose = 'recurring'`

### Admin View (`/admin` route)
- **Password-gated** (env var `ADMIN_PASSWORD`)
- **Error queue**: list of `error_reports`, filterable by status/type
- **RLHF patterns**: aggregate disagreement rates by standard, criterion, reviewer
- **Tester management**: create/edit/deactivate testers
- **Course assignments**: assign IDAs to courses
- **Release notes**: view current plugin version, push updates

### Rename requirements (existing code)
- `FindingCard.tsx`: "Approved" → "Agree", "Rejected" → "Disagree", "False Positive" → "Not an Issue"
- Add "N/A" option
- `supabase.ts`: update TypeScript interfaces for new fields and decision enum

---

## 7. Audit Skill Updates

Location: `/Users/bespined/claude-plugins/IDW-QA/skills/audit/SKILL.md`

### Streamlined modes (replaces old 5-mode system)

Old modes 1-4 (Design Standards, Accessibility, CRC, Full) and proposed Mode 5 (IDAsst Deterministic) are consolidated into 3 modes with scope filters.

| Mode | Depth | Time | Who uses it |
|---|---|---|---|
| **Quick Check** | Pass 1 (deterministic) + light AI verification | ~1-2 min | QA team (recurring), IDs (pre-check) |
| **Deep Audit** | Pass 1 + Pass 2 (full AI evaluation per standard) | ~10-15 min | IDs (self-audit), QA team (launch gate) |
| **Guided Review** | Same as Deep Audit but interactive with live fixes | ~20-30 min | IDs during active course building |

**Quick Check light AI pass**: After deterministic checks, one LLM call reviews results + raw content from flagged pages. Catches false positives (empty pages with correct titles, placeholder CLOs, template text). Does NOT evaluate instructional quality.

### Scope filters (apply to any mode)

| Scope | What's included |
|---|---|
| `all` (default) | All 25 standards + 18 CRC items |
| `essential` | Only the 7 essential standards (01, 02, 06, 08, 12, 22, 23) |
| `crc` | Only the 18 CRC operational items not covered by standards |
| `essential,crc` | Both essential standards + CRC items |

### Unified check registry

All checks (standards + WCAG + CRC) run from one registry. Each check is tagged with:
- `standard_id`: which of the 25 standards (or `crc` for operational items)
- `criterion_id`: specific criterion (e.g., "01.1", "crc.04")
- `reviewer_tier`: `id_assistant` (Col B) or `id` (Col C)
- `check_type`: `deterministic`, `ai`, or `hybrid`
- `essential`: true/false
- `category`: `design_standard` | `wcag` | `crc`

WCAG checks (heading hierarchy, alt text, contrast, link text, captions) are absorbed into their parent standards (primarily 22, 23) rather than being a separate mode. CRC items that don't map to any standard get `standard_id: 'crc'`.

### 18 CRC gap items (not covered by 25 standards)

These operational/template checks from the original Course Readiness Checklist have no matching design standard. They are tagged `category: 'crc'` and run as supplemental checks:

```
crc.01  Nav - Time in AZ link exists
crc.02  Course tour video exists
crc.03  Old RPNow info removed
crc.04  Course is complete (no missing weeks)
crc.05  Course design (holistic assessment)
crc.06  Ally accessibility score
crc.07  Academic integrity (assessment variety)
crc.08  Textbook info in syllabus
crc.09  Digital textbook option provided
crc.10  Syllabus grading policy/procedure
crc.11  Syllabus late work policy
crc.12  Virtual office hours listed
crc.13  Course type identification
crc.14  Source course detection
crc.15  All videos appear and play in student view
crc.16  Appropriate course material
crc.17  Placeholder text removed
crc.18  Overall course readiness (holistic)
```

Source: `[Auryan] IDAsst QA Tasks.xlsx` → "CRC Item Categorization" sheet, items where "Covered in Standards?" = No

### Changes to all modes
- Every finding MUST include:
  - `reviewer_tier`: from `standards.yaml` mapping
  - `content_excerpt`: the specific text/HTML that triggered the finding
  - `canvas_link`: full URL to the Canvas page/item
  - `criterion_id`: from `standards.yaml`
  - `category`: `design_standard` | `wcag` | `crc`
  - `essential`: whether the parent standard is essential
- `audit_report.py` must write these new fields to Supabase
- `auditor_id` must come from `IDW_TESTER_ID` in `.env` (not hardcoded "ID Workbench")

### Two-pass architecture (existing, keep)
- Pass 1: `deterministic_checks.py` (runs all hardcoded checks)
  - Uses `standards.yaml` for criterion_id and check_type
  - Binary checks: present/absent, measurable/unmeasurable
  - Includes WCAG checks (absorbed from old `audit_pages.py`)
  - Includes CRC operational checks
  - No enrichment context needed
- Pass 2: LLM reasoning (for `check_type: "ai"` and `check_type: "hybrid"`)
  - Uses `standards.yaml` for WHAT to check
  - Uses `standards_enrichment.yaml` for HOW to judge it
  - Enrichment provides per standard: measurable_criteria, expectations, considerations, examples, research citations
  - This is what enables qualitative Col C judgments (e.g., "is this CLO truly measurable?" vs just "does a CLO exist?")
- Quick Scan skips Pass 2 entirely

### Role of `standards_enrichment.yaml`
- Location: `config/standards_enrichment.yaml`
- Provides rich context cards for each of the 25 standards
- Each card contains: measurable_criteria, expectations, considerations, examples, research citations
- The LLM reads this during Pass 2 to make informed qualitative judgments
- Directly impacts Col C finding quality — if enrichment is vague, AI findings will be vague
- RLHF target: when IDs disagree with Col C findings, the root cause is often incomplete enrichment

### Guided Review flow (Mode 3 detail)
- Walks through 9 standard groups conversationally:
  - Group 1: Standards 01, 02, 03 (Alignment)
  - Group 2: Standards 04, 05 (Structure + introductions)
  - Group 3: Standards 06, 07 (Workload + instructor guide)
  - Group 4: Standards 08, 09, 10 (Assessment quality)
  - Group 5: Standards 11, 12, 13 (Cognitive skills + materials)
  - Group 6: Standards 14, 15, 16 (Relevance, UDL, media)
  - Group 7: Standards 17, 18, 19 (Community, instructor media, active learning)
  - Group 8: Standards 20, 21 (Tools + support)
  - Group 9: Standards 22, 23, 24, 25 + CRC items (Accessibility, cost, operational)
- After each group, pause: "Fix now?" / "Note and continue" / "Skip"
- Fixes applied immediately via staging workflow
- Report annotated with "Reviewed", "Fixed during review", "Accepted"

---

## 8. RLHF Feedback Loop

### Data collection (during pilot)
- Every verdict stored in `finding_feedback` with reviewer UUID and tier
- Disagreements include `corrected_finding` + `correction_note`
- Overrides tracked separately (`overridden_by`, `override_reason`)

### Analysis (admin dashboard)
- Disagreement rate by standard (which standards does the AI get wrong most?)
- Disagreement rate by criterion (which specific checks fail?)
- Disagreement rate by reviewer (is one reviewer an outlier?)
- Corrected findings clustered by type (what patterns does the AI miss?)
- **Enrichment card effectiveness**: which `standards_enrichment.yaml` cards have highest disagreement — those need richer examples/criteria
- **IDA quality tracking**: % of IDA verdicts NOT overridden by QA team IDs, per IDA, per standard, over time (query: `WHERE original_decision IS NOT NULL`)

### Improvement cycle
```
Admin reviews patterns on Vercel /admin dashboard
    → identifies problematic criteria or standards
    → diagnosis: is the issue in...
        a) skill prompts (AI misapplied the enrichment context)
        b) standards_enrichment.yaml (enrichment is vague/incomplete/wrong)
        c) standards.yaml (criterion itself is ambiguous)
        d) deterministic_checks.py (hardcoded check has a bug)
    → updates the appropriate file
    → runs /update-idw to distribute via git pull
    → next audit run uses improved prompts
```

### Target metric
- 85% agreement rate across all findings by end of pilot

---

## 9. Airtable Integration

### Sync mechanism
- **Trigger**: all findings in a session have a verdict (agree/disagree/not_an_issue/N/A)
- **Method**: Supabase webhook (pg_net or Edge Function) → Airtable API batch create
- **Backup**: nightly cron job syncs any sessions not yet synced (`airtable_synced_at IS NULL`)
- **Direction**: one-way, Supabase → Airtable (never Airtable → Supabase)

### Airtable structure
- One row per finding (mirrors `audit_findings` + `finding_feedback`)
- Columns: standard, criterion, finding text, severity, reviewer_tier, verdict, corrected_finding, course, session date
- Read-only for all viewers

### Airtable is NOT
- The operational system (that's Supabase)
- Editable by anyone during pilot
- The place where IDAs submit verdicts

---

## 10. Auth

### Pilot auth (Supabase Auth email+password)
```
1. QA admin creates tester record in Supabase (name, role, email, password)
2. IDA/ID opens Vercel app → login form
3. Supabase Auth validates credentials → returns session
4. App reads testers table for UUID + role
5. Role-based view loads
```

### Why not SSO for pilot
- New hires don't have ASU email for weeks after starting
- SSO integration is complex and not needed for small pilot group

### Post-pilot
- Add ASU SSO (SAML/OIDC)
- Link existing UUID to ASU identity
- All verdict history preserved (tied to UUID, not email)

---

## 11. Known Bugs (pre-pilot blockers) — ALL FIXED in Phase 0

### Bug 1: Supabase report URLs broken ✅ FIXED
- **Fix applied**: `audit_report.py` line 108 — `authenticated` → `public`
- **Verified**: real audit on LAW 517 generated working public Supabase URL

### Bug 2: HTML/XLSX reports show 0 data ✅ FIXED
- **Fix applied**: Added `_normalize_audit_data()` function to `audit_report.py`
- Normalizes unwrapped sections, lowercase summary keys, missing arrays
- Called in 3 entry points: `push_to_rlhf()`, `generate_report()`, `main()`
- **Verified**: malformed JSON input now generates correct reports; real audit (42 findings) rendered correctly

### Bug 3: Staging workflow fragile ✅ FIXED (Phase 0 simplification)
- **Fix applied**: Removed ~300 lines of dead JS from `unified_preview.py` (port 3847 references, contenteditable, drag-and-drop, push/delete buttons)
- Preview is now read-only with visual approval checkboxes
- Updated `staging/SKILL.md` with conversational approval flow
- **Note**: Inline editing will be re-added via Tiptap Lite (see Section 11.1 below)

### Bug 4: auditor_id always "ID Workbench" ✅ FIXED
- **Fix applied**: Added `_resolve_auditor()` helper — env var → data dict → fallback
- Replaced all 3 hardcoded instances
- **Verified**: fallback chain works correctly

---

## 11.1. Staging Preview Editor (Tiptap Lite)

### Purpose
Minor tweaks to staged HTML before pushing to Canvas — fix typos, adjust punctuation, clean up a word. Heavy editing happens in Claude Code; the preview editor is for last-mile polish.

### Architecture

```
Single server on port 8111 (upgraded from static http.server to Flask/FastAPI)
    ├── GET /{slug}.html → serves staged preview (read-only shell + Tiptap editor)
    ├── GET /_unified_preview.html → serves unified preview
    ├── PUT /api/staging/{slug} → saves edited HTML back to staging/{slug}.html
    └── Static files (CSS, JS)
```

### Editor: Tiptap Lite
- **Library**: Tiptap v3 via CDN (no npm build step — injected into preview HTML template)
- **Toolbar**: Bold, italic, underline, link, headings (H2-H4), bullet list, ordered list, undo/redo
- **No**: Color picker, image resize, slash commands, command palette, font picker, AI assist
- **Canvas paste cleanup**: Strips Word/Google Docs formatting on paste (from Canvas Shadow Editor pattern)
- **Auto-save**: Debounced (1s after last keystroke) → `PUT /api/staging/{slug}` → writes to `staging/{slug}.html`
- **Save indicator**: "Saved" / "Saving..." / "Unsaved" badge per page

### Server upgrade
- Replace `python3 -m http.server 8111 --directory staging` in `.claude/launch.json`
- New: lightweight Python server (`scripts/staging_server.py`) with:
  - Static file serving for `staging/` directory
  - `PUT /api/staging/{slug}` endpoint that:
    1. Receives HTML body from Tiptap
    2. Wraps in canvas-shell.html (using staging_manager.py logic)
    3. Writes to `staging/{slug}.html`
    4. Returns `{ok: true}`
  - CORS headers for local development

### What Tiptap Lite does NOT do
- Does not push to Canvas (that's the `/staging push` skill)
- Does not delete staged files (that's `staging_manager.py --clear`)
- Does not validate HTML (that's `preflight_checks.py`)
- Does not handle images or media (edit those in Claude Code)

### Reference implementations
- `/Users/bespined/Desktop/CanvasCurator` — full Tiptap RTE (1,030 lines), too heavy
- `/Users/bespined/Desktop/Canvas Shadow Editor` — leaner Tiptap (738 lines), good patterns
- Tiptap Lite target: ~150-200 lines of JS + toolbar HTML

### Implementation phase
- Part of Phase 0.5 (between Phase 0 bug fixes and Phase 1 audit skill)
- Dependencies: none (uses existing staging_manager.py, canvas-shell.html)
- Estimated: 1 session to build server + inject Tiptap into preview template

---

## 12. Implementation Phases

### Phase 0 — Bug Fixes ✅ COMPLETE

All 4 bugs fixed and verified against LAW 517 (course 223406). See Section 11 for details.

### Phase 0.5 — Staging Preview Editor ✅ COMPLETE

Tiptap Lite RTE in unified preview, staging_server.py with PUT API, course-scoped staging, Canvas paste cleanup, auto-save, course name in header.

### Phase 1 — Audit Skill Foundation ✅ COMPLETE

- 98 criteria tagged with reviewer_tier (57 id_assistant + 41 id) and category
- 18 CRC gap items added (crc.01-crc.18)
- Audit streamlined to 3 modes: Quick Scan / Full Audit / Guided Review
- Scope filters: all / essential / crc (nested under Quick Scan only)
- Finding schema updated with reviewer_tier, content_excerpt, canvas_link, criterion_id, category, essential
- Verified via real audit on LAW 517

### Phase 2 — Supabase Schema ✅ COMPLETE

- Migration: `migrations/001_phase2_schema.sql`
- New columns on audit_sessions: audit_purpose, audit_round, status, plugin_version, launch_gate fields
- New columns on audit_findings: reviewer_tier, canvas_link, criterion_id, category, remediation_requested
- New columns on finding_feedback: corrected_finding, correction_note, original_decision, override fields
- New tables: testers, tester_course_assignments, error_reports
- RLS: service_role full access on new tables
- audit_report.py updated to write all new fields
- Verified: 63/63 findings pushed with new fields populated

### Phase 3 — Vercel App (NEXT)

**Location**: `/Users/bespined/Desktop/idw-review-app/`

**Current state** (what already exists):
- Next.js 16.2.1, React 19, Tailwind CSS 4, Supabase client
- 3 routes: `/` (session list), `/session/[id]` (review page), `/dashboard` (RLHF metrics)
- FindingCard.tsx: approve/reject/false_positive with correction form
- Session page: filter by finding_type + review status, progress bar
- Dashboard: agreement rate by standard, reviewer activity table, JSON export
- No auth — reviewer name is manual text input
- All data access is direct Supabase queries from client components
- Styling: Tailwind utilities, brand color #8C1D40

**Existing files to modify**:

| File | What to change |
|---|---|
| `src/lib/supabase.ts` | Update TypeScript interfaces: add new fields to AuditSession, AuditFinding, FindingFeedback. Add Tester, TesterCourseAssignment, ErrorReport interfaces. |
| `src/components/FindingCard.tsx` | Rename actions: Approved→Agree, Rejected→Disagree, False Positive→Not an Issue, add N/A. Show content_excerpt inline. Add canvas_link as clickable button. Update feedback insert to use new field names (corrected_finding, correction_note). |
| `src/app/page.tsx` | Add role-based filtering: IDA sees assigned sessions only. Add session status badges (in_progress, pending_qa_review, etc.). Show audit_purpose tag. |
| `src/app/session/[id]/page.tsx` | Add reviewer_tier filter (IDA sees Col B only). Replace text name input with auth-based reviewer. Add "Submit for QA Review" button (ID view). Show QA feedback when status=revisions_required. |
| `src/app/dashboard/page.tsx` | Add IDA quality tracking (override rates). Add enrichment card effectiveness. |
| `src/app/globals.css` | Minor — update any hardcoded color values if needed. |

**New files to create**:

| File | Purpose |
|---|---|
| `src/app/login/page.tsx` | Email + password login form via Supabase Auth |
| `src/lib/auth.ts` | Auth helpers: getCurrentUser, requireAuth, getUserRole |
| `src/components/AuthGuard.tsx` | Wrapper component that checks auth + role, redirects to login |
| `src/components/NotificationBadge.tsx` | In-app badge for assignments/status changes |
| `src/app/admin/page.tsx` | Admin dashboard: error queue, RLHF patterns, tester management |
| `src/app/api/auth/route.ts` | Server-side auth endpoints if needed |

**Implementation order for Phase 3**:
1. Update TypeScript interfaces (supabase.ts) — foundation for everything else
2. Update FindingCard.tsx — rename actions, add evidence inline, add N/A
3. Add Supabase Auth (login page + auth helpers) — unblocks role-based views
4. Add role-based routing + AuthGuard — IDA/ID/QA/Admin views
5. Update session page — reviewer_tier filter, Submit for QA Review
6. Update home page — role-based session list, status badges
7. Build admin page — error queue, RLHF patterns, tester management
8. Add notification badges
9. Update dashboard — IDA quality tracking

**Key decisions already made**:
- Auth: email + password via Supabase Auth (not SSO — new hires don't have ASU email)
- Notifications: in-app badges only (no email)
- IDA view: Col B findings only (reviewer_tier = id_assistant)
- ID view: all findings + Submit for QA Review button
- QA team view: Pending Review queue + assign IDAs + override verdicts
- Admin: /admin route, password-gated via env var

**Phase 3 progress**:
- Step 1 ✅ TypeScript interfaces updated (supabase.ts) — all Phase 2 fields + new table interfaces
- Step 2 ✅ FindingCard updated — Agree/Disagree/Not an Issue/N/A + evidence inline + canvas link + reviewer_tier badges
- Step 3 ✅ Supabase Auth — login page (src/app/login/page.tsx), auth helpers (src/lib/auth.ts)
- Step 4 ✅ AuthGuard component — render prop wrapper, redirects to /login, role checking
- Step 5 ✅ Session page — AuthGuard, IDA sees Col B only (reviewer_tier filter), Submit for QA Review button (ID), Approve/Request Revisions (QA), status badges, round indicator, revisions banner
- Step 6 ✅ Home page — AuthGuard, sign out, user name+role in header, session status badges, audit purpose labels, round numbers
- Step 7 ✅ Admin page — /admin route (admin-only AuthGuard), testers management (add/activate/deactivate), error queue (list/resolve), RLHF summary stats
- Step 8: Notification badges — deferred to post-pilot-testing (needs real usage data to be meaningful)
- Step 9: Dashboard IDA quality tracking — deferred to post-pilot-testing (existing dashboard already shows agreement rates)
- Build verified: zero TypeScript errors, all routes registered (/, /login, /admin, /dashboard, /session/[id])
- NOTE: Before testing login, user must: (1) Enable email+password in Supabase Auth dashboard (Authentication → Providers → Email), (2) Create user in Supabase Auth, (3) Create matching row in testers table with same email
- Phase 3 IN PROGRESS — core MVP working, admin review UX remaining.

**Completed in Phase 3**:
- Login page + Supabase Auth (email+password)
- AuthGuard + role-based routing (3 roles: id, id_assistant, admin)
- FindingCard: Correct/Incorrect/N/A verdicts with Undo, ASU brand colors, evidence inline, canvas link
- Session page: reviewer_tier filter (IDA=Col B only), Submit for QA Review, pending banner
- Home page: auth, sign out, status badges, audit purpose
- Admin page: tester management (add/edit role/delete/activate), error queue, RLHF summary
- Audit modes renamed: Quick Check / Deep Audit / Guided Review
- qa_team role merged into admin (migration 002 applied)
- Supabase RLS: finding_feedback INSERT/DELETE for authenticated, testers SELECT by email
- Decision values: correct / incorrect / not_applicable
- finding_feedback reviewer_id FK issue resolved (omitted from inserts — FK points to auth.users not testers)

- **Admin FindingCard view** ✅ COMPLETE:
  - Shows "Reviewed by [name] — Marked Correct/Incorrect/N/A" with attribution
  - "Confirm" button (admin agrees) — green, instant
  - "Override" button (admin disagrees) — ASU Gold accent, requires reason
  - Override preserves original_decision, records overridden_by + override_reason
  - Overridden cards get gold border + "Overridden" badge
  - Confirmed cards get green "Confirmed" badge
  - Admin can still Correct/Incorrect/N/A on unreviewed findings
- Admin view: based on session status — pending_qa_review=QA mode, in_progress=ID mode
- 3-color progress bar: green (correct/agreed), red (incorrect/disagreed), gray (N/A)
- Unified single-row filter bar: All/Unreviewed/Reviewed/Correct/Incorrect/N/A (or Agreed/Disagreed for admin)
- Approve requires all findings reviewed + all agreed. Request Revisions requires at least one disagreement.
- Undo for Approve/Request Revisions decisions
- ASU brand colors on all buttons and badges

**Remaining Phase 3 work**:
- ✅ Admin revision comments visible to ID — pink box shows "Admin disagreed" + reason on ID view after revisions requested
- **ID re-review after revisions**: When admin requests revisions, findings where admin disagreed should auto-reset the ID's verdict so Correct/Incorrect/N/A buttons show again (instead of Undo). The ID needs to re-decide with admin feedback visible.
- **Session list filters on home page**: filter by status (in_progress, pending_qa_review, qa_approved, revisions_required). Approved sessions should be hidden by default, shown with a "Completed" filter. All roles need this.
- Session list filters: filter by tester, course, status, audit_purpose (admin page enhancement)
- Comment history: show full decision/override history per finding (who decided what and when)
- Notification badges (deferred — post-pilot)
- Dashboard IDA quality tracking (deferred — post-pilot)
- IDA sessions: admin Agree/Disagree applies the same way as ID sessions

### Phase 4 — Airtable Integration

| Task | Details |
|---|---|
| Design Airtable base structure | one row per finding, columns matching Supabase fields |
| Build Supabase → Airtable sync function | Edge Function or pg_net, batch Airtable API |
| Trigger on session complete | all findings verdicted → fire sync |
| Nightly catch-up job | cron, sync sessions where airtable_synced_at IS NULL |
| Test sync with real audit data | end-to-end validation |

### Phase 5 — RLHF + Admin Skills

| Task | Details |
|---|---|
| `/assignments` skill | IDA course list from tester_course_assignments |
| `/assign` skill | Admin assigns IDAs to courses |
| `/report-error` skill | User reports bug/issue → error_reports table |
| `/update-idw` skill | git pull to distribute prompt/config updates |
| `fetch_fix_queue.py` script | query Supabase for remediation_requested findings |
| Update `/course-review` to use fix queue | pull from Supabase instead of local |
| Admin RLHF pattern analysis | aggregate queries on finding_feedback |

---

## 13. Pilot Scope

### Scale
- **Total**: ~40-50 courses during pilot across both workflows
- **Course types**: all kinds, not limited to specific degrees or programs
- **Workflows**: both new course dev AND recurring audits from day one

### Duration
- **1-2 months** — long enough to collect meaningful RLHF data and iterate on prompts
- Goal: train the plugin to best accuracy before full launch

### Success criteria
- 85% agreement rate across all findings by end of pilot
- Staging workflow stable and reliable
- Airtable sync functioning
- IDA review workflow validated (assign → verdict → override → sync)

---

## 14. Notifications

- **In-app badges only** (no email) — QA team and IDAs are logged into Vercel app to review, so notifications live there
- **Why not email**: too many emails already; IDAs may not have ASU email for weeks
- **IDA notifications**: badge when assigned to a new session, badge count of un-verdicted findings
- **ID notifications**: badge when QA review is complete, badge when status = 'revisions_required'
- **QA team notifications**: badge when ID submits for QA review (new item in Pending Review queue)

---

## 15. Plugin Version Tracking

- `plugin_version` field on `audit_sessions` — records which version of the audit skill generated findings
- Format: semver or git short hash (e.g., `"0.3.1"` or `"a1b2c3d"`)
- Written by `audit_report.py` when pushing to Supabase
- Used by admin dashboard to correlate RLHF improvements with prompt/config changes
- Enables rollback identification: "disagreement rate spiked after version X"

---

## 16. Concurrency Rules

- **2 IDAs cannot be assigned to the same session** — enforce in Vercel app assignment UI
- **ID does not modify course during QA review** — by convention (IDs move to other courses after submitting). No technical enforcement needed for pilot.
- **Multiple sessions per course are fine** — each audit creates a new session (different audit_round or audit_purpose)

---

## 17. Unresolved Questions

### Q1: IDA Canvas token access (BLOCKS: who triggers recurring audits)
- **Options**: A (no token, QA runs audits) vs B (IDA has token + Claude Code)
- **Decision needed from**: QA team + Canvas admin
- **Documents**: `IDW-QA-IDA-access-comparison.md`, `IDW-QA-option-A-IDAs-no-canvas.mmd`, `IDW-QA-option-B-IDAs-have-canvas.mmd`
- **Context**: IDAs are CS masters students (technically capable), but are student workers with semester tenure. Token provisioning and revocation adds admin overhead.
- **Recommendation**: Option A for pilot, Option B post-pilot if needed

### Q2: Recurring course remediation owner (DOES NOT BLOCK pilot)
- Currently: passive, findings go to Airtable, faculty/IDs fix if they have time
- Not launch-gated
- No action needed for pilot

### Q3: Communication to faculty (DOES NOT BLOCK pilot)
- IDAs do NOT send communications to faculty
- For pilot: manual, out-of-system (email from whoever did the fix)
- No automation needed

---

## 18. Reference Files

### Plugin structure
```
/Users/bespined/claude-plugins/IDW-QA/
├── CLAUDE.md                          # Plugin instructions (read first)
├── PLANNING.md                        # THIS FILE
├── IDW-QA-system.mmd                  # Full system diagram (Mermaid)
├── IDW-QA-option-A-IDAs-no-canvas.mmd # Process chart: Option A
├── IDW-QA-option-B-IDAs-have-canvas.mmd # Process chart: Option B
├── IDW-QA-IDA-access-comparison.md    # IDA access decision document
├── config/
│   ├── standards.yaml                 # 25 standards + criteria (needs reviewer_tier)
│   └── standards_enrichment.yaml      # Enriched criteria with examples
├── scripts/
│   ├── canvas_api.py                  # Canvas API utilities
│   ├── audit_report.py                # Report generation + Supabase push (HAS BUGS)
│   ├── deterministic_checks.py        # 18 hardcoded checks (needs expansion to 107)
│   ├── preflight_checks.py            # Content validation
│   ├── staging_manager.py             # Local staging (HAS BUGS)
│   └── ... (see CLAUDE.md for full list)
├── skills/
│   ├── audit/SKILL.md                 # Audit skill (needs 3-mode streamline + evidence)
│   ├── staging/SKILL.md               # Staging skill (needs simplification)
│   └── ... (16 skills total)
├── standards/
│   ├── canvas-standards.md            # ASU design standards
│   ├── page-design.md                 # HTML/CSS design system
│   └── ...
├── reference/                         # Source documents (copied from Downloads)
│   ├── [QA + AI] Experience Stage_Review Item Lists.xlsx
│   └── [Auryan] IDAsst QA Tasks.xlsx
└── templates/
    └── canvas-shell.html              # Staging preview template
```

### Vercel app
```
/Users/bespined/Desktop/idw-review-app/
├── src/app/page.tsx                   # Home — needs role routing
├── src/components/FindingCard.tsx      # Needs rename + N/A + evidence
├── src/lib/supabase.ts                # TypeScript interfaces (needs update)
└── ...
```

### Source spreadsheets (copied to `reference/`)
```
[QA + AI] Experience Stage_Review Item Lists.xlsx
└── Sheet: "Review Item Lists"
    ├── Col A: 25 standards (with * for essential)
    ├── Col B: 107 IDAsst deterministic checks (reviewer_tier = id_assistant)
    └── Col C: 42 ID qualitative checks (reviewer_tier = id)

[Auryan] IDAsst QA Tasks.xlsx
├── Sheet: "Original - Course Readiness Che" — 52 original CRC items
├── Sheet: "CRC Item Categorization" — CRC items mapped to standards (33 covered, 18 NOT covered)
├── Sheet: "CRC Items - Design Standard Ali" — detailed alignment notes per CRC item
├── Sheet: "IDAsst Checklist Redesign" — redesigned checklist brainstorming
└── Sheet: "Ordering" — ordering/priority of checks
```
