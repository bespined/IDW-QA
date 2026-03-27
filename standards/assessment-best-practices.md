# Assessment Best Practices

> **Plugin Reference** — This document is part of the ASU Canvas Builder plugin.
> Evidence-based assessment design standards for higher education courses.
> Referenced by: `quiz-generator`, `assignment-generator`, `rubric-creator`, `course-audit`, `course-readiness-check` skills.
> **Note**: For proctored exams, see the `proctoring` section in `templates/course-config.json` and the CRC Category 8 checks in `standards/canvas-standards.md`.

## 1. NBME-STYLE QUESTION WRITING

### Clinical Vignette Structure (Standard Order)
> This format is standard for health sciences courses. For other disciplines, adapt the vignette structure to use discipline-appropriate scenarios (case studies, situational prompts, data sets, etc.).

1. **Context/demographics**: Relevant background (e.g., "A 52-year-old woman" or "A small business owner")
2. **Situation**: Where/when presenting (e.g., "comes to the emergency department" or "contacts your consulting firm")
3. **Primary issue**: Reason for the scenario with relevant timeframe
4. **Supporting details**: Quality, severity, timing, associated factors
5. **Relevant history** (optional): Background information pertinent to the case
6. **Data/observations**: Key findings, measurements, or evidence
7. **Additional data** (optional): Lab values, metrics, survey results, financial data
8. **Context update** (optional): What has been done, how situation has evolved

### Lead-in (Stem) Rules
- MUST end with a question mark
- Should be answerable from the stem alone (before seeing options)
- Avoid negative phrasing ("Which of the following is NOT...")
- Avoid vague phrasing ("Which of the following is true about...")
- Use focused lead-ins:
  - "Which of the following is the most likely explanation?"
  - "Which of the following is the most likely underlying mechanism?"
  - "Which of the following is the most appropriate next step?"
  - "Which of the following best explains these findings?"
  - "Which of the following factors is most likely responsible?"

### Discipline-Specific Lead-in Examples
> Adapt these to your subject area. The examples below use health sciences language but the pattern applies to any discipline.

- "Which of the following changes would be expected in this scenario?"
- "Which of the following best explains the mechanism of this effect?"
- "Which factor is most likely responsible for this finding?"
- "What is the most likely outcome of this intervention?"
- "Which of the following compensatory responses is most likely activated?"

### Answer Option Rules
- **Number of options**: 4-5 options (3 strong distractors preferred over 5 weak ones)
- **Homogeneity**: All options must be the same type (all explanations, all mechanisms, all approaches)
- **Parallel structure**: Same grammatical form and approximate length
- **Alphabetical or logical order**: Don't cluster correct answer in one position
- **No "all of the above" or "none of the above"**
- **No absolutes**: Avoid "always," "never" in options
- **No vague qualifiers**: Avoid "usually," "sometimes," "often"
- Correct answer should NOT be conspicuously longer than distractors

---

## 2. DISTRACTOR DESIGN

### Principles of Good Distractors
- Based on **common student misconceptions** or frequent errors
- **Plausible** to students who haven't mastered the concept
- **Homogeneous** with the correct answer (same category/type)
- Each distractor chosen by >5% of examinees (functional threshold)
- 2-3 strong distractors > 4-5 weak ones

### Common Distractor Strategies
| Strategy | Example |
|---|---|
| Related but different mechanism | If answer is "increased X," distractor could be "increased Y" (related variable) |
| Opposite direction | If answer is "decrease," distractor is "increase" |
| Different system/category | If answer is one subsystem's response, distractor is another's |
| Common student confusion | Mix up closely related concepts or terms |
| Partially correct | Correct reasoning but wrong conclusion or context |
| Associated but not causal | Related finding that is effect rather than cause |

### 14 Item Writing Flaws to Avoid

**Testwiseness Flaws (give clues to correct answer):**
1. **Grammatical cues**: Distractors don't follow grammatically from stem
2. **Logical cues**: Subset of options is collectively exhaustive (A or not-A)
3. **Absolute terms**: "Always" or "never" in some options (usually wrong)
4. **Long correct answer**: Correct option is longer/more specific than others
5. **Word repeats**: Word from stem appears in correct answer only
6. **Convergence**: Correct answer shares most elements with other options

**Irrelevant Difficulty Flaws (make question harder without testing knowledge):**
7. **Complex/double options**: Options are unnecessarily long or compound
8. **Inconsistent numeric data**: Numbers lack consistent formatting
9. **Vague terminology**: Imprecise qualifiers ("rarely," "usually")
10. **Non-parallel language**: Inconsistent grammar across options
11. **Non-logical ordering**: Options lack logical sequence
12. **"None of the above"**: Not recommended
13. **Tricky/misleading stems**: Unnecessarily complex question phrasing
14. **Hinged answers**: Answer depends on other questions

---

## 3. BLOOM'S TAXONOMY FOR QUIZ QUESTIONS

### Cognitive Levels with Examples

#### Level 1: REMEMBER (Recall facts)
- **Verbs**: Define, list, name, identify, recognize, recall, state
- **Target**: ~10-15% of quiz questions
- **When to use**: Foundational vocabulary, key values, basic structures

#### Level 2: UNDERSTAND (Explain concepts)
- **Verbs**: Describe, explain, summarize, classify, compare, interpret, paraphrase
- **Target**: ~20-25% of quiz questions
- **When to use**: Mechanism explanations, concept relationships

#### Level 3: APPLY (Use knowledge in new situations)
- **Verbs**: Calculate, demonstrate, solve, use, implement, predict
- **Target**: ~30-35% of quiz questions (bulk of assessment)
- **When to use**: Scenarios, calculations, predicting outcomes

