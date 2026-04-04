---
name: update-module
description: "Add, replace, or rearrange content within an existing module."
---

# Update Module Skill

> **Plugin**: ASU Canvas Course Builder
> **Run**: `/update-module`
> **Invokes**: quiz, assignment-generator, discussion-generator, rubric-creator, interactive-content, media-upload

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python scripts/idw_metrics.py --track skill_invoked --context '{"skill": "update-module"}'
```
This records usage metrics for the pilot dashboard. Do not skip this step.

## Purpose

Make targeted changes to a single module that has already been built in Canvas. This is the **post-build editing tool** — use it when:

- A module needs a new or revised assessment
- Page content needs updating (new resources, corrected content, updated media)
- Interactive activities need to be added, replaced, or reordered
- A rubric needs revising
- Media (audio primer or lecture video) needs re-embedding
- Module items need reordering

This skill operates on **one module at a time** and preserves all existing Canvas IDs (pages, assignments, quizzes, discussions) unless explicitly replacing them.

## Prerequisites

- Canvas API credentials configured (`.env` exists)
- `course-config.json` exists in the working directory
- The target module has already been created in Canvas (via `/course-build` or manually)

---

## Step 1: Identify the Module

Show the live course tree via `python scripts/course_navigator.py --json` so the user can see all modules and their contents:

```
Course: BIO 101 (canvas.asu.edu)

+ Module 0: Getting Started
    [P] Welcome [welcome]
    [P] Syllabus [syllabus]
+ Module 1: Homeostasis
    [P] Module 1 Overview [m1-overview]
    [Q] Knowledge Check 1
    ...
+ Module 2: Body Fluids, Transport & Gradients
    ...
