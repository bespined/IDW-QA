# IDW QA (SCOUT ULTRA) — Course Quality Assurance & Remediation Plugin

## Overview

IDW QA is a Claude Code plugin providing 21 focused skills for auditing, reviewing, and remediating WCAG-compliant Canvas LMS courses following ASU instructional design standards. It includes a guided concierge, course navigation, 3-mode quality auditing with semantic alt text validation, design review, staging/preview/push workflow, content remediation (quizzes, assignments, discussions, rubrics, interactives, syllabus), course configuration, RLHF feedback integration via Supabase, role-gated admin/ID Assistant workflows, and error reporting.

This is the QA-focused subset of ID Workbench, purpose-built for pilot testing with instructional designers who audit and remediate existing courses.

## Default Entry Point

When a user starts a conversation without specifying a skill, invoke `/qa-concierge`. This guides them through three modes:

1. **Audit** — Run a full quality check on a course
2. **Review** — Walk through findings and fix issues
3. **Search** — Find specific content in the course

IDs interact through natural conversation — the concierge routes to the right skill automatically. The 21 skills are the engine; the concierge is the steering wheel.

Users can still invoke any skill directly by name (e.g., `/audit`) — the concierge is the default, not a gatekeeper.

## Setup Gate

**Before using any skill**, check:

1. If `.env` does **not** exist at the plugin root (`<plugin_root>/.env`):
   - If running `qa-concierge`: it handles setup transparently within its flow. Proceed.
   - Otherwise: tell the user "Let me help you connect to Canvas first," then run inline setup (ask for API token + domain + course URL, write `.env`), and resume the original skill.
2. **Course confirmation** (for all skills except `qa-concierge`):
   - If `.env` has a course ID: fetch the course name via API, then confirm: *"You're connected to **[Course Name]** ([domain]). Is this the right course?"* → [Yes] / [Switch course].
   - If user says "Switch course": run `python scripts/setup_env.py --list-courses`, show numbered list, let them pick, update `.env`.
   - If no course ID in `.env`: show the course list automatically and let them pick.
   - **Skip this confirmation** if the user's message already names the course (e.g., "audit Module 3 for BIO 101") and it matches the active course.
3. If `course-config.json` does **not** exist in the current working directory:
   - For `qa-concierge` / `syllabus-generator`: config gets created during the flow. Proceed.
   - For remediation skills (`quiz`, `assignment-generator`, `discussion-generator`, `rubric-creator`, `interactive-content`): create a minimal config from the confirmed course.
   - For QA skills (`audit`, `course-review`): create a minimal config with just the course ID.
   - For staging/publishing skills (`staging`): only needs `.env` (domain + course ID). No `course-config.json` required.
   - For navigation/management skills (`canvas-nav`, `bulk-edit`, `course-config`, `media-upload`): only needs `.env`.

## Configuration

### Canvas Credentials (`.env` at plugin root)

All Python scripts and API operations read credentials from `.env` at the plugin root via `python-dotenv`. The file contains:

```
# Production instance
CANVAS_TOKEN=<personal access token>
CANVAS_DOMAIN=<canvas instance domain>
CANVAS_COURSE_ID=<course ID from URL>

# Dev / Sandbox instance (optional)
CANVAS_DEV_TOKEN=<dev access token>
CANVAS_DEV_DOMAIN=<dev instance domain>
CANVAS_DEV_COURSE_ID=<dev course ID>

# Active instance: "prod" or "dev" (default: prod)
CANVAS_ACTIVE_INSTANCE=prod

# Tester identity (for role-gated skills)
# Required for id and admin roles. ID Assistants don't need this.
# Get this UUID from the Vercel admin UI (primary) or admin_actions.py --register (secondary).
IDW_TESTER_ID=<tester UUID from admin>
```

**SECURITY**: Never display, log, or transmit the `CANVAS_TOKEN` or `CANVAS_DEV_TOKEN` values. If the user asks you to show it, remind them it is stored in `.env` and should not be shared.

### Pilot Onboarding

Testers are created in the **Vercel admin UI** (primary path) or via **Claude Code admin skill** (secondary path for technical admins). Both create the same `testers` row in Supabase.

- **ID Assistants** (`id_assistant`): Only need QA portal access. No Claude Code setup required.
- **IDs** (`id`): Need QA portal access + `IDW_TESTER_ID` in plugin `.env` for Claude Code.
- **Admins** (`admin`): Need QA portal access + `IDW_TESTER_ID` in plugin `.env` for Claude Code.

The Vercel admin UI provisions both the tester row and sends a login invite email. The UUID is shown after creation with a copy button.

