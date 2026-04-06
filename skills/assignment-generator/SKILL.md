---
name: assignment-generator
description: "Create or edit assignments — full generation or quick metadata edits (points, dates, groups, attempts)."
---

# Assignment Skill (Create or Edit)

> **Plugin**: ASU Canvas Course Builder
> **References**: syllabus-generator/SKILL.md (for objective alignment), rubric-creator/SKILL.md (for rubric generation)

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python scripts/idw_metrics.py --track skill_invoked --context '{"skill": "assignment-generator"}'
```
This records usage metrics for the pilot dashboard. Do not skip this step.

## When to Use — Mode Routing

Route to the correct mode based on the user's request:

| User says... | Mode |
|---|---|
| "Create an assignment for Module 4" / "Generate artifact" | **Mode 1: Create** (full generation flow) |
| "Change points on the M3 assignment to 50" / "Set due date" | **Mode 2: Edit Metadata** (fast-path, no generation) |
| "Fix the instructions on the Module 5 assignment" | **Mode 2: Edit Description** (staging workflow) |
| "Move assignment to Homework group" / "Change to 3 attempts" | **Mode 2: Edit Metadata** (fast-path) |

**Fast-path rule:** If the user asks for a narrow metadata change, skip the generation questionnaire entirely and go straight to Mode 2.

---

## Mode 1: Create Assignment

### Purpose
Generate a ~20 minute "Create an Artifact" assignment for each module. These are the primary graded assignments in each module. They serve to:
- Require students to **apply and synthesize** module concepts (not just recall)
- Develop professional reasoning and scientific communication skills
- Create a tangible artifact that demonstrates understanding
- Prepare students for discipline-specific assessment formats

## Required Inputs

| Input | Source |
|---|---|
| Module number and title | Course blueprint |
| Module learning objectives | Course blueprint |
| Assessment-to-Objective alignment | Course blueprint alignment matrix |
| Assignment type recommendation | Based on module content (see types below) |
| Professional/clinical context | Discipline-specific scenarios |
| Prior module connections | For cross-module integration component |

## Pre-Generation Prompt — Assignment Configuration

Before generating any assignment, **always walk through these questions with the user** using `AskUserQuestion`. Ask them in order — each answer shapes the next question.

### Question 1: Assignment Format

> "What type of assignment is this?"

| Label | Description |
|---|---|
| **Video assignment** | Students record and submit a video (presentation, demonstration, reflection) |
| **Written assignment** | Students write and submit a document (analysis, report, problem set) |
| **Discussion** | Students post and respond to peers in a threaded discussion → *Route to `skills/discussion-generator/SKILL.md` instead — discussions are a separate skill with their own prompt types and peer interaction model.* |

If the user picks **Discussion**, hand off to the discussion-generator skill seamlessly. Do not generate a discussion as an assignment.

### Question 2: Bloom's Complexity Level

> "What cognitive complexity level should this assignment target?"

| Label | Description |
|---|---|
| **Remember (Level 1)** | Recall facts, dates, definitions. *Rarely appropriate for graded assignments — suggest a higher level.* |
| **Understand (Level 2)** | Explain concepts, summarize, compare at a basic level. |
| **Apply (Level 3)** | Use knowledge in new situations — solve problems, demonstrate, implement. |
| **Analyze (Level 4)** | Break down information, find patterns, explain relationships and causes. |
| **Evaluate (Level 5)** | Judge, assess, critique, defend a position with evidence. |
| **Create (Level 6)** | Design, build, propose something new by synthesizing knowledge. |

**Default recommendation**: Level 3 (Apply) for early modules, Level 4-5 for mid/late modules. Always suggest a level based on where the module sits in the course, but let the user override.

The selected Bloom's level directly shapes the assignment instructions:
- **Level 1-2**: Structured prompts, recall-focused tasks (flag as potentially too low for graded work)
- **Level 3**: Application scenarios — "use X to solve Y," demonstrations, implementations
- **Level 4**: Analysis tasks — "break down," "compare," "explain why," cause-effect chains
- **Level 5**: Evaluation tasks — "assess," "critique," "defend," evidence-based arguments
- **Level 6**: Creation tasks — "design," "propose," "build," original artifacts

### Question 3: Assignment Subtype

**For Video assignments:**

| Label | Description |
|---|---|
| **Presentation** | Student presents analysis or findings (with slides or visuals) |
| **Demonstration** | Student demonstrates a skill, process, or technique |
| **Reflection** | Student reflects on learning, connects to experience |
| **Explainer** | Student explains a concept as if teaching it to someone else |

**For Written assignments:**

| Label | Description |
|---|---|
| **Case Analysis** | Analyze a real-world scenario using module concepts |
| **Concept Map** | Visualize relationships between interconnected concepts |
| **Calculation Problem Set** | Apply formulas/quantitative reasoning to real problems |
| **Comparison/Contrast** | Structured analysis of parallel systems or approaches |

### Question 4: Points, Word Count, Rubric

> **Points** — "30 points is our default. Does this fit your grading scheme?"
>
> **Word count / Video length** — "400-600 words (or 3-5 min video) is standard. Need more or less?"
>
> **Rubric structure** — "3 criteria × 10 pts each (default), or different?"
>
> | Points | Typical Rubric | Use Case |
> |---|---|---|
> | 30 pts | 3 criteria × 10 pts | Standard module assignment |
> | 50 pts | 4 criteria (15/15/10/10) | Heavier module or midpoint assignment |
> | 100 pts | 5 criteria (25/25/20/15/15) | Final project or capstone |
>
> **Submission type** — "Text entry, file upload, media recording, or combination?" (default: file upload for video, text + upload for written)

### Question 5: Page Design

> "Should the assignment description use the ASU page design system (styled HTML with callout boxes, colored sections), or plain HTML?"

| Label | Description |
|---|---|
| **Plain HTML** | Clean, unstyled HTML — standard for assignment descriptions that go into the Canvas assignment body. **(Default)** |
| **Styled (Page Design System)** | Uses the ASU page design system from `standards/page-design.md` — appropriate when the assignment has its own Canvas wiki page |

**Default is plain HTML.** Only use the page design system when the user explicitly requests styled output or the assignment lives on a standalone Canvas page (not an assignment description field).

If the user specifies "assignments for all modules," ask these once for the batch and apply consistently, noting any per-module overrides.

---

## Instruction Quality Requirements

**Every generated assignment MUST include all of the following sections.** Thin or vague instructions are not acceptable — the goal is for a student to read the instructions and know exactly what success looks like.

### Required Sections in Assignment Instructions

1. **Context / Hook** (1-2 paragraphs)
   - Set the scene: why does this topic matter in the real world or in their discipline?
   - Connect to current events, professional scenarios, or personal relevance
   - Engage the student — don't just state the task cold

2. **Task Description** (1-2 paragraphs)
   - Clearly state what the student must do, using verbs matched to the Bloom's level
   - Be explicit about scope: what to include and what NOT to include
   - Reference specific module concepts, readings, or videos they should draw from

3. **Deliverable Checklist** ("Your Submission Should Include:")
   - Bulleted list of every required component
   - Word counts, video lengths, format requirements
   - Required references, diagrams, or supporting evidence
   - For video: presentation quality expectations (lighting, audio, slides if applicable)

4. **Peer Interaction Expectations** (if applicable — especially for video assignments)
   - How many peer responses are required
   - What constitutes a substantive response (not just "great job")
   - Specific prompts for peer feedback (e.g., "identify one strength and one area for deeper analysis")

5. **Success Criteria** ("How You'll Be Evaluated:")
   - Brief summary of rubric criteria in plain language
   - What distinguishes excellent from adequate work
   - Common pitfalls to avoid

6. **Closing Motivation** (1-2 sentences)
   - Tie back to why this matters — professional growth, skill building, or real-world application

---

## Assignment Parameters (ASU Canvas Standards)

| Setting | Default | Notes |
|---|---|---|
| **Points** | 30 | User confirms or overrides |
| **Time** | ~20 minutes | Scales with points |
| **Submission type** | Online (text + upload) | User can narrow |
| **Rubric** | 3 criteria × 10 pts | User confirms criteria count |
| **Due date** | End of module period | Instructor sets specific date |
| **Word count** | 400-600 words | User confirms or overrides |

## Assignment Types

### Type 1: Case Analysis
**Best for**: Modules with strong professional/clinical connections
- Present a real-world or clinical scenario with relevant data
- Students analyze the underlying mechanisms using module concepts
- Must trace cause-effect chains from foundational principles to observable outcomes
- Often includes "what would happen if..." prediction questions

**When to use**: When the module's concepts directly explain a professional situation, patient presentation, engineering failure, or policy outcome.

**Structure:**
```
## Case Analysis: [Scenario description]
[2-3 paragraph scenario with relevant data, measurements, or observations]

