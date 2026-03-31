---
name: audit
description: "Audit a Canvas course: design standards, accessibility, or launch readiness."
---

# Audit

> **Run**: `/audit`

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python scripts/idw_metrics.py --track skill_invoked --context '{"skill": "audit"}'
```
This records usage metrics for the pilot dashboard. Do not skip this step.

## Purpose

Unified audit skill with 3 modes: Quick Scan (deterministic only), Full Audit (deterministic + AI), and Guided Review (interactive with live fixes). All modes use a single check registry with scope filters.

## When to Use

- "Audit my course" / "Check my course" / "Quick scan" → **Ask which mode** (see Entry Point below)
- "Quick scan" / "Fast audit" / "Deterministic check" → **Quick Scan** (skip prompt)
- "Full audit" / "Complete audit" / "Comprehensive audit" → **Full Audit** (skip prompt)
- "Walk me through it" / "Audit with me" / "Interactive audit" / "Guided review" → **Guided Review** (skip prompt)
- "Just check essential standards" → **Full Audit --scope essential** (skip prompt)

## Audit Purpose Inference

**Before any other setup**, determine `audit_purpose` from the tester's role. This controls the Supabase session type, who can verdict findings in the review app, and the post-audit workflow.

```bash
python3 scripts/role_gate.py --check any
```

| Tester Role | Context | `audit_purpose` |
|---|---|---|
| `id` | Running on their own course (course ID matches an assignment they own) | `self_audit` |
| `id` | Running on a course assigned to another tester (QA review of someone else's work) | `qa_review` |
| `id_assistant` | Running on any assigned course | `recurring` |
| `admin` | Running on any course | `qa_review` |

**Infer from context:**
- If `id_assistant` role → always `recurring`
- If `id` or `admin` role → check whether the course matches a `tester_course_assignments` row owned by another tester. If yes → `qa_review`. Otherwise → `self_audit`.
- Store the inferred `audit_purpose` and use it when creating the Supabase `audit_sessions` row.

**Also infer `audit_round`**: Query `audit_sessions` for prior sessions on this course + purpose combination. `audit_round` = count of prior sessions + 1. Pass to the audit session row and to `audit_report.py`.

---

## Entry Point — Course Selection

Before asking about audit mode, determine which course(s) to audit. Use `AskUserQuestion`:

| Option | Label | Description |
|---|---|---|
| 1 | **Current course** | Audit the course in `.env` (show course name for confirmation) |
| 2 | **Pick from my assignments** | Show courses assigned to me via `/assignments` and let me choose |
| 3 | **Batch audit** | Audit multiple courses sequentially — I'll pick which ones |
| 4 | **Different course** | Let me provide a course URL or ID |

**Skip this prompt** if the user already specified a course (e.g., "audit BIO 101" or "audit course 223406").

**For Batch Audit:**
1. Show the user's assigned courses (from `tester_course_assignments`) or let them paste a list of course IDs
2. Confirm the list: "I'll audit these N courses sequentially: [list]. Each takes ~10 minutes for Deep Audit. Continue?"
3. Run the audit on each course in sequence, generating separate reports and sessions for each
4. At the end, show a summary table: Course | Score | Standards Met | Critical Issues
5. Each course gets its own Supabase session and HTML report

## Audit Mode Selection

When the user asks for a general audit without specifying a mode, **always present the choice first** before fetching any data. Use `AskUserQuestion` with these options:

| Option | Label | Description |
|---|---|---|
| 1 | **Quick Check** | Fast structural check with AI verification — catches setup issues and obvious content gaps. Takes 1-2 minutes. Best for recurring audits and pre-checks. |
| 2 | **Deep Audit** | Comprehensive quality review — evaluates alignment, assessment design, content quality, and instructional effectiveness in depth. Takes 10-15 minutes. |
| 3 | **Guided Review** | Same depth as Deep Audit but walks through the course with you section by section, pausing after each to review findings and fix issues on the spot. Best when you're actively building the course. |

Only skip this prompt when the user's message clearly specifies a mode.

**If the user picks Quick Check**, follow up with a scope question using `AskUserQuestion`:

| Option | Label | Description |
|---|---|---|
| 1 | **All standards + course readiness** | Checks all 25 design standards and course readiness items for structural issues (does it exist? is it set up correctly?) with a light AI verification pass to catch false positives. |
| 2 | **Essential standards only** | Focus on the 7 core standards required for course launch (alignment, workload, assessments, materials, accessibility). |
| 3 | **Course readiness** | Template setup, navigation links, syllabus content, dates, and other launch-day checks. |

**If the user picks Deep Audit or Guided Review**, always run all standards — no scope question.

### Scope Filter Reference (internal — do not present to user)

| Scope | What's included | Triggered by |
|---|---|---|
| `all` (default) | All 25 standards + CRC items (98 criteria) | Default — no user prompt |
| `essential` | 7 essential standards: 01, 02, 06, 08, 12, 22, 23 | User says "essential" or "essential standards only" |
| `crc` | 18 CRC operational items | User says "CRC" or "operational checklist" or "readiness check" |

To filter: load `config/standards.yaml`, include only criteria where the parent standard has `essential: true` (for essential scope) or criteria with `category: "crc"` (for crc scope).

### Staging Requirement

**All page content changes MUST go through staging.** If the audit finds issues and the user asks to fix them, stage the fix first — never push HTML directly to Canvas. The flow is always: stage → preview → user approves → push. This applies to Quick Scan, Full Audit, and Guided Review equally. See CLAUDE.md for the full staging workflow.

---

## Two-Pass Architecture (used by all modes)

All modes use the same check registry from `config/standards.yaml`. Quick Scan runs Pass 1 only. Full Audit and Guided Review run both passes.

### Reviewer Tier Tagging

Every finding MUST be tagged with `reviewer_tier` from `standards.yaml`:
- `reviewer_tier: "id_assistant"` — Col B checks (deterministic/existence). IDAs can verdict these.
- `reviewer_tier: "id"` — Col C checks (qualitative/judgment). Only QA team IDs verdict these.

### Quick Check (Mode 1)

Runs **Pass 1 (deterministic) + light AI verification**. Two steps:
1. All deterministic checks run via `deterministic_checks.py`
2. One AI verification call: Claude receives a summary of all deterministic results + raw content from flagged pages (syllabus body, module overviews, CLO text). The AI checks for obvious false positives and false negatives — pages that exist but are empty, CLOs that technically use measurable verbs but are meaningless, template placeholders that weren't caught by regex. The AI does NOT evaluate instructional quality — that's what Deep Audit does.

All findings tagged `reviewer_tier: "id_assistant"`. This is what the QA team runs for recurring courses reviewed by student workers (`id_assistant` role).

### Deep Audit (Mode 2)

Runs **Pass 1 + Pass 2 (full AI evaluation)**. Comprehensive evaluation against all 25 ASU Online Course Design Standards plus 18 CRC operational checks. Each standard gets individual AI judgment using enrichment cards from `standards_enrichment.yaml`. Findings tagged with appropriate `reviewer_tier` from standards.yaml.

### Standards Reference Files
- `config/standards.yaml` — Base definitions of 25 standards
- `config/standards_enrichment.yaml` — Enriched with measurable_criteria, expectations, considerations, examples, and research citations

### Progress Reporting

During any audit mode, report progress to the user as each major step completes. Never leave the user waiting in silence.

```
  → Fetching course data...
