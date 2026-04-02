---
name: course-config
description: "Configure course settings: publish/unpublish, due dates, assignment groups, navigation, late policy, grading, LTI tool placement."
---

# Course Config

> **Run**: `/course-config`

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python scripts/idw_metrics.py --track skill_invoked --context '{"skill": "course-config"}'
```
This records usage metrics for the pilot dashboard. Do not skip this step.

## Purpose

One skill for all course-level configuration that isn't content: publishing items, setting due dates, configuring assignment groups with grade weighting, managing navigation tabs, setting the home page, and configuring late policies.

## When to Use

- "Publish Module 3" / "Unpublish all quizzes" → **Publish mode**
- "Set due dates for all assignments" → **Dates mode**
- "Set up assignment groups with weighting" → **Groups mode**
- "Hide the Files tab" / "Set home page to modules" → **Settings mode**
- "Configure late policy" / "Set up grading" → **Settings mode**
- "Add Turnitin to Module 3" / "Place Perusall in all modules" → **LTI mode**
- "Set up my course" → Ask which operations needed

---

## Mode 1: Publish / Unpublish

### Supported Item Types

| Type | API Endpoint | Publish Field |
|---|---|---|
| Module | `PUT /courses/:id/modules/:id` | `module[published]` |
| Page | `PUT /courses/:id/pages/:slug` | `wiki_page[published]` |
| Assignment | `PUT /courses/:id/assignments/:id` | `assignment[published]` |
| Quiz | `PUT /courses/:id/quizzes/:id` | `quiz[published]` |
| Discussion | `PUT /courses/:id/discussion_topics/:id` | `published` |

### Workflow

1. Ask: "What would you like to publish or unpublish?"
   - Specific item: "Publish the Module 3 quiz"
   - Bulk: "Publish all modules" / "Unpublish all pages"
   - By module: "Publish everything in Module 1"
2. Show preview of what will change
3. Confirm, then apply
4. Report results

### Bulk Operations

For "publish everything in Module N":
1. Publish the module itself
2. Publish all items within it (pages, assignments, quizzes, discussions)
3. Report each item's status

---

## Mode 2: Set Dates

### Supported Date Fields

| Item Type | Date Fields |
|---|---|
| Assignment | `due_at`, `unlock_at`, `lock_at` |
| Quiz | `due_at`, `unlock_at`, `lock_at` |
| Discussion (graded) | `assignment.due_at`, `assignment.unlock_at`, `assignment.lock_at` |
| Module | `unlock_at` (module availability) |

### Workflow

1. **Audit mode**: "Show me what's missing dates" — scan all graded items and list those without due dates
2. **Individual**: "Set the Module 2 quiz due date to March 15 at 11:59 PM"
3. **Bulk**: "Set due dates for all modules — weekly on Sundays at 11:59 PM starting Jan 13"
4. Preview all changes before applying
5. Apply and report

### Date Format

Canvas expects ISO 8601 with timezone: `2026-03-15T23:59:00-07:00`

For Arizona (no DST): always use `-07:00` offset.

### Bulk Date Patterns

| Pattern | Description |
|---|---|
| Weekly | Due every [day] at [time], starting [date] |
| Bi-weekly | Due every other [day] |
| Same day offset | All due dates relative to module unlock |
| Custom | Provide specific date per item |

---

## Mode 3: Assignment Groups

### Workflow

1. **View current groups**:
   ```
   GET /courses/:id/assignment_groups?include[]=assignments
   ```
   Display: group name, weight, assignment count, drop rules

2. **Create groups**:
   ```
   POST /courses/:id/assignment_groups
   Body: { "name": "Quizzes", "group_weight": 20, "rules": { "drop_lowest": 1 } }
   ```

3. **Enable weighted grading**:
   ```
   PUT /courses/:id
   Body: { "course": { "apply_assignment_group_weights": true } }
   ```

4. **Move assignments between groups**:
   ```
   PUT /courses/:id/assignments/:id
   Body: { "assignment": { "assignment_group_id": <group_id> } }
   ```

### Common Setups

| Pattern | Groups |
|---|---|
| Standard | Quizzes 20%, Assignments 30%, Discussions 15%, Exams 25%, Participation 10% |
| Project-Based | Projects 40%, Quizzes 15%, Discussions 20%, Final 25% |
| No Exams | Assignments 35%, Quizzes 20%, Discussions 20%, Portfolio 25% |

### Drop Rules

```json
"rules": {
  "drop_lowest": 1,
  "drop_highest": 0,
  "never_drop": [12345]
}
```

---

## Mode 4: Course Settings

### Navigation Tabs

```
GET /courses/:id/tabs  → list all tabs with visibility
PUT /courses/:id/tabs/:tab_id → { "hidden": true/false, "position": N }
```

**Standard ASU navigation** (recommended):
- Visible: Home, Modules, Assignments, Grades, People, Syllabus, Discussions
- Hidden: Files, Outcomes, Pages, Quizzes, Collaborations

**Home tab** cannot be hidden or moved from position 1.

### Home Page / Default View

```
PUT /courses/:id
Body: { "course": { "default_view": "modules" } }
```

Valid values: `"feed"`, `"wiki"` (front page), `"modules"`, `"syllabus"`, `"assignments"`

If setting to `"wiki"`, a published front page must exist.

### Late Policy

```
POST /courses/:id/late_policy   (create new)
PATCH /courses/:id/late_policy  (update existing)

