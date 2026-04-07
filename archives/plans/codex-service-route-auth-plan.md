# IDW Review App Service-Route Auth Lockdown Plan

## Goal

Lock down the six remaining service-key API routes in `idw-review-app` so they are no longer callable by arbitrary clients.

Target repo:

- `/Users/bespined/Desktop/idw-review-app`

Target routes:

1. `/api/sync-airtable`
2. `/api/session-assign`
3. `/api/findings/remediation`
4. `/api/remediation-events`
5. `/api/change-requests`
6. `/api/session-complete`

This work should use the shared server auth layer, not ad hoc checks inside each route.

## Critical Constraint

Do not start by sprinkling `requireRole()` into routes until the server can actually read the logged-in user session.

Right now the app still appears to use a plain browser Supabase client in:

- `/Users/bespined/Desktop/idw-review-app/src/lib/supabase.ts`

The route auth helper in:

- `/Users/bespined/Desktop/idw-review-app/src/lib/server/route-auth.ts`

expects SSR-readable auth cookies via `@supabase/ssr`.

So the correct order is:

1. make server-readable auth real
2. verify it works
3. apply route auth to the six service-key routes

## Phase 1: Make Server Auth Real End-to-End

### Objective

Ensure a user who signs in through the review app produces a Supabase session that server route handlers can read.

### Required work

Use the official `@supabase/ssr` app-router pattern consistently.

Expected pieces:

- browser client helper
- server client helper
- middleware or equivalent cookie refresh/update path
- route-auth helper built on that server client

### Recommended file targets

- `/Users/bespined/Desktop/idw-review-app/src/lib/supabase.ts`
- `/Users/bespined/Desktop/idw-review-app/src/lib/server/route-auth.ts`
- `/Users/bespined/Desktop/idw-review-app/src/lib/server/supabase-admin.ts`
- `/Users/bespined/Desktop/idw-review-app/middleware.ts`

If Claude prefers a slightly different folder layout for Supabase SSR helpers, that is fine, but the app must have all four responsibilities covered.

### Implementation requirements

- replace plain browser `createClient(...)` usage with the `@supabase/ssr` browser client pattern
- ensure login writes auth state in a form the server client can read on subsequent requests
- ensure route handlers can call `supabase.auth.getUser()` successfully from request cookies
- keep the service-role client server-only
- do not expose `SUPABASE_SERVICE_KEY` to client code

### Verification for Phase 1

Before touching the six routes, prove these work:

1. sign in through `/login`
2. make a same-origin request to a protected test route or existing admin route
3. `route-auth.ts` resolves the correct tester record
4. unauthenticated request returns `401`
5. authenticated request reaches the handler

If this step is not working, the route lockdown work is not complete.

## Phase 2: Normalize Shared Route Auth Helpers

### Objective

Use one shared auth/authorization layer for all service-key routes.

### Required helpers in `route-auth.ts`

- `getAuthUser(req)`
- `requireSignedInUser(req)`
- `requireRole(req, allowedRoles)`
- `requireAdminUser(req)`
- `isAuthError(result)`

Add one more category of helper for object-level checks so routes do not each reinvent the same access logic.

Recommended helpers:

- `getAuthorizedSession(sessionId, auth)`
- `getAuthorizedFinding(findingId, auth)`

These do not need to be generic abstractions for everything. Thin pragmatic helpers are enough.

### Rules for all protected routes

- authenticate first
- authorize by role second
- load the target object third
- enforce object-level access before mutating
- only then use the service-role client for the actual write

## Phase 3: Route-by-Route Lockdown

### 1. `/api/session-assign`

Files:

- `/Users/bespined/Desktop/idw-review-app/src/app/api/session-assign/route.ts`

Required auth:

- `GET`: `admin` only
- `POST`: `admin` only

Required validation:

- `session_id` required for `POST`
- if `assigned_to` is non-null, verify the tester exists, is active, and has role `id_assistant`

Notes:

- this route already has a clean role boundary in the UI
- admin is the only legitimate caller today
- no client-provided actor fields should be trusted

### 2. `/api/sync-airtable`

Files:

- `/Users/bespined/Desktop/idw-review-app/src/app/api/sync-airtable/route.ts`

Required auth:

- `POST`: `admin` or `id_assistant`

Required object-level checks:

- load the target session before syncing
- if caller is `id_assistant`, require:
  - `audit_sessions.assigned_to === auth.testerId`
  - session status is one of:
    - `complete`
    - `qa_approved`
- if caller is `admin`, allow broader access

Required payload hardening:

- do not trust any caller identity from the body
- derive any actor/audit fields server-side if needed

Recommended guardrails:

- optionally reject already-synced sessions with a clear response, unless re-sync is explicitly intended
- fail clearly if session or findings are missing

### 3. `/api/findings/remediation`

Files:

- `/Users/bespined/Desktop/idw-review-app/src/app/api/findings/remediation/route.ts`

Required auth:

- `PATCH`: `id` or `admin`

Why:

- the UI only exposes remediation toggling to non-IDA reviewers
- current component logic hides it for `id_assistant`

Required validation:

- `finding_id` required
- `remediation_requested` must be boolean

Recommended object-level check:

- verify the finding exists
- load its parent session
- ensure the authenticated user is allowed to work with that session

