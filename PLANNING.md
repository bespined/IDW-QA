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
17. [System Rename: IDW QA → SCOUT ULTRA](#17-system-rename-idw-qa--scout-ultra)
18. [Unresolved Questions](#18-unresolved-questions)
19. [Reference Files](#19-reference-files)

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

| Role in system | Who | Claude Code | Vercel App | What they do |
|---|---|---|---|---|
| `id` | IDs AND IDAs (ID Associates) | Yes | Yes | Audit both Col B + C, remediate, submit for QA review |
| `id_assistant` | Student workers / Working learners | No (web app only) | Yes | Verdict Col B findings only, validate readiness, assigned by admin |
| `admin` | QA team (3 people) | Yes (QA token) | Yes (/admin) | Run recurring audits, assign ID Assistants, manage testers, outreach, analytics |

**Naming clarification:** IDA = "ID Associate" = full `id` role (can audit + remediate). ID Assistant = student worker = `id_assistant` role (verdict Col B only, no Canvas access, no remediation). These are NOT the same despite similar names.

**Note**: The `qa_team` role was merged into `admin` — there are now 3 roles, not 4.

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
8. Session appears in admin queue as "New Course Dev"
9. Admin assigns ID Assistant to session (assigned_to field)
10. ID Assistant verdicts Col B findings (correct/incorrect/not_applicable)
    - If incorrect → corrected_finding text required
11. Col C findings auto-approved when ID marks complete (no review gate)
12. Decision:
    - If ID Assistant agrees on all Col B → qa_approved
    - If ID Assistant disagrees on any → revisions_required, back to ID for remediation
    - All approved → Airtable sync
```

### Workflow C — Recurring Course Audit (NOT launch-gated)

```
1. Admin triggers audit via Claude Code → audit_purpose = 'recurring' (inferred from admin role)
2. Findings → Supabase
3. Admin assigns ID Assistant to session
4. ID Assistant verdicts Col B findings in Vercel app
5. Admin spot-checks (not required for every finding)
6. Admin sends faculty outreach based on findings
7. Findings sync to Airtable
8. Remediation is PASSIVE:
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

Updated 2026-03-31 from `config/standards.yaml`. Source: [QA+AI] Experience Stage sheet + existing criteria for standards without sheet entries.

```
Standard 01 (Course-Level Alignment)*:      3B / 3C =  6
Standard 02 (Module-Level Alignment)*:      2B / 2C =  4
Standard 03 (Alignment Made Clear):         0B / 2C =  2
Standard 04 (Consistent Layout):           46B / 1C = 47
Standard 05 (Engaging Introductions):       0B / 3C =  3
Standard 06 (Clear Workload)*:              5B / 5C = 10
Standard 07 (Instructor Guide):             1B / 2C =  3
Standard 08 (Assessments Align)*:           1B / 1C =  2
Standard 09 (Clear Grading Criteria):       8B / 0C =  8
Standard 10 (Varied Assessments):           2B / 2C =  4
Standard 11 (Cognitive Skills):             0B / 2C =  2
Standard 12 (Materials Align)*:             0B / 1C =  1
Standard 13 (High-Quality Content):        14B / 2C = 16
Standard 14 (Real-World Relevance):         0B / 3C =  3
Standard 15 (Universally Designed Content): 0B / 1C =  1
Standard 16 (Universally Designed Media):   1B / 1C =  2
Standard 17 (Open Space for Questions):     4B / 1C =  5
Standard 18 (Instructor-Created Media):     2B / 4C =  6
Standard 19 (Active Learning):              0B / 5C =  5
Standard 20 (Tool Integration):             4B / 3C =  7
Standard 21 (Technical/Academic Support):   0B / 1C =  1
Standard 22 (Material Accessibility)*:     11B / 1C = 12
Standard 23 (Tool Accessibility)*:          0B / 2C =  2
Standard 24 (Mobile/Offline):               1B / 0C =  1
Standard 25 (Low-Cost Resources):           1B / 1C =  2
CRC (Course Readiness Checks):             18B / 0C = 18
                                   TOTAL: 124B / 49C = 173
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
                   -- 'correct' | 'incorrect' | 'not_applicable'
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
                   -- 'correct' | 'incorrect' | 'not_applicable'
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
- **Trigger**: all findings in a session have a verdict (correct/incorrect/not_applicable)
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

- 173 criteria tagged with reviewer_tier (124 id_assistant + 49 id) and category
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

### Phase 3 — Vercel App ✅ COMPLETE

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

**Recently completed**:
- ✅ Admin revision comments visible to ID — pink "Admin disagreed" box
- ✅ ID auto-reset after admin disagrees — Correct/Incorrect/N/A show again with admin comment
- ✅ Session list filters: Pending Review (default) | Active | Completed | All with counts
- ✅ Admin search bar: filter by course name, code, or auditor
- ✅ "Needs Revision" filter on session page (ID view, revisions_required)
- ✅ Custom UI modals replacing all window.alert/confirm
- ✅ Admin unreviewed findings show "Awaiting ID review" not action buttons

**Remaining Phase 3 work (continue next session)**:
- ✅ Bug fixed: Admin re-review after ID revision — old feedback deleted, fresh Agree/Disagree shown
- ✅ Course assignment UI — admin page "Course Assignments" tab with assign/remove
- ✅ IDA home page filtering — IDAs only see sessions for assigned courses
- ✅ Course assignment UI on admin page
- ✅ Feedback history preserved (no deletion on re-review, most recent picked by reviewed_at)
- ✅ Bug fixed: IDA dropdown — RLS policy updated so authenticated users can read all testers
- ✅ "Needs Review" filter added for admin mode
- ✅ Assignment table search filter (by IDA name or course)
- **Bug: Assignment INSERT blocked by RLS** — need to run SQL: policy for authenticated users on tester_course_assignments
- **Bug: Admin round 2 shows Undo** — root cause: admin's agree/disagree UPDATEs the feedback row's overridden_at. When ID re-reviews (new row), the new row is clean, but if admin already agreed on it, overridden_at is set → shows Undo. Test session has been reset for clean round testing.
- ✅ Feedback history UI — collapsible "Show decision history (N entries)" per finding, reverse chronological, shows all decisions + admin comments
- **Admin round 2 Undo bug** — admin may still see Undo instead of Agree/Disagree after ID re-reviews. Verify with testing.
- ✅ Mass course assignment (comma-separated IDs)
- ✅ Tester page search + role filter
- ✅ IDA "Mark as Complete" flow (no QA gate — IDA verdicts are final for Col B)
- **IDA end-to-end test** — assign course → IDA reviews Col B → marks complete → verdicts ready for Airtable
- **IDA workflow clarification**: Admin does NOT Agree/Disagree on IDA verdicts. IDA's correction is final say for Col B. Admin only spot-checks quality via dashboard metrics.
- ✅ IDA only sees recurring sessions (not ID self-audits)
- ✅ Completed filter count includes IDA 'complete' status
- ✅ Reopen button for IDA after marking complete
- **Advanced filters (post-Phase 3)**: Jira/Asana-style dropdowns + checkboxes for tester, role, course, status. Save View button for persistent default views per user (localStorage or Supabase). Major UI feature.
- Notification badges — deferred
- Dashboard IDA quality tracking — deferred

**Phase order discussion**:
- Consider swapping Phase 4 (Airtable) and Phase 5 (RLHF/Admin skills) — Airtable sync may be less critical than getting the admin/IDA skills working in Claude Code. Discuss before proceeding.

### Phase 4 — RLHF + Admin Skills ✅ COMPLETE

**Claude Code skills to build** (in `/Users/bespined/claude-plugins/IDW-QA/skills/`):

| Skill | Trigger | Role gate | What it does |
|---|---|---|---|
| `/assignments` | "my assignments", "what courses" | IDA only | Query tester_course_assignments → show assigned courses + status |
| `/assign` | "assign IDA to course" | Admin only | Insert into tester_course_assignments via Supabase service key |
| `/report-error` | "report a bug", "something broke" | All roles | Insert into error_reports table with context (session_id, skill, etc.) |
| `/update-idw` | "update plugin", "pull latest" | Admin only | git pull to get latest prompts/config, show changelog |
| `/admin` | "admin", "error queue" | Admin only | View error_reports, RLHF stats, manage testers from Claude Code |

**Scripts to build** (in `scripts/`):

| Script | Purpose |
|---|---|
| `fetch_fix_queue.py` | Query Supabase for findings where remediation_requested=true, return as actionable list |
| `rlhf_analysis.py` | Aggregate finding_feedback: agreement rate by standard, by criterion, by reviewer, trends over time |

**Role gating for skills**: Each skill checks `IDW_TESTER_ID` in `.env` → queries Supabase `testers` table → verifies role before executing. Non-authorized roles get "This skill requires [role] access."

**Dashboard fix**: Update `/dashboard` page to use new decision values (correct/incorrect/not_applicable) and handle missing Supabase views gracefully.

**Fix queue integration**: Update `/course-review` skill to pull from Supabase `audit_findings` where `remediation_requested=true` instead of local files.

**Implementation order**:
1. Fix dashboard (quick — update queries)
2. Role gating helper (shared by all skills)
3. `/assignments` + `/assign` (IDA + admin course management)
4. `/report-error` (all roles)
5. `fetch_fix_queue.py` + `/course-review` integration
6. `/update-idw` + `/admin`
7. `rlhf_analysis.py`

**Status**: Complete. Tagged v0.5.0.

### Phase 4.5 — Report Updates + Fix Queue UX ✅ COMPLETE

**What was built:**

1. **FindingCard "Needs remediation" checkbox** — always visible regardless of verdict. Toggles `remediation_requested` on `audit_findings` via server-side API route (`/api/findings/remediation`) using service key to bypass RLS. Verdict and remediation are independent decisions.

2. **HTML report — Phase 2 fields added:**
   - Reviewer tier badge on each finding card: Design (brown), Readiness (blue), A11y (purple)
   - "View in Canvas" clickable link when `canvas_link` is present
   - Category filter bar: toggle Design/Readiness/A11y independently, combines with status filters (Met/Partial/Not Met)
   - QA Categories table: added Tier column
   - Accessibility table: page names link to Canvas when `canvas_link` present

3. **XLSX report — Phase 2 fields added:**
   - Column K: Reviewer Tier ("IDA" or "ID") with color coding
   - Dashboard sheet: reviewer tier breakdown row (IDA-reviewable vs ID-reviewable counts)

4. **Report download from Vercel** — session page header shows "Report" download button when `report_html_url` exists on the session. Opens HTML report from Supabase storage.

5. **RLS migration** (`migrations/005_allow_anon_remediation_toggle.sql`) — allows anon key to read/update `audit_findings` for the remediation checkbox. Superseded by API route approach but kept for reference.

### Phase 5 — Airtable Integration + Workflow Updates (IN PROGRESS)

#### Updated Workflow (March 2026)

##### Roles (finalized)

| Role in system | Who | Reviews | Remediates? | Canvas access? |
|---|---|---|---|---|
| `id` | IDs AND IDAs (ID Associates) | Col B + Col C | Yes | Yes |
| `id_assistant` | Student workers / Working learners | Col B only | No | No (web app only) |
| `admin` | QA team (3 people) | Owns analytics + outreach | No finding-level review | Yes |

**Naming clarification:** IDA = "ID Associate" = full `id` role. ID Assistant = student worker = `id_assistant` role. These are NOT the same.

##### EDL New Course Development Workflow

```
1. ID/IDA runs /audit on the course
2. ID/IDA reviews ALL findings (Col B + C) in review app
   ├── Verdicts: correct / incorrect / N/A
   ├── Flags "needs remediation" on confirmed issues
   └── Remediates with faculty using plugin skills
3. ID/IDA marks session complete
   ├── Col C findings: auto-set to qa_approved (no review gate)
   └── Col B findings: move to pending_qa_review for ID Assistant validation
4. ID Assistant validates Col B findings
   ├── Round 1 (pre-remediation): Correct/Incorrect on AI finding
   ├── Round 2+ (post-remediation): Agree/Disagree on whether fix worked
   ├── All agree → qa_approved
   └── Any disagree → revisions_required → back to ID/IDA
       └── Auto-sets remediation_requested=true → finding re-enters fix queue
5. All qa_approved findings → single Airtable sync
```

##### Recurring Course Audit Workflow

```
1. QA team (admin) runs /audit
2. ID Assistant reviews Col B findings only in review app
   ├── Verdicts: correct / incorrect / N/A
   └── NO remediation, NO faculty contact
3. ID Assistant marks session complete
4. Admin reviews ID Assistant verdicts (spot-check only, not required for every finding)
5. Admin sends faculty outreach based on flagged items
6. Findings sync to Airtable
```

##### Finding Card Lifecycle

```
── After AI audit (no human has touched it) ──
Standard 23 — Image Accessibility
AI Verdict: Not Met — 15 images missing alt text
[Correct] [Incorrect] [N/A]     ☐ Needs remediation

── After ID reviews ──
Standard 23 — Image Accessibility
AI Verdict: Not Met — 15 images missing alt text
ID Decision: Correct (Jane Doe, Mar 15)          [Undo]
                                                  ☑ Needs remediation

── After ID remediates ──
Standard 23 — Image Accessibility
AI Verdict: Not Met — 15 images missing alt text
ID Decision: Correct (Jane Doe, Mar 15)
  → Remediated via /bulk-edit (Jane Doe, Mar 15)
                                                  ☑ Needs remediation

── ID Assistant validates (Col B only) ──
Standard 23 — Image Accessibility
AI Verdict: Not Met — 15 images missing alt text
ID Decision: Correct (Jane Doe, Mar 15)
  → Remediated via /bulk-edit (Jane Doe, Mar 15)
ID Assistant: Validated (Alice Chen, Mar 18)      ✓ Approved

── ID Assistant disagrees (Round 2) ──
Standard 23 — Image Accessibility
AI Verdict: Not Met — 15 images missing alt text
ID Decision: Correct (Jane Doe, Mar 15)
  → Remediated via /bulk-edit (Jane Doe, Mar 15)
ID Assistant: Disagree — "5 images still missing alt text" (Alice Chen, Mar 18)
  → Remediated via /bulk-edit (Jane Doe, Mar 19)
ID Assistant: Validated (Alice Chen, Mar 20)      ✓ Approved
```

##### New Table: remediation_events

Tracks what was fixed, when, how, and by whom. Separate from `audit_findings` (what AI found) and `finding_feedback` (human verdicts).

```sql
CREATE TABLE IF NOT EXISTS remediation_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  finding_id UUID REFERENCES audit_findings(id) NOT NULL,
  remediated_by UUID REFERENCES testers(id),
  skill_used TEXT,              -- e.g., 'bulk-edit', 'quiz', 'interactive-content', 'manual'
  description TEXT,             -- e.g., 'Added alt text to 15 images'
  created_at TIMESTAMPTZ DEFAULT now()
);
```

##### ID Assistant Verdict Vocabulary

| Context | Buttons shown | Meaning |
|---|---|---|
| Auditing (reviewing AI finding) | Correct / Incorrect / N/A | "I agree/disagree the AI finding is accurate" |
| Validating (checking ID's work post-remediation) | Agree / Disagree | "I confirm/deny the fix resolved the issue" |

Both create `finding_feedback` rows. The UI shows the right buttons based on whether the finding has prior remediation events.

##### Disagree → Re-enter Fix Queue

When ID Assistant disagrees on a remediated finding:
1. `finding_feedback` row created with `decision: 'disagree'` + reason
2. `audit_findings.remediation_requested` auto-set to `true`
3. Session status → `revisions_required`
4. Finding re-appears in `/course-review` Step 0 fix queue
5. ID/IDA re-remediates → new `remediation_events` row
6. ID Assistant re-validates

#### Airtable Integration

##### Architecture: Unified Data, Separate Concerns

```
Canvas → Plugin → Supabase (source of truth) → Vercel (workflow) → Supabase (verdicts)
                                                                          ↓
                                                               Airtable (data store + faculty view)
```

**Supabase + Vercel** = backend + frontend (where work happens)
**Airtable** = data store for faculty/stakeholder consumption (read-only output)

Airtable is NOT a separate system with its own structure. It mirrors Supabase data in a format faculty and academic units can filter and view. The sync is a one-way push from Supabase → Airtable.

##### Data Unification Plan

**Problem:** The audit currently produces one finding per standard (25 rows). The [QA+AI] sheet defines 147 criteria (106 Col B + 41 Col C). Airtable, Supabase, and the Vercel app all need per-criterion granularity to be useful.

**Solution:** Unify around per-criterion findings everywhere:

1. **`config/standards.yaml`** — Add all 147 criteria from [QA+AI] sheet with `B-XX.Y` and `C-XX.Y` IDs, mapped to their column (Col B = `reviewer_tier: id_assistant`, Col C = `reviewer_tier: id`)
2. **Audit skill** — Produce one `audit_findings` row per criterion (147 findings per full audit instead of 25)
3. **Supabase `audit_findings`** — Already supports per-criterion via `criterion_id` field. No schema change needed.
4. **Vercel app** — Already groups findings by `standard_id`. More findings per standard = more detail, same UX.
5. **Airtable sync** — Maps `criterion_id` directly to column name (`B-04.1` → `B-04.1 Layout: Getting Started*`). Standard-level rating derived from criteria (all Yes = Met, any No = Not Met). Notes auto-generated from failing criteria.

**Result:** One source of truth (Supabase), one structure (per-criterion findings), three consumers (Vercel for workflow, Airtable for faculty, HTML report for download). No translation layer needed — just a pivot from rows to columns for Airtable.

##### Implementation Order

1. **Update `config/standards.yaml`** — Add all 147 criteria from [QA+AI] sheet with `B-XX.Y` / `C-XX.Y` IDs
2. **Update audit skill** — Evaluate per criterion, produce one `audit_findings` row per criterion with `criterion_id`
3. **Update `audit_report.py` (HTML report)** — Standard cards show expandable criteria list (`_render_criteria_results()` already exists, needs real data). Each criterion shows Yes/No + evidence for failures.
4. **Update Vercel session page** — Group FindingCards under standard headers. One card per criterion. Verdict buttons only on failing criteria. ID Assistants see only B-* criteria.
5. **Update `airtable_sync.py`** — Map `criterion_id` → Airtable column name (direct lookup). Standard rating derived from criteria (all Yes = Met, any No = Not Met/Partially Met). Notes auto-generated from failing criteria only.
6. **Test end-to-end** — Audit → Supabase (147 per-criterion rows) → Vercel (grouped view) → HTML report (criteria tables) → Airtable (all columns populated)
7. **Admin sync button** — Already built in Vercel session page (manual trigger)
8. **Faculty outreach** — Template-based email drafts from Airtable data. Phase 6 if complex.

##### Consumer Changes Summary

| Consumer | Before (per-standard) | After (per-criterion) |
|---|---|---|
| **Supabase** | ~25 findings per audit | ~147 findings per audit. No schema change — `criterion_id` field already exists |
| **HTML report** | One card per standard, one evidence block | One card per standard with expandable criteria list. Each criterion: Yes/No + evidence on failure |
| **Vercel session** | One FindingCard per standard | FindingCards grouped under standard headers. One card per criterion. Verdict buttons only on failing items. ID Assistants see B-* only |
| **Airtable** | Standard-level rating + notes (criteria columns empty) | All 147 B/C columns populated + standard rating + notes |
| **RLHF feedback** | Verdicts on standard-level findings | Verdicts on individual criteria (more precise training signal) |

##### Architecture Decision: Vercel + Airtable (Dual Approach)

Vercel app handles interactive review workflow (finding cards, role-based views, verdict buttons, remediation tracking). Airtable handles reporting and analytics (filter by school/program, stakeholder views, faculty outreach). Both read from Supabase (source of truth). Neither is redundant — removing Vercel degrades the workflow, removing Airtable degrades reporting. See `IDW-QA-Frontend-Architecture-Recommendation.docx` on Desktop for full rationale.

Data flow: Canvas → Plugin → Supabase → Vercel (review) → Supabase (verdicts) → Airtable (reporting)

##### Airtable Base Structure (QA Test — use this during testing, NOT SCOUT ULTRA)

- **Base:** appHzYJqoyopf4jN8 (QA Test)
- **Table:** Course Audits (tblI55WEIy16aftkS) — 207 fields
- **Format:** One row per course. Columns:
  - Metadata: Course Name, Code, Term, Canvas URL, Audit Date, Auditor, Overall Score, Session Status
  - Per standard (25): `XX. Standard Name — Rating` (Met/Partially Met/Not Met/Not Auditable) + `XX. Standard Name — Notes` (high-level summary for faculty)
  - Col B criteria (106): `B-XX.Y Description` (Yes/No/N/A) — ID Assistant reviewable
  - Col C criteria (41): `C-XX.Y Description` (Yes/No/N/A) — ID reviewable
- **Views:** (create manually in Airtable — API doesn't support view creation)
  - ID/IDA view: all columns
  - ID Assistant view: metadata + B-* columns only (Col C hidden)
  - Admin/Summary view: metadata + ratings + notes only (criteria hidden)

##### Phase 5 Progress (as of 2026-03-31)

**Completed:**
- `airtable_sync.py` — per-criterion sync, maps all 147 B-/C- columns directly from criterion_id. Tested with CRJ 201 (147/147 criteria populated).
- `remediation_events` table — migration 006 created. API routes: GET + POST at `/api/remediation-events`.
- Session completion API — `/api/session-complete` handles Col C auto-approve + Col B → pending_qa_review.
- Sync button — admin-only button on Vercel session page header.
- Auditor name — now pulls from tester identity (IDW_TESTER_ID → Supabase testers table).
- `standards.yaml` — updated with all 173 criteria (124 B + 49 C) from [QA+AI] sheet.
- Audit skill — updated for per-criterion evaluation, produces `criteria_results` per standard.
- HTML report — per-criterion expandable tables with B/C badges, met counts, evidence.
- `audit_report.py` — pushes per-criterion findings to Supabase (one row per criterion).

**Completed (cont.):**
- FindingCards grouped view — StandardGroup component groups findings by standard. Collapsible, shows met counts, Col B/C separation.
- Category filter — Design/Readiness/A11y toggle buttons on session page.
- Batch audit — audit skill asks course selection first (current/pick/batch/other).
- Review app pushed to GitHub with all API routes and UI changes.

**In Progress — Evidence Quality Fix (CRITICAL for demo + pilot):**

The audit produces per-criterion findings but the evidence is not specific enough for reviewers to verify or for remediation skills to act on. Three problems identified:

*Problem 1: Field mapping is swapped.*
`audit_report.py` stores criterion QUESTION in `content_excerpt` and evidence summary in `ai_reasoning`. FindingCard renders `content_excerpt` in the "Evidence" box — so reviewers see the question labeled as evidence.

Fix: In `audit_report.py` push_to_rlhf, swap fields:
- `ai_reasoning` = criterion question + verdict explanation ("This criterion checks if... Result: Partially Met because...")
- `content_excerpt` = actual evidence (specific pages, elements, content found/missing)

*Problem 2: FindingCard display order is wrong.*
Currently: ai_reasoning as body text (unlabeled), content_excerpt in "Evidence" box. Should be: criterion question as subtitle, evidence as the labeled evidence block.

Fix: In FindingCard.tsx, restructure:
- Card title area: criterion_id + verdict badge
- Subtitle: criterion question (from content_excerpt after fix, or a new field)
- Body: ai_reasoning as the verdict explanation
- Evidence box: actual evidence with page/element specifics

*Problem 3: Audit evaluation doesn't read page content.*
The eval_criterion function returns generic summaries ("Module overviews present objectives but...") without reading actual page HTML. For remediation to work, evidence must include:
- Which specific pages were checked
- What was found or not found on each page
- For images: page slug + img src
- For headings: page slug + the heading skip
- For missing content: where it should be

Fix: The audit evaluation must use the fetched page_bodies to produce per-page evidence. For deterministic checks (Col B), parse HTML and list every instance. For AI checks (Col C), read relevant pages and cite specific content.

This is the biggest remaining quality issue — without specific evidence, the review workflow and remediation skills are both blind.

**Completed (cont.):**
- Fix 1: Field mapping — `ai_reasoning` = criterion question, `content_excerpt` = actual evidence. Pushed + tested.
- Fix 2: FindingCard — criterion question in italic, evidence in labeled bold box. Pushed.
- Fix 3: Content-aware evaluation — audit now reads page HTML, collects per-page image/heading/content evidence. Tested on LAW 517 (96 specific images identified across 68 pages).

**Remaining — Session Assignment + Routing:**

*Session assignment for ID Assistants:*
- New field: `audit_sessions.assigned_to` (UUID → testers). Admin assigns an ID Assistant to review a session.
- ID Assistant's Vercel dashboard shows only sessions where `assigned_to = my_id`.
- Assignment is sticky through rounds — same ID Asst reviews all rounds unless admin reassigns.
- Migration needed: `ALTER TABLE audit_sessions ADD COLUMN IF NOT EXISTS assigned_to UUID REFERENCES testers(id);`

*Audit purpose — inferred from role, no prompt:*
- `id` role runs audit → `audit_purpose = self_audit` (new course dev). Always.
- `admin` role runs audit → `audit_purpose = recurring`. Always.
- No extra question needed. Role = purpose.

*Iterative self-audits during course build (CLARIFIED 2026-04-02):*
IDs will run multiple self-audits during a course build for iterative improvement — not for formal QA. This creates many sessions on their dashboard. Without UX handling, the dashboard becomes a wall of sessions that all look the same.

**Session grouping model:**
- Sessions are grouped by `course_id` + `audit_purpose` on the dashboard
- Within a group, sessions are ordered by `audit_round` (1, 2, 3...)
- Dashboard shows ONE card per course, with the latest session expanded and prior rounds collapsed:
  ```
  ┌─ BIO 101 (Self-Audit) ──────────────────────┐
  │ Latest: Round 3 — Score 78 — 4 findings      │
  │ ▸ Round 2 — Score 65 — 12 findings (Mar 28)  │
  │ ▸ Round 1 — Score 41 — 23 findings (Mar 25)  │
  │ [Run Another Audit] [Submit for QA Review]    │
  └───────────────────────────────────────────────┘
  ```
- "Submit for QA Review" only appears on the latest round
- Prior rounds are view-only (historical — shows improvement over time)
- Progress visualization: score trend (41 → 65 → 78) shows the ID is improving the course

**What changes:**
- Vercel app: sessions home page groups by course instead of flat list
- Vercel app: add score trend mini-chart per course group
- `audit_session_manager.py` already increments `audit_round` — no backend change needed
- Audit skill: after completing, show "Score improved from X to Y since last audit" if prior rounds exist

**Why this matters for pilot:**
- 40-50 courses × 3-5 rounds each = 150-250 sessions
- Without grouping, the dashboard is unusable

### Progress Check vs. Submit for Review (CLARIFIED 2026-04-02)

**Problem:** Currently every audit pushes findings to Supabase + Vercel. IDs running iterative self-audits to fix their course flood Supabase with intermediate findings that:
- IDAs waste time reviewing (Round 1 findings the ID already fixed by Round 3)
- Pollute RLHF data (verdicts on stale findings train the system on outdated course state)
- Clutter the Vercel dashboard with sessions that were never meant for review

**Solution:** The audit skill must ask **before pushing to Supabase**:

```
Your audit is complete. What would you like to do?

  [Progress check]  — Save the report locally. I'm still fixing this course.
  [Submit for review] — Push findings to the review app for QA team/IDA review.
```

**Behavior by choice:**

| | Progress Check | Submit for Review |
|---|---|---|
| HTML report generated | ✅ Yes (local file) | ✅ Yes (local file) |
| `audit_results.json` saved | ✅ Yes | ✅ Yes |
| Supabase `audit_sessions` row | ❌ No | ✅ Yes |
| Supabase `audit_findings` rows | ❌ No | ✅ Yes |
| Vercel review app link | ❌ No | ✅ Yes |
| IDA can review/verdict | ❌ No | ✅ Yes |
| RLHF data collected | ❌ No | ✅ Yes |
| Airtable sync available | ❌ No | ✅ Yes (after IDA review) |
| Score delta shown | ✅ Yes (from local prior `audit_results.json`) | ✅ Yes |

**Implementation:**
1. `audit/SKILL.md` — add AskUserQuestion after audit completes, before calling `audit_report.py`
2. `audit_report.py` — add `--local-only` flag that generates HTML/XLSX but skips `push_to_rlhf()`
3. For progress checks: `python3 scripts/audit_report.py --input audit_results.json --open --local-only`
4. For submissions: `python3 scripts/audit_report.py --input audit_results.json --open` (existing behavior)
5. Score delta: compare current `audit_results.json` against prior saved results (store as `audit_results_round_N.json`)

**RLHF impact:** Only submitted audits enter the feedback loop. This means:
- Fewer but higher-quality findings for IDAs to review
- Verdicts reflect the course's final state, not intermediate states
- Agreement rates are more meaningful (comparing AI vs human on the same content)
- No need to retroactively clean stale findings from Supabase
- With grouping, each course shows as ONE card with progress history

*Vercel admin view:*
- Filter: [All] [New Course Dev] [Recurring]
- Badge on each session: 🔵 New Course Dev / 🟢 Recurring
- Assign button per session → picks from active ID Assistants
- Unassigned sessions highlighted

*Vercel ID Assistant view:*
- Shows only sessions where `assigned_to = my_id`
- Separated into: "New Course Dev" (needs validation, may loop through remediation) and "Recurring" (validation only, no remediation)
- Progress indicator per session

*Post-validation routing by audit_purpose:*
- `self_audit` (new course dev): ID Asst disagrees → `revisions_required` → back to ID for remediation
- `recurring`: ID Asst disagrees → findings logged, admin notified for faculty outreach. No remediation loop.

*Smart remediation (discussed, not yet implemented):*
- Audit identifies problems at standard level ("96 images missing alt")
- Remediation skill does focused re-scan at element level (finds every specific image)
- ID says "fix Standard 22" → skill re-audits just that issue, generates fixes, stages, pushes
- Checkbox "needs remediation" stays for data tracking (how many flagged vs fixed)

*Manual-entry fields:*
- Some criteria can't be checked via API: Ally score (B-22.9), SCOUT results (B-22.10), Readability (B-22.11)
- Add text input on FindingCard when criterion is N/A due to "requires manual tool"
- Value stored in `finding_feedback.corrected_finding` or new `manual_value` field
- `airtable_sync.py` picks up manual values and writes to corresponding Airtable column

**Completed (cont.):**
- Migration 007: `assigned_to` on audit_sessions — done, SQL run
- Vercel admin assign UI — dropdown per session on home page
- Vercel admin views — Needs Attention (default) + All Sessions toggle
- Vercel ID Asst dashboard — filters by `assigned_to = me`
- ID Assistant Agree/Disagree — post-remediation buttons: "Agree — Fix Verified" / "Disagree — Not Fixed"
- Manual-entry text fields — amber input box for Ally/SCOUT/readability scores, saves to finding_feedback
- Deterministic evaluator — criterion_evaluator.py produces complete audit JSON, guaranteed consistency
- Split scores — Readiness / Design / A11y shown separately in HTML report + Vercel session header

**Completed (Apr 2 code review — items previously listed as remaining):**
- ✅ IDA self-sync to Airtable — Vercel sync button is role-aware: IDA can sync after "complete" or "qa_approved", locked after sync, admin retains backup ability
- ✅ Change request flow — migration 008 run, Vercel API (GET/POST/PATCH), UI on FindingCard + admin queue on home page
- ✅ Admin sync visibility — sync badges on sessions home page
- ✅ Remediation tracker script — `remediation_tracker.py` fully functional (validates, records, clears)
- ✅ 6 remediation skills reference `remediation_tracker.py` — quiz, assignment-generator, discussion-generator, rubric-creator, interactive-content, bulk-edit
- ✅ 6 enforcement scripts built + tested — push_to_canvas, post_write_verify, audit_session_manager, remediation_tracker, admin_actions, assignment_status
- ✅ Admin actions audit trail — `admin_actions.py` logs to `logs/admin_audit.jsonl`
- ✅ Error messages — role_gate.py, canvas_api.py (401 handling), push_to_canvas.py all have clear, actionable messages
- ✅ Session completion logic — clarified and documented
- ✅ Vercel login + Airtable sync — tested end-to-end

**Completed (cont.):**
- IDA feedback isolation — IDA sees own action buttons, ID decision shown as context
- Airtable views — manually created (ID/IDA, ID Assistant, Admin Summary)
- Vercel deployment — main domain working

**Still remaining — Phase 5 completion (updated 2026-04-02):**

*1. ✅ DONE — Airtable sync uses IDA corrections:*
Fixed `build_airtable_row()` + `_generate_notes()` to check `feedback_map` for each finding. If IDA marked `decision = 'incorrect'`, uses `corrected_finding` as verdict and `correction_note` as notes.

*2. ✅ DONE — Enforcement script wiring:*
All skills now reference their enforcement scripts:
- `staging/SKILL.md` → `push_to_canvas.py` (replaced `canvas_api.update_page()`)
- `audit/SKILL.md` → `audit_session_manager.py --create` (replaced inline purpose inference)
- `admin/SKILL.md` → `admin_actions.py` (replaced inline Supabase PATCH + role_gate.py --register)
- `assignments/SKILL.md` → `assignment_status.py` (replaced inline Supabase PATCH)
- bulk-edit, quiz, discussion-generator, assignment-generator, rubric-creator, interactive-content → `remediation_tracker.py` ✅

*3. ✅ DONE — audit_report.py --local-only flag + syntax fix:*
- Added `--local-only` flag: generates HTML/XLSX report without pushing to Supabase (for progress checks)
- Fixed f-string syntax error (backslashes in JS regex broke Python 3.9 compilation — script was non-functional)
- Fixed `Path | None` type hint (requires `from __future__ import annotations` for Python 3.9)

*4. ✅ DONE — Remediation event batch fetch:* Fixed (dead code cleanup, Supabase .in() query works correctly)

*5. ✅ DONE — Error message polish:* Sync errors show HTTP status + response. "Report error" mailto link with session context. Confidence filter added (All / Low / High).

*6. ✅ DONE — Optional report generation:* Audit skill asks "Generate report?" after audit. Yes = HTML + Supabase. No = results in conversation only.

*7. ✅ DONE — Confidence filter:* Session page filter for IDs/Admins: All / Low (verify) / High. Low-confidence findings flagged with red badge.

*8. Smart remediation:* Deferred — ID maintains full control via manual /bulk-edit. Element-level auto-fix risky for judgment calls (alt text, content quality).

**Remaining code items: NONE — all Phase 5 code complete**

*9. ✅ DONE — Session grouping in Vercel app:*
Sessions grouped by `course_id` + `audit_purpose`. Latest round expanded, prior rounds in collapsible `<details>`. Score trend shown inline (41% → 65% → 78%). Round count displayed ("Round 3 of 5"). All existing filters (status, purpose, search, sort) respected. Build passes with zero TS errors. Commit `3fd59b5` in idw-review-app.

*Session completion logic (CLARIFIED):*
- "Mark Complete" = "I've reviewed every finding." That's the only requirement.
- Any mix of Correct/Incorrect/Agree/Disagree/N/A is valid — all are review outcomes.
- Incorrect means "AI was wrong" — no fix needed, not a blocker.
- Disagree means "ID's fix didn't work" (post-remediation only) — triggers revisions_required → back to ID.
- After Mark Complete, routing depends on whether any Disagrees exist:
  - No Disagrees → ready to sync to Airtable
  - Has Disagrees (new course dev) → session status: revisions_required → ID re-remediates → ID Asst re-validates
  - Has Disagrees (recurring) → sync anyway, findings logged as-is (no remediation in recurring)

*Col B criteria needing human verification (22 total, low confidence):*
The Python evaluator handles these deterministically but gives default answers. Flagged with `confidence: low` and red badge in UI.

Quality judgment (can't assess content quality):
- **B-13.1-13.8** Content quality, typos, formatting, completeness, design practices
- **B-13.10** Text free of typos
- **B-13.14** Text not too dense

Reading comprehension (can't verify meaning):
- **B-06.1** Workload details provided — checks length but not content
- **B-06.2** Time commitments clearly communicated
- **B-09.1** Assessment instructions clearly explain
- **B-22.5** Hyperlinks use descriptive meaningful text

Cross-reference checks (can't compare across sources):
- **B-04.7** Template personalization/customization
- **B-04.14** Grade breakdown in syllabus
- **B-09.6** Grade breakdown alignment with syllabus
- **B-17.1** Moderation policy exists
- **B-17.2** Response turnaround time specified

External tools required (manual entry fields):
- **B-22.9** Ally accessibility score
- **B-22.11** Readability score

Manual review (criteria undefined for pilot):
- **B-24.1** Mobile/offline access specifications — collecting ID feedback during pilot
- **B-17.1** Moderation policy — evaluator checks discussion exists but can't verify policy content
- **B-17.2** Response turnaround time — evaluator searches for keywords but may miss
- **B-22.9** Ally score — requires Ally dashboard (manual entry field)
- **B-22.11** Readability score — requires readability tool (manual entry field)

These should be flagged with `confidence: low` in the evaluator output so the FindingCard shows a visual indicator ("⚠ Verify" badge) prompting the reviewer to double-check.

*Standard exclusions:*
- **Standard 23** (Tool Accessibility): Excluded from audits. All external tools must pass ASU accessibility standards before approval. Always Met by policy.
- **Standards 05, 14**: Design audits only (Col C, ID reviews). Not ID Assistant scope.

*Optional report generation:*
- Audit skill should ask "Generate HTML report?" after audit completes
- New course dev IDs iterate many times before submitting for QA review — they don't need a report every run
- Report generation also pushes to Supabase which creates a new session — wasteful for iterative audits
- Options: "Yes — generate report + push to Supabase" / "No — just show results in conversation"
- criterion_evaluator.py `--quick-check` and `--full-audit` should support `--no-report` flag to skip audit_report.py
- This keeps iterative audits lightweight while still producing reports when ready for review

*Session status after admin override (manual for pilot):*
- Admin changes verdict from change request → admin re-syncs to Airtable
- Recurring: stays complete, admin re-syncs
- New course dev: admin manually reopens if needed (has Undo/Reopen buttons)

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
- ID Assistant validation loop working end-to-end
- IDA review workflow validated (assign → verdict → override → sync)

### Pre-launch operational checklist (non-code)

**Moved to standalone document:** `~/Desktop/SCOUT-ULTRA-Pilot-Ops-Checklist.md`
Covers user provisioning, credential distribution, communication, rollback testing, post-launch rhythm, known limitations, and success criteria. Brent owns all operational items.

**Previously tested:**
- [x] Verify login works for all registered users (Supabase Auth + testers table match) ✅
- [x] Test "Mark Complete" → sync → Airtable row appears correctly ✅

---

### Phase 5.5 — Pilot Launch Implementation Plan (updated 2026-04-02)

Three sub-phases: code → prep → go-live. Each phase must complete before the next starts.

#### Phase 5.5a — Remaining Code (Claude + Brent, ~4 hours)

| # | Task | Owner | Effort | Status |
|---|---|---|---|---|
| 1 | ✅ DONE — Session grouping in Vercel (group by course, collapse rounds, score trend) | Claude + Brent | 3-4 hrs | Commit 3fd59b5 |
| 2 | ✅ Remediation event batch fetch | — | — | Done |
| 3 | ✅ Error message polish (sync errors, report link, confidence filter) | — | — | Done |
| 4 | ✅ Progress check prompt in audit skill (`--local-only`) | — | — | Done |
| 5 | Test rollback end-to-end on sandbox | Brent | 30 min | **REMAINING — manual test** |
| 6 | ✅ HTML report score layout (compact, matches Vercel app) | — | — | Done |

**Exit criteria:** Session grouping deployed. Rollback verified.

#### Phase 5.5b — User Provisioning & Credentials (Brent, ~3 hours)

| # | Task | Owner | Effort | Notes |
|---|---|---|---|---|
| 1 | Compile pilot user list: name, email, role (id / id_assistant / admin) | Brent | 30 min | Get from QA team lead |
| 2 | Batch-register testers in Supabase `testers` table | Brent + Claude | 30 min | `python3 scripts/admin_actions.py --register` per user |
| 3 | Register same users in Supabase Auth (email+password) | Brent | 30 min | Supabase dashboard → Authentication → Users |
| 4 | Confirm Canvas token permissions — can all IDs generate personal access tokens? | Brent | 15 min | Check with Canvas admin if unsure |
| 5 | Confirm Claude Code access — all pilot users have Anthropic accounts/licenses | Brent | 15 min | Check org plan |
| 6 | Pre-assign IDAs to courses via `/assign` | Brent + Claude | 30 min | Requires user list + course list |
| 7 | Prepare `.env` template + `.env.local` with Supabase keys | Claude | 15 min | Claude generates, Brent fills in secrets |
| 8 | Distribute credentials to users (Slack DM or 1-on-1 setup) | Brent | 30 min | Each user gets: `.env` template, `.env.local`, their `IDW_TESTER_ID` |

**Exit criteria:** All users registered in both Supabase tables (testers + Auth). All users have credentials. All IDAs assigned to at least one course.

#### Phase 5.5c — Communication & Go-Live (Brent + Claude, ~2 hours)

| # | Task | Owner | Effort | Notes |
|---|---|---|---|---|
| 1 | Create Slack feedback channel (e.g., `#scout-ultra-pilot`) | Brent | 5 min | |
| 2 | Write quick-start guide (`ONBOARDING.md`) | Claude (draft) → Brent (review) | 1 hr | "Your first 10 minutes" — setup, first audit, review findings |
| 3 | Write rollback instructions (1-pager) | Claude | 15 min | "If you pushed something wrong..." |
| 4 | Draft pilot kickoff message (Slack/email) | Claude (draft) → Brent (review) | 30 min | What the system does, links to guide, feedback channel, escalation path |
| 5 | Send kickoff message | Brent | 5 min | |
| 6 | Verify RLS policies with a non-admin test account | Brent | 15 min | Login as id_assistant, confirm they only see assigned sessions |

**Exit criteria:** Kickoff message sent. Users have the guide. Feedback channel exists. RLS verified.

#### Post-Launch Operational Rhythm (ongoing during pilot)

| Cadence | Task | Owner |
|---|---|---|
| Daily (week 1) | Check Slack feedback channel for blockers | Brent |
| Daily (week 1) | Check error queue via `/admin` → Error Queue | Brent |
| Weekly | Review RLHF agreement rates via `/admin` → RLHF Stats | Brent |
| Weekly | Triage and fix reported bugs | Brent + Claude |
| Bi-weekly | Update enrichment cards for standards with <70% agreement | Brent + Claude |
| Ad-hoc | Re-assign courses as IDAs complete their queues | Brent |
| Ad-hoc | Run `/update-idw` (or `/update-scout` after rename) to push fixes to all users | Brent |

#### Timeline

```
Day 1-2:  Phase 5.5a — Code (session grouping, batch fetch, error polish)
Day 2-3:  Phase 5.5b — Provisioning (user list, register, credentials)
Day 3:    Phase 5.5c — Communication (guide, kickoff message, go-live)
Day 4:    🚀 Pilot launches
Week 1:   Daily monitoring, rapid bug fixes
Week 2+:  Weekly rhythm, enrichment card updates, RLHF analysis
```

---

### Phase 6 — Faculty Outreach, Analytics & Prioritization

| Task | Details | Priority |
|---|---|---|
| Faculty outreach email templates | Template-based drafts from Airtable findings. Admin reviews + sends. Use standard-level notes as the email body. Include course name, top issues, specific action items. | High — QA team needs this for recurring course workflow |
| Draft generation in Claude Code | `/admin` or new `/outreach` skill generates email draft from a session's findings. Plain text, no jargon, grouped by priority (critical → important → enhancement). | High |
| Post-launch analytics | DWF (Drop/Withdraw/Fail) rates, grade distributions, summative/formative assessment analysis. IDs use this data for course improvements. Requires external data source from ASU institutional systems. | Medium — not blocking pilot, data source TBD |
| Course prioritization | Filter/sort courses by enrollment count, DWF rates to decide which courses to audit first. Airtable view + Claude Code `/admin` integration. Requires enrollment data. | Medium — depends on post-launch analytics data |
| Automated outreach triggers | Airtable automations that draft emails when findings reach certain thresholds (e.g., >5 Not Met standards). Admin still reviews before sending. | Low — manual outreach works for pilot scale |
| IDA audit vs ID Assistant audit comparison | Dashboard view comparing what the ID found vs what the ID Assistant found on the same course. Highlights discrepancies for training. | Medium — valuable for RLHF but not launch-blocking |

**Dependencies:**
- Post-launch analytics requires DWF/enrollment data from ASU systems (API or spreadsheet import)
- Faculty outreach requires a sending mechanism (ASU email system, or manual copy-paste from generated drafts)
- Course prioritization requires enrollment data + Airtable integration

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

## 17. System Rename: IDW QA → SCOUT ULTRA

### Rationale

The system has outgrown its original name. "IDW QA" (ID Workbench Quality Assurance) implies a narrow auditing tool. The system is now a full issue/project management platform — audit, findings management, remediation tracking, role-based workflows, analytics, and Airtable sync — used by IDs, QA team IDs, and student workers. "SCOUT ULTRA" aligns with the existing Airtable SCOUT ULTRA format and is already familiar to the team.

### Naming Map

| Current | New | Scope |
|---|---|---|
| `IDW QA` | `SCOUT ULTRA` | Display name everywhere |
| `idw-review-app` | `scout-ultra` | Vercel project name + repo |
| `idw-review-app.vercel.app` | `scout-ultra.vercel.app` | URL (after Vercel rename) |
| `IDW_TESTER_ID` | `SCOUT_TESTER_ID` | Environment variable (`.env`) |
| `idw_logger.py` | `scout_logger.py` | Module file + all imports |
| `idw_metrics.py` | `scout_metrics.py` | Module file + all imports |
| `idw_metrics.json` | `scout_metrics.json` | Metrics data file + `.gitignore` |
| `update-idw` (skill) | `update-scout` | Skill folder + name + command |
| `IDW-QA-*.mmd/.md` | `SCOUT-ULTRA-*.mmd/.md` | Document filenames in repo root |
| `rlhf-reports` (Supabase bucket) | `scout-reports` | Storage bucket (optional, low priority) |
| `/Users/bespined/claude-plugins/IDW-QA/` | `/Users/bespined/claude-plugins/scout-ultra/` | Directory path (last — breaks all absolute paths) |
| `/Users/bespined/Desktop/idw-review-app/` | `/Users/bespined/Desktop/scout-ultra/` | Vercel app directory path |

### What stays the same

- `qa-concierge` skill name — still accurate, QA is what users do
- Supabase table names (`audit_sessions`, `audit_findings`, `testers`, etc.) — renaming tables requires migrations and risks breaking the live review app
- Canvas API patterns — no naming dependency
- `role_gate.py`, `canvas_api.py`, `staging_manager.py`, etc. — script names that don't contain "idw"
- Standards/config YAML files — no naming dependency

### Migration Phases

#### Phase A: Internal code (no user-visible impact)

1. **Rename logger + metrics modules**
   - `scripts/idw_logger.py` → `scripts/scout_logger.py`
   - `scripts/idw_metrics.py` → `scripts/scout_metrics.py`
   - Update all `from idw_logger import` → `from scout_logger import` across ~25 scripts
   - Update all `from idw_metrics import` → `from scout_metrics import` across ~25 scripts
   - Keep backward-compat shims: `idw_logger.py` that imports from `scout_logger` (so old code doesn't break mid-transition)
   - Update `.gitignore`: `idw_metrics.json` → `scout_metrics.json`

2. **Rename env variable**
   - All scripts: `IDW_TESTER_ID` → `SCOUT_TESTER_ID`
   - Backward compat: read both, prefer `SCOUT_TESTER_ID`, fall back to `IDW_TESTER_ID`
   - Update `.env` template and setup instructions
   - Announce to testers: "Add `SCOUT_TESTER_ID=<your-id>` to `.env` — the old name still works but will be removed"

3. **Rename skill folder + command**
   - `skills/update-idw/` → `skills/update-scout/`
   - Update SKILL.md: `name: update-scout`, `> **Run**: /update-scout`
   - Update all CLAUDE.md and PLANNING.md references
   - Update metric tracking context: `'{"skill": "update-scout"}'`

4. **Update all SKILL.md metric tracking lines**
   - Every skill has: `python3 scripts/idw_metrics.py --track skill_invoked`
   - Change to: `python3 scripts/scout_metrics.py --track skill_invoked`

#### Phase B: Documentation + display names

5. **CLAUDE.md**: Replace all "IDW QA" → "SCOUT ULTRA", update script table, update skill table
6. **PLANNING.md**: Replace all "IDW QA" → "SCOUT ULTRA", update paths
7. **Skill SKILL.md files**: Replace "IDW QA" in descriptions and user-facing messages (qa-concierge greeting, admin panel title, etc.)
8. **Migration SQL comments**: Replace "IDW QA" → "SCOUT ULTRA" (cosmetic only)
9. **Rename root documents**: `IDW-QA-system.mmd` → `SCOUT-ULTRA-system.mmd`, etc.

#### Phase C: Vercel app + URLs (requires Vercel dashboard)

10. **Rename Vercel project**: `idw-review-app` → `scout-ultra` in Vercel dashboard
11. **Update domain**: `scout-ultra.vercel.app` (Vercel auto-assigns)
12. **Update all URL references** in scripts and skills: `idw-review-app.vercel.app` → `scout-ultra.vercel.app`
13. **Rename local directory**: `/Users/bespined/Desktop/idw-review-app/` → `/Users/bespined/Desktop/scout-ultra/`

#### Phase D: Repository + directory rename (last — highest impact)

14. **Rename GitHub repo**: `IDW-QA` → `scout-ultra` (GitHub Settings → rename)
15. **Rename local directory**: `/Users/bespined/claude-plugins/IDW-QA/` → `/Users/bespined/claude-plugins/scout-ultra/`
16. **Update all absolute paths** in skills that reference `/Users/bespined/claude-plugins/IDW-QA/`
17. **Update `.claude/` project references** (Claude Code project settings reference the directory path)
18. **Re-clone or `git remote set-url`** for all testers using the plugin

### Impact per file category

| Category | File count | Effort | Risk |
|---|---|---|---|
| Scripts (imports) | ~25 | Medium — bulk find/replace + backward compat shims | Low — internal only |
| Skills (SKILL.md) | 21 | Medium — metric lines + scattered references | Low — prompt text |
| Documentation (CLAUDE.md, PLANNING.md) | 3 | Low — find/replace | None |
| Root documents (.mmd, .md) | 5 | Low — git mv | None |
| Migration SQL | 8 | Low — comment-only changes | None |
| Environment variable | ~40 refs | Medium — backward compat needed | Medium — breaks auth if not careful |
| Vercel app | Separate repo | Medium — dashboard rename + local directory | Medium — URL changes break links |
| GitHub repo + directory | 1 | Low — but cascading path updates | High — breaks all absolute paths |

### Order of operations

```
Phase A (internal) → commit + push → have testers run /update-scout
Phase B (docs) → commit + push
Phase C (Vercel) → rename in dashboard → update URLs → commit + push
Phase D (repo/dir) → rename repo → update all absolute paths → commit + push → notify all testers to re-clone
```

### Backward compatibility period

- `IDW_TESTER_ID` accepted for 30 days after rename (scripts check both)
- `idw_logger.py` / `idw_metrics.py` shim files kept for 30 days
- `/update-idw` command keeps working for 30 days (redirects to `/update-scout`)
- After 30 days: remove all backward compat shims

---

## 18. Unresolved Questions (renumbered from 17)

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

## 19. Reference Files (renumbered from 18)

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
│   ├── audit_report.py                # Report generation + Supabase push (per-criterion)
│   ├── deterministic_checks.py        # Deterministic criterion checks
│   ├── preflight_checks.py            # Content validation
│   ├── staging_manager.py             # Local staging
│   └── ... (see CLAUDE.md for full list)
├── skills/
│   ├── audit/SKILL.md                 # Audit skill (needs 3-mode streamline + evidence)
│   ├── staging/SKILL.md               # Staging skill (needs simplification)
│   └── ... (21 skills total)
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