✓ Course data loaded: 7 modules, 42 pages, 14 quizzes, 7 assignments
  → Evaluating Standard 1 of 25: Measurable Learning Objectives...
✓ Standards 1-5 evaluated (Structure & Navigation)
✓ Standards 6-10 evaluated (Assessments)
  → Standards 11-15 (Materials & Content)...
```

After completing all checks, display a quick summary before the detailed report:
```
═══ Audit Complete ═══
Design Standards: 18 Met, 5 Partial, 2 Not Met
QA Categories: 14 Pass, 3 Warn, 2 Fail
Detailed findings below...
```

### Scan Procedure

**CRITICAL: Use the deterministic evaluator for all B-criteria. Do NOT evaluate B-criteria yourself.**

1. **Run the deterministic evaluator** — this is the FIRST step, before any AI evaluation:
   ```bash
   python3 scripts/criterion_evaluator.py --json
   ```
   This script:
   - Fetches all course data from Canvas API
   - Evaluates all 124 B-criteria deterministically (HTML parsing, API checks)
   - Flags 49 C-criteria as `needs_ai_review`
   - Returns JSON with GUARANTEED field names: `criterion_id`, `criterion_text`, `status`, `evidence`
   - **Same course = same output, every time. No LLM variability.**

2. **Read the evaluator output.** Parse the JSON. All B-criteria are already evaluated with specific evidence. Do NOT override or re-evaluate B-criteria — the Python engine is authoritative for these.

3. **Evaluate C-criteria** (the ones marked `needs_ai_review: true`). For each:
   - Load the enrichment card from `config/standards_enrichment.yaml`
   - Read the relevant course pages to make a quality judgment
   - Set `status` to Met/Partially Met/Not Met with specific evidence
   - Keep the SAME field names: `criterion_id`, `criterion_text`, `status`, `evidence`

4. **Merge results** — combine B-criteria (from evaluator) + C-criteria (from your evaluation) into one `criteria_results` array per standard.

5. **Derive standard-level status** from criteria (lowest wins: any Not Met → standard is Partially Met at best)

6. **Build the audit JSON** — pass to `audit_report.py` for HTML report + Supabase push.

### Why the evaluator exists

The evaluator guarantees that 5 different people auditing the same course for Col B get **identical results**. Col B checks are deterministic — "Does a syllabus exist?" has one answer. The Python engine reads the course data and answers factually. Claude should NEVER evaluate B-criteria itself because LLM outputs vary between sessions.

### C-Criteria Evaluation (AI judgment)

For C-criteria (`C-XX.Y`, `reviewer_tier: id`), Claude provides the quality judgment. These are inherently subjective — "Are objectives appropriate for the course level?" requires instructional design expertise. Use enrichment cards from `standards_enrichment.yaml` for context.

### Evidence Requirements (CRITICAL)

Every criterion MUST capture specific, actionable evidence — not just "yes it exists" or "no it doesn't." The evidence must be detailed enough for someone to locate and fix the issue without re-auditing.

**For Met criteria:**
- State WHAT was found and WHERE: "Syllabus page contains 14,813 chars of content including grading policy, late work policy, and AI statement"
- Reference specific pages/elements when relevant: "Instructor introduction found at pages/meet-your-instructor"

**For Not Met criteria:**
- List EVERY specific instance of the failure:
  - Images: list each page slug + img src or description. e.g., "m3-lesson-introduction: anatomy-diagram.png (no alt), m5-resources: chart-data.png (alt='')"
  - Headings: list each page + the skip. e.g., "m12-dot-1-required-reading-2: h2→h4 ('CASE')"
  - Missing content: state exactly what's missing and where it should be
- This data goes into `content_excerpt` and is used by remediation skills to locate and fix issues

**For Partially Met criteria:**
- State what passes AND what fails with specific instances

**Example — BAD evidence (unusable):**
```
"evidence": "Some images missing alt text"
```

**Example — GOOD evidence (actionable):**
```
"evidence": "96 of 100 images missing alt text",
"content_excerpt": "m1-overview: banner.jpg (no alt), m1-lesson: fig1-torts.png (alt=''), m2-overview: header.jpg (no alt), m2-lesson: diagram-negligence.png (alt=''), m3-overview: banner.jpg (no alt) ... [showing 5 of 96, full list in audit data]"
```

**Per-criterion result model with evidence:**

**Output per standard item must include `criteria_results`:**
```json
{
  "id": "04",
  "name": "Consistent Layout",
  "status": "Partially Met",
  "evidence": "43 of 47 criteria met. Getting Started module exists, syllabus published. Course tour page missing, assignment groups not configured.",
  "recommendation": "Add a course tour page and configure assignment groups.",
  "confidence": "High",
  "reviewer_tier": "id_assistant",
  "criteria_results": [
    {"criterion_id": "B-04.1", "status": "Met", "evidence": "Welcome and Start Here module found", "check_type": "deterministic", "reviewer_tier": "id_assistant"},
    {"criterion_id": "B-04.2", "status": "Met", "evidence": "Syllabus page has content (14,813 chars)", "check_type": "deterministic", "reviewer_tier": "id_assistant"},
    {"criterion_id": "B-04.15", "status": "Not Met", "evidence": "No course tour page found", "check_type": "deterministic", "reviewer_tier": "id_assistant"},
    {"criterion_id": "C-04.1", "status": "Met", "evidence": "Recurring elements follow consistent formatting", "check_type": "ai", "reviewer_tier": "id"}
  ]
}
```

**Standard-level status** = derived from criteria (lowest criterion wins):
- ALL criteria Met → Standard "Met"
- Any Not Met but most Met → Standard "Partially Met"
- Most Not Met → Standard "Not Met"
- Cannot evaluate (missing data) → Standard "Not Auditable"

**Standard-level evidence** = summary sentence aggregating criteria results (e.g., "43 of 47 criteria met. Missing: course tour, assignment groups.")

### Two-Pass Evaluation (Graph + AI)

For every standard, follow this evaluation protocol:

**Pass 1 — Deterministic checks (graph-powered, high confidence):**
Run structural/data checks that produce provable results. These checks use the alignment graph, page HTML parsing, and Canvas API data — no AI judgment needed.

**Pass 2 — AI quality judgment (medium confidence):**
After deterministic checks, evaluate subjective quality criteria using the full enrichment card (measurable_criteria + expectations + considerations + examples) from `standards_enrichment.yaml`. Inject the enrichment card into your evaluation context for each standard.

**Scoring rules:**
- If all deterministic checks pass AND AI judgment is positive → **Met** (High confidence)
- If deterministic checks pass but AI finds quality concerns → **Partially Met** (Medium confidence)
- If any deterministic check fails but some evidence exists → **Partially Met** (Medium confidence)
- If deterministic checks fail and no evidence → **Not Met** (High confidence)
- If prerequisite data is missing (e.g., no CLOs found for Standard 01) → **Not Auditable** (excluded from score denominator)

### Alignment Graph Integration — Standards 01, 02, 03, 08, 12

These five standards depend on structural alignment relationships. When the alignment graph is available, use these deterministic checks FIRST:

#### Standard 01: Course-Level Alignment

**Deterministic (from graph):**
- [ ] All CLO verbs are measurable — check `graph.clos[].is_measurable`. Fail if ANY CLO uses an unmeasurable verb (understand, learn, know, be aware, realize, appreciate).
- [ ] CLO count is reasonable — 3-credit course typically has 4-8 CLOs. Flag if <3 or >10.
- [ ] Every CLO maps to ≥1 MLO — check `graph.clos[].mlo_ids` is non-empty. Report count of unmapped CLOs from `graph.gaps.unmapped_clos`.

**AI judgment (using enrichment card 01):**
- Are verbs appropriate for course level (introductory vs. advanced)?
- Do CLOs collectively address professional, academic, and personal growth?
- Are CLOs aligned with program/industry standards?

#### Standard 02: Module-Level Alignment

**Deterministic (from graph):**
- [ ] All MLO verbs are measurable — check `graph.mlos[].is_measurable`.
- [ ] Every MLO maps to ≥1 CLO — check `graph.mlos[].clo_ids` is non-empty. Report unmapped MLOs from `graph.gaps.unmapped_mlos`.
- [ ] Bloom's progression — check `graph.coverage.blooms_progression`. If false, report which modules break the progression from `graph.coverage.blooms_by_module`.

**AI judgment (using enrichment card 02):**
- Is each MLO-to-CLO mapping semantically valid? (Does the MLO genuinely support the CLO it claims?)
- Do MLOs show logical progression within each module?

#### Standard 03: Alignment Made Clear

**Deterministic (from graph):**
- [ ] CLO→MLO→Assessment chain complete — for every CLO, trace: CLO → at least one MLO → at least one assessment. Report broken chains from `graph.gaps.clos_without_summative`.
- [ ] Module overview pages contain objectives text — check each module's first page for objective-like content (regex for "objectives", "by the end", "able to").
- [ ] Alignment documentation visible — search all page HTML for alignment tables, objective references, CLO/MLO labels on assessments.

**AI judgment (using enrichment card 03):**
- Is the alignment documentation clear and helpful to students?
- Would a student reading the course understand how each activity connects to outcomes?

#### Standard 08: Assessments Align with Objectives

**Deterministic (from graph):**
- [ ] Every assessment maps to ≥1 MLO — check `graph.assessments[].mlo_ids`. Report orphan assessments from `graph.gaps.orphan_assessments`.
- [ ] Every MLO has ≥1 assessment (formative or summative) — cross-reference MLO IDs against all assessment `mlo_ids`.
- [ ] Assessment Bloom's level ≥ MLO Bloom's level — for each assessment, the assessment's complexity should match or exceed its mapped MLOs.
- [ ] Graded assignments/discussions have rubrics — check `graph.assessments[].has_rubric` for summative items.

**AI judgment (using enrichment card 08):**
- Do assessment instructions explicitly state which objectives are being evaluated?
- Does the assessment actually measure what the MLO claims? (Semantic analysis)
- Do rubric criteria reinforce the stated objectives?

#### Standard 12: Materials Align with Objectives

**Deterministic (from graph):**
- [ ] Every material maps to ≥1 MLO — check `graph.materials[].mlo_ids`. Report orphan materials from `graph.gaps.orphan_materials`.
- [ ] Every MLO has ≥1 material — cross-reference MLO IDs against all material `mlo_ids`.
- [ ] Material types are varied per module (UDL) — group materials by module, count distinct `canvas_type` values. Flag modules where all materials are the same type.

**AI judgment (using enrichment card 12):**
- Does the material content actually support the mapped MLO?
- Are materials from credible, current sources?
- Do materials provide multiple means of engagement per UDL?

### Standards 04–07, 09–11, 13–25 (Non-Alignment)

These standards do NOT use the alignment graph. Evaluate them using the standard approach:
1. Read the enrichment card from `standards_enrichment.yaml`
2. Fetch relevant course content (pages, assignments, quizzes, etc.)
3. Run any applicable structural checks (heading hierarchy, link text, rubric presence)
4. Apply AI judgment using the full enrichment criteria
5. Score with evidence and recommendation

### Evidence Verification (QAI Port)

After scoring each standard, verify evidence integrity:

1. **Quote verification**: If your evidence includes a direct quote from course content, verify the quote actually exists using `alignment_graph.verify_evidence(quote, page_text)`. If the quote is NOT found in the actual content, downgrade status from "Met" to "Not Met" and add note: "Evidence quote not found in course content — manual review required."

2. **Coverage-aware status**: For module-scoped criteria, evidence must appear in ≥60% of modules to be "Met". Use `alignment_graph.coverage_status(found_modules, total_modules, "module")`. Evidence in <60% but >0 modules = "Partially Met".

3. **Confidence degradation**: Start at "High" confidence. Degrade one level for each trigger:
   - Evidence verification fails → degrade
   - Coverage below 60% threshold → degrade
   - Graph edges are `source="inferred"` (not declared/extracted) → degrade
   - Standard depends on CLOs but no CLOs found in course → degrade + mark "Not Auditable"

### "Not Auditable" Status

When prerequisite data is missing, mark the standard as **"Not Auditable"** instead of "Not Met":
- Standards 01, 02: No CLOs found in syllabus or course-config → Not Auditable
- Standard 03: No alignment graph AND no visible alignment documentation → Not Auditable
- Standards 08, 12: No MLOs AND no CLOs found → Not Auditable

"Not Auditable" standards are **excluded from the score denominator**. Report them separately with the recommendation to provide the missing prerequisite data.

### Enrichment Cards (for Col C / AI criteria)

When evaluating `C-XX.Y` criteria (check_type: "ai"), load the corresponding enrichment card from `config/standards_enrichment.yaml`. The enrichment card provides:
- `measurable_criteria` — specific things to look for
- `expectations` — what "Met" looks like
- `considerations` — edge cases and nuances
- `examples` — concrete examples of good vs. poor
- `research` — citations backing the standard

Inject the full enrichment card into your evaluation context for each C-criterion. This provides the evidence depth needed for qualitative judgments. Do NOT evaluate C-criteria without the enrichment card — the criteria text alone is too vague for reliable judgment.

### Enrichment-Injected Prompts

When evaluating each standard, construct your evaluation context with the FULL enrichment card:

```
STANDARD [ID]: [Name]
Category: [category]
Essential: [yes/no]

