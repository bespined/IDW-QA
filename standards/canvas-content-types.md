# Canvas LMS Content Types Reference

> **Plugin Reference** — This document is part of the ASU Canvas Builder plugin.
> Complete API reference for Canvas content objects: quizzes, assignments, discussions, rubrics, modules, and HTML standards.
> Referenced by: `course-build`, `course-audit`, `quiz-generator`, `assignment-generator`, `discussion-generator`, `rubric-creator` skills.

## 1. QUIZZES (New Quizzes - current system; Classic Quizzes sunsetting Dec 2025)

### Quiz Configuration Fields
| Field | Description | Values/Notes |
|---|---|---|
| title | Quiz name (required) | String |
| description | HTML overview content | Supports RCE HTML |
| quiz_type | Purpose of quiz | `assignment` (graded), `practice_quiz`, `graded_survey`, `survey` |
| time_limit | Minutes allowed | Integer or null (unlimited) |
| allowed_attempts | Number of attempts | Integer; -1 = unlimited |
| scoring_policy | Multi-attempt scoring | `keep_highest`, `keep_latest` |
| shuffle_answers | Randomize MC options | Boolean |
| one_question_at_a_time | Paginated display | Boolean |
| cant_go_back | Lock after answering | Boolean (requires one_question_at_a_time) |
| show_correct_answers | Show answer key | Boolean |
| show_correct_answers_at | Delayed answer reveal | ISO 8601 DateTime |
| hide_correct_answers_at | Hide answers after date | ISO 8601 DateTime |
| show_correct_answers_last_attempt | Only show on final attempt | Boolean |
| one_time_results | Prevent repeat result viewing | Boolean |
| hide_results | When to hide results | `always`, `until_after_last_attempt`, null |
| access_code | Password protection | String |
| ip_filter | IP range restriction | String |
| due_at | Due date | ISO 8601 DateTime |
| lock_at | Close date | ISO 8601 DateTime |
| unlock_at | Available from date | ISO 8601 DateTime |
| assignment_group_id | Grade category | Integer ID |
| published | Visibility state | Boolean |

### New Quizzes Additional Settings
- Require waiting period between attempts (cool-down)
- Shuffle questions globally
- Add extra time/attempts for entire course (accommodations)
- Partial credit for multiple choice
- Student accommodations applied across all quizzes

### Question Types (New Quizzes)
| Type | Description | Use Case |
|---|---|---|
| **Multiple Choice** | Select ONE correct answer from list | Standard assessment; single best answer |
| **Multiple Answer** | Select ALL correct answers from list | "Select all that apply" questions |
| **True/False** | Judge factual statement | Quick knowledge checks |
| **Essay** | Free-text response | Explanation, analysis, reasoning |
| **Fill in the Blank** | Enter text, select dropdown, or word bank | Terminology, definitions, labeling |
| **Matching** | Match items from drop-down to list | Pair concepts (e.g., term → definition) |
| **Ordering** | Arrange items in specific sequence | Sequences, processes, timelines |
| **Categorization** | Sort items into correct categories | Classification tasks |
| **Numeric** | Type numerical answer | Calculations, quantitative problems |
| **Formula** | Computed numerical answer | Math-based questions with variables |
| **Hot Spot** | Click specific area on image | Diagram interpretation, identification |
| **Stimulus** | Content block (image/text/table) with attached questions | Scenario with multiple sub-questions |
| **File Upload** | Student uploads file | Reports, diagrams, extended work |
| **Text (No Question)** | Informational text block | Instructions, context between question groups |

### Classic Quizzes Question Types (API-level names)
- `multiple_choice_question`
- `true_false_question`
- `short_answer_question`
- `essay_question`
- `matching_question`
- `multiple_answers_question`
- `multiple_dropdowns_question`
- `fill_in_multiple_blanks_question`
- `numerical_question`
- `calculated_question`
- `file_upload_question`
- `text_only_question`

### Question JSON Structure (Classic Quiz API)
```json
{
  "question_name": "Topic Q1",
  "question_type": "multiple_choice_question",
  "question_text": "<p>HTML content of question</p>",
  "points_possible": 2,
  "position": 1,
  "correct_comments": "Correct! Explanation...",
  "incorrect_comments": "Review the concept of...",
  "neutral_comments": "This question tests...",
  "answers": [
    {
      "id": 1,
      "answer_text": "Option A text",
      "answer_weight": 100,
      "answer_comments": "Feedback for this choice"
    },
    {
      "id": 2,
      "answer_text": "Option B text",
      "answer_weight": 0,
      "answer_comments": "Feedback for this choice"
    }
  ]
}
```

Answer weight: 100 = correct, 0 = incorrect.
Matching uses `answer_match_left` and `answer_match_right`.
Numerical uses `exact`, `margin`, `start`, `end`, `approximate`, `precision`.

