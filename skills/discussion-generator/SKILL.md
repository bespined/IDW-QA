---
name: discussion-generator
description: "Create or edit graded discussions — full generation, quick metadata edits (points, dates, post-first), or prompt editing."
---

# Discussion Skill (Create or Edit)

> **Plugin**: ASU Canvas Course Builder
> **References**: syllabus-generator/SKILL.md (for objective alignment), rubric-creator/SKILL.md (for rubric generation)

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python scripts/idw_metrics.py --track skill_invoked --context '{"skill": "discussion-generator"}'
```
This records usage metrics for the pilot dashboard. Do not skip this step.

## When to Use — Mode Routing

| User says... | Mode |
|---|---|
| "Create a discussion for Module 3" / "Generate discussion prompt" | **Mode 1: Create** (full generation flow) |
| "Set require_initial_post on Module 2 discussion" / "Change points" | **Mode 2: Edit Settings** (fast-path, no generation) |
| "Set due date on the discussion" / "Move to Discussions group" | **Mode 2: Edit Settings** (fast-path) |
| "Fix the discussion prompt for Module 4" / "Rewrite the prompt" | **Mode 3: Edit Prompt** (staging workflow) |

**Fast-path rule:** If the user asks for a narrow settings change, skip the generation questionnaire and go straight to Mode 2.

**Critical field boundary:** Graded discussion dates, points, and assignment group live on the **linked assignment object**, NOT the discussion topic. The discussion topic only holds: title, message, require_initial_post, discussion_type, pinned, locked, published. See Mode 2 for the correct API targets.

---

## Mode 1: Create Discussion

### Purpose
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

### Attaching Rubrics to Discussions

Canvas discussions with grading enabled have an underlying assignment object. To attach a rubric, you must target that assignment — not the discussion topic itself.

**Step 1 — Get the assignment_id:**
```
GET /api/v1/courses/:course_id/discussion_topics/:topic_id
→ response includes "assignment_id": 12345
```

**Step 2 — Invoke rubric-creator** with the `assignment_id`. Rubric-creator owns the Canvas rubric API call (POST /rubrics with `rubric_association`). See `skills/rubric-creator/SKILL.md` for the canonical API format (dict-of-dicts with string keys). Do NOT make your own rubric API call — pass context to rubric-creator and let it handle attachment.

## Intra-Module Alignment Check

Before generating a discussion, verify alignment with the other assessments in the same module:

1. **Reference the syllabus** (`syllabus-generator/SKILL.md`) for this module's objectives and the Assessment-to-Objective Alignment Matrix
2. **Review the module's Knowledge Check and Artifact**: Which objectives do they assess? The Discussion should extend into different territory — open-ended reasoning, peer debate, or cross-module integration — rather than re-testing the same skills
3. **Verify Bloom's level**: Discussions should target **Evaluate** or **Create** — higher than the Knowledge Check (Apply/Analyze) and complementary to the Artifact (Analyze/Evaluate)
4. **Check the formative→summative progression**: The Knowledge Check should preview relevant concepts, but the Discussion should push students beyond what any auto-graded assessment can measure
5. **Document alignment** in the output: list covered objectives by ID and explain how the Discussion complements the Artifact

### Step 6: Stage, Preview, and Push Discussion

**Stage the discussion prompt HTML first — do NOT push directly to Canvas:**
1. Save the prompt HTML to `staging/discussion-m{N}.html`
2. Run unified preview: `python3 scripts/unified_preview.py` → screenshot in conversation
3. Wait for user approval before pushing

**Canvas API for creating the discussion (after staging approval):**
```
POST /api/v1/courses/:course_id/discussion_topics
Body: {
  "title": "Discussion N: [Title]",
  "message": "<p>staged HTML content</p>",
  "discussion_type": "threaded",
  "require_initial_post": true,
  "published": false,
  "assignment": {
    "name": "Discussion N: [Title]",
    "points_possible": 25,
    "due_at": "2026-03-15T23:59:00-07:00",
    "lock_at": "2026-03-17T23:59:00-07:00",
    "assignment_group_id": <id>,
    "submission_types": ["discussion_topic"]
  }
}
```

**Important:** The nested `assignment` object creates a graded discussion. Dates, points, and assignment group go HERE — not on the topic itself. Only include date/group fields when the user provides them.

**After creation:**
1. Attach rubric using the rubric integration steps below (GET assignment_id from the created topic, then POST rubric with association)
2. Verify via `python3 scripts/post_write_verify.py --type discussion --id <topic_id>`
3. Provide Canvas link

### Output
The skill produces:
1. Complete discussion prompt with scenario, requirements, and rubric reference
2. Canvas setup configuration (points, due dates, post-first settings enabled)
3. Objective alignment map (referencing blueprint objective IDs)
4. Suggested grading notes for instructor
5. 2-3 example "strong response" descriptions to help calibrate expectations

---

## Mode 2: Edit Discussion Settings

For changing settings on an existing discussion. **Skip the generation questionnaire.**

### Step 1: Identify the discussion
```
GET /api/v1/courses/:course_id/discussion_topics?search_term=<query>&per_page=20
```

### Step 2: Display current settings

Fetch the topic and its linked assignment (if graded):
```
GET /api/v1/courses/:course_id/discussion_topics/:topic_id
```

If `assignment_id` exists, also fetch:
```
GET /api/v1/courses/:course_id/assignments/:assignment_id
```

Show combined settings:
| Field | Current Value | Lives On |
|---|---|---|
| Title | Discussion 3: Debate | Topic |
| Discussion type | threaded | Topic |
| Require initial post | true | Topic |
| Published | true | Topic |
| Pinned | false | Topic |
| Points | 25 | Assignment |
| Due date | 2026-03-15T23:59:00-07:00 | Assignment |
| Available from | (not set) | Assignment |
| Available until | (not set) | Assignment |
| Assignment group | Discussions (id: 12345) | Assignment |
| Rubric | Yes (3 criteria) | Assignment |

### Step 3: Apply edits

**Topic-level settings** — PUT on the discussion topic:
```
PUT /api/v1/courses/:course_id/discussion_topics/:topic_id
Body: { <only changed fields> }
```

| Field | API Parameter | Target |
|---|---|---|
| Title | `title` | Topic |
| Require initial post | `require_initial_post` | Topic |
| Discussion type | `discussion_type` | Topic (threaded / side_comment) |
| Published | `published` | Topic |
| Pinned | `pinned` | Topic |
| Locked | `locked` | Topic |

**Grading settings** — PUT on the linked assignment:
```
PUT /api/v1/courses/:course_id/assignments/:assignment_id
Body: { "assignment": { <only changed fields> } }
```

| Field | API Parameter | Target |
|---|---|---|
| Points | `assignment[points_possible]` | Assignment |
| Due date | `assignment[due_at]` | Assignment (-07:00 for AZ) |
| Available from | `assignment[unlock_at]` | Assignment |
| Available until | `assignment[lock_at]` | Assignment |
| Assignment group | `assignment[assignment_group_id]` | Assignment |
| Grading type | `assignment[grading_type]` | Assignment |

**Warning:** Do NOT PUT dates or points on the discussion topic — they won't work. Always target the linked assignment for grading fields.

Confirm with the user before pushing. Verify via `post_write_verify.py --type discussion --id <topic_id>`.

---

## Mode 3: Edit Discussion Prompt (Body)

For rewriting or fixing the discussion prompt text. Uses the staging workflow.

### Step 1: Fetch current prompt
```
GET /api/v1/courses/:course_id/discussion_topics/:topic_id
```
The body is in the `message` field (not `description`).

### Step 2: Edit and stage
1. Apply the requested changes to the HTML
2. Save to `staging/discussion-{slug}.html`
3. Run `python3 scripts/unified_preview.py` → screenshot in conversation
4. Wait for user approval

### Step 3: Push
```bash
python3 scripts/push_to_canvas.py --type discussion --id <topic_id> --html-file staging/discussion-{slug}.html
```

### Step 4: Verify
```bash
python3 scripts/post_write_verify.py --type discussion --id <topic_id>
```

---

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

