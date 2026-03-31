---
name: course-review
description: "Instructional design review with a scored rubric report."
---

# Course Review Skill

> **Plugin**: ASU Canvas Course Builder
> **Run**: `/course-review`
> **Standalone**: Yes — works on any Canvas course, not just courses built with this plugin

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python scripts/idw_metrics.py --track skill_invoked --context '{"skill": "course-review"}'
```
This records usage metrics for the pilot dashboard. Do not skip this step.

## Purpose

Perform a comprehensive instructional design review of a completed (or near-complete) Canvas course. This is the "expert eye" that evaluates the course holistically — not just structure and compliance (that's `/course-audit`), but **pedagogical quality, alignment coherence, and student experience**.

Use this skill:
- After completing a course build, before launch
- When reviewing a course built by someone else
- As a periodic quality check on a running course
- When preparing for formal course review (e.g., Quality Matters)

## Difference from `/course-audit`

| | `/course-audit` | `/course-review` |
|---|---|---|
| **Focus** | Structural compliance | Pedagogical quality |
| **Checks** | "Does every module have 7 pages?" | "Do the pages create a coherent learning journey?" |
| **Output** | Pass/fail checklist | Scored rubric with narrative feedback |
| **Speed** | Fast (automated checks) | Thorough (reads and evaluates content) |
| **Fixes** | Can auto-fix many issues | Produces recommendations for human action |

---

## Review Dimensions

The review evaluates the course across 8 dimensions, each scored 1-4:

| Score | Label | Meaning |
|---|---|---|
| 4 | **Exemplary** | Exceeds best practices; could serve as a model |
| 3 | **Proficient** | Meets expectations with minor improvement opportunities |
| 2 | **Developing** | Significant gaps that should be addressed before launch |
| 1 | **Beginning** | Fundamental issues that must be resolved |

### Dimension 1: Learning Objective Alignment (weight: 15%)

- Are CLOs clearly stated and appropriately scoped?
- Do module objectives map to CLOs with complete coverage?
- Are Bloom's levels appropriate and progressive across modules?
- Does every assessment align to specific module objectives?
- Are there orphan objectives (stated but never assessed)?
- Are there orphan assessments (no clear objective connection)?

**Evidence**: Read `course-config.json` (or syllabus page), cross-reference with assessment instructions and rubric criteria.

### Dimension 2: Assessment Quality (weight: 20%)

- Do quiz questions test understanding, not just recall? (Bloom's Apply+ for Knowledge Checks)
- Are assignment instructions clear, with unambiguous deliverables?
- Do rubrics have observable, measurable descriptors (not vague)?
- Are rubric levels clearly differentiated (Exemplary vs. Proficient vs. Developing vs. Beginning)?
- Do discussions require higher-order thinking (not just "summarize")?
- Is the assessment mix appropriate (variety of types across modules)?
- Are point allocations balanced and fair?

**Evidence**: Read quiz questions, assignment instructions, rubric cells, discussion prompts.

### Dimension 3: Content Quality & Accuracy (weight: 15%)

- Is content current, accurate, and authoritative?
- Are sources properly cited or attributed?
- Is content appropriately scoped (not too much or too little per module)?
- Are key concepts explained before being assessed?
- Is discipline-specific terminology used correctly and defined?
- Are multimedia elements pedagogically purposeful (not decorative)?

**Evidence**: Read lesson pages, resource links, media descriptions.

### Dimension 4: Student Experience & Navigation (weight: 10%)

- Is the module structure intuitive and consistent?
- Can students easily find what they need?
- Are instructions clear about what to do and when?
- Is the estimated workload reasonable per module?
- Are there clear signposts (overview → conclusion arc)?
- Do conclusion pages effectively bridge to the next module?
- Is the tone welcoming and encouraging rather than transactional or punitive?
- Does language use asset-based framing (what students *will* learn) rather than deficit-based framing (what students *lack*)?
- Are examples, scenarios, and case studies diverse and inclusive (names, contexts, perspectives)?
- Is communication style consistent across modules (voice, tone, level of formality)?
- Are students addressed respectfully and as partners in learning?

**Evidence**: Walk through each module as a student would. Read overview, lesson, and conclusion pages for tone. Check assignment instructions and discussion prompts for inclusive framing. Compare voice across early, middle, and late modules for consistency.

### Dimension 5: Engagement & Active Learning (weight: 15%)

- Do modules include active learning opportunities (not just reading)?
- Are interactive activities meaningful (not busywork)?
- Do discussions prompt genuine intellectual exchange?
- Are there opportunities for self-assessment and reflection?
- Is there variety in activity types across modules?
- Do media elements (podcasts, videos) add value beyond text?

**Evidence**: Review interactive activities, discussion prompts, guided practice activities.

### Dimension 6: Accessibility & Inclusion (weight: 10%)

- Do all images have meaningful alt text?
- Is heading hierarchy correct and consistent?
- Are color contrasts WCAG 2.1 AA compliant?
- Do all media have captions and transcripts?
- Are link texts descriptive (no "click here")?
- Is content readable without CSS/JavaScript?
- Are multiple means of representation provided (UDL)?

**Evidence**: Run `/accessibility-audit` and review results; check media for captions.

### Dimension 7: Scaffolding & Progression (weight: 10%)

- Do modules build on each other logically?
- Are prerequisite concepts introduced before they're needed?
- Is there appropriate scaffolding for complex tasks?
- Does cognitive demand increase appropriately across the course?
- Are bridging elements present (prior module → current module connections)?
- Are early modules more scaffolded than later ones?

**Evidence**: Read overview and conclusion pages for bridging; check Bloom's progression in objectives.

### Dimension 8: Professional/Applied Connections (weight: 5%)

- Are professional/clinical scenarios realistic and relevant?
- Do students see why the content matters for their career?
- Are applied examples discipline-appropriate?
- Do assignments simulate real-world professional tasks?

**Evidence**: Read assignment prompts, discussion scenarios, lesson page connections.

---

## How to Conduct a Review

### Step 0: Course Selection + Fix Queue

**If the user has multiple course assignments**, show them first so they can pick which course to review:

```bash
python3 scripts/fetch_fix_queue.py --summary
```

If there are remediation items across multiple courses, present a summary:

> **Courses with pending remediations:**
> 1. **CRJ 201** — 5 items flagged
> 2. **LAW 517** — 3 items flagged
> 3. **BIO 101** — 0 items (all clear)
>
> Which course would you like to review?

If the user picks a course, switch to it (update `.env`) and proceed.

**For the selected course**, check the fix queue:

```bash
python3 scripts/fetch_fix_queue.py --course-id <COURSE_ID> --with-feedback --summary
```

If the queue has items, present them to the user:

> **There are N findings flagged for remediation** from previous audits.
> Would you like to:
> 1. **Address the fix queue first** — work through flagged items before the full review
> 2. **Run the full review** — review the whole course (fix queue items will be included)
> 3. **View the queue** — see the detailed list of flagged items

If the user chooses to address the fix queue:
```bash
python3 scripts/fetch_fix_queue.py --course-id <COURSE_ID> --with-feedback
```

Present each finding with its `criterion_id` (B-XX.Y or C-XX.Y), reviewer feedback (if any), and offer to fix it using the appropriate remediation skill (quiz, assignment-generator, bulk-edit, etc.).

**After each fix:**
1. Clear the finding's `remediation_requested` flag
2. Record a `remediation_events` row so the FindingCard shows the remediation history:
```bash
python3 -c "
import requests, os
resp = requests.post('https://YOUR_VERCEL_URL/api/remediation-events',
    json={'finding_id': '<FINDING_ID>', 'remediated_by': os.getenv('IDW_TESTER_ID'), 'skill_used': '<SKILL>', 'description': '<WHAT_WAS_FIXED>'},
    timeout=15)