DESCRIPTION: [description from standards.yaml]

MEASURABLE CRITERIA:
[bulleted list from standards_enrichment.yaml]

EXPECTATIONS:
[bulleted list from standards_enrichment.yaml]

CONSIDERATIONS:
[bulleted list from standards_enrichment.yaml]

EXAMPLES:
[bulleted list from standards_enrichment.yaml]

RESEARCH:
[bulleted list from standards_enrichment.yaml]

ALIGNMENT GRAPH DATA (if applicable):
[relevant graph data for this standard]

EVIDENCE FROM COURSE:
[actual course content relevant to this standard]

EVALUATE: Score this standard as Met/Partially Met/Not Met/Not Auditable.
Provide: status, evidence, recommendation, confidence, coverage.
```

### 19 QA Categories

1. Module structure consistency
2. Page title formatting
3. Learning objectives presence
4. Assessment-objective alignment
5. Quiz configuration (attempts, time, shuffle)
6. Heading hierarchy (H2→H3→H4)
7. Image alt text presence
8. Link accessibility (target, noopener, sr-text)
9. Video captions/transcripts
10. File accessibility
11. Color contrast
12. Table structure (headers, scope)
13. Font consistency
14. Navigation consistency
15. Module completeness (7-page structure)
16. Grading transparency
17. External link validation
18. Content freshness (dates, references)
19. Mobile-friendly layout

### Output Format

```
=== ASU Course Design Standards Audit ===
Course: [Name] (ID: [id])
Date: [timestamp]

