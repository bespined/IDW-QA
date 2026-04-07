---
name: admin
description: "Admin dashboard — error queue, RLHF stats, tester management. Admin role required."
---

# Admin

> **Run**: `/admin`

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python3 scripts/idw_metrics.py --track skill_invoked --context '{"skill": "admin"}'
```

## Purpose

Central admin panel for the IDW QA plugin. Provides access to error reports, RLHF agreement statistics, tester management, and system health — all from within Claude Code.

## Role Gate

This skill requires the `admin` role. Run:

```bash
python3 scripts/role_gate.py --check admin
```

- If exit code is 0: proceed
- If exit code is 1: show the error and stop.

## Entry Point

Present the admin menu using `AskUserQuestion`:

> **Admin Panel**
>
> 1. **Error Queue** — View and manage bug reports
> 2. **RLHF Stats** — Agreement rates and reviewer activity
> 3. **Manage Testers** — Add, deactivate, or list testers
> 4. **Session Assignments** — View and manage IDA session assignments
> 5. **System Health** — Plugin version, migration status, config check

---

## 1. Error Queue

### View Open Errors

```bash
python3 -c "
import json, sys
sys.path.insert(0, 'scripts')
from role_gate import _get_supabase_config, _supabase_get

url, key = _get_supabase_config()
errors = _supabase_get(url, key, 'error_reports', {
    'status': 'eq.open',
    'order': 'created_at.desc'
})
print(json.dumps(errors or [], indent=2, default=str))
"
```

Present as a table:

```
## Open Error Reports (N total)

| # | Type | Reporter | Description | Reported |
|---|------|----------|-------------|----------|
| 1 | bug | Alice Chen | Staging preview not loading... | Mar 25 |
| 2 | wrong_finding | Bob Smith | Standard 4.1 flagged but page... | Mar 24 |
```

### Actions on Errors

For each error, offer:
- **Acknowledge** — mark as `acknowledged` (admin is aware, working on it)
- **Resolve** — mark as `resolved` with resolution note
- **View context** — show the full `context` JSON

```bash
python3 -c "
import json, os, sys, requests
sys.path.insert(0, 'scripts')
from role_gate import _get_supabase_config
from datetime import datetime, timezone

url, key = _get_supabase_config()
admin_id = os.getenv('IDW_TESTER_ID', '').strip()

resp = requests.patch(
    f'{url}/rest/v1/error_reports?id=eq.<ERROR_ID>',
    headers={
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation',
    },
    json={
        'status': '<STATUS>',
        'resolved_by': admin_id,
        'resolved_at': datetime.now(timezone.utc).isoformat()
    },
    timeout=15,
)
print(json.dumps(resp.json(), indent=2, default=str))
"
```

### Filter Options
- Show all (including resolved): add `--all`
- Filter by type: "show crash reports only"
- Filter by reporter: "show Bob's reports"

---

## 2. RLHF Stats

Run the analysis script:

```bash
python3 scripts/rlhf_analysis.py --summary
```

Display the output — it includes:
- Overall agreement rate
- Agreement by standard (sorted worst to best)
- Agreement by reviewer
- Trend over time (by week)
- Standards needing prompt attention (agreement < 70%)

For deeper analysis:
```bash
python3 scripts/rlhf_analysis.py --by-standard
python3 scripts/rlhf_analysis.py --by-reviewer
python3 scripts/rlhf_analysis.py --trends
python3 scripts/rlhf_analysis.py --low-agreement --threshold 70
```

### IDA Quality Tracking

Track per-IDA override rates to identify where student workers need coaching or where the audit prompt is misleading them:

```bash
python3 scripts/rlhf_analysis.py --by-ida
```

This shows: for each `id_assistant` tester, the standards where their verdicts most frequently disagree with QA-team IDs. Present as:

```
IDA Quality Report

