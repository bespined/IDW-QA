# Codex QA Coordinator Review Plan

Findings from QA coordinator walkthrough (2026-04-06). Each item has been deep-dive verified against the codebase. Items span both the Claude Code plugin (`IDW-QA`) and the Vercel review app (`idw-review-app`).

Do not broaden scope beyond these items.

---

## Summary

| # | Item | Repo | Severity | Status |
|---|------|------|----------|--------|
| 1 | N/A label overloaded — means 3 different things | Plugin | High | Confirmed |
| 2 | Double change request submission (no debounce) | Review App | Medium | Confirmed |
| 3 | "View in Canvas" links go to generic modules page | Plugin | Medium | Confirmed |
| 4 | Instructor guide check — literal string match only | Plugin | Medium | Confirmed |
| 5 | Structured per-page evidence too weak / missing | Both | Medium | Confirmed |
| 6 | "Mark as Complete" button — confusing UX | Review App | Medium | Confirmed |
| ~~7~~ | ~~Col B vs Col C not labeled clearly in Airtable~~ | ~~Plugin~~ | ~~Low~~ | **Dropped** — not a code fix, Airtable view config |
| 8 | CLO placeholder / prompt wording in correction form | Review App | Low | Confirmed |
| 9 | Decorative alt text false positives | Plugin | High | **Fixed** |

---

## Fix 1: N/A Label Split (Plugin + Review App)

### Current Problem

`criterion_evaluator.py` emits `"N/A"` status for three distinct situations:

1. **Criterion genuinely doesn't apply** — e.g., no proctoring in course → proctoring checks are N/A
2. **Evaluator can't determine** — regex didn't match, falls back to N/A with "Criterion not matched by deterministic evaluator — needs AI review"
3. **Manual entry required** — Ally score, SCOUT, readability — human must check external tool

All three render identically in the review app. An IDA seeing N/A on "What is the Ally Score?" can't tell if it means "skip" or "go check."

### Required End State

Three distinct statuses with clear labels:

| Status Value | Display Label | Meaning |
|---|---|---|
| `not_applicable` | "Not Applicable" | Criterion doesn't apply to this course (no proctoring, no slide decks, etc.) |
| `needs_review` | "Needs Review" | Evaluator couldn't determine — requires human judgment in Canvas |
| `manual_entry` | "Manual Entry" | Requires data from external tool (Ally, readability analyzer) |

### File Targets

**Plugin:**
- `scripts/criterion_evaluator.py` — all locations emitting `"N/A"` status (lines ~280, 364, 415, 423, 452, 458, 460, 462, 466, 475, 478). Classify each into one of the three new statuses based on evidence string content.
- `scripts/audit_report.py` — update HTML report rendering to show distinct labels/colors per status.

**Review App:**
- `src/components/StandardGroup.tsx` — update finding-status labels/colors for the new status values.
- `src/components/FindingCard.tsx` — update finding-status rendering where the audit verdict/status is shown.
- `src/lib/supabase.ts` — update the `AuditFinding` type if new status values are treated more strictly.
- `src/app/session/[id]/page.tsx` — update any filters/progress logic that currently assumes all non-pass statuses collapse into the existing values.

### Constraints

- Supabase `audit_findings` table uses a `status` text column — no enum migration needed, new values are additive.
- Backward compatible: old "N/A" findings in existing sessions should render as "Not Applicable" (default fallback).

### Classification Table

Use this mapping for the currently verified deterministic `N/A` cases:

| Approx Line | Situation | Current Evidence | New Status |
|---|---|---|---|
| `~280` | Source course provenance cannot be verified by API | `Not determinable via API` | `needs_review` |
| `~364` | No proctoring present | `No proctoring detected` | `not_applicable` |
| `~415` | No separate slide decks | `No separate slide decks` | `not_applicable` |
| `~423` | No proctoring present | `No proctoring` | `not_applicable` |
| `~452` | No critical visual-only video found | `No critical visual-only video detected` | `not_applicable` |
| `~458` | Ally score requires external tool | `Requires Ally dashboard — enter manually` | `manual_entry` |
| `~460` | SCOUT score no longer used | `SCOUT score no longer used — skip` | `not_applicable` |
| `~462` | Readability requires external tool | `Requires readability analysis — enter manually` | `manual_entry` |
| `~466` | Mobile/offline statement needs human review | `Manual review required...` | `needs_review` |
| `~475` | CRC criterion deferred out of this evaluator | `CRC criterion — evaluate separately` | `needs_review` |
| `~478` | Deterministic fallback / unmatched criterion | `Criterion not matched by deterministic evaluator — needs AI review` | `needs_review` |

### Verification

- Re-run `criterion_evaluator.py --quick-check` on a course with known manual-entry and not-applicable cases.
- Confirm the output contains `not_applicable`, `needs_review`, and `manual_entry` instead of a single overloaded `N/A`.
- Confirm older sessions with stored `N/A` still render sensibly as `Not Applicable`.

---

## Fix 2: Double Change Request Submission (Review App)

### Current Problem

`FindingCard.tsx:754-769` — the change request submit button has no loading guard. The `onClick` handler does `await fetch(...)` but the button remains clickable during the request. No `try-catch` either, so errors fail silently.

Other handlers in the same file (e.g., `handleSubmitCorrection` at line 156) properly use a `submitting` state to disable the button during fetch.

### Required End State

- Add `changeRequestLoading` state variable.
- Disable button while fetch is in-flight (same pattern as `handleSubmitCorrection`).
- Wrap fetch in `try-catch` with user-visible error feedback.
- Prevent duplicate records in Supabase.

### File Targets

- `src/components/FindingCard.tsx:754-769` — add loading state, disabled prop, error handling.

### Constraints

- Follow the existing pattern at line 156 (`submitting` state) for consistency.
- No API-side idempotency needed if client-side guard is solid, but consider adding `UNIQUE(session_id, finding_id)` constraint on `change_requests` table as defense-in-depth.

### Verification

- Click the change-request submit button rapidly multiple times in the review app.
- Confirm only one request is created and the button disables while the request is in flight.
- Confirm network/API failures show visible feedback.

---

## Fix 3: Structured Per-Page Evidence (Plugin + Review App)

### Current Problem

Evidence strings contain page slugs but are rendered as plain text, and the review app falls back to a single generic Canvas link. IDAs need direct page links plus concise per-page issue context, but not full excerpts or bloated dumps.

### Required End State

- Emit one structured `affected_pages` field for findings that reference specific Canvas pages.
- Each entry should include:
  - `slug`
  - `title`
  - `url`
  - `issue_summary`
  - optional `issue_count`
- Top-level `canvas_link` should remain as a convenience/fallback link to the most relevant page.
- The review app should render `affected_pages` as a collapsible section:
  - first 3 visible by default
  - `+N more` to expand
  - each row is a direct Canvas link with a 1-sentence issue summary

### File Targets

- `scripts/criterion_evaluator.py` — build specific page URLs from slugs already in evidence and emit structured `affected_pages`.
- `scripts/audit_report.py` — persist `affected_pages` through the RLHF push path and render it in the HTML report.
- add the necessary persistence/serialization path so `affected_pages` survives plugin → Supabase → review app.
- `src/lib/supabase.ts` — add `affected_pages` to `AuditFinding`.
- `src/components/FindingCard.tsx` — render the collapsible affected-pages section.

### Constraints

- The URL pattern is deterministic: `https://{domain}/courses/{id}/pages/{slug}`.
- Don't break existing `canvas_link` field (used by review app) — keep it as a fallback/top-level convenience link.
- Backward compatible: if `affected_pages` is absent (old findings), fall back to existing `canvas_link`.
- Prefer one structured field over multiple overlapping fields (`canvas_links`, `context_excerpt`, etc.).
- Recommended shape:
  ```json
  {
    "affected_pages": [
      {
        "slug": "module-1-overview",
        "title": "Module 1 Overview",
        "url": "https://canvas.asu.edu/courses/123/pages/module-1-overview",
        "issue_summary": "2 images missing alt text near the opening banner",
        "issue_count": 2
      }
    ]
  }
  ```

