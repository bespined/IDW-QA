---
name: interactive-content
description: "Build interactive HTML learning activities for Canvas pages."
---

# Interactive Content Creation Skill

> **Plugin**: ASU Canvas Course Builder
> **Scripts**: `scripts/generator.py` (generates HTML), `scripts/deploy_interactives.py` (uploads to Canvas)

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python scripts/idw_metrics.py --track skill_invoked --context '{"skill": "interactive-content"}'
```
This records usage metrics for the pilot dashboard. Do not skip this step.

## Purpose
Design interactive learning activities embedded throughout a course to:
- Provide **immediate formative feedback** during self-paced learning
- Support **retrieval practice** (more effective than re-reading)
- Make **abstract concepts** concrete through visual manipulation
- Offer **applied reasoning practice** via branching decision scenarios
- Reduce cognitive load by **segmenting** complex topics into interactive chunks

Interactive content is NOT for the sake of interactivity — every activity must serve a specific learning objective and be the right tool for that objective (not just the most impressive one).

## Pre-Generation Prompt — Activity Configuration

Before generating any interactive activity, **always confirm these parameters with the user**:

> **1. Activity type** — "Which type fits this module's learning objectives?"
>
> | Type | Best For | Placement | Time |
> |---|---|---|---|
> | **Dialog Cards** | Vocabulary / key terms primer | Prepare to Learn | 2-3 min |
> | **Sequencing** | Process steps / ordering | Guided Practice | 3-5 min |
> | **Fill in the Blanks** | Equations / definitions / processes | Guided Practice | 3-5 min |
> | **Branching Scenario** | Applied reasoning / decision-making | Guided Practice | 3-5 min |
> | **Review Quiz** | Mixed-format concept review | Guided Practice or Conclusion | 3-5 min |
> | **Custom** | Anything else — describe what you want | Any page | Varies |
>
> **2. How many activities for this module?** — "1-2 is typical. Max 4 per module to avoid cognitive overload."
>
> **3. Placement page** — "Guided Practice is the default. Dialog Cards go on Prepare to Learn. Override?"
>
> **4. Content scope** — "Which concepts or terms should the activity cover? (I'll pull from module objectives if you're not sure.)"

If the user specifies "interactives for all modules," ask these once for the batch, recommend a per-module activity plan, and confirm before generating. Example plan:

> | Module | Activity 1 | Activity 2 |
> |---|---|---|
> | M1 | Dialog Cards (key terms) | Sequencing (intro process) |
> | M2 | Dialog Cards (key terms) | Branching Scenario (case) |
> | M3 | Fill in the Blanks (equations) | Review Quiz |
> | ... | ... | ... |

---

## Deployment Paths

### Path 1: Built-in HTML Generator → Canvas iframe (Primary)
- **Use for**: Dialog Cards, Sequencing, Fill-in-the-Blanks, Branching Scenarios, Review Quizzes
- **Output**: Self-contained HTML/CSS/JS files (no external dependencies)
- **Cost**: Free
- **Gradebook**: No passback (formative only — graded items use Canvas quizzes/assignments)
- **Workflow**:
  1. Define content in a Python data file (see `scripts/generator.py`)
  2. Run: `python scripts/generator.py <content_data.py> --output-dir ./output`
  3. Upload to Canvas: `python scripts/deploy_interactives.py <content_data.py> --output-dir ./output`
  4. Activities are embedded as iframes in Canvas pages

### Path 2: Custom HTML Activity → Canvas iframe
- **Use for**: Any activity type not covered by the 5 built-in types — custom interactions designed by Claude based on your description
- **Output**: Self-contained HTML/CSS/JS file with ASU branding and WCAG compliance
- **Cost**: Free
- **Workflow**: Describe what you want → Claude generates the HTML → Upload to Canvas Files → Embed via iframe
- **See**: Custom Activity Mode section below

### Path 3: External Embeds (Simulations, Interactive Videos)
- **Use for**: PhET simulations, PlayPosit interactive videos, Lumi (H5P exports), discipline-specific tools
- **Cost**: Varies (PhET is free; Lumi is free; PlayPosit may require institutional license)
- **Workflow**: Create externally → Export as HTML or get embed URL → Upload/embed via iframe

### Canvas iframe Template
```html
<iframe src="/courses/[COURSE_ID]/files/[FILE_ID]/preview"
        width="100%" height="600"
        style="border: 1px solid #ccc; border-radius: 8px;"
        sandbox="allow-same-origin allow-scripts allow-forms"
        title="[Activity Title]"
        loading="lazy">
