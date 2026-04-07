# Codex Mass Session Assign Plan

This plan is for Claude Code to replace the stale **course-level ID Assistant assignment** model with a **bulk session assignment** workflow in `idw-review-app`.

The live review workflow is already session-based via `audit_sessions.assigned_to`. This plan removes the admin/UI drift around `tester_course_assignments` and replaces it with an operationally useful bulk assignment flow.

Keep this work focused on assignment workflow alignment. Do not broaden it into unrelated admin redesign.

---

## Goal

Admins should assign ID Assistants to **review sessions**, not to courses.

The admin workflow should support:

- viewing unassigned sessions that are ready for review
- selecting one or many sessions
- assigning them to a specific active ID Assistant
- optionally reassigning or clearing assignments

The old course-assignment model should no longer be presented as the active pilot workflow.

---

## Why This Change Is Needed

The current system has two different assignment models:

1. **Live review workflow** — session-based
   - ID Assistant dashboard filters by `audit_sessions.assigned_to`
   - review actions enforce `assigned_to`
   - admin session assignment already exists in the main review view via `/api/session-assign`

2. **Stale admin workflow** — course-based
   - admin page still has a `Course Assignments` tab
   - it reads/writes `tester_course_assignments`
   - this appears to be a leftover from the earlier assumption that ID Assistants would have a broader course-assignment model

For pilot, the active workflow should be session-based end to end.

---

## Desired End State

### User-Facing Behavior

- Admin opens the review app
- Admin sees unassigned sessions that need ID Assistant review
- Admin can:
  - assign one session
  - assign multiple selected sessions
  - assign all currently filtered unassigned sessions
  - reassign selected sessions
  - clear assignment if needed

- ID Assistants continue to see only sessions assigned to them

### What Should No Longer Be the Active Workflow

- assigning an ID Assistant to a course as the primary review workflow
- course-assignment messaging in the admin UI
- `tester_course_assignments` as the main operational assignment surface

---

## Scope

### In Scope

- admin UI changes in `idw-review-app`
- admin session-assignment API support for bulk operations
- doc/workflow alignment around session assignment
- de-emphasizing or removing the course-assignment tab from the pilot workflow
- deprecating course-assignment-specific plugin/docs surfaces that are no longer part of the pilot workflow

### Out of Scope

- redesigning the full admin app
- changing ID Assistant review logic
- changing audit submission logic
- deleting database tables unless clearly safe and explicitly intended
- changing Airtable sync behavior

---

## Recommended Product Decision

For pilot:

1. **Promote bulk session assignment as the primary admin workflow**
2. **Replace the existing Course Assignments tab with a Session Assignments tab**
3. Keep `tester_course_assignments` only if it still serves an internal/non-pilot purpose
4. Do not present `tester_course_assignments` as the active assignment model for review work

If there is uncertainty about deleting course-assignment support, prefer:

- replace/deprecate in UI first
- keep backend table/routes temporarily
- document as legacy/internal-only

---

## Implementation Plan

### Phase 1 — Confirm Session Assignment Source of Truth

Review and use the existing session-based paths as the source of truth:

- [`/Users/bespined/Desktop/idw-review-app/src/app/page.tsx`](/Users/bespined/Desktop/idw-review-app/src/app/page.tsx)
- [`/Users/bespined/Desktop/idw-review-app/src/app/api/session-assign/route.ts`](/Users/bespined/Desktop/idw-review-app/src/app/api/session-assign/route.ts)
- any supporting auth helpers already used by those routes

Confirm:

- a session is assignable through `audit_sessions.assigned_to`
- the role/auth rules already work for admin
- session assignment is what drives the ID Assistant dashboard

### Phase 2 — Replace Course Assignments UI with Session Assignment UI

Update the admin page:

- [`/Users/bespined/Desktop/idw-review-app/src/app/admin/page.tsx`](/Users/bespined/Desktop/idw-review-app/src/app/admin/page.tsx)

Do this surgically:

- keep the existing admin page/tab layout intact
- replace the current `Course Assignments` tab with `Session Assignments`
- do not reshuffle tester management, error queue, or RLHF sections unless necessary

This reduces regression risk in the admin surface.

New admin assignment tab should focus on sessions:

- list sessions ready for assignment
- show key columns:
  - course name / code
  - session id or short id
  - audit purpose
  - round
  - run date
  - status
  - currently assigned IDA (if any)
- support filters:
  - unassigned only
  - assigned only
  - pending QA review
  - revisions required
  - by course
  - by assigned IDA

Add bulk controls:

- checkbox per row
- select all visible
- bulk assign selected to chosen IDA
- bulk clear selected assignments
- optional bulk reassign selected sessions

### Phase 3 — Add Bulk Session Assignment API

Use the existing session assignment route if it can be extended cleanly, or add a dedicated bulk route.

Preferred options:

1. extend:
   - [`/Users/bespined/Desktop/idw-review-app/src/app/api/session-assign/route.ts`](/Users/bespined/Desktop/idw-review-app/src/app/api/session-assign/route.ts)

or

2. add a dedicated bulk route, for example:
   - `/api/session-assign/bulk`

Requirements:

- admin auth only
- validate target tester is an active `id_assistant`
- validate all session ids exist
- update `audit_sessions.assigned_to`
- return per-session success/failure if partial failure handling is needed

Optional but recommended:

- support clearing assignment with `assigned_to = null`
- support idempotent behavior if a session is already assigned to that tester

### Phase 4 — De-emphasize Course Assignments

Review these stale surfaces:

- [`/Users/bespined/Desktop/idw-review-app/src/app/api/admin/assignments/route.ts`](/Users/bespined/Desktop/idw-review-app/src/app/api/admin/assignments/route.ts)
- [`/Users/bespined/Desktop/idw-review-app/src/app/api/admin/assignments/[id]/route.ts`](/Users/bespined/Desktop/idw-review-app/src/app/api/admin/assignments/[id]/route.ts)
- course-assignment sections in [`/Users/bespined/Desktop/idw-review-app/src/app/admin/page.tsx`](/Users/bespined/Desktop/idw-review-app/src/app/admin/page.tsx)
- [`/Users/bespined/claude-plugins/IDW-QA/skills/assignments/SKILL.md`](/Users/bespined/claude-plugins/IDW-QA/skills/assignments/SKILL.md)
- [`/Users/bespined/claude-plugins/IDW-QA/scripts/assignment_status.py`](/Users/bespined/claude-plugins/IDW-QA/scripts/assignment_status.py)

For pilot, choose one:

#### Option A — Preferred

- replace the course-assignment tab in the admin UI with the session-assignment tab
- leave backend routes/table in place temporarily but unused
- mark them legacy/internal-only in docs/comments if needed
- keep `/assignments` deprecated
- mark `assignment_status.py` as legacy/deprecated in docs if it is no longer part of the pilot workflow

#### Option B

- keep the tab only if it serves a separate staffing/planning purpose
- rename it clearly so it is not confused with review assignment
- remove it from the primary pilot workflow

### Phase 5 — Update Plugin and App Messaging

Update assignment-related docs/instructions so they consistently reflect session assignment:

- [`/Users/bespined/claude-plugins/IDW-QA/skills/assign/SKILL.md`](/Users/bespined/claude-plugins/IDW-QA/skills/assign/SKILL.md)
- [`/Users/bespined/claude-plugins/IDW-QA/skills/assignments/SKILL.md`](/Users/bespined/claude-plugins/IDW-QA/skills/assignments/SKILL.md)
- [`/Users/bespined/claude-plugins/IDW-QA/AGENTS.md`](/Users/bespined/claude-plugins/IDW-QA/AGENTS.md)
- [`/Users/bespined/claude-plugins/IDW-QA/CLAUDE.md`](/Users/bespined/claude-plugins/IDW-QA/CLAUDE.md)
- [`/Users/bespined/claude-plugins/IDW-QA/scripts/assignment_status.py`](/Users/bespined/claude-plugins/IDW-QA/scripts/assignment_status.py) documentation/comments if needed
- any review-app admin copy that still says “course assignments”

The message should be:

- admins assign ID Assistants to review sessions
- ID Assistants review sessions assigned to them
- course-level assignment is not the active pilot workflow
- `/assignments` and `assignment_status.py` are legacy/deprecated unless intentionally retained for non-pilot staffing/admin tracking

---

## Suggested UX for the New Admin Tab

Title:

- `Session Assignments`

Primary actions:

- `Assign Selected`
- `Clear Selected`
- optional `Assign All Visible`

Row columns:

- select checkbox
- course
- purpose
- round
- status
- run date
- assigned IDA

Inline row actions:

- assign dropdown
- clear assignment

Bulk action flow:

1. Admin selects sessions
2. Admin chooses an ID Assistant
3. Admin clicks `Assign Selected`
4. UI updates and shows success/error feedback

---

## Acceptance Criteria

### Functional

- Admin can bulk assign multiple sessions to one ID Assistant
- Admin can assign a single session without leaving the page
- ID Assistant dashboard continues to show only sessions assigned to them
- Clearing/reassigning assignments works cleanly

### Workflow Alignment

- No primary admin workflow in the app teaches course-level assignment for review work
- `/assign` in the plugin matches the session-based model
- review app assignment UX matches the real `assigned_to` workflow
- `/assignments` remains deprecated and `assignment_status.py` is not presented as part of the active pilot workflow unless explicitly justified

### Safety

- routes remain admin-protected
- target tester must be an active `id_assistant`
- invalid session ids fail cleanly
- assignment changes do not break ID Assistant filtering

---

## Verification Checklist

Claude should verify:

1. Admin can assign one unassigned session to an ID Assistant
2. Admin can bulk assign multiple unassigned sessions
3. Admin can clear an assignment
4. Assigned sessions appear on the correct ID Assistant dashboard
5. Sessions no longer appear as part of a course-assignment workflow in the admin UI
6. `npm run lint` passes
7. `tsc --noEmit --incremental false` passes
8. Tester management, error queue, and RLHF admin sections still work after the tab replacement

---

## Recommended Rollout Strategy

Do this in two safe steps if needed:

1. Add bulk session assignment and make it the prominent path
2. Replace/deprecate the course-assignment UI after verifying no pilot workflow depends on it

That reduces risk while still aligning the product with the real review process.