### Verification

- Run an audit with known multi-page findings (e.g. alt text).
- Confirm the HTML report shows direct per-page links with short issue summaries.
- Confirm the review app shows a collapsed `Affected Pages` section that expands correctly.
- Confirm old findings without `affected_pages` still fall back to `canvas_link`.

---

## Fix 4: Instructor Guide Check — Semantic Expansion (Plugin)

### Current Problem

`criterion_evaluator.py:330` checks only page slugs for "instructor" AND "guide":
```python
guide_pages = [s for s in cd["pages"] if "instructor" in s and "guide" in s]
```

This misses the actual pattern used at ASU: an unpublished **module** called "ASU Online Facilitation Guide" containing sub-pages like "Complete Tasks on Your Preparation and Facilitation Checklist," "Set Up Virtual Office Hours," "Review Zoom Setting Recommendations," etc.

Key context from QA coordinator:
- The guide is a **module**, not just a page.
- Not all sub-pages are used — IDs/faculty pick what's relevant.
- It doesn't need to be in every module — one module containing guide content is sufficient.
- The module is typically unpublished/hidden from students.

### Required End State

**Deterministic layer (expanded):**
1. Search **module names** (not just page slugs) for: "instructor guide", "facilitation guide", "facilitation checklist", "faculty guide", "teaching guide", "instructor resources", "facilitation"
2. Search page slugs with the same expanded terms
3. If either matches → Met

**Quick Check AI verification layer:**
If deterministic check finds nothing, the Quick Check AI verification pass should explicitly look for:
- unpublished/hidden modules with instructor-facing content patterns
- modules containing office hours, Zoom setup, grading checklists, facilitation tasks, or preparation checklists
- likely instructor-guide content regardless of exact naming

### File Targets

- `scripts/criterion_evaluator.py:328-331` — expand deterministic check to include module names and broader keyword set.
- `skills/audit/SKILL.md` — explicitly add instructor-guide validation to the list of Quick Check AI verification heuristics.

### Constraints

- Don't require all sub-pages to be present — the guide module existing at all is sufficient for B-07.1.
- Don't fail the check just because the module is unpublished — that's expected behavior (hidden from students).

### Verification

- Re-run `criterion_evaluator.py --quick-check` on a course with the ASU facilitation guide module.
- Confirm B-07.1 passes even when the guide is an unpublished module rather than a page named `instructor-guide`.

---

## Fix 6: "Mark as Complete" Button UX (Review App)

### Current Problem

`session/[id]/page.tsx:533-555` — the button has two issues:

1. **Dual-state label** (`"Review all findings first (73%)"` → `"Mark as Complete"`) doesn't communicate that it triggers a session status transition, not just a "I'm done" acknowledgment.
2. **Hidden branching logic** — clicking it silently routes to either `mark_complete` or `mark_revisions` depending on disagreements on remediated findings. The IDA has no idea this branching exists.
3. **Same green color** (#78BE20) as "Correct" verdict buttons — doesn't stand out as a workflow-changing action.

### Required End State

- Distinct visual treatment (different color or prominent placement) to signal "this changes the session status."
- If the action will trigger `mark_revisions` (send back to ID), show a confirmation: "Some remediated findings have disagreements — this will send the session back to the ID for revisions. Continue?"
- Consider renaming to "Submit Review" or "Finish Review" to make the action clearer.

### File Targets

- `src/app/session/[id]/page.tsx:533-555` — update button styling, add confirmation modal for revision path.

### Constraints

- Don't change the API contract (`mark_complete` / `mark_revisions` actions stay the same).
- The disabled-at-<100% behavior is correct and should stay.

---

## ~~Fix 7: Col B vs Col C Labeling in Airtable~~ — DROPPED

**Not a code fix.** Investigation of the QA test Airtable base (appHzYJqoyopf4jN8) shows the 207-field schema already names criterion columns with `B-` and `C-` prefixes (106 B-fields, 41 C-fields). The distinction is baked into the column names themselves. Adding a redundant "Column" field doesn't make sense in the one-row-per-course layout.

**Resolution:** Create filtered Airtable views ("Col B Only" / "Col C Only") that hide the opposite column type. This is a 2-minute manual configuration in Airtable, not a code change to `airtable_sync.py`.

---

## Fix 8: CLO Placeholder Wording (Review App)

### Current Problem

`FindingCard.tsx:825` — the correction textarea placeholder reads:
```
"Describe what is actually true (e.g., 'CLOs are present but labeled as Course Learning Outcomes')"
```

Issues:
- "CLOs" is jargon — new IDAs may not know the abbreviation.
- The example is meta-confusing (describes a labeling ambiguity using the ambiguous label).
- "Describe what is actually true" is vague — should clarify: describe what you **see in Canvas**.

### Required End State

Replace with clearer, jargon-free wording. Options:

**Option A (minimal):** Remove the CLO example entirely:
```
"Describe what you see in Canvas (e.g., 'The page exists but is empty' or 'The content is present but under a different heading')"
```

**Option B (specific examples):**
```
"Describe what you found in Canvas (e.g., 'Page exists but has no content' or 'Objectives are present but labeled differently')"
```

### File Targets

- `src/components/FindingCard.tsx:825` — update placeholder text.
- Consider also updating line 837 (`"Any additional context about why the AI was wrong..."`) to be less technical.

### Constraints

- Low priority — copy change only.
- Get QA coordinator sign-off on final wording before shipping.

---

## Fix 9: Decorative Alt Text False Positives (Plugin) — COMPLETED

### What Was Done

`criterion_evaluator.py` treated `alt=""` (Canvas decorative) the same as a truly missing alt attribute. Fixed by:

1. Added `is_decorative` flag to image parsing (line 129) — distinguishes `alt=""` from `alt=None`.
2. Split `imgs_no_alt_by_page` (truly missing) from `imgs_decorative_by_page` (intentionally decorative).
3. Updated B-22.3 (alt text criterion) — decorative images no longer counted as "missing."
4. Updated B-22.4 (decorative criterion) — now reports actual decorative count with verification prompt.
5. Updated Q07 (QA category) — `Fail` → `Warn` when all images have alt or are decorative.
6. Fixed accessibility summary to count Critical vs Warning separately.

**Result:** LAW 517 went from 96 "missing" → 0 truly missing, 96 decorative (Warning — verify intent). Overall score: 87 → 88.

---

## Already Completed / Remove From Active Queue

- **Bulk session assign** is already implemented and manually verified:
  - `/assign` supports bulk assignment intent in the skill flow
  - `admin_actions.py` includes `--list-unassigned` and `--assign-session`
  - `/api/session-assign` accepts `session_ids` for bulk assignment
  - review app admin UI has `Assign Selected` / `Clear Selected`

Do not include bulk assignment in the active implementation queue for this plan.

---

## Implementation Order

Recommended sequencing based on pilot impact:

| Phase | Items | Rationale | Status |
|---|---|---|---|
| **Phase 1 — Pilot blockers** | Fix 1 (N/A split), Fix 4 (instructor guide) | High-severity findings that produce misleading audit results | **Done** |
| **Phase 2 — Review app UX** | Fix 2 (double submit), Fix 6 (complete button), Fix 8 (CLO wording) | Direct IDA workflow friction | **Done** |
| **Phase 3 — Evidence quality** | Fix 3 (structured per-page evidence) | One coordinated evidence contract instead of multiple overlapping fields | **Done** |
| ~~Phase 4~~ | ~~Fix 7 (Airtable labeling)~~ | ~~Dropped — Airtable columns already prefixed B-/C-, create filtered views instead~~ | **Dropped** |