### Supabase Credentials (`.env.local` at plugin root)

RLHF feedback loop credentials are stored separately from Canvas credentials:

```
SUPABASE_URL=<project URL>
SUPABASE_ANON_KEY=<anon public key>
SUPABASE_SERVICE_KEY=<service role key>
```

**SECURITY**: Never display or transmit Supabase keys. These are loaded by `audit_report.py` when the user chooses to submit findings for review.

### Multi-Instance Support

The plugin supports both production and dev/sandbox Canvas instances. Use the concierge or say 'switch to dev' to toggle between them or change courses mid-session. The active instance is stored in `CANVAS_ACTIVE_INSTANCE` in `.env`.

### Course Context (`course-config.json` in working directory)

When any skill needs module objectives, CLOs, course structure, assessment architecture, or grading information, read `course-config.json` from the current working directory. This is the **source of truth** for all "Required Inputs" referenced in skill files.

## RLHF Feedback Loop

After an audit completes, the user chooses what to do with the results. **The available options depend on whether portal upload is possible** — check `role_gate.can_upload_to_portal()`:

**When portal upload is available** (Supabase configured + `IDW_TESTER_ID` set):
1. **Just show results** — summary in conversation, no report, no upload
2. **Generate report (local only)** — HTML report saved to `reports/`, nothing uploaded
3. **Upload to QA portal** — HTML report saved AND findings uploaded to Supabase for the ID to review and correct in the QA portal

**When portal upload is unavailable** (missing Supabase config or tester identity):
1. **Just show results** — summary in conversation
2. **Generate report (saved locally)** — HTML report saved to `reports/`

With a note: "Portal upload unavailable — requires Supabase credentials and tester identity. Run /setup to enable."

Only option 3 (when available) enters the RLHF pipeline. Upload is a **portal handoff**, not final QA submission — the ID reviews and corrects findings in the portal, then clicks "Submit for QA Review" there. The review app then collects:
- **Agree** — AI got it right
- **Disagree** — AI was wrong; reviewer provides corrected verdict + explanation
- **N/A** — requires external tool (Ally, readability)

This feedback refines the audit prompts over time. The dashboard at `/dashboard` shows agreement rates by standard and reviewer activity.

## Page Content Edits — Staging Always Required

**ANY change to a Canvas page's HTML body — no matter how small — must go through staging before pushing.** This includes formatting fixes, structural corrections, copy edits, accessibility remediations, and template alignment. There are no exceptions.

The required flow for all page body changes:
1. **Apply fix** → write corrected HTML to `staging/{slug}.html`
2. **Screenshot** the staged page and show it to the user in conversation
3. **Wait for explicit approval** ("looks good", "push it", "approved") — never push on assumed approval
4. **Push** only after the user confirms

This applies equally to:
- Bulk remediations (e.g., fixing heading hierarchy across all modules)
- Single-page fixes (e.g., correcting alt text on one image)
- Any reformatting, restructuring, or content remediation

**Never push ANY HTML content directly to Canvas in a single step**, even when the fix is obvious or the user asked for the fix. Stage → show → wait → push.

This rule applies to ALL HTML body content across Canvas object types:
- **Pages** — wiki page body HTML
- **Assignment descriptions** — the HTML in the assignment description field
- **Quiz descriptions** — the HTML in quiz instructions/description
- **Discussion prompts** — the HTML message body of discussion topics

## Staging Workflow

Content-remediating skills (quiz, assignment-generator, discussion-generator, interactive-content, update-module, bulk-edit) stage pages locally instead of pushing directly to Canvas:

1. **Generate/Fix** — skill produces updated HTML content
2. **Stage** — write HTML via `staging_manager.py --stage --slug <slug> --html-file <file>`
3. **Unified Preview** — run `python3 scripts/unified_preview.py`, then `preview_start("staging-preview")`, open `http://localhost:8111/_unified_preview.html` and screenshot in conversation. For single pages, `http://localhost:8111/{slug}.html` is acceptable.
4. **Iterate** — user requests changes, page is re-staged, unified preview regenerated, and re-previewed
5. **Push** — when approved, `/staging` shows a diff, creates a backup, and pushes to Canvas

This gives users a review loop before anything touches Canvas. Skills support `--direct` to bypass staging.

## Script-Enforced Workflows (Mandatory)

**All Canvas writes and Supabase operations MUST go through the enforcement scripts below.** Do not use inline `python3 -c` commands or direct API calls for these operations. The scripts enforce backup, verification, audit trails, and state machine rules that prompt instructions cannot guarantee.

