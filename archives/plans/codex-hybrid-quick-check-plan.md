# Codex Hybrid Quick Check Plan

Quick Check is already designed as deterministic + light AI verification (see `skills/audit/SKILL.md` lines 101-107). But the AI verification pass is generic — it doesn't know which specific criteria to double-check. This plan adds targeted AI verification for criteria where the deterministic engine is structurally unable to produce reliable results.

Do not broaden scope beyond the items listed here.

---

## Summary

| # | Item | Type | Impact |
|---|------|------|--------|
| 1 | B-04 catch-all silently passes unhandled criteria | Deterministic fix | False positives |
| 2 | B-10.2 (practice assessments) always returns Met | Deterministic fix | False positives |
| 3 | B-04.29 (eval reminder) narrow keyword matching | Deterministic fix | False negatives |
| 4 | Hybrid Quick Check target set for weak B-criteria | AI verification | Reduces false positives/negatives |
| 5 | Evaluator outputs `needs_ai_verification` flag | Structural | Enables targeted AI pass |
| 6 | SKILL.md AI verification checklist | Prompt update | Directs the AI pass |

---

## Phase A — Deterministic Fixes (no AI, just better logic)

These can be fixed entirely within `criterion_evaluator.py` without any AI involvement.

### Fix 1: B-04 catch-all — stop silently passing unhandled criteria

**Current problem:**
`criterion_evaluator.py:374` — any B-04 criterion that doesn't match a specific keyword check falls through to:
```python
return ("Met", "Layout element present")
```
This masks unhandled criteria as passing.

**Required end state:**
Change the catch-all to `needs_review` so unhandled B-04 criteria surface for human or AI review instead of silently passing.

**File targets:**
- `scripts/criterion_evaluator.py:374`

**Change:**
```python
# Before
return ("Met", "Layout element present")

# After
return ("needs_review", "B-04 criterion not matched by specific check — needs verification")
```

**Risk:** Some B-04 criteria that currently pass via the catch-all may be legitimately Met but just lack a specific handler. After this change, they'll surface as `needs_review`. This is the correct behavior — better to flag for review than to silently assume Met.

**Verification:**
- Run `--quick-check` on LAW 517.
- Identify which B-04 criteria were previously falling through to the catch-all.
- Confirm they now show `needs_review` instead of `Met`.
- If any are clearly deterministic (can be checked via existing data), add specific handlers for them.

### Fix 2: B-10.2 (practice assessments) — actually check the data

**Current problem:**
`criterion_evaluator.py:443-444` — always returns Met without checking:
```python
if "ungraded" in t or "practice" in t:
    return ("Met", "Practice activities available")
```

**Required end state:**
Check the `assignments` data (already fetched) for items with `points_possible == 0` or `grading_type == "not_graded"` or `submission_types` containing `"not_graded"`. Also check for quizzes with `quiz_type == "practice_quiz"`.

**File targets:**
- `scripts/criterion_evaluator.py:443-444`

**Verification:**
- Run on a course with known practice quizzes → should be Met with specific evidence.
- Run on a course with no practice assessments → should be Not Met or Partially Met.

### Fix 3: B-04.29 (eval reminder) — expand keywords

**Current problem:**
`has_eval_reminder` (defined in the page data aggregation) likely uses narrow keyword matching. Need to verify what it checks and expand.

**Required end state:**
Search page content for: "course evaluation", "student evaluation", "end-of-course survey", "course feedback", "please complete the evaluation", "your feedback about this course", "course survey". Also check page slugs for "evaluation", "course-eval", "feedback".

**File targets:**
- `scripts/criterion_evaluator.py` — wherever `has_eval_reminder` is computed (page data aggregation section, ~line 150-200).

**Verification:**
- Run on LAW 517 — confirm eval reminder is detected with expanded keywords.

---

## Phase B — Hybrid Target Set + `needs_ai_verification`

Before adding AI checks, the evaluator needs:
1. a clear target set of B-criteria where hybrid verification is actually useful
2. a way to signal "I produced a result but it's unreliable — AI should double-check this."

### Fix 4: Define the hybrid Quick Check target set

