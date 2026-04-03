# IDW Review App Admin RLS Fix Plan

## Goal

Remove the current pilot workaround and make the `/admin` page fully functional without relying on client-side anon-key writes that RLS blocks.

This plan is for the frontend repo at:

- `/Users/bespined/Desktop/idw-review-app`

It is based on the current code shape as of `d49c4fd`:

- Admin UI is in `/Users/bespined/Desktop/idw-review-app/src/app/admin/page.tsx`
- Auth is client-side only via `/Users/bespined/Desktop/idw-review-app/src/components/AuthGuard.tsx` and `/Users/bespined/Desktop/idw-review-app/src/lib/auth.ts`
- Admin writes currently go directly from the browser to Supabase anon client on:
  - `testers`
  - `tester_course_assignments`
  - `error_reports`
- Those writes are blocked by RLS and silently fail

## Scope

Fix only the admin-page RLS problem first:

1. Add server-side authenticated admin API routes
2. Move admin mutations off the browser anon client
3. Return real success/error responses to the UI
4. Keep existing admin UX mostly intact

Do not bundle unrelated cleanup into this work.

## Why This Is the Right Fix

The problem is not the UI itself. The problem is that the UI is doing privileged writes with the anon key.

The durable fix is:

- browser uses normal signed-in session
- Next route handler verifies the current user
- route handler checks tester role is `admin`
- route handler uses `SUPABASE_SERVICE_KEY`
- route performs the mutation server-side
- UI handles success/failure explicitly

This removes the workaround and gives the app a real admin control plane.

## Current Mutation Paths To Replace

In `/Users/bespined/Desktop/idw-review-app/src/app/admin/page.tsx`, replace these direct Supabase calls:

- `handleAddTester()` → `supabase.from("testers").insert(...)`
- `handleToggleActive()` → `supabase.from("testers").update(...)`
- `handleChangeRole()` → `supabase.from("testers").update(...)`
- `handleDeleteTester()` → `supabase.from("testers").delete(...)`
- `handleAssignCourse()` → `supabase.from("tester_course_assignments").insert(...)`
- `handleRemoveAssignment()` → `supabase.from("tester_course_assignments").delete(...)`
- `handleResolveError()` → `supabase.from("error_reports").update(...)`

## Recommended Implementation Order

### Phase 1: Add shared server auth helpers

Create a small shared server helper layer so every admin route uses the same auth logic.

Recommended files:

- `/Users/bespined/Desktop/idw-review-app/src/lib/server/supabase-admin.ts`
- `/Users/bespined/Desktop/idw-review-app/src/lib/server/route-auth.ts`

Responsibilities:

- `supabase-admin.ts`
  - create a service-role Supabase client from:
    - `NEXT_PUBLIC_SUPABASE_URL`
    - `SUPABASE_SERVICE_KEY`
  - export one helper only, something like `getServiceSupabase()`

- `route-auth.ts`
  - create a request-scoped Supabase SSR client using cookies
  - read the signed-in Supabase auth user from the request
  - look up the matching `testers` row by email and `is_active = true`
  - return a normalized auth result like:
    - `user`
    - `tester`
    - `role`
  - export:
    - `requireSignedInUser()`
    - `requireAdminUser()`

Important:

- Do not trust role information from the client
- Do not accept `tester_id` or `role` from the browser as authorization
- Use the logged-in Supabase session to identify the user

### Phase 2: Add admin API routes

Add server routes under `/src/app/api/admin/...` and put all privileged admin mutations there.

Recommended routes:

- `POST /api/admin/testers`
  - create tester

- `PATCH /api/admin/testers/[id]`
  - update role and/or `is_active`

- `DELETE /api/admin/testers/[id]`
  - delete tester

- `POST /api/admin/assignments`
  - create one or many course assignments

- `DELETE /api/admin/assignments/[id]`
  - remove one course assignment

- `PATCH /api/admin/errors/[id]`
  - resolve or acknowledge an error report

Route requirements:

- every route must call `requireAdminUser()`
- every route must return:
  - `401` if not signed in
  - `403` if signed in but not admin
  - `400` for bad payloads
  - `500` for real server/database errors
- every write should use the service client
- every mutation response should include the updated row or a clear success payload

Validation rules to enforce:

- tester create:
  - require `name`
  - validate `role` in `id | id_assistant | admin`
  - normalize blank email to `null`

- tester update:
  - only allow intended mutable fields:
    - `role`
    - `is_active`
    - optionally `email`
    - optionally `name`
  - reject no-op/empty payloads

- tester delete:
  - require explicit route param `id`
  - consider blocking self-delete for current admin

- assignment create:
  - require `tester_id`
  - require at least one `course_id`
  - support existing comma-separated input behavior
  - set `assigned_by` from authenticated admin, not from browser payload
  - preserve current default `canvas_domain` behavior unless product wants it changed

- assignment delete:
  - delete by assignment row id only

- error resolve:
  - set:
    - `status = "resolved"`
    - `resolved_by = current admin tester id`
    - `resolved_at = now`

### Phase 3: Refactor admin page to call the new routes

Update `/Users/bespined/Desktop/idw-review-app/src/app/admin/page.tsx` so mutations use `fetch()` to the new API routes instead of `supabase.from(...).insert/update/delete`.

Recommended refactor pattern:

