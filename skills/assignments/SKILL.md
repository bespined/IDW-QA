---
name: assignments
description: "DEPRECATED — ID Assistants use the Vercel review app, not Claude Code. This skill is inactive for pilot."
---

# My Assignments (DEPRECATED)

> **Status**: DEPRECATED for pilot. ID Assistants (id_assistant role) review findings in the Vercel review app at https://idw-review-app.vercel.app, not in Claude Code. Admins can view IDA assignments via the admin page in the review app or via `/admin` skill.
>
> If this skill is invoked, inform the user: "ID Assistant assignments are managed in the review app. Use `/admin` to manage assignments from Claude Code."
>
> **Run**: `/assignments`

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python3 scripts/idw_metrics.py --track skill_invoked --context '{"skill": "assignments"}'
```

## Purpose

Shows the current user their assigned courses, review progress, and pending work. This is the home base for knowing what to work on next.

> **Role terminology**: This skill is gated to `id_assistant` (student workers). In the broader system, `id_assistant` = instructional design student assistant; `id` = QA-team ID or ID Associate (full role). Student workers run recurring audits and verdict Col B findings only.

## Role Gate

This skill requires the `id_assistant` role. Before doing anything else, run:

```bash
python3 scripts/role_gate.py --check id_assistant
```

- If exit code is 0: proceed
- If exit code is 1: show the error message from the JSON output and stop. Do not continue.

## Workflow

### 1. Authenticate & Fetch Assignments

After passing the role gate, extract the tester ID from the `--check` output, then query Supabase for this user's assignments:

```bash
python3 -c "
import json, os, sys
sys.path.insert(0, 'scripts')
from role_gate import _get_supabase_config, _supabase_get

url, key = _get_supabase_config()
tester_id = os.getenv('IDW_TESTER_ID', '').strip()

# Get assignments with session counts
assignments = _supabase_get(url, key, 'tester_course_assignments', {
    'tester_id': f'eq.{tester_id}',
    'order': 'assigned_at.desc'
})
print(json.dumps(assignments or [], indent=2, default=str))
"
```

### 2. For Each Assignment, Get Session Stats

**Session type note**: `id_assistant` users run `recurring` audits only — they do NOT see `self_audit` sessions (those belong to the course owner). Filter sessions by `audit_purpose` when querying:

```python
sessions = _supabase_get(url, key, 'audit_sessions', {
    'course_id': f'eq.{course_id}',
    'audit_purpose': 'in.(recurring,qa_review)',  # id_assistant never sees self_audit sessions
    'order': 'run_date.desc',
    'limit': '5'
})
```

For each assigned course, query `audit_sessions` and `audit_findings` to show:
- Number of audit sessions for this course (recurring + qa_review only)
- Total findings awaiting review (findings with no feedback yet)
- Findings by verdict status
- Count of findings with `remediation_requested = true` (fix queue depth)

```bash
python3 -c "
import json, os, sys
sys.path.insert(0, 'scripts')
from role_gate import _get_supabase_config, _supabase_get

url, key = _get_supabase_config()
course_id = '<COURSE_ID>'  # Replace with actual

sessions = _supabase_get(url, key, 'audit_sessions', {
    'course_id': f'eq.{course_id}',
    'order': 'run_date.desc',
    'limit': '5'
})
print(json.dumps(sessions or [], indent=2, default=str))
"
```

### 3. Display Format

Present assignments as a clear summary table:

```
## Your Assignments

| # | Course | Status | Sessions | Pending Review | Assigned |
|---|--------|--------|----------|----------------|----------|
| 1 | BIO 101 (canvas.asu.edu) | In Progress | 2 sessions | 14 findings | Mar 15, 2026 |
| 2 | ENG 200 (canvas.asu.edu) | Assigned | 0 sessions | — | Mar 20, 2026 |
| 3 | CHM 113 (canvas.asu.edu) | Completed | 1 session | 0 findings | Mar 10, 2026 |
```

Then offer actions:
- "Switch to [course name]" — updates `.env` with that course's ID and domain
- "Start reviewing [course name]" — switches course and launches `/audit` or shows the fix queue
- "Work fix queue for [course name]" — switches course and runs `fetch_fix_queue.py` to pull remediation items
- "Mark [course name] as complete" — updates the assignment status

### 4. Status Updates

**All status changes MUST go through `assignment_status.py`.** This enforces ownership checks and valid state transitions (assigned → in_progress → completed).

When the user wants to update an assignment status:

```bash
python3 scripts/assignment_status.py --update --assignment-id <ASSIGNMENT_ID> --status <in_progress|completed>
```

The script validates: tester owns the assignment (or is admin), and the transition is valid (e.g., can't go from `completed` back to `assigned`).

### 5. No Assignments

If the user has no assignments, say:

> You don't have any course assignments yet. An admin needs to assign you to a course using `/assign`.

## Error Handling

- If `IDW_TESTER_ID` is not set: "Add your tester ID to `.env` — ask your admin for it."
- If Supabase is unreachable: "Can't reach the review database. Check your internet connection and `.env.local` credentials."
- If the user has the wrong role: show the role gate error message.
