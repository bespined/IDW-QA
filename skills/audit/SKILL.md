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

Unified audit skill with 3 modes: Quick Check (deterministic only), Deep Audit (deterministic + AI), and Guided Review (interactive with live fixes). All modes use a single check registry with scope filters.

## Role Gate

**ID Assistants (`id_assistant` role) do NOT use this skill.** If an `id_assistant` invokes `/audit`, stop immediately and respond:

> "ID Assistants review audit findings in the Vercel review app at https://idw-review-app.vercel.app — not in Claude Code. Contact your QA admin if you need access."

Do not proceed with any audit workflow for `id_assistant` users.

## When to Use

- "Audit my course" / "Check my course" / "Quick scan" → **Ask which mode** (see Entry Point below)
- "Quick scan" / "Fast audit" / "Deterministic check" → **Quick Check** (skip prompt)
- "Full audit" / "Complete audit" / "Comprehensive audit" → **Deep Audit** (skip prompt)
- "Walk me through it" / "Audit with me" / "Interactive audit" / "Guided review" → **Guided Review** (skip prompt)
- "Just check essential standards" / "Quick readiness check" → **Quick Check** (skip prompt)

## Session Creation Timing

**Do NOT create a Supabase session at the start of the audit.** Sessions are created only when the user explicitly chooses "Generate report + submit for review" at the end. The `audit_report.py` script handles session creation internally via `push_to_rlhf()` — no separate `audit_session_manager.py --create` call is needed.

**Why:** IDs run many iterative audits while building a course. Creating a session for every run floods the review app with intermediate findings that no one should review. Only the final submission should enter the pipeline.

The `audit_session_manager.py` script is still available for:
- `--submit` — transition a session from `in_progress` to `pending_qa_review`
- `--status` — check session status and finding counts
- `--create --dry-run` — preview what purpose/round would be inferred (useful for debugging)

---

## Entry Point — Course Selection

Before asking about audit mode, determine which course(s) to audit. Use `AskUserQuestion`:

| Option | Label | Description |
|---|---|---|
| 1 | **Current course** | Audit the course in `.env` (show course name for confirmation) |
| 2 | **Batch audit** | Audit multiple courses sequentially — I'll pick which ones |
| 3 | **Different course** | Let me provide a course URL or ID |

**Skip this prompt** if the user already specified a course (e.g., "audit BIO 101" or "audit course 223406").

**For Batch Audit:**
1. Let the user paste a list of course IDs or URLs
2. Confirm the list: "I'll audit these N courses sequentially: [list]. Each takes ~10 minutes for Deep Audit. Continue?"
3. Run the audit on each course in sequence, generating separate reports and sessions for each
4. At the end, show a summary table: Course | Score | Standards Met | Critical Issues
5. Each course gets its own Supabase session and HTML report

## Audit Mode Selection

When the user asks for a general audit without specifying a mode, **always present the choice first** before fetching any data. Use `AskUserQuestion` with these options:

| Option | Label | Description |
|---|---|---|
| 1 | **Quick Check** | Structural readiness scan — checks whether required elements exist and are set up correctly (e.g., CLOs present, rubrics attached, navigation links working, syllabus populated, due dates set). Col B criteria only. Takes 1-2 minutes. |
| 2 | **Deep Audit** | Full quality review of all standards — everything in Quick Check plus instructional design quality, alignment depth, assessment design, content effectiveness, and accessibility. Col B + Col C criteria. Takes 10-15 minutes. |
| 3 | **Guided Review** | Same depth as Deep Audit but walks through the course with you section by section, pausing after each to review findings and stage fixes for your approval before pushing. Best when you're actively building the course. |

Only skip this prompt when the user's message clearly specifies a mode.

**If the user picks Quick Check**, proceed directly — no scope question. Quick Check always evaluates all 124 Col B criteria across all 25 standards + CRC readiness items. The evaluator runs in ~30 seconds regardless.

**If the user picks Deep Audit or Guided Review**, also run all standards — Deep Audit adds Col C (design quality) evaluation on top of the same Col B checks.

### Staging Requirement

**All page content changes MUST go through staging.** If the audit finds issues and the user asks to fix them, stage the fix first — never push HTML directly to Canvas. The flow is always: stage → preview → user approves → push. This applies to Quick Check, Deep Audit, and Guided Review equally. See CLAUDE.md for the full staging workflow.

---