---

## 2. ASSIGNMENTS

### Assignment Fields
| Field | Description | Values/Notes |
|---|---|---|
| name | Assignment title (required) | String |
| description | HTML instructions/content | Supports full RCE HTML |
| points_possible | Maximum points | Number |
| grading_type | How to display grade | `points`, `percent`, `letter_grade`, `gpa_scale`, `pass_fail`, `not_graded` |
| submission_types[] | How students submit | See list below |
| due_at | Due date | ISO 8601 DateTime |
| lock_at | Closes for submission | ISO 8601 DateTime |
| unlock_at | Opens for submission | ISO 8601 DateTime |
| assignment_group_id | Grade category | Integer ID |
| published | Visibility | Boolean |
| peer_reviews | Enable peer review | Boolean |
| automatic_peer_reviews | Auto-assign reviewers | Boolean |
| peer_review_count | Reviews per student | Integer |
| allowed_extensions[] | File types for upload | Array of strings (e.g., ["pdf", "docx"]) |
| allowed_attempts | Submission attempts | Integer (-1 = unlimited) |
| turnitin_enabled | Plagiarism detection | Boolean |
| anonymous_grading | Hide student identity | Boolean |
| moderated_grading | Enable moderation | Boolean |
| group_category_id | Group assignment | Integer ID |
| grade_group_students_individually | Individual vs group grade | Boolean |
| omit_from_final_grade | Exclude from total | Boolean |
| only_visible_to_overrides | Restricted visibility | Boolean |
| position | Display order | Integer |

### Submission Types
- `online_text_entry` — Rich text editor submission
- `online_upload` — File upload
- `online_url` — URL submission
- `media_recording` — Audio/video recording
- `student_annotation` — Annotate a document
- `on_paper` — Physical submission (manual grading)
- `external_tool` — LTI tool submission
- `online_quiz` — Quiz-type assignment
- `discussion_topic` — Discussion-type assignment
- `none` — No submission (grade only)

---

## 3. DISCUSSIONS

### Discussion Topic Fields
| Field | Description | Values/Notes |
|---|---|---|
| title | Topic title (required) | String |
| message | HTML body/prompt | Full RCE HTML supported |
| discussion_type | Threading model | `side_comment` (flat), `threaded`, `not_threaded` |
| require_initial_post | Must post before viewing | Boolean — key for equitable participation |
| published | Draft or live | Boolean |
| delayed_post_at | Scheduled publication | ISO 8601 DateTime |
| lock_at | Close for comments | ISO 8601 DateTime |
| pinned | Pin to top | Boolean |
| locked | Prevent comments | Boolean |
| allow_rating | Enable liking/rating | Boolean |
| only_graders_can_rate | Restrict rating | Boolean |
| podcast_enabled | RSS feed | Boolean |
| podcast_has_student_posts | Include student posts in feed | Boolean |
| group_category_id | Small group discussions | Integer ID |
| assignment | Graded discussion config | Object with assignment fields |
| is_announcement | Post as announcement | Boolean |
| specific_sections | Section targeting | Comma-separated section IDs |

### Discussion as Graded Assignment
When `assignment` object is provided, the discussion becomes a graded assignment with:
- points_possible
- due_at, lock_at, unlock_at
- assignment_group_id
- peer_reviews settings

### Key Discussion Options for Course Design
- **Threaded**: Best for open-ended case discussions
- **Require initial post**: Ensures original thinking before peer influence
- **Group discussions**: Small group (4-6 students) for deeper engagement
- **Graded**: Attach rubric for structured assessment

---

## 4. RUBRICS

### Rubric Structure
```
Rubric
├── title (string)
├── free_form_criterion_comments (boolean)
├── points_possible (total across all criteria)
└── criteria[] (array of criterion objects)
    ├── id (string, e.g., "_10")
    ├── description (criterion name/title)
    ├── long_description (detailed explanation)
    ├── points (max points for this criterion)
    ├── criterion_use_range (boolean — range vs fixed points)
    └── ratings[] (array of rating objects)
        ├── id (string)
        ├── description (rating level name, e.g., "Exemplary")
        ├── long_description (what this level looks like)
        └── points (points for this rating level)
```

### Rubric Association (linking rubric to content)
| Field | Description | Values |
|---|---|---|
| association_id | Target object ID | Integer |
| association_type | What it's attached to | `Assignment`, `Course`, `Account` |
| use_for_grading | Calculate grade from rubric | Boolean |
| hide_score_total | Hide total from students | Boolean |
| purpose | Rubric purpose | `grading` or `bookmark` |

