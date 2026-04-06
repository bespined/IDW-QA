---
name: assign
description: "Assign an ID Assistant to a course for review. Admin role required."
---

# Assign IDA to Course

> **Run**: `/assign`

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python3 scripts/idw_metrics.py --track skill_invoked --context '{"skill": "assign"}'
```

## Purpose

Allows admins to assign student workers (role: `id_assistant`) to courses for RLHF verdict work — reviewing Col B findings and submitting verdicts in the Vercel review app. Creates a row in `tester_course_assignments` linking a tester to a course.

> **Role terminology**: In this plugin, `id_assistant` = student worker / instructional design assistant. The `id` role = QA-team instructional designer (ID Associate or full ID). The `id_assistant` role handles deterministic (Col B) findings only; the `id` role handles both Col B and Col C (qualitative) findings.

## Role Gate

This skill requires the `admin` role. Before doing anything else, run:

```bash
python3 scripts/role_gate.py --check admin
```

- If exit code is 0: proceed
- If exit code is 1: show the error message and stop.

## Workflow

### 1. Show Available ID Assistants

List all active ID Assistants:

```bash
python3 scripts/admin_actions.py --list-testers
```

Filter the output to show only `id_assistant` role testers.

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

### 3. Check for Duplicate & Create Assignment

**All assignment operations MUST go through `assignment_status.py`.** This enforces ownership checks and valid state transitions.

Check for existing assignments, then create:

```bash
# Check if already assigned (read operation)
python3 scripts/assignment_status.py --list

# Create the assignment via admin_actions (audited, logged)
python3 scripts/admin_actions.py --assign-course --tester-id <TESTER_ID> --course-id <COURSE_ID> --course-name "<COURSE_NAME>" --domain canvas.asu.edu
```

If a non-completed assignment exists, warn:
> **[ID Assistant name] is already assigned to this course** (status: in_progress, assigned Mar 15). Create another assignment anyway?

**Note:** If `admin_actions.py --assign-course` is not yet implemented, use `assignment_status.py` for status tracking after manual Supabase insert. The enforcement requirement is that all operations are logged and auditable.

### 5. Confirm

After successful creation, display:

> Assigned **[ID Assistant name]** to **[Course name]** ([domain], course [ID]).
> They'll see it in the review app at https://idw-review-app.vercel.app when sessions are submitted for this course.

### 6. Bulk Assignment

If the admin says "assign all IDAs to this course" or provides multiple names:
- Loop through each ID Assistant and create separate assignments
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