## Two-Pass Architecture (used by all modes)

All modes use the same check registry from `config/standards.yaml`. Quick Check runs Pass 1 only. Deep Audit and Guided Review run both passes.

### Reviewer Tier Tagging

Every finding MUST be tagged with `reviewer_tier` from `standards.yaml`:
- `reviewer_tier: "id_assistant"` — Col B checks (deterministic/existence). IDAs can verdict these.
- `reviewer_tier: "id"` — Col C checks (qualitative/judgment). Only QA team IDs verdict these.

### Quick Check (Mode 1)

Runs **Pass 1 (deterministic) + light AI verification**. Two steps:
1. All deterministic checks run via `criterion_evaluator.py --quick-check` (supersedes legacy `deterministic_checks.py`)
2. One AI verification call: Claude receives a summary of all deterministic results + raw content from flagged pages (syllabus body, module overviews, CLO text). The AI checks for obvious false positives and false negatives — pages that exist but are empty, CLOs that technically use measurable verbs but are meaningless, template placeholders that weren't caught by regex. The AI does NOT evaluate instructional quality — that's what Deep Audit does.

All findings tagged `reviewer_tier: "id_assistant"` (Col B). These are validated by ID Assistants in the Vercel review app after submission.

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

**CRITICAL: The Python evaluator produces the audit JSON. Claude does NOT build JSON from scratch.**

#### Quick Check (Col B only — no AI evaluation)

Step 1: Run the evaluator:
```bash
python3 scripts/criterion_evaluator.py --quick-check > audit_results.json
```

Step 2: Show the summary (Met/Partial/Not Met counts + overall score) in conversation.

Step 3: **STOP and ASK before generating any report.** Use `AskUserQuestion` with these options:

| Option | Label | Description |
|---|---|---|
| 1 | **Just show results** | No report, no Supabase push. Fastest — for iterative checks during course building. |
| 2 | **Generate report (local only)** | Creates HTML report saved locally. Does NOT push to Supabase or create a review session. |
| 3 | **Generate report + submit for review** | Creates HTML report AND pushes to Supabase. Creates a session in the review app for ID Assistant validation. |

**Do NOT skip this prompt. Do NOT auto-generate reports. Do NOT push to Supabase without the user explicitly choosing option 3.**

If option 1 — Just show results:
Display the summary in conversation. Done. No commands to run.

If option 2 — Local only:
```bash
python3 scripts/audit_report.py --input audit_results.json --local-only --open
```
Show the local file path. No Supabase session created.

If option 3 — Submit for review:
```bash
python3 scripts/audit_report.py --input audit_results.json --open
```
Show the HTML report link and Supabase session ID.

#### Deep Audit (Col B deterministic + Col C AI evaluation)

```bash
python3 scripts/criterion_evaluator.py --full-audit > audit_results.json
```

This produces the complete JSON with B-criteria evaluated and C-criteria marked `needs_ai_review`. Then:

1. **Read `audit_results.json`** — all B-criteria are done. Do NOT re-evaluate them.
2. **For each C-criterion with `"needs_ai_review": true`:**
   - Load the enrichment card from `config/standards_enrichment.yaml` for that standard
   - Read the relevant course pages (the evaluator already fetched them — page slugs are in the B-criteria evidence)
   - Evaluate: Met / Partially Met / Not Met with specific evidence
   - Update the criterion's `status` and `evidence` fields in the JSON
   - Set `needs_ai_review` to `false`
3. **Save the updated JSON** to `audit_results.json`
4. **Show the summary** (Met/Partial/Not Met counts + overall score) in conversation.
5. **STOP and ASK using `AskUserQuestion`** — same 3 options as Quick Check:
   - **Just show results** — no report, no push
   - **Generate report (local only)** — HTML saved locally, no Supabase
   - **Generate report + submit for review** — HTML + Supabase push

   **Do NOT skip this prompt. Do NOT auto-generate reports.**

   If local only: `python3 scripts/audit_report.py --input audit_results.json --local-only --open`
   If submit: `python3 scripts/audit_report.py --input audit_results.json --open`

**IMPORTANT: Do NOT rebuild the JSON from scratch. Read the evaluator's output, update only the C-criteria, and pass through.** The B-criteria results, QA categories, accessibility findings, and readiness checks are all produced by the Python engine with guaranteed field names.

#### Guided Review (same as Deep Audit, but interactive)

