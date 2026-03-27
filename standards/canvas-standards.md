# ASU Canvas Course Standards

> **Plugin Reference** — This document is part of the ASU Canvas Builder plugin.
> Synthesized from 14 Canvas course scans across multiple ASU programs (March 2026).
> Updated with ASU Course Readiness Check (CRC) requirements, FRAME accessibility framework, and 25 Design Standards.
> Referenced by: `course-build`, `course-audit`, `course-readiness-check`, `accessibility-audit`, `content-fix` skills.

---

## Gold Standard Module Template (7 items per module)
1. Module #: Overview (Page)
2. Module #: Prepare to Learn (Page)
3. Module #: Lesson ~40 min (Page)
4. Module #: Knowledge Check ~5 min (Page/Quiz)
5. Module #: Guided Practice ~10 min (Page)
6. Module #: Create an Artifact ~20 min (Page/Assignment)
7. Module #: Conclusion (Page)

**Total**: ~75 min per module

---

## Required Navigation Menu (Canvas Tabs API)

The following navigation items must be enabled and visible to students:

| Tab | Required | Notes |
|---|---|---|
| Home | Yes | Landing page for the course |
| Modules | Yes | Primary content organization |
| Syllabus | Yes | Course policies and schedule |
| Announcements | Yes | Instructor communication channel |
| Assignments | Yes | All graded items |
| Grades | Yes | Student gradebook view |
| ASU Course Policies | Yes | Links to university-level policies |
| Accessibility | Yes | Links to SAILS and accessibility resources |
| Time in AZ | Conditional | Required for online/hybrid courses in Arizona |

**Verification**: Use Canvas Tabs API (`GET /api/v1/courses/{id}/tabs`) to check enabled tabs. Items with `hidden: true` or `visibility: "admins"` are not visible to students.

---

## Module 0 Required Elements
- Welcome page (welcoming tone, course tour, instructor introduction)
- Syllabus & Course Policies page
- Academic integrity agreement
- Introductory activity (discussion or survey)
- Pre-assessment (diagnostic, low/no stakes)

---

## Course Readiness Check (CRC) Requirements

ASU's formal Course Readiness Check is a 9-category quality assurance process used by Instructional Design Assistants before course launch. All items are evaluated as PASS, FAIL, or WARN.

### CRC Category 1: Navigation Menu
- All required tabs enabled (see Navigation Menu section above)
- No extraneous tabs visible to students (e.g., Files, People, unless intentional)
- Home page set and functional

### CRC Category 2: Syllabus Completeness
The syllabus must contain all 19 required elements:

| # | Element | Plugin Source |
|---|---|---|
| 1 | Course description | `course.course_description` |
| 2 | Credit hours | `course.credit_hours` |
| 3 | Instructor contact information | `instructor.*` (placeholder until faculty updates) |
| 4 | Communication methods and response time | `instructor.communication_methods` |
| 5 | Course-level learning outcomes (CLOs) | `clos[]` |
| 6 | Module-level learning objectives | `modules[].objectives[]` |
| 7 | General Studies Gold statement | `course.general_studies_gold_statement` (conditional) |
| 8 | Technology requirements | `policies.technology_requirements` |
| 9 | Course access statement | `policies.course_access_statement` |
| 10 | Submitting coursework instructions | `policies.submitting_coursework` |
| 11 | Late/missed work policy | `policies.late_work` |
| 12 | Grading turnaround time | `policies.grading_turnaround_days` |
| 13 | Grade breakdown by category | `grading.categories[]` |
| 14 | Grading scale | `grading.scale` |
| 15 | Academic integrity policy | `policies.academic_integrity` |
| 16 | Generative AI policy | `policies.gen_ai_policy` |
| 17 | Virtual office hours information | `instructor.office_hours` (placeholder) |
| 18 | Syllabus disclaimer | `policies.syllabus_disclaimer` |
| 19 | No outdated information | Manual check — dates, links, tool references current |

### CRC Category 3: Canvas Template Application
- Course uses an approved ASU template or follows Gold Standard structure
- Banner images present and consistent across modules
- Module naming convention followed: "Module #: Descriptive Title"
- Course image/banner set in course settings

