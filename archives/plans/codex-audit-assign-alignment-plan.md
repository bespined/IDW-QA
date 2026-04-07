# Codex Audit + Assign Alignment Plan

This plan is for Claude Code to make two narrow pilot-critical fixes:

1. Align `/audit` with the promised output-choice workflow.
2. Align `/assign` with the real admin session-assignment workflow in the Vercel review app.

Do not broaden scope beyond these two topics.

---

## Goal

The pilot promise and the actual experience must match:

- Running an audit should **not** create a review-app session until the user explicitly chooses **Generate report + submit for review**.
- `/assign` should describe and support assigning an ID Assistant to a **session**, not to a course.

---

## Fix 1: Audit Workflow Alignment

### Current Problem

The intended pilot workflow is:

1. Run the audit
2. Show results
3. Ask the user:
   - Just show results
   - Generate report (local only)
   - Generate report + submit for review
4. Only create a review-app session if the user explicitly chooses submission

But the current implementation/docs are still misaligned:

- [`skills/audit/SKILL.md`](/Users/bespined/claude-plugins/IDW-QA/skills/audit/SKILL.md) still says to create a session before any audit work.
- [`scripts/audit_session_manager.py`](/Users/bespined/claude-plugins/IDW-QA/scripts/audit_session_manager.py) creates `audit_sessions` rows immediately and returns a review URL.
- [`AGENTS.md`](/Users/bespined/claude-plugins/IDW-QA/AGENTS.md) still teaches the old "every audit automatically pushes findings and reports" workflow.

### Required End State

- `Just show results`:
  - no HTML report
  - no Supabase push
  - no `audit_sessions` row
  - no review-app URL

- `Generate report (local only)`:
  - local HTML report only
  - no Supabase push
  - no `audit_sessions` row
  - no review-app URL

- `Generate report + submit for review`:
  - HTML report generated
  - Supabase session/findings created
  - review-app URL returned

### File Targets

- [`skills/audit/SKILL.md`](/Users/bespined/claude-plugins/IDW-QA/skills/audit/SKILL.md)
- [`AGENTS.md`](/Users/bespined/claude-plugins/IDW-QA/AGENTS.md)
- [`CLAUDE.md`](/Users/bespined/claude-plugins/IDW-QA/CLAUDE.md)
- [`scripts/audit_session_manager.py`](/Users/bespined/claude-plugins/IDW-QA/scripts/audit_session_manager.py)
- [`scripts/audit_report.py`](/Users/bespined/claude-plugins/IDW-QA/scripts/audit_report.py) if the invocation order needs a narrow adjustment

### Implementation Steps

1. Update [`skills/audit/SKILL.md`](/Users/bespined/claude-plugins/IDW-QA/skills/audit/SKILL.md)
- Remove the instruction that says to create an audit session before any audit work.
- Make the execution order explicit:
  - run evaluator
  - show summary
  - ask output choice
  - if submit chosen: create session, then generate/push the review artifacts
- Keep the output-choice prompt mandatory for Quick Check and Deep Audit.
- Make Guided Review follow the same rule at the end: no review submission unless the user explicitly chooses it.

2. Update top-level docs
- Rewrite the RLHF section in [`AGENTS.md`](/Users/bespined/claude-plugins/IDW-QA/AGENTS.md) so it matches the choice-based workflow.
- Verify [`CLAUDE.md`](/Users/bespined/claude-plugins/IDW-QA/CLAUDE.md) and [`skills/audit/SKILL.md`](/Users/bespined/claude-plugins/IDW-QA/skills/audit/SKILL.md) all describe the same process.
- Remove XLSX from active pilot-facing language if it is no longer part of the intended workflow.

3. Fix session timing
- Do not create `audit_sessions` up front for every audit run.
- Create the session only in the explicit submission path.
- Keep the change narrow:
  - no evaluator refactor
  - no audit scoring changes
  - no report template rewrite

4. Check `audit_report.py` expectations
- Confirm whether it assumes a pre-existing `session_id`.
- If yes, adjust the documented invocation/order narrowly so session creation happens immediately before submission, not at audit start.
- Preserve existing submit behavior for the review path.