Same as Deep Audit but pause after each standard group to show findings and offer fixes.

### Why the evaluator exists

The evaluator guarantees that 5 different people auditing the same course for Col B get **identical results**. Col B checks are deterministic — "Does a syllabus exist?" has one answer. The Python engine reads the course data and answers factually. Claude NEVER evaluates B-criteria itself because LLM outputs vary between sessions.

### C-Criteria Evaluation (AI judgment — Deep Audit only)

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

The 18 Course Readiness Check items that don't map to the 25 design standards are now in `standards.yaml` under `id: "crc"`. They run automatically in all modes as deterministic checks (Pass 1) alongside the 25 design standards.

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

**Do NOT auto-generate reports.** The report prompt is handled in the Quick Check and Deep Audit sections above (Step 3 / Step 5). This section documents the report commands AFTER the user has chosen.

**Never push to Supabase without the user explicitly choosing "Generate report + submit for review."** The local-only report is useful for talking points, planning remediation, or sharing with the SME. Supabase submission is a separate, deliberate action.

```bash
# Local only (progress check — no Supabase push)
python3 scripts/audit_report.py --input audit_results.json --open --local-only

# Submit for review (full push to Supabase + Vercel review app)
python3 scripts/audit_report.py --input audit_results.json --open
```

**Demo report:**

```bash
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
2. **Ask the user** (AskUserQuestion) with 3 options — this prompt is MANDATORY after every audit:

   | Label | Description |
   |---|---|
   | **Just show results** | I'll review the summary in conversation. No report, no Supabase. |
   | **Generate report (local only)** | Create an HTML report I can share or reference. Nothing goes to the review app. |
   | **Generate report + submit for review** | Create the report AND push findings to the review app for IDA/QA review. |

3. **If just show results**: Done. No `audit_report.py` call. The conversation summary is sufficient.
4. **If local only**: `python3 scripts/audit_report.py --input audit_results.json --open --local-only`
   - Report saved to `reports/` and opened in browser
   - NO Supabase push, NO Vercel session, NO review pipeline
   - Tell the user: "Report saved locally. When you're ready for formal review, run another audit and choose 'Submit for review.'"
5. **If submit for review**: `python3 scripts/audit_report.py --input audit_results.json --open`
   - Report saved + findings pushed to Supabase + session created (all handled by `push_to_rlhf()` inside the script)
   - The script returns `rlhf_session_id` in its JSON output — use this as `<SESSION_ID>`
   - Provide the Vercel review app URL:
     > Your findings are live at: `https://idw-review-app.vercel.app/session/<SESSION_ID>`

   **Post-submission messaging — vary by audit purpose:**

   - **If `self_audit`** (ID auditing their own course):
     > "Your findings are submitted. Next steps:"
     > 1. "Review your findings in the review app at the link above"
     > 2. "When ready, submit for QA review — an admin will assign an ID Assistant to validate the Col B (structural) findings"
     > 3. "Once the ID Assistant completes their review, you can remediate any approved issues"
     >
     > "Want to submit for QA review now, or review the findings yourself first?"

     If yes: `python3 scripts/audit_session_manager.py --submit --session-id <SESSION_ID>`

   - **If `qa_review` or `recurring`** (QA team auditing a course):
     > "Your findings are submitted. Here's what happens next:"
     > 1. "An admin assigns an ID Assistant to this session in the review app"
     > 2. "The ID Assistant validates all Col B findings (agree/disagree on each)"
     > 3. "When they mark the session complete, Col C findings are auto-approved"
     > 4. "Then you can remediate flagged issues using the fix queue"
     >
     > "You can monitor progress in the review app. Want to start remediating now, or wait for the IDA review?"

5. **If user wants to remediate now**: Transition to fix queue (Path D in concierge) or offer `/bulk-edit` for batch fixes
6. **If user wants to wait**: End the audit flow — they can return later via "Work through fix queue" in the concierge

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

## XLSX Report Output (DEPRECATED)

XLSX report generation exists in `audit_report.py --xlsx` but is **not part of the pilot workflow**. The HTML report is the primary deliverable. Airtable serves as the structured data output. Do not offer XLSX generation during audits unless the user explicitly asks for an Excel file.

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

7. **At the end**, present the same 3-choice output prompt as Quick Check and Deep Audit (show results only / local report / submit for review). If the user chooses a report, produce it with annotations:
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