### CRC Category 4: Accessibility
- Run `accessibility-audit` skill for automated WCAG 2.1 AA checks
- Run Canvas Ally Course Report for file accessibility scores
- Run SCOUT (if available) for additional accessibility scanning
- Verify FRAME compliance (see FRAME section below)

### CRC Category 5: Course Component Settings
- All assignment due dates set and in chronological order
- Due dates within the current session window (not past dates)
- Grade breakdown matches syllabus (assignment group names and weights)
- No empty assignment groups
- Assessment settings (attempts, time limits) match instructions

### CRC Category 6: Assessments
- Practice assessments exist (formative before summative)
- Assessment variety across the course (not all one type)
- Instructions are clear with unambiguous deliverables
- Settings match (time limits, attempts, submission types)
- Rubrics attached and aligned to objectives
- Quiz question order/answer shuffling enabled where appropriate

### CRC Category 7: Content & Media
- All embedded videos play correctly
- All external URLs resolve (no broken links)
- External links use `target="_blank"` with `rel="noopener noreferrer"`
- Content formatting is clean (no leftover Word/HTML artifacts)
- Media sources properly cited or attributed

### CRC Category 8: Proctoring (Conditional)
- Proctoring tool settings enabled in Canvas (if applicable)
- Proctoring instructions in syllabus and on exam pages
- Student setup/test instructions provided before first proctored exam

### CRC Category 9: Launch Readiness
- All items published (no unpublished pages or assignments visible in modules)
- Prerequisites set correctly (if used)
- Course available to students (published)
- Faculty Resources module unpublished (hidden from students)

---

## FRAME Accessibility Framework

ASU's FRAME (Faculty Resources for Accessible Media Essentials) framework defines five categories of accessibility requirements. All Canvas courses must comply.

### F — Fonts
- Use standard, readable fonts (Canvas default fonts are acceptable)
- Minimum text size: 12pt equivalent (16px)
- Avoid decorative or script fonts for body text
- Do not use text in images as the sole means of conveying information

### R — Readability
- Heading hierarchy: H2 → H3 → H4 (never use H1 in Canvas page content)
- Never skip heading levels (no H2 → H4 without H3)
- Use proper list markup (`<ul>`, `<ol>`, `<li>`) — do not fake lists with dashes/asterisks
- Tables have `<th>` headers with `scope` attributes
- Sufficient color contrast (WCAG 2.1 AA: 4.5:1 normal text, 3:1 large text)
- Color is not the only means of conveying information

### A — Accessible Media
- All videos have synchronized captions (upload VTT tracks or use MediaPlus)
- All audio has text transcripts
- Auto-generated captions must be reviewed and corrected
- Expandable transcript blocks provided below media embeds
- Caption format: WebVTT (.vtt) preferred

### M — Meaningful Hyperlinks
- Link text is descriptive (no "click here," "here," "read more," "link")
- URL is not used as link text
- Links opening in new windows include screen-reader hint text
- External links have `target="_blank"` with `rel="noopener noreferrer"`

### E — Equitable Design
- Images have meaningful alt text (or `alt=""` for decorative images)
- Alt text describes purpose, not just content ("Chart showing revenue growth" not "chart.png")
- Interactive elements are keyboard accessible
- Content is perceivable without CSS or JavaScript
- Multiple means of representation (UDL)

### Document Accessibility
- **PDF files**: Verify with Equidox or Adobe Accessibility Checker before uploading
- **Office files (DOCX, PPTX, XLSX)**: Run Microsoft Accessibility Checker
- **Canvas Ally**: Use Ally Course Report for automated scoring of uploaded files
- Flag all uploaded documents in audit reports with reminders to verify accessibility

---

## Key Design Rules

### Heading Hierarchy
- **H1**: NEVER in page content (Canvas auto-generates from page title)
- **H2**: Major sections
- **H3**: Subsections
- **H4**: Minor subsections
- Never skip levels (no H2 → H4)

### Visual Identity
- ASU Colors: Maroon `#8C1D40`, Gold `#FFC627`
- Banner images consistent across all modules
- Module naming convention: "Module #: Descriptive Title"

