---
name: quiz
description: "Create quizzes (practice knowledge checks or graded scenario-based) or edit existing quiz questions on Canvas."
---

# Quiz Skill

> **Run**: `/quiz`

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python scripts/idw_metrics.py --track skill_invoked --context '{"skill": "quiz"}'
```
This records usage metrics for the pilot dashboard. Do not skip this step.

## Purpose

One skill for all quiz operations: generate practice knowledge checks, graded scenario-based quizzes, or edit/add/remove questions on existing quizzes.

## When to Use

- "Create a quiz for Module 3" → **Ask: practice or graded?** then generate
- "Knowledge check for Module 5" → **Practice quiz** (Mode 1A)
- "Graded quiz for Module 2" → **Graded quiz** (Mode 1B)
- "Practice quizzes for all modules" → **Batch practice** (Mode 1A × N)
- "Add questions to the midterm" → **Edit mode** (Mode 2)
- "Change the answer on question 4" → **Edit mode**
- "Show me the questions on the Module 2 quiz" → **View mode**

---

## Pre-Generation Prompt — Question Count

Before generating any quiz, **always ask the user how many questions they want**. Present the defaults but let them override:

> "How many questions for this quiz?"
> - Practice quiz default: **5 questions** (0 pts each)
> - Graded quiz default: **7 questions** (3 pts each = 21 pts)
> - Or specify a custom count (e.g., "10 questions at 2 pts each")

Adjust the question type mix proportionally. For example, a 10Q graded quiz:
- 5 Multiple Choice, 2 Multiple Answer, 2 Matching, 1 True/False

After the user confirms the count, also confirm points per question for graded quizzes so the total is explicit: "7 questions × 3 pts = **21 pts total**. Sound right?"

---

## Mode 1A: Practice Quiz (Knowledge Check)

Ungraded formative assessment — lets students self-check understanding before the graded quiz. Low stakes, unlimited attempts, encouraging feedback.

### Practice Quiz Parameters

| Setting | Default | Notes |
|---|---|---|
| **quiz_type** | `practice_quiz` | |
| **Questions** | 5 | User can override |
| **Points per question** | 0 (ungraded) | |
| **points_possible** | 0 | |
| **Attempts** | Unlimited (`allowed_attempts: -1`) | |
| **Time limit** | None | |
| **Shuffle answers** | true (except T/F) | |
| **Show correct answers** | Immediately after submission | |
| **scoring_policy** | `keep_latest` | |

### Question Design (Practice)

- **Bloom's level**: Remember → Understand → Apply (lower-order, formative)
- **Tone**: Encouraging — feedback should teach, not penalize
- **Format**: Direct knowledge recall, concept matching, term identification
- **Feedback** (all three levels required on every question):
  1. `correct_comments` — shown when the student answers correctly. Reinforce the concept briefly.
  2. `incorrect_comments` — shown when the student answers incorrectly. Address the likely misconception and redirect to the relevant Learning Materials section.
  3. `answer_comment` (per-answer) — on every individual answer option, explain why that specific choice is right or wrong. Even correct answers need reinforcement.

### Recommended Mix (scales with question count)

| Questions | MC (concept) | T/F | Matching | Fill-in-Blank |
|---|---|---|---|---|
| 3 | 1 | 1 | 1 | 0 |
| 5 (default) | 2 | 1 | 1 | 1 |
| 7 | 3 | 1 | 2 | 1 |
| 10 | 4 | 2 | 2 | 2 |

---

## Mode 1B: Graded Quiz (Scenario-Based)

Summative assessment — tests applied reasoning with real-world forensic/clinical/professional scenarios. Higher stakes, limited attempts, detailed per-answer feedback.

### Graded Quiz Parameters

| Setting | Default | Notes |
|---|---|---|
| **quiz_type** | `assignment` | |
| **Questions** | 7 | User can override |
| **Points per question** | 3 | User can override |
| **points_possible** | questions × pts_each | Auto-calculated |
| **Attempts** | 2 (`allowed_attempts: 2`) | |
| **Time limit** | None (or ~15 min if instructor prefers) | |
| **Shuffle answers** | true (except T/F and ordering) | |
| **Show correct answers** | After last attempt | |
| **scoring_policy** | `keep_highest` | |

### Question Design (Graded)

- **Bloom's level**: Apply → Analyze (higher-order, summative)
- **Scenario-based format**: Every MCQ must open with a real-world scenario (forensic case, clinical vignette, engineering problem, policy situation). Never ask bare definition questions.
- **Distractor rules**:
  1. All distractors must be plausible
  2. Avoid "none/all of the above"
  3. Keep answer lengths similar
  4. Parallel grammatical structure
  5. Each distractor tests a different misconception
- **Feedback** (all three levels required on every question):
  1. `correct_comments` — shown when the student answers correctly. Explain why the answer is correct, reinforcing the underlying concept.
  2. `incorrect_comments` — shown when the student answers incorrectly. Address the most common misconception and reference the relevant Learning Materials section.
  3. `answer_comment` (per-answer) — on every individual answer option, explain why that specific choice is right or wrong. Tie explanations to module concepts and address the specific misconception each distractor tests.

### Recommended Mix (scales with question count)

| Questions | MC (scenario) | Multiple Answer | Matching | T/F |
|---|---|---|---|---|
| 5 | 3 | 1 | 1 | 0 |
| 7 (default) | 4 | 1 | 1 | 1 |
| 10 | 5 | 2 | 2 | 1 |
| 15 | 8 | 3 | 2 | 2 |

---

## Available Question Types

| Type | Canvas API `question_type` | Best For | Notes |
|---|---|---|---|
| **Multiple Choice** | `multiple_choice_question` | Scenario-based reasoning | Most versatile |
| **Multiple Answer** | `multiple_answers_question` | "Select all that apply" | `answer_weight: 100` on each correct |
| **True/False** | `true_false_question` | Common misconceptions | NEVER shuffle answers |
| **Matching** | `matching_question` | Pairing concepts/terms | Uses `matching_answer_incorrect_matches` for distractors |
| **Fill in the Blank** | `fill_in_multiple_blanks_question` | Key terms/vocabulary | Multiple accepted spellings via `answer_text` variants |
| **Ordering** | `ordering_question` | Process steps, sequences | NEVER shuffle |
| **Numeric** | `numerical_question` | Calculations | Set `exact`, `margin` or `start`/`end` range |

## Generation Steps

1. Read module objectives from `course-config.json`
2. Determine quiz type (practice or graded) from user intent
3. Select question count and type mix per the mode above
4. Write questions with stems/scenarios, answers, and detailed feedback
5. Tag Bloom's level per question
6. Verify alignment with module MLOs
7. Stage as JSON in `staging/m{N}_{practice|graded}_quiz.json` or push directly with `--direct`

---

## Mode 2: Edit Existing Quiz

Triggered when the user wants to modify questions on an existing quiz.

### Step 1 — Identify the Quiz

Ask: "Which quiz would you like to edit?"

Resolve via course navigator or:
```
GET /api/v1/courses/:course_id/quizzes
```

### Step 2 — Show Current Questions

```
GET /api/v1/courses/:course_id/quizzes/:quiz_id/questions
```

Display with type abbreviations (MC, TF, SA, ES, MA, MT, FB, NM), points, text, and correct answers marked.

### Step 3 — Get Edit Instructions

Common operations:
- **Add questions** — type, text, answers, points, feedback
- **Edit question text** — update prompt
- **Change answers** — modify text or correct answer
- **Adjust points** — change point value
- **Add feedback** — add correct/incorrect comments
- **Delete questions** — remove from quiz
- **Change question type** — requires delete + recreate

### Step 4 — Apply Changes

**Create:**
```
POST /api/v1/courses/:course_id/quizzes/:quiz_id/questions
Body: { "question": {
  "question_name": "...",
  "question_text": "<p>...</p>",
  "question_type": "multiple_choice_question",
  "points_possible": 3,
  "correct_comments": "Correct! [Explain WHY this is right — reinforce the concept]",
  "incorrect_comments": "Not quite. [Address the likely misconception and redirect to the relevant section of the Learning Materials page]",
  "answers": [
    { "answer_text": "...", "answer_weight": 100, "answer_comments": "Correct — [specific per-answer explanation]" },
    { "answer_text": "...", "answer_weight": 0, "answer_comments": "Incorrect — [explain why this option fails and what misconception it reflects]" }
  ]
} }
```

**Question-level feedback fields (required on every question):**
- `correct_comments` — shown when student answers correctly. Reinforce the concept and explain why.
- `incorrect_comments` — shown when student answers incorrectly. Address the misconception and point to the Learning Materials section.
- `answer_comment` (singular — Canvas API write field; reads back as `comments`) — per-answer feedback shown for each individual option. Explains why that specific choice is right or wrong.

**Update:**
```
PUT /api/v1/courses/:course_id/quizzes/:quiz_id/questions/:id
```

**Delete:**
```
DELETE /api/v1/courses/:course_id/quizzes/:quiz_id/questions/:id
```

### Step 5 — Verify and Sync Points

Re-fetch and display updated quiz. **Then sync the quiz total:**

```
PUT /api/v1/courses/:course_id/quizzes/:quiz_id
Body: { "quiz": { "points_possible": <sum of all question points> } }
```

⚠️ **Canvas Classic Quizzes does NOT auto-calculate `points_possible`** after adding, editing, or replacing questions via the API. If you skip this step, the quiz may show 0 pts in Canvas even though individual questions have points. Always issue a second PUT to sync the total.

For graded quizzes (`quiz_type: "assignment"`), also update the linked assignment object:
```
PUT /api/v1/courses/:course_id/assignments/:assignment_id
Body: { "assignment": { "points_possible": <same total> } }
```

The `assignment_id` is returned in the quiz object as `assignment_id`.

---

## Key Rules

- `answer_weight`: 100 = correct, 0 = incorrect (not boolean)
- **Per-answer feedback field name quirk**: The Canvas API **writes** with `answer_comment` (singular) but **reads** back as `comments` (plural). Always use `answer_comment` when creating/updating questions.
- **Three feedback levels required**: Every question must have `correct_comments`, `incorrect_comments`, and `answer_comment` on every answer option. Never skip per-answer feedback.
- For true/false and ordering: NEVER use `shuffle_answers: true`
- HTML supported in `question_text`
- **`points_possible` does NOT auto-sync** — always issue a second PUT after question changes (see Step 5)
- Published quiz changes are live immediately — warn user
- Practice quizzes use `quiz_type: "practice_quiz"` — they do NOT create an assignment object and do NOT appear in the gradebook
- Graded quizzes use `quiz_type: "assignment"` — they create a linked assignment and appear in the gradebook

## Error Handling

| Error | Resolution |
|---|---|
| Quiz not found | List available quizzes |
| Type change needed | Explain delete + recreate requirement |
| Invalid answer format | Validate before API call |
| Quiz is published | Warn changes are live |
| Quiz shows 0 pts after push | Run the points_possible sync PUT (Step 5) |
