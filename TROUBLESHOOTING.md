# IDW QA — Troubleshooting Guide

Common issues and how to fix them. For engineering details, see `ENGINEERING.md`.

---

## Canvas API Issues

### 401 Unauthorized
**Symptom:** "Unauthorized" or "Invalid access token" on any Canvas API call.
**Cause:** `CANVAS_TOKEN` expired or revoked.
**Fix:** Generate a new personal access token in Canvas → Profile → Settings → New Access Token. Update `.env`.

### 403 Forbidden
**Symptom:** API returns 403 on a specific course.
**Cause:** Token doesn't have access to that course (not enrolled as teacher/designer).
**Fix:** Verify course enrollment. Or use a different course ID.

### 429 Rate Limit
**Symptom:** API returns 429 after many rapid calls (common during full page body fetch).
**Cause:** Canvas rate limits (700 requests per 10 minutes typical).
**Fix:** The scripts use `timeout=30` but don't retry. Wait 60 seconds and re-run. For large courses (100+ pages), the evaluator fetches all bodies sequentially — this can take 2-3 minutes.

### 404 Course Not Found
**Symptom:** "The specified resource does not exist" on audit.
**Cause:** Wrong `CANVAS_COURSE_ID` in `.env`, or course was deleted.
**Fix:** Check the course ID in the Canvas URL: `canvas.asu.edu/courses/XXXXXX`. Update `.env`.

---

## Supabase Issues

### "supabaseKey is required" on Vercel
**Symptom:** Vercel API routes return 500 with this message.
**Cause:** `SUPABASE_SERVICE_KEY` not set in Vercel environment variables.
**Fix:** Go to Vercel → Settings → Environment Variables → Add `SUPABASE_SERVICE_KEY`. Redeploy.
**Note:** All API routes use lazy `getSupabase()` init to avoid build-time crashes. If you see this at build time, the route is using module-level `createClient()` — fix by wrapping in a function.

### RLS Blocking Writes
**Symptom:** Supabase returns 200 but empty array (silent failure).
**Cause:** Row Level Security policy blocks the operation for the current auth level.
**Fix:** All mutations should go through server-side API routes (which use the service key). The anon key is only used for reads. If a client-side write is silently failing, move it to a server route. See `ADMIN_RLS_STATUS.md` in the review app repo for the full fix history.

### Connection Timeout
**Symptom:** "fetch failed" or timeout errors when talking to Supabase.
**Fix:** Check internet connection. Verify `SUPABASE_URL` is correct. Try `curl https://YOUR_PROJECT.supabase.co/rest/v1/` to test connectivity.

---

## Vercel Issues

### Build Failure — Module-Level createClient
**Symptom:** `Error: supabaseKey is required` during `npm run build`.
**Cause:** An API route calls `createClient()` at module level, which runs during static page generation when env vars aren't available.
**Fix:** Wrap in a function:
```typescript
// BAD — crashes at build time
const supabase = createClient(process.env.URL!, process.env.KEY!);

// GOOD — only runs at request time
function getSupabase() {
  return createClient(process.env.URL!, process.env.KEY!);
}
```

### Deployment Not Promoting to Production
**Symptom:** Latest code pushed but production domain shows old version.
**Cause:** Vercel deploys succeeded but production domain still points to an older deployment.
**Fix:** Vercel Dashboard → Deployments → find latest "Ready" deployment → click `...` → "Promote to Production".

### Environment Variables Not Available
**Symptom:** Features work locally but fail on Vercel.
**Cause:** Env vars set locally in `.env.local` but not in Vercel dashboard.
**Fix:** Vercel → Settings → Environment Variables. Ensure all required vars are set AND scoped to "Production" (not just "Preview" or "Development").