### Learning Objectives
- 3-5 learning objectives per module (up to 7 for complex modules)
- Use measurable Bloom's taxonomy verbs
- Align objectives → assessments → activities → materials
- Objectives visible on module Overview pages

### Assessment Standards
- Rubrics: analytic, 3-5 criteria, 4 performance levels (Exemplary / Proficient / Developing / Beginning)
- Each module includes at minimum: Knowledge Check + one graded activity
- Formative practice before summative assessment in every module

### Media Standards
- Videos: 6-10 min optimal length, responsive embed
- All media must have captions and transcripts
- WCAG 2.1 AA compliance required (ASU deadline: April 2026)
- Cite or attribute all third-party media

### Interactive Elements
- HTML5 accordions, jQuery UI tabs, H5P activities
- Formative (ungraded) — used for practice and self-assessment
- 2-4 interactive activities per module

---

## Assessment Group Weights (Typical Ranges)
| Category | Weight Range |
|---|---|
| Module 0 / Orientation | 2.5-5% |
| Weekly Assignments | 20-30% |
| Discussions | 10-25% |
| Quizzes / Knowledge Checks | 10-15% |
| Major Projects | 20-30% |
| Exams / Final Assessment | 15-30% |

> Adjust weights to fit your course design. Total must equal 100%.

---

## Best Practices

### Welcoming & Inclusive Language
- Use asset-based framing ("You will learn..." not "Students often struggle with...")
- Write in a welcoming, encouraging tone — avoid punitive or transactional language
- Use diverse names and contexts in examples, scenarios, and case studies
- Maintain consistent voice and level of formality across all modules

### External Link Handling
All external links must:
1. Use `target="_blank"` to open in a new tab
2. Include `rel="noopener noreferrer"` for security (prevents reverse tabnapping)
3. Include screen-reader hint text: `<span class="sr-only">(opens in new tab)</span>`

```html
<a href="https://example.com" target="_blank" rel="noopener noreferrer">
  Descriptive Link Text <span class="sr-only">(opens in new tab)</span>
</a>
```

### Student Support Ecosystem
Every course should reference these ASU support resources (typically on a Resources page and/or in the syllabus):

| Resource | Purpose |
|---|---|
| SAILS | Accessibility accommodations |
| Canvas Help (24/7) | Technical support |
| Success Coaching | Academic strategy support |
| Academic Advising | Degree planning |
| Tutoring | Subject-specific help |
| Counseling Services | Mental health support |
| Dean of Students | Personal emergencies |

### Mobile & Responsive Design
- Test content on mobile devices (Canvas Student app)
- Avoid fixed-width layouts that break on small screens
- Use responsive embed codes for media (`max-width: 100%`)
- Verify interactive activities function on touch devices

---

## Quality Checklist

### Structure & Navigation
- [ ] All modules follow 7-item Gold Standard template
- [ ] Module 0 has all required elements
- [ ] Navigation includes all required tabs
- [ ] Module naming convention followed
- [ ] Banner images consistent across modules

### Syllabus & Policies
- [ ] All 19 CRC syllabus elements present
- [ ] Grade breakdown matches assignment group weights
- [ ] No outdated information (dates, links, tools)

### Accessibility (FRAME)
- [ ] Heading hierarchy correct (H2 → H3 → H4, no H1)
- [ ] All images have alt text
- [ ] All media have captions and transcripts
- [ ] All links are descriptive (no "click here")
- [ ] Color contrast meets WCAG 2.1 AA (4.5:1 minimum)
- [ ] External links have `target="_blank"` + `rel="noopener noreferrer"` + sr-only text
- [ ] Uploaded documents verified for accessibility

### Assessments
- [ ] Rubrics attached to all graded assignments
- [ ] Learning objectives visible on Overview pages
- [ ] Formative practice before summative in each module
- [ ] Assessment variety across the course

### Content & Media
- [ ] All videos play and all links resolve
- [ ] Media properly cited/attributed
- [ ] Content formatting clean (no HTML artifacts)

### Launch Readiness
- [ ] All items published
- [ ] Due dates set and chronological
- [ ] Student support resources linked
- [ ] Faculty Resources module hidden from students