For pre-pilot, if ownership semantics for `id` are still unclear, at minimum enforce the role check now and add the session-level ownership helper if the existing data model supports it cleanly.

### 4. `/api/remediation-events`

Files:

- `/Users/bespined/Desktop/idw-review-app/src/app/api/remediation-events/route.ts`

Required auth:

- `GET`: authenticated user with access to the related finding/session
- `POST`: `id` or `admin`

Required payload hardening:

- stop trusting `remediated_by` from the request body
- derive `remediated_by` from `auth.testerId`

Required validation:

- `finding_id` required
- if `skill_used` or `description` are missing, normalize them server-side as today

Notes:

- this route is not heavily exercised in the current UI, but it should still be secured before pilot

### 5. `/api/change-requests`

Files:

- `/Users/bespined/Desktop/idw-review-app/src/app/api/change-requests/route.ts`

This route needs tighter rules than the earlier draft. It is not truly “any authenticated user” across all methods.

Required auth:

- `GET`:
  - `admin` only for the current global queue usage (`?status=pending`)
  - if Claude wants to support session-scoped `GET ?session_id=...` for non-admins, add explicit object-level checks first
- `POST`:
  - `admin` or `id_assistant`
- `PATCH`:
  - `admin` only

Why:

- the current global queue is rendered only for admins on the home page
- the request-change button is shown from admin review context and from locked IDA context

Required payload hardening:

- stop trusting `requested_by` from the request body
- stop trusting `resolved_by` from the request body
- derive both from `auth.testerId`

Required validation:

- `POST`: `session_id` and `reason` required
- `PATCH`: `id` and `status` required
- validate `status` against allowed values

### 6. `/api/session-complete`

Files:

- `/Users/bespined/Desktop/idw-review-app/src/app/api/session-complete/route.ts`

Required auth:

- `POST`: `id` only

Why:

- the file header and system docs describe this as the “ID marks session complete” route
- do not broaden to `id_assistant` unless product behavior is explicitly changed

Required payload hardening:

- stop trusting `submitted_by` from the request body
- derive it from `auth.testerId`

Required additional fixes to bundle here:

- check insert errors when writing synthetic `finding_feedback`
- do not report success if the auto-approval insert fails

Optional but strongly recommended:

- align the route’s returned session status with the actual intended Col B / Col C workflow semantics

## Phase 4: Update Client Callers To Match the Locked Routes

Do not leave stale caller payloads behind after locking the routes.

### Required caller updates

- `/Users/bespined/Desktop/idw-review-app/src/app/page.tsx`
  - remove `resolved_by` from `change-requests` PATCH payload

- `/Users/bespined/Desktop/idw-review-app/src/components/FindingCard.tsx`
  - remove `requested_by` from `change-requests` POST payload
  - leave `finding_id` and `reason`

- any remediation-events caller
  - remove `remediated_by` from payload if present

- any `session-complete` caller
  - remove `submitted_by` from payload if present

### Fetch behavior

Same-origin `fetch("/api/...")` should carry cookies automatically once SSR auth is wired correctly. If Claude sees inconsistent behavior, add explicit `credentials: "same-origin"` on protected route calls rather than relying on guesswork.

## Phase 5: Verification Matrix

### Auth transport

1. Sign in through `/login`
2. Hit one protected route as admin and confirm success
3. Sign out and confirm the same route returns `401`

### Route-role checks

1. `/api/session-assign`
   - admin succeeds
   - non-admin gets `403`

2. `/api/sync-airtable`
   - assigned IDA can sync allowed session
   - unassigned IDA gets blocked
   - admin can sync

3. `/api/findings/remediation`
   - ID/admin can toggle
   - IDA gets `403`

4. `/api/remediation-events`
   - authorized caller succeeds
   - unauthorized caller blocked

5. `/api/change-requests`
   - admin queue `GET` works
   - non-admin global queue `GET` blocked
   - admin or IDA request creation works if intended
   - `requested_by` and `resolved_by` are set from auth, not payload

6. `/api/session-complete`
   - ID succeeds
   - non-ID blocked
   - `submitted_by` comes from auth
   - auto-approval insert failure surfaces as error

### Static checks

- `npm run lint`
- `./node_modules/.bin/tsc --noEmit --incremental false`

## Suggested Execution Order For Claude

1. Finish the SSR auth transport so server routes can read auth state reliably.
2. Confirm protected admin routes work end-to-end with real cookies.
3. Expand `route-auth.ts` from admin-only usage to shared `requireRole()` usage.
4. Lock down `session-assign` first.
5. Lock down `change-requests` and remove client actor fields.
6. Lock down `sync-airtable` with role plus session-assignment checks.
7. Lock down `findings/remediation` and `remediation-events`.
8. Lock down `session-complete`, including actor derivation and insert error handling.
9. Update client callers and rerun verification.

## Short Version To Hand Claude

Finish real SSR-based auth first so server routes can read the logged-in Supabase session. Then use the shared `requireRole()` helpers to lock down the six remaining service-key routes: `session-assign`, `sync-airtable`, `findings/remediation`, `remediation-events`, `change-requests`, and `session-complete`. Do not trust actor IDs from the browser (`requested_by`, `resolved_by`, `remediated_by`, `submitted_by`); derive them from the authenticated tester server-side. Add route-specific role checks and object-level checks where needed, especially for Airtable sync and change-request queue access.