**Current problem:**
The repo already has a `LOW_CONFIDENCE` bucket in `criterion_evaluator.py`, but the Quick Check AI verification step does not use it directly. The current plan also mixes together three different categories:
- criteria that should be improved deterministically
- criteria that should be hybrid-checked by AI
- criteria that require external tools and should stay `manual_entry`

That will drift unless the plan explicitly separates them.

**Required end state:**
Use one explicit hybrid target set for Quick Check. The AI verification pass should only re-check these B-criteria:

- `B-04.23` — welcome communication
- `B-04.24` — course tour
- `B-06.1` — workload details provided
- `B-06.2` — time commitments clearly communicated
- `B-09.1` — assessment instructions clearly explain expectations
- `B-13.1` — citations
- `B-13.2` — video playback in student view
- `B-13.3` — links work
- `B-13.10` — typos
- `B-13.11` — grammar accuracy
- `B-13.13` — formatting consistency
- `B-13.14` — text density
- `B-17.1` — moderation policy
- `B-17.2` — response turnaround time
- `B-22.5` — meaningful/descriptive link text
- `B-24.1` — mobile/offline access statements

These should explicitly stay out of hybrid Quick Check:
- `B-22.9` — Ally score
- `B-22.11` — readability score

Those remain `manual_entry` because AI cannot replace the external tool.

**Constraints:**
- Do not hybridize criteria that can be made reliably deterministic with a simple parser fix.
- Do not hybridize external-tool criteria.
- Keep the hybrid list aligned with the existing low-confidence/problematic evaluator paths instead of inventing a second drifting list.

**Verification:**
- Compare the target set against `LOW_CONFIDENCE` in `criterion_evaluator.py`.
- Confirm every hybrid criterion is one where AI can realistically add value from page content.
- Confirm `B-22.9` and `B-22.11` remain outside the hybrid set.

### Fix 5: Add `needs_ai_verification` flag to criterion results

**Current problem:**
The evaluator returns a status + evidence for every criterion, but there's no way to distinguish "I'm confident about this" from "I'm guessing." The `confidence` field exists but is coarse (high/medium/low) and isn't used to drive AI verification.

**Required end state:**
Add a boolean `needs_ai_verification` field to criterion results. When `True`, the AI verification pass in Quick Check should re-evaluate this criterion using page content.

Criteria that should set `needs_ai_verification: True`:
- B-04.23 (welcome communication) — when deterministic says Not Met
- B-04.24 (course tour) — when deterministic says Not Met
- B-06.1, B-06.2 — when deterministic says Not Met or Partially Met
- B-09.1 — always
- B-13.1, B-13.2, B-13.3, B-13.10, B-13.11, B-13.13, B-13.14 — always
- B-17.1, B-17.2 — always
- B-22.5 — always
- B-24.1 — always
- Any criterion that falls through to a catch-all or returns a static default

**File targets:**
- `scripts/criterion_evaluator.py` — add `needs_ai_verification` to the result dict in `evaluate_all()` (alongside existing `needs_ai_review`).
- Key difference: `needs_ai_review` means "this is a C-criterion that hasn't been evaluated at all." `needs_ai_verification` means "this is a B-criterion that has a deterministic result but the result may be wrong."

**Implementation:**
After `evaluate_b_criterion` returns, check if the criterion ID is in a `NEEDS_AI_VERIFICATION` set:
```python
NEEDS_AI_VERIFICATION = {
    "B-04.23", "B-04.24",
    "B-06.1", "B-06.2",
    "B-09.1",
    "B-13.1", "B-13.2", "B-13.3", "B-13.10", "B-13.11", "B-13.13", "B-13.14",
    "B-17.1", "B-17.2",
    "B-22.5",
    "B-24.1",
}

# Also flag dynamically: any B-04 that hits the catch-all
# Also flag: any criterion with a static default or fallback-only result
```

**Verification:**
- Run `--quick-check` and confirm flagged criteria have `needs_ai_verification: true` in the JSON output.

---

## Phase C — SKILL.md AI Verification Checklist

### Fix 6: Explicit AI verification checklist in SKILL.md

**Current problem:**
The AI verification step in `skills/audit/SKILL.md` says:
> "The AI checks for obvious false positives and false negatives — pages that exist but are empty, CLOs that technically use measurable verbs but are meaningless, template placeholders that weren't caught by regex."

