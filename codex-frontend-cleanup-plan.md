# IDW Review App Pilot-Readiness Cleanup Plan

This plan is for the frontend/review-app repo at:

`/Users/bespined/Desktop/idw-review-app`

Purpose:

- make the review app safe enough for pilot use
- close the highest-risk correctness and security gaps first
- defer aesthetic refactors and large component decomposition until the app is behaviorally correct

This plan is intentionally ordered. Claude should execute it top to bottom and stop after each phase if a blocker appears.

## Current Assessment

The review app is the main remaining risk in the system.

What is good:

- the repo is small enough to stabilize quickly
- `tsc --noEmit --incremental false` currently passes
- main user flows are implemented
- the UI already has route-level pages and basic auth gating

What is not pilot-ready yet:

- multiple server routes use `SUPABASE_SERVICE_KEY` without authenticating or authorizing the caller
- at least one route claims to persist state it does not actually persist
- the admin page still performs privileged mutations directly from the browser
- lint is not clean
- there is no real test coverage

## Non-Negotiable Pilot Blockers

These must be fixed before calling the review app pilot-ready.

### 1. Server Route Authorization

Files:

- `src/app/api/findings/remediation/route.ts`
- `src/app/api/remediation-events/route.ts`
- `src/app/api/session-complete/route.ts`
- `src/app/api/session-assign/route.ts`
- `src/app/api/change-requests/route.ts`
- `src/app/api/sync-airtable/route.ts`

Problem:

- these routes use `SUPABASE_SERVICE_KEY`
- they do not verify the current logged-in user server-side
- they do not enforce role-based authorization
- page-level `AuthGuard` is not a security boundary for route handlers

Pilot risk:

- if the app is reachable, these endpoints can be hit directly
- the service key bypasses RLS
- that means unauthorized reads/writes are possible unless access is externally blocked

Required outcome:

- every service-key route must authenticate the caller on the server
- every route must enforce a role policy before doing any DB write

### 2. `session-complete` Behavior Mismatch

File:

- `src/app/api/session-complete/route.ts`

Problem:

- the route says Col C findings are auto-approved
- it counts which findings would be auto-approved
- it does not actually insert/update feedback rows for them

Pilot risk:

- UI and stored state disagree
- downstream workflows can treat those findings as still unreviewed

Required outcome:

- either persist the approvals
- or change the route behavior and response text so they match reality

### 3. Privileged Browser Writes

Primary file:

- `src/app/admin/page.tsx`

Problem:

- the admin page currently creates, updates, and deletes privileged records directly from the client using the anon Supabase client
- this may depend on permissive RLS or inconsistent database policy assumptions

Pilot risk:

- behavior depends on DB policy rather than explicit application control
- the route layer and the page layer do not share one audited admin path

Required outcome:

- admin mutations should go through authenticated server routes
- or RLS must be explicitly verified and documented if any client-side privileged writes remain

## Recommended Execution Order

Do not start with `FindingCard.tsx` or big component splits.

Recommended order:

1. Add server-side auth/role helpers for API routes.
2. Lock down all service-key routes.
3. Fix `session-complete` so behavior and persistence match.
4. Move admin mutations behind server routes or documented/verified policy.
5. Clean lint errors and warnings that affect behavior confidence.
6. Add a minimal regression harness and manual QA checklist.
7. Only then consider structural refactors of large components/pages.

## Phase 0: Prep

Goal:

- create a safe execution baseline before behavior changes

Tasks:

- create a dedicated branch for review-app stabilization
- run and capture:
  - `npm run lint`
  - `./node_modules/.bin/tsc --noEmit --incremental false`
- list the exact route handlers using the service key
- confirm whether the deployed pilot app is publicly reachable or protected by external access controls

Acceptance criteria:

- baseline errors/warnings documented
- deployed access assumptions documented

## Phase 1: Build Shared Server Auth Helpers

Goal:

- make route handlers use a single server-side auth path

Suggested implementation shape:

- add a small server auth module, for example:
  - `src/lib/server-auth.ts`
  - `src/lib/server-supabase.ts`

What it should do:

- create a server-side Supabase client using the request context/cookies for the current user
- resolve the authenticated Supabase auth user
- resolve the matching `testers` row
- expose helper functions like:
  - `requireUser()`
  - `requireRole([...])`
  - `requireAdmin()`
  - `requireIDOrAdmin()`
  - `requireAssignedReviewerOrAdmin(sessionId)`

Important:

- keep `SUPABASE_SERVICE_KEY` access in a separate admin client helper
- never use the service-key client before auth/role checks pass
- continue using page-level `AuthGuard` for UX, but do not rely on it for security

Acceptance criteria:

- all route handlers can call a shared helper instead of inlining auth assumptions

## Phase 2: Lock Down Service-Key Routes

Goal:

- every service-key route becomes explicitly authenticated and authorized

Suggested role policy:

- `POST /api/sync-airtable`
  - admin only by default
  - if business rules require ID Assistant access, keep it explicit and documented
- `GET /api/session-assign`
  - admin only
- `POST /api/session-assign`
  - admin only
- `PATCH /api/findings/remediation`
  - authenticated reviewer only
  - ideally ID/Admin, depending on product rules
- `GET /api/remediation-events`
  - authenticated user with access to the parent session/finding
- `POST /api/remediation-events`
  - authenticated user with mutation rights for that session/finding
- `GET /api/change-requests`
  - authenticated, filtered by role
  - admin may see all
  - non-admin should see only what they are allowed to view
- `POST /api/change-requests`
  - authenticated reviewer only
- `PATCH /api/change-requests`
  - admin only
- `POST /api/session-complete`
  - authenticated user with permission to submit that session

Implementation notes:

- validate request bodies with narrow checks
- reject unauthorized requests with `401` or `403`
- stop returning raw backend errors where possible; use safe error messages

Acceptance criteria:

- unauthenticated requests to service-key routes fail
- wrong-role requests fail
- expected-role requests succeed

## Phase 3: Fix `session-complete`

Goal:

- align route semantics, DB writes, and UI messaging

File:

- `src/app/api/session-complete/route.ts`

Required decision:

- choose one of these and implement it consistently:

Option A:

- actually create feedback rows for unreviewed Col C findings
- then keep the current message about auto-approval

Option B:

- do not claim auto-approval
- only move the session status
- update the response and UI copy to match

Recommendation:

- prefer Option A if the product truly depends on Col C auto-approval

Acceptance criteria:

- the database state matches the route response
- repeated calls are idempotent or safely guarded

## Phase 4: Move Admin Writes Behind Server Routes

Goal:

- stop relying on direct client-side privileged mutations for admin operations

Primary file:

- `src/app/admin/page.tsx`

Current direct client mutations to replace or validate:

- add tester
- toggle tester active status
- change tester role
- delete tester
- insert tester-course assignments
- delete tester-course assignments
- resolve error reports

Recommended path:

- add dedicated admin API routes if they do not exist yet
- use server auth helpers plus service-key/admin client where appropriate
- make the page call those routes instead of mutating tables directly

If not changing this pre-pilot:

- explicitly document the exact RLS policies that make the direct client mutations safe
- prove they are enforced

Acceptance criteria:

- admin actions flow through explicit server-side authorization
- or the retained client-side path is justified and documented with verified policy

## Phase 5: Clean Lint/Hook Issues

Goal:

- remove current lint errors and risky warnings that make the UI harder to trust

Known current issues:

- `src/app/admin/page.tsx`
  - effect/setState lint error around `loadData`
- `src/app/page.tsx`
  - unused variable warning
- `src/app/session/[id]/page.tsx`
  - unused variables
  - missing hook dependency warning

Priority:

- fix the error first
- then fix the hook dependency and meaningful warnings
- leave purely cosmetic warning cleanup for last if needed

Acceptance criteria:

- `npm run lint` passes cleanly

## Phase 6: Data/Decision Vocabulary Cleanup

Goal:

- reduce confusion between legacy and current review semantics

Observed drift:

- some code still reasons in legacy decision values like `approved`, `rejected`, `agree`, `disagree`
- current types normalize toward `correct`, `incorrect`, `not_applicable`

Tasks:

- define one canonical decision vocabulary
- centralize mapping logic in one helper
- remove duplicated ad hoc legacy checks from pages/components where possible
- ensure admin stats, filters, and badges derive from the same normalized values

Acceptance criteria:

- one canonical internal decision model
- legacy values only handled at controlled boundaries

## Phase 7: Minimal Regression Harness

Goal:

- add just enough automated checking to make future cleanup safe

Do not overbuild this initially.

Minimum recommended coverage:

- route-level smoke tests for:
  - unauthorized request rejected
  - wrong-role request rejected
  - valid request accepted
- one behavior test for `session-complete`
- one behavior test for remediation toggle route
- one behavior test for change-request creation/resolution

If adding a test framework is too much for the same pass:

- create a documented manual QA checklist and run it before pilot

Acceptance criteria:

- either automated route smoke tests exist
- or a strict manual QA checklist is completed and recorded

## Phase 8: Manual Pilot QA Checklist

Run this after the route/auth fixes.

### Authentication

- login works with a valid tester
- unauthenticated users are redirected from protected pages
- admin-only page rejects non-admins

### Review Flows

- ID Assistant can open assigned sessions only
- ID can review intended sessions
- admin can review/approve/reject as intended
- locked/view-only behavior after sync is correct

### Mutations

- remediation toggle works only for allowed users
- change request creation works only for allowed users
- change request resolution works only for admins
- session assignment works only for admins
- session completion behaves exactly as designed

### Integrations

- Airtable sync only works for allowed roles
- Airtable sync failure surfaces a safe error
- remediation events render correctly

### Abuse Checks

- direct `curl`/Postman calls to protected API routes fail when not authenticated
- wrong-role calls fail with `403`

## Phase 9: Post-Pilot Refactors

Only do these after the app is behaviorally safe.

Targets:

- split `src/components/FindingCard.tsx`
- split `src/app/session/[id]/page.tsx`
- split `src/app/admin/page.tsx`
- split `src/app/page.tsx`

Recommended extraction order:

1. API/action hooks
2. filter state helpers
3. presentational subcomponents
4. modal/action sections

Do not do a rewrite. Extract incrementally with behavior locks in place.

## Concrete File Targets

Highest priority files:

- `src/app/api/findings/remediation/route.ts`
- `src/app/api/remediation-events/route.ts`
- `src/app/api/session-complete/route.ts`
- `src/app/api/session-assign/route.ts`
- `src/app/api/change-requests/route.ts`
- `src/app/api/sync-airtable/route.ts`
- `src/app/admin/page.tsx`
- `src/lib/auth.ts`
- `src/lib/supabase.ts`

Likely new files to add:

- `src/lib/server-auth.ts`
- `src/lib/server-supabase.ts`
- `src/lib/route-guards.ts`
- optionally a shared schema/validation helper for request payloads

## What Not To Touch First

Do not begin with:

- visual redesign
- global CSS cleanup
- `FindingCard.tsx` decomposition
- session page decomposition
- dashboard polish

Those are not the current pilot blockers.

## Definition Of Pilot Ready

The review app is pilot-ready when all of the following are true:

- all service-key routes enforce server-side auth and role checks
- `session-complete` behavior matches persisted state
- privileged admin mutations are server-controlled or explicitly policy-verified
- lint passes
- typecheck passes
- the manual QA checklist passes
- no direct unauthenticated request can mutate protected data

## Suggested Claude Execution Prompt

When ready, give Claude something close to this:

> Read `codex-frontend-cleanup-plan.md` first. Work only in `/Users/bespined/Desktop/idw-review-app`. Execute the plan in order, starting with server-side auth/authorization for all service-key API routes. Do not begin with component refactors. Keep changes incremental, verify each phase, and stop if a role-policy decision is ambiguous.

