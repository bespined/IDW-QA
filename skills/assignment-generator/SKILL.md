---
name: assignment-generator
description: "Create applied assignments with rubrics for a Canvas module."
---

# Assignment Generation Skill (Create an Artifact)

> **Plugin**: ASU Canvas Course Builder
> **References**: syllabus-generator/SKILL.md (for objective alignment), rubric-creator/SKILL.md (for rubric generation)

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python scripts/idw_metrics.py --track skill_invoked --context '{"skill": "assignment-generator"}'
```
This records usage metrics for the pilot dashboard. Do not skip this step.

## Purpose
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

Before generating any assignment, **always confirm these parameters with the user**:

> **1. Assignment type** — "Which type fits this module?"
>
> | Type | Best For | Example |
> |---|---|---|
> | **Case Analysis** | Professional/clinical connections — analyze a real-world scenario | "Analyze this forensic case using signal detection theory" |
> | **Concept Map** | Complex interconnected concepts — visualize relationships | "Map the relationships between cognitive bias types" |
> | **Calculation Problem Set** | Quantitative modules — apply formulas to real problems | "Calculate reliability metrics for this forensic lab" |
> | **Comparison/Contrast** | Parallel systems or approaches — structured analysis | "Compare adversarial vs. inquisitorial expert testimony models" |
>
> **2. Points** — "30 points is our default. Does this fit your grading scheme?"
>
> **3. Word count** — "400-600 words is standard. Need more or less for this module?"
>
> **4. Rubric structure** — "3 criteria × 10 pts each (default), or different?"
>
> | Points | Typical Rubric | Use Case |
> |---|---|---|
> | 30 pts | 3 criteria × 10 pts | Standard module assignment |
> | 50 pts | 4 criteria (15/15/10/10) | Heavier module or midpoint assignment |
> | 100 pts | 5 criteria (25/25/20/15/15) | Final project or capstone |
>
> **5. Submission type** — "Text entry, file upload, or both?" (default: both)

If the user specifies "assignments for all modules," ask these once for the batch and apply consistently, noting any per-module overrides.

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

### Step 5: Push Assignment + Rubric to Canvas

**Create or update the assignment:**
```
POST /api/v1/courses/:course_id/assignments
Body: {
  "assignment": {
    "name": "Module N: Create an Artifact — [Title]",
    "description": "<p>...</p>",
    "points_possible": 30,
    "submission_types": ["online_text_entry", "online_upload"],
    "published": false
  }
}
```

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

## Preview

After pushing the assignment to Canvas, offer: "Want me to preview this on Canvas? I can screenshot how it looks in the browser." If the user accepts, run the `/canvas-preview` workflow using the assignment URL returned by the Canvas API.