### Acceptance Criteria

- Running `/audit` no longer creates a Supabase session before the user chooses output mode.
- `Just show results` creates no session and no report.
- `Generate report (local only)` creates local HTML only and no session.
- `Generate report + submit for review` creates the review session and returns the review URL.
- [`AGENTS.md`](/Users/bespined/claude-plugins/IDW-QA/AGENTS.md), [`CLAUDE.md`](/Users/bespined/claude-plugins/IDW-QA/CLAUDE.md), and [`skills/audit/SKILL.md`](/Users/bespined/claude-plugins/IDW-QA/skills/audit/SKILL.md) all describe the same flow.

---

## Fix 2: `/assign` Session-Assignment Alignment

### Clarified Product Intent

`/assign` is **not** the deprecated IDA-facing skill.

- [`skills/assignments/SKILL.md`](/Users/bespined/claude-plugins/IDW-QA/skills/assignments/SKILL.md) is the deprecated ID Assistant Claude Code workflow.
- [`skills/assign/SKILL.md`](/Users/bespined/claude-plugins/IDW-QA/skills/assign/SKILL.md) should remain active for admins.

But `/assign` must describe the real workflow:

- Admin assigns an ID Assistant to a **session** for review
- This should mirror the Vercel review app’s session assignment behavior
- It should not describe the active workflow as assigning an ID Assistant to a course

### Current Problem

[`skills/assign/SKILL.md`](/Users/bespined/claude-plugins/IDW-QA/skills/assign/SKILL.md) still says things like:

- “Assign an ID Assistant to a course for review”
- creates a row in `tester_course_assignments`
- “They’ll see it in the review app when sessions are submitted for this course”

That does not match the live review-app UX, which is session assignment.

### Required End State

- `/assign` is an admin skill for assigning an ID Assistant to a **session**
- The wording matches the Vercel review app behavior
- No active user-facing instruction says the assignment workflow is course-based if pilot behavior is session-based

### File Targets

- [`skills/assign/SKILL.md`](/Users/bespined/claude-plugins/IDW-QA/skills/assign/SKILL.md)
- [`AGENTS.md`](/Users/bespined/claude-plugins/IDW-QA/AGENTS.md)
- [`CLAUDE.md`](/Users/bespined/claude-plugins/IDW-QA/CLAUDE.md)
- [`README.md`](/Users/bespined/claude-plugins/IDW-QA/README.md)
- [`SETUP.md`](/Users/bespined/claude-plugins/IDW-QA/SETUP.md) if it still describes the wrong assignment flow

### Implementation Steps

1. Rewrite [`skills/assign/SKILL.md`](/Users/bespined/claude-plugins/IDW-QA/skills/assign/SKILL.md)
- Change the purpose/description from course assignment to session assignment.
- Make the flow describe:
  - identify the target review session
  - list active ID Assistants
  - assign the selected IDA to that session
  - confirm that the session now appears in the IDA review workflow
- Remove or rewrite course-assignment language from the active flow.

2. Keep deprecated and active skills clearly separated
- [`skills/assignments/SKILL.md`](/Users/bespined/claude-plugins/IDW-QA/skills/assignments/SKILL.md) stays deprecated.
- `/assign` remains active for admins only.
- Do not let the two skills overlap in purpose.

3. Clean up docs
- Update any active docs/instruction tables that still describe `/assign` as course assignment.
- Keep `tester_course_assignments` references only if they are still used for internal/admin tracking.
- Do not present `tester_course_assignments` as the primary user-facing session review workflow unless the app truly depends on it.

### Acceptance Criteria

- `/assign` clearly means admin session assignment for IDA review.
- No active plugin doc tells users/admins that `/assign` is course assignment if the real workflow is session assignment.
- `/assignments` remains the deprecated IDA-facing skill.

---

## Out of Scope

Do not use this task to:

- refactor unrelated skills
- redesign RLHF data model
- rewrite audit report templates
- replace review-app route architecture
- remove internal tables unless they are directly blocking workflow alignment

Keep this pass surgical and pilot-focused.