| Operation | Script | Replaces |
|---|---|---|
| Push page/assignment/quiz content | `python3 scripts/push_to_canvas.py` | Inline `canvas_api.update_page()` + manual backup + clear |
| Verify any Canvas write | `python3 scripts/post_write_verify.py` | Manual GET + confirm |
| Create/submit audit sessions | `python3 scripts/audit_session_manager.py` | Inline Supabase POST + purpose inference |
| Record remediation events | `python3 scripts/remediation_tracker.py` | Inline Supabase POST + flag clearing |
| Admin tester management | `python3 scripts/admin_actions.py` | Inline Supabase PATCH + no audit trail |
| Session assignment (admin) | `python3 scripts/admin_actions.py --assign-session` | Inline Supabase PATCH + no validation |

**Exceptions (metadata only — no HTML body):**
These can skip staging but **still require explicit user approval before pushing**. Always confirm the change with the user first — never push metadata silently.
- Quick metadata edits (rename, due date, points, submission type) — confirm → `canvas_api.py` directly.
- Interactive content file uploads — confirm → `deploy_interactives.py`.
- Quiz settings (attempts, shuffle, time limit) — confirm → direct API.
- Rubric creation — confirm → direct API.
- Course settings (publish, nav tabs, late policy) — confirm → direct API.

**If the edit touches HTML content that a student will read, it must go through staging.** When in doubt, stage it.

## Post-Push Verification (Required)

**After ANY operation that creates or modifies content in Canvas**, always run:

```bash
python3 scripts/post_write_verify.py --type <page|assignment|quiz|discussion> --slug <slug> or --id <id>
```

This fetches the object back from Canvas and confirms: exists, content length > 0, published status, point values, rubric attached. Display the output to the user.

Then **offer a live screenshot**: "Want me to screenshot how this looks in Canvas?" If yes, navigate to the Canvas URL and capture it.

## Quick Edits (No Skill Required)

For simple one-off changes to **metadata only** (not page HTML body), Claude should handle them directly via the Canvas API without invoking a full skill workflow. Examples:

- "Rename Module 3 to 'Membrane Biology'" → `PUT /courses/:id/modules/:id` with `module[name]`
- "Change the Module 2 quiz to 3 attempts" → `PUT /courses/:id/quizzes/:id` with `quiz[allowed_attempts]`
- "Update the due date on the Module 5 assignment to March 20" → `PUT /courses/:id/assignments/:id`

**Quick edits apply to metadata only — never to page HTML body.** If the change touches a page's body content in any way, it must go through staging.

**Safety gate**: Before making any quick edit, run `python scripts/canvas_api.py --check-write` or check `CANVAS_READ_ONLY` in `.env`. If read-only mode is enabled, inform the user.

## Delete Operations

Delete functions are available in `canvas_api.py`. **Before any delete**, always:
1. **Confirm with the user** — show exactly what will be deleted
2. **For bulk deletes** (3+ items), show the full list and get explicit confirmation
3. Pages are automatically backed up before deletion

## Page Design System

All content-generating skills that produce Canvas page HTML must follow the design system in `standards/page-design.md`. Canvas strips `<style>` blocks and most CSS classes, so all styling uses inline `style=""` attributes.

## ASU Template Flexibility (Critical)

IDs **do not build courses from scratch** — they receive a pre-built ASU Canvas DEV template and remediate it. The template contains MORE pages than any single course will use.

**Never assume all template pages are required.** Common adjustments:
- IDs may combine pages and delete unused ones
- Some modules may not need certain page types
- IDs may use external LTI tools instead of Canvas pages

**How IDW QA handles this:**
1. **Ask, don't assume** — when helping fix pages, ask which pages the ID is keeping
2. **Preflight skips deleted pages** — only check pages the ID is actively working on
3. **Canvas nav shows what's there** — use `/canvas-nav` to see actual module structure
4. **Respect the ID's choices** — help them structure content well rather than enforcing patterns

## Skills Reference