DESIGN STANDARDS (25):
  Met:           18
  Partially Met:  5
  Not Met:        2

[Detailed findings per standard with evidence and citations]

QA CATEGORIES (19):
  Pass:  14
  Warn:   3
  Fail:   2

[Detailed findings per category]

CLO ALIGNMENT MATRIX:
[Table mapping CLOs to assessments]
```

---

## Accessibility Checks (absorbed into all modes)

WCAG accessibility checks are now part of the unified check registry under Standards 22 and 23 (deterministic checks in `audit_pages.py`). They run automatically in all modes as part of Pass 1.

Optional deep analysis is still available:
- **Vision-based analysis** (`--deep`): Extract images via `scripts/vision_audit.py`, compare alt text vs actual content
- **Semantic alt text validation** (`--semantic`): Download images, rate alt text as good/partial/mismatch/decorative

These are add-on passes, not separate modes. Run them with: "also check image alt text accuracy" or "run deep accessibility scan".

---

## CRC Items (absorbed into all modes)

The 18 Course Readiness Check items that don't map to the 25 design standards are now in `standards.yaml` under `id: "crc"`. They run automatically in all modes as deterministic checks (Pass 1). Use `--scope crc` to see only these items.

### Scan Procedure

1. Fetch course data (modules, items, pages, assignments, quizzes, tabs, late policy)
2. Run each category's checks programmatically
3. Score: Pass / Fail per item within each category

### Output Format

```
=== Course Readiness Check ===
Course: [Name]
Status: [READY / NOT READY]

