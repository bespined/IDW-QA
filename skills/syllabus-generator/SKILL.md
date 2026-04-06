---
name: syllabus-generator
description: "Define course objectives, assessments, grading, and policies."
---

# Syllabus Generator Skill (Course Source of Truth)

> **Plugin**: ASU Canvas Course Builder
> **Trigger**: `/syllabus-generator`
> **Referenced by**: quiz, assignment-generator, discussion-generator, rubric-creator, audit

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python scripts/idw_metrics.py --track skill_invoked --context '{"skill": "syllabus-generator"}'
```
This records usage metrics for the pilot dashboard. Do not skip this step.

## Purpose
This skill serves two functions:
1. **Source of truth**: Canonical reference for all learning objectives, assessment specifications, and grading policies. Other skills (quiz, assignment-generator, discussion-generator, rubric-creator) reference this skill when verifying alignment.
2. **Syllabus generator**: Produces the complete course syllabus document formatted for the Canvas Syllabus page.

---

## Required Inputs

Before using this skill, the user must provide:

| Input | Description | Example |
|---|---|---|
| **Course title** | Full course name | "Core Physiology: Foundations for Medical Practice" |
| **Institution** | University/department | "Arizona State University — School of Medicine" |
| **Format** | Delivery mode | Fully online asynchronous, hybrid, etc. |
| **Duration** | Session length | "7.5-week session" |
| **Level** | Student audience | Pre-matriculation medical students |
| **Module count** | Number of content modules | 8 content modules + Module 0 orientation |
| **Module topics** | Title and key content per module | Provided as a list or table |
| **Course-Level Learning Objectives (CLOs)** | 5-10 CLOs for the course | Provided by the instructor or co-developed |
| **Module-Level Objectives** | 3-5 objectives per module with Bloom's levels | Co-developed using backward design |
| **Assessment types** | Which assessment categories to use | Knowledge Checks, Assignments, Discussions, Final |
| **Point allocations** | Points per assessment type | 15 pts per quiz, 30 pts per assignment, etc. |
| **Clinical/professional connections** | Per-module application contexts | Discipline-specific scenarios |

---

## Course Metadata Template

| Field | Value |
|---|---|
| **Course Title** | [Course name] |
| **Institution** | [University — School/Department] |
| **Format** | [Online/Hybrid/In-person] |
| **Duration** | [Session length] |
| **Level** | [Target audience] |
| **Modules** | [# content modules + Module 0 orientation] |
| **Prerequisites** | [Prior coursework or standing] |
| **Required Materials** | [Textbook, OER, or "all materials provided in Canvas at no cost"] |

---

## Course-Level Learning Objectives (CLOs)

Define 5-10 CLOs using this format:

| CLO | Objective | Primary Modules |
|---|---|---|
| **CLO-1** | [Verb + knowledge/skill description] | M#, M# |
| **CLO-2** | [Verb + knowledge/skill description] | M# |
| ... | ... | ... |

**Guidelines**:
- Use measurable action verbs (Bloom's taxonomy)
- Each CLO should map to 1-3 modules
- Include at least one cross-cutting CLO (e.g., "Apply [discipline] concepts to [professional] scenarios") that spans all content modules
- Align with program-level outcomes where applicable

---

## Module-Level Learning Objectives

For each module, define 3-5 objectives:

### M[#]: [Module Title]
| ID | Objective | CLO | Bloom's |
|---|---|---|---|
| M#.1 | [Objective text] | CLO-# | [Level] |
| M#.2 | [Objective text] | CLO-# | [Level] |
| M#.3 | [Objective text] | CLO-#, CLO-# | [Level] |
| M#.4 | [Objective text] | CLO-# | [Level] |
| M#.5 | [Objective text] | CLO-#, CLO-# | [Level] |

**[Professional/Clinical] Connections**: [Relevant applications for this module]

**Guidelines**:
- Target a range of Bloom's levels within each module (Understand → Analyze)
- Each objective should map to at least one CLO
- Include at least one objective per module that connects to professional practice
- Use the format `M#.#` for cross-referencing by other skills

---

## Complete Assessment Architecture

### Gold Standard Module Structure (7 items)
Each content module follows this structure:

1. **Module Overview** — Welcome, objectives, roadmap
2. **Prepare to Learn** — Audio primer + pre-class vocabulary/activities
3. **Lesson** — Lecture video (anchor content) + supplementary resources
4. **Knowledge Check** — Low-stakes formative quiz
5. **Guided Practice** — Interactive activities with formative feedback
6. **Create an Artifact** — Summative applied assignment
7. **Conclusion** — Discussion, reflection, next steps