### Your Task
1. Identify the primary mechanism(s) responsible for [specific observation/finding]
2. Trace the causal chain from [foundational concept] → [intermediate process] → [observable outcome]
3. Predict what would happen to [specific variable] if [intervention]. Explain your reasoning.
4. Connect this case to at least one concept from a previous module.

### Submission Requirements
- 400-600 words
- Use proper discipline-specific terminology
- Include at least one diagram, concept map, or flow chart
- Reference at least one course resource

### Grading
This assignment is worth 30 points. See the attached rubric.
```

### Type 2: Concept Map / Mechanism Diagram
**Best for**: Modules with complex interconnected concepts
- Students create a visual representation of concept relationships
- Must show directional cause-effect arrows with labeled explanations
- Connects module concepts to prior knowledge
- Can be hand-drawn (photo upload) or digital

**When to use**: When the key learning outcome is understanding relationships between multiple concepts, especially signaling cascades, system architectures, or process networks.

**Structure:**
```
## Concept Map: [Topic]

### Your Task
Create a comprehensive concept map that illustrates [specific topic/relationship].

Your map MUST include:
- [ ] All of the following key concepts: [list 6-8 specific terms/concepts]
- [ ] Directional arrows showing cause-effect relationships
- [ ] Brief labels on each arrow explaining the relationship
- [ ] At least one professional/clinical connection showing disruption → consequence
- [ ] At least one connection to a concept from a previous module

