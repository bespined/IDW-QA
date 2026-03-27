---
name: canvas-nav
description: "Browse your Canvas course structure — modules, pages, assignments, quizzes — without leaving the conversation."
---

# Canvas Course Navigator

> **Plugin**: ASU Canvas Course Builder
> **Run**: `/canvas-nav`

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python scripts/idw_metrics.py --track skill_invoked --context '{"skill": "canvas-nav"}'
```
This records usage metrics for the pilot dashboard. Do not skip this step.

## Purpose

Display the full course tree (modules → text headers → pages/assignments/quizzes/discussions/files/external tools) directly in the conversation. Browse, search, and jump to any content item without clicking through Canvas.

## When to Use

- Before editing — find the page slug you need
- After building — verify the course structure looks right
- When the user says "show me the course", "what's in module 3", "find the quiz"
- As a reference while running other skills

## Required Inputs

| Input | Source |
|---|---|
| Canvas domain | `.env` at plugin root |
| Course ID | `.env` at plugin root |

Both are read automatically. If either is missing, run `/canvas-setup` first.

## Accepted Commands

| Input | What It Does |
|---|---|
| `/canvas-nav` | Show the full course tree |
| `/canvas-nav module 3` | Show only Module 3 and its items |
| `/canvas-nav find quiz` | Search for all quiz items |
| `/canvas-nav find m2-overview` | Search by page slug |
| `/canvas-nav refresh` | Force-refresh the cached tree |

## Workflow

### Step 1 — Fetch the Course Tree

Run: `python scripts/course_navigator.py --json`

This returns the full module → items tree as JSON. The script caches results for 5 minutes to avoid repeated API calls.

### Step 2 — Display the Tree

Render the tree in a clear, structured format:

```
Course: BIO 101 - Intro to Biology (ID: 255160)
Instance: prod (canvas.asu.edu)

+ Module 0: Getting Started
    --- Welcome & Course Overview
    [P] Welcome to BIO 101 [welcome]
    [P] Syllabus [syllabus]
    [A] Introduce Yourself (25 pts) [introduce-yourself]
    [Q] Pre-Assessment (0 pts)

+ Module 1: Cell Biology
    --- Overview
    [P] Module 1 Overview [m1-overview]
    --- Prepare to Learn
    [P] Prepare to Learn [m1-prepare-to-learn]
    --- Lesson
    [P] Cell Structure & Function [m1-lesson-cell-structure]
    --- Assess Your Learning
    [Q] Knowledge Check 1 (15 pts)
    [A] Guided Practice 1 (10 pts)
    [A] Create an Artifact 1 (30 pts)
    [D] Discussion 1 (25 pts)
    --- Wrap Up
    [P] Conclusion [m1-conclusion]

- Module 2: Genetics (unpublished)
    ...
```

**Legend** (show at bottom):
```
[P] Page  [A] Assignment  [Q] Quiz  [D] Discussion
[F] File  [T] External Tool  [U] External URL  --- Text Header
+ Published  - Unpublished
```

### Step 3 — Handle Search / Filter

If the user specified a module number or search query:

- **Module filter** (`/canvas-nav module 3`): Run `python scripts/course_navigator.py --find "module 3"` and display only matching items with module context.
- **Search** (`/canvas-nav find quiz`): Run `python scripts/course_navigator.py --find "quiz"` and display matching items.
- **Slug search** (`/canvas-nav find m2-overview`): Matches against page_url field.

### Step 4 — Quick Actions

After displaying the tree, offer:

"You can:
- **Read a page**: 'show me m1-overview' — I'll fetch and display the content
- **Edit a page**: 'edit m1-overview' — I'll stage it for editing
- **Preview a page**: 'preview m1-overview' — I'll screenshot it from Canvas
- **View a quiz**: 'show me the module 3 quiz' — I'll display all questions and settings
- **View an assignment**: 'show me the module 2 artifact' — I'll display instructions, rubric, and settings
- **View a discussion**: 'show me the module 1 discussion' — I'll display the prompt and settings
- **Run another search**: 'find discussion' — I'll search the tree"

### Reading Content (All Item Types)

Use the tree to resolve any user request to the correct Canvas object, then display:

**Pages** — Fetch via `canvas_api.get_page(config, slug)` and display the HTML content in a readable summary (headings, key sections, word count).

**Quizzes** — Fetch via `GET /api/v1/courses/:id/quizzes/:quiz_id` + `GET .../questions`:
```
Quiz: Knowledge Check 3 (15 pts, 5 questions)
  Settings: 2 attempts, no time limit, shuffle answers, show one question at a time

  Q1 (MC, 3 pts): "Which membrane protein is responsible for..."
    a) Channel protein  b) Carrier protein ✓  c) Receptor  d) Enzyme
  Q2 (TF, 3 pts): "Active transport requires ATP."
    True ✓ / False
  ...
