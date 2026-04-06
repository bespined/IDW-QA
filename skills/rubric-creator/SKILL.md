---
name: rubric-creator
description: "Create or edit analytic rubrics for Canvas assessments. Owns all rubric API calls including attachment."
---

# Rubric Skill (Create or Edit)

> **Plugin**: ASU Canvas Course Builder
> **Called by**: assignment-generator, discussion-generator (they provide `assignment_id`, this skill handles all rubric API calls)
> **Standalone**: Yes — can be invoked directly with `/rubric-creator`

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python scripts/idw_metrics.py --track skill_invoked --context '{"skill": "rubric-creator"}'
```
This records usage metrics for the pilot dashboard. Do not skip this step.

## Purpose
Generate assessment rubrics for assignments and discussions. Rubrics are required for all graded assignments and discussions per ASU Canvas standards. They serve to:
- Communicate clear expectations before students begin work
- Ensure consistent, fair grading
- Provide structured feedback that references specific criteria
- Align assessment directly to module learning objectives

## Modes of Operation

### Integrated Mode (default)
Used when invoked by `assignment-generator` or `discussion-generator` during course building. All required inputs come from the calling skill and `course-config.json`. The intra-module alignment check runs automatically.

### Standalone Mode
Use `/rubric-creator` directly to generate a rubric for any assessment — even one not yet defined in a course blueprint. In standalone mode, the skill will ask for the required inputs interactively:

1. **What is being assessed?** — Assessment title and brief description of the task
2. **Assessment type?** — Assignment, Discussion, Presentation, Portfolio, or Other
3. **Total points?** — How many points the rubric should sum to
4. **How many criteria?** — 3-5 criteria (default: 3)
5. **Discipline context?** — The academic field (for terminology and rubric language)
6. **What does success look like?** — Brief description of exemplary work (helps calibrate the Exemplary level)

Standalone mode does NOT require `course-config.json`. It asks for all inputs interactively and skips the intra-module alignment check. Module number and objectives are optional — if unavailable, the rubric is built from the assessment description alone. All other rubric design principles apply fully.

## Required Inputs

| Input | Source | Standalone |
|---|---|---|
| Assessment title | The assessment being rubric'd | Asked interactively |
| Assessment type | Assignment, Discussion, Presentation, Portfolio, or Other | Asked interactively |
| Total points | From course blueprint | Asked interactively |
| Module number and objectives | Course blueprint | Optional (skipped if unavailable) |
| Specific task description | What students are creating/doing | Asked interactively |
| Discipline context | For criterion examples | Asked interactively |

## ASU Canvas Rubric Standards
- **Type**: Analytic rubrics (not holistic)
- **Criteria**: 3-5 criteria per rubric
- **Performance levels**: 4 levels (Exemplary, Proficient, Developing, Beginning)
- **Points**: Criteria points must sum to the assignment total
- **Descriptors**: Each cell must contain specific, observable descriptions (not vague)
- **Attached to**: Every Assignment and graded Discussion in Canvas

## Rubric Structure

### Performance Level Definitions
| Level | Score Range | General Description |
|---|---|---|
| **Exemplary** | 90-100% of criterion points | Exceeds expectations; demonstrates sophisticated understanding, insightful connections, or exceptional quality |
| **Proficient** | 75-89% of criterion points | Meets expectations; demonstrates solid understanding with minor gaps or areas for improvement |
| **Developing** | 50-74% of criterion points | Approaching expectations; demonstrates partial understanding with significant gaps or errors |
| **Beginning** | 0-49% of criterion points | Below expectations; demonstrates minimal understanding or fails to address the criterion |

### Criterion Categories

**For Assignments (Create an Artifact):**
1. **Conceptual Accuracy** — Correctness of key concepts, terminology, relationships
2. **Applied Reasoning** — Quality of connections between concepts and professional/clinical scenarios
3. **Analytical Depth** — Level of reasoning, cause-effect logic, systems thinking
4. **Communication** — Clarity, organization, use of proper discipline-specific terminology
5. **Completeness** — Addresses all required components of the assignment

**For Discussions:**
1. **Initial Post Quality** — Depth of response, evidence of critical thinking, use of course concepts
2. **Professional/Scientific Reasoning** — Application of disciplinary principles to the discussion prompt
3. **Peer Engagement** — Quality of responses to classmates (not just "I agree")
4. **Evidence Integration** — Use of course materials, resources, or outside sources
5. **Professionalism** — Writing quality, respectful tone, appropriate language

## Rubric Design Principles

### 1. Backward Design Alignment
Every criterion must trace back to a specific module learning objective:
- Start with the objective → What does "meeting this objective" look like?
- Exemplary = exceeds the objective (deeper insight, novel connections)
- Proficient = meets the objective as stated
- Developing = partially meets (correct direction but incomplete)
- Beginning = does not meet (fundamental misunderstanding or missing)

### 2. Observable & Measurable Descriptors
Each cell must describe **what the evaluator can see**, not internal states:
- ❌ "Student understands the concept well"
- ✅ "Student correctly identifies all components of the [process/system] and explains the role of each with a specific example"

### 3. Graduated Differentiation
Each level should clearly differ from adjacent levels:
- Exemplary vs. Proficient: depth, insight, connections
- Proficient vs. Developing: accuracy, completeness
- Developing vs. Beginning: presence of attempt, partial vs. absent

### 4. Discipline-Appropriate Values
Rubrics should value:
- Analytical reasoning and application over memorization
- Mechanistic explanation (cause → effect chains)
- Integration across topics (connecting to prior modules)
- Professional communication skills

**For health sciences courses**, additionally value:
- Clinical reasoning and pathophysiological tracing
- Patient-centered thinking
- Evidence-based reasoning

## How to Generate a Rubric

### Step 1: Identify Assignment Parameters
- Assignment type (Assignment or Discussion)
- Total points
- Module number and learning objectives
- Specific task description (what students are creating/doing)

### Step 2: Select 3-5 Criteria
Based on the assignment type and objectives:
- Map each criterion to 1-2 learning objectives
- Ensure criteria don't overlap significantly
- Distribute points based on relative importance
- Weight conceptual accuracy and applied reasoning highest

### Step 3: Write Descriptors
For each criterion × level cell:
1. Write the **Proficient** level first (this IS the expectation)
2. Write **Exemplary** by asking "what would exceed this?"
3. Write **Developing** by asking "what would partially meet this?"
4. Write **Beginning** by asking "what would fundamentally miss this?"

### Step 4: Format for Canvas
Output in this format:

```
## Rubric: [Assignment/Discussion Name]
**Total Points**: [X]
**Module**: [#] — [Title]
**Objectives Assessed**: [List]

| Criterion | Exemplary ([X] pts) | Proficient ([X] pts) | Developing ([X] pts) | Beginning ([X] pts) |
|---|---|---|---|---|
| **[Criterion 1]** ([X] pts) | [Description] | [Description] | [Description] | [Description] |
| **[Criterion 2]** ([X] pts) | [Description] | [Description] | [Description] | [Description] |
| **[Criterion 3]** ([X] pts) | [Description] | [Description] | [Description] | [Description] |
```

---

## Edit Existing Rubric

When the user wants to fix or modify an existing rubric, skip the generation questionnaire.

### Step 1: Fetch the rubric

If the user provides an assignment or discussion, get the rubric from it:
```
GET /api/v1/courses/:course_id/assignments/:assignment_id?include[]=rubric
```
The `rubric` field contains the criteria array. The `rubric_settings.id` gives the rubric ID.

Or fetch directly:
```
GET /api/v1/courses/:course_id/rubrics/:rubric_id
```

### Step 2: Display current criteria

Show a table:
| # | Criterion | Points | Exemplary | Proficient | Developing | Beginning |
|---|---|---|---|---|---|---|
| 1 | Conceptual Accuracy | 10 | (truncated) | (truncated) | (truncated) | (truncated) |
| 2 | Applied Reasoning | 10 | ... | ... | ... | ... |
| 3 | Communication | 10 | ... | ... | ... | ... |

### Step 3: Get edit instructions

Common operations:
- Change criterion descriptors
- Add/remove a criterion
- Adjust point distribution
- Rewrite for a different Bloom's level

### Step 4: Rebuild and push

Canvas does NOT support partial criterion updates — you must PUT the entire rubric:
```
PUT /api/v1/courses/:course_id/rubrics/:rubric_id
Body: <full rubric JSON — see Canvas API Format below>
```

### Step 5: Verify
```
GET /api/v1/courses/:course_id/rubrics/:rubric_id
```
Confirm criteria count, total points, and attachment.

---

## Canvas API Format (Authoritative Reference)

**This is the canonical documentation for rubric serialization.** Assignment-generator and discussion-generator defer to this section.

Canvas requires rubric criteria and ratings as **dict-of-dicts with string keys**, not arrays. Arrays will silently fail and create a rubric with no criteria.

### Create rubric + attach to assessment:
```json
POST /api/v1/courses/:course_id/rubrics
{
  "rubric": {
    "title": "Assignment Rubric — Module N",
    "criteria": {
      "0": {
        "description": "Conceptual Accuracy",
        "points": 10,
        "ratings": {
          "0": { "description": "Exemplary", "points": 10 },
          "1": { "description": "Proficient", "points": 7 },
          "2": { "description": "Developing", "points": 4 },
          "3": { "description": "Beginning", "points": 0 }
        }
      },
      "1": {
        "description": "Applied Reasoning",
        "points": 10,
        "ratings": {
          "0": { "description": "Exemplary", "points": 10 },
          "1": { "description": "Proficient", "points": 7 },
          "2": { "description": "Developing", "points": 4 },
          "3": { "description": "Beginning", "points": 0 }
        }
      }
    }
  },
  "rubric_association": {
    "association_type": "Assignment",
    "association_id": <assignment_id>,
    "use_for_grading": true,
    "purpose": "grading"
  }
}
```

**Key rules:**
- `criteria` keys are `"0"`, `"1"`, `"2"` — string integers, not arrays
- `ratings` keys are also `"0"`, `"1"`, `"2"`, `"3"` — string integers
- `association_type` is always `"Assignment"` — even for graded discussions (target the discussion's linked assignment)
- `association_id` is the Canvas assignment ID
- `use_for_grading: true` makes it the active grading rubric

### Update existing rubric:
```json
PUT /api/v1/courses/:course_id/rubrics/:rubric_id
{
  "rubric": {
    "title": "Updated Rubric Title",
    "criteria": { ... same dict-of-dicts format ... }
  }
}
```
The association is preserved — no need to re-attach.

---

## Attachment Ownership Rule

**Rubric-creator owns all rubric Canvas API calls.** When invoked by assignment-generator or discussion-generator:

1. The calling skill creates the assessment (assignment or discussion) and gets back the `assignment_id`
2. The calling skill passes the `assignment_id` and rubric requirements to rubric-creator
3. **Rubric-creator handles the POST /rubrics call with `rubric_association`** — the calling skill does NOT make its own rubric API call
4. Rubric-creator verifies the rubric was attached correctly

This prevents competing rubric-attachment code in multiple skills.

---

## Template: Assignment Rubric (30 points)

```
| Criterion | Exemplary (9-10 pts) | Proficient (7-8 pts) | Developing (5-6 pts) | Beginning (0-4 pts) |
|---|---|---|---|---|
| **Conceptual Accuracy** (10 pts) | All key concepts are correctly described with precise terminology. Identifies nuances or exceptions that demonstrate deep understanding. | All major concepts are correctly described. Minor terminology imprecisions that don't affect meaning. | Most concepts are described but contains 1-2 significant conceptual errors. Some terminology is incorrect. | Multiple fundamental conceptual errors. Key concepts are missing or described incorrectly. |
| **Applied Reasoning** (10 pts) | Scenario is analyzed with sophisticated reasoning. Correctly identifies the causal chain from foundational concepts to observable outcomes. Makes connections beyond what was explicitly taught. | Scenario is correctly analyzed. Identifies the main mechanisms. Connections between concepts and outcomes are logical and accurate. | Attempts to connect concepts to the scenario but reasoning has gaps. Some mechanisms are correct but the causal chain is incomplete. | Fails to connect concepts to the scenario. Analysis is superficial or contains fundamental errors. |
| **Analytical Depth & Communication** (10 pts) | Reasoning is exceptionally clear and well-organized. Uses cause-effect logic throughout. Integrates concepts from multiple modules. Writing is polished and precise. | Reasoning is clear and follows logical structure. Cause-effect relationships are identified. Writing uses appropriate terminology. | Reasoning is present but sometimes unclear. Some cause-effect relationships are identified but not consistently. Writing quality is inconsistent. | Little to no analytical reasoning. Response is descriptive rather than analytical. Writing is disorganized. |
```

## Template: Discussion Rubric (25 points)

```
| Criterion | Exemplary (9-10 pts) | Proficient (7-8 pts) | Developing (5-6 pts) | Beginning (0-4 pts) |
|---|---|---|---|---|
| **Initial Post: Reasoning Quality** (10 pts) | Response demonstrates sophisticated understanding of the concepts. Provides mechanistic explanation with clear cause-effect reasoning. Makes insightful connections to professional practice or prior modules. | Response correctly applies concepts to the prompt. Reasoning is logical and mostly analytical. Addresses the application component. | Response addresses the prompt but reasoning is superficial. Some concepts are correct but explanation lacks depth. | Response does not meaningfully address the prompt or contains fundamental misconceptions. |
| **Peer Responses: Critical Engagement** (10 pts) | Responses to peers advance the discussion substantively. Adds new perspectives, asks probing questions, or respectfully challenges reasoning with evidence. | Responses to peers engage meaningfully with their ideas. Asks relevant questions or adds supporting information. | Responses to peers are brief or superficial. Limited engagement with peers' reasoning. | No peer responses, or responses are off-topic/do not engage with peers' content. |
| **Evidence & Communication** (5 pts) | References specific course content (lecture, readings, resources) and uses precise terminology. Writing is clear and professional. | References course content and uses mostly appropriate terminology. Writing is clear. | Limited reference to course content. Some terminology is incorrect. Writing quality is adequate. | No reference to course materials. Terminology is inappropriate. Writing quality impedes understanding. |
```

## Intra-Module Alignment Check

Before generating a rubric, verify it aligns with the assessment it serves and the broader module assessment suite:

1. **Reference the syllabus** (`syllabus-generator/SKILL.md`) for this module's objectives and the Assessment-to-Objective Alignment Matrix
2. **Match rubric criteria to assessed objectives**: Each rubric criterion should map to 1-2 specific module objectives. Document this mapping
3. **Verify Bloom's level in descriptors**: The Exemplary level should describe work at or above the target Bloom's level for the assessment type (KC = Apply, Artifact = Analyze/Evaluate, Discussion = Evaluate/Create)
4. **Check complementarity with other module rubrics**: If the module has both an Artifact rubric and a Discussion rubric, ensure criteria don't overlap heavily — each should evaluate different dimensions of learning
5. **Document alignment** in the output: include a criterion-to-objective mapping table

## Post-Push Verification (Required)

After pushing a rubric to Canvas, always:

1. **Fetch and confirm** via `GET /api/v1/courses/:id/rubrics/:id` and display:
   - Rubric title, criterion count, total points, assessment it's attached to
2. **Provide the direct Canvas link** to the associated assignment or discussion:
   - Assignment: `https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/assignments/{id}`
   - Discussion: `https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/discussion_topics/{id}`
3. **Offer a screenshot**: "Want me to screenshot the rubric as it appears in Canvas?" If yes, navigate and capture it.

## Output
The skill produces:
1. Complete analytic rubric formatted for Canvas
2. Criterion-to-objective alignment map (using blueprint objective IDs)
3. Point distribution rationale
4. Canvas setup instructions (how to attach rubric to assignment)


## Remediation Event Recording

When this skill fixes an issue that was flagged from an audit finding, record the remediation event so the FindingCard shows the fix history. **This step is required when the fix originated from the fix queue.**

After successfully pushing the fix to Canvas, run:

```bash
python3 scripts/remediation_tracker.py --record --finding-ids <FINDING_ID> --skill rubric-creator --description "<WHAT_WAS_FIXED>"
```

This:
1. Records a `remediation_events` row in Supabase
2. Clears the `remediation_requested` flag on the finding
3. The FindingCard in Vercel will show "Remediated via /<skill> (Name, Date)"

If the fix was NOT from the fix queue (e.g., user asked to create something new), skip this step.