### Rubric Design Patterns
**Standard 4-level rubric (most common in Canvas):**
- Exemplary / Proficient / Developing / Beginning
- Or: Excellent / Good / Satisfactory / Needs Improvement

**Point range feature:** Each rating can have min/max range instead of fixed value.

**Free-form comments:** When enabled, grader can write custom feedback per criterion rather than selecting a pre-defined rating.

### Example Rubric JSON
```json
{
  "rubric": {
    "title": "Case Analysis Rubric",
    "free_form_criterion_comments": true,
    "criteria": {
      "0": {
        "description": "Core Concepts",
        "long_description": "Accurately identifies and explains the underlying concepts",
        "points": 10,
        "criterion_use_range": false,
        "ratings": {
          "0": { "description": "Exemplary", "long_description": "Complete, accurate explanation with application", "points": 10 },
          "1": { "description": "Proficient", "long_description": "Accurate explanation with minor gaps", "points": 8 },
          "2": { "description": "Developing", "long_description": "Partially correct with significant gaps", "points": 5 },
          "3": { "description": "Beginning", "long_description": "Incorrect or missing explanation", "points": 0 }
        }
      }
    }
  },
  "rubric_association": {
    "association_type": "Assignment",
    "use_for_grading": true,
    "purpose": "grading"
  }
}
```

---

## 5. MODULES

### Module Fields
| Field | Description | Values/Notes |
|---|---|---|
| name | Module title (required) | String |
| position | Display order | Integer (1-based) |
| unlock_at | Available from date | ISO 8601 DateTime |
| require_sequential_progress | Linear progression | Boolean |
| prerequisite_module_ids[] | Must complete first | Array of module IDs |
| publish_final_grade | Post grade on completion | Boolean |

### Module Item Types
| Type | Description | Required Fields |
|---|---|---|
| **Page** | Canvas wiki page | type, page_url |
| **Assignment** | Graded assignment | type, content_id |
| **Quiz** | Quiz/assessment | type, content_id |
| **Discussion** | Discussion topic | type, content_id |
| **File** | Uploaded file | type, content_id |
| **SubHeader** | Text divider/label | type only |
| **ExternalUrl** | Link to external site | type, external_url |
| **ExternalTool** | LTI tool | type, content_id |

### Module Item Fields
| Field | Description | Values/Notes |
|---|---|---|
| title | Display name | String |
| type | Item type (required) | See types above |
| content_id | ID of linked content | Integer (not needed for SubHeader/ExternalUrl) |
| position | Order within module | Integer (1-based) |
| indent | Visual nesting level | 0-based integer (0, 1, 2, 3) |
| external_url | URL for ExternalUrl type | String |
| new_tab | Open in new window | Boolean (ExternalTool/ExternalUrl) |

### Completion Requirements
| Type | Description |
|---|---|
| `must_view` | Student must open/view the item |
| `must_contribute` | Student must participate (discussions) |
| `must_submit` | Student must submit (assignments/quizzes) |
| `min_score` | Student must achieve minimum score |
| `must_mark_done` | Student manually marks complete |

### Module Organization Best Practices
- Use **SubHeaders** to divide module into sections
- Use **indent** levels to create visual hierarchy under SubHeaders
- Set **require_sequential_progress** for scaffolded learning paths
- Use **prerequisites** to enforce module ordering
- Follow the Gold Standard 7-item template (see `canvas-standards.md`)

---

## 6. HTML CONTENT STANDARDS FOR CANVAS

### Heading Hierarchy
- **H2** = Broadest topic (Canvas uses H1 for page title)
- **H3** = Subtopics under H2
- **H4** = Sub-subtopics
- Never skip levels (no H2 → H4)
- Never use `<strong>` as a heading substitute

### Accessibility Requirements
- All images must have alt text
- Tables must have row/column headers and captions
- Tables should NOT be used for layout (data only)
- Use proper list markup (not manual numbering)
- Links must be descriptive (not "click here")
- Color should not be the sole way to convey information
- Canvas has built-in accessibility checker (catches 11 issue types)

### Supported HTML Elements
- Paragraphs: `<p>`
- Headings: `<h2>` through `<h4>`
- Lists: `<ul>`, `<ol>`, `<li>`
- Tables: `<table>`, `<thead>`, `<tbody>`, `<tr>`, `<th>`, `<td>`, `<caption>`
- Links: `<a href="">`
- Images: `<img src="" alt="">`
- Emphasis: `<strong>`, `<em>`
- Iframes: `<iframe>` (for embedded content)
- Divs/spans with inline styles (limited CSS support)

### CSS Limitations
- Canvas strips many CSS properties
- Inline styles work better than class-based styles
- Supported: color, background-color, padding, margin, border, text-align, width, font-size
- Canvas may strip: position, float, display (in some contexts), custom fonts