This is too generic. The AI doesn't know which specific criteria to re-examine.

**Required end state:**
The SKILL.md should instruct the AI verification pass to:

1. Read the `needs_ai_verification` flags from the evaluator output.
2. For each flagged criterion, re-evaluate using the relevant page content.
3. Override the deterministic result when the AI disagrees, with evidence.

Add a specific checklist to the SKILL.md:

```
AI verification targets (check these when flagged):

B-04.23/24 (welcome communication, course tour):
  → Read the welcome/getting-started module pages
  → Look for any video or text that introduces the instructor or orients students
  → Override to Met if found, citing the specific page

B-06.1/06.2 (workload details, time commitments):
  → Read the syllabus and module overview pages
  → Look for concrete workload language, time estimates, weekly pacing, or expected hours
  → Override only when specific workload/time language exists

B-09.1 (assessment instructions):
  → Spot-check assignment, quiz, and discussion descriptions
  → Look for clear completion expectations, required components, submission expectations, or grading cues
  → Override only when directions are clearly substantive

B-17.1 (moderation policy):
  → Read the community forum / discussion instructions / syllabus
  → Look for any language about discussion expectations, moderation, netiquette
  → Override to Met if found, citing the specific text

B-17.2 (response time):
  → Read the syllabus + discussion instructions + getting-started pages
  → Look for any response time commitment (e.g., "within 24-48 hours")
  → Override to Met if found, citing the specific text

B-13.1/2/3/10/11/13/14 and B-22.5 (content quality spot-check):
  → Spot-check 3-5 content pages from different modules
  → Flag obvious issues only (clearly missing citations, broken embeds, vague "click here" links, obvious typos, extremely dense text, visibly inconsistent formatting)
  → Do NOT attempt comprehensive link checking or full typo/grammar scanning
  → Override to Partially Met or Not Met only when clear evidence exists

B-24.1 (mobile/offline access statements):
  → Read the syllabus, getting-started content, and support/help pages
  → Look for explicit statements about what works on mobile versus what requires laptop/desktop access
  → Keep as Needs Review if no explicit statement exists

Instructor guide (B-07.1) — already handled by existing AI verification heuristic.
```

**File targets:**
- `skills/audit/SKILL.md` — expand the AI verification step (around line 105-110) with the structured checklist above.

**Verification:**
- Run a Quick Check with AI verification enabled on a course.
- Confirm the AI addresses flagged criteria specifically rather than doing a generic scan.

---

## Constraints

- Quick Check must remain fast. The AI verification pass should examine only flagged hybrid criteria, not re-evaluate all 106.
- The deterministic engine remains the source of truth for structural checks. AI only overrides when it has specific evidence.
- The `needs_ai_verification` flag is purely informational for the AI pass — it doesn't change the deterministic result in the JSON output. The AI decides whether to override.
- All changes are backward compatible. Older audit results without `needs_ai_verification` still work.
- Do not touch C-criteria. This plan is B-criteria only.
- Do not use AI to replace external tools. `B-22.9` and `B-22.11` remain manual-entry criteria.

---

## Implementation Order

| Phase | Items | Rationale |
|---|---|---|
| **Phase A — Deterministic** | Fix 1 (B-04 catch-all), Fix 2 (practice assessments), Fix 3 (eval reminder) | Pure Python, no AI, fixes the most obvious false positives/negatives |
| **Phase B — Hybrid structure** | Fix 4 (hybrid target set), Fix 5 (`needs_ai_verification` flag) | Defines exactly which B-criteria should be re-checked by AI |
| **Phase C — AI checklist** | Fix 6 (SKILL.md update) | Directs the AI pass to use the new flag and re-evaluate specific criteria |

Phase A can ship independently. Phases B and C should ship together.

---

## What this does NOT cover

- Comprehensive link checking (would require HTTP requests to every link — too slow for Quick Check)
- Full typo/grammar scanning (would require running every page through a language model — Deep Audit territory)
- Video playback verification (would require browser automation — not feasible in Quick Check)
- Document accessibility checking (requires Ally — stays as `manual_entry`)

These remain honest about their limitations: the deterministic engine says "Met" with low confidence, the AI spot-checks a sample, and the rest is flagged for human verification in the review app.