Body: { "late_policy": {
  "late_submission_deduction_enabled": true,
  "late_submission_deduction": 10.0,
  "late_submission_deduction_interval": "day",
  "late_submission_minimum_percent_enabled": true,
  "late_submission_minimum_percent": 50.0,
  "missing_submission_deduction_enabled": true,
  "missing_submission_deduction": 0.0
} }
```

| Pattern | Deduction | Interval | Min | Missing |
|---|---|---|---|---|
| Lenient | 5% | day | 50% | 0% |
| Standard | 10% | day | 50% | 0% |
| Strict | 10% | day | 0% | 100% |
| No late work | 100% | day | 0% | 100% |

### Grading Scheme

```
GET /courses/:id/grading_standards  → list available
PUT /courses/:id → { "course": { "grading_standard_id": 12345 } }
```

### Course Properties

```
PUT /courses/:id
Body: { "course": { "name": "...", "time_zone": "America/Phoenix", "license": "..." } }
```

---

## Mode 5: LTI Tool Placement

Place externally-hosted tools (Turnitin, Perusall, McGraw-Hill, Packback, etc.) into modules and assignments. This does **not** install new LTI tools — tools must already be installed at the account or course level by a Canvas admin. This mode **places** pre-installed tools where they need to go.

### When to Use

- "Add Turnitin to the Module 3 assignment"
- "Put the McGraw-Hill link in Module 5"
- "Set up Perusall for all reading assignments"
- "Add Packback to the discussion in every module"

### List Available Tools

First, show the user what tools are already installed:

```
GET /api/v1/courses/:id/external_tools?per_page=50
```

Display:
```
Available LTI Tools:
  1. Turnitin (id: 12345) — turnitin.com
  2. Perusall (id: 23456) — app.perusall.com
  3. McGraw-Hill Connect (id: 34567) — connect.mheducation.com
  ...
```

### Place as Module Item

Add a tool link directly to a module:

```
POST /api/v1/courses/:id/modules/:module_id/items
Body: {
  "module_item": {
    "title": "Turnitin: Submit Your Paper",
    "type": "ExternalTool",
    "external_url": "<tool launch URL>",
    "new_tab": true,
    "position": <position>
  }
}
```

### Place as Assignment (External Tool Submission)

Create an assignment that launches through an LTI tool:

```
POST /api/v1/courses/:id/assignments
Body: {
  "assignment": {
    "name": "Turnitin: Research Paper",
    "submission_types": ["external_tool"],
    "external_tool_tag_attributes": {
      "url": "<tool launch URL>",
      "new_tab": true
    },
    "points_possible": 100,
    "assignment_group_id": <group_id>
  }
}
```

### Bulk Placement

For "add Perusall to every module":
1. List available tools → user picks one
2. Show course tree → user confirms target modules
3. For each target module: create module item or assignment with the tool
4. Report results with Canvas links

### Important Notes

- If the tool the user needs isn't in the list, tell them: "That tool isn't installed in this Canvas course yet. A Canvas admin needs to install it first. Once it's installed, I can place it anywhere in your course."
- The launch URL may differ per tool — some use the tool's base URL, others need course-specific URLs
- External tool assignments appear in the gradebook if points are assigned
- Tool placement does NOT require opening Canvas at all

---

## Post-Push Verification (Required)

After any configuration change, always:

1. **Re-fetch and confirm** the change is reflected:
   - Publish/unpublish: re-fetch the item and check `published` / `workflow_state`
   - Due dates: re-fetch the assignment/quiz and confirm `due_at`
   - Assignment groups: re-fetch groups and confirm weights
   - Nav tabs: re-fetch `/tabs` and confirm visibility
   - Late policy: re-fetch `/late_policy` and confirm values
2. **Provide a direct Canvas link** to the affected item(s):
   - Assignments: `https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/assignments/{id}`
   - Quizzes: `https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/quizzes/{id}`
   - Modules: `https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/modules`
   - Course settings: `https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/settings`
3. **For bulk operations** (e.g., "publish all modules"): provide a summary count — "Published 6 modules, 14 pages, 5 quizzes" — with a link to the modules page.

## Workflow Summary

For any operation:
1. Fetch current state
2. Ask what to change (or infer from user request)
3. Preview proposed changes
4. Confirm
5. Apply
6. Verify by re-fetching + provide Canvas link (see Post-Push Verification above)

## Error Handling

| Error | Resolution |
|---|---|
| Can't hide Home tab | Home is locked at position 1 |
| No front page for wiki view | Create and publish one first |
| Late policy already exists | Use PATCH instead of POST |
| Weights don't sum to 100% | Warn user, Canvas allows it but flag |
| Date in the past | Warn user, allow if intentional |
| 403 Forbidden | Requires teacher or admin role |

---

### Google Drive Integration

Use the Google Drive MCP connector to find configuration templates, course setup documents, or previously exported course configs.

**MCP Tools**:
- `google_drive_search` — Search for course configuration templates, grading policy documents, or `course-config.json` exports from previous builds
- `google_drive_fetch` — Fetch configuration documents to extract settings (assignment group weights, late policies, navigation preferences)

**Where It Fits**:
- **Template reuse**: Search Drive for configuration templates from similar courses to pre-populate settings
- **Policy documents**: Find departmental grading policies or late policy standards to apply consistently
- **Config import**: Locate a previously exported `course-config.json` on Drive and import it for a new course shell
