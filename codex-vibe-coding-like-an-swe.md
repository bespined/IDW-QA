# Vibe Coding Like An SWE

> **Type: Evergreen reference.** Not a plan — a checklist for engineering judgment when building with AI tools.

## Purpose

Use this checklist when building features with Claude, Codex, or any AI coding tool so you keep product momentum without skipping core engineering judgment.

The goal is not “write perfect code.”

The goal is:

- safe enough
- consistent enough
- testable enough
- operable enough

## The 8 Questions

Before shipping any meaningful feature, ask:

1. Who is allowed to do this?
2. Where is that permission enforced?
3. Am I trusting anything from the client that should be decided on the server?
4. Am I duplicating logic that already exists somewhere else?
5. How will I know if this broke something?
6. If this fails in production, will it fail loudly or silently?
7. Can I undo or contain damage if this goes wrong?
8. What is the smallest proof that this still works after my change?

If you consistently ask these 8 questions, you are already thinking more like an SWE.

## 1. Security Boundaries

Think:

- client is untrusted
- browser payload is untrusted
- secrets stay server-side
- server decides identity and permissions

Ask:

- Can a random user call this route directly?
- Does this code use a privileged key?
- Am I trusting `user_id`, `role`, or ownership from the request body?
- Is authorization checked before the write happens?

Good defaults:

- derive actor IDs server-side
- derive roles server-side
- validate inputs before writes
- never expose service keys to the browser

## 2. Consistency Of Shared Abstractions

Think:

- if this rule changes later, how many places must be updated?

Ask:

- Is there already a helper for this?
- Am I bypassing the shared path because it is faster right now?
- Will this create drift between two workflows that should behave the same?

Good defaults:

- one auth helper
- one config path
- one status-transition path
- one write wrapper for risky operations

Warning sign:

- the same rule exists in 3+ places

## 3. Regression Protection

Think:

- how will I know I broke existing behavior?

Ask:

- What are the 3-5 workflows that absolutely must keep working?
- What is the cheapest test or smoke check for each?
- What output should stay stable after refactoring?

Good defaults:

- always run lint
- always run typecheck
- keep one smoke checklist for critical flows
- use golden fixtures for complex logic where possible

For small products, “regression protection” can start as:

- one test
- one fixture
- one manual checklist

It does not need to start as a giant test suite.

## 4. Operational Hardening

Think:

- when this breaks, how will we detect it and recover?

Ask:

- Does this fail visibly?
- Is there enough logging context?
- Can I see which user, session, course, or record was affected?
- Is there a rollback or read-only mode?
- Can I temporarily disable this without taking down the whole system?

Good defaults for important write paths:

- validation
- authorization
- structured logging
- explicit error handling
- recovery path

## 5. Shipping Checklist

Before merging or deploying:

- Auth: correct roles enforced
- Ownership: users can only act on allowed records
- Secrets: no privileged keys in client code
- Reuse: no unnecessary bypass of shared helpers
- Errors: failures are visible to the user or operator
- Logging: enough context to debug
- Verification: lint + typecheck + smoke check
- Rollback: you know how to undo the change

## 6. Prompting AI Better

When asking Claude or Codex to build something, include:

- the user role
- the exact mutation or workflow
- the allowed permissions
- the shared helper it should reuse
- the validation rules
- what must not be trusted from the client
- how to verify the result

Example:

“Add a server route for this admin action. Reuse the shared auth helper. Do not trust actor IDs from the client. Derive identity from auth server-side. Return 401/403/400/500 correctly. Update the UI to show failure visibly. Run lint and typecheck.”

That prompt is much stronger than “build this feature.”

## 7. What Good Looks Like

A solid AI-built feature usually has:

- the right behavior
- the right permissions
- one clear path for shared logic
- visible failure handling
- a basic proof it still works

That is the bar for a practical product.

## 8. What To Avoid

Watch for these patterns:

- public route using a service key
- trusting `role`, `user_id`, or `resolved_by` from the client
- copy-pasted business logic across files
- silent failures
- “fixes” that only satisfy lint but not correctness
- refactors without any proof of preserved behavior

## 9. A Good Weekly Habit

Once a week, ask:

- What are the top 3 risks in this system?
- Where are we trusting too much?
- What breaks silently today?
- What duplicated logic should be consolidated later?
- What one smoke test would buy the most confidence?

That habit compounds quickly.

## Short Version

Build fast, but always ask:

- Who can do this?
- Where is that enforced?
- What am I trusting?
- What logic am I duplicating?
- How do I know it still works?
- How do I detect failure?
- How do I recover?

That is the core mindset shift from “just vibe coding” to “vibe coding with engineering judgment.”