#### Level 4: ANALYZE (Break down and examine relationships)
- **Verbs**: Compare, differentiate, distinguish, examine, organize, relate
- **Target**: ~20-25% of quiz questions
- **When to use**: Reasoning tasks, relationship analysis, mechanism analysis

#### Level 5: EVALUATE (Justify decisions)
- **Verbs**: Assess, critique, defend, judge, justify, recommend
- **Target**: ~5-10% of quiz questions
- **When to use**: Decision-making, evidence evaluation

#### Level 6: CREATE (Generate new solutions)
- **Verbs**: Design, construct, develop, formulate, propose, synthesize
- **Not typically tested via MCQ** — better for essays, case analyses, projects
- **Target**: 0% of MCQ; use in assignments/discussions instead

### Target Distribution
- Adjust based on course level:
  - **Introductory courses**: Emphasize Levels 2-3 (Understand/Apply)
  - **Intermediate courses**: Emphasize Levels 3-4 (Apply/Analyze)
  - **Advanced courses**: Emphasize Levels 4-5 (Analyze/Evaluate)
- Goal: minimum 40% higher-order items (Level 3+)

---

## 4. RUBRIC DESIGN

### Four Essential Components
1. **Task description**: What the student is being assessed on
2. **Scale**: Rating levels (typically 3-5 levels)
3. **Dimensions/Criteria**: Categories being evaluated
4. **Performance descriptions**: What each level looks like for each criterion

### Recommended Rating Scale Options

**4-Level Scale (most common for coursework):**
| Level | Label | Description Pattern |
|---|---|---|
| 4 | Exemplary | Exceeds expectations; demonstrates mastery with integration |
| 3 | Proficient | Meets expectations; demonstrates competence |
| 2 | Developing | Approaches expectations; demonstrates partial understanding |
| 1 | Beginning | Below expectations; demonstrates minimal understanding |

**Dreyfus Model (for clinical/professional competency):**
Novice → Advanced Beginner → Competent → Proficient → Expert

### Rubric Templates by Assignment Type

#### Case Analysis Rubric (4 criteria)
1. **Core Concepts** (30%): Accuracy and depth of explanation
2. **Application** (25%): Connection between theory and case
3. **Critical Analysis** (25%): Evaluation of evidence, consideration of alternatives
4. **Communication** (20%): Clarity, organization, use of appropriate terminology

#### Discussion Board Rubric (4 criteria)
1. **Initial Post Quality** (30%): Depth of analysis, evidence-based reasoning
2. **Peer Engagement** (25%): Substantive responses to peers, building on ideas
3. **Content Accuracy** (25%): Correctness of concepts and claims
4. **Timeliness & Professionalism** (20%): Meeting deadlines, respectful discourse

#### Research/Report Rubric (5 criteria)
1. **Thesis/Position** (15%): Clear, well-defined, arguable
2. **Evidence/Data** (20%): Accurate collection, appropriate presentation
3. **Analysis** (25%): Correct interpretation, sound reasoning
4. **Explanation** (25%): Mechanism-based or theory-based interpretation
5. **Conclusions** (15%): Summary, limitations, implications

### Critical Thinking Criteria (for any rubric)
| Level | Description |
|---|---|
| Exemplary | Synthesizes multiple perspectives; identifies assumptions; evaluates evidence quality; proposes novel connections |
| Proficient | Analyzes from multiple angles; supports claims with evidence; recognizes limitations |
| Developing | Provides surface-level analysis; relies on single perspective; limited evidence use |
| Beginning | Restates information without analysis; no evidence of critical evaluation |

---

## 5. QUESTION WRITING PROCESS (Step-by-Step)

### Step 1: Start with Learning Objective
- Identify the specific objective being assessed
- Determine the Bloom's level appropriate for that objective
- Choose whether MCQ, essay, or other format best assesses it

### Step 2: Write the Scenario/Stem
- For Apply+ levels: Use a scenario or case
- Include only information needed to answer (plus some context)
- Avoid "red herrings" (deliberately misleading information)
- Make the question answerable from the stem alone

### Step 3: Write the Correct Answer First
- Must be clearly and unambiguously correct
- Should be concise and specific

### Step 4: Write Distractors
- Base each on a specific misconception or common error
- Make all options homogeneous and parallel
- Check that no option is obviously wrong
- Verify correct answer is not conspicuously different

### Step 5: Review for Technical Flaws
- Check all 14 item writing flaws
- Verify grammatical consistency
- Ensure no cueing between questions
- Confirm appropriate Bloom's level
- Test: Can a non-expert eliminate options using test-taking strategy alone?

### Step 6: Write Feedback
- Correct answer feedback: Explain WHY it's correct (reinforce learning)
- Incorrect answer feedback: Explain the specific misconception
- Reference the learning objective and relevant content

---

## 6. DISCIPLINE-SPECIFIC ASSESSMENT TIPS

> The examples below use health sciences scenarios. Adapt the patterns to your discipline by replacing clinical contexts with discipline-appropriate cases, data sets, or scenarios.

### Integrative Question Design
The best questions require integrating knowledge across topics:
- Questions that span multiple modules or concepts
- Scenarios requiring synthesis of several principles
- "What if" variations that test transfer of learning

### High-Yield Question Patterns
| Pattern | Description |
|---|---|
| Mechanism questions | "Which mechanism best explains..." |
| Prediction questions | "What would happen if..." |
| Comparison questions | "How does X differ from Y in this context?" |
| Application questions | "Given this data, which approach is most appropriate?" |
| Integration questions | Combine concepts from multiple modules |
| Error analysis questions | "What is the most likely error in this reasoning?" |