### Submission Requirements
- Submit as an image (photo of hand-drawn, or digital export)
- Include a brief written explanation (200-300 words) walking through the key pathway(s)
- Identify the single most important relationship and explain why

### Grading
This assignment is worth 30 points. See the attached rubric.
```

### Type 3: Calculation Problem Set
**Best for**: Quantitatively-focused modules
- Students solve 3-4 problems using module equations/relationships
- Each problem includes a real-world or professional context
- Must show work and explain reasoning (not just final answer)
- Builds quantitative reasoning skills

**When to use**: When the module includes equations, formulas, or quantitative relationships that students need to apply.

**Structure:**
```
## Problem Set: [Topic]

### Instructions
Solve each problem below. You MUST show your work and explain your reasoning — correct answers without explanation will receive partial credit only.

### Problem 1: [Title] (8 pts)
[Scenario with relevant data]
a) Calculate [specific value] using [equation]. Show your work.
b) Explain in 2-3 sentences what this result means practically.
c) Predict how [specific change] would affect your answer, and explain why.

### Problem 2: [Title] (8 pts)
[Similar structure with different application]

### Problem 3: [Title] (8 pts)
[Similar structure]

### Problem 4: Integration (6 pts)
[A question that connects quantitative reasoning across multiple concepts or to professional context]

### Submission Requirements
- Submit as a single document (typed or photographed handwritten work)
- Must show all calculations and unit conversions
- Must include written explanations for each part

