---
name: discussion-generator
description: "Create graded discussion prompts for a Canvas module."
---

# Discussion Board Generation Skill

> **Plugin**: ASU Canvas Course Builder
> **References**: syllabus-generator/SKILL.md (for objective alignment), rubric-creator/SKILL.md (for rubric generation)

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python scripts/idw_metrics.py --track skill_invoked --context '{"skill": "discussion-generator"}'
```
This records usage metrics for the pilot dashboard. Do not skip this step.

## Purpose
Generate graded discussion board activities for Canvas courses. Every content module includes a discussion to:
- Develop argumentation and communication skills
- Encourage peer learning through structured engagement
- Apply concepts to open-ended professional, clinical, or ethical scenarios
- Build community among students
- Practice the type of reasoning and debate valued in their discipline

## Required Inputs

| Input | Source |
|---|---|
| Module number and title | Course blueprint |
| Module learning objectives | Course blueprint |
| Assessment-to-Objective alignment | Course blueprint alignment matrix |
| Discussion type recommendation | Based on module position and content |
| Professional/clinical context | Discipline-specific scenarios |
| Prior module concepts | For integration-type discussions |

## Pre-Generation Prompt — Discussion Configuration

Before generating any discussion, **always confirm these parameters with the user**:

> **1. Discussion type** — "Which type fits this module?"
>
> | Type | Best For | Bloom's | Example |
> |---|---|---|---|
> | **Type E: Reflective Application** | Early modules, foundational concepts | Apply | "How does this concept connect to your professional goals?" |
> | **Type A: Professional Reasoning Debate** | Modules with ambiguous scenarios | Analyze | "Which explanation is more likely? Defend your position." |
> | **Type B: Significance Comparison** | Modules with parallel concepts | Evaluate | "Which mechanism has greater practical significance?" |
> | **Type C: What Would Happen If** | Modules with predictive/causal content | Evaluate | "Predict the consequences of this intervention." |
> | **Type D: Integration Challenge** | Late modules, cross-module synthesis | Create | "Explain this case using concepts from 3 modules." |
>
> **2. Points** — "25 points is our default. Does this fit your grading scheme?" (Intro discussion = 10 pts)
>
> **3. Word count** — "Initial post: 300-400 words, peer responses: 150-250 words. Adjust?"
>
> **4. Peer response count** — "2 peer responses is standard. More or fewer?"
>
> **5. Rubric structure** — "3 criteria (Reasoning 10 / Engagement 10 / Communication 5) is default. Different?"

If the user specifies "discussions for all modules," ask these once for the batch and apply consistently, noting any per-module overrides. Recommend the type progression (E → A/B → C/D) for scaffolded difficulty.

---

## Discussion Parameters
- **Points**: 25 points per module discussion (adjustable); introductory discussion = 10 pts
- **Structure**: Initial post + 2 peer responses
- **Rubric**: Required — use the rubric-creator skill
- **Timing**: Initial post due mid-module; responses due end of module
- **Canvas setting**: "Students must post before seeing replies" = ENABLED (required)

## Discussion Prompt Design

### Prompt Characteristics
A great discussion prompt:
1. **Has no single right answer** — requires reasoning, not recall
2. **Invites legitimate disagreement** — students can argue different positions with evidence
3. **Requires course content application** — can't be answered without the module material
4. **Connects to professional reality** — feels relevant to career practice
5. **Is specific enough** to focus responses but **open enough** to generate diverse perspectives
6. **Builds on the lecture video** — extends the anchor content into debatable territory

### Prompt Types

**Type A: Professional/Clinical Reasoning Debate**
Present a scenario with an ambiguous or complex mechanism. Students argue for a specific explanation using module concepts.
- "A [scenario] occurs with [observations]. Two explanations are proposed: [A] and [B]. Which do you think is more likely, and why? Use specific concepts from this module to support your argument."

**Type B: Mechanism Comparison & Significance**
Ask students to compare related mechanisms or approaches and argue which is more significant.
- "We've studied [mechanism X] and [mechanism Y] in this module. Which do you think has greater [practical/clinical/theoretical] significance, and why? Support your argument with at least one specific scenario."

**Type C: "What Would Happen If" Prediction**
Present a hypothetical perturbation and ask students to predict consequences using disciplinary reasoning.
- "Imagine [a new intervention/tool/drug/policy] is developed that [specific mechanism of action]. Predict the consequences at [multiple levels of analysis]. What unintended effects would you anticipate, and why?"

**Type D: Integration Challenge**
Ask students to connect concepts across multiple modules.
- "We've now covered [topics from multiple modules]. Choose a single [case/scenario/problem] and explain it using concepts from at least [2-3] different modules. How do these concepts interact?"

**Type E: Reflective Application**
Scaffolded prompt for lower-Bloom's engagement — ideal for early modules, introductory courses, or modules where students need structured support before higher-order debates. Students reflect on a concrete scenario and connect it to their own experience or professional aspirations.
- "Consider this [real-world scenario/professional situation]: [brief description]. In your post: (1) Identify which concept(s) from this module are most relevant to understanding the situation. (2) Explain how you would apply one concept to [a specific task/decision] in the scenario. (3) Reflect on how this connects to your own experience or professional goals. What surprised you or changed your thinking?"

**When to use Type E**: When students are new to the discipline, the module introduces foundational concepts, or the discussion serves as a warmup before more demanding Type A-D discussions later in the course. Type E builds confidence in applying concepts before students are expected to debate or integrate across modules.

### Recommended Progression
- **Early modules (M1-M2)**: Type E or A — scaffolded application or single-module reasoning
- **Middle modules (M3-M5)**: Type A, B, or C — mechanism application, comparison, and prediction
- **Late modules (M6-M8)**: Type C or D — cross-module integration challenges

## Discussion Prompt Template

```
## Discussion [#]: [Title]

