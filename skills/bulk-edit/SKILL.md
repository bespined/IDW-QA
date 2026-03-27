---
name: bulk-edit
description: "Bulk modify course pages: document-grounded batch edits, copy pages across modules, or fix accessibility/branding issues."
---

# Bulk Edit

> **Run**: `/bulk-edit`

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python scripts/idw_metrics.py --track skill_invoked --context '{"skill": "bulk-edit"}'
```
This records usage metrics for the pilot dashboard. Do not skip this step.

## Purpose

One skill for all multi-page content modifications: apply content from a source document across pages, copy a page template across modules with variable substitution, or bulk-fix accessibility and branding issues.

## When to Use

- "Add learning objectives to all overview pages" → **Batch mode**
- "Insert this content from my doc into each module" → **Batch mode**
- "Copy the overview template to all 8 modules" → **Propagate mode**
- "Fix all accessibility issues" / "Fix branding" → **Fix mode**
- "Add a footer to all pages" → **Batch mode**
- "Update the header on every page" → **Batch mode**

---

## Course Confirmation (All Modes)

Before any bulk operation, confirm the active course and show available content:

1. Read the active course from `.env`. Fetch the course name via API.
2. Confirm: "You're connected to **[Course Name]**. Is this the right course?" → [Yes] / [Switch course]
3. If switching: show numbered course list via `setup_env.py --list-courses`, let user pick.
4. **Show the course tree** via `python scripts/course_navigator.py --json` and display:
   ```
   + Module 1: Cell Biology
       [P] Module 1 Overview [m1-overview]
       [P] Prepare to Learn [m1-prepare-to-learn]
       [Q] Knowledge Check 1
       ...
   + Module 2: Genetics
       [P] Module 2 Overview [m2-overview]
       ...
   ```
5. Ask: "Which pages do you want to edit? You can say things like:
   - 'All overview pages'
   - 'Everything in Module 3'
   - 'Modules 1-4 conclusion pages'
   - Or pick specific items by name"

Then proceed to the appropriate mode below.

### Progress Reporting

During any bulk operation, report progress after each page is modified:

```
✓ Module 1 Overview: heading hierarchy fixed (1/14 pages)
✓ Module 1 Prepare to Learn: alt text added to 3 images (2/14 pages)
  → Module 2 Overview: scanning... (3/14 pages)
```

After all pages are processed:
```
═══ Bulk Edit Complete ═══
Pages modified: 14
Changes made: 23 heading fixes, 8 alt text additions, 5 link text improvements
All changes staged — run /staging to preview and push.
```

---

## Mode 1: Batch Edit (Document-Grounded)

Apply per-module content from a source document across matching pages.

### Required Inputs
- Source document with per-module content (e.g., objectives per module, custom content per page)
- Target pages identified from the course tree above

### Workflow

1. **Identify source content**: User provides a document, paste, or description. Extract per-module sections.
2. **Identify target pages**: Match user's selection against the course tree shown above. Confirm the matched pages before proceeding.
3. **Generate edits**: For each target page:
   - Fetch current HTML from Canvas
   - Determine insertion point (beginning, end, replace section, after element)
   - Generate new HTML with source content merged
4. **Stage all edits**: Write modified pages to `staging/` for preview
5. **Preview**: Show diffs or screenshots for review
6. **Iterate**: User requests changes → re-stage
7. **Push**: When approved, push via the staging workflow (backup + diff + push)

### Content Insertion Patterns

| Pattern | Description |
|---|---|
| Prepend | Add content before existing body |
| Append | Add content after existing body (e.g., footer) |
| Replace section | Find a section by heading/comment and replace |
| After element | Insert after a specific HTML element |
| Wrap | Wrap existing content in new container |

### Footer Example
```
User: "Add 'Edited by Brent's ID Workbench' footer to all pages"

For each page:
1. Fetch current body
2. Append: <hr style="margin-top:40px;border-color:#E8E8E8">
   <p style="text-align:center;font-size:12px;color:#999;">
   Edited by Brent's ID Workbench
   </p>