### Assessment Inventory Template

| Module | Knowledge Check | Guided Practice | Create an Artifact | Discussion |
|---|---|---|---|---|
| M0 | — | — | — | D0: Introduction |
| M1 | KC1: [Focus] | GP1: Interactive | A1: [Type — Topic] | D1: [Title] |
| M2 | KC2: [Focus] | GP2: Interactive | A2: [Type — Topic] | D2: [Title] |
| ... | ... | ... | ... | ... |

### Assessment-to-Objective Alignment Matrix

Each assessment must cover 2-3 module objectives. Document full coverage:

| Module | KC Objectives | Artifact Objectives | Discussion Objectives |
|---|---|---|---|
| M1 | M1.1, M1.2, M1.3 | M1.2, M1.4, M1.5 | M1.3, M1.4, M1.5 |
| M2 | M2.1, M2.3, M2.5 | M2.3, M2.4, M2.5 | M2.2, M2.4, M2.5 |
| ... | ... | ... | ... |

**Rules**:
- Every module objective must be assessed by at least one graded item
- No single assessment should cover all objectives — distribute across KC, Artifact, Discussion
- The KC and Artifact should share at least one objective (the KC previews skills the Artifact requires)

### Formative → Summative Progression

Within each module, assessments form a coherent learning progression:

1. **Audio Primer** (ungraded) → Primes curiosity, activates prior knowledge
2. **Lecture Video** (ungraded) → Core content delivery — the anchor
3. **Knowledge Check** (low points, formative) → Tests comprehension; previews the *type of thinking* required by the Artifact
4. **Guided Practice** (low points, formative) → Hands-on application with interactive tools
5. **Create an Artifact** (high points, summative) → Deep application requiring synthesis and reasoning
6. **Discussion** (high points, summative) → Open-ended reasoning, peer engagement, and debate

**Critical alignment rule**: The Knowledge Check must preview skills the Artifact requires. For example:
- If the Artifact is a calculation problem set → at least 1 KC question involves a calculation
- If the Artifact is a concept map → at least 1 KC question tests relationships between the mapped concepts
- If the Artifact is a case analysis → at least 1 KC question uses a similar scenario

---

## Grading Breakdown Template

