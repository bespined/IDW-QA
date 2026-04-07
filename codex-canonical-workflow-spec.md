# Codex Canonical Workflow Spec

This file defines the intended end-to-end pilot workflow for `IDW-QA` and `idw-review-app`.

Its purpose is to reduce drift between:

- Claude Code skills
- Python enforcement scripts
- Vercel review app routes and UI
- onboarding/setup docs

When a doc, skill, UI, or script conflicts with this spec, treat that as workflow drift and resolve it against this file.

---

## Core Principle

The system has two primary execution surfaces:

1. **Claude Code / plugin**
   - used for audits, course analysis, remediation, staging, and Canvas changes

2. **Vercel review app**
   - used for reviewing findings, assigning ID Assistants, completing review lifecycle steps, and admin management

The plugin generates and fixes work.
The review app governs review workflow and session state.

---

## Roles

### `id`

Instructional designer or course builder using Claude Code and the review app.

Primary responsibilities:
- run audits
- review/correct uploaded findings in the portal
- submit sessions for QA review
- remediate issues in Claude Code

### `id_assistant`

Reviewer using the Vercel app only.

Primary responsibilities:
- review assigned sessions
- validate Col B findings
- complete review or request revisions

### `admin`

QA/admin user with access to both systems.

Primary responsibilities:
- create/manage testers
- run recurring or targeted QA audits
- assign sessions to ID Assistants
- approve/reject/reopen sessions
- monitor RLHF/admin workflows

---

## Identity Model

There is one shared tester identity model, used differently by each surface.

### Shared source of truth

Supabase `testers` row:
- `id`
- `name`
- `email`
- `role`
- `is_active`

### Review app identity

- user signs in with Supabase Auth
- app matches auth email to an active `testers` row
- role comes from `testers.role`

### Claude Code identity

- plugin reads:
  ```env
  IDW_TESTER_ID=<tester uuid>
  ```
- plugin resolves that UUID to the `testers` row
- name and role come from the tester row

### Rule

One human should map to one tester row.
The tester UUID is the Claude Code identity anchor.

---

## Onboarding Workflow

### Primary onboarding path: Vercel admin UI

1. Admin creates tester in Vercel.
2. System creates `testers` row.
3. System provisions review-app login.
4. If role is `id` or `admin`, the UI shows:
   ```env
   IDW_TESTER_ID=<uuid>
   ```
   for Claude Code setup.
5. If role is `id_assistant`, no Claude Code setup is required.

### Secondary onboarding path: Claude Code admin flow

1. Technical admin uses the admin skill/script.
2. Script creates the `testers` row.
3. UUID is returned.
4. Admin shares the UUID for Claude Code setup where needed.
5. This path must use the same identity model as Vercel, not a separate one.

### Role-specific onboarding expectations

#### `id_assistant`
- review app login only
- no `IDW_TESTER_ID` required for normal pilot use

#### `id`
- review app login
- `IDW_TESTER_ID` required for Claude Code

#### `admin`
- review app login
- `IDW_TESTER_ID` required if using Claude Code admin/audit workflows

---

## Course Connection Setup

Claude Code users must also connect Canvas:

1. configure `.env` with Canvas credentials
2. confirm the active course
3. optionally configure dev/prod course switching

This is separate from tester identity.

Canvas setup answers:
- which course am I connected to?

Tester setup answers:
- who am I?
- what role do I have?

---

## Audit Workflow

### Audit modes

Claude Code supports:
- Quick Check
- Deep Audit
- Guided Review

### Output choice is mandatory

After an audit completes, the user chooses from a context-dependent prompt.

**When portal upload is available** (`role_gate.can_upload_to_portal()` returns `True`), present 3 options:

1. **Just show results**
2. **Generate report (local only)**
3. **Upload to QA portal**

**When portal upload is unavailable** (`role_gate.can_upload_to_portal()` returns `False`), present 2 options only:

1. **Just show results**
2. **Generate report (saved locally)**

With a note: "Portal upload unavailable — requires Supabase credentials and tester identity. Run /setup to enable."

Portal upload requires both Supabase configuration (`SUPABASE_URL` + `SUPABASE_SERVICE_KEY` in `.env.local`) and tester identity (`IDW_TESTER_ID` in `.env`). If either is missing, the upload option is not shown. This conditional prompt is a specified behavior, not drift — presenting the upload option when it cannot succeed leads to confusing errors. The 2-option prompt is a deliberate reduction.

This choice must happen before any report generation or Supabase upload.

### Meaning of each option

#### 1. Just show results
- summary only in conversation
- no report
- no portal session

#### 2. Generate report (local only)
- HTML report saved locally
- no portal session
- no Supabase review workflow

#### 3. Upload to QA portal
- HTML report saved
- findings uploaded to Supabase
- review session created in Vercel
- this is a portal handoff, not final QA submission

---

## Audit Purpose Rules

`audit_purpose` should reflect why the session exists.

### `self_audit`

Use when:
- an `id` audits their own course and uploads findings

### `recurring`

Use when:
- an `admin` runs a batch/recurring QA sweep and uploads sessions for review