"
```

### Step 1: Gather Course Data

1. Read `course-config.json` for the blueprint (objectives, assessments, grading)
2. Fetch all pages from Canvas: `GET /api/v1/courses/{id}/pages?per_page=100`
3. Fetch all assignments: `GET /api/v1/courses/{id}/assignments?per_page=100`
4. Fetch all quizzes: `GET /api/v1/courses/{id}/quizzes?per_page=100`
5. Fetch all discussion topics: `GET /api/v1/courses/{id}/discussion_topics?per_page=100`
6. Fetch all modules with items: `GET /api/v1/courses/{id}/modules?include[]=items&per_page=100`

### Step 2: Module-by-Module Review

For each content module (M1 through M-N):

1. **Read every page** in the module (Overview through Conclusion)
2. **Read the assessment content** (quiz questions, assignment instructions, discussion prompts)
3. **Check rubric quality** (if rubrics exist)
4. **Evaluate interactive activities** (if embedded)
5. **Check media** (captions present, pedagogically purposeful)
6. **Note strengths and weaknesses** per dimension

### Step 3: Cross-Module Analysis

After reviewing individual modules, assess:
- Progression of Bloom's levels across the course
- Assessment variety (not all concept maps, not all case studies)
- Discussion type variety
- Consistent quality across modules (no "early modules great, later modules rushed")
- CLO coverage completeness

### Step 4: Score and Report

Assign a score (1-4) for each of the 8 dimensions. Calculate a weighted overall score.

---

## Report Format

```markdown
# Course Review Report
**Course**: [Title]
**Reviewer**: Claude (ASU Canvas Course Builder)
**Date**: [date]
**Overall Score**: [X.X / 4.0]