3. Stage → Preview → Push
```

---

## Mode 2: Propagate (Copy Page Across Modules)

Copy one page to multiple modules with variable substitution.

### Required Inputs
- Source page (slug or content)
- Target modules (numbers or "all")
- Variable mappings (what changes per module)

### Workflow

1. **Get source page**: Fetch HTML body from Canvas or staged content
2. **Define variables**: Identify placeholders (module number, title, objectives, topic)
   - Auto-detect: `{{MODULE_NUM}}`, `{{MODULE_TITLE}}`, `{{TOPIC}}`
   - Or from `course-config.json` module definitions
3. **Generate copies**: For each target module, substitute variables and generate page HTML
4. **Stage all copies** to `staging/`
5. **Preview** → **Iterate** → **Push**

### Variable Substitution

| Variable | Source | Example |
|---|---|---|
| `{{MODULE_NUM}}` | Module index | 1, 2, 3... |
| `{{MODULE_TITLE}}` | `course-config.json` | "Foundations of Theory" |
| `{{OBJECTIVES}}` | `course-config.json` | Formatted objective list |
| `{{TOPIC}}` | `course-config.json` | Module topic slug |

---

## Mode 3: Content Fix (Bulk Remediation)

Scan and fix accessibility, branding, or structural issues across all pages. Supports 10 specific fix types that can be run individually or in combination.

### Fix Types

| # | Fix Type | What It Does |
|---|----------|-------------|
| 1 | **Heading Hierarchy** | Corrects heading levels: H1→H2 (Canvas reserves H1), fixes skipped levels (H2→H4 becomes H2→H3), ensures logical nesting |
| 2 | **Alt Text** | Flags images missing alt text; marks decorative images with `alt=""`; flags complex images for manual review with `<!-- ALT_REVIEW: describe this image -->` |
| 3 | **Link Text** | Replaces generic link text ("click here", "read more", "link") with descriptive text derived from link URL/context; adds `target="_blank" rel="noopener"` to external links; appends `<span class="screenreader-only">(opens in new tab)</span>` |
| 4 | **Color Contrast** | Fixes low-contrast inline colors: `#999`→`#767676`, `#aaa`→`#767676`, `#ccc`→`#595959`; flags any remaining non-compliant color pairs for manual review |
| 5 | **Placeholder Removal** | Finds and flags TODO, TBD, INSERT, PLACEHOLDER, Lorem ipsum, and `[bracket placeholders]` for author attention; optionally removes empty placeholder sections |
| 6 | **Transcript/Caption Fixes** | Adds expandable transcript containers to pages with video/audio embeds that lack them; validates VTT caption references |
| 7 | **Submission Button Fixes** | Ensures assignment pages have a clear submission CTA; adds "Submit Assignment" button linking to Canvas submission URL when missing |
| 8 | **Table Header Fixes** | Converts first-row `<td>` to `<th scope="col">`; adds `scope="row"` to first-column cells in data tables; adds `role="presentation"` to layout tables |
| 9 | **ARIA Attribute Fixes** | Adds `role` attributes to interactive elements; ensures `aria-label` on icon-only buttons/links; adds `aria-live="polite"` to dynamic content regions |
| 10 | **Inline Style Standardization** | Normalizes inconsistent inline colors to ASU palette (#8C1D40 maroon, #FFC627 gold, #333 body text); standardizes padding/margin patterns; ensures consistent font-size usage |

### Fix Type Detail: Patterns & Examples

#### Fix 1: Heading Hierarchy

**Issue**: Heading levels skip (H2 → H4) or use H1 in page content (Canvas reserves H1 for the page title).

```
Find: <h1>Section Title</h1>
Fix:  <h2 style="color: #8C1D40;">Section Title</h2>

Find: <h4> immediately after <h2> (with no <h3> between)
Fix:  Change <h4> to <h3>
```

**Logic**: Scan each page's heading elements in order. If the sequence jumps more than one level (e.g., H2→H4, H3→H5), promote the deeper heading. If H1 is used anywhere in body content, demote to H2. Preserve all existing classes, IDs, and inline styles on the heading element.

#### Fix 2: Alt Text

**Issue**: Images missing `alt` attributes entirely.

```
Find: <img src="..." >                    (no alt attribute at all)
Fix:  <img src="..." alt="">              (decorative — spacers, borders, icons < 50px)
      <img src="..." alt="<!-- ALT_REVIEW: describe this image -->">  (content images)
```

**Detection heuristics for decorative images**:
- Filename contains: spacer, border, divider, icon, bullet, arrow, line, pixel
- Image dimensions < 50×50 px (if available from inline style/attributes)
- Image is inside a purely decorative container (e.g., `<div role="presentation">`)

**CRITICAL**: Never auto-generate descriptive alt text. Only mark decorative images as `alt=""` or flag content images for human review. AI-generated alt text requires explicit human verification via the deep accessibility audit.

#### Fix 3: Link Text

**Issue**: Generic, non-descriptive link text.

```
Find: <a href="https://example.com">click here</a>
Fix:  <a href="https://example.com" target="_blank" rel="noopener noreferrer">
        OpenStax Membrane Transport chapter
        <span class="screenreader-only"> (opens in new tab)</span>
      </a>
```

**Generic terms to flag**: "click here", "here", "link", "read more", "more", "this", "this link", "learn more", "see more", "go here"

**Replacement strategy**:
- Canvas file links → use the filename (without extension)
- Canvas page links → use the page title
- External links → use the page `<title>` if fetchable, otherwise flag for manual review
- Always add `target="_blank" rel="noopener noreferrer"` to external links
- Always append screen reader "(opens in new tab)" text

#### Fix 4: Color Contrast

**Issue**: Inline styles with colors that fail WCAG 2.1 AA contrast ratio (4.5:1 for normal text, 3:1 for large text).

```
Find: color: #999       Fix: color: #767676    (4.54:1 on white — passes AA)
Find: color: #aaa       Fix: color: #767676
Find: color: #bbb       Fix: color: #767676
Find: color: #ccc       Fix: color: #595959    (7:1 on white — passes AAA)
Find: color: #666       Fix: color: #595959
Find: color: lightgray  Fix: color: #767676
```

**For ASU palette standardization**:
- Subtitle/secondary text: `#595959` or `#767676`
- Body text: `#333` (minimum)
- Heading text: `#8C1D40` (ASU Maroon) or `#333`

#### Fix 5: Placeholder Removal

**Issue**: Unfinished content markers left in published pages.

```
Find: <!-- TODO: add content -->           Fix: [remove]
Find: [INSERT ASSIGNMENT INSTRUCTIONS]     Fix: [flag for author]
Find: Lorem ipsum dolor sit amet...        Fix: [flag for author]
Find: TBD                                  Fix: [flag for author]
Find: PLACEHOLDER                          Fix: [flag for author]
Find: [Your text here]                     Fix: [flag for author]
```

**Regex pattern**: `/(TODO|TBD|PLACEHOLDER|FIXME|\[INSERT[^\]]*\]|\[YOUR[^\]]*\]|Lorem ipsum)/gi`

**Action**: Generate a report listing every placeholder with page slug, line context, and suggested action. Do NOT auto-remove — flag for author review. Optionally remove HTML comments containing TODO/FIXME.

#### Fix 6: Transcript/Caption Fixes

**Issue**: Media embeds without expandable transcripts or caption references.

```
Find: <a id="media_comment_..." class="instructure_inline_media_comment">
      (no <details> transcript block following within 500 chars)
Fix:  Append expandable transcript container:
      <details style="margin-top: 10px;">
        <summary style="cursor: pointer; color: #8C1D40; font-weight: 600;">
          View Transcript
        </summary>
        <div style="padding: 15px; background: #f5f5f5; border-radius: 6px; margin-top: 8px;">
          <p style="color: #767676; font-style: italic;">Transcript not yet available.
          Use /media-upload to add captions and transcript.</p>
        </div>
      </details>
```

#### Fix 7: Submission Button Fixes

**Issue**: Assignment/discussion pages have placeholder divs instead of real Canvas submission buttons.

```
Find: <div class="submission-placeholder">Submit your work here</div>
Fix:  <div style="text-align: center; margin: 30px 0;">
        <a href="/courses/[COURSE_ID]/assignments/[ASSIGNMENT_ID]"
           style="display: inline-block; background-color: #8C1D40; color: white;
                  padding: 15px 40px; border-radius: 6px; text-decoration: none;
                  font-size: 18px; font-weight: bold;">
          Submit Your [Assignment Type] →
        </a>
      </div>
```

#### Fix 8: Table Header Fixes

**Issue**: Data tables using `<td>` for header cells, missing `scope` attributes.

```
Find: <tr><td>Header 1</td><td>Header 2</td></tr>  (first row of a data table)
Fix:  <tr><th scope="col">Header 1</th><th scope="col">Header 2</th></tr>

Find: First <td> in each subsequent row (when table has row headers)
Fix:  <th scope="row">Row Header</th>
```

**Detection**: A table is a "data table" if its first row content looks like headers (short text, no links, different styling). Layout tables (used for page structure) get `role="presentation"` instead.

#### Fix 9: ARIA Attribute Fixes

**Issue**: Interactive elements missing accessibility attributes.

```
Find: <div onclick="...">                   Fix: <div onclick="..." role="button" tabindex="0">
Find: <button><img src="icon.png"></button>  Fix: <button aria-label="[action]"><img src="icon.png" alt=""></button>
Find: <div id="dynamic-content">            Fix: <div id="dynamic-content" aria-live="polite">
Find: <div class="progress-bar">            Fix: <div class="progress-bar" role="progressbar"
                                                   aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
```

#### Fix 10: Inline Style Standardization

**Issue**: Inconsistent styling across pages built at different times or by different people.

**ASU Standard Palette**:
```
Heading color:     #8C1D40 (ASU Maroon)
Accent color:      #FFC627 (ASU Gold)
Body text:         #333333
Secondary text:    #595959
Border/divider:    #E8E8E8
Background light:  #F5F5F5
Link color:        #8C1D40
```

**Standardization rules**:
- All `<h2>` and `<h3>` elements: `color: #8C1D40` (unless inside a dark container)
- All body `<p>` elements: `color: #333; line-height: 1.6`
- All subtitle/meta text: `color: #595959; font-size: 14px`
- Callout boxes: consistent `padding: 20px; border-radius: 8px`
- Button styles: consistent `padding: 15px 40px; border-radius: 6px`

### Workflow

1. **Select fix types**: Show the 10 fix types and ask which to run. User can pick by number, name, or say "all".
2. **Scan**: Fetch all target pages, analyze HTML for issues matching selected fix types
3. **Report findings**: Show a summary table:
   ```
   Fix Type              Pages Affected   Issues Found
   ─────────────────────────────────────────────────────
   Heading Hierarchy     4                12
   Alt Text              7                15 (3 decorative, 12 need review)
   Link Text             6                8
   ...
   ─────────────────────────────────────────────────────
   Total                 12 pages         47 issues
   ```
4. **Confirm scope**: "Fix all 47 issues across 12 pages? Or would you like to exclude any fix types?"
5. **Generate fixes**: Modify HTML programmatically for each fix type
6. **Stage all fixes** to `staging/` for preview
7. **Preview**: Show before/after diffs for a sample page per fix type
8. **Push**: When approved, push all via staging workflow (backup + diff + push)

### Batch Operation Format

Each fix is tracked as a structured operation:
```json
{
  "fixType": "heading-hierarchy",
  "slug": "m3-overview",
  "element": "h4",
  "original": "<h4>Key Concepts</h4>",
  "fixed": "<h3>Key Concepts</h3>",
  "reason": "Heading level skipped from H2 to H4"
}
```

### Safety Rules

- **Never auto-fix alt text content** — only flag for review or mark as decorative. AI-generated alt text requires human verification.
- **Never remove content** — only modify, wrap, or flag. Placeholder removal is opt-in.
- **Preserve all inline styles** — fixes add/modify attributes but never strip existing styling unless it's the specific issue being fixed.
- **One backup per batch** — a single timestamped backup is created before the batch push, not per-page.
- **Large batch warning** — if the operation will modify 10 or more pages, warn the user before proceeding: "This will modify **[N] pages** on **[domain]** ([instance]). Want to review the full list first, or proceed?" Always show instance and domain in the confirmation.
- **Instance indicator** — always display the target Canvas instance (domain + prod/dev) when confirming any write operation.

---

---

## Mode 4: Template Cleanup (Wrong-Course Content Removal)

Remove leftover content from a previously imported template that doesn't belong to the current course. This is common when an ASU template carries pages, discussions, quizzes, or assignment groups from a different discipline.

### When to Use

- "Delete the leftover Criminal Justice content" → Template cleanup
- "Remove the old discussions that aren't mine" → Template cleanup
- "Clean up the template — there's stuff from another course" → Template cleanup
- "Delete Videos and Readings pages from all modules" → Bulk page deletion (a common template adjustment)

### Workflow

1. **Identify foreign content**: Fetch all modules, pages, discussions, quizzes, assignments, and assignment groups. Cross-reference against `course-config.json` to identify items that don't belong (wrong discipline, placeholder exams, duplicate pages, etc.)
2. **Show findings**: Present a categorized list:
   ```
   ═══ Template Cleanup Scan ═══
   Discussions (wrong course):
     - "Fourth Amendment Search & Seizure" (CRJ template)
     - "Police Interrogation Techniques" (CRJ template)
     - "Miranda Rights in Modern Context" (CRJ template)

   Placeholder modules:
     - Module 15: Midterm Exam (empty)
     - Module 20: Final Exam (empty)

   Assignment groups:
     - "Exams" (50% weight, 0 items) — not in course design

   Redundant pages (per module):
     - "Videos" pages in M1–M7 (merged into Learning Materials)
     - "Readings" pages in M1–M7 (merged into Learning Materials)
   ```
3. **Confirm**: "Delete all 14 items listed above? Or select specific categories?"
4. **Execute deletions**:
   - Pages: `DELETE /api/v1/courses/:id/pages/:slug` (auto-backed up before deletion)
   - Module items: `DELETE /api/v1/courses/:id/modules/:mid/items/:item_id`
   - Modules: `DELETE /api/v1/courses/:id/modules/:mid`
   - Discussions: `DELETE /api/v1/courses/:id/discussion_topics/:id`
   - Assignment groups: Reweight remaining groups, then `DELETE /api/v1/courses/:id/assignment_groups/:id?move_assignments_to=<target_group_id>`
5. **Report**: Show deletion results with counts per category

### Common Template Adjustments

| Pattern | Action | Notes |
|---|---|---|
| Delete Videos + Readings pages from all modules | `DELETE /pages/:slug` for each `m{N}-videos` and `m{N}-readings` slug | IDs often consolidate into a single Learning Materials page |
| Remove Midterm/Final exam placeholder modules | Delete module items first, then delete the module | Check for any real content before deleting |
| Remove wrong-discipline discussions | Delete the discussion topic; if it has an underlying assignment, delete that too | Always list them by name before deleting |
| Fix assignment group weights | `PUT /assignment_groups/:id` with correct `group_weight` | Typically after removing the Exams group |

### Safety

- All page deletions go through `delete_page()` which auto-backs up before deleting
- Module/item deletions are logged but **not reversible** — always confirm with user
- Assignment group deletion requires a `move_assignments_to` target for any remaining items
- Never delete a group without first checking if it contains assignments
- All deletes respect `_check_write_allowed()` — blocked by read-only mode

---

## Common to All Modes

### Staging Integration

All bulk edits flow through the staging workflow:
1. Generate modified HTML
2. Stage to `staging/{slug}.html`
3. Preview (local server or screenshots)
4. Iterate on changes
5. Push with backup when approved

### Safety

- Nothing touches Canvas until the user approves the push
- Every push creates a timestamped backup
- User can rollback any page via `/staging` rollback mode
- Batch operations show a summary before executing

## Error Handling

| Error | Resolution |
|---|---|
| Page not found | Skip and report, continue with others |
| Source document unclear | Ask user to clarify which content maps to which module |
| HTML parsing error | Show raw HTML, ask user to verify structure |
| Variable not found in config | Ask user to provide value manually |