### The Scenario
[2-3 paragraphs presenting the scenario, question, or challenge. Include enough
detail to ground the discussion but leave room for interpretation and debate.]

### Your Initial Post (due [date])
In your initial post (300-400 words), address the following:

1. [Primary question — requires applying module concepts to the scenario]
2. [Secondary question — requires reasoning about mechanism or significance]
3. Support your reasoning with specific concepts from this module. Reference the
   lecture video, readings, or other course resources.

### Peer Responses (2 responses due [date])
Respond to at least TWO classmates' posts (150-250 words each). Your responses should:
- Engage substantively with their reasoning (not just "I agree, good point")
- Add a new perspective, ask a probing follow-up question, or respectfully challenge their reasoning
- Reference specific course concepts in your response

### What Makes a Great Post
- Uses precise discipline-specific terminology
- Traces reasoning through multiple levels of analysis
- Makes connections to prior modules
- Acknowledges complexity and uncertainty where appropriate
- References specific course resources

### Grading
This discussion is worth 25 points. See the attached rubric.
```

## Module 0: Introduction Discussion

Every course should include an introductory discussion (D0) for community building:

**Type**: Community building + baseline assessment
**Points**: 10 (lower stakes than content discussions)
**Rubric**: Simplified 2-criterion rubric (Engagement 5 pts, Completeness 5 pts)

**Template:**
"What is the most interesting [discipline topic/concept] you've encountered in your studies so far, and why does it fascinate you? Describe it in your own words and explain why you think it's important for [professional context]. Respond to at least two classmates — if someone mentions a topic you're curious about, ask them a question!"

**Design note**: This is diagnostic and community-building. Keep it low-stakes and welcoming.

## Discussion Facilitation Guide (for Instructor)
To maximize discussion quality:
1. **Model exemplary reasoning** — Post a faculty response to the first 1-2 discussions showing the depth and style expected
2. **Redirect off-topic threads** — Gently steer conversations back to course concepts when they drift
3. **Prompt quieter students** — Ask follow-up questions to students who post but don't receive responses
4. **Highlight strong reasoning** — Call out (anonymously or with permission) posts that demonstrate excellent analytical thinking

## Rubric Integration
Each module discussion uses the standard discussion rubric template from the rubric-creator skill:
- Scientific/Professional Reasoning (10 pts)
- Peer Engagement (10 pts)
- Evidence & Communication (5 pts)

D0 uses a simplified 10-point rubric:
- Engagement & Thoughtfulness (5 pts)
- Completeness & Peer Interaction (5 pts)

### Attaching Rubrics to Discussions (Canvas API)

Canvas discussions with grading enabled have an underlying assignment object. To attach a rubric, you must target that assignment — not the discussion topic itself.

**Step 1 — Get the assignment_id:**
```
GET /api/v1/courses/:course_id/discussion_topics/:topic_id
→ response includes "assignment_id": 12345
```

**Step 2 — POST the rubric with association:**
```
POST /api/v1/courses/:course_id/rubrics
Body: {
  "rubric": {
    "title": "Discussion Rubric — Module N",
    "criteria": {
      "0": { "description": "Scientific/Professional Reasoning", "points": 10,
             "ratings": { "0": {"description":"...","points":10}, "1": {"description":"...","points":7}, ... }},
      "1": { "description": "Peer Engagement", "points": 10, ... },
      "2": { "description": "Evidence & Communication", "points": 5, ... }
    }
  },
  "rubric_association": {
    "association_type": "Assignment",
    "association_id": 12345,
    "use_for_grading": true,
    "purpose": "grading"
  }
}
```

**Important**: The `criteria` and `ratings` use a dict-of-dicts format with **string keys** ("0", "1", "2"), not arrays. Each rating also uses string keys. This is a Canvas API quirk — arrays will silently fail.

## Intra-Module Alignment Check

Before generating a discussion, verify alignment with the other assessments in the same module:

1. **Reference the syllabus** (`syllabus-generator/SKILL.md`) for this module's objectives and the Assessment-to-Objective Alignment Matrix
2. **Review the module's Knowledge Check and Artifact**: Which objectives do they assess? The Discussion should extend into different territory — open-ended reasoning, peer debate, or cross-module integration — rather than re-testing the same skills
3. **Verify Bloom's level**: Discussions should target **Evaluate** or **Create** — higher than the Knowledge Check (Apply/Analyze) and complementary to the Artifact (Analyze/Evaluate)
4. **Check the formative→summative progression**: The Knowledge Check should preview relevant concepts, but the Discussion should push students beyond what any auto-graded assessment can measure
5. **Document alignment** in the output: list covered objectives by ID and explain how the Discussion complements the Artifact

## Output
The skill produces:
1. Complete discussion prompt with scenario, requirements, and rubric reference
2. Canvas setup configuration (points, due dates, post-first settings enabled)
3. Objective alignment map (referencing blueprint objective IDs)
4. Suggested grading notes for instructor
5. 2-3 example "strong response" descriptions to help calibrate expectations

## Error Handling

| Error | User Message | Recovery |
|-------|-------------|----------|
| No course-config.json | "I need course context first. Let me create a config from your course." | Auto-create minimal config |
| Missing module objectives | "Module {N} doesn't have objectives defined yet. Let's add them before creating the discussion." | Guide objective creation |
| Push fails | "The discussion push failed but your content is saved in staging/. Let's try again." | Retry |
| Canvas API 401/403 | "Authentication issue — check your Canvas token and course permissions." | Guide re-auth |
| Read-only mode | "Read-only mode is active. The discussion is staged locally but can't be pushed until writes are enabled." | Guide .env change |

## Post-Push Verification (Required)

After pushing the discussion to Canvas, always:

1. **Fetch and confirm** the created discussion via `GET /api/v1/courses/:id/discussion_topics/:id` and display:
   - Title, points, rubric attached (yes/no), published status, post-before-seeing-replies setting
2. **Provide the direct Canvas link**: `https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/discussion_topics/{id}`
3. **Offer a screenshot**: "Want me to screenshot how this looks in Canvas?" If yes, navigate to the Canvas URL and capture it.


## Remediation Event Recording

When this skill fixes an issue that was flagged from an audit finding, record the remediation event so the FindingCard shows the fix history. **This step is required when the fix originated from the fix queue.**

After successfully pushing the fix to Canvas, run:

```bash
python3 scripts/remediation_tracker.py --record --finding-ids <FINDING_ID> --skill discussion-generator --description "<WHAT_WAS_FIXED>"
```

This:
1. Records a `remediation_events` row in Supabase
2. Clears the `remediation_requested` flag on the finding
3. The FindingCard in Vercel will show "Remediated via /<skill> (Name, Date)"

If the fix was NOT from the fix queue (e.g., user asked to create something new), skip this step.