```

Ask: "Which module would you like to update?"

Accept any of:
- Module number: `3`, `M3`, `Module 3`
- Module title: `"Membranes & Excitability"`
- Canvas module ID: `2872310`

Resolve the module number, then fetch the current module state from Canvas:
- `GET /api/v1/courses/{id}/modules/{module_id}/items` — current module items
- Cross-reference with `course-config.json` for objectives and assessment details

---

## Step 2: Show Current State

Display the module's current contents:

```
Module 3: Membranes & Excitability

  Pages:
    1. Module Overview (m3-overview)
    2. Prepare to Learn (m3-prepare-to-learn)
    3. Lesson: Membranes & Excitability (m3-lesson-membranes)
    4. Knowledge Check 3 (m3-knowledge-check)
    5. Guided Practice 3 (m3-guided-practice)
    6. Create an Artifact 3 (m3-create-artifact)
    7. Conclusion & Next Steps (m3-conclusion)

  Assessments:
    - Knowledge Check: Quiz #1962366 (15 pts, 5 questions)
    - Guided Practice: Assignment #7258604 (10 pts)
    - Create an Artifact: Assignment #7258585 + Rubric #1284795 (30 pts)
    - Discussion: Topic #7430437 (25 pts)

  Media:
    - Audio primer: File #127948436 (embedded in Prepare to Learn)
    - Lecture video: File #127955569 (embedded in Lesson)

  Interactives:
    - AP Phase Sequencing (File #127967617, Guided Practice)
    - Dialog Cards (File #127967618, Prepare to Learn)
    - Nernst Fill-Blanks (File #127967619, Guided Practice)
```

---

## Step 3: What to Update

Ask: "What would you like to change?" and handle the following operations:

### Update Page Content

```
/update-module → update page → [page name or number]
```

- Fetch current page HTML from Canvas
- Show a summary of current content
- Ask what to change (add section, replace content, update resource links, etc.)
- **Stage the updated HTML** to `staging/{slug}.html` — do not push directly
- Show a preview screenshot of the staged page and wait for explicit approval
- Push only after the user approves

### Replace an Assessment

```
/update-module → replace assessment → [KC | artifact | discussion | GP]
```

- **Knowledge Check**: Invoke `/quiz-generator` with current module objectives. Creates a new quiz and replaces the old one in the module items.
- **Artifact**: Invoke `/assignment-generator` then `/rubric-creator`. Creates a new assignment+rubric and replaces the old one.
- **Discussion**: Invoke `/discussion-generator` then `/rubric-creator`. Creates a new discussion topic and replaces the old one.
- **Guided Practice**: Update the GP assignment description.

When replacing: offer to delete the old Canvas object or keep it as a backup (unpublished).

### Update a Rubric

```
/update-module → update rubric → [artifact | discussion]
```

- Fetch the current rubric from Canvas
- Show current criteria and descriptors
- Ask what to change (add/remove criterion, revise descriptors, adjust point distribution)
- Update via `PUT /api/v1/courses/{id}/rubrics/{rubric_id}`

### Add/Replace Interactive Activities

```
/update-module → add interactive → [type]
/update-module → replace interactive → [activity name]
```

- For **add**: Invoke `/interactive-content` to design the new activity, generate HTML, upload to Canvas, and embed in the target page
- For **replace**: Upload the new file, update the iframe `src` on the page, optionally delete the old file

### Update Media

```
/update-module → update media → [audio | video]
```

- For a new audio primer or lecture video:
  1. Guide user through generating the media content (NotebookLM or other tool)
  2. Upload new media file to Canvas via `/media-upload`
  3. Update the embed on the target page (Prepare to Learn or Lesson)
  5. Upload new VTT captions and update the expandable transcript

### Reorder Module Items

```
/update-module → reorder
```

- Show current item order with position numbers
- Ask which items to move (e.g., "move item 5 to position 3")
- Use `PUT /api/v1/courses/{id}/modules/{module_id}/items/{item_id}` with `position` parameter

### Add a New Page

```
/update-module → add page → [title]
```

- Create a new wiki page using the appropriate template
- Add it to the module at the specified position
- Populate with content

---

## Step 4: Verify Changes

After applying changes:

1. Re-fetch the module items from Canvas to confirm the update
2. If a page was modified, run a quick accessibility check on that page only
3. Show a summary of what changed:
   ```
   Changes applied to Module 3:
     ✓ Knowledge Check quiz replaced (old: #1962366 → new: #1962374)
     ✓ 5 new questions created
     ✓ Module item updated to point to new quiz
     ✓ Knowledge Check page button URL updated
   ```

---

## Safety Features

### Non-Destructive by Default
- When replacing an assessment, the old Canvas object is **unpublished but not deleted** by default
- The user must explicitly confirm deletion of old objects
- Page updates can be previewed before pushing

### Alignment Check
- When replacing an assessment, verify the new version still aligns with module objectives from `course-config.json`
- Warn if point totals change (affects grading weights)
- Warn if a rubric criterion no longer maps to a module objective

### Config Sync
- After changes, prompt the user to update `course-config.json` if the module structure has changed
- Specifically: new assessment types, changed point values, added/removed pages

---

## Output

The skill produces:
1. Updated Canvas module with requested changes applied
2. Change log (what was modified, old → new IDs)
3. Alignment verification (objectives still covered)
4. Reminder to update `course-config.json` if structural changes were made

## Post-Push Verification (Required)

After applying any update to Canvas, always:

1. **Provide a direct Canvas link** to the modified item:
   - Pages: `https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/pages/{slug}`
   - Quizzes: `https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/quizzes/{id}`
   - Assignments: `https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/assignments/{id}`
   - Discussions: `https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/discussion_topics/{id}`
   - Modules: `https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/modules`
2. **Auto-verify** by re-fetching the updated object from the Canvas API and confirming the change is reflected.
3. **Take a screenshot**: Navigate to the Canvas URL and capture the updated item — do not make this optional. Show it to the user.

---

## Remediation Event Recording

When this skill fixes an issue that was flagged from an audit finding, record the remediation event so the FindingCard shows the fix history. **This step is required when the fix originated from the fix queue.**

After successfully pushing the fix to Canvas, run:

```bash
python3 scripts/remediation_tracker.py --record --finding-ids <FINDING_ID> --skill update-module --description "<WHAT_WAS_FIXED>"
```

This:
1. Records a `remediation_events` row in Supabase
2. Clears the `remediation_requested` flag on the finding
3. The FindingCard in Vercel will show "Remediated via /update-module (Name, Date)"

If the fix was NOT from the fix queue (e.g., user asked to update content unprompted), skip this step.
