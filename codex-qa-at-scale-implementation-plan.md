# QA-at-Scale: Implementation Plan

> **System:** Automated Course Quality Auditing for ASU Online
> **Stack:** Railway + CreateAI + Airtable + Cloudflare R2
> **Scope:** 1,000+ courses per semester, zero human-attended compute
> **Date:** 2026-04-08
> **Status:** Design — v2 rewrite incorporating Codex review

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [The Two-System Model](#3-the-two-system-model)
4. [Operational Handoff: QA-at-Scale → Claude Code Remediation](#4-operational-handoff-qa-at-scale--claude-code-remediation)
5. [The RLHF Loop](#5-the-rlhf-loop)
6. [Component Design](#6-component-design)
   - [6.1 Railway Audit Worker](#61-railway-audit-worker)
   - [6.2 CreateAI Integration](#62-createai-integration)
   - [6.3 Airtable Data Model](#63-airtable-data-model)
   - [6.4 Cloudflare R2 Archive](#64-cloudflare-r2-archive)
7. [ID Workflow: New Course Development](#7-id-workflow-new-course-development-phase-5--future)
8. [Workflows](#8-workflows)
   - [8.1 Automated Audit](#81-automated-audit)
   - [8.2 ID Assistant Review](#82-ida-review)
   - [8.3 New Course Dev: ID Review + Submit](#83-new-course-dev-id-review--submit)
   - [8.4 New Course Dev: ID Assistant Validation + QA Gate](#84-new-course-dev-ida-validation--qa-gate)
   - [8.5 RLHF Feedback Aggregation](#85-rlhf-feedback-aggregation)
9. [CreateAI API Integration Details](#9-createai-api-integration-details)
10. [Standards-as-Knowledge-Base (RAG)](#10-standards-as-knowledge-base-rag)
11. [Airtable Schema Deep Dive](#11-airtable-schema-deep-dive)
12. [Migration from Current System](#12-migration-from-current-system)
13. [Phased Rollout](#13-phased-rollout)
14. [Cost Model](#14-cost-model)
15. [Risk Analysis](#15-risk-analysis)
16. [Open Questions](#16-open-questions)

---

## 1. Executive Summary

### Problem

Auditing 1,000+ courses per semester using the current system (IDW-QA Claude Code plugin + Vercel review app + Supabase) requires human-attended compute for every audit session. Each course takes 20-30 minutes with an ID or ID Assistant sitting in Claude Code. At scale, that's 333-500 hours of human labor per audit cycle — and the ID Assistants who do this work already live in Airtable, not in a terminal.

### Solution

Replace the human-attended audit pipeline with an automated one:

- **Railway** runs audit workers that evaluate courses autonomously
- **CreateAI** (ASU's internal AIML platform) provides model-agnostic AI evaluation — Claude, GPT-4o, Llama, etc. — with built-in RAG, vision, structured output, and usage tracking
- **Airtable** serves as both the dashboard and the review interface, built on the existing SCOUT ULTRA table structure ID Assistants already use
- **Cloudflare R2** archives detailed reports and page snapshots

IDs keep Claude Code as a standalone self-audit and remediation tool. It does not connect to this system.

### What This Eliminates

| Current Component | Status |
|---|---|
| Vercel review app (idw-review-app) | **Replaced** by Airtable Interfaces |
| Supabase (DB + auth + RLS) | **Replaced** by Airtable for QA workflow |
| 21 Claude Code skills | **Not needed** — worker runs one evaluation flow |
| 23 Python scripts | **~3-5 scripts** replace the whole set |
| 7 database migrations | **One-time setup script** — Airtable schema generated from `standards.yaml`, then field-map discovery on startup |
| 12+ custom API routes | **Zero** — Airtable automations handle routing |
| Per-user Claude Code setup | **One** CreateAI service token on Railway |
| Custom auth system | **Airtable permissions** (built-in) |

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Airtable (SCOUT ULTRA)                   │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐ │
│  │ QA Admin    │  │ ID Assistant Review  │  │ ID Review            │ │
│  │ Interface   │  │ Interface   │  │ "My Courses" (Ph 5)  │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬───────────┘ │
│         │                │                     │             │
│  ┌──────┴────────────────┴─────────────────────┴───────────┐ │
│  │              Tables + Automations                        │ │
│  │  Courses (173 criterion columns) | Corrections Log      │ │
│  │  Reviewers | Audit Runs                                  │ │
│  └──────────────────────┬──────────────────────────────────┘ │
└─────────────────────────┼────────────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              │    Airtable Automations│
              │  (trigger audits,      │
              │   log corrections,     │
              │   notify reviewers)    │
              └───────────┬───────────┘
                          │
┌─────────────────────────┼────────────────────────────────────┐
│                    Railway (Audit Engine)                      │
│                                                               │
│  ┌──────────┐  ┌───────────────┐  ┌────────────────────────┐ │
│  │ API      │  │ Audit Workers │  │ Cron Scheduler         │ │
│  │ Gateway  │  │ (parallel)    │  │ (nightly / on-demand)  │ │
│  └────┬─────┘  └───────┬───────┘  └────────────┬───────────┘ │
│       │                │                        │             │
│       │         ┌──────┴──────┐                 │             │
│       │         │  Postgres   │                 │             │
│       │         │  Job Queue  │                 │             │
│       │         └─────────────┘                 │             │
│       └────────────────┼────────────────────────┘             │
└────────────────────────┼──────────────────────────────────────┘
                         │
           ┌─────────────┼─────────────┐
           │             │             │
           ▼             ▼             ▼
   ┌──────────────┐ ┌─────────┐ ┌──────────┐
   │  CreateAI    │ │ Canvas  │ │   R2     │
   │  (ASU AIML)  │ │   API   │ │ (private)│
   │              │ │         │ │          │
   │ /query (RAG) │ │ Pages   │ │ Reports  │
   │ /search      │ │ Modules │ │ Snapshots│
   │ /vision      │ │ Quizzes │ │ (signed) │
   └──────────────┘ └─────────┘ └──────────┘
```

### Data Flow

```
1. QA admin assigns course (or cron fires)
     │
2. Airtable automation → Railway API
     │
3. Railway enqueues job in Postgres (durable — survives restarts)
     │
4. Worker picks up job:
     ├── Fetches course content from Canvas API
     ├── Runs deterministic checks locally
     ├── Evaluates AI criteria via CreateAI /query (with RAG)
     ├── Pre-fills criterion columns (Yes/No/N/A) on the course row in Airtable
     ├── Writes standard-level ratings + auto-generated notes
     ├── Generates HTML report → R2 (private, signed URL)
     └── Updates course status → "Audit Complete"
     │
5. Airtable automation notifies assigned ID Assistant
     │
6. ID Assistant opens their existing Airtable Interface:
     ├── Criterion dropdowns are pre-filled by AI (instead of blank)
     ├── ID Assistant verifies each dropdown — changes any they disagree with
     ├── Any changed cell triggers an automation → append row to Corrections Log
     └── ID Assistant clicks "Mark Review Complete"
     │
7. Recurring: Course status → "Complete"
   New course dev (Phase 5): ID Assistant validates Col B after ID has submitted → QA gate → "Launch Approved"
     │
8. RLHF signal = Corrections Log entries (ai_baseline_value vs. new_value per correction)
```

---

## 3. The Two-System Model

Two completely independent systems for two different user profiles.

### System A: ID Self-Service (Claude Code — existing)

| Aspect | Detail |
|---|---|
| **Users** | Instructional Designers (course builders) |
| **Tool** | IDW-QA Claude Code plugin (local) |
| **Purpose** | Self-audit courses during development, remediate issues |
| **AI access** | Claude Code license (per-user) |
| **Interface** | Terminal / conversational |
| **Results** | Local — in conversation, `reports/`, optional Supabase |
| **Remediation** | Full staging workflow → push to Canvas |
| **Connected to QA pipeline?** | **No** — standalone tool |

### System B: QA-at-Scale Pipeline (new — this plan)

| Aspect | Detail |
|---|---|
| **Users** | QA admins, ID Assistants, IDs (as reviewers, not operators) |
| **Tool** | Railway workers + Airtable Interfaces |
| **Purpose** | Automated audit of 1,000+ courses, human review, RLHF |
| **AI access** | CreateAI service token (one for the whole pipeline) |
| **Interface** | Airtable (everyone already uses it) |
| **Results** | Airtable (live), R2 (archived reports) |
| **Remediation** | IDs fix in Canvas manually, system re-audits to verify |
| **Connected to Claude Code?** | **No** — IDs can use Claude Code separately if they want |

### Why They Stay Separate

1. **Different users, different needs.** IDs need interactive remediation tools. QA needs batch automation.
2. **Different access models.** Claude Code requires per-user installation + license. The QA pipeline needs one service token.
3. **Different cadences.** IDs audit during course development (ad hoc). QA audits at scale on schedule (recurring).
4. **Coupling adds risk.** If the QA pipeline breaks, IDs can still self-audit. If Claude Code is unavailable, QA still runs.
5. **Future bridge is possible.** If we ever want to connect them (e.g., ID self-audit results feed into QA tracking), we add a sync — not a dependency.

---

## 4. Operational Handoff: QA-at-Scale → Claude Code Remediation

The two systems work side by side with a **human handoff**, not a technical dependency.

### Priority

**First priority:** recurring audits for the QA team and ID Assistants. Phases 0-4 ship the automated audit + ID Assistant review loop.

**Later, when clarified by QA leadership:** the Instructional Designer workflow can be formalized. Until then, IDs may use Claude Code as an optional remediation tool, but it is not part of the required v1-v4 operating model.

### Division of Responsibility

| System | Owns | Does Not Own |
|---|---|---|
| **QA-at-Scale** | Scheduled audits, AI pre-fill, ID Assistant review, QA dashboards, RLHF correction data | Editing Canvas, staging HTML, preview/push workflow |
| **Claude Code / IDW-QA plugin** | Deep investigation, remediation, staging, preview, approval, push to Canvas | Batch recurring audits, queueing, QA dashboarding |

### Operational Flow

```
1. QA-at-Scale audits a course
   → Writes criterion values to Airtable
   → Generates report + evidence links

2. ID Assistant reviews in Airtable
   → Confirms or corrects values
   → Marks review complete

3. If remediation is needed
   → Human opens the current Claude Code plugin
   → Uses criterion IDs, Canvas links, and report evidence as the remediation brief

4. Claude Code remediates the course
   → Investigates the specific issue
   → Uses the existing staging / preview / approval / push workflow

5. QA-at-Scale re-audits later
   → Verifies whether the criterion now passes
```

### Handoff Artifact

The new system does not push work directly into Claude Code. Instead, Airtable gives the human enough context to start remediation quickly:

- Course row with current criterion values
- Canvas course link
- Report URL
- Criterion IDs that failed or were corrected
- ID Assistant note (when present)

This is intentionally lightweight. The handoff is "open Claude Code with this context," not "synchronize two state machines."

### Why This Stays Loose

The staging and push rules in the current plugin are the safety layer for real Canvas changes. Rebuilding that logic inside the at-scale audit system would collapse the two systems back into one large, coupled workflow.

The audit system should stay read-only. The remediation system should stay human-attended.

### Future Clarification Path

When the QA team is ready to define the ID workflow more precisely, Phase 5 can add a more formal handoff process. Until then:

- The required workflow is QA admin + ID Assistant recurring audits
- The optional workflow is ID remediation via Claude Code
- Re-audit is the verification mechanism between the two systems

---

## 5. The RLHF Loop

The RLHF signal comes from two different workflows that share the same Corrections Log:

### Workflow C — Recurring Audits (Phases 0-4)

Two perspectives: AI evaluates Col B, ID Assistant reviews Col B, QA oversees ID Assistants.

| Role | What They See | What They Do | Signal They Provide |
|---|---|---|---|
| **AI** (CreateAI) | Course HTML, structure, content | Evaluate Col B criteria (structural/existence) | Initial verdict + evidence + confidence |
| **ID Assistant** | AI verdict + evidence for Col B | Verify Col B criteria — change dropdowns if AI was wrong | Whether the AI's Col B evaluation was correct |
| **QA** (admin) | Col B values + ID Assistant corrections | Review ID Assistant's work; can directly correct Col B values if needed | Highest-authority ground truth for RLHF |

### Workflow A — New Course Development (Phase 5)

The course-building ID reviews both Col B and Col C. They are the **only** person who validates Col C — QA and ID Assistants do not have the course-specific knowledge to judge qualitative criteria.

| Role | What They See | What They Do | Signal They Provide |
|---|---|---|---|
| **AI** (CreateAI) | Course HTML, structure, content | Evaluate Col B + Col C criteria | Initial verdict + evidence + confidence |
| **ID** (course builder) | AI verdict for Col B + Col C | Review both — sole validator of Col C, can correct Col B | Design context, pedagogical judgment |
| **ID Assistant** | Col B values (after ID review) | Validate Col B only | Structural/existence verification |
| **QA** (admin) | Col B values + ID Assistant work; Col C visible (read-only) | Review ID Assistant's Col B work; can directly correct Col B values; does NOT validate Col C | Highest-authority ground truth for Col B |

### Feedback Signal Matrix (Col B — both workflows)

| AI Says | ID Assistant Says | Signal | Action |
|---|---|---|---|
| Fail | Agrees (leaves as-is) | **AI confirmed correct** | No action |
| Fail | Changes to Pass | **AI was wrong** | Correction Log → retrain |
| Pass | Changes to Fail | **AI missed it** | Correction Log → retrain |
| Pass | Agrees (leaves as-is) | **AI confirmed correct** | No action |

### Feedback Signal Matrix (Col C — new course dev only)

| AI Says | ID Says | Signal | Action |
|---|---|---|---|
| Fail | Agrees (leaves as-is) | **AI confirmed correct** | ID remediates before launch |
| Fail | Changes to Pass | **AI was wrong** — valid design choice | Correction Log → teach AI the pattern |
| Pass | Changes to Fail | **AI missed it** | Correction Log → retrain; ID remediates |
| Pass | Agrees (leaves as-is) | **AI confirmed correct** | No action |

### RLHF Data Collection

In v1 (AI + ID Assistant only), the RLHF signal comes from the **Corrections Log** — an append-only table where each row represents an ID Assistant changing an AI-prefilled value:

```
Corrections Log row (created automatically when any reviewer changes a dropdown):
{
  "criterion_id": "B-04.1",
  "audit_run_id": "run_2026-04-08_001",
  "course_id": "12345",
  "ai_baseline_value": "No",
  "previous_value": "No",
  "new_value": "Yes",
  "reviewer": "jane.doe@asu.edu",
  "reviewer_role": "ID Assistant",
  "note": "Getting Started page exists but is named differently — 'Welcome to Module 3'",
  "ai_model": "claude3_5_sonnet",
  "prompt_version": "v1.2.0",
  "timestamp": "2026-04-08T14:30:00Z"
}
```

No entry is created for unchanged cells — marking "Review Complete" attests that unchanged values were reviewed and confirmed.

In Phase 5 (new course dev), an ID correcting a Col C criterion would produce:
```
{
  "ai_baseline_value": "No",      // AI originally said No
  "previous_value": "No",          // No one else reviewed Col C before the ID
  "new_value": "Yes",              // ID says it passes
  "reviewer_role": "ID",
  "note": "Objectives use discipline-specific verbs appropriate for lab courses — AI flagged them incorrectly"
}
```

An ID correcting a Col B criterion (overriding ID Assistant) would produce:
```
{
  "ai_baseline_value": "No",      // AI originally said No
  "previous_value": "Yes",         // ID Assistant had changed it to Yes
  "new_value": "No",               // ID changed it back to No
  "reviewer_role": "ID",
  "note": "This module intentionally omits Getting Started — it's a lab continuation"
}
```

The `ai_baseline_value` anchors every correction to the AI's original judgment, regardless of who reviewed it since.

Over time, aggregation of the Corrections Log reveals:
- Which criteria the AI consistently gets wrong (retrain prompts)
- Which model performs best per criterion type (compare correction rates by AI Model)
- Which standards have the most corrections (may need enriched RAG context)
- Confidence thresholds where human review is/isn't needed

---

## 6. Component Design

### 6.1 Railway Audit Worker

The core of the system. A Python service that receives audit requests, fetches course content, evaluates criteria, and writes results.

#### File Structure

```
qa-at-scale/
├── railway.toml              # Railway config
├── Dockerfile                # Python 3.12 + Playwright
├── requirements.txt          # requests, airtable-python, boto3
├── .env.example              # Template for Railway env vars
│
├── src/
│   ├── main.py               # FastAPI app — API gateway (enqueues jobs)
│   ├── worker.py             # Core audit orchestration (pulls from queue)
│   ├── job_queue.py          # Postgres-backed durable job queue
│   ├── canvas_client.py      # Canvas API (read-only: pages, modules, quizzes, assignments)
│   ├── createai_client.py    # CreateAI API wrapper (query, search, vision)
│   ├── airtable_client.py    # Airtable read/write (course rows, field-map discovery)
│   ├── r2_client.py          # R2 upload (reports, snapshots — private, signed URLs)
│   ├── evaluator.py          # Criterion evaluation logic (deterministic + AI)
│   ├── report_generator.py   # HTML report builder
│   └── models.py             # Pydantic models for findings, criteria, etc.
│
├── standards/                 # Source files → uploaded to CreateAI as knowledge base
│   ├── standards.yaml         # 25 standards, 173 criteria (WHAT to check)
│   ├── standards_enrichment.yaml  # Expectations, examples, considerations, research (HOW to check)
│   ├── canvas-standards.md    # ASU Canvas course design standards prose
│   └── upload_kb.py           # One-time script: merges YAML + uploads to CreateAI collection
│
├── config/
│   └── model_routing.yaml    # Which model to use per criterion type
│
└── tests/
    ├── test_evaluator.py
    ├── test_canvas_client.py
    └── test_createai_client.py
```

#### Worker Flow (`worker.py`)

```python
async def audit_course(course_id: str, canvas_domain: str, canvas_token: str,
                       standards_to_check: list[str] | None = None) -> AuditResult:
    """
    Main audit orchestration.

    1. Fetch course structure from Canvas
    2. For each module, fetch all pages/items
    3. Evaluate each applicable criterion
    4. Aggregate results
    5. Write to Airtable + R2
    """

    # 1. Fetch course tree
    course = await canvas.get_course(course_id)
    modules = await canvas.get_modules_with_items(course_id)

    # 2. Collect all evaluable content
    pages = []
    for module in modules:
        for item in module.items:
            if item.type in ("Page", "Assignment", "Discussion", "Quiz"):
                content = await canvas.get_item_content(course_id, item)
                pages.append(content)

    # 3. Evaluate criteria (parallel)
    findings = []
    criteria = load_criteria(standards_to_check)

    # Batch by type for efficiency
    deterministic_criteria = [c for c in criteria if c.check_type == "deterministic"]
    ai_criteria = [c for c in criteria if c.check_type in ("ai", "hybrid")]

    # Deterministic: run locally, fast
    for criterion in deterministic_criteria:
        result = evaluator.check_deterministic(criterion, pages, course)
        findings.extend(result)

    # AI: batch to CreateAI (parallel requests, respecting rate limits)
    ai_tasks = []
    for criterion in ai_criteria:
        task = evaluator.check_with_ai(criterion, pages, course)
        ai_tasks.append(task)
    ai_results = await asyncio.gather(*ai_tasks)
    findings.extend(flatten(ai_results))

    # 4. Write results
    audit_result = aggregate_findings(course, findings)

    # Pre-fill criterion columns on the course row (Yes/No/N/A dropdowns)
    field_map = await airtable.get_field_map()  # criterion_id -> field_name
    await airtable.prefill_course_row(course_id, audit_result, field_map)

    # Upload evidence + report to R2 (private, signed URLs)
    evidence_url = await r2.upload_evidence(audit_result)
    report_url = await r2.upload_report(audit_result)

    # Update course metadata
    await airtable.update_course_status(
        course_id, audit_status="Audit Complete",
        review_status="Not Started", report_url=report_url
    )

    return audit_result
```

#### Airtable Write Batching

Each course audit writes ~130+ fields to a single Airtable row (criterion values + standard ratings + notes + metadata). Airtable's API has constraints:

- **10 records per PATCH** — not an issue (we write one row per course), but relevant for batch status updates
- **5 requests/second** per base — the real bottleneck at batch scale
- **Field payload size** — a single record with 130+ fields is a large payload; split into chunks if timeouts occur

The worker writes results in two Airtable API calls per course:

```python
# airtable_client.py — batched write
async def prefill_course_row(course_id, audit_result, field_map):
    """Write all criterion values + metadata in minimal API calls."""

    # Call 1: All criterion dropdowns + standard ratings + notes
    # (single PATCH to one record — Airtable allows all fields in one call)
    fields = {}
    for finding in audit_result.findings:
        field_name = field_map[finding.criterion_id]
        fields[field_name] = finding.verdict  # "Yes" / "No" / "N/A"
    for standard in audit_result.standard_summaries:
        fields[f"Standard {standard.id}... — Rating"] = standard.rating
        fields[f"Standard {standard.id}... — Notes"] = standard.notes
    await airtable.update_record(course_id, fields)

    # Call 2: Metadata (status, report URL, criterion models JSON, etc.)
    # Separated so criterion writes succeed even if metadata write fails
    await airtable.update_record(course_id, {
        "Audit Status": "Audit Complete",
        "Review Status": "Not Started",
        "Report URL": report_url,
        "Criterion Models": json.dumps(model_map),
        "Prompt Version": PROMPT_VERSION,
        "Last Audit Date": datetime.utcnow().isoformat(),
    })
```

At batch scale (100+ courses), workers must respect the 5 req/s base-wide limit. The job queue naturally throttles this — each worker processes one course at a time, and 10 concurrent workers produce ~20 Airtable calls across the batch (2 per course, staggered by processing time). If bursts occur, the worker adds a `asyncio.sleep(0.2)` between Airtable calls.

#### API Gateway (`main.py`)

The API enqueues jobs into a Postgres-backed durable queue. Workers pull from the queue independently. If a worker crashes or Railway redeploys, unfinished jobs remain in the queue and are picked up on restart.

```python
from fastapi import FastAPI

app = FastAPI()

@app.post("/audit")
async def trigger_audit(request: AuditRequest):
    """Triggered by Airtable automation or cron. Enqueues a durable job."""
    job_id = await job_queue.enqueue(
        task="audit_course",
        payload={
            "course_id": request.course_id,
            "canvas_domain": request.canvas_domain,
            "standards": request.standards,
        }
    )
    return {"status": "queued", "job_id": job_id, "course_id": request.course_id}

@app.post("/audit/batch")
async def trigger_batch(request: BatchRequest):
    """Audit multiple courses. Each course is a separate durable job."""
    job_ids = []
    for course_id in request.course_ids:
        job_id = await job_queue.enqueue(
            task="audit_course",
            payload={"course_id": course_id, ...}
        )
        job_ids.append(job_id)
    return {"status": "queued", "count": len(job_ids)}

@app.get("/health")
async def health():
    queue_depth = await job_queue.pending_count()
    return {"status": "ok", "pending_jobs": queue_depth}
```

#### Durable Job Queue (`job_queue.py`)

Postgres-backed. Railway provides Postgres natively — no extra infrastructure.

```python
# Jobs table schema (created on first deploy):
# id: UUID, task: TEXT, payload: JSONB, status: TEXT (pending/running/complete/failed),
# created_at: TIMESTAMP, started_at: TIMESTAMP, completed_at: TIMESTAMP,
# worker_id: TEXT, error: TEXT, attempts: INT

async def enqueue(task: str, payload: dict) -> str:
    """Insert a job row. Returns job ID."""
    ...

async def dequeue(worker_id: str) -> Job | None:
    """Atomically claim the next pending job (SELECT ... FOR UPDATE SKIP LOCKED)."""
    ...

async def complete(job_id: str, result: dict):
    """Mark job complete with result metadata."""
    ...

async def fail(job_id: str, error: str):
    """Mark job failed. Will be retried if attempts < max_retries."""
    ...
```

Workers run as a separate Railway service (or the same service with a `--worker` flag) polling the queue. `SELECT ... FOR UPDATE SKIP LOCKED` ensures multiple workers don't grab the same job.

#### Environment Variables (Railway)

```
# Canvas API (read-only service account)
CANVAS_TOKEN=<service account token>
CANVAS_DOMAIN=canvas.asu.edu

# CreateAI
CREATEAI_TOKEN=<service token>
CREATEAI_BASE_URL=https://api-main.aiml.asu.edu
CREATEAI_PROJECT_ID=<project id>

# Airtable
AIRTABLE_TOKEN=<personal access token>
AIRTABLE_BASE_ID=<SCOUT ULTRA base id>

# R2
R2_ACCOUNT_ID=<cloudflare account>
R2_ACCESS_KEY_ID=<key>
R2_SECRET_ACCESS_KEY=<secret>
R2_BUCKET=qa-audit-reports

# Postgres (Railway-provided — durable job queue)
DATABASE_URL=<railway postgres connection string>

# Worker config
MAX_CONCURRENT_AUDITS=10
AUDIT_TIMEOUT_SECONDS=600
```

### 6.2 CreateAI Integration

#### Model Routing Strategy

Not every criterion needs the same model. Route by check type for cost efficiency and quality.

```yaml
# config/model_routing.yaml
deterministic:
  # No AI needed — run locally
  engine: local
  description: "Existence checks, structural validation"

ai_structural:
  # Simpler AI checks (heading hierarchy, link patterns)
  provider: aws
  model: nova-micro
  temperature: 0.1
  description: "Structural checks needing some interpretation"

ai_qualitative:
  # Judgment calls (alignment, pedagogy, design quality)
  provider: aws
  model: claude3_5_sonnet
  temperature: 0.1
  thinking_level: MEDIUM
  description: "Qualitative evaluation requiring pedagogical judgment"

ai_vision:
  # Visual accessibility and layout checks
  provider: openai
  model: gpt4o
  temperature: 0.1
  description: "Screenshot-based visual evaluation"

criterion_overrides:
  # Per-criterion model preferences (discovered via RLHF)
  C-01.1: { provider: aws, model: claude3_5_sonnet, thinking_level: HIGH }
  B-14.1: { engine: local }
```

#### Query Template (Criterion Evaluation)

```python
async def check_with_ai(criterion, pages, course):
    """Evaluate a single criterion via CreateAI with RAG."""

    # Build context: relevant page content for this criterion
    page_context = build_context(criterion, pages)

    payload = {
        "query": f"""Evaluate this Canvas course content against criterion {criterion.id}.

Criterion: {criterion.text}
Standard: {criterion.standard_name}

Course content to evaluate:
{page_context}

Respond with your evaluation.""",

        "model_provider": criterion.model_config.provider,
        "model_name": criterion.model_config.model,
        "model_params": {
            "temperature": 0.1,
            "system_prompt": EVALUATOR_SYSTEM_PROMPT,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "criterion_evaluation",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "verdict": {
                                "type": "string",
                                "enum": ["pass", "fail", "not_auditable"]
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1
                            },
                            "evidence": {
                                "type": "string",
                                "description": "Specific content that supports the verdict"
                            },
                            "location": {
                                "type": "string",
                                "description": "Where in the course this was found"
                            },
                            "suggestion": {
                                "type": "string",
                                "description": "What should be changed if failing"
                            }
                        },
                        "required": ["verdict", "confidence", "evidence", "location"],
                        "additionalProperties": False
                    }
                }
            }
        },
        "enable_search": True,
        "search_params": {
            "collection": STANDARDS_COLLECTION_ID,
            "retrieval_type": "chunk",
            "top_k": 5,
            "tags": [f"standard_{criterion.standard_id}"],
            "output_fields": ["content", "source_name", "tags"]
        },
        "response_format": {"type": "json"}
    }

    response = await createai.query(payload)
    return parse_criterion_result(criterion, response)
```

#### Vision Query (Accessibility Checks)

```python
async def check_visual_accessibility(page_url, screenshot_b64):
    """Use CreateAI vision to evaluate visual accessibility."""

    payload = {
        "endpoint": "vision",
        "request_source": "override_params",
        "query": """Evaluate this Canvas page screenshot for WCAG 2.1 AA compliance.
Check: color contrast ratios, heading visual hierarchy, image alt text indicators,
link distinguishability, text readability, layout consistency with ASU branding.""",
        "image_file": f"data:image/png;base64,{screenshot_b64}",
        "model_provider": "openai",
        "model_name": "gpt4o",
        "model_params": {
            "system_prompt": "You are an accessibility auditor...",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "visual_accessibility",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "issues": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string"},
                                        "severity": {"enum": ["critical","major","minor"]},
                                        "description": {"type": "string"},
                                        "location": {"type": "string"}
                                    }
                                }
                            },
                            "overall_score": {"type": "number"}
                        }
                    }
                }
            }
        },
        "response_format": {"type": "json"}
    }
    return await createai.query(payload)
```

### 6.3 Airtable Data Model

The data model follows the SCOUT ULTRA pattern: **criteria are columns, not rows.** One row per course, criterion columns containing Yes/No/N/A dropdown values. The AI pre-fills these columns; reviewers correct them in-place. An append-only Corrections Log captures the RLHF signal.

**Phasing:** Phases 0-4 populate only the 124 Col B columns (ID Assistant-reviewed). The 49 Col C columns are created at setup but remain blank until Phase 5, when IDs join the review loop — because ID Assistants only check Col B, and Col C (qualitative/judgment) requires ID-level review.

#### Tables

**Table 1: Courses** (SCOUT ULTRA format — one row per course, criteria as columns)

This is both the audit result store AND the ID Assistant review interface. The AI writes to the same dropdown columns that ID Assistants have always used.

| Field | Type | Description |
|---|---|---|
| **Metadata** | | |
| Course Name | Text | Course title from Canvas |
| Course Code | Text | e.g., "BIO 101" |
| Course ID | Number | Canvas course ID |
| Term | Text | e.g., "2026 Fall A" |
| Template Version | Text | e.g., "2026A" |
| Canvas URL | URL | Link to course in Canvas |
| **Assignment + Review State** | | |
| Assigned ID Assistant | Collaborator | Who reviews this course |
| Assigned ID | Collaborator | Who built this course (Phase 5) |
| Audit Status | Single Select | Pending / Scheduled / Queued / Auditing / Audit Complete / Submitted for Review / Revisions Needed / Launch Approved / Complete |
| Review Status | Single Select | Not Started / In Progress / Complete |
| Reviewed By | Collaborator | Which ID Assistant completed the review |
| Review Date | Date | When ID Assistant marked review complete |
| Last Audit Date | Date | When the worker last ran |
| Audit Run ID | Text | UUID linking to Audit Runs table |
| Criterion Models | Long Text | JSON map of `criterion_id → model` (e.g., `{"B-04.1": "local", "C-01.1": "claude3_5_sonnet", "C-01.2": "gpt4o"}`) — set by worker, read by correction automation to resolve per-criterion model |
| Prompt Version | Text | Git SHA or version tag of evaluator prompts — set by worker, read by correction automation |
| Report URL | URL | R2 signed URL to full HTML report |
| Overall Score | Formula | `COUNTALL("Yes") / (COUNTALL("Yes") + COUNTALL("No")) × 100` — excludes blank (unevaluated) and N/A fields so the score is valid across phases (Phases 1-4: only Col B populated; Phase 5+: Col B + Col C) |
| **Criterion Columns (173 total)** | | |
| B-01.1 {label} | Single Select | Yes / No / N/A — AI pre-fills, ID Assistant corrects |
| B-01.2 {label} | Single Select | Yes / No / N/A |
| ... (all 124 Col B criteria) | | |
| C-01.1 {label} | Single Select | Yes / No / N/A (Phase 5 — ships with ID workflow; ID Assistants do not review Col C) |
| ... (all 49 Col C criteria) | | |
| **Standard Summaries (25 total)** | | |
| Standard 01 — Rating | Single Select | Met / Partially Met / Not Met / Not Auditable |
| Standard 01 — Notes | Long Text | Auto-generated summary of issues |
| ... (repeat for all 25 standards) | | |

**Total column count:** ~173 criteria + 25 ratings + 25 notes + ~15 metadata = ~238 columns. Airtable Business allows 500 fields per table — well within limits.

**Table 2: Corrections Log** (append-only — the RLHF artifact)

One row per correction by any reviewer (ID Assistant, ID, or QA Admin). Created whenever someone changes a criterion dropdown value after the AI pre-fill. This is the training data for prompt improvement.

Field names are **role-neutral** so the same table cleanly represents all correction types: ID Assistant correcting an AI pre-fill on Col B, an ID correcting AI pre-fills on Col B + Col C (new course dev), or a QA Admin overriding any value during oversight or launch gate review.

| Field | Type | Description |
|---|---|---|
| Correction ID | Autonumber | Unique identifier |
| Course | Link (Courses) | Which course |
| Criterion ID | Text | e.g., "B-04.1" |
| Standard ID | Text | e.g., "04" |
| Audit Run ID | Text | Which audit run this course was part of |
| AI Baseline Value | Single Select | Yes / No / N/A — what the AI originally wrote (always the AI's value, regardless of who is correcting) |
| Previous Value | Single Select | Yes / No / N/A — the value in the cell immediately before this correction (may equal AI Baseline if ID Assistant is first corrector, or may differ if a later reviewer is correcting after an earlier one) |
| New Value | Single Select | Yes / No / N/A — the value the reviewer set |
| Reviewer | Collaborator | Who made this correction |
| Reviewer Role | Single Select | ID Assistant / ID / QA Admin |
| Note | Long Text | Why the value was changed (required) |
| AI Model | Text | Which model evaluated this specific criterion — resolved per criterion from the course row's `Criterion Models` JSON (e.g., `"local"`, `"claude3_5_sonnet"`, `"gpt4o"`) |
| Prompt Version | Text | Git SHA or version tag (from course row `Prompt Version` field) |
| Timestamp | DateTime | When the correction was made |

**Why three value fields:**
- `AI Baseline Value` is always the AI's original pre-fill — the anchor for RLHF. Even after multiple corrections, you can trace back to what the AI said.
- `Previous Value` is what was in the cell before this specific correction — needed to understand the correction chain (e.g., AI said No → ID Assistant changed to Yes → ID changed back to No).
- `New Value` is what the reviewer set.

**Row count at scale:** At 20% disagreement rate, ~25 corrections per course per ID Assistant review cycle (Col B only). In Phase 5 with ID + QA corrections on Col B + Col C, assume ~20 additional corrections per course. 1,000 courses × 45 = 45,000 rows per audit cycle. Well within Airtable's 100K limit. Older cycles can be archived.

**Table 3: Reviewers**

| Field | Type | Description |
|---|---|---|
| Name | Text | Full name |
| Email | Email | ASU email |
| Role | Single Select | QA Admin / ID Assistant / ID |
| Active | Checkbox | Currently active |

**Table 4: Audit Runs**

One row per audit execution (batch or individual). Links to R2 for detailed per-criterion evidence that doesn't fit in Airtable columns.

| Field | Type | Description |
|---|---|---|
| Run ID | Text | UUID from Railway |
| Trigger | Single Select | Cron / Manual / Re-audit |
| Courses Audited | Number | Count |
| Started | DateTime | |
| Completed | DateTime | |
| Pass Rate | Number | Percentage of criteria met across all courses |
| Total Cost | Currency | Accumulated from CreateAI usage metrics |
| Errors | Long Text | Any courses that failed to audit |
| Evidence Archive | URL | R2 signed URL to per-criterion evidence JSON for this run |
| Criteria Evaluated | Long Text | JSON summary: per-criterion counts of evaluated/yes/no/na across all courses in this run (RLHF denominator) |

#### Where Per-Criterion Evidence Lives

The Airtable criterion columns store the verdict (Yes/No/N/A) but not the evidence, confidence, or suggestions. That detail lives in R2:

```
R2: {course_id}/{run_id}/evidence.json
{
  "B-04.1": {
    "verdict": "No",
    "confidence": 0.92,
    "evidence": "Getting Started page missing from Module 3",
    "location": "Module 3",
    "suggestion": "Add a Getting Started page following the template structure",
    "model": "claude3_5_sonnet"
  },
  ...
}
```

The HTML report (also in R2) renders this evidence in a readable format. The Airtable `Report URL` field links to it. ID Assistants can click through to see the full evidence when reviewing a criterion — but they don't need to leave Airtable for routine agree/disagree decisions.

#### Review State Semantics

The `Audit Status` and `Review Status` fields work together to eliminate ambiguity about what's been reviewed:

| Audit Status | Review Status | Meaning | Workflow | Phase |
|---|---|---|---|---|
| Pending | — | Course not yet audited | Both | 0+ |
| Scheduled | — | Course queued for next cron-triggered batch | Recurring | 2+ |
| Queued | — | Job enqueued in Railway | Both | 0+ |
| Auditing | — | Worker is processing | Both | 0+ |
| Audit Complete | Not Started | AI has pre-filled criteria. Reviewer hasn't touched it yet. | Both | 1+ |
| Audit Complete | In Progress | Reviewer has started (first edit or "Start Review") | Both | 1+ |
| Audit Complete | Complete | Reviewer clicked "Mark Review Complete" | Recurring | 1+ |
| Complete | Complete | Recurring audit cycle finished (ID Assistant reviewed Col B) | Recurring | 1+ |
| Submitted for Review | — | ID reviewed Col B + Col C, submitted for ID Assistant/QA review | New course dev | 5+ |
| Revisions Needed | — | QA pushed back to ID — Col B issues found by ID Assistant | New course dev | 5+ |
| Launch Approved | — | Col B passed ID Assistant + QA review. Course can launch. | New course dev | 5+ |

**"In Progress" transition:** Set automatically when either (a) the ID Assistant makes their first criterion dropdown change on the course (the same field-change automation that logs corrections also sets `Review Status = In Progress` if currently `Not Started`), or (b) the ID Assistant clicks a "Start Review" button in the Interface. This gives the QA dashboard visibility into which courses are actively being reviewed vs. untouched.

**"Mark Review Complete"** is an explicit action by the ID Assistant — a button in the Airtable Interface that sets `Review Status = Complete`, `Reviewed By = current user`, `Review Date = now`. This is the attestation that all unchanged cells were reviewed and confirmed. Without this step, the course stays in "Audit Complete" and the QA dashboard shows it as pending review.

### 6.4 Cloudflare R2 Archive

#### Bucket Structure

```
qa-audit-reports/                          # PRIVATE bucket — no public access
├── {course_id}/
│   ├── {audit_run_id}/
│   │   ├── report.html                   # Full audit report (human-readable)
│   │   ├── evidence.json                 # Per-criterion evidence, confidence, model (machine-readable)
│   │   ├── snapshots/
│   │   │   ├── {page_slug}.html          # Raw page HTML at audit time
│   │   │   ├── {page_slug}.png           # Screenshot at audit time (Phase 4+)
│   │   │   └── ...
│   │   └── metadata.json                 # Audit metadata (date, duration, cost, models used)
│   └── latest/                           # Copy of most recent run's files
└── index.json                             # Global index of all audits
```

#### Access — Private with Signed URLs

Course audit data must not be publicly accessible. R2 bucket is **private by default**.

- **Signed URLs** with 24-hour expiry are generated by the Railway worker at audit time and written to the Airtable `Report URL` field. ID Assistants click the link in Airtable → opens the report directly.
- **URL refresh:** A Railway endpoint or cron regenerates expired URLs on demand. If an ID Assistant clicks an expired link, the Airtable automation calls Railway to get a fresh signed URL.
- **No public-read access.** No custom domain serving reports openly.

```python
# r2_client.py — generate signed URL
import boto3
from botocore.config import Config

s3 = boto3.client('s3',
    endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    config=Config(signature_version='s3v4')
)

def get_signed_url(key: str, expires_in: int = 86400) -> str:
    """Generate a pre-signed URL for a private R2 object. Default 24h expiry."""
    return s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': R2_BUCKET, 'Key': key},
        ExpiresIn=expires_in
    )
```

#### Evidence Freshness

If a course is audited in January and reviewed in March, the ID Assistant is reviewing stale evidence. The course may have changed, the AI verdicts may be wrong, and trust erodes. Three mitigations:

**1. Audit age indicator (Phase 2+)**

The ID Assistant Review Interface displays "Audited X days ago" prominently on each course record. Thresholds:
- **≤7 days:** Normal — no indicator
- **8-30 days:** Yellow flag — "Evidence may be stale"
- **>30 days:** Red flag — "Re-audit required before review"

At >30 days, the ID Assistant cannot click "Mark Review Complete" — the Interface enforces a re-audit first. Implemented as an Airtable Interface conditional rule on the `Last Audit Date` field.

**2. Canvas change detection (Phase 4+)**

On re-audit, the worker diffs fetched course HTML against the stored snapshots in R2:

```python
async def detect_content_changes(course_id, run_id, pages):
    """Compare current course content to stored snapshots from latest audit."""
    latest_snapshots = await r2.get_latest_snapshots(course_id)
    changed_pages = []
    for page in pages:
        stored = latest_snapshots.get(page.slug)
        if stored is None or content_diff_significant(page.html, stored):
            changed_pages.append(page.slug)
    return changed_pages
```

If significant changes are detected, the worker sets a `Content Changed Since Last Audit` flag on the course row. The ID Assistant Interface highlights these courses — the ID Assistant knows to look more carefully, or QA triggers a full fresh audit.

**3. Re-audit cadence policy (Phase 4+)**

A Railway cron enforces automatic re-audit scheduling:
- Courses with `Audit Status = Complete` and `Last Audit Date` older than 90 days automatically re-enter the queue as `Scheduled`
- QA admin can configure the cadence per term or course type
- Prevents evidence from going stale between audit cycles without manual intervention

---

## 7. ID Workflow: New Course Development (Phase 5 — Future)

> **Timing:** Deferred to Phase 5 (~2 months out). New course development doesn't end until then. The immediate priority is recurring audits (Phases 0-4).
>
> **Context:** This is Workflow A from the existing IDW-QA design. The ID who builds the course self-audits, remediates, then submits for QA review. The new system automates the audit step — the ID reviews AI-prefilled criteria instead of manually evaluating them.
>
> IDs can still use Claude Code for self-audits and remediation independently — that tool is unchanged and unconnected to this system.

### How It Works

The new system supports the existing new course development workflow:

```
1. ID builds course in Canvas
     ↓
2. ID triggers audit via Airtable (or QA triggers on their behalf)
     → Worker pre-fills Col B + Col C criteria on the course row
     ↓
3. ID reviews ALL criteria in Airtable Interface:
     - Col B (structural): AI-prefilled, ID corrects any errors
     - Col C (qualitative): AI-prefilled, ID is the ONLY human validator
     - Each correction → Corrections Log (same automation as ID Assistant corrections)
     ↓
4. ID remediates issues found (in Canvas directly, or via Claude Code)
     ↓
5. ID re-audits (repeat steps 2-4 until satisfied)
     ↓
6. ID submits for review
     → Audit Status → "Submitted for Review"
     ↓
7. QA assigns ID Assistant to validate Col B
     → ID Assistant reviews Col B dropdowns (same as recurring audit workflow)
     → Col C is visible to ID Assistant and QA but NOT validated by them
     ↓
8. QA reviews ID Assistant's Col B work
     → If Col B passes: launch gate approved
     → If Col B has issues: push back to ID to remediate, re-submit
```

### What IDs See (Airtable Interface: "My Courses")

An Airtable Interface filtered to courses where `Assigned ID = {current user}`.

**Course Dashboard View:**
- List of their courses with audit status
- Overall score per course
- Link to full report in R2

**Course Review View:**
When they click into a course, they see all criterion dropdowns:
- **Col B dropdowns:** AI-prefilled. ID reviews and corrects before submitting.
- **Col C dropdowns:** AI-prefilled. The ID is the **only** person who validates Col C. QA and ID Assistants can view Col C values but do not validate them — they lack the course-specific knowledge.
- Each correction requires a note (provides context for RLHF)
- Report link to R2 for full evidence
- Canvas link per criterion for verification

### What IDs Do NOT Do in This System

- Run the AI evaluation themselves (the worker does this)
- Install any software (it's Airtable, in the browser)
- Push changes to Canvas through this system (they remediate in Canvas directly or via Claude Code)

### Col C Ownership

**Col C lives and dies with the course-building ID.** This is by design:

- Col C criteria are qualitative/judgment calls (e.g., "Does each course-level objective indicate tasks relating to the course focus?")
- Only the ID who built the course has the context to validate these
- QA team IDs manage ID Assistants — they don't have course-specific knowledge
- ID Assistants check structural/existence criteria (Col B) — they don't have ID-level pedagogical knowledge
- QA and ID Assistants can **view** Col C values for context, but they do not validate or correct them

### Launch Gate

New course development is **launch-gated**:
- Col B must pass ID Assistant validation + QA review
- Col C must be reviewed by the course-building ID (AI-only verdicts are not sufficient for launch)
- If the ID hasn't reviewed Col C, the course cannot launch
- There is no timeout that auto-completes Col C — it blocks until the ID reviews it
- QA admin can see which courses are blocked on ID review and nudge accordingly

---

## 8. Workflows

> **Phase priority:** Workflows 8.1 and 8.2 ship first (Phases 0-2). These cover recurring audits — the daily need. Workflows 8.3 and 8.4 ship in Phase 5 when the new course dev workflow is added.

### 8.1 Automated Audit (Phase 0-1 — ships first)

```
Trigger: Airtable automation (Audit Status → "Queued")
   OR: Railway cron (nightly batch of all courses with Audit Status = "Scheduled")
   OR: Manual — QA admin clicks "Run Audit" button in Airtable Interface

   → Railway API /audit (or /audit/batch)
   → Job enqueued in Postgres (durable)
   → Worker picks up job:
     1. Fetch course content from Canvas API
     2. Evaluate criteria:
        - Phases 1-4: 124 Col B criteria only (deterministic/hybrid) — ID Assistant-reviewed
        - Phase 5+: + 49 Col C criteria (AI via CreateAI with RAG) — ID-reviewed
     3. Pre-fill criterion columns on the course row in Airtable (Yes/No/N/A)
     4. Write standard-level ratings + auto-generated notes
     5. Upload evidence.json + report.html to R2 (private)
     6. Write signed report URL to course row
     7. Set Audit Status → "Audit Complete", Review Status → "Not Started"
   → Airtable automation notifies assigned ID Assistant
```

### 8.2 ID Assistant Review (Phase 1 — ships first)

The ID Assistant workflow is nearly identical to today. They open the same Airtable Interface, see the same criterion dropdowns. The only difference: **the dropdowns are pre-filled by the AI instead of blank.**

```
Trigger: Airtable automation (Audit Status = "Audit Complete")
   → ID Assistant gets notification
   → ID Assistant opens Airtable Interface → "My Reviews" → selects course

   For each criterion dropdown:
     → If AI got it right: ID Assistant leaves the value as-is (no action needed)
     → If AI got it wrong: ID Assistant changes the dropdown value
       → Airtable automation fires on field change:
         - Appends a row to Corrections Log with:
           audit_run_id, course_id, criterion_id, ai_baseline_value,
           previous_value, new_value, reviewer, reviewer_role, ai_model,
           prompt_version, timestamp
         - Note required (brief explanation of why AI was wrong)

   When done reviewing all criteria:
     → ID Assistant clicks "Mark Review Complete" button in Interface
     → Sets Review Status → "Complete", Reviewed By, Review Date
     → Audit Status → "Complete" (v1, Phases 1-4)
     → New course dev (Phase 5): ID has already reviewed and submitted; ID Assistant validates Col B as part of launch gate
```

**What "Mark Review Complete" means:** The ID Assistant attests that they have reviewed all criterion values. Any unchanged cells are confirmed agreements. Without this step, the course stays in "Audit Complete / Not Started" and shows as pending in the QA dashboard.

**Recurring audits (Phases 1-4+):** The ID Assistant is the final human reviewer for Col B. The criterion values on the course row (AI-prefilled, ID Assistant-corrected) are the final Col B verdicts. No Col C, no ID involvement.

**New course dev (Phase 5+):** ID Assistants validate Col B after the course-building ID has reviewed Col B + Col C and submitted for review. Same ID Assistant workflow, just positioned after the ID's review in the chain.

### 8.3 New Course Dev: ID Review + Submit (Phase 5 — future)

> This is Workflow A — the new course development audit. The course-building ID reviews the AI's evaluation, remediates, then submits for ID Assistant/QA review.

```
Trigger: ID triggers audit on their course (or QA triggers on their behalf)
   → Worker pre-fills Col B + Col C on the course row
   → Audit Status → "Audit Complete"

   ID opens Airtable Interface → "My Courses" → selects course
   → Reviews Col B dropdowns (AI-prefilled) — corrects any errors
   → Reviews Col C dropdowns (AI-prefilled) — sole human validator
   → All corrections → Corrections Log (reviewer_role = "ID")

   ID remediates issues in Canvas (directly or via Claude Code)
   ID can re-trigger audit to verify fixes

   When satisfied:
   → ID clicks "Submit for Review"
   → Audit Status → "Submitted for Review"
   → QA assigns ID Assistant to validate Col B
```

### 8.4 New Course Dev: ID Assistant Validation + QA Gate (Phase 5 — future)

> After the ID submits, the same Col B review chain from recurring audits applies. QA and ID Assistants do NOT validate Col C.

```
Trigger: Audit Status = "Submitted for Review"
   → QA assigns ID Assistant
   → ID Assistant reviews Col B dropdowns (same workflow as recurring audits — 8.2)
     - Col C is visible but read-only for ID Assistants
   → ID Assistant clicks "Mark Review Complete"

   QA reviews ID Assistant's Col B work:
   → QA may directly correct Col B dropdown values if needed
     → Corrections Log row appended (reviewer_role = "QA Admin")
   → If Col B passes: Audit Status → "Launch Approved"
   → If Col B has issues: Audit Status → "Revisions Needed" → notify ID
     → ID remediates → re-submits → cycle repeats

   Col C is NOT reviewed by QA or ID Assistant.
   Col C values (set by ID) are visible for context but not validated.
```

All corrections flow into the same Corrections Log, distinguished by `reviewer_role`. ID Assistant corrections on Col B drive the primary RLHF signal (both recurring and new course dev). ID corrections on Col C produce a separate signal unique to the new course dev workflow.

### 8.5 RLHF Feedback Aggregation (Phase 3+)

The Corrections Log IS the RLHF dataset. No separate aggregation pipeline is needed in v1.

#### The Denominator Problem

The Corrections Log only records *corrections* (ID Assistant changed a value). To compute accuracy rates, you also need to know *how many times each criterion was evaluated* (the denominator). Without this, you know "B-04.1 was corrected 15 times" but not whether that's 15 out of 50 (30% correction rate) or 15 out of 500 (3%).

**Solution:** The Audit Runs table stores a `Criteria Evaluated` JSON field — a summary of how many courses each criterion was evaluated on in that run:

```json
// Audit Runs → Criteria Evaluated field (written by worker at end of run)
{
  "B-04.1": {
    "evaluated": 100, "yes": 82, "no": 15, "na": 3,
    "model": "local"
  },
  "C-01.1": {
    "evaluated": 100, "yes": 70, "no": 25, "na": 5,
    "model": "claude3_5_sonnet"
  },
  "C-01.2": {
    "evaluated": 100, "yes": 88, "no": 10, "na": 2,
    "model": "gpt4o"
  },
  ...
}
```

Each criterion entry includes the `model` used to evaluate it in that run. This provides the per-model denominator needed for model comparison.

For A/B testing (Phase 3), where the same criterion runs through two models on different course subsets, the worker records both:

```json
// A/B test run: half courses evaluated by each model
"C-01.1": {
  "evaluated": 100,
  "by_model": {
    "claude3_5_sonnet": {"evaluated": 50, "yes": 35, "no": 12, "na": 3},
    "gpt4o": {"evaluated": 50, "yes": 38, "no": 10, "na": 2}
  }
}
```

This is a per-run snapshot produced by the worker after pre-filling all course rows. Written once, never modified.

#### Accuracy Calculation

```
Per-criterion correction rate (for run R):
  corrections = COUNT(Corrections Log WHERE criterion_id = X AND audit_run_id = R)
  evaluated   = Audit Runs[R].criteria_evaluated[X].evaluated
  rate        = corrections / evaluated

Per-model correction rate (for run R):
  corrections = COUNT(Corrections Log WHERE ai_model = M AND audit_run_id = R)
  evaluated   = SUM(Audit Runs[R].criteria_evaluated[*].by_model[M].evaluated)
               (or .evaluated where .model = M for non-A/B runs)
  rate        = corrections / evaluated

Per-criterion accuracy (across all runs):
  total_corrections = COUNT(Corrections Log WHERE criterion_id = X)
  total_evaluated   = SUM(Audit Runs[*].criteria_evaluated[X].evaluated)
  accuracy          = 1 - (total_corrections / total_evaluated)
```

For v1 (no A/B testing), the per-model denominator is simply the count of criteria evaluated by that model across all courses. The `model` field on each criterion entry provides this directly. A/B testing in Phase 3 uses the `by_model` breakdown.

For v1, a Railway cron computes these rates by reading `Criteria Evaluated` JSON from Audit Runs + correction counts from the Corrections Log, and writes a summary to a dashboard view. Airtable formula capabilities are insufficient for cross-table JSON aggregation at this level.

#### Dashboard

```
QA Admin Interface → "RLHF Dashboard" view:
  → Per-criterion correction rate (worst-performing first)
  → Per-model correction rate (compare Claude vs GPT-4o vs Nova)
  → Per-standard correction rate
  → ID Assistant notes aggregated (common themes in why AI was wrong)
  → Criteria with >20% correction rate flagged for prompt review

Action:
  → Update model_routing.yaml to switch models for underperforming criteria
  → Re-upload refined standard descriptions to CreateAI knowledge base
  → Phase 5+: include ID correction data (Col B + Col C) for richer signal
```

**Why no separate RLHF Log table in v1:** The Corrections Log + Audit Runs `Criteria Evaluated` field together capture everything needed — corrections (numerator) and exposures (denominator). A separate RLHF Log would duplicate this data.

#### Analytics Trajectory

Airtable is the operational layer, not the permanent analytics home. The RLHF dashboard will outgrow Airtable's capabilities as the team wants richer slicing (model × criterion × audit type × time period × reviewer role). Expected progression:

- **Phase 3:** Railway cron computes summary stats from Corrections Log + Audit Runs, writes to a dashboard summary table in Airtable. Sufficient for initial prompt improvement cycles.
- **Phase 4+:** If the team wants interactive drill-downs or trend analysis, move analytics to a Postgres view on the existing Railway Postgres. The Corrections Log and Audit Runs data can be synced or queried directly. A lightweight dashboard (Metabase, Retool, or a static HTML report generated by the cron) replaces the Airtable dashboard view for analytics. Airtable remains the operational interface for reviews and status tracking.
- **No migration required:** The Corrections Log stays in Airtable regardless — it's the operational artifact. Analytics reads from it but doesn't need to own it.

---

## 9. CreateAI API Integration Details

### Authentication

```python
# Service token — one token for the whole pipeline
headers = {
    "Authorization": f"Bearer {os.environ['CREATEAI_TOKEN']}",
    "Content-Type": "application/json"
}
```

Service tokens don't require `model_name` or `model_provider` in every request (project defaults apply), but we override them per criterion for model routing.

### Rate Limiting Strategy

- Service token rate limit: **750,000 tokens/minute**
- Average criterion evaluation: ~2,000 tokens (input + output)
- Theoretical max: ~375 evaluations/minute
- With 10 concurrent workers processing different courses: ~37 evaluations/minute per worker
- Well within limits even at scale

### Cost Tracking

Every CreateAI response includes `usage_metric`:

```json
{
  "input_token_count": 1250,
  "output_token_count": 180,
  "total_token_cost": 0.00715
}
```

The worker accumulates these per audit run and writes the total to the Audit Runs table. Over time, we have precise cost-per-course and cost-per-criterion data.

### Error Handling

```python
async def query_with_retry(payload, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = await createai.query(payload)
            if response.status_code == 200:
                return response.json()
            if response.status_code == 429:  # Rate limited
                await asyncio.sleep(2 ** attempt)
                continue
            if response.status_code >= 500:  # Server error
                await asyncio.sleep(2 ** attempt)
                continue
            # 4xx client error — don't retry
            log.error(f"CreateAI error {response.status_code}: {response.text}")
            return None
        except Exception as e:
            log.error(f"CreateAI exception: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
    return None
```

---

## 10. Standards-as-Knowledge-Base (RAG)

### The Two Standards Files

The audit knowledge base is built from two complementary YAML files:

**`standards.yaml`** — The criteria checklist (WHAT to check)
- 25 standards, 173 criteria (124 Col B + 49 Col C)
- Each criterion has: ID, text, check_type, reviewer_tier
- Tells the AI exactly what question to answer (e.g., "Are the course outcomes present?")

**`standards_enrichment.yaml`** — The evaluation context (HOW to check)
- Same 25 standards, enriched with 6 fields per standard:

| Field | Purpose | AI Use |
|---|---|---|
| `measurable_criteria` | What to actually measure | Grounds the AI in observable evidence |
| `expectations` | What good looks like | Helps the AI distinguish pass vs. fail |
| `considerations` | Edge cases, nuances, exceptions | Prevents false positives on valid design choices |
| `examples` | Concrete passing examples | Gives the AI reference points for comparison |
| `research` | Citations and evidence | Can be surfaced in reports for faculty/stakeholder buy-in |
| `source_title` | Human-readable standard name | Used in report labels |

**Why both matter:** `standards.yaml` alone would produce checkbox-style audits ("is X present? yes/no"). The enrichment YAML transforms evaluation into informed judgment. For example:

- **Without enrichment (Standard 01):** "Are course objectives present?" → AI checks if objectives exist on the page
- **With enrichment (Standard 01):** AI also knows that objectives should use measurable Bloom's verbs, should avoid "understand/know/realize," should indicate tasks relating to course focus, and can reference specific examples of good vs. bad objectives. The `considerations` field warns that objectives "should not be treated as a task list" — preventing the AI from flagging well-structured objectives that happen to look like lists.

### Setup (One-Time)

Upload standards documents to a CreateAI knowledge base collection, structured for precise retrieval:

**Collection 1: Standards + Enrichment (primary)**

Each standard is uploaded as a single document containing both the criteria from `standards.yaml` and the enrichment from `standards_enrichment.yaml`, tagged for filtered retrieval:

```python
# Upload script: merge standards.yaml + enrichment into tagged documents
for standard in standards:
    enrichment = enrichment_data.get(standard.id)
    document = f"""
    Standard {standard.id}: {standard.name}
    Category: {standard.category}
    Description: {standard.description}

    CRITERIA:
    {format_criteria(standard.criteria)}

    MEASURABLE CRITERIA:
    {format_list(enrichment.measurable_criteria)}

    EXPECTATIONS:
    {format_list(enrichment.expectations)}

    CONSIDERATIONS (edge cases — do NOT flag these as failures):
    {format_list(enrichment.considerations)}

    EXAMPLES OF MEETING THIS STANDARD:
    {format_list(enrichment.examples)}

    SUPPORTING RESEARCH:
    {format_list(enrichment.research)}
    """
    upload_to_collection(
        document=document,
        tags=[f"standard_{standard.id}"],
        metadata={"standard_id": standard.id, "category": standard.category}
    )
```

**Collection 2: Design References (supplementary)**

- `canvas-standards.md` — ASU Canvas course design standards prose
- `page-design.md` — Page design system (for visual/structural checks)
- `assessment-best-practices.md` — Assessment design guidelines
- `instructional-design.md` — ID frameworks (UDL, backward design, Mayer)

Tagged by topic for retrieval when evaluating specific standard categories.

### How RAG Improves Evaluation

Without RAG:
- Stuff all 173 criteria + enrichment into the system prompt (~40K+ tokens)
- Model has to find the relevant standard among 25
- Context window fills up, less room for course content
- Enrichment details get lost in the noise

With RAG:
- System prompt stays small (~500 tokens of evaluation instructions)
- `enable_search` pulls just the relevant standard + its enrichment (1-3 chunks, ~1,500 tokens)
- The AI gets measurable_criteria, expectations, considerations, and examples for exactly the standard it's evaluating
- More context window available for course content
- The `considerations` field prevents false positives by teaching the AI about valid exceptions

### Query with RAG Example

```python
payload = {
    "query": f"Evaluate this Canvas course content against the standard retrieved below.\n\nCourse content:\n{page_html[:3000]}",
    "model_params": {
        "system_prompt": """You are an ASU course quality auditor. Evaluate the provided content
against the standard retrieved from the knowledge base.

Use the MEASURABLE CRITERIA to determine what to look for.
Use the EXPECTATIONS to determine what good looks like.
Use the CONSIDERATIONS to avoid false positives on valid design choices.
Use the EXAMPLES as reference points for comparison.

Return structured JSON with your verdict, evidence, and confidence.""",
        "temperature": 0.1
    },
    "enable_search": True,
    "search_params": {
        "collection": STANDARDS_COLLECTION_ID,
        "retrieval_type": "chunk",
        "top_k": 3,
        "tags": [f"standard_{criterion.standard_id}"],
        "output_fields": ["content", "source_name", "tags"],
        "prompt_mode": "custom",
        "search_prompt": "Use the following standard definition, expectations, and examples as the evaluation criteria:\n\n{data}\n\nNow evaluate this course content:\n{query}"
    },
    "response_format": {"type": "json"}
}
```

### Research Citations in Reports

The enrichment YAML includes research citations for each standard. The report generator can surface these when a standard fails:

```
Standard 04: Consistent Layout — NOT MET
Issue: Module 3 uses a different page structure than Modules 1-2.

Why this matters: "Consistent layouts reduce cognitive load and improve
accessibility for diverse learners" (CAST, 2025). Research shows students
have positive perceptions of course template consistency and find it
benefits their learning (Todoran et al., 2019).
```

This transforms audit reports from "you failed this checkbox" into "here's why this matters, backed by research" — critical for faculty communication.

---

## 11. Airtable Schema Deep Dive

### Interface Design

**Interface 1: QA Admin Dashboard**
- All courses with status filters (Pending / Scheduled / Audit Complete / Complete / Submitted for Review / Launch Approved)
- Batch audit trigger (select courses → "Run Audit" button calls Railway API)
- Review progress: which ID Assistants have completed reviews, which are pending
- New course dev status: which courses are awaiting ID review, ID Assistant validation, or QA gate
- RLHF metrics view: Corrections Log grouped by criterion, showing correction rates
- Audit run history with cost tracking (from Audit Runs table)

**Interface 2: ID Assistant Review** (same Interface ID Assistants use today — criteria as dropdowns)
- Courses assigned to current ID Assistant, filtered to:
  - Recurring: Audit Status = "Audit Complete"
  - New course dev (Phase 5): Audit Status = "Submitted for Review"
- Course record opens with Col B criterion dropdowns pre-filled by AI
- Col C columns: hidden for recurring audits; visible but read-only for new course dev (Phase 5)
- ID Assistant changes Col B dropdowns they disagree with (triggers Corrections Log entry)
- "Mark Review Complete" button (sets Review Status, Reviewed By, Review Date)
- Report link (R2 signed URL) for full evidence when needed
- **Audit age indicator** (Phase 2+): shows "Audited X days ago" prominently; flags courses >7 days old, requires re-audit if >30 days
- **Review focus mode** (Phase 3+): hides high-confidence criteria (>0.95) by default, showing only uncertain or historically-corrected criteria. ID Assistant reviews 20-30 flagged criteria, then clicks "Confirm remaining" to attest the rest. Reduces 124-dropdown fatigue to a focused review.
- **Re-audit diff view** (Phase 4+): for courses audited before, shows only criteria whose values *changed* since the prior run. ID Assistant reviews the delta, not the full set.

**Interface 3: ID Review ("My Courses")** — Phase 5 (new course dev only)
- Courses where current user is Assigned ID
- Filtered to Audit Status = "Audit Complete" (ID reviews before submitting)
- Course record shows Col B + Col C dropdowns (AI-prefilled)
- ID corrects dropdowns → Corrections Log entries (reviewer_role = "ID")
- "Submit for Review" button → Audit Status = "Submitted for Review"

### Automations

**Recurring audits (Phases 1-4+):**

| Trigger | Condition | Action |
|---|---|---|
| Audit Status → "Queued" | — | POST to Railway /audit API |
| Audit Status → "Audit Complete" | Assigned ID Assistant exists, Audit Type = Recurring | Send email notification to ID Assistant |
| Criterion column value changed | Audit Status in ("Audit Complete", "Submitted for Review", "Revisions Needed") | Append row to Corrections Log with: `ai_baseline_value`, `previous_value`, `new_value`, `reviewer`, `reviewer_role` (ID Assistant / ID / QA Admin), + `Audit Run ID` and `Prompt Version` from course row. `AI Model` resolved per criterion from the course row's `Criterion Models` JSON. |
| Review Status → "Complete" | Audit Type = Recurring | Set Audit Status → "Complete" |
| Audit Status → "Complete" or "Launch Approved" | — | Recalculate Overall Score from criterion columns |

**New course dev (Phase 5+):**

| Trigger | Condition | Action |
|---|---|---|
| Audit Status → "Audit Complete" | Assigned ID exists, Audit Type = New Course Dev | Notify assigned ID to review |
| Audit Status → "Submitted for Review" | — | Notify QA to assign ID Assistant |
| ID Assistant Review Status → "Complete" | Audit Type = New Course Dev | Notify QA for launch gate review |
| QA approves | — | Set Audit Status → "Launch Approved" |
| QA rejects Col B | — | Set Audit Status → "Revisions Needed"; notify ID |

### Schema Setup and Field Discovery

**The 173 criteria are new.** They don't exist in the current SCOUT ULTRA testing table. The new Airtable base is built from scratch.

**One-time setup:** A setup script uses the Airtable Metadata API to programmatically create columns from `standards.yaml`:

```python
# scripts/setup_airtable_schema.py — run once to create the base structure
for standard in standards:
    for criterion in standard.criteria:
        create_field(
            table_id=COURSES_TABLE_ID,
            name=f"{criterion.id} {criterion.short_label}",
            type="singleSelect",
            options={"choices": [
                {"name": "Yes", "color": "greenBright"},
                {"name": "No", "color": "redBright"},
                {"name": "N/A", "color": "grayBright"}
            ]}
        )
    create_field(
        table_id=COURSES_TABLE_ID,
        name=f"Standard {standard.id}. {standard.name} — Rating",
        type="singleSelect",
        options={"choices": [
            {"name": "Met"}, {"name": "Partially Met"},
            {"name": "Not Met"}, {"name": "Not Auditable"}
        ]}
    )
    create_field(
        table_id=COURSES_TABLE_ID,
        name=f"Standard {standard.id}. {standard.name} — Notes",
        type="multilineText"
    )
```

**Ongoing field discovery:** Column names include human labels (e.g., `B-04.1 Layout: Getting Started`) that can be edited in the Airtable UI. The worker cannot hardcode field names. On startup, it discovers the mapping:

```python
# airtable_client.py — cached field map, same pattern as existing airtable_sync.py
def build_field_map(token, base_id, standards_path="standards/standards.yaml") -> dict[str, str]:
    """Fetch table schema, return criterion_id -> field_name mapping.
    e.g., {"B-04.1": "B-04.1 Layout: Getting Started", ...}
    Cached for the duration of the audit run.
    Validates against standards.yaml on startup — fails loudly if any
    expected criterion is missing or duplicated."""
    resp = requests.get(
        f"https://api.airtable.com/v0/meta/bases/{base_id}/tables",
        headers={"Authorization": f"Bearer {token}"}
    )
    fields = extract_course_table_fields(resp.json())
    field_map = {
        fname.split(" ", 1)[0]: fname
        for fname in fields
        if fname.startswith(("B-", "C-"))
    }

    # Validate: every criterion in standards.yaml must map to exactly one field
    expected_ids = load_criterion_ids(standards_path)
    missing = expected_ids - field_map.keys()
    if missing:
        raise RuntimeError(
            f"Airtable field map is missing {len(missing)} criteria: {sorted(missing)[:10]}... "
            f"Run setup_airtable_schema.py or check for renamed columns."
        )
    return field_map
```

This is the same approach used in the existing `airtable_sync.py` (line 86). It handles renamed columns, reordered fields, and human-edited labels gracefully. The startup validation ensures that if someone renames a column and removes the criterion ID prefix, the worker fails immediately with a clear error instead of silently skipping that criterion.

**Migration path:** The current SCOUT ULTRA testing table continues in use for the existing manual process. The new base runs in parallel. Once validated, the new base becomes the production standard.

---

## 12. Migration from Current System

### What Migrates

| From | To | How |
|---|---|---|
| `criterion_evaluator.py` logic | `evaluator.py` in Railway worker | Port deterministic checks; replace inline Claude calls with CreateAI |
| `canvas_api.py` (read operations) | `canvas_client.py` in Railway worker | Strip to read-only; remove staging/push/backup |
| `airtable_sync.py` field discovery pattern | `airtable_client.py` in Railway worker | Same Metadata API approach; new base with new columns |
| `standards.yaml` + `standards_enrichment.yaml` | CreateAI knowledge base collection | Merge into per-standard documents, tag, upload |

### What Doesn't Migrate

- Vercel review app (replaced by Airtable Interfaces — ID Assistants already work in Airtable)
- Supabase (no separate database — Airtable is the store, R2 is the archive)
- All 21 skills (QA pipeline runs one evaluation flow)
- Staging workflow (QA audits are read-only — nothing writes to Canvas)
- Push/backup/verify scripts (nothing writes to Canvas)
- Claude Code setup gate (one service token on Railway)
- Custom auth system (Airtable permissions)
- Role gating scripts (Airtable Interface filtering)
- Remediation tracker (IDs fix in Canvas manually, re-audit verifies)

### What's New (not ported from current system)

- Postgres-backed durable job queue (Railway-native)
- Corrections Log table (append-only RLHF artifact — no equivalent in current system)
- Review state model (Audit Status + Review Status + Mark Complete)
- R2 evidence archive with signed URLs
- Model routing (different CreateAI models per criterion type)

### Timeline

> Priority: Recurring audits are happening daily. ID Assistant workflow is the bottleneck. Ship the ID Assistant pipeline first, add the new course dev workflow when course development wraps up (~2 months).

| Week | Current System | New System | Milestone |
|---|---|---|---|
| Week 1 | Still primary | Phase 0: POC — Railway + CreateAI + Canvas + Postgres queue | Worker audits 1 course, writes to Airtable |
| Week 2-3 | ID Assistants still manual | Phase 1: Col B pre-fill + ID Assistant review in Airtable | ID Assistants verify AI-prefilled dropdowns |
| Week 4 | Begin ID Assistant transition | Phase 2: QA admin + batch ops | QA runs 50-course batches |
| Week 5-6 | ID Assistants fully on new system | Phase 3: RLHF dashboard + model optimization (Col B) | Correction rates visible, prompt improvements |
| Week 7-8 | Vercel app deprecated | Phase 4: Scale + vision | 200+ courses/week, visual a11y checks |
| ~Month 3 | Claude Code = ID self-service only | Phase 5: New course dev workflow + Col C | IDs review Col B + Col C, submit for ID Assistant/QA gate |

**Key transition point:** After Phase 1 (Week 3), ID Assistants stop filling out criteria from scratch. They review AI-prefilled dropdowns in the same Airtable Interface they already use. This is the moment the system pays for itself.

---

## 13. Phased Rollout

> **Priority context:** Recurring course audits happen daily. New course development doesn't wrap up for ~2 months. The ID Assistant/QA workflow for recurring audits is the immediate need. The new course dev workflow (ID review + submit + Col C) is a future enhancement.

### Phase 0: Proof of Concept (Week 1)

**Goal:** Railway worker can audit one course and write results to an Airtable course row.

**Why first:** Prove the full loop — Canvas fetch → CreateAI evaluate → Airtable pre-fill — before adding review workflows.

- [ ] Create Railway project with Postgres add-on
- [ ] Deploy skeleton FastAPI app + durable job queue (`job_queue.py`)
- [ ] Create CreateAI project + obtain service token
- [ ] Build and upload merged knowledge base to CreateAI collection:
  - Merge `standards.yaml` + `standards_enrichment.yaml` into per-standard documents
  - Tag each document by standard ID for filtered retrieval
- [ ] Implement `canvas_client.py` (read-only: course, modules, pages)
- [ ] Implement `createai_client.py` (query wrapper with retry + rate limit handling)
- [ ] Implement `evaluator.py` with 10 deterministic criteria + 5 AI criteria
- [ ] Run setup script to create new Airtable base with criterion columns from YAML
- [ ] Implement `airtable_client.py` with field-map discovery (Metadata API)
- [ ] Worker pre-fills criterion columns on one course row
- [ ] **Verify:** Audit one known course, compare AI-prefilled values to a human-completed row

**Exit criteria:** Worker produces correct verdicts for 15 criteria and writes them to Airtable column dropdowns on a course row.

### Phase 1: ID Assistant Pipeline — Col B Pre-fill + Review (Week 2-3)

**Goal:** All 124 Col B criteria automated and pre-filled. ID Assistants verify AI output in the same Airtable Interface they already use, with Corrections Log capturing RLHF signal from day one.

**Why second:** Col B is what ID Assistants spend most time on. Pre-filling dropdowns instead of leaving them blank saves hours per course immediately.

- [ ] Port all 124 Col B deterministic/hybrid criteria from `criterion_evaluator.py`
- [ ] Worker writes per-criterion Yes/No/N/A to column dropdowns on course rows
- [ ] Worker writes standard-level ratings (Met/Partially Met/Not Met)
- [ ] Worker writes auto-generated notes per standard
- [ ] Worker sets Audit Status → "Audit Complete", Review Status → "Not Started"
- [ ] Create **Corrections Log** table (append-only: audit_run_id, course, criterion_id, standard_id, ai_baseline_value, previous_value, new_value, reviewer, reviewer_role, note, ai_model (from Criterion Models JSON), prompt_version, timestamp)
- [ ] Create Reviewers table (ID Assistant roster)
- [ ] Build automation: criterion column changed while Audit Status = "Audit Complete" → append Corrections Log row
- [ ] Build **ID Assistant Review Interface** in Airtable:
  - Courses assigned to current ID Assistant, filtered to Audit Status = "Audit Complete"
  - Course record opens with pre-filled criterion dropdowns
  - "Mark Review Complete" button (sets Review Status, Reviewed By, Review Date)
- [ ] Build automations:
  - Audit Status → "Queued" → POST to Railway API
  - Audit Status → "Audit Complete" → notify ID Assistant
  - Review Status → "Complete" → set Audit Status → "Complete"
- [ ] **Verify:** 10 courses audited. ID Assistants review pre-filled dropdowns, correct errors, mark complete. Corrections Log captures all changes.

**Exit criteria:** ID Assistant reviews a full Col B audit by verifying pre-filled dropdowns in <15 minutes (vs. 60+ minutes filling from scratch). Corrections Log has entries for every ID Assistant change.

### Phase 2: QA Admin + Batch Operations (Week 4)

**Goal:** QA team can assign courses, trigger batch audits, and monitor progress.

- [ ] Build **QA Admin Interface** in Airtable:
  - All courses with status filters
  - Batch audit trigger (select courses → automation calls Railway /audit/batch)
  - ID Assistant assignment (assign ID Assistant to course record)
  - Review progress dashboard (how many audited, reviewed, pending)
- [ ] Create Audit Runs table (track batch jobs: count, duration, cost, errors)
- [ ] Implement `/audit/batch` endpoint on Railway
- [ ] Implement R2 upload: evidence.json + report.html per course (private, signed URLs)
- [ ] Add Report URL to course rows (signed URL, clickable from Interface)
- [ ] Build scheduling: Railway cron for nightly batch of "Scheduled" courses
- [ ] Build error handling: courses that fail audit → logged in Audit Runs, QA notified
- [ ] Add **audit age indicator** to ID Assistant Review Interface: "Audited X days ago" shown on course record; flag if >7 days; require re-audit if >30 days
- [ ] Decide on Airtable automation batching strategy (see Automation Capacity Math in Risk Analysis): per-field-change corrections vs. batched "Save Review" action. **Must resolve before Phase 4.**
- [ ] **Verify:** QA admin triggers batch of 50 courses, monitors progress, assigns ID Assistants

**Exit criteria:** QA can manage 50+ courses/week from their Airtable Interface.

### Phase 3: RLHF Dashboard + Model Optimization (Week 5-6)

**Goal:** Surface RLHF data from Col B Corrections Log. Optimize model routing and prompts based on ID Assistant correction patterns.

**Why now:** By this point, Phases 1-2 have produced real ID Assistant correction data across 50+ courses. This is enough signal to identify which Col B criteria the AI gets wrong most often and which models perform best.

**Col C is NOT added in this phase.** ID Assistants only review Col B. Col C (qualitative/judgment) requires ID-level review and ships in Phase 5 alongside the ID workflow.

- [ ] Build **RLHF Dashboard** view in QA Admin Interface:
  - Per-criterion correction rate for Col B (from Corrections Log, grouped by criterion_id)
  - Per-model correction rate (grouped by AI Model field)
  - Per-standard correction rate
  - Criteria with >20% correction rate flagged for prompt review
  - ID Assistant notes aggregated for common themes (why AI was wrong)
- [ ] Implement model routing for Col B hybrid/AI criteria:
  - Different models per criterion type based on correction data
  - Update `model_routing.yaml` with initial assignments
- [ ] A/B test models on Col B: same criteria through different models, compare correction rates
- [ ] Implement confidence thresholds:
  - High confidence (>0.95): ID Assistant can skim
  - Low confidence (<0.7): highlighted in Interface for careful review
- [ ] Build **review focus mode** in ID Assistant Interface: hide high-confidence criteria by default; show only uncertain or historically high-correction-rate criteria. ID Assistant reviews the flagged subset, clicks "Confirm remaining" to attest the rest. Target: reduce active review from 124 dropdowns to ~20-30.
- [ ] First round of prompt refinement based on ID Assistant correction patterns
- [ ] Re-upload refined standard descriptions to CreateAI knowledge base if needed
- [ ] **Verify:** 50+ courses with RLHF dashboard showing accuracy data. At least one prompt improvement cycle completed.

**Exit criteria:** Correction rates visible per Col B criterion and per model. First prompt improvements demonstrate measurable accuracy gains on Col B.

### Phase 4: Scale + Vision (Week 7-8)

**Goal:** Handle 1,000+ courses per semester. Add visual accessibility checks.

- [ ] Load test: 100 concurrent audits via Railway workers
- [ ] Implement re-audit: only re-evaluate criteria that previously failed (after ID remediates)
- [ ] Build **re-audit diff view** in ID Assistant Interface: for re-audited courses, show only criteria whose values changed since the prior run. ID Assistant reviews the delta, not the full set.
- [ ] Add Playwright to Railway worker for Canvas page screenshots
- [ ] Implement visual accessibility checks via CreateAI /vision endpoint
- [ ] Implement cost dashboard (per-course, per-criterion, per-model costs from CreateAI usage metrics)
- [ ] Implement **Canvas change detection**: worker diffs fetched HTML against stored R2 snapshots on re-audit; sets `Content Changed Since Last Audit` flag on course row if significant changes detected
- [ ] Implement **re-audit cadence policy**: Railway cron automatically sets courses with `Audit Status = Complete` and `Last Audit Date` >90 days to `Scheduled` for re-audit
- [ ] Monitor and optimize: Airtable automation limits, R2 storage, CreateAI token usage
- [ ] If RLHF dashboard outgrows Airtable views: migrate analytics to Postgres views on Railway Postgres + lightweight dashboard (Metabase/Retool/static HTML). Airtable remains operational layer.
- [ ] Archive strategy: move findings older than 1 semester to archive base
- [ ] Document: ID Assistant training guide, QA admin runbook, Railway ops playbook

**Exit criteria:** System handles 200+ courses/week without manual intervention. Cost per course is tracked and optimized. Stale evidence is automatically flagged or re-audited.

### Phase 5: New Course Development Workflow + Col C (Future — ~2 months out)

**Goal:** Support Workflow A (new course dev) in the new system. Two things ship together: (1) the ID audit/review/submit workflow, and (2) Col C criteria — because the course-building ID is the only person who validates Col C.

**Why together:** Col C requires the course-building ID's pedagogical judgment. QA and ID Assistants can view Col C values but do not validate them — they lack course-specific knowledge. There's no point evaluating Col C without an ID reviewing it.

**Why last:** New course development doesn't end for ~2 months. By Phase 5, the recurring audit pipeline (Col B) is stable, the ID Assistant workflow is proven, and the RLHF dashboard has real correction data.

- [ ] **Col C AI evaluation:**
  - Implement AI evaluation for all 49 Col C criteria via CreateAI /query with RAG
  - Apply model routing lessons from Phase 3 (best models for qualitative checks)
  - Worker pre-fills Col C columns alongside Col B for new course dev audits
  - Update `Criteria Evaluated` JSON in Audit Runs to include Col C counts
- [ ] **ID Review Interface** in Airtable ("My Courses"):
  - Filtered to Assigned ID = current user
  - Course record shows all criterion dropdowns:
    - Col B: AI-prefilled (ID reviews and corrects before submitting)
    - Col C: AI-prefilled (ID is the sole human validator — QA and ID Assistants do not validate Col C)
  - ID changes dropdowns → same Corrections Log automation fires (reviewer_role = "ID")
  - "Submit for Review" button → Audit Status → "Submitted for Review"
- [ ] Add Assigned ID field to course records
- [ ] Add Audit Type field: Recurring / New Course Dev (determines workflow)
- [ ] **ID Assistant Interface for new course dev:** Col C columns visible (read-only for context). ID Assistants validate Col B only, same as recurring.
- [ ] **QA Interface for new course dev:** Col C visible (read-only for context). QA reviews ID Assistant's Col B work only.
- [ ] Build new course dev automations:
  - Audit Status → "Submitted for Review" → QA assigns ID Assistant
  - ID Assistant completes Col B review → QA reviews ID Assistant's work
  - QA approves → Audit Status → "Launch Approved"
  - QA rejects Col B → Audit Status → "Revisions Needed" → notify ID → ID remediates → re-submits
- [ ] **Launch gate:** Col C must be reviewed by the course-building ID before launch. No timeout auto-completes Col C. Course blocks until ID reviews it.
- [ ] Update RLHF dashboard:
  - Segment correction rates by reviewer role (ID Assistant vs. ID)
  - Segment by audit type (recurring vs. new course dev)
  - Add Col C correction rates (new data — ID corrections only)
  - Per-model accuracy for Col C criteria
- [ ] Update Overall Score formula to include Col C for new course dev audits
- [ ] **Verify:** 10 new course dev audits through full cycle: AI pre-fills Col B + Col C → ID reviews both → submits → ID Assistant validates Col B → QA reviews ID Assistant → launch approved or revisions needed

**Exit criteria:** New course dev workflow operational. Col C AI-evaluated and ID-reviewed. Launch gate enforced (Col C blocks without ID review). Corrections Log captures ID (Col B + Col C) and ID Assistant (Col B) corrections separately.

### Phase 6: Refinement + Expansion (Ongoing)

- [ ] Prompt versioning: track prompt changes in git, measure accuracy impact
- [ ] Model routing optimization: use RLHF data to assign best model per criterion
- [ ] Cross-semester trending: compare audit results across semesters
- [ ] Faculty-facing view: read-only Airtable Interface for faculty (if needed)
- [ ] Multi-template support: different standards for different course types
- [ ] Optional Claude Code bridge: let ID self-audit results sync to QA tracking (if value is proven)

---

## 14. Cost Model

### CreateAI Costs (per course audit)

| Check Type | Count | Tokens/Check | Cost/Check* | Total |
|---|---|---|---|---|
| Deterministic (local) | 124 | 0 | $0.00 | $0.00 |
| AI — structural (Nova Micro) | ~15 | ~1,500 | ~$0.001 | ~$0.015 |
| AI — qualitative (Claude 3.5) | ~34 | ~2,500 | ~$0.008 | ~$0.27 |
| Vision (GPT-4o) | ~5 pages | ~3,000 | ~$0.015 | ~$0.075 |
| **Total per course** | | | | **~$0.36** |

*Costs are estimates based on CreateAI usage metrics. Actual costs depend on content length.

### At Scale

| Courses | Cost/Course | Total | Frequency |
|---|---|---|---|
| 100 | $0.36 | $36 | Per audit cycle |
| 500 | $0.36 | $180 | Per audit cycle |
| 1,000 | $0.36 | $360 | Per audit cycle |
| 1,000 (4x/year) | $0.36 | $1,440 | Annual |

### Infrastructure Costs

| Service | Plan | Monthly Cost |
|---|---|---|
| Railway | Hobby → Pro | $5-20 |
| Cloudflare R2 | Free tier (10GB) → Pay-as-you-go | $0-5 |
| Airtable | Business (existing) | $0 (already paid) |
| CreateAI | ASU internal (usage-based) | See above |
| **Total infrastructure** | | **~$10-25/month** |

### Comparison to Current System

| | Current (human labor) | New (automated) |
|---|---|---|
| 1,000 courses | 333-500 hours × $25/hr = **$8,300-12,500** | **$360 + $25/mo infra** |
| Annual (4 cycles) | **$33,200-50,000** | **~$1,740** |

---

## 15. Risk Analysis

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| CreateAI rate limits hit during batch | Medium | Delays | Durable queue with backoff; spread batch over hours |
| CreateAI model quality varies | Medium | False positives/negatives | Model routing + Corrections Log data drives improvement |
| Airtable automation limits (25K/month on Business) | **Medium** — see capacity math below | Missed corrections, silent data loss | Batch corrections into a single "Save Review" action; see mitigation below |
| Canvas API throttling | Medium | Slow fetches | Cache course content; respect rate limits; stagger requests |
| Corrections Log row growth | Low (35K rows/cycle at 20% correction rate) | Approaches Airtable limits after ~3 cycles | Archive older cycles to a separate base |
| Railway Postgres storage limits | Low | Job queue grows | Prune completed jobs older than 30 days |

#### Airtable Automation Capacity Math

Airtable Business allows **25,000 automation runs/month**. Each "run" is one automation trigger firing. Here's the per-cycle math:

**Per-course automations (recurring audit, Phases 1-4):**

| Event | Automations Fired | Count per Course |
|---|---|---|
| Audit Status → "Queued" | 1 (POST to Railway) | 1 |
| Audit Status → "Audit Complete" | 1 (notify ID Assistant) | 1 |
| ID Assistant criterion corrections (per changed dropdown) | 1 each (append Corrections Log) | ~25 (at 20% correction rate on 124 Col B criteria) |
| Review Status → "In Progress" (first edit) | 1 | 1 |
| Review Status → "Complete" | 1 (set Audit Status) | 1 |
| Audit Status → "Complete" | 1 (recalculate score) | 1 |
| **Total per course** | | **~30** |

**At scale:**

| Courses/Month | Automations/Month | % of 25K Limit | Status |
|---|---|---|---|
| 50 | ~1,500 | 6% | Safe |
| 200 | ~6,000 | 24% | Safe |
| 500 | ~15,000 | 60% | Caution |
| 800 | ~24,000 | 96% | At limit |
| 1,000 | ~30,000 | **120%** | **Over limit** |

**The per-field-change correction automation is the cost driver.** At 1,000 courses, ~25,000 of the ~30,000 runs are correction log appends.

**Mitigation options (implement before Phase 4):**

1. **Batch corrections:** Replace per-field-change automations with a single "Save Review" button that writes all corrections in one automation run. Reduces ~25 runs/course to 1. At 1,000 courses: ~5,000 runs/month (20% of limit). **Recommended.**
2. **Railway-side correction logging:** Instead of Airtable automations, have the ID Assistant Interface call a Railway endpoint on "Mark Review Complete" that diffs current values against AI baseline and writes corrections. Zero Airtable automation runs for corrections. **Fallback if option 1 is insufficient.**
3. **Upgrade to Airtable Enterprise:** 100K+ automation runs/month. Solves the problem with money, not architecture.

**Decision needed before Phase 2:** Choose option 1, 2, or 3. Option 1 is simplest and stays within Airtable. Option 2 moves logic to Railway but eliminates the limit concern entirely.

### Process Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| ID Assistants resist Airtable review (prefer current) | Low | Adoption failure | They already work in Airtable — this is familiar |
| ID doesn't review new course dev audit | Medium | Launch blocked (Col C unreviewed) | QA dashboard visibility; reminders; QA can reassign. Col C never auto-completes — launch gate enforced. |
| ID doesn't review Col C on new course dev | Medium | Launch blocked | QA dashboard visibility; nudge ID; no auto-complete |
| Standards change mid-cycle | Medium | Stale evaluations | Re-upload standards to CreateAI collection; re-audit |

### Security Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Canvas token exposure | Low | Unauthorized access | Railway env vars (encrypted); read-only service account |
| CreateAI token exposure | Low | Unauthorized API usage | Railway env vars; rotate quarterly |
| R2 signed URL shared externally | Low | Unauthorized report access | 24-hour expiry; regenerate on demand; audit access logs |

---

## 16. Open Questions

### Must Answer Before Phase 0

1. **CreateAI project setup.** Who provisions the project and service token? What's the approval process?
2. **Canvas service account.** Can we get a read-only service account for the worker, rather than using a personal token?
3. **Airtable base.** Do we build on the existing SCOUT ULTRA base or create a new one? (Recommendation: new base for development, migrate to SCOUT ULTRA for production.)
4. **R2 bucket.** Who owns the Cloudflare account? Or do we use ASU-managed object storage?

### Must Answer Before Phase 2

5. **ID Assistant onboarding.** How do we map "current user" in Airtable Interfaces to the Reviewers table? Airtable's `collaborator` field type or email match?
6. **ID assignment.** How do we know which ID built which course? Manual assignment in Airtable or auto-detect from Canvas?
7. **Notification method.** Airtable email notifications, or Slack/Teams integration?

### Must Answer Before Phase 4

8. **Airtable Business plan automation limits.** 25K automation runs/month — is that enough for 1,000+ courses with multiple status transitions and notifications? May need Enterprise.
9. **Historical data.** Do we keep all finding records forever, or archive after a semester?
10. **Faculty-facing view.** Do faculty ever see audit results? If so, a fourth Airtable Interface (read-only, high-level)?
11. **Canvas webhooks.** Can we get notified when a course is published/updated, or must we poll?

### Future Considerations

12. **ID self-audit integration.** If an ID runs a self-audit via Claude Code *and* the QA pipeline audits the same course, how do we reconcile? (Current answer: we don't — they're separate systems. Future: optional sync.)
13. **Multi-institution.** If another ASU unit or partner institution wants to use this, how does the Airtable/Railway architecture scale? (Answer: new base per institution, shared Railway worker, separate CreateAI projects.)
14. **Prompt versioning.** As RLHF improves prompts, how do we version them? (Answer: model_routing.yaml in git, deployed with Railway.)

---

## Appendix A: Criterion Distribution

> **Note:** These 173 criteria are the NEW post-implementation QA standard from `standards.yaml`. They are not reflected in the current SCOUT ULTRA testing table, which uses the existing manual QA criteria. The new Airtable base will be built around this structure.

From `standards.yaml` (2026-04-02):

| Category | Count | Reviewer Tier | Check Type |
|---|---|---|---|
| Col B (structural/existence) | 124 | id_assistant (ID Assistant reviews; ID can override in Phase 5) | Mostly deterministic |
| Col C (qualitative/judgment) | 49 | id only (ID Assistants never review Col C) | Mostly AI |
| **Total** | **173** | | |
| Standard 23 | excluded | — | Excluded from audits |
| Standard 24 | manual | — | Manual review only |

### Check Type Breakdown

| Check Type | Count | Where It Runs |
|---|---|---|
| Deterministic | ~100 | Railway worker (local, fast) |
| Hybrid | ~24 | Local first, CreateAI for edge cases |
| AI | ~49 | CreateAI /query with RAG |
| Vision | ~5-10 per course | CreateAI /vision |

---

## Appendix B: CreateAI Model Options

From CreateAI documentation, models available for criterion evaluation:

| Model | Provider | Best For | Relative Cost |
|---|---|---|---|
| `claude3_5_sonnet` | aws | Qualitative judgment, pedagogy evaluation | Medium |
| `gpt4o` | openai | Structured extraction, vision checks | Medium |
| `nova-micro` | aws | Simple structural checks, fast | Low |
| `nova-lite` | aws | Moderate complexity, good value | Low-Medium |
| `llama3_1_70b` | aws | Open-source fallback, good quality | Low |

The model routing strategy uses the cheapest effective model per criterion type, with RLHF data informing which model performs best for each criterion over time.

---

## Appendix C: Comparison Summary

| Dimension | IDW-QA + Review App | QA-at-Scale (this plan) |
|---|---|---|
| Custom code | ~40 files across 2 repos | ~10 files in 1 repo |
| Infrastructure | 3 services (Supabase, Vercel, per-user Claude Code) | Railway (worker + Postgres) + R2 + existing Airtable + CreateAI |
| Frontend | Custom SvelteKit app | Airtable Interfaces — same ones ID Assistants already use |
| Data store | Supabase (7 migrations, RLS, auth) | Airtable (columns from YAML) + R2 (evidence archive) + Postgres (job queue only) |
| Auth | Custom (Supabase email+password, role gates) | Airtable permissions (built-in) |
| AI access | Per-user Claude Code license | 1 CreateAI service token on Railway |
| Audit execution | Human runs `/audit`, waits 20-30 min | Durable queue, worker processes autonomously in 2-5 min |
| Findings model | Row-per-finding in Supabase | Column-per-criterion on course row (SCOUT ULTRA pattern) |
| ID Assistant workflow change | Learn new review app | **No change** — same Interface, dropdowns come pre-filled |
| RLHF signal | Agree/Disagree + corrected_finding in Supabase | Corrections Log (ai_baseline_value vs. new_value, append-only, per reviewer role) |
| Review state | Custom session state machine | Audit Status + Review Status + "Mark Complete" attestation |
| 1,000 courses | 333-500 human-hours | ~2-3 hours compute, 0 human-hours |
| Annual cost (1K courses, 4 cycles) | $33,200-50,000 (labor) | ~$1,740 (compute + infra) |
| ID Assistant onboarding | Install Claude Code, configure .env, learn CLI | "Dropdowns are pre-filled now. Review and mark complete." |
| ID involvement (Phase 5) | Not in QA loop | New course dev: ID reviews Col B + Col C, submits for ID Assistant/QA review. Launch-gated. |