[Category] .......................... [PASS/FAIL]
  ✓ Syllabus is published
  ✓ Course description set
  ✗ No instructor contact info on home page
  ...
```

---

## HTML Report Output

Generate a polished, shareable HTML audit report for leadership and team review.

**Always generate after every audit — no exception.** At the end of every Quick Check, Deep Audit, and Guided Review, automatically run the report generator. Do not wait for the user to ask.

**Generate:**

```bash
python scripts/audit_report.py --input audit_results.json --open   # From saved results
python scripts/audit_report.py --demo --open                        # Demo with sample data
```

**Saved to:** `reports/{COURSE-CODE_TERM}/{COURSE-CODE_YYYY-MM-DD_HH-MM_AI-Audit}.html`

Audit reports are standalone deliverables — NOT staging files. They save directly to `reports/` with the course code and timestamp. The `--open` flag opens the report in the default browser. Reports are never overwritten — each audit creates a new timestamped file.

**Features:**
- Overall score ring (weighted: 40% standards, 30% QA, 15% accessibility, 15% readiness)
- Summary cards for all 4 audit sections with color-coded counts
- Collapsible sections: Design Standards (25), QA Categories (19), Accessibility (WCAG), Readiness (9)
- Filter buttons to show only Met/Partially Met/Not Met findings
- Recommendations highlighted with gold callout boxes
- **Remediation Roadmap** — auto-generated section ranking all Not Met / Fail / Warn / Partial findings by priority and score impact, with current → projected progress bars and quick-wins callout
- CLO Alignment Matrix
- Print-friendly for PDF export
- Self-contained HTML — share as a single file, no server needed

**Required JSON schema** — `audit_results.json` must follow this structure exactly or all counts will render as 0:

```json
{
  "course": {"name": "...", "id": "...", "domain": "canvas.asu.edu"},
  "audit_date": "2026-03-25T09:41:00",
  "auditor": "ID Workbench v1.5.0",
  "audit_mode": "quick_scan|full_audit|guided_review",
  "audit_scope": "all|essential|crc|essential,crc",
  "sections": {
    "design_standards": {
      "summary": {"Met": 9, "Partially Met": 14, "Not Met": 1, "Not Auditable": 1},
      "items": [
        {
          "id": "01",
          "name": "Course-Level Alignment",
          "status": "Met|Partially Met|Not Met|Not Auditable",
          "evidence": "Description of what was found",
          "recommendation": "What to fix (null if Met)",
          "confidence": "High|Medium|Low",
          "coverage": "13/13 modules",
          "reviewer_tier": "id_assistant|id",
          "content_excerpt": "The actual text/HTML that triggered this finding",
          "canvas_link": "https://canvas.asu.edu/courses/223406/pages/syllabus",
          "category": "design_standard|crc",
          "essential": true,
          "criterion_id": "01.1",
          "criteria_results": [
            {"criterion_id": "01.1", "status": "Met", "evidence": "...", "reviewer_tier": "id_assistant"}
          ]
        }
      ]
    },
    "qa_categories": {
      "summary": {"Pass": 9, "Warn": 7, "Fail": 2},
      "items": [{"id":"Q01","name":"...","status":"Pass|Warn|Fail","detail":"..."}]
    },
    "accessibility": {
      "summary": {"Critical": 1, "Warning": 3, "Info": 2},
      "items": [{"severity":"Critical|Warning|Info","page":"...","issue":"...","element":"...","fix":"..."}]
    },
    "readiness": {
      "overall": "READY|NOT READY",
      "categories": [{"name":"...","status":"Pass|Warn|Fail","checks":[{"item":"...","status":"Pass|Fail|Warn","note":"..."}]}]
    }
  },
  "clo_alignment": {"clos": [{"id":"CLO-1","text":"...","modules":[1,2],"assessments":4}]},
  "external_links": [{"page":"...","text":"...","url":"...","domain":"...","status":"Not Reviewed|Reviewed|Broken","notes":"..."}]
}
```

**New required fields per finding** (added for pilot):
- `reviewer_tier` — from `standards.yaml`. Determines who can verdict this finding in the Vercel review app.
- `content_excerpt` — the specific text/HTML that triggered the finding. Shown inline to reviewers.
- `canvas_link` — direct URL to the Canvas page/item. Reviewers click to verify.
- `category` — `"design_standard"` or `"crc"`. Used for scope filtering.
- `essential` — whether the parent standard is essential. Used for essential scope filter.
- `criterion_id` — the specific criterion from `standards.yaml` (e.g., "01.1", "crc.04").

⚠️ **Common failure**: putting `design_standards`, `qa_categories` etc. at the top level instead of inside `"sections"` — and using lowercase keys (`met`, `pass`) instead of title-case (`"Met"`, `"Pass"`) inside `"summary"`. Both cause all counts to silently render as 0. The normalization layer in `audit_report.py` will attempt to fix these, but always use the correct format.

**Workflow integration:**
1. Run `/audit` → results display in conversation + saved as `audit_results.json`
2. **Automatically run** `python scripts/audit_report.py --input audit_results.json --open` → shareable HTML report (always — do not skip)
3. Report local path and Supabase URL to the user
4. **Provide the Vercel review app URL** so the ID can review findings and submit verdicts:
   > Your findings are live at: `https://idw-review-app.vercel.app/sessions/<SESSION_ID>`
   > Reviewers can approve, reject, or flag each finding there.
