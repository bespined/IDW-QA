---
name: assign
description: "Assign an IDA to a course for review. Admin role required."
---

# Assign IDA to Course

> **Run**: `/assign`

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python3 scripts/idw_metrics.py --track skill_invoked --context '{"skill": "assign"}'
```

## Purpose

Allows admins to assign IDAs (instructional design assistants) to courses for RLHF review. Creates a row in `tester_course_assignments` linking a tester to a course.

## Role Gate

This skill requires the `admin` role. Before doing anything else, run:

```bash
python3 scripts/role_gate.py --check admin
```

- If exit code is 0: proceed
- If exit code is 1: show the error message and stop.

## Workflow

### 1. Show Available IDAs

List all active IDAs from the testers table:

```bash
python3 -c "
import json, sys
sys.path.insert(0, 'scripts')
from role_gate import _get_supabase_config, _supabase_get

url, key = _get_supabase_config()
testers = _supabase_get(url, key, 'testers', {
    'role': 'eq.id_assistant',
    'is_active': 'eq.true',
    'order': 'name.asc'
})
print(json.dumps(testers or [], indent=2, default=str))
"
```

Present as a numbered list:
```
## Available IDAs
1. Alice Chen (alice@asu.edu)
2. Bob Smith (bob@asu.edu)
3. Carol Martinez (carol@asu.edu)
```

### 2. Identify the Course

The admin must provide:
- **Course ID** — the Canvas course ID (numeric)
- **Course name** — display name for the assignment
- **Canvas domain** — which Canvas instance (e.g., canvas.asu.edu)

If the admin has an active course in `.env`, offer it as a default:
> Assign to the current course (**BIO 101**, canvas.asu.edu, ID 12345)? Or specify a different course.

### 3. Check for Duplicate Assignments

Before creating, check if this IDA is already assigned to this course:

```bash
python3 -c "
import json, sys
sys.path.insert(0, 'scripts')
from role_gate import _get_supabase_config, _supabase_get

url, key = _get_supabase_config()
existing = _supabase_get(url, key, 'tester_course_assignments', {
    'tester_id': 'eq.<TESTER_ID>',
    'course_id': 'eq.<COURSE_ID>',
    'status': 'neq.completed'
})
print(json.dumps(existing or [], indent=2, default=str))
"
```

If a non-completed assignment exists, warn:
> **[IDA name] is already assigned to this course** (status: in_progress, assigned Mar 15). Create another assignment anyway?

### 4. Create the Assignment

```bash
python3 -c "
import json, os, sys, requests
sys.path.insert(0, 'scripts')
from role_gate import _get_supabase_config

url, key = _get_supabase_config()
admin_id = os.getenv('IDW_TESTER_ID', '').strip()

row = {
    'tester_id': '<TESTER_ID>',
    'course_id': '<COURSE_ID>',
    'course_name': '<COURSE_NAME>',
    'canvas_domain': '<CANVAS_DOMAIN>',
    'assigned_by': admin_id,
    'status': 'assigned'
}

resp = requests.post(
    f'{url}/rest/v1/tester_course_assignments',
    headers={
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation',
    },
    json=row,
    timeout=15,
)
print(json.dumps(resp.json(), indent=2, default=str))
"
```

### 5. Confirm

After successful creation, display:

> Assigned **[IDA name]** to **[Course name]** ([domain], course [ID]).
> They'll see it when they run `/assignments`.

### 6. Bulk Assignment

If the admin says "assign all IDAs to this course" or provides multiple names:
- Loop through each IDA and create separate assignments
- Show a summary table of all created assignments

### 7. Register New Tester

If the admin wants to assign someone who isn't in the system yet:

> That person isn't registered as a tester. Want me to add them?

Then use role_gate.py to register:
```bash
python3 scripts/role_gate.py --register --name "New Person" --email "new@asu.edu" --role id_assistant
```

After registration, proceed with the assignment.

## Error Handling

- Supabase unreachable: "Can't reach the review database."
- No active IDAs: "No active IDAs found. Register one first with `/assign` and provide their name, email, and role."
- Invalid course ID: "Course ID must be numeric."
