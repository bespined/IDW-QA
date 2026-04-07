# IDW-QA Pre-Pilot Plugin Fix Plan

## Goal

Close the remaining pre-pilot plugin gaps in `/Users/bespined/claude-plugins/IDW-QA` so the plugin matches the actual operating model:

- `id_assistant` users work in the Vercel review app, not Claude Code
- audit sessions link to the correct review-app URL
- session creation docs and CLI match real behavior
- remediation tracking promises are true
- concierge remediation/fix-queue flow is explicit enough to work consistently

This plan is intentionally scoped to plugin/docs/workflow fixes only.

## Priority Order

### 1. Fix the wrong review-app URL

This is a real functional bug.

Current problem:

- the plugin generates `https://idw-review-app.vercel.app/sessions/<SESSION_ID>`
- the actual review app route is `/session/[id]`, singular

Verified locations:

- `/Users/bespined/claude-plugins/IDW-QA/scripts/audit_session_manager.py`
- `/Users/bespined/claude-plugins/IDW-QA/skills/audit/SKILL.md`

Required changes:

- update all generated/documented review URLs from `/sessions/<id>` to `/session/<id>`
- verify there are no remaining plural-path references in docs, scripts, or prompts

Acceptance criteria:

- session creation output prints the correct URL
- audit skill docs show the correct URL
- no stale `/sessions/` links remain in active plugin files

## 2. Remove `id_assistant` from Claude Code entry flows

The product model now says `id_assistant` is Vercel-only. The plugin still exposes Claude Code flows for that role.

Current drift:

- concierge still routes `id_assistant` into assignments/audit/fix-queue flows
- `/assignments` still exists as an IDA-facing skill
- audit docs still infer recurring audits from `id_assistant`
- README and reference docs still describe IDAs as Claude Code users

Primary files to update:

- `/Users/bespined/claude-plugins/IDW-QA/skills/qa-concierge/SKILL.md`
- `/Users/bespined/claude-plugins/IDW-QA/skills/assignments/SKILL.md`
- `/Users/bespined/claude-plugins/IDW-QA/skills/audit/SKILL.md`
- `/Users/bespined/claude-plugins/IDW-QA/README.md`
- `/Users/bespined/claude-plugins/IDW-QA/AGENTS.md`
- `/Users/bespined/claude-plugins/IDW-QA/CLAUDE.md`
- `/Users/bespined/claude-plugins/IDW-QA/SETUP.md`
- `/Users/bespined/claude-plugins/IDW-QA/ENGINEERING.md` if it implies IDAs use Claude Code directly

Required product decision for implementation:

- `id_assistant` should not be offered plugin workflows
- admins may still need assignment visibility from Claude Code

Recommended implementation:

- remove `id_assistant` role routing from concierge
- deprecate `/assignments` as an IDA skill
- either:
  - repurpose it as admin-only assignment visibility, or
  - mark it deprecated and remove it from active references
- update all role tables and workflow descriptions so `id_assistant` is clearly Vercel-only

Acceptance criteria:

- concierge no longer offers IDA Claude workflows
- docs no longer tell IDAs to use Claude Code for assigned audits
- skill reference tables match the actual product model

## 3. Remove dead `--scope` session-manager surface

This is dead interface surface and doc drift.

Current problem:

- `scripts/audit_session_manager.py` still requires `--scope`
- `scope` is accepted and passed through
- `scope` is never stored or used in session creation

Verified files:

- `/Users/bespined/claude-plugins/IDW-QA/scripts/audit_session_manager.py`
- `/Users/bespined/claude-plugins/IDW-QA/skills/audit/SKILL.md`

Required changes:

- remove `--scope` from the script CLI
- remove `scope` from `create_session(...)` if it is truly unused
- update usage examples, error messages, and skill docs

Important:

- do not remove `--mode`; that one is still used/documented
- keep behavior otherwise unchanged

Acceptance criteria:

- session creation works without `--scope`
- no active docs still tell Claude to pass `--scope`
- script usage output and examples are accurate

## 4. Make remediation tracking claims true

Current problem:

- the docs and concierge say remediation skills auto-record via `remediation_tracker.py`
- but four skills still appear to be missing the tracking call pattern

Skills Claude should verify and patch if missing:

- `/Users/bespined/claude-plugins/IDW-QA/skills/update-module/SKILL.md`
- `/Users/bespined/claude-plugins/IDW-QA/skills/syllabus-generator/SKILL.md`
- `/Users/bespined/claude-plugins/IDW-QA/skills/course-config/SKILL.md`
- `/Users/bespined/claude-plugins/IDW-QA/skills/media-upload/SKILL.md`

