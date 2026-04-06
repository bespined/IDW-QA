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
| `admin` | QA team leads | Assign courses, review overrides, manage testers, sync to Airtable |

## Key Features

- **3-mode audit**: Quick Check (deterministic only), Deep Audit (deterministic + AI), Guided Review (interactive walkthrough)
- **173 criteria**: 124 Col B (deterministic/existence checks) + 49 Col C (qualitative/judgment)
- **Staging workflow**: All HTML content changes go through stage → preview → approve → push. Nothing touches Canvas without user approval.
- **Enforcement scripts**: Critical operations (push, verify, session creation, remediation tracking, admin actions) go through Python scripts that enforce backup, verification, and audit trails.
- **RLHF feedback loop**: IDA verdicts feed back into the system — when the AI is wrong, corrections improve future audits via enrichment card updates.
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
| `PLANNING.md` | System design, data model, workflows, implementation phases |
| `config/standards.yaml` | 25 ASU standards with 173 criteria |
| `config/standards_enrichment.yaml` | Enriched criteria with examples and research |

## Version

**v1.0.0** — Pilot release

## License

Internal use only — ASU Online instructional design team.