## Scorecard

| Dimension | Weight | Score | Rating |
|---|---|---|---|
| Learning Objective Alignment | 15% | X/4 | [Rating] |
| Assessment Quality | 20% | X/4 | [Rating] |
| Content Quality & Accuracy | 15% | X/4 | [Rating] |
| Student Experience & Navigation | 10% | X/4 | [Rating] |
| Engagement & Active Learning | 15% | X/4 | [Rating] |
| Accessibility & Inclusion | 10% | X/4 | [Rating] |
| Scaffolding & Progression | 10% | X/4 | [Rating] |
| Professional/Applied Connections | 5% | X/4 | [Rating] |
| **Weighted Overall** | **100%** | **X.X/4.0** | **[Rating]** |

## Strengths
1. [Specific strength with evidence]
2. [Specific strength with evidence]
3. [Specific strength with evidence]

## Priority Recommendations

### Critical (Must Fix Before Launch)
1. [Issue]: [Specific problem] → [Specific fix]

### Important (Should Fix Soon)
1. [Issue]: [Specific problem] → [Specific fix]

### Enhancement (Nice to Have)
1. [Issue]: [Specific improvement] → [Specific suggestion]

## Module-by-Module Notes

### Module 1: [Title]
**Strengths**: ...
**Areas for Improvement**: ...

### Module 2: [Title]
...

## Alignment Matrix

| CLO | M1 | M2 | M3 | M4 | ... | Coverage |
|---|---|---|---|---|---|---|
| CLO-1 | KC, D | A | — | KC | ... | 3/N modules |
| CLO-2 | — | KC | A, D | — | ... | 2/N modules |
...

(KC = Knowledge Check, A = Artifact, D = Discussion, GP = Guided Practice)
```

---

## Standalone Mode

When reviewing a course NOT built with this plugin (no `course-config.json`):

1. Skip the blueprint cross-reference
2. Infer objectives from syllabus page content (if available)
3. Still evaluate all 8 dimensions based on what's in Canvas
4. Note in the report: "No course-config.json found — alignment analysis based on page content only"

---

## Integration with Other Skills

After a review, the user can act on recommendations:

- **Assessment issues** → `/update-module` to replace/revise
- **Rubric issues** → `/rubric-creator` (standalone mode) to regenerate
- **Accessibility issues** → `/accessibility-audit` + `/content-fix`
- **Structural issues** → `/course-audit` for detailed structural checks
- **Content gaps** → `/update-module` to add content

---

---

### Browser Automation (Claude in Chrome)

Use Claude in Chrome for visual course review — verifying the student-facing experience matches design intent.

**MCP Tools**: `navigate`, `computer`, `read_page`, `get_page_text`, `javascript_tool`, `tabs_context_mcp`

**Where It Fits**:
- **Visual consistency review**: Navigate each Canvas page and take screenshots to verify layout, branding, and styling are consistent across modules
- **Student view QA**: Switch to student view in Canvas to confirm the experience matches what was designed — check that conditional content, locked modules, and prerequisite gates behave correctly
- **Responsive layout check**: Resize the browser to verify pages render well on different screen sizes
- **Interactive content verification**: Click through embedded interactives (H5P, external tools) to confirm they load and function correctly
- **Navigation flow**: Walk through the course as a student would — module by module — to evaluate the learning path and identify UX friction

---

## Output

The skill produces:
1. Scored review report (8 dimensions, weighted overall)
2. Prioritized recommendation list (Critical / Important / Enhancement)
3. Module-by-module notes
4. CLO-to-assessment alignment matrix
5. Comparison to ASU Canvas standards (if applicable)