</iframe>
```

## Built-in Activity Types (Python Generator)

The `scripts/generator.py` produces self-contained HTML files for 5 activity types:

### 1. Dialog Cards (Vocabulary Primer)
- Front: Term or concept name
- Back: Definition + one-sentence applied relevance
- 5-8 cards per module
- **Placement**: Prepare to Learn page
- **Estimated time**: 2-3 minutes
- **iframe height**: 550px

### 2. Sequencing (Process Ordering)
- Arrange steps/stages in correct order via drag-and-drop
- 4-8 items per activity
- **Placement**: Guided Practice page
- **Estimated time**: 3-5 minutes
- **iframe height**: 650px

### 3. Fill in the Blanks (Concept Completion)
- Cloze-style completion of key equations, definitions, or process descriptions
- Includes feedback explaining each blank
- **Placement**: Guided Practice page
- **Estimated time**: 3-5 minutes
- **iframe height**: 600px

### 4. Branching Scenario (Applied Reasoning)
- 2-3 decision points with consequence-based branching
- Each branch leads to an explained outcome
- End screens show score and explain the optimal path
- **Placement**: Guided Practice page
- **Estimated time**: 3-5 minutes
- **iframe height**: 700px

### 5. Review Quiz (Mixed-format Review)
- 3-5 questions (multiple choice, true/false)
- Different from the graded Knowledge Check — this is ungraded practice
- **Placement**: Guided Practice or Conclusion page
- **Estimated time**: 3-5 minutes
- **iframe height**: 650px

## Design Principles

### 1. Match Interaction to Learning Objective
Do NOT default to the most complex interaction type. Use the simplest interaction that achieves the objective:

| Learning Goal | Best Interaction | Why |
|---|---|---|
| Term recognition | Dialog Cards | Low motor load, high retrieval |
| Equation/process completion | Fill in the Blanks | Practices recall of components |
| Sequence ordering | Sequencing | Tests understanding of process steps |
| Applied reasoning | Branching Scenario | Decision-making with consequences |
| Concept review | Review Quiz | Mixed formats in one container |
| Spatial identification | Image Hotspots (custom HTML or Lumi) | Click-based (lower load than drag-and-drop) |
| Diagram labeling | Label a Diagram (custom HTML or Lumi) | Only when spatial reasoning IS the objective |

### 2. Cognitive Load Management
Research shows that high motor complexity (e.g., multi-zone drag-and-drop) can **impair** transfer learning by consuming working memory. Design rules:
- **Prefer click-based over drag-based** interactions for concept tasks
- **Limit to 2-4 activities per module** (more creates fatigue)
- **Keep branching scenarios to 2-3 decision nodes**
- **Remove decorative elements** — every element must serve the learning objective

### 3. Feedback Design
Immediate corrective feedback is the primary mechanism by which interactive content improves learning:
- **Correct answer feedback**: Explain WHY it's correct (reinforce the mechanism)
- **Incorrect answer feedback**: Address the specific misconception, not just "Try again"
- **Enable retry** for all formative activities
- **Show solution** after final attempt so students can self-correct

### 4. Mayer's Multimedia Principles Applied
| Principle | Application |
|---|---|
| Multimedia | Always pair diagrams with text for spatial concepts |
| Signaling | Use arrows, color coding, and markers to direct attention |
| Segmenting | Break content into small interactive chunks |
| Coherence | Remove decorative elements; everything serves learning |
| Contiguity | Place explanations adjacent to the element they describe |
| Pretraining | Dialog Cards with key terms BEFORE complex interactions |

### 5. Placement Within Module Structure
Each module has 7 items. Interactive content should be embedded WITHIN existing pages, not as separate module items:

| Module Page | Interactive Content |
|---|---|
| **Overview** | Optional: confidence self-rating |
| **Prepare to Learn** | Dialog Cards (5-8 key terms) |
| **Lesson** | Optional: interactive video or simulation embed |
| **Knowledge Check** | Already a Canvas quiz; no additional activities needed |
| **Guided Practice** | 1-2 activities (sequencing, fill-blanks, or branching) — the core opportunity |
| **Create an Artifact** | No activities — this is a graded student-produced artifact |
| **Conclusion** | Optional: quick review quiz |

**The Guided Practice page is the primary home for interactive content.**

## Activity Specification Format

When designing an interactive activity, produce this specification:

```
## Interactive Activity Specification