| Category | Skill | Trigger | Purpose |
|---|---|---|---|
| **Entry** | `qa-concierge` | `/qa-concierge` | Guided entry point — 3 modes: Audit, Review & Fix, Search |
| **Navigation** | `canvas-nav` | `/canvas-nav` | Browse the full course tree (modules → items) in conversation |
| **QA** | `audit` | `/audit` | 3-mode audit: design standards (25 ASU), accessibility (WCAG 2.1 AA), or launch readiness (CRC) |
| **Review** | `course-review` | `/course-review` | Expert instructional design review of a completed course |
| **Staging** | `staging` | `/staging` | Preview staged pages, push to Canvas with backup, or rollback |
| **Remediation** | `update-module` | `/update-module` | Modify a single module — add, replace, rearrange, or reorder content |
| **Remediation** | `bulk-edit` | `/bulk-edit` | Batch edits, page propagation, or bulk accessibility/branding fixes |
| **Remediation** | `course-config` | `/course-config` | Publish/unpublish, due dates, assignment groups, navigation tabs, late policy, grading |
| **Remediation** | `quiz` | `/quiz` | Fix quiz settings, add feedback, edit questions |
| **Remediation** | `rubric-creator` | `/rubric-creator` | Create or fix analytic rubrics (3-5 criteria, 4 levels) |
| **Remediation** | `discussion-generator` | `/discussion-generator` | Fix or create graded discussion prompts (5 types) |
| **Remediation** | `assignment-generator` | `/assignment-generator` | Fix or create assignments with rubrics |
| **Remediation** | `interactive-content` | `/interactive-content` | Fix or create interactive HTML activities (5 types + custom) |
| **Remediation** | `syllabus-generator` | `/syllabus-generator` | Fix or generate syllabus content (CRC compliance) |
| **Remediation** | `media-upload` | `/media-upload` | Upload media files to Canvas and embed in pages |
| **Knowledge** | `knowledge` | `/knowledge` | Local course content cache for search and Q&A |
| **Deprecated** | `assignments` | `/assignments` | DEPRECATED — IDAs use Vercel review app, not Claude Code |
| **Admin** | `assign` | `/assign` | Assign an ID Assistant to a review session (Admin role) |
| **All** | `report-error` | `/report-error` | Report bugs, wrong findings, crashes (any role) |
| **All** | `update-idw` | `/update-idw` | Pull latest plugin code, show changelog (any role) |
| **Admin** | `admin` | `/admin` | Error queue, RLHF stats, tester management (Admin role) |

## Python Scripts

All scripts are in `<plugin_root>/scripts/` and load credentials from `.env` automatically:

| Script | Purpose |
|---|---|
| `canvas_api.py` | Shared API utilities (auth, pagination, upload, pages, folders, multi-instance) |
| `setup_env.py` | Setup validation helper (test, validate, list courses, verify course) |
| `course_navigator.py` | Fetch and display full course tree (modules → items), cached with 5-min TTL |
| `audit_report.py` | Generate HTML audit reports. `--local-only` skips Supabase push. Without flag, pushes findings to Supabase for review. |
| `audit_pages.py` | Audit all pages for accessibility issues |
| `alignment_graph.py` | CLO→MLO→Material→Assessment alignment analysis |
| `preflight_checks.py` | Lightweight content-type validation |
| `preflight.py` | Pre-flight checklist — verifies env, credentials, and dependencies are ready |
| `diff_engine.py` | Unified diff and summary between two HTML strings |
| `backup_manager.py` | Save/list/restore page backups with SHA256 checksums |
| `staging_manager.py` | Stage pages locally in Canvas-like shell for preview |
| `vision_audit.py` | Extract and download page images for vision-based accessibility analysis |
| `deploy_interactives.py` | Upload HTML interactives to Canvas + patch pages |
| `upload_captions.py` | Upload VTT caption tracks to Canvas media objects |
| `add_transcripts.py` | Add expandable text transcripts to wiki pages |
| `generator.py` | Generate HTML interactive activity files |
| `course_content_cache.py` | Dump, refresh, and search local course content cache |
| `unified_preview.py` | Render all staged pages in one scrollable document |
| `idw_logger.py` | Shared structured logging |
| `idw_metrics.py` | Lightweight metrics/telemetry tracking |
| `role_gate.py` | Role gating helper — verify tester role before executing protected skills |
| `fetch_fix_queue.py` | Query Supabase for findings where remediation_requested=true |
| `rlhf_analysis.py` | Aggregate finding_feedback: agreement rate by standard, reviewer, criterion, trends |
| `airtable_sync.py` | Sync approved findings to Airtable SCOUT ULTRA format (one row per course, 25 standards) |
| `criterion_evaluator.py` | Hybrid criterion evaluator — evaluates all B-criteria deterministically, flags weak results with `needs_ai_verification` for AI re-check. `--quick-check` for Col B only, `--full-audit` for B+C with AI flags, `--purpose` to stamp audit metadata |
| `deterministic_checks.py` | Legacy deterministic checks (superseded by `criterion_evaluator.py` — do not call directly) |
| `build_checkpoint.py` | Save/restore audit progress checkpoints for long-running audits |
| `metrics_sync.py` | Sync usage metrics to Supabase for admin dashboard |
| `staging_server.py` | Local HTTP server for staging page previews (port 8111) |
| `template_manager.py` | Manage Canvas page templates for course building |
| `push_to_canvas.py` | **Atomic push wrapper** — backup → push → clear → verify → remediation trail (MANDATORY for all content writes) |
| `post_write_verify.py` | **Post-push verification** — fetches Canvas object back, confirms existence + properties (MANDATORY after every write) |
| `audit_session_manager.py` | **Audit session lifecycle** — deterministic purpose inference, round counting, session status transitions |
| `remediation_tracker.py` | **Centralized remediation events** — records events + clears flags atomically (replaces all inline Supabase POSTs) |
| `admin_actions.py` | **Audited admin operations** — tester registration, deactivation, role changes with audit log |
| `supabase_client.py` | Centralized Supabase config + PostgREST helpers (GET/POST/PATCH/upload). All scripts import from here. |
| `assignment_status.py` | **DEPRECATED** — course-level assignment status. Pilot uses session-based assignment via review app. |