```

**Assignments** — Fetch via `GET /api/v1/courses/:id/assignments/:id`:
```
Assignment: Create an Artifact 3 (30 pts)
  Type: Online (file upload + text entry)
  Due: Mar 21, 2027 at 11:59 PM
  Rubric: 4 criteria, 30 pts total
    - Analysis Depth (10 pts)
    - Evidence Quality (8 pts)
    - Communication (7 pts)
    - Format & Citations (5 pts)
```

**Discussions** — Fetch via `GET /api/v1/courses/:id/discussion_topics/:id`:
```
Discussion: Module 3 Discussion (25 pts)
  Post-first: Yes (students must post before seeing replies)
  Prompt: "Consider the role of membrane proteins in..."
  Rubric: 3 criteria, 25 pts total
```

**Files** — List course files: `GET /api/v1/courses/:id/files?sort=updated_at&order=desc`
```
Course Files:
  /course files/
    Module 1/  (4 files, 12.3 MB)
    Module 2/  (6 files, 28.1 MB)
    unfiled/   (2 files, 0.5 MB)
  Total: 40.9 MB across 12 files
```

**Edit**: Fetch the page, stage it locally, and let the user make changes via conversation.

### Gradebook Summary

When the user asks "show me the gradebook setup" or "verify grading":

Fetch all assignment groups (`GET /api/v1/courses/:id/assignment_groups?include[]=assignments`) and display:
```
Gradebook Setup:
  Knowledge Checks (15%): 8 quizzes × 15 pts = 120 pts
  Guided Practice (10%): 8 assignments × 10 pts = 80 pts
  Create an Artifact (30%): 8 assignments × 30 pts = 240 pts
  Discussions (25%): 8 discussions × 25 pts = 200 pts
  Final Project (20%): 1 assignment × 100 pts = 100 pts
  ─────────────────────────────────────
  Total: 740 pts | Weights: 100% ✓
```

### Link Validation

When the user asks "check links" or "validate links":

1. Fetch all pages in the course
2. Extract all `<a href="">` URLs from page HTML
3. Test each URL with a HEAD request (timeout 5s)
4. Report:
```
Link Check: 47 links across 24 pages
  ✓ 42 links OK
  ⚠ 3 links slow (>3s response)
  ✗ 2 links broken:
    - m3-lesson: https://example.com/old-resource → 404
    - m5-prepare: https://example.com/moved → 301 → 404
```

## Persistent Context

After the tree is displayed, remember it for the rest of the conversation. If the user later says "edit the m3 overview" or "what's in module 5", use the cached tree to resolve page slugs without re-fetching.

## Refresh

The course navigator caches the tree for 5 minutes. If the user just made changes (e.g., via `/staging` push or `/course-build`), suggest refreshing:

"The course tree may be outdated. Run `/canvas-nav refresh` to see the latest structure."

Or automatically refresh after any skill that modifies course structure.

## Tips

- The tree shows the same structure as Canvas's Modules page
- Text headers (---) are visual separators, not clickable items
- Unpublished items are marked — useful for spotting content that needs publishing
- Page slugs in brackets (e.g., `[m1-overview]`) are what other skills use to target pages
- "show me" = read-only view; "edit" = stages for editing; "preview" = live screenshot
