# Codex Workflow Review Checklist

This checklist is for learning the system by reviewing one workflow at a time.

Use it when you want to understand:
- how a workflow actually works
- which files own each step
- where the state changes happen
- where wording, code, and product process can drift

This is not a coding exercise. It is a **workflow comprehension** exercise.

---

## How To Use This

Pick one workflow, for example:
- onboarding
- ID audit upload
- portal review
- admin session assignment
- ID Assistant review
- remediation
- Airtable sync

Then work through the checklist in order.

Do not try to understand the whole system at once.
Do one workflow at a time.

---

## Step 1 — Name The Workflow

Write a one-line title:

> Example: "ID uploads audit findings to the QA portal"

Then answer:

- Who starts this workflow?
- Why are they doing it?
- What is the intended outcome?

Template:

```md
Workflow:
Actor:
Goal:
End state:
```

---

## Step 2 — Write The Workflow In Plain English First

Before looking deeply at code, write the steps in your own words.

Keep it short:

1. User does X
2. System does Y
3. User sees Z
4. State changes to A

This is your **starting mental model**.

Do not worry if it is wrong. The point is to compare it to reality.

---

## Step 3 — Find The Source Of Truth

For the workflow you picked, identify:

- the canonical workflow spec section
- the skill/doc that describes it
- the backend/script that enforces it
- the frontend route/UI that exposes it
- the DB table/fields that store its state

Template:

```md
Workflow spec:
User-facing doc/skill:
Backend/script owner:
Frontend owner:
DB owner:
```

Questions to answer:

- Which file describes the workflow?
- Which file actually enforces the workflow?
- Are they the same thing?

---

## Step 4 — Map Inputs And Outputs

For the chosen workflow, list:

### Inputs
- user action
- request body
- CLI args
- env vars
- DB rows read

### Outputs
- DB rows inserted/updated
- files written
- session state changes
- UI messages shown
- URLs/IDs returned

Template:

```md
Inputs:
- 

Outputs:
- 
```

Questions:

- What starts the workflow technically?
- What data must already exist?
- What new data is created?

---

## Step 5 — Trace The State Changes

This is the most important part.

Write:

- what state existed before
- what state exists after
- where the transition is enforced

Template:

```md
Before:
After:
Transition owner:
```

Examples:

- no session -> session created
- `in_progress` -> `pending_qa_review`
- unassigned -> assigned to IDA
- remediation requested false -> true

Questions:

- Which table/field changes?
- Is the transition happening in the right layer?
- Is the state name consistent with the user-facing wording?

---

## Step 6 — Identify Role Boundaries

For every workflow, answer:

- which roles can start it?
- which roles can view it?
- which roles can complete it?
- where is that enforced?

Template:

```md
Allowed roles:
- 

Blocked roles:
- 

Enforced in:
- 
```

Questions:

- Is role enforcement in the client only, or server/script side too?
- Could the wrong role hit this path directly?
- Is object-level access also enforced, not just role?

---

## Step 7 — Identify User-Facing Wording

Write down the exact phrases the user sees during this workflow.

Examples:

- "Upload to QA portal"
- "Submit for QA Review"
- "Assign to ID Assistant"

Questions:

- Does the wording match the actual workflow stage?
- Does any phrase imply the wrong next step?
- Does the code create a different state than the wording suggests?

This step catches a lot of drift.

---

## Step 8 — Find Failure Modes

For the workflow, list the top 3-5 ways it can fail.

Think in plain language:

- missing tester identity
- wrong role
- missing course ID
- invite fails after row creation
- session created but wrong purpose
- route succeeds but UI message is misleading

Template:

```md
Likely failure modes:
1.
2.
3.
```

Questions:

- What happens if a required dependency is missing?
- Does failure leave behind partial state?
- Is the failure visible to the user/admin?

---

## Step 9 — Decide What Needs Manual Testing

For each workflow, separate:

### Safe to verify by reading code
- static mapping logic
- obvious field wiring
- doc drift
- deterministic script output shape

### Needs runtime/manual testing
- auth/session cookies
- role enforcement in deployed app
- DB side effects across multiple systems
- browser flow behavior
- invite/login emails

Template:

```md
Source review is enough for:
- 

Manual/runtime testing needed for:
- 
```

This builds your judgment about when code reading is enough and when it is not.

---

## Step 10 — Write Your Explanation

Now write the workflow explanation as if you were explaining it to:

- a product manager
- an AI lead
- a new teammate

Keep it to:

1. purpose
2. actor
3. steps
4. state change
5. risk points

Template:

```md
This workflow exists so that...
It starts when...
The system then...
The key state change is...
The biggest risk/drift area is...
```

This is the exercise that improves your ability to translate code into English.

---

## Step 11 — Review Your Explanation

Give your explanation to Claude or Codex and ask:

1. What is incorrect?
2. What is missing?
3. What did I misunderstand?
4. What file/route/script actually owns this step?
5. What part still needs manual testing?

Then rewrite your explanation.

Repeat until the explanation is tight.

---

## Step 12 — Capture Drift

After reviewing the workflow, write:

### Aligned
- what matches the canonical workflow

### Drift
- docs say X, code does Y
- UI says A, state transition is B
- wrong layer owns the transition

### Needed action
- no action
- doc fix
- narrow implementation plan
- manual test

Template:

```md
Aligned:
- 

Drift:
- 

Action:
- 
```

---

## Workflow Review Questions

Use these for every workflow:

1. What is the exact start trigger?
2. Who is allowed to trigger it?
3. What data does it read?
4. What data does it write?
5. What state changes?
6. What wording does the user see?
7. Does the wording match the state?
8. Which file owns the business rule?
9. Which file only describes it?
10. What can fail halfway?
11. What requires manual testing?
12. Is this workflow aligned with the canonical workflow spec?

---

## Recommended Workflow Review Order

Do these in this order:

1. Onboarding
2. Claude Code identity + Canvas setup
3. ID audit flow
4. Audit upload to portal
5. ID portal review + submit for QA review
6. Admin session assignment
7. ID Assistant review flow
8. Admin approval/revisions flow
9. Remediation flow
10. Airtable sync/reporting flow

This order works well because each later workflow depends on the earlier ones.

---

## What Good Looks Like

You understand a workflow well when you can explain:

- who starts it
- why it exists
- which file owns the rule
- which DB fields change
- which user-facing words correspond to which state
- what can fail
- whether code review alone is enough or runtime testing is required

If you can do that clearly, you understand the workflow.

---

## Best Practice

When a workflow changes:

1. update the canonical workflow spec first
2. review alignment against the codebase
3. make an implementation plan
4. implement
5. review again

That is how you reduce drift over time.