| Category | Details | Points | % of Grade |
|---|---|---|---|
| **Module 0 Activities** | Intro discussion, orientation items | [pts] | [%] |
| **Knowledge Checks** | [#] quizzes × [pts] each | [total] | [%] |
| **Guided Practice** | [#] activities × [pts] each | [total] | [%] |
| **Create an Artifact** | [#] assignments × [pts] each | [total] | [%] |
| **Discussions** | [#] discussions × [pts] each | [total] | [%] |
| **Final Assessment** | Comprehensive final | [pts] | [%] |
| **Total** | | **[total]** | **100%** |

### Grade Scale
| Grade | Percentage |
|---|---|
| A | 90–100% |
| B | 80–89% |
| C | 70–79% |
| D | 60–69% |
| E/F | Below 60% |

---

## Syllabus Metadata (Interview Group 4b)

After gathering assessment and grading information, collect the following metadata before moving to policies:

| Prompt | Field | Default |
|---|---|---|
| "How many credit hours is this course?" | `course.credit_hours` | — (required) |
| "Provide the course description (catalog description or a custom summary)." | `course.course_description` | — (required) |
| "Is this a General Studies Gold course? If yes, which designation (e.g., L, MA, SQ) and provide the Gold statement." | `course.general_studies_gold` | `false` |
| "Will this course use proctoring? If yes, which tool (Respondus LockDown Browser, Honorlock, etc.) and what are the student instructions?" | `proctoring.enabled`, `proctoring.tool`, `proctoring.instructions` | `false` |
| "Any specific technology requirements?" | `policies.technology_requirements` | "Reliable internet connection, modern web browser (Chrome or Firefox recommended), webcam and microphone" |
| "Provide a course access statement (when/how the course becomes available)." | `policies.course_access_statement` | — (required) |
| "What is the expected grading turnaround time?" | `policies.grading_turnaround_days` | 5 (business days) |

**Interview flow**: These questions are asked after the grading breakdown is finalized but before policy customization begins. If the user has an existing syllabus to import, many of these fields are auto-populated (see [Importing an Existing Syllabus](#importing-an-existing-syllabus)).

---

## Course Policies Template

### Late Work
Assignments submitted after the due date receive a **10% deduction per day**, up to 3 days late. After 3 days, late submissions are not accepted unless an approved extension was obtained *before* the deadline.

### Academic Integrity
All work must be the student's own. [Link to institutional academic integrity policy.]

### Generative AI Policy
AI tools (ChatGPT, Claude, Gemini, etc.) are permitted for **learning support** — explaining concepts, checking understanding, brainstorming approaches — but are **not** permitted for generating submitted work. Students must disclose any AI tool usage in their submissions. Submitting AI-generated content as original work constitutes an academic integrity violation. `[FACULTY: Update before launch]`

### Accessibility & Accommodations
Students with disabilities should register with the institution's disability services office and provide accommodation letters. All timed assessments have Canvas accommodation overrides enabled. Alternative submission formats accepted when supported by accommodations.

### Communication
Instructor response time: within 24 hours on weekdays. Use Canvas Inbox for course-related questions. For urgent issues, email the instructor directly.

### Required Materials
[Specify textbook, OER, or "All materials provided within Canvas at no cost."]

---

## How to Generate the Syllabus

### Step 1: Assemble Course Information
Use the metadata, CLOs, module objectives, and policies — either from the user's inputs or from a completed blueprint.

### Step 2: Build Module Schedule
Create a week-by-week module schedule with:
- Module title and topic
- Key learning objectives (abbreviated)
- Assessments with point values and due dates
- Professional/clinical connections

### Step 3: Compile Grading Section
Use the grading breakdown table and grade scale.

### Step 4: Add Policies
Include all policies from the Course Policies section, customized for the institution.

### Step 5: Stage for Preview
**Before pushing to Canvas, all syllabus HTML must go through staging:**
1. Write the generated HTML to `staging/syllabus.html`
2. Use Claude Preview to screenshot the staged page and show it to the user
3. Wait for explicit approval ("looks good", "push it") — never push without confirmation
4. Push only after the user approves

### Step 6: Format for Canvas
Output as ASU-branded HTML using:
- Maroon (#8C1D40) headers and accents
- Gold (#FFC627) for highlights
- Clean table formatting with alternating row colors
- Responsive layout (no fixed widths)

### Required Syllabus Sections (CRC-Compliant, 35 Elements (19 CRC + 16 ASU Institutional))

The HTML output must include all of the following sections in order. Items marked **(CONDITIONAL)** are only included when the corresponding config field is enabled. Items marked **(PLACEHOLDER)** contain `[FACULTY: Update before launch]` markers.

1. **Course Title & Header Metadata** — title, institution, format, duration, credit hours (`course.credit_hours`)
2. **Course Description** — from `course.course_description`
3. **Instructor Information** **(PLACEHOLDER)** — name, email, office hours, preferred contact method — all fields set to `[FACULTY: Update before launch]`
4. **Communication Methods** — how students should contact the instructor, expected response times
5. **Course-Level Learning Objectives (CLOs)** — full CLO table with primary module mappings
6. **Module-Level Objectives** — objectives per module with Bloom's levels and CLO references
7. **General Studies Gold Statement** **(CONDITIONAL)** — only rendered if `course.general_studies_gold` is set; includes designation and Gold statement text
8. **Technology Requirements** — from `policies.technology_requirements`
9. **Course Access Statement** — from `policies.course_access_statement`
10. **Submitting Coursework** **(PLACEHOLDER)** — general submission guidance with `[FACULTY: Update before launch]` for any instructor-specific instructions
11. **Late/Missed Work Policy** — late deduction schedule and extension procedures
12. **Grading Turnaround Time** — from `policies.grading_turnaround_days` (e.g., "Grades will be posted within 5 business days of the due date")
13. **Grade Breakdown Table** — assessment categories with points and percentages
14. **Grade Scale** — letter grade to percentage mapping
15. **Academic Integrity Statement** — institutional policy reference
16. **Generative AI Policy** — permitted/prohibited uses of AI tools, disclosure requirements
17. **Virtual Office Hours** **(PLACEHOLDER)** — schedule and access link with `[FACULTY: Update before launch]`
18. **Syllabus Disclaimer** — standard statement that the syllabus is subject to change with notice
19. **Proctoring Requirements** **(CONDITIONAL)** — only rendered if `proctoring.enabled` is true; includes tool name (`proctoring.tool`), installation instructions, and exam-day procedures (`proctoring.instructions`)

### ASU Institutional Policy Boilerplate (Sections 20-35)

The following 16 sections use standard ASU institutional language. They do not change per course. Include all of them after the 19 CRC elements above. Items marked **(CONDITIONAL)** are only included when the corresponding context applies.

20. **Student Code of Conduct** — "All students are expected to adhere to the ASU Student Code of Conduct. For details, visit [eoss.asu.edu/dos/srr/codeofconduct](https://eoss.asu.edu/dos/srr/codeofconduct)."

21. **Copyright & Intellectual Property** — "Course materials, including lectures, presentations, and assignments, are the intellectual property of the instructor and Arizona State University. Students may not distribute, share, or post course materials without explicit written permission. For ASU's full policy, see [provost.asu.edu/academic-integrity](https://provost.asu.edu/academic-integrity)."

22. **Disability Accommodations (SAILS/DRC)** — "Students who need academic accommodations should register with the Disability Resource Center (DRC) at [eoss.asu.edu/drc](https://eoss.asu.edu/drc) and provide the instructor with an accommodation letter at the beginning of the term. Timed assessments in this course have Canvas accommodation overrides enabled."

23. **Title IX** — "Title IX is a federal law that provides protections against sex-based discrimination. ASU's Title IX Office can be reached at [sexualviolenceprevention.asu.edu](https://sexualviolenceprevention.asu.edu). Students can report concerns confidentially to the ASU Counseling Center."

24. **Mandatory Reporting** — "All ASU employees, including instructors, are mandatory reporters. If a student discloses information about sexual violence or other protected concerns, the instructor is required to report it to the Title IX Office."

25. **Drop/Add/Withdrawal Deadlines** — "Students are responsible for knowing the drop/add and withdrawal deadlines for the current session. Deadlines are published at [students.asu.edu/academic-calendar](https://students.asu.edu/academic-calendar). A 'W' grade appears on transcripts for withdrawals after the drop/add deadline."

26. **Incomplete Grade Policy** — "A grade of Incomplete (I) may be granted at the instructor's discretion when a student who is passing the course cannot complete a small portion of remaining work due to circumstances beyond their control. Students must initiate the request before the last day of class. Per ASU policy, all Incomplete work must be finished within one calendar year."

27. **Religious Accommodations** — "Students who need to be absent from class due to the observance of a religious holiday or who need accommodations for religious practices should notify the instructor at the beginning of the term. ASU policy requires reasonable accommodation. See [provost.asu.edu](https://provost.asu.edu)."

28. **Military/Veteran Services** — "Students who are active military or veterans may be eligible for additional support through Pat Tillman Veterans Center at [veterans.asu.edu](https://veterans.asu.edu). Please notify the instructor if military obligations may affect your coursework."

29. **Student Success Resources** — Include a bulleted list:
    - **Tutoring**: ASU Tutoring — [tutoring.asu.edu](https://tutoring.asu.edu)
    - **Writing Support**: ASU Writing Centers — [writingcenters.asu.edu](https://writingcenters.asu.edu)
    - **Library**: ASU Library — [lib.asu.edu](https://lib.asu.edu)
    - **Academic Advising**: Contact your academic advisor through [eadvisor.asu.edu](https://eadvisor.asu.edu)

30. **Mental Health Resources** — "ASU offers free, confidential counseling services to all enrolled students through ASU Counseling Services at [eoss.asu.edu/counseling](https://eoss.asu.edu/counseling). For 24/7 crisis support, contact the ASU Crisis Line at 480-921-1006 or the 988 Suicide & Crisis Lifeline."

31. **Netiquette / Online Conduct** — "Online communication should follow the same standards of professionalism and respect as in-person interaction. Be constructive in discussions, use professional language, respect differing viewpoints, and avoid all-caps (which reads as shouting). Remember that tone is easily misinterpreted in text-based communication."

32. **Course Evaluation / Feedback** — "Students will have the opportunity to provide feedback on the course and instruction through the ASU course evaluation process at the end of the term. Your honest feedback helps improve future course offerings."

33. **ASU Policies URL Block** — Include a consolidated list of policy links:
    - Academic Integrity: [provost.asu.edu/academic-integrity](https://provost.asu.edu/academic-integrity)
    - Student Rights and Responsibilities: [eoss.asu.edu/dos/srr](https://eoss.asu.edu/dos/srr)
    - ACD 304-01 (Classroom & Research Behavior): [asu.edu/aad/manuals/acd/acd304-01.html](https://www.asu.edu/aad/manuals/acd/acd304-01.html)
    - ACD 304-02 (Disruptive Behavior): [asu.edu/aad/manuals/acd/acd304-02.html](https://www.asu.edu/aad/manuals/acd/acd304-02.html)

34. **Emergency / Safety Information** — "In case of an emergency on any ASU campus, call ASU Police at 480-965-3456 or dial 911. ASU's emergency information page: [asu.edu/emergency](https://www.asu.edu/emergency). Sign up for ASU alerts at [getinfo.asu.edu](https://getinfo.asu.edu)."

35. **Land Acknowledgment** **(CONDITIONAL)** — Only include if the user or institution requests it: "ASU is situated on the ancestral homelands of the Akimel O'odham (Pima) and Pee Posh (Maricopa) peoples. We acknowledge and respect the Indigenous peoples of this land and their continuing connection to it."

---

## Alignment-Critical vs. Metadata Fields

This skill serves as the source of truth for both **assessment alignment** and **syllabus/CRC compliance**. To ensure expanding the syllabus doesn't interfere with the source-of-truth role for assessment alignment, fields are classified into two categories:

### Alignment-Critical Fields
Referenced by quiz, assignment-generator, discussion-generator, and rubric-creator when verifying assessment alignment:

| Field Path | Used By | Purpose |
|---|---|---|
| `modules[].objectives[]` (IDs, text, CLO mapping, Bloom's level) | All assessment skills | Target objectives for each assessment |
| `clos[]` (ID, text, primary_modules) | All assessment skills | Course-level outcome verification |
| `modules[].assessments` (type, title, points, focus) | All assessment skills | Assessment specification and scope |
| `grading.categories` (names, weights, points) | rubric-creator, quiz | Point allocation and weight validation |

**Rule**: Changes to alignment-critical fields require propagation to all referencing skills. Run the alignment check after any modification.

### Metadata Fields
Used only by syllabus HTML output and CRC compliance checks — never referenced by assessment skills:

| Field Path | Used By | Purpose |
|---|---|---|
| `course.credit_hours` | Syllabus output | Header metadata |
| `course.course_description` | Syllabus output | Course description section |
| `course.general_studies_gold` | Syllabus output | Conditional Gold statement |
| `instructor.*` (name, email, office_hours, contact_method) | Syllabus output | Placeholder fields for faculty |
| `policies.technology_requirements` | Syllabus output | Technology section |
| `policies.course_access_statement` | Syllabus output | Access statement |
| `policies.gen_ai_policy` | Syllabus output | Generative AI policy section |
| `policies.grading_turnaround_days` | Syllabus output | Turnaround time statement |
| `proctoring.*` (enabled, tool, instructions) | Syllabus output | Conditional proctoring section |

Sections 20-35 (ASU Institutional Policy Boilerplate) are all **Metadata Fields** — they are never referenced by assessment alignment skills and can be updated without propagation.

**Rule**: Metadata fields can be updated without affecting assessment alignment. No propagation to assessment skills is needed.

---

## Importing an Existing Syllabus

When a course already has a syllabus, this skill can import and parse it to populate the course configuration rather than building from scratch. Downstream assessment skills work identically regardless of whether the syllabus was generated fresh or imported.

### Input Modes

The skill accepts an existing syllabus in three ways:

| Mode | Input | Processing |
|---|---|---|
| **Canvas URL** | URL to a Canvas Syllabus or wiki page | Fetch page body via Canvas API (`GET /api/v1/courses/:id/pages/:url`), parse returned HTML |
| **File path** | Local path to a PDF, DOCX, or HTML file | Read file content; extract text from DOCX (docx2txt or equivalent) or PDF (pdftotext or equivalent) |
| **Pasted text** | Raw text pasted into the conversation | Accept directly as-is |

### Parsing Logic

The parser attempts to extract the following from the source document:

1. **Course title** — from the document heading or first `<h1>`/`<h2>`
2. **Course description** — from a "Description" or "Overview" section
3. **CLOs** — from a "Course Objectives" or "Learning Outcomes" section; parsed into `clos[]` array
4. **Module structure** — from a schedule table, topic list, or weekly outline; parsed into `modules[]` with titles and topics
5. **Module-level objectives** — if listed per module/week; parsed into `modules[].objectives[]`
6. **Assessment types and points** — from a grading table or assessment section; parsed into `modules[].assessments` and `grading.categories`
7. **Policies** — late work, academic integrity, AI policy, communication, etc.; mapped to `policies.*` fields
8. **Instructor information** — name, email, office hours; mapped to `instructor.*`
9. **Credit hours, prerequisites, materials** — mapped to `course.*` metadata

### Post-Parse Workflow

1. Populate `course-config.json` with all extracted data
2. Set `syllabus_source.type` to `canvas_url`, `file`, or `pasted_text`
3. Set `syllabus_source.value` to the URL, file path, or `"inline"`
4. Present the extracted configuration to the user in a structured summary for review and correction
5. Flag any items that couldn't be auto-parsed with `[NEEDS REVIEW]` markers for interactive completion
6. Once the user confirms, the configuration is finalized and available to all downstream skills

### Handling Gaps

If critical fields are missing from the imported syllabus (e.g., no Bloom's levels on objectives, no CLO mappings), the skill prompts the user interactively to fill them in — using the same interview flow as a from-scratch build, but only for the missing fields.

---

## Placeholder Convention

Any field in the syllabus HTML output that requires faculty-specific input receives the marker:

```
[FACULTY: Update before launch]
```

This applies to:
- Instructor name, email, office hours, and contact method
- Virtual office hours schedule and link
- Submitting coursework instructions
- Generative AI policy (if faculty wants to customize)
- Any other field where a generic default would be inappropriate

The **course-readiness-check** skill scans the final syllabus for these markers and flags each one as a `WARN` item, ensuring nothing goes live without faculty review.

---

## Cross-Reference Protocol

### How Other Skills Use This File

When generating any assessment (quiz, assignment, discussion, rubric), the generating skill should:

1. **Look up the module's objectives** in the Module-Level Learning Objectives section
2. **Check the Assessment-to-Objective Alignment Matrix** to see which objectives this assessment should cover
3. **Verify the Formative → Summative Progression** to ensure this assessment's cognitive demands are appropriate for its position in the module sequence
4. **Reference the CLO mapping** to confirm the assessment supports course-level outcomes
5. **Document alignment** in the output: list covered objectives by ID (e.g., "This quiz assesses M3.1, M3.2, and M3.3")

### Updating This File
When any assessment specification changes (new discussion added, point value adjusted, objective revised), update this file FIRST, then propagate changes to affected skills.

---

## Error Handling

| Error | User Message | Recovery |
|-------|-------------|----------|
| No SME content provided | "I can create a syllabus template with placeholder sections. You'll need to fill in course-specific details." | Generate template with placeholders |
| course-config.json exists | "A course config already exists. Want me to update it or start fresh?" | Ask user preference |
| Section count mismatch | "Some institutional sections may not apply to your course type (e.g., Land Acknowledgment is conditional). I'll include all required sections and flag optional ones." | Auto-include required, flag optional |
| Read-only mode | "Read-only mode is active. I've generated the syllabus locally but can't push to Canvas until writes are enabled." | Guide .env change |

---

## Post-Push Verification (Required)

After pushing the syllabus to Canvas, always:

1. **Fetch and confirm** via `GET /api/v1/courses/:id?include[]=syllabus_body` and verify the body is non-empty.
2. **Provide the direct Canvas link**: `https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/assignments/syllabus`
3. **Offer a screenshot**: "Want me to screenshot the syllabus as it appears in Canvas?" If yes, navigate and capture it.

## Output
The skill produces:
1. Complete syllabus document formatted for Canvas (HTML)
2. Module schedule with objectives, assessments, and professional/clinical connections
3. Full grading breakdown with point totals
4. All course policies
5. Objective alignment summary for instructor reference

---

## Remediation Event Recording

When this skill fixes a syllabus issue flagged from an audit finding, record the remediation event. **This step is required when the fix originated from the fix queue.**

After successfully pushing the fix to Canvas, run:

```bash
python3 scripts/remediation_tracker.py --record --finding-ids <FINDING_ID> --skill syllabus-generator --description "<WHAT_WAS_FIXED>"
```

This:
1. Records a `remediation_events` row in Supabase
2. Clears the `remediation_requested` flag on the finding
3. The FindingCard in Vercel will show "Remediated via /syllabus-generator (Name, Date)"

If the fix was NOT from the fix queue (e.g., generating a new syllabus from scratch), skip this step.