- keep reads as-is for the first pass if they already work
- move writes only
- create small wrapper helpers in the component, for example:
  - `apiCreateTester()`
  - `apiUpdateTester()`
  - `apiDeleteTester()`
  - `apiCreateAssignments()`
  - `apiDeleteAssignment()`
  - `apiResolveError()`

UI behavior requirements:

- check `res.ok` on every request
- parse and surface route error messages
- do not clear forms until request succeeds
- do not call `loadData()` after a failed request
- show visible error state in the page, not silent failure
- keep loading/disabled states around buttons while requests are in flight

Recommended minimal UX additions:

- one page-level `actionError` banner
- one page-level `actionSuccess` banner
- clear success after next action or tab switch

### Phase 4: Make reads consistent if needed

This is optional for the first merge but recommended if you want the admin page to be fully server-backed.

Current reads in `admin/page.tsx` use anon client queries for:

- `testers`
- `error_reports`
- `audit_findings`
- `finding_feedback`
- `tester_course_assignments`

If those reads are intended to be admin-only and not broadly readable by RLS, move them behind:

- `GET /api/admin/overview`

That route can return:

- testers
- assignments
- recent errors
- RLHF summary counts

This is cleaner than scattering multiple admin-only reads in the browser.

If time is tight, do writes first and leave read centralization for the next pass.

### Phase 5: Close the loop with tests and verification

Minimum verification:

- `npm run lint`
- `./node_modules/.bin/tsc --noEmit --incremental false`
- manual admin smoke test:
  - add tester
  - change role
  - deactivate tester
  - reactivate tester
  - assign course
  - remove assignment
  - resolve error

For each action verify:

- UI shows success
- database row actually changed
- no silent failure
- non-admin user gets blocked

Recommended lightweight tests:

- route-auth unit tests or narrow integration tests for:
  - unauthenticated request → `401`
  - non-admin request → `403`
  - admin request → success
- one happy-path test per route if test harness exists

## Suggested File-Level Work Plan

### New files

- `/Users/bespined/Desktop/idw-review-app/src/lib/server/supabase-admin.ts`
- `/Users/bespined/Desktop/idw-review-app/src/lib/server/route-auth.ts`
- `/Users/bespined/Desktop/idw-review-app/src/app/api/admin/testers/route.ts`
- `/Users/bespined/Desktop/idw-review-app/src/app/api/admin/testers/[id]/route.ts`
- `/Users/bespined/Desktop/idw-review-app/src/app/api/admin/assignments/route.ts`
- `/Users/bespined/Desktop/idw-review-app/src/app/api/admin/assignments/[id]/route.ts`
- `/Users/bespined/Desktop/idw-review-app/src/app/api/admin/errors/[id]/route.ts`

### Existing files to update

- `/Users/bespined/Desktop/idw-review-app/src/app/admin/page.tsx`
- `/Users/bespined/Desktop/idw-review-app/ADMIN_RLS_STATUS.md`

### Optional follow-up files

- `/Users/bespined/Desktop/idw-review-app/src/app/api/admin/overview/route.ts`

## Important Design Decisions

### 1. Use SSR auth helpers, not client-provided identity

The app already has `@supabase/ssr` installed but is not using it.

Claude should use that package for route auth instead of inventing a custom token format.

### 2. Keep service key server-only

Only route handlers should touch `SUPABASE_SERVICE_KEY`.

Do not import service-key helpers into client components.

### 3. Preserve existing role model

Use the existing `testers.role` values:

- `admin`
- `id`
- `id_assistant`

Do not redesign auth or role storage in this task.

### 4. Avoid bundling broader API hardening into this change

This task is specifically to eliminate the admin-page RLS workaround.

Do not mix in:

- `session-complete` redesign
- `sync-airtable` redesign
- `session-assign` hardening
- dashboard metrics cleanup

Those are valid follow-ups, but they should not block this fix.

## Acceptance Criteria

This issue is fixed when all of the following are true:

1. Admin page no longer writes directly to Supabase anon client for testers, assignments, or error resolution
2. Admin actions succeed for signed-in admins
3. Admin actions fail cleanly for non-admins and unauthenticated users
4. The UI shows real success/failure instead of silently reloading
5. `ADMIN_RLS_STATUS.md` is updated from "workaround required" to "fixed"
6. Lint and typecheck pass

## Nice-to-Have Hardening After This Fix

These are not required for the admin RLS fix, but Claude should note them for next round:

1. Move admin reads to `GET /api/admin/overview`
2. Add audit logging for admin mutations
3. Block deletion of testers with live assignments unless explicitly confirmed
4. Prevent self-demotion/self-deactivation for the currently logged-in admin
5. Reuse the same server auth helper across the other service-key routes:
   - `/api/session-assign`
   - `/api/sync-airtable`
   - `/api/remediation-events`
   - `/api/change-requests`
   - `/api/findings/remediation`
   - `/api/session-complete`

## Short Version To Hand Claude

Fix the admin-page RLS issue by moving all admin mutations in `src/app/admin/page.tsx` off the browser anon Supabase client and into new server-side `/api/admin/*` routes protected by SSR-based `requireAdminUser()` auth. Use the service key only inside route handlers, return real HTTP errors, update the UI to handle failures visibly, and keep the change scoped to testers, assignments, and error-resolution flows.
