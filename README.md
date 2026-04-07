# SCOUT ULTRA

**Course Quality Assurance & Remediation System for Canvas LMS**

A Claude Code plugin + Vercel review app + Supabase backend + Airtable sync that gives instructional design teams a complete QA workflow: audit courses against 25 ASU design standards, review and verdict AI findings, remediate issues, and sync results to Airtable.

## System Architecture

```
Claude Code Plugin ──→ Supabase ──→ Vercel Review App ──→ Airtable
  (audit + fix)        (data)       (review + verdict)     (reporting)
```

| Component | What it does | Who uses it |
|---|---|---|
| **Claude Code Plugin** | Audit courses, fix content, stage/push changes | IDs, Admins |
| **Vercel Review App** | Review AI findings, submit verdicts, sync to Airtable | IDs, ID Assistants, Admins |
| **Supabase** | Stores sessions, findings, feedback, testers, assignments | All (backend) |
| **Airtable** | Final reporting — one row per course, 25 standards | QA team, leadership |

## Roles

| Role | Who | What they do |
|---|---|---|
| `id` | Instructional Designers, ID Associates | Build courses, run self-audits, remediate findings |
| `id_assistant` | Student workers | Verdict Col B findings in Vercel review app (do not use Claude Code) |
| `admin` | QA team leads | Assign sessions to IDAs, review overrides, manage testers, sync to Airtable |

## Key Features

- **Hybrid Quick Check**: Deterministic evaluator (106 B-criteria) + targeted AI verification for 12 criteria where regex can't reliably determine the result. `needs_ai_verification` flag drives the AI pass.
- **3-mode audit**: Quick Check (hybrid deterministic + AI), Deep Audit (all standards + AI), Guided Review (interactive walkthrough)
- **173 criteria**: 124 Col B (deterministic/existence checks) + 49 Col C (qualitative/judgment)
- **Granular finding statuses**: `Met`, `Not Met`, `Partially Met`, `not_applicable`, `needs_review`, `manual_entry` — no more overloaded N/A
- **Structured per-page evidence**: Findings include `affected_pages` with direct Canvas URLs and issue summaries, not just generic module links
- **Staging workflow**: All HTML content changes go through stage → preview → approve → push. Nothing touches Canvas without user approval.
- **Enforcement scripts**: Critical operations (push, verify, session creation, remediation tracking, admin actions) go through Python scripts that enforce backup, verification, and audit trails.
- **RLHF feedback loop**: IDA verdicts feed back into the system — when the AI is wrong, corrections improve future audits via enrichment card updates.
- **Full onboarding**: Both Vercel admin UI and Claude Code CLI can fully provision testers (tester row + login invite + UUID handoff).
- **Rollback**: Every push creates a backup. If something goes wrong, rollback restores the original content.

## 21 Skills

| Category | Skills |
|---|---|
| **Entry** | `qa-concierge` — guided entry point (start here) |
| **QA** | `audit`, `course-review` |
| **Staging** | `staging` — preview, push, rollback |
| **Remediation** | `quiz`, `assignment-generator`, `discussion-generator`, `rubric-creator`, `interactive-content`, `update-module`, `bulk-edit`, `course-config`, `syllabus-generator`, `media-upload` |
| **Navigation** | `canvas-nav`, `knowledge` |
| **Role-gated** | `assign` (Admin), `admin` (Admin) |
| **Utility** | `report-error`, `update-idw` |

## Getting Started

See [SETUP.md](SETUP.md) for installation and first-time setup.

## Documentation

| File | Purpose |
|---|---|
| `SETUP.md` | First-time setup guide (10 minutes) |
| `CLAUDE.md` | Plugin instructions — Claude reads this every session |
| `ENGINEERING.md` | Technical architecture, data model, enforcement scripts |
| `PLANNING.md` | System design, data model, workflows, implementation phases |
| `TROUBLESHOOTING.md` | Common issues and fixes |
| `config/standards.yaml` | 25 ASU standards with 173 criteria |
| `config/standards_enrichment.yaml` | Enriched criteria with examples and research |
| `codex-canonical-workflow-spec.md` | Intended end-to-end pilot workflow spec |
| `archives/plans/` | Completed implementation plans (8 plans archived) |

## Migrations

Run in order in the Supabase SQL Editor:

| Migration | Purpose |
|---|---|
| `001` – `008` | Phase 2 schema, roles, dashboard views, RLS, remediation events, session assignment, change requests |
| `009_affected_pages.sql` | JSONB column for structured per-page evidence on `audit_findings` |

## Version

**v1.3.0** — Hybrid Quick Check, account onboarding, QA coordinator review fixes

## License

Internal use only — ASU Online instructional design team.
