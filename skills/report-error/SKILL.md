---
name: report-error
description: "Report a bug, wrong finding, crash, or issue with the plugin. Any role."
---

# Report Error

> **Run**: `/report-error`

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python3 scripts/idw_metrics.py --track skill_invoked --context '{"skill": "report-error"}'
```

## Purpose

Lets any authenticated user report bugs, incorrect findings, crashes, or other issues. Reports go to the `error_reports` table in Supabase where admins can triage them via `/admin`.

## Role Gate

This skill requires any authenticated role. Run:

```bash
python3 scripts/role_gate.py --check any
```

- If exit code is 0: proceed (capture the tester info from output)
- If exit code is 1: show the error and stop.

## Workflow

### 1. Gather Report Details

Ask the user conversationally. Use `AskUserQuestion` for the error type:

**Error type** (required):
- **Bug** — something isn't working as expected
- **Wrong Finding** — the audit produced an incorrect result
- **Crash** — the plugin crashed or threw an error
- **Other** — anything else

**Description** (required): Ask the user to describe what happened. Encourage specifics:
> What happened? Include what you were doing, what you expected, and what actually happened.

### 2. Auto-Capture Context

Automatically collect context from the current session — do NOT ask the user for these:

```python
context = {
    "skill": "<last skill invoked, if known>",
    "course_id": os.getenv("CANVAS_COURSE_ID", ""),
    "canvas_domain": os.getenv("CANVAS_DOMAIN", ""),
    "active_instance": os.getenv("CANVAS_ACTIVE_INSTANCE", "prod"),
    "plugin_version": "<from git rev-parse --short HEAD>",
    "timestamp": "<ISO 8601 UTC>"
}
```

Get plugin version:
```bash
git rev-parse --short HEAD 2>/dev/null || echo "unknown"
```

### 3. Submit the Report

```bash
python3 -c "
import json, os, sys, requests
from datetime import datetime, timezone
sys.path.insert(0, 'scripts')
from role_gate import _get_supabase_config

url, key = _get_supabase_config()
tester_id = os.getenv('IDW_TESTER_ID', '').strip() or None

row = {
    'reported_by': tester_id,
    'error_type': '<ERROR_TYPE>',
    'description': '<DESCRIPTION>',
    'context': <CONTEXT_DICT>,
    'status': 'open'
}

resp = requests.post(
    f'{url}/rest/v1/error_reports',
    headers={
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation',
    },
    json=row,
    timeout=15,
)
result = resp.json()
print(json.dumps(result, indent=2, default=str))
"
```

### 4. Confirm

After successful submission:

> **Bug report submitted.** Report ID: `<id>`. An admin will see this in the error queue. Thanks for helping improve the plugin!

### 5. Wrong Finding Shortcut

If the user says "this finding is wrong" or "the audit got this wrong" while reviewing findings, pre-fill:
- `error_type`: `wrong_finding`
- Include the finding ID, standard, and AI verdict in the context
- Ask only for a brief description of what's incorrect

## Error Handling

- Supabase unreachable: "Can't submit the report right now. Note it down and try again later, or tell your admin directly."
- No tester ID: still allow submission with `reported_by: null` — anonymous reports are better than no reports.