5. **If `audit_purpose` is `self_audit`**, offer to submit for QA review:
   > "Would you like to submit this audit for QA review? This notifies your QA lead that it's ready for their review."
   > If yes: update `audit_sessions.session_status` from `in_progress` → `pending_qa_review` via Supabase.
   ```bash
   python3 -c "
   import requests, os
   from dotenv import load_dotenv
   load_dotenv('.env.local')
   url = os.getenv('SUPABASE_URL')
   key = os.getenv('SUPABASE_SERVICE_KEY')
   session_id = '<SESSION_ID>'
   resp = requests.patch(
       f'{url}/rest/v1/audit_sessions?id=eq.{session_id}',
       headers={'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json', 'Prefer': 'return=representation'},
       json={'session_status': 'pending_qa_review'},
       timeout=15
   )
   print(resp.status_code)
   "
   ```
6. Fix issues via `/bulk-edit` → staged → reviewed in unified preview → pushed

## Faculty Feedback Summary

After an audit completes, offer:

> "Would you like me to generate a faculty summary you can share with the SME? It translates findings into non-technical language with clear action items."

If the user says yes, generate using `audit_report.generate_faculty_summary(data)`:
- Plain text output (email-ready, not HTML)
- No jargon: avoids CLO, MLO, WCAG, Bloom's unless explained
- Grouped by priority: High (required standards Not Met), Medium (Partially Met or essential), Low (nice-to-have)
- Shows what's working well first
- Saved to `reports/{course}/faculty-summary_{date}.txt`