## Migrations

All migrations are in `<plugin_root>/migrations/`. Run in order in the Supabase SQL Editor:

| Migration | Purpose |
|---|---|
| `001_phase2_schema.sql` | Phase 2: testers, tester_course_assignments, error_reports tables + new columns on audit_sessions, audit_findings, finding_feedback |
| `002_merge_qa_team_role.sql` | Merge qa_team role into admin (3 roles: id, id_assistant, admin) |
| `003_update_decision_enum.sql` | Decision values: correct/incorrect/not_applicable (backward compatible with old values) |
| `004_update_dashboard_views.sql` | Dashboard views: feedback_by_standard, reviewer_activity (new column names) |
| `005_allow_anon_remediation_toggle.sql` | RLS policy for anon key to update audit_findings.remediation_requested |
| `006_remediation_events.sql` | remediation_events table (tracks what was fixed, when, how, by whom) |
| `007_session_assignment.sql` | Add `assigned_to` on audit_sessions for ID Assistant session assignment |

## Review App API Routes

The Vercel review app (`idw-review-app`) has server-side API routes. All routes authenticate callers via SSR cookie auth (`src/lib/server/route-auth.ts`) and use the service key for DB writes (`src/lib/server/supabase-admin.ts`). Actor fields are derived server-side from auth.

| Route | Method | Required Role | Purpose |
|---|---|---|---|
| `/api/admin/testers` | POST | admin | Create tester (+ provision login invite) |
| `/api/admin/testers/[id]` | PATCH, DELETE | admin | Update/delete tester |
| `/api/admin/assignments` | POST | admin | Create course assignments (legacy — session assignment is primary) |
| `/api/admin/assignments/[id]` | DELETE | admin | Remove assignment |
| `/api/admin/errors/[id]` | PATCH | admin | Resolve error report |
| `/api/session-assign` | GET, POST | admin | List IDAs / assign to session (supports bulk: `session_ids` array) |
| `/api/session-complete` | POST | id only | Mark session complete — Col C auto-approves, Col B → pending_qa_review |
| `/api/session-transition` | POST | varies | Admin: approve/revisions/undo. IDA: complete/revisions/reopen |
| `/api/change-requests` | GET, POST, PATCH | varies | GET: admin (global) or auth+session_id; POST: admin/IDA; PATCH: admin |
| `/api/sync-airtable` | POST | any auth (owner/assigned check) | Trigger Airtable sync for a session |
| `/api/findings/remediation` | PATCH | id or admin | Toggle `remediation_requested` on a finding |
| `/api/remediation-events` | GET, POST | GET: any auth; POST: id/admin | Fetch or record remediation events |

## MCP Connectors

### Google Drive (`google_drive_search`, `google_drive_fetch`)
Search and fetch files from institutional Google shared drives for audit cross-referencing, source document comparison, and media sourcing.

### Claude in Chrome (Browser Automation)
Navigate Canvas for visual QA, screenshot verification, external link validation, and embed testing.

### Canvas REST API
All skills use the Canvas API for CRUD operations on pages, quizzes, assignments, discussions, modules, and course settings.

## Standards & Config

| File | Purpose |
|---|---|
| `standards/page-design.md` | Page design system: reusable HTML/CSS components |
| `standards/canvas-standards.md` | ASU Canvas course design standards |
| `standards/instructional-design.md` | ID frameworks (UDL, backward design, Mayer) |
| `standards/assessment-best-practices.md` | Assessment design guidelines |
| `standards/canvas-content-types.md` | Canvas REST API object reference |
| `config/standards.yaml` | 25 ASU Online Course Design Standards — base definitions |
| `config/standards_enrichment.yaml` | Enriched standards with measurable criteria and examples |
