---
name: assign
description: "Assign an ID Assistant to a review session. Admin role required."
---

# Assign ID Assistant to Session

> **Run**: `/assign`

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python3 scripts/idw_metrics.py --track skill_invoked --context '{"skill": "assign"}'
```

## Purpose

Allows admins to assign an ID Assistant to a **review session** for Col B verdict work. This mirrors the session assignment dropdown in the Vercel review app — the IDA sees the session in their dashboard and can begin verdicting findings.

> **Key distinction:** This skill assigns IDAs to **sessions** (specific audit runs), not to courses. The Vercel review app uses `audit_sessions.assigned_to` for this. The `tester_course_assignments` table is a separate admin tracking concept and is not part of the pilot review workflow.

## Role Gate

This skill requires the `admin` role. Before doing anything else, run:

```bash
python3 scripts/role_gate.py --check admin
```

- If exit code is 0: proceed
- If exit code is 1: show the error message and stop.

## Workflow

### 1. Show Unassigned Sessions

Query Supabase for sessions that need assignment (submitted but no IDA assigned):

```bash
python3 -c "
import json, sys
sys.path.insert(0, 'scripts')
from role_gate import _get_supabase_config, _supabase_get

url, key = _get_supabase_config()
sessions = _supabase_get(url, key, 'audit_sessions', {
    'status': 'in.(pending_qa_review,in_progress)',
    'assigned_to': 'is.null',
    'order': 'run_date.desc',
    'select': 'id,course_name,course_code,audit_purpose,audit_round,overall_score,run_date'
})
print(json.dumps(sessions or [], indent=2, default=str))
"
```

Present as a numbered list:

```
Unassigned Sessions:
 #  | Course                  | Purpose     | Round | Score | Date
 1  | BIO 101                 | self_audit  | 3     | 78%   | Apr 2
 2  | ENG 200                 | recurring   | 1     | 65%   | Apr 1
 3  | CHM 113                 | self_audit  | 1     | 44%   | Mar 31
```

If no unassigned sessions: "All sessions are assigned. Nothing to do."

### 2. Show Available ID Assistants

```bash
python3 scripts/admin_actions.py --list-testers
```

Filter to show only `id_assistant` role testers:

```
Available ID Assistants:
 1. Alice Chen (alice@asu.edu)
 2. Bob Smith (bob@asu.edu)
```

### 3. Assign IDA to Session

Ask the admin which session and which IDA, then assign:

```bash
python3 -c "
import json, sys, requests
sys.path.insert(0, 'scripts')
from role_gate import _get_supabase_config

url, key = _get_supabase_config()
resp = requests.patch(
    f'{url}/rest/v1/audit_sessions?id=eq.<SESSION_ID>',
    headers={
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation',
    },
    json={'assigned_to': '<TESTER_ID>'},
    timeout=15,
)
print(json.dumps(resp.json(), indent=2, default=str))
"
```

### 4. Confirm

After successful assignment:

> Assigned **[IDA name]** to review **[Course name]** (Round [N], [purpose]).
> They'll see this session in the review app at https://idw-review-app.vercel.app.

### 5. Bulk Assignment

If the admin says "assign Alice to all unassigned sessions":
- Loop through each unassigned session and assign
- Show a summary table of all assignments made

### 6. Register New Tester

If the admin wants to assign someone who isn't in the system yet:

> That person isn't registered as a tester. Want me to add them?

```bash
python3 scripts/admin_actions.py --register --name "New Person" --email "new@asu.edu" --role id_assistant
```

After registration, proceed with the session assignment.

## Error Handling

- Supabase unreachable: "Can't reach the review database."
- No active ID Assistants: "No active ID Assistants found. Register one first."
- Session already assigned: "This session is already assigned to [name]. Reassign anyway?"
- No unassigned sessions: "All sessions have been assigned."