### `qa_review`

Use when:
- an `admin` or QA user audits/reviews a specific course in a targeted review context

### Rule

Do not rely on implicit defaults when the workflow already knows the purpose.
Stamp the intended purpose explicitly when generating audit JSON for upload.

---

## ID Audit Flow

1. ID connects to Canvas in Claude Code.
2. ID runs `/audit`.
3. ID chooses audit mode.
4. Audit runs.
5. ID chooses output mode.
6. If the ID chooses **Upload to QA portal**:
   - portal session is created
   - `audit_purpose = self_audit`
   - session starts in `in_progress`
7. ID opens the portal session.
8. ID reviews/corrects findings in the portal.
9. ID clicks **Submit for QA Review** in the portal.
10. Session becomes `pending_qa_review`.

### Important wording rule

Claude-side upload is **not** the same as portal-side “Submit for QA Review.”
The upload step is a handoff into the portal workflow.

---

## Admin Recurring Audit Flow

1. Admin runs `/audit`.
2. Admin chooses **Batch audit**.
3. Admin pastes one course ID or Canvas URL per line.
4. Claude audits the listed courses sequentially.
5. Claude shows a batch summary.
6. Admin chooses:
   - results only
   - local reports only
   - upload all to QA portal
7. If uploaded:
   - sessions are created in the portal
   - `audit_purpose = recurring`
   - sessions are attributed to the admin as auditor
8. Admin assigns sessions to ID Assistants in the review app.

### Batch input format

Accepted input:
- one course ID per line
- or one Canvas course URL per line
- optional labels/course names allowed on each line

Examples:

```text
252193
251884
https://canvas.asu.edu/courses/252001
252400 LAW 517 Torts
```

---

## Admin Targeted QA Review Flow

1. Admin runs `/audit` on a specific course.
2. Admin chooses upload.
3. Session is created with:
   - `audit_purpose = qa_review`
4. Session enters the portal workflow as a targeted admin review artifact.

This is distinct from recurring batch QA sweeps.

---

## Session Assignment Workflow

The live review workflow is session-based, not course-based.

### Rule

ID Assistants are assigned to **sessions**, not to courses, for pilot review work.

### Admin actions

Admins can:
- assign one session
- bulk assign multiple sessions
- clear assignment / reassign

### Source of truth

Session assignment is driven by:
- `audit_sessions.assigned_to`

Not by:
- `tester_course_assignments` as a user-facing pilot review mechanism

Course-level assignments may still exist for admin/internal tracking, but they are not the primary live review workflow.

---

## ID Assistant Review Flow

1. ID Assistant signs into the Vercel app.
2. They see only sessions assigned to them.
3. They review Col B findings.
4. They can mark the session:
   - `complete`
   - or `revisions_required`
5. If `complete`, the session is ready for the next downstream action.
6. If `revisions_required`, the session goes back to the ID workflow.

### Rule

ID Assistants do not use Claude Code for pilot review workflow.

---

## Admin QA Decision Flow

After the relevant portal review work is complete:

1. Admin reviews the session in the review app.
2. Admin can:
   - approve
   - request revisions
   - undo decision if needed
3. Approved sessions may sync to Airtable or downstream reporting.

---

## Remediation Workflow

### Discovery

Findings marked for remediation are reviewed in the portal or fix queue.

### Execution

Claude Code performs remediation using the appropriate skill.

### HTML content rule

Any HTML content change must go through:

1. stage
2. preview
3. user approval
4. push
5. post-write verification

### Tracking

Remediation events must be recorded through the centralized remediation path.

---

## Ownership Boundaries

### Claude Code owns

- running audits
- generating audit JSON
- Canvas reads/writes
- remediation execution
- staging and push workflow

### Review app owns

- session review lifecycle
- role-based review UI
- session assignment
- change requests
- admin management
- session transitions and approval flow

### Shared system owns

- tester identity
- session/finding persistence
- audit metadata

---

## Non-Negotiable Workflow Rules

1. No portal upload without explicit user choice.
2. No review-app session should exist for “results only” or “local only” audits.
3. IDA review workflow is Vercel-only.
4. Session assignment is session-based.
5. `IDW_TESTER_ID` is required for Claude Code users (`id`, `admin`).
6. HTML content edits always require staging.
7. All protected state transitions and service-key operations must go through server/script-enforced paths.

---

## Drift Checklist

When reviewing a feature or bug, ask:

1. Which step of this canonical workflow does it belong to?
2. Which surface owns that step?
3. Does the current wording match the actual state transition?
4. Is the same rule described differently elsewhere?
5. Is a stale course-based, plugin-based, or auto-submit assumption reappearing?

If the answer is yes, fix the drift against this spec.

---

## Bottom Line

This is the intended pilot workflow:

- onboarding is role-aware
- audits are choice-based
- uploads hand off to the portal
- IDs review before QA submission
- admins assign sessions to IDAs
- IDAs review in Vercel only
- remediation happens in Claude Code

This file should be the baseline for future cleanup, review, and implementation planning.