### Metadata
- **Activity Name**: [descriptive name]
- **Activity Type**: [Dialog Cards / Sequencing / Fill in Blanks / Branching / Quiz]
- **Module**: M[#] — [title]
- **Placement**: [which page it embeds in]
- **Learning Objective(s)**: [M#.# objectives assessed]
- **Estimated Time**: [1-5 minutes]

### Content

**For Dialog Cards:**
- Card 1 Front: [term] → Back: [definition + applied relevance]
- Card 2 Front: [...] → Back: [...]

**For Sequencing:**
- Items in correct order:
  1. [first step]
  2. [second step]
  3. ...
- Feedback for correct/incorrect completion

**For Fill in the Blanks:**
- Text with *blanks* marked: "The [process] is primarily determined by *[answer]*..."
- Acceptable answers for each blank
- Feedback per blank

**For Branching Scenario:**
- Starting scenario: [description]
- Decision 1: [question] → Option A: [consequence] → Option B: [consequence]
- Decision 2: [question] → ...
- End screens: [summary feedback for each path]

**For Review Quiz:**
- Q1: [question] | Type: [MC/TF] | Correct: [answer] | Distractors: [...] | Feedback: [...]

### Canvas Integration
- Upload to: Canvas Files → /[folder]/M[#]/[filename].html
- Embed in page: [page slug]
- iframe height: [recommended px]
```

## Content Data File Format

The Python generator expects a content data file with this structure:

```python
ALL_ACTIVITIES = {
    "m1": [
        {
            "type": "dialog_cards",
            "title": "Module 1 Key Terms",
            "filename": "m1-dialog-cards.html",
            "page_slug": "m1-prepare-to-learn",
            "page_type": "prepare",
            "cards": [
                {"front": "Term", "back": "Definition + relevance"},
                ...
            ]
        },
        {
            "type": "sequencing",
            "title": "Process Steps",
            "filename": "m1-sequencing.html",
            "page_slug": "m1-guided-practice",
            "page_type": "guided",
            "items": ["Step 1", "Step 2", "Step 3", ...],
            "feedback_correct": "Correct! ...",
            "feedback_incorrect": "Not quite. ..."
        },
        ...
    ],
    "m2": [...],
}
```

## Custom Activity Mode

When the 5 built-in types don't fit the learning objective, Claude can generate a custom interactive HTML activity from scratch. This is an open-ended mode — describe what you want, and Claude will build it.

### When to Use Custom Mode
- The learning objective requires an interaction pattern not covered by dialog cards, sequencing, fill-blanks, branching, or quiz
- You want a unique experience (e.g., a drag-to-label diagram, a matching exercise, a timeline builder, a decision matrix)
- You have a specific pedagogical idea that doesn't fit the built-in templates

### How to Invoke
Ask Claude to create a custom interactive activity. Provide:
1. **Module and placement** — which module and page it goes on
2. **Learning objective(s)** — what the student should practice or demonstrate
3. **Interaction description** — what the student does (e.g., "drag labels onto a diagram," "sort items into categories," "build a timeline")
4. **Content** — the actual terms, scenarios, questions, or data to include

### What Claude Generates
A single self-contained HTML file that:
- **Works standalone** — all HTML, CSS, and JavaScript in one file (no external dependencies)
- **Embeds via iframe** — uses the standard Canvas iframe template (see above)
- **Follows ASU branding** — Maroon (#8C1D40) and Gold (#FFC627) color scheme
- **Meets WCAG 2.1 AA** — keyboard navigable, proper ARIA labels, sufficient contrast, screen-reader compatible
- **Provides feedback** — immediate corrective feedback with explanations
- **Is mobile-friendly** — responsive layout, touch-friendly targets (≥44px)
- **Includes a progress indicator** — shows completion state

### Canvas Integration Requirements
All custom activities must follow these Canvas iframe constraints:
- **Sandbox attribute**: `sandbox="allow-same-origin allow-scripts allow-forms"` — activities cannot access parent page DOM, open popups, or navigate the parent frame
- **No external requests**: All assets (fonts, images, icons) must be inline or data-URI encoded
- **Recommended iframe heights**: 550-700px depending on content density
- **File size**: Keep under 500KB (inline assets add up quickly)
- **Title attribute**: Every iframe needs a descriptive `title` for screen readers

### Example Custom Activities
| Idea | Description | Good For |
|---|---|---|
| Category Sort | Drag items into 2-3 labeled columns | Classification tasks |
| Label a Diagram | Click regions of an SVG to identify structures | Anatomy, systems diagrams |
| Timeline Builder | Arrange events chronologically on a visual timeline | Historical processes, pathways |
| Matching Exercise | Connect items from two columns | Term-definition, cause-effect |
| Decision Matrix | Fill in a matrix comparing options across criteria | Evaluation, comparison |
| Concept Checker | Multi-step guided walkthrough with embedded questions | Complex procedures |

### Quality Standards for Custom Activities
Custom activities follow the same design principles and quality checklist as built-in types — see below.

---

## Quality Checklist
Before finalizing any interactive activity:
- [ ] Does this activity assess or reinforce a specific learning objective?
- [ ] Is this the simplest interaction type that achieves the goal?
- [ ] Would removing this activity reduce learning outcomes? (If not, cut it)
- [ ] Is feedback explanatory (not just "correct/incorrect")?
- [ ] Does the activity take ≤5 minutes to complete?
- [ ] Is retry enabled for formative activities?
- [ ] Does the activity avoid excessive motor demands?
- [ ] Is the total interactive content for this module ≤4 activities?

## Output
When invoked, the skill produces:
1. Complete activity specification following the format above
2. Content for the activity (terms, scenarios, questions, etc.)
3. Feedback text for all correct and incorrect responses
4. Canvas page integration instructions (where to embed, iframe code)
5. Alignment to specific module learning objectives

## Error Handling

| Error | User Message | Recovery |
|-------|-------------|----------|
| No course-config.json | "I need course context first. Let me create a config from your course." | Auto-create minimal config |
| Missing module objectives | "Module {N} doesn't have objectives defined yet. Let's add them before creating the interactive." | Guide objective creation |
| Push fails | "The interactive push failed but your content is saved in staging/. Let's try again." | Retry |
| Canvas API 401/403 | "Authentication issue — check your Canvas token and course permissions." | Guide re-auth |
| Read-only mode | "Read-only mode is active. The interactive is staged locally but can't be pushed until writes are enabled." | Guide .env change |
| deploy_interactives.py error | "The interactive deployment script hit an issue. Your HTML is saved locally. Let me try a different injection approach." | Use fallback chain |

## Post-Push Verification (Required)

After deploying an interactive activity to Canvas, always:

1. **Fetch and confirm** the page it was embedded in via `GET /api/v1/courses/:id/pages/:slug` and verify the iframe is present in the body HTML.
2. **Provide the direct Canvas link**: `https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/pages/{slug}`
3. **Take a screenshot**: Navigate to the page in Canvas and capture a screenshot to confirm the interactive renders correctly — do not skip this step. Show it to the user as proof the embed worked.


## Remediation Event Recording

When this skill fixes an issue that was flagged from an audit finding, record the remediation event so the FindingCard shows the fix history. **This step is required when the fix originated from the fix queue.**

After successfully pushing the fix to Canvas, run:

```bash
python3 scripts/remediation_tracker.py --record --finding-ids <FINDING_ID> --skill interactive-content --description "<WHAT_WAS_FIXED>"
```

This:
1. Records a `remediation_events` row in Supabase
2. Clears the `remediation_requested` flag on the finding
3. The FindingCard in Vercel will show "Remediated via /<skill> (Name, Date)"

If the fix was NOT from the fix queue (e.g., user asked to create something new), skip this step.