Required behavior:

- if a skill fixes audit findings, it must instruct Claude to call:
  - `python3 scripts/remediation_tracker.py --record ...`
- the flow should match the already-correct pattern used in:
  - quiz
  - assignment-generator
  - discussion-generator
  - rubric-creator
  - interactive-content
  - bulk-edit

Implementation guidance:

- copy the established instruction pattern instead of inventing a new one
- only add remediation tracking where the skill can genuinely fix a finding
- be explicit about passing finding IDs

Acceptance criteria:

- all remediation-capable skills either:
  - include the tracker call pattern, or
  - explicitly say they do not remediate audit findings
- concierge claims about auto-recording are true

## 5. Update post-submission messaging for the real review workflow

Current problem:

- audit messaging is too thin after findings are pushed
- it does not explain the actual review pipeline well enough

The messaging should distinguish:

- `self_audit`
- `qa_review`
- `recurring`

Desired behavior:

- if `self_audit`:
  - explain the findings are in the review app
  - offer submit-for-QA-review flow
  - explain admin/IDA validation sequence only if relevant

- if `qa_review` / `recurring`:
  - explain the next step is admin assignment in the review app
  - explain ID Assistant validates Col B findings
  - explain completion returns the work to the ID for remediation

Primary file:

- `/Users/bespined/claude-plugins/IDW-QA/skills/audit/SKILL.md`

Also verify concierge wording if it references the same flow.

Acceptance criteria:

- a user reading the audit result knows exactly what happens next
- wording reflects the actual Vercel workflow
- messaging differs by audit purpose where needed

## 6. Flesh out concierge Path D so it is executable, not aspirational

Current problem:

- Path D says to present findings and route them to skills
- but it is too vague to produce consistent behavior

Primary file:

- `/Users/bespined/claude-plugins/IDW-QA/skills/qa-concierge/SKILL.md`

Claude should make Path D concrete:

- specify how to present each fix-queue item
- include:
  - finding ID
  - criterion ID
  - page/item context
  - reviewer feedback
  - suggested fix direction
- specify how Claude chooses the remediation skill
- specify how finding IDs are carried into the remediation flow
- specify that after push, remediation tracking must be recorded

Recommended output shape for each finding:

- `Finding ID`
- `Criterion`
- `Location`
- `Reviewer feedback`
- `Recommended remediation skill`
- `Proposed next step`

Keep it simple and procedural. The goal is reliable execution, not elegant prose.

Acceptance criteria:

- Path D gives Claude enough detail to run a fix-queue workflow consistently
- remediation skills receive finding context cleanly
- the tracking step is explicit

## Suggested Execution Order For Claude

1. Fix review-app URL path bug.
2. Remove `id_assistant` from Claude Code-facing flows and docs.
3. Remove dead `--scope` from session manager and audit docs.
4. Add missing remediation tracking instructions to the 4 skills.
5. Rewrite audit post-submission messaging to reflect the actual review flow.
6. Flesh out concierge Path D into a concrete step-by-step workflow.

## Verification Checklist

After implementation, Claude should verify:

- `rg "/sessions/"` no longer finds active review-app URL references in scripts/docs where `/session/` is intended
- `rg "id_assistant"` in skill/docs no longer implies IDAs use Claude Code for audits/remediation
- `python3 scripts/audit_session_manager.py --help` no longer shows `--scope`
- audit skill examples no longer pass `--scope`
- the 4 target remediation skills now reference `remediation_tracker.py --record` if applicable
- concierge Path D explicitly includes finding context + routing + tracking
- lint/typecheck are not relevant here, but Python scripts should still parse and docs should be internally consistent

## Out Of Scope For This Pass

Do not bundle these into the same change unless directly required:

- post-pilot monolith refactors
- review-app frontend changes
- generalized abstraction cleanup
- session-monitoring enhancements from Claude Code
- automatic finding-aware skill orchestration beyond clearer docs/instructions

## Short Version To Hand Claude

Fix the remaining pre-pilot plugin drift in `IDW-QA`: correct the review-app URL from `/sessions/<id>` to `/session/<id>`, remove `id_assistant` as a Claude Code user path, remove dead `--scope` from `audit_session_manager.py` and its docs, add missing `remediation_tracker.py --record` instructions to the remaining remediation skills, rewrite audit post-submission messaging to match the real admin→IDA→remediation flow, and make concierge Path D concrete enough to run reliably.