The ID reviews the summary before sending to faculty. AI never contacts faculty directly.

## XLSX Report Output (QA Initiate Format)

Generate a standards-aligned XLSX audit report using the QA Initiate template for formal deliverables.

**When to use:** "Generate an Excel audit report", "I need a QA form", "audit for my lead in Excel"

**Generate:**

```bash
python scripts/audit_report.py --input audit_results.json --xlsx              # XLSX only
python scripts/audit_report.py --input audit_results.json --xlsx --open       # Generate and open
python scripts/audit_report.py --demo --xlsx                                   # Demo with sample data
python scripts/audit_report.py --demo --xlsx --xlsx-output my_report.xlsx     # Custom output path
```

**Output file:** Auto-archived at `reports/{COURSE-CODE_TERM}/{COURSE-CODE_TERM_YYYY-MM-DD_HH-MM_AI-Audit}.xlsx`

**Sheets:**
1. **QA Initiate** — 25 standards with 3-state status, evidence, confidence, coverage, Canvas links
2. **Dashboard** — Summary charts, overall score, confidence distribution, top action items
3. **External Links** — Inventory of all external links with review status

**Columns (QA Initiate sheet):**

| Column | Content |
|---|---|
| A | Standard status formula (Meets / Partially Meets / Does Not Meet) |
| B | Status: Met / Partially Met / Not Met (dropdown) |
| C | Measurable criteria and expectations |
| D | Reviewer notes / evidence |
| E | Recommendations |
| F | Confidence (High / Medium / Low) |
| G | Coverage (e.g., "8/12 modules") |
| H | Scope (Course-wide / Module-level / Assessment-level) |
| I | Evidence source (Canvas / External / Mixed) |
| J | Canvas deep link |

**Confidence tiers:**
- **High** — Deterministic check passed or explicit evidence found and verified
- **Medium** — Evidence found but ambiguous or incomplete
- **Low** — Insufficient evidence; manual review recommended

**Audit scope policy:**
> This audit evaluates content within Canvas. External links are listed but not reviewed unless external scanning is enabled. "Met" requires evidence across all relevant modules. "Partially Met" indicates evidence in some modules.

**Dashboard features:**
- Overall score (weighted: 40% standards, 30% QA, 15% accessibility, 15% readiness)
- Bar charts for Design Standards and QA Categories
- Pie chart for Confidence Distribution
- Course Readiness status with category checkmarks
- Top Action Items table (Not Met + Low Confidence + QA Fail items)

## Read-Only Mode

All audit modes are **read-only by default**. No content is modified. If findings suggest fixes, recommend `/bulk-edit` to apply them.

## Error Handling

| Error | Resolution |
|---|---|
| Course data fetch fails | Check credentials and course ID |
| Vision analysis timeout | Fall back to text-only analysis |
| Syllabus is PDF-only | Flag as warning, note inline content unavailable |
| Page body empty | Flag as warning in content availability check |

---

## Guided Review (Mode 3) — Interactive Audit Walkthrough

An alternative to batch auditing — walk through standards conversationally with the ID so they can review, fix, and approve findings in real time.

### When to Use

- "Walk me through the audit"
- "Audit with me"
- "Let's review each standard together"
- "Interactive audit"
- User explicitly wants to fix issues as they're found rather than reviewing a report afterward

### How It Works