### Grading
This assignment is worth 30 points. See the attached rubric.
```

### Type 4: Comparison/Contrast Analysis
**Best for**: Modules with parallel systems or approaches to compare
- Students create a structured comparison of related concepts or systems
- Must go beyond listing differences — explain WHY they differ
- Connects structural/foundational differences to functional/practical outcomes
- Can include tables plus narrative explanation

**When to use**: When the module covers multiple related but distinct systems, approaches, or frameworks that benefit from systematic comparison.

## Assignment Design Principles

### 1. Backward Design Alignment
Every assignment must:
- Directly assess 2-3 module learning objectives
- Require application or analysis (Bloom's Apply/Analyze/Evaluate)
- Connect to the module's professional/clinical themes
- Build on the lecture video content (the anchor)

### 2. Scaffolded Difficulty
Across modules, assignments should progressively increase in complexity:
- **Early modules**: More structured prompts, clearer scaffolding
- **Middle modules**: Moderate scaffolding, more open-ended components
- **Later modules**: Less scaffolding, more integration required, more independent reasoning

### 3. Authentic Professional Context
All assignments should feel relevant to professional practice:
- Use realistic scenarios (not abstract textbook problems)
- Include actual data, measurements, or case details
- Connect to situations students will encounter in their careers
- Value professional reasoning alongside conceptual accuracy

### 4. Clear Deliverables
Students must know exactly what to produce:
- Specify word count ranges
- List required components with checkboxes
- Clarify whether diagrams are required or optional
- State the submission format explicitly

## How to Generate an Assignment

### Step 1: Select Assignment Type
Based on the module content and the type guidance above.

### Step 2: Identify Objectives & Content
- List the 2-3 learning objectives this assignment assesses
- Identify the professional/clinical connection from the course blueprint
- Review the lecture video content strategy for this module
- Note which supplementary resources are relevant

### Step 3: Write the Assignment
Following the template for the selected type:
1. Write the scenario or task description
2. Create explicit deliverable requirements
3. Set word count/format expectations
4. Add the integration component (connection to prior modules)

### Step 4: Generate Rubric
Use the rubric-creator skill to create the attached rubric:
- 3 criteria × 10 points = 30 total (adjustable)
- Align criteria to the assignment's specific deliverables
- Customize descriptors for the assignment type

### Step 5: Stage, Preview, and Push Assignment

**Stage the assignment description HTML first — do NOT push directly to Canvas:**
1. Save the assignment description HTML to `staging/assignment-{slug}.html`
2. Run unified preview: `python3 scripts/unified_preview.py` → screenshot in conversation
3. Wait for user approval before pushing
4. After approval, push via `python3 scripts/push_to_canvas.py`

**Canvas API for creating the assignment (after staging approval):**
```
POST /api/v1/courses/:course_id/assignments
Body: {
  "assignment": {
    "name": "Module N: Create an Artifact — [Title]",
    "description": "<p>...</p>",
    "points_possible": 30,
    "submission_types": ["online_text_entry", "online_upload"],
    "published": false,
    "assignment_group_id": <id>,         // optional — lookup via GET /courses/:id/assignment_groups
    "grading_type": "points",            // points | percent | letter_grade | pass_fail | not_graded
    "allowed_attempts": -1,              // -1 = unlimited, or specific number
    "due_at": "2026-03-15T23:59:00-07:00",      // optional — Arizona, no DST = always -07:00
    "unlock_at": "2026-03-01T00:00:00-07:00",   // optional — available from
    "lock_at": "2026-03-17T23:59:00-07:00",     // optional — available until
    "omit_from_final_grade": false       // optional — exclude from total
  }
}
```

Only include optional fields when the user provides them or when `course-config.json` specifies defaults. Do not ask about every field — use sensible defaults (points grading, unlimited attempts, no dates unless specified).

**Attach the rubric in the same call or separately:**
```
POST /api/v1/courses/:course_id/rubrics
Body: {
  "rubric": {
    "title": "Assignment Rubric — Module N",
    "criteria": {
      "0": {
        "description": "Criterion 1 Name", "points": 10,
        "ratings": {
          "0": {"description": "Excellent", "points": 10},
          "1": {"description": "Proficient", "points": 7},
          "2": {"description": "Developing", "points": 4},
          "3": {"description": "Beginning", "points": 0}
        }
      },
      "1": { ... },
      "2": { ... }
    }
  },
  "rubric_association": {
    "association_type": "Assignment",
    "association_id": <assignment_id from POST above>,
    "use_for_grading": true,
    "purpose": "grading"
  }
}
```

**Important**: The `criteria` and `ratings` use a **dict-of-dicts format with string keys** ("0", "1", "2"), not arrays. This is a Canvas API requirement — arrays will silently fail and create a rubric with no criteria.

### Step 6: Format for Canvas
Output includes:
- Complete assignment instructions (HTML-ready)
- Attached rubric (via API, not just referenced)
- Canvas settings (points, submission type, due date logic)

## Intra-Module Alignment Check

Before generating an Artifact assignment, verify alignment with the other assessments in the same module:

1. **Reference the syllabus** (`syllabus-generator/SKILL.md`) for this module's objectives and the Assessment-to-Objective Alignment Matrix
2. **Review the module's Knowledge Check**: Which objectives does it assess? The Artifact should build on KC-assessed skills at a higher Bloom's level — the KC previews, the Artifact deepens
3. **Review the module's Discussion**: Which objectives does it extend? The Artifact and Discussion should assess different facets of the module — avoid having both test the exact same skill the same way
4. **Verify Bloom's level**: Artifact assignments should primarily target **Analyze** and **Evaluate** — above the KC (Apply/Analyze) and complementary to the Discussion (Evaluate/Create)
5. **Check the integration requirement**: For M2+, verify the cross-module connection component references a specific prior module
6. **Document alignment** in the output: list covered objectives by ID and note how the Artifact complements the KC and Discussion

## Output
The skill produces:
1. Complete assignment with instructions, scenario, and deliverables
2. Matching rubric (via rubric-creator skill)
3. Canvas setup configuration
4. Objective alignment map (using blueprint objective IDs)
5. Grading notes for the instructor
6. Intra-module alignment note explaining how the Artifact complements the KC and Discussion

## Error Handling

| Error | User Message | Recovery |
|-------|-------------|----------|
| No course-config.json | "I need course context first. Let me create a config from your course." | Auto-create minimal config |
| Missing module objectives | "Module {N} doesn't have objectives defined yet. Let's add them before creating the assignment." | Guide objective creation |
| Push fails | "The assignment push failed but your content is saved in staging/. Let's try again." | Retry |
| Canvas API 401/403 | "Authentication issue — check your Canvas token and course permissions." | Guide re-auth |
| Read-only mode | "Read-only mode is active. The assignment is staged locally but can't be pushed until writes are enabled." | Guide .env change |

---

## Mode 2: Edit Existing Assignment

For editing an existing assignment's metadata or description. **Skip the full generation questionnaire** — go straight to the edit.

### Step 1: Identify the assignment

Find the assignment by name search or user-provided ID:
```
GET /api/v1/courses/:course_id/assignments?search_term=<query>&per_page=20
```

### Step 2: Display current settings

Fetch the full assignment and display in a table:
```
GET /api/v1/courses/:course_id/assignments/:assignment_id
```

Show:
| Field | Current Value |
|---|---|
| Name | Module 3: Create an Artifact — Membrane Analysis |
| Points | 30 |
| Grading type | points |
| Submission types | online_text_entry, online_upload |
| Allowed attempts | -1 (unlimited) |
| Assignment group | Assignments (id: 12345) |
| Due date | 2026-03-15T23:59:00-07:00 |
| Available from | (not set) |
| Available until | (not set) |
| Published | false |
| Rubric | Yes (3 criteria) |
| Description | 2,400 chars |

### Step 3: Apply edits

**For metadata (points, dates, attempts, groups, grading type, submission types):**

Direct PUT — no staging required:
```
PUT /api/v1/courses/:course_id/assignments/:assignment_id
Body: {
  "assignment": {
    <only the fields being changed>
  }
}
```

Confirm with the user before pushing. Example: "I'll change points to 50 and set due date to March 20. Confirm?"

**Supported metadata fields:**

| Field | API Parameter | Notes |
|---|---|---|
| Points | `assignment[points_possible]` | |
| Due date | `assignment[due_at]` | ISO 8601, `-07:00` for Arizona |
| Available from | `assignment[unlock_at]` | |
| Available until | `assignment[lock_at]` | |
| Assignment group | `assignment[assignment_group_id]` | Lookup: `GET /courses/:id/assignment_groups` |
| Allowed attempts | `assignment[allowed_attempts]` | -1 = unlimited |
| Grading type | `assignment[grading_type]` | points / percent / letter_grade / pass_fail / not_graded |
| Submission types | `assignment[submission_types][]` | Array: online_text_entry, online_upload, online_url, etc. |
| Published | `assignment[published]` | |
| Omit from grade | `assignment[omit_from_final_grade]` | |

**For description (HTML body):**

Route through staging workflow:
1. Fetch current description: `GET /api/v1/courses/:id/assignments/:id` → `description` field
2. Apply edits to the HTML
3. Stage to `staging/assignment-{slug}.html`
4. Preview via `python3 scripts/unified_preview.py` → screenshot
5. After approval: `python3 scripts/push_to_canvas.py --type assignment --id <id> --html-file staging/assignment-{slug}.html`

### Step 4: Verify

Run `python3 scripts/post_write_verify.py --type assignment --id <assignment_id>` and display the result.

Provide the Canvas link: `https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/assignments/{id}`

---

## Post-Push Verification (Required)

After pushing the assignment to Canvas, always:

1. **Fetch and confirm** the created assignment via `GET /api/v1/courses/:id/assignments/:id` and display:
   - Assignment name, points, submission types, rubric attached (yes/no)
2. **Provide the direct Canvas link**: `https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/assignments/{id}`
3. **Offer a screenshot**: "Want me to screenshot how this looks in Canvas?" If yes, navigate to the Canvas URL and capture it.


## Remediation Event Recording

When this skill fixes an issue that was flagged from an audit finding, record the remediation event so the FindingCard shows the fix history. **This step is required when the fix originated from the fix queue.**

After successfully pushing the fix to Canvas, run:

```bash
python3 scripts/remediation_tracker.py --record --finding-ids <FINDING_ID> --skill assignment-generator --description "<WHAT_WAS_FIXED>"
```

This:
1. Records a `remediation_events` row in Supabase
2. Clears the `remediation_requested` flag on the finding
3. The FindingCard in Vercel will show "Remediated via /<skill> (Name, Date)"

If the fix was NOT from the fix queue (e.g., user asked to create something new), skip this step.