| IDA | Standard | Their Verdicts | Overrides | Agreement |
|-----|----------|---------------|-----------|-----------|
| Alice Chen | Standard 08 | 14 | 6 | 57% ⚠ |
| Alice Chen | Standard 22 | 11 | 1 | 91% ✓ |
```

Standards where an IDA has < 75% agreement are coaching opportunities — not dismissals. Offer to show the IDA's specific overrides for review.

### Enrichment Card Improvement Workflow

When a standard's agreement rate is below 70%, the audit prompt needs improvement. Walk through this workflow:

1. Show the standards below threshold: `python3 scripts/rlhf_analysis.py --low-agreement --threshold 70`
2. For each low-agreement standard, show the overridden findings with reviewer corrections:
   ```bash
   python3 scripts/rlhf_analysis.py --standard <ID> --show-overrides
   ```
3. Identify the pattern in disagreements (e.g., AI flags as Met when reviewers say Not Met)
4. Suggest enrichment card updates to `config/standards_enrichment.yaml`:
   - Add a new `considerations` entry addressing the edge case
   - Sharpen the `measurable_criteria` for the ambiguous criterion
   - Add a concrete `examples` entry showing the failing pattern
5. After updating the enrichment YAML, commit and tell the team to run `/update-idw`

---

## 3. Manage Testers

### List All Testers

```bash
python3 scripts/admin_actions.py --list-testers
```

### Register New Tester

**Primary path**: Create testers in the Vercel admin UI at the QA portal — it provisions both the tester row and the login invite in one step.

**Secondary path (Claude Code)**: For technical admins who prefer the CLI. All tester management MUST go through `admin_actions.py` — this enforces admin role verification and writes to the audit log.

```bash
python3 scripts/admin_actions.py --register --name "<NAME>" --email "<EMAIL>" --role <ROLE>
```

**Email is required** — it's used for QA portal login. The script will reject registration without an email.

After registration, show role-specific next steps:

**For `id` or `admin`:**
> Registered **[name]** as **[role]**. Their tester ID is: `<uuid>`
> Login invite sent to **[email]** (or auth user already exists).
>
> Claude Code setup (add to plugin `.env`):
> `IDW_TESTER_ID=<uuid>`

**For `id_assistant`:**
> Registered **[name]** as **id_assistant**. This user only needs the QA portal — no Claude Code setup required.
> Login invite sent to **[email]** (or auth user already exists).

**If registration fails:** The script rolls back the tester row if the login invite fails — no half-provisioned accounts are left behind.

### Deactivate Tester

```bash
python3 scripts/admin_actions.py --deactivate --tester-id <TESTER_ID>
```

### Change Role

```bash
python3 scripts/admin_actions.py --change-role --tester-id <TESTER_ID> --new-role <ROLE>
```

All operations are logged to `logs/admin_audit.jsonl` with caller ID and timestamp.

---

## 4. Course Assignments

### View All Assignments

```bash
python3 -c "
import json, sys
sys.path.insert(0, 'scripts')
from role_gate import _get_supabase_config, _supabase_get

url, key = _get_supabase_config()
assignments = _supabase_get(url, key, 'tester_course_assignments', {
    'order': 'status.asc,assigned_at.desc',
    'select': '*,testers(name,role)'
})
print(json.dumps(assignments or [], indent=2, default=str))
"
```

Present grouped by status (assigned → in_progress → completed).

### Quick Assign

From here, the admin can jump to `/assign` to create new assignments.

---

## 5. System Health

### Plugin Version

```bash
git log --oneline -1 && echo "---" && git describe --tags 2>/dev/null || echo "no tags"
```

### Migration Status

Check which migrations exist:
```bash
ls -la migrations/*.sql
```

Remind admin if any new migrations need to be run.

### Config Check

Verify required environment variables are set:

```bash
python3 -c "
import os, json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('$(pwd)/.env'))
load_dotenv(Path('$(pwd)/.env.local'))

checks = {
    'CANVAS_TOKEN': bool(os.getenv('CANVAS_TOKEN', '')),
    'CANVAS_DOMAIN': bool(os.getenv('CANVAS_DOMAIN', '')),
    'CANVAS_COURSE_ID': bool(os.getenv('CANVAS_COURSE_ID', '')),
    'SUPABASE_URL': bool(os.getenv('SUPABASE_URL', '')),
    'SUPABASE_SERVICE_KEY': bool(os.getenv('SUPABASE_SERVICE_KEY', '')),
    'IDW_TESTER_ID': bool(os.getenv('IDW_TESTER_ID', '')),
}
print(json.dumps(checks, indent=2))
"
```

Present as a checklist with checkmarks/X marks.

## Navigation

After any sub-panel action, offer to return to the admin menu or exit.