1. **Fetch course data** the same way as Mode 1 (modules, pages, quizzes, assignments, discussions, tabs, alignment graph)
2. **Walk through standards one at a time** (or in small groups of 2-3 related standards), presenting findings conversationally:

```
Standard 1: Course-Level Alignment
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
I found 6 CLOs. Let me check each one...

✅ CLO-1: "Explain and apply foundational human factors principles" — "explain" is measurable ✓
✅ CLO-2: "Analyze how cognitive factors influence decision-making" — "analyze" is measurable ✓
⚠️ CLO-3: "Understand the role of stress in forensic work" — "understand" is not measurable
   Suggestion: Replace with "Describe" or "Evaluate"

→ Want to update CLO-3 now, or note it and continue?
```

3. **After each standard or group**, pause with an `AskUserQuestion`:

| Label | Description |
|---|---|
| **Fix now** | Let me address the issues before moving on |
| **Note and continue** | I'll come back to these later — keep going |
| **Looks good, skip** | I've reviewed this and accept it as-is |

4. **Track the review state** for each standard:
   - `reviewed_live` — ID saw it and responded (fix, note, or accept)
   - `auto_evaluated` — Standard was batch-evaluated (for standards the ID skips)

5. **Standard grouping** for conversational flow:

| Group | Standards | Theme |
|---|---|---|
| 1 | 01, 02, 03 | Alignment (CLOs, MLOs, connections) |
| 2 | 04, 05 | Course structure & introductions |
| 3 | 06, 07 | Workload & instructor guide |
| 4 | 08, 09, 10 | Assessment quality |
| 5 | 11, 12, 13 | Cognitive skills & materials |
| 6 | 14, 15, 16 | Relevance, UDL, media |
| 7 | 17, 18, 19 | Community, instructor media, active learning |
| 8 | 20, 21 | Tools & support |
| 9 | 22, 23, 24, 25, CRC | Accessibility, cost & operational readiness |

6. **Fixing on the spot**: When the ID says "fix now," handle fixes directly:
   - **Measurability**: Suggest replacement verbs and update `course-config.json`
   - **Missing rubric**: Route to `/rubric-creator` inline
   - **Heading hierarchy**: Fix via API or stage the corrected page
   - **Missing alt text**: Show the image and ask the ID to describe it
   - **Missing overview page**: Generate one from `course-config.json` objectives
   - **Due date missing**: Prompt for date and update via API
   After each fix, re-check that specific criterion and show the updated status.

7. **At the end**, produce the same HTML/XLSX report as Mode 1, but with annotations:
   - Items reviewed live show a "Reviewed with ID ✓" badge
   - Items the ID accepted as-is show "Accepted" status
   - Items fixed during walkthrough show "Fixed during review" with before/after
   - Items auto-evaluated (batch) show standard confidence indicators

### Presentation Rules

- **Plain language** — no standard numbers in conversation (say "Course-Level Alignment" not "Standard 01")
- **One group at a time** — never dump all 25 standards at once
- **Show evidence** — for every finding, quote the specific content that was checked
- **Celebrate wins** — when a group is all Met, say so: "Standards 4 and 5 are solid — your course structure and introductions look great."
- **Prioritize errors** — within each group, show Not Met items first, then Partially Met, then Met
- **Estimate remaining time** — "6 of 9 groups reviewed. About 10 minutes left."

### Exit Early

If the ID says "that's enough for now" or "I'll review the rest later":
- Generate a partial report with reviewed items annotated
- List unreviewed standards as "Not yet reviewed"
- Save state so a future session can resume

---

### Google Drive Integration

Use the Google Drive MCP connector to find source documents for cross-referencing against published Canvas content.

**MCP Tools**:
- `google_drive_search` — Search for original SME documents, approved syllabi, or master content files to compare against what's published in Canvas
- `google_drive_fetch` — Fetch source documents to compare content accuracy, check for missing sections, or verify assessment alignment

**Where It Fits**:
- **Standards Audit**: Cross-reference published Canvas content against original source documents on Drive to detect content drift or missing material
- **Accessibility Audit**: Find original image files on Drive to check if alt text matches the original intent/description
- **Readiness Audit**: Locate the approved syllabus on Drive and verify the Canvas course matches it

---

### Browser Automation (Claude in Chrome)

Use Claude in Chrome for visual verification of published Canvas pages.

**MCP Tools**: `navigate`, `computer`, `read_page`, `get_page_text`, `javascript_tool`, `tabs_context_mcp`

**Where It Fits**:
- **Visual QA**: Navigate to published Canvas pages and take screenshots to verify layout, styling, and visual consistency match design standards
- **External link validation**: Click through external links on Canvas pages to verify they load correctly and aren't broken
- **Embedded media checks**: Verify that embedded videos, iframes, and interactive content render correctly in the browser
- **Student view verification**: Navigate Canvas in student view mode to confirm the student-facing experience matches design intent
