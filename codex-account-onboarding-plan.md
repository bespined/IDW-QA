# Codex Account Onboarding Plan

> **Status: Completed** (April 2026). All phases implemented — Vercel admin UI provisions login + UUID, Claude Code admin path works, role-specific messaging is live. See `codex-canonical-workflow-spec.md` for the current onboarding contract.

This plan makes the Vercel review app the primary account-creation surface for pilot admins while preserving the plugin's UUID-based identity model for Claude Code users.

It also keeps a sanctioned Claude Code admin path for technical admins who prefer to provision accounts from the plugin.

The goal is to eliminate the current half-onboarding state where the admin UI creates a `testers` row but does not provision review-app login or clearly hand off the tester UUID needed by Claude Code.

Do not broaden scope beyond onboarding, account provisioning, and role-specific setup messaging.

---

## Problem Summary

Today there are two separate identity layers:

1. `testers` row in Supabase
   - stores `id`, `name`, `email`, `role`, `is_active`
   - used for role gating, assignment, attribution, and review workflow

2. Supabase Auth user
   - used for signing into the Vercel review app
   - matched to the tester row by `email`

Current gaps:

- The Vercel admin UI creates only the `testers` row.
- It does not create or invite a Supabase Auth user.
- It does not surface the tester UUID clearly.
- It allows `email` to be optional, even though Vercel login depends on email.
- It does not show role-specific setup instructions after account creation.

Operationally, this means:

- `id_assistant` users may have a tester row but still cannot sign in.
- `id` and `admin` users may have a tester row but still cannot use Claude Code unless someone manually gives them the tester UUID.

---

## Desired End State

Creating a tester from either sanctioned admin surface should fully onboard the user for the pilot:

1. **Primary path**: Vercel admin UI
2. **Secondary path**: Claude Code admin skill / script flow

Role-specific expectations:

- `id_assistant`
  - Vercel login provisioned
  - no Claude Code setup required

- `id`
  - Vercel login provisioned
  - tester UUID shown clearly for Claude Code setup

- `admin`
  - Vercel login provisioned
  - tester UUID shown clearly for Claude Code setup

The admin should not need to leave the Vercel app to complete pilot onboarding.

Technical admins should also be able to complete onboarding from Claude Code without creating a separate identity model.

---

## Scope

### In scope

- Vercel admin tester creation flow
- Claude Code admin tester creation flow
- server-side provisioning/invite for Supabase Auth
- UUID display and copy UX
- role-specific onboarding instructions
- optional resend-invite/reset-password admin actions if needed for pilot usability

### Out of scope

- replacing the plugin's `IDW_TESTER_ID` model
- redesigning review-app login architecture
- self-serve role selection by end users
- broad auth-system refactors beyond what is required for pilot onboarding

---

## Phase 1 — Define the Pilot Onboarding Contract

### Required rules

1. `email` is required for any pilot tester created through the Vercel admin UI.
2. Admins create users in the Vercel app.
   - This is the default path for non-technical admins.
3. The system provisions review-app login as part of tester creation.
4. Technical admins may also create users through Claude Code using a script-enforced admin path.
   - This path must create the same `testers` row shape as Vercel.
   - It must not create a separate identity model.
5. UUID is shown only when useful:
   - show for `id`
   - show for `admin`
   - optional to show for `id_assistant`, but not necessary
6. Roles remain admin-assigned only.

### Acceptance criteria

- There is one documented source of truth for pilot onboarding.
- The role-specific expectations are explicit and consistent across docs/UI.
- Admin cannot create a pilot user without an email.

---

## Phase 2 — Make Vercel Tester Creation Provision Login

### Current problem

[`/Users/bespined/Desktop/idw-review-app/src/app/api/admin/testers/route.ts`](/Users/bespined/Desktop/idw-review-app/src/app/api/admin/testers/route.ts) only inserts into `testers`.

That is not sufficient for review-app access.

### Required end state

When an admin creates a tester in the Vercel app:

1. validate `name`, `email`, and `role`
2. create the tester row
3. provision the Supabase Auth user for that email
4. trigger an onboarding method:
   - preferred: invite email or password-setup/reset email

### Recommended implementation

Use a server-only route with the service role key to:

- insert into `testers`
- then invite the auth user using Supabase Auth admin APIs

For pilot, use:

- `supabase.auth.admin.inviteUserByEmail()`

Preferred UX:

- if email is new: create tester row + send invite
- if email already exists in Auth or is already attached to another tester row: fail clearly and surface the conflict to the admin

### File targets

- [`/Users/bespined/Desktop/idw-review-app/src/app/api/admin/testers/route.ts`](/Users/bespined/Desktop/idw-review-app/src/app/api/admin/testers/route.ts)
- possibly a small helper under:
  - [`/Users/bespined/Desktop/idw-review-app/src/lib/server/`]( /Users/bespined/Desktop/idw-review-app/src/lib/server/ )

### Constraints

- keep admin-only auth enforcement
- do not expose service-role operations to the client
- handle duplicate email cases clearly and conservatively for pilot

### Acceptance criteria

- Creating a tester in Vercel results in both:
  - tester row
  - usable review-app login path

---

## Phase 3 — Add a Supported Claude Code Admin Provisioning Path

### Current problem

The plugin already has a script path:

- [`/Users/bespined/claude-plugins/IDW-QA/scripts/admin_actions.py`](/Users/bespined/claude-plugins/IDW-QA/scripts/admin_actions.py)

But the onboarding story currently treats Vercel and Claude Code as disconnected experiences.

### Required end state

There should be a clear secondary admin path in Claude Code for creating users, returning the UUID, and showing the same role-specific next steps.

### Recommended implementation

Keep using the existing script-enforced backend:

```bash
python3 scripts/admin_actions.py --register --name "<NAME>" --email "<EMAIL>" --role <ROLE>
```

Add or refine a Claude admin skill flow so that technical admins can:

1. choose `Create tester`
2. enter `name`, `email`, `role`
3. run the script-enforced registration path
4. see:
   - tester UUID
   - role
   - next steps by role
5. optionally copy the Claude Code setup snippet for `id` and `admin`:
   ```env
   IDW_TESTER_ID=<uuid>
   ```

This should be documented as a **secondary** path, not the default onboarding path for non-technical admins.

### File targets

- [`/Users/bespined/claude-plugins/IDW-QA/skills/admin/SKILL.md`](/Users/bespined/claude-plugins/IDW-QA/skills/admin/SKILL.md)
- optionally a dedicated skill if you prefer stronger separation, but reusing `/admin` is acceptable for pilot
- [`/Users/bespined/claude-plugins/IDW-QA/scripts/admin_actions.py`](/Users/bespined/claude-plugins/IDW-QA/scripts/admin_actions.py) only if messaging/output needs cleanup

### Constraints

- keep `admin_actions.py` as the enforcement layer
- do not invent a separate UUID-generation step
- Supabase row creation remains the source of truth for UUID creation

### Acceptance criteria

- Technical admins can fully provision a tester from Claude Code.
- The returned UUID and next steps match the Vercel onboarding contract.
- Vercel remains the documented primary onboarding path.

---

## Phase 4 — Surface the Tester UUID Clearly

### Current problem

Claude Code users still need:

```env
IDW_TESTER_ID=<uuid>
```

But the Vercel admin UI does not clearly display the tester UUID after creation or in the testers table.

### Required end state

After tester creation, the admin UI should show:

- tester name
- role
- email
- tester UUID
- copy button

For `id` and `admin`, also show:

> Claude Code setup: add `IDW_TESTER_ID=<uuid>` to the plugin `.env`.

### Recommended UX

1. Success banner after creation:
   - “Tester created”
   - “Invite sent” or equivalent login status
   - UUID with copy button
   - Claude Code setup snippet with copy button for `id` and `admin`:
     ```env
     IDW_TESTER_ID=<uuid>
     ```

2. In the testers table:
   - either a visible UUID column
   - or a “Show setup” / “Copy UUID” action

### File targets

- [`/Users/bespined/Desktop/idw-review-app/src/app/admin/page.tsx`](/Users/bespined/Desktop/idw-review-app/src/app/admin/page.tsx)

### Acceptance criteria

- Admin can copy the UUID without using Claude Code or Supabase directly.
- Admin can copy the full Claude Code setup snippet without editing it manually.
- `id` and `admin` onboarding instructions are visible immediately after creation.

---

## Phase 5 — Role-Specific Setup Messaging

### Required end state

After tester creation, show different next steps by role.

#### `id_assistant`

Show:

- “Use the QA portal only”
- “Check your email to finish account setup”

Do not emphasize Claude Code.

#### `id`

Show:

- “Check your email to finish QA portal login”
- “For Claude Code, add this to your plugin `.env`:
  `IDW_TESTER_ID=<uuid>`”

#### `admin`

Show:

- “Check your email to finish QA portal login”
- “For Claude Code admin/audit workflows, add:
  `IDW_TESTER_ID=<uuid>`”

### File targets

- [`/Users/bespined/Desktop/idw-review-app/src/app/admin/page.tsx`](/Users/bespined/Desktop/idw-review-app/src/app/admin/page.tsx)

### Acceptance criteria

- Admin can onboard each role correctly without external documentation.

---

## Phase 6 — Update Plugin and Setup Docs

### Current problem

Docs currently assume admin hands out tester credentials manually, but the Vercel app should become the primary creation surface.

### Required end state

Update docs so they describe:

- Vercel admin UI creates pilot users by default
- Claude Code admin skill is the secondary fallback/power-user path
- Vercel also provisions login
- `id` and `admin` still need the tester UUID for Claude Code
- `id_assistant` does not

### File targets

- [`/Users/bespined/claude-plugins/IDW-QA/SETUP.md`](/Users/bespined/claude-plugins/IDW-QA/SETUP.md)
- [`/Users/bespined/claude-plugins/IDW-QA/README.md`](/Users/bespined/claude-plugins/IDW-QA/README.md)
- [`/Users/bespined/claude-plugins/IDW-QA/AGENTS.md`](/Users/bespined/claude-plugins/IDW-QA/AGENTS.md)
- [`/Users/bespined/claude-plugins/IDW-QA/CLAUDE.md`](/Users/bespined/claude-plugins/IDW-QA/CLAUDE.md)
- any relevant admin skill docs:
  - [`/Users/bespined/claude-plugins/IDW-QA/skills/admin/SKILL.md`](/Users/bespined/claude-plugins/IDW-QA/skills/admin/SKILL.md)

### Acceptance criteria

- No active doc implies that review-app onboarding is complete without login provisioning.
- No active doc implies that `id_assistant` users need Claude Code UUID setup.
- Docs clearly distinguish:
  - Vercel = primary onboarding path
  - Claude Code admin skill = secondary provisioning path

---

## Phase 7 — Optional Pilot Convenience Actions

These are not required for the first pass, but would materially improve admin usability:

1. resend invite / resend password setup email
2. reset password trigger
3. “Setup complete / invite pending” status in testers table
4. explicit deactivation follow-up behavior in the admin UI

These can be follow-up items if the core onboarding path lands first.

### Deactivation note

For pilot, it is acceptable if deactivation only blocks app/plugin access via `is_active = false` and does not disable the Supabase Auth user directly.

But this should be documented so the behavior is intentional and not surprising.

---

## Recommended Execution Order

1. Define the onboarding contract and require email
2. Provision Supabase Auth during tester creation via `inviteUserByEmail`
3. Add the sanctioned Claude Code admin provisioning path
4. Surface UUID + Claude Code setup snippet + role-specific next steps in the admin UI
5. Update plugin/setup docs
6. Add resend/reset conveniences if needed

---

## Verification Checklist

### ID Assistant

1. Admin creates tester in Vercel with email + role `id_assistant`
   - or technical admin creates the same tester via Claude Code admin path
2. User receives invite or password-setup path
3. User can log into the review app
4. No UUID is needed for their normal workflow

### ID

1. Admin creates tester in Vercel with email + role `id`
   - or technical admin creates the same tester via Claude Code admin path
2. User receives invite or password-setup path
3. Admin can copy the tester UUID from the UI
4. User can log into the review app
5. User can add `IDW_TESTER_ID=<uuid>` to plugin `.env`
6. Claude Code role-gated skills recognize the user correctly

### Admin

1. Admin creates tester in Vercel with email + role `admin`
   - or technical admin creates the same tester via Claude Code admin path
2. User receives invite or password-setup path
3. UUID is surfaced for Claude Code use
4. User can log into the review app
5. User can use plugin admin/audit flows with the UUID in `.env`

---

## Bottom Line

The current Vercel admin UI creates only the tester profile, not the full account.

This plan makes Vercel-based admin onboarding complete by handling:

- tester row
- review-app login provisioning
- UUID handoff for Claude Code users
- role-specific instructions

And it keeps a clean secondary Claude Code provisioning path for technical admins using the same underlying identity model.

That is the minimum clean pilot-ready onboarding model.