Required Vercel env vars:
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_KEY`
- `AIRTABLE_TOKEN`
- `AIRTABLE_BASE_ID`

---

## Airtable Issues

### Search Formula 422 Error
**Symptom:** Airtable returns 422 `INVALID_FILTER_BY_FORMULA`.
**Cause:** URL encoding mangled the `{Field Name}` curly braces.
**Fix:** Use `URLSearchParams` for the filter formula, or use the table ID (e.g., `tblI55WEIy16aftkS`) instead of the table name to avoid encoding issues with spaces.

### "Failed to fetch Airtable schema"
**Symptom:** Vercel sync returns 500 with this message.
**Cause:** The schema API (`/v0/meta/bases/{id}/tables`) requires `schema.bases:read` scope on the Airtable token. Or the token/base_id env vars are missing on Vercel.
**Fix:** The current sync route uses hardcoded field maps and skips schema fetch. If you see this error, you're running an old version. Redeploy.

### Duplicate Rows in Airtable
**Symptom:** Same course appears multiple times.
**Cause:** The search formula to find existing records failed (encoding issue), so each sync created a new row instead of updating.
**Fix:** This was fixed by using `URLSearchParams`. Delete duplicates manually in Airtable. The sync uses upsert (find by Course Name → update, or create if not found).

### Ratings Not Populating
**Symptom:** Criteria columns (Yes/No) fill but Rating columns (Met/Not Met) stay empty.
**Cause:** Rating field names were being discovered from existing records, but empty records don't return those fields.
**Fix:** Rating and Notes field maps are now hardcoded in the sync route (`RATING_MAP` and `NOTES_MAP` objects). No discovery needed.

---

## Audit Issues

### Claude Ignores "Generate Report?" Prompt
**Symptom:** Audit auto-generates report and pushes to Supabase without asking.
**Cause:** Conflicting instructions in `skills/audit/SKILL.md` — one section said "always generate" while another said "ask first."
**Fix:** The SKILL.md was fixed with explicit "Do NOT auto-generate" guards. If it happens again, check for any new "always" or "automatically" instructions in the SKILL.md.

### Different Results Across Sessions (Col B)
**Symptom:** Two Quick Check audits on the same course produce different B-criteria results.
**Cause:** Claude evaluated B-criteria itself instead of using `criterion_evaluator.py`.
**Fix:** Check if the audit SKILL.md instructions clearly say "Run criterion_evaluator.py --quick-check" as the first step. Claude should NEVER evaluate B-criteria — the Python script is authoritative.

### C-Criteria Vary Between Sessions
**Symptom:** Deep Audit produces different C-criteria verdicts each run.
**Cause:** Normal — C-criteria use AI judgment. The phrasing may differ but verdicts should be similar.
**Not a bug.** C-criteria are inherently subjective. The enrichment cards in `standards_enrichment.yaml` constrain variability but can't eliminate it.

### Evidence Is Generic
**Symptom:** Evidence says "Layout element present" instead of specific page names.
**Cause:** The `evaluate_b_criterion()` function hit a fallback branch instead of a specific handler.
**Fix:** Add a specific handler in `criterion_evaluator.py` for that criterion ID. Search for the `cid_str.startswith("B-XX.")` pattern.

---

## Staging Issues

### Port 8111 Already in Use
**Symptom:** Staging preview server won't start.
**Fix:** `lsof -i :8111 | grep LISTEN` to find the process. Kill it: `kill -9 <PID>`. Or use a different port.

### Preview Shows Old Content
**Symptom:** Staged page shows previous version, not latest fix.
**Fix:** Re-run `python3 scripts/unified_preview.py` to regenerate the unified preview. The staging server serves files from `staging/` — verify the file was actually updated.

---

## Role & Auth Issues

### "IDW_TESTER_ID not set"
**Symptom:** Role gate rejects all operations.
**Fix:** Add `IDW_TESTER_ID=<your UUID>` to `.env`. Get your UUID from an admin or check `testers` table in Supabase.

### "Tester not found or inactive"
**Symptom:** `IDW_TESTER_ID` is set but role gate still fails.
**Cause:** The UUID doesn't match any active tester, or `is_active = false`.
**Fix:** Check Supabase `testers` table. Register with `python3 scripts/role_gate.py --register --name "Name" --email "email" --role admin`.

### ID Assistant Can't See Session
**Symptom:** ID Assistant logs into Vercel but the session list is empty.
**Cause:** No sessions have `assigned_to` = their tester ID, or the session status is `in_progress` (not yet submitted for review).
**Fix:** Admin must assign the ID Assistant to the session. Session must be in `pending_qa_review` or later status.

### Review App API Returns 401
**Symptom:** Admin page actions fail, or Airtable sync returns 401.
**Cause:** Browser auth cookies not reaching the server. Likely the browser Supabase client isn't using `@supabase/ssr`'s `createBrowserClient`.
**Fix:** Verify `src/lib/supabase.ts` uses `createBrowserClient` from `@supabase/ssr` (not `createClient` from `@supabase/supabase-js`). The former stores auth in cookies; the latter uses localStorage which server routes can't read.

### Review App API Returns 403
**Symptom:** User is signed in but gets "Forbidden" on an API call.
**Cause:** The user's role doesn't match the route's `requireRole()` check, or their `testers` record has `is_active = false`.
**Fix:** Check the route auth matrix in `ENGINEERING.md` section 3 for required roles. Verify the user's email matches an active row in the `testers` table with the correct role.

### Admin Page Actions Silently Fail (Legacy)
**Symptom:** Admin adds a tester or assigns a course but it doesn't persist after page refresh.
**Cause:** (Pre-v1.1) The admin page wrote directly to Supabase via the anon key, which RLS blocked silently.
**Status:** Fixed in v1.1. All admin mutations now go through `/api/admin/*` routes using the service key with server-side auth. If you still see this, you're running an old version.
