# SCOUT ULTRA — Setup Guide

Get up and running in 10 minutes.

## Prerequisites

- [Claude Code](https://claude.ai/code) installed (CLI, desktop app, or IDE extension)
- Canvas personal access token (Canvas → Account → Settings → New Access Token)
- Your tester credentials (provided by your admin) — optional for local-only audits

## Minimum Requirements by Use Case

| Use case | `.env` needed | `.env.local` needed |
|---|---|---|
| Quick Check (local) | `CANVAS_TOKEN`, `CANVAS_DOMAIN`, `CANVAS_COURSE_ID` | Not required |
| Deep Audit (local) | Same as Quick Check | Not required |
| Upload to QA portal | Same + `IDW_TESTER_ID` | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY` |
| Airtable sync | Same as portal | Same + `AIRTABLE_TOKEN`, `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_ID` |

You can run audits with just Canvas credentials — the audit skill detects missing Supabase config and offers local-only output options. Portal upload requires full credentials.

## 1. Clone the Plugin

```bash
git clone https://github.com/bespined/IDW-QA.git
cd IDW-QA
```

## 2. Create `.env`

Create a file called `.env` in the plugin root with your Canvas credentials:

```
CANVAS_TOKEN=<your personal access token>
CANVAS_DOMAIN=canvas.asu.edu
CANVAS_COURSE_ID=<your first course ID from the URL>

IDW_TESTER_ID=<your tester UUID — provided by admin>
```

**To get your tester UUID:** Your admin creates your account in the QA portal (Vercel admin UI). After creation, the admin copies your UUID and shares it with you. Only `id` and `admin` roles need this — `id_assistant` users only use the QA portal and don't need Claude Code setup.

**To find your course ID:** Open any course in Canvas. The number in the URL is the course ID:
`https://canvas.asu.edu/courses/123456` → course ID is `123456`

## 3. Create `.env.local`

Create a file called `.env.local` with the shared Supabase credentials (provided by your admin):

```
SUPABASE_URL=<provided by admin>
SUPABASE_ANON_KEY=<provided by admin>
SUPABASE_SERVICE_KEY=<provided by admin>
```

## 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

## 5. Start Using

Open Claude Code in the plugin directory and type:

```
/qa-concierge
```

This guides you through three modes:
- **Audit** — Run a quality check on your course
- **Review & Fix** — Walk through findings and fix issues
- **Search** — Find specific content in the course

## Quick Commands

| Command | What it does |
|---|---|
| `/qa-concierge` | Guided entry point (start here) |
| `/audit` | Run a course audit directly |
| `/staging` | Preview, push, or rollback staged content |
| `/admin` | Manage testers, assignments, errors (Admin only) |
| `/report-error` | Report a bug or wrong finding |
| `/update-idw` | Pull latest plugin updates |

## Review App

After submitting an audit for review, your findings appear in the review app:

**URL:** (provided by your admin)

Login with the email and password your admin set up for you.

## If Something Goes Wrong

- **Pushed bad content to Canvas?** Run `/staging` → choose Rollback → select the backup → restore
- **Canvas token expired?** Regenerate at Canvas → Account → Settings → New Access Token, update `.env`
- **Something broke?** Run `/report-error` to file a bug report, or post in the team Slack channel
- **Need help?** Ask your admin or post in the feedback channel

## Switching Courses

To work on a different course, update `CANVAS_COURSE_ID` in your `.env` file, or say "switch course" to the concierge.
