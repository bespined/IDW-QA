# IDA Access Options — Canvas API + Claude Code Decision

## The Question

Should IDAs have Canvas API tokens and Claude Code installed, or should they only access the Vercel review app?

This decision affects recurring course audit workflow, IDA onboarding, QA team workload, and system scaling.

---

## Option A: IDAs DO NOT have Canvas API + Claude Code

### What IDAs need
- Web browser
- Vercel app login (via Supabase — name, role, UUID already in testers table)

### What IDAs do NOT need
- Canvas API token
- Claude Code installation
- Terminal/CLI knowledge

### Workflow impact

| Workflow | Who triggers audit | Who reviews |
|---|---|---|
| New course | ID (own token + Claude Code) | IDAs verdict Col B → QA team IDs verdict all |
| Recurring | **QA team** (QA token + Claude Code) | IDAs verdict Col B → QA team IDs verdict all |

### Pros
- Zero IDA onboarding friction — just open a URL
- No token management for IDAs
- No Claude Code support burden for IDAs
- IDAs focus purely on review (agree/disagree), not running tools
- Simpler permission model — IDAs never touch Canvas programmatically

### Cons
- QA team must trigger every recurring audit manually
- QA team becomes bottleneck: if they're busy, recurring audits queue up
- Doesn't scale beyond QA team's capacity to run audits
- QA team needs to manage tokens for all courses IDAs are assigned to

### Best if
- IDA pool is non-technical
- Canvas admin won't issue API tokens to IDAs
- Pilot phase (keep it simple, validate the review workflow first)
- QA team has bandwidth to run audits

---

## Option B: IDAs HAVE Canvas API + Claude Code

### What IDAs need
- Web browser (for Vercel app)
- Canvas API token (personal access token from Canvas admin)
- Claude Code installed on their machine
- Basic training on running `/audit` command

### Workflow impact

| Workflow | Who triggers audit | Who reviews |
|---|---|---|
| New course | ID (own token + Claude Code) | IDAs verdict Col B → QA team IDs verdict all |
| Recurring | **IDA** (own token + Claude Code) | IDA verdicts own results → QA team IDs verdict all |

### Pros
- QA team bottleneck removed — IDAs trigger their own audits
- Scales with IDA headcount (more IDAs = more recurring audits processed)
- IDAs develop deeper understanding of the audit process
- QA team freed up to focus on qualitative review (Col C) and launch gates

### Cons
- Higher onboarding: install Claude Code, get Canvas token, learn CLI
- More support surface: token issues, setup problems, Claude Code updates
- IDAs run Mode 5 (deterministic only) — they still can't do qualitative checks
- Canvas admin must approve token issuance for IDAs
- More points of failure per IDA

### Best if
- IDA pool is somewhat technical or trainable
- Canvas admin will issue API tokens
- Large volume of recurring audits exceeds QA team capacity
- Post-pilot phase where the review workflow is already validated

---

## Comparison Table

| Dimension | Option A (No Canvas) | Option B (Has Canvas) |
|---|---|---|
| IDA onboarding | Open URL, log in | Install Claude Code, get token, learn CLI |
| IDA daily workflow | Open Vercel → click agree/disagree | Run /audit in CLI → then open Vercel → click agree/disagree |
| Who triggers recurring audits | QA team only | IDAs themselves |
| QA team workload | Trigger + review | Review only |
| Scaling | Limited by QA team | Scales with IDA count |
| Support burden | Low (web app only) | Higher (CLI + tokens + setup) |
| Token management | QA team tokens only | QA team + all IDA tokens |
| Canvas admin approval needed | No (IDAs never touch API) | Yes (IDAs need personal tokens) |
| Pilot readiness | Ready now | Requires IDA training + token provisioning |

---

## Recommendation for Discussion

**Start with Option A for pilot.** Validate the review workflow (agree/disagree on findings) without adding the complexity of IDA Claude Code setup. If recurring audit volume exceeds QA team capacity, transition IDAs to Option B post-pilot.

This is not a permanent decision — the Vercel app and Supabase schema work identically in both options. The only difference is who triggers the audit and what software IDAs need installed.

---

## IDA Context (from QA team)

- **IDAs are CS masters students** — technically capable, comfortable with CLI tools
- **IDAs are student workers** (not full-time employees) — semester-long tenure unless renewed
- **Semester turnover** — every semester: new IDAs onboarded, departing IDAs offboarded
- **New hires may not have ASU email for weeks** — institutional SSO is not viable for day-one access

### Turnover implications for Option B
- Every semester: Canvas tokens provisioned + Claude Code installed + training for new IDAs
- If Canvas admin is slow to issue tokens → IDA is blocked for weeks
- Departing IDAs need token revocation
- Training investment is repeated every semester

### Auth decision for pilot
- **Email + password via Supabase Auth** — QA admin creates account in testers table before IDA starts
- Day one: IDA logs in with credentials, no ASU email needed
- Post-pilot: link ASU email for SSO when available, UUID preserves all verdict history

---

## Questions for QA Team + Airtable Manager

1. Will Canvas admin issue personal API tokens to IDAs (student workers)? (Determines feasibility of Option B)
2. How many recurring courses need auditing per cycle? (Determines if QA team can handle audit triggers alone)
3. Are IDAs comfortable with CLI tools, or is web-only strongly preferred? (Context: they are CS masters students — CLI is feasible)
4. For pilot: is Option A acceptable to validate the review workflow first?
