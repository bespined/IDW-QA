# Codex LE QA Port Plan

**Date**: 2026-04-07
**Source**: LE QA Plugin (`dchandarana07/claude-plugins` — Divyansh's Course QA skill)
**Target**: IDW-QA plugin
**Status**: Complete — all three phases implemented

---

## Context

LE QA is a lightweight, zero-setup Claude Code skill that runs ~30 launch-readiness checks across 8 sections using 7 parallel agents. IDW-QA is a deeper system (173 criteria, deterministic + AI hybrid, full remediation pipeline). This plan ports the specific capabilities from LE QA that fill real gaps in IDW-QA — not a merge, not a rewrite.

**What we're porting:**
1. Canvas Link Validator integration (broken links + images)
2. Graceful no-Supabase/no-tester fallback behavior

**What we're NOT porting:**
- Agent-per-section architecture (IDW-QA's deterministic evaluator is more reliable for B-criteria)
- Canvas MCP integration (`canvas_api.py` gives better control)
- Plugin marketplace packaging (git-based distribution works)
- Spreadsheet mapping table (Airtable sync covers this)

**Deferred to separate plan:**
- Parallel C-criteria evaluation — valuable optimization but too large and architecturally distinct to ride along as a "port." See [Appendix A](#appendix-a-parallel-c-criteria-deferred) for rationale.

---

## Phase 1: Canvas Link Validator (High Value, Low Effort)

### Problem

IDW-QA has 6 functionality criteria that it can't actually verify:
- `B-13.3`: Do all URLs/links work?
- `B-13.4`: Do all documents linked/embedded appear in Student view?
- `B-13.5`: Do all media elements (images) display correctly?
- `B-13.6`: Are media elements sized appropriately?
- `B-13.2`: Do all videos appear and play?
- `B-13.1`: Do all citations link to proper sources?

These are all in `ALWAYS_VERIFY` — the deterministic engine punts them to AI, which also can't browse links. Canvas has a free, built-in link validator that crawls the entire course.

### What LE QA does

Phase 0 of LE QA's orchestrator calls:
```
GET  /api/v1/courses/{id}/link_validation  → check if already completed
POST /api/v1/courses/{id}/link_validation  → trigger if not running
GET  /api/v1/courses/{id}/link_validation  → poll up to 12x (sleep 5s)
```

Then categorizes `results.issues`:
| Condition | Category |
|-----------|----------|
| `image === true` + any reason | Broken image → FAIL |
| `reason: course_mismatch` | Cross-course link → FAIL |
| `reason: unpublished_item` | Unpublished target → FAIL |
| `reason: missing` | Deleted resource → FAIL |
| `reason: unreachable` + `tel:`/`mailto:` | False positive → IGNORE |
| `reason: unreachable` + `doi.org` | Paywalled → REVIEW |
| `reason: unreachable` + other external | External broken → REVIEW |

### Implementation

- [ ] **Create `scripts/link_validator.py`**
  - CLI: `python3 link_validator.py --course-id {ID}`
  - Uses `canvas_api.py` helpers for auth + base URL
  - Trigger → poll → categorize (matching LE QA's logic above)
  - Output: JSON with `{ links: [...], images: [...], summary: { total, broken, review, ignored } }`
  - Timeout: 60s max (12 polls x 5s)
  - Exit codes: 0 = all clean, 1 = failures found, 2 = validator timeout/error

- [ ] **Wire into `criterion_evaluator.py`**
  - Import `link_validator.run_validation(course_id)` at evaluation time (not module scope)
  - Cache result for the duration of the audit (one call covers B-13.1 through B-13.6)
  - Map validator results to criteria:
    - `B-13.3` (links work): FAIL if any non-image `reason: missing | unpublished_item | course_mismatch`
    - `B-13.4` (documents appear): FAIL if any `reason: unpublished_item` where URL points to a file
    - `B-13.5` (images display): FAIL if any `image === true` result
    - `B-13.2` (videos play): Remains `ALWAYS_VERIFY` — link validator can't test playback
    - `B-13.1` (citations): Remains `ALWAYS_VERIFY` — link validator doesn't evaluate citation quality
    - `B-13.6` (image sizing): Remains `ALWAYS_VERIFY` — link validator doesn't measure dimensions
  - Move `B-13.3`, `B-13.4`, `B-13.5` out of `ALWAYS_VERIFY` and `LOW_CONFIDENCE` sets

- [ ] **Populate `affected_pages` using the existing contract**
  - Each issue from the link validator must be transformed to the established `AffectedPage` shape:
    ```json
    {
      "slug": "<page slug extracted from issue url>",
      "title": "<page title from cd['pages'] lookup, fallback to slug>",
      "url": "<full Canvas URL: {course_link}/pages/{slug}>",
      "issue_summary": "<category>: <reason> — <url that failed>",
      "issue_count": 1
    }
    ```
  - Group issues by source page slug, aggregate `issue_count` per page
  - Example for B-13.3 with 3 broken links on the same page:
    ```json
    {
      "slug": "module-1-overview",
      "title": "Module 1 Overview",
      "url": "https://canvas.asu.edu/courses/12345/pages/module-1-overview",
      "issue_summary": "3 broken link(s): 1 missing, 1 unpublished_item, 1 course_mismatch",
      "issue_count": 3
    }
    ```
  - This ensures the review app's collapsible evidence UI renders correctly without changes
  - Backward compatible: old findings without link validation results use existing `affected_pages` path

- [ ] **Add `--skip-link-validation` flag to criterion_evaluator.py**
  - For fast local runs where network latency is unwanted
  - When skipped, B-13.3/4/5 stay in `ALWAYS_VERIFY` as today

- [ ] **Update `audit_results.json` schema**
  - Add top-level `link_validation` object:
    ```json
    {
      "link_validation": {
        "status": "completed",
        "total_issues": 12,
        "broken_links": 3,
        "broken_images": 2,
        "review_items": 5,
        "ignored": 2,
        "issues": [...]
      }
    }
    ```

- [ ] **Update `audit_report.py`**
  - Add "Link & Media Health" section to HTML report
  - List broken links/images with page URLs (actionable for IDs)
  - Show REVIEW items separately (external links needing manual check)

### Migration notes
- No database migration needed — findings schema already supports `affected_pages` JSONB
- No review app changes — findings appear as normal B-criteria with properly shaped `affected_pages`
- Link validator results are ephemeral (not persisted beyond the audit run)

### Estimated effort
- `link_validator.py`: 2-3 hours
- `criterion_evaluator.py` integration + `affected_pages` mapping: 2-3 hours
- Report updates: 1 hour
- Testing against live course: 1 hour

---

## Phase 2: Graceful No-Supabase Fallback (Medium Value, Low Effort)

### Problem

The audit skill's canonical workflow already supports three output paths: "Just show results," "Generate report (local only)," and "Upload to QA portal." `audit_report.py` already implements `--local-only`. The real gap is narrower: **when `.env.local` is missing or `IDW_TESTER_ID` is absent, the system doesn't degrade gracefully.** Scripts that import Supabase config at module scope may error, role gating fails, and the user gets cryptic failures instead of a clean local-only path.

This is not a new audit mode. It's tightening the existing fallback behavior so that the "Just show results" and "Generate report" paths work cleanly when Supabase/tester identity is absent.

### Implementation

- [ ] **Audit all Supabase-importing scripts for fail-safe behavior**
  - Scripts that touch Supabase: `audit_report.py`, `audit_session_manager.py`, `role_gate.py`, `remediation_tracker.py`, `airtable_sync.py`, `rlhf_analysis.py`, `admin_actions.py`, `fetch_fix_queue.py`
  - Each must handle missing `SUPABASE_URL` / `SUPABASE_ANON_KEY` without crashing at import time
  - Pattern: lazy config load, early return with clear message (not stack trace)

- [ ] **Do NOT change `role_gate.py` global behavior**
  - `role_gate` is a shared enforcement module used by many protected skills — it must never silently stub a role
  - Instead, add a narrow helper: `role_gate.can_upload_to_portal() → bool`
    - Returns `True` when `IDW_TESTER_ID` is unset AND `SUPABASE_URL` is unset
    - Does NOT return a role stub — callers get a boolean, not an identity
  - Only the `audit` skill and `audit_report.py` should check this flag to decide whether to skip Supabase operations
  - All other skills (`admin`, `assign`, `report-error`, etc.) continue to call `role_gate` normally and fail explicitly with: "Tester identity required — run /setup to configure"

- [ ] **Update `audit` skill SKILL.md — conditional output prompt**
  - The canonical 3-path output choice ("Just show results" / "Generate report" / "Upload to QA portal") remains the default when Supabase is configured
  - When `role_gate.can_upload_to_portal()` returns `True`, the skill presents a **reduced 2-path prompt**:
    1. "Just show results"
    2. "Generate report (saved to `reports/`)"
  - The third option ("Upload to QA portal") is not shown — not greyed out, not disabled, just absent
  - Below the prompt, show a one-line note: "Portal upload unavailable — Supabase not configured. Run /setup to enable."
  - This is an explicit conditional variation of the canonical audit prompt. Update `codex-canonical-workflow-spec.md` § Audit Output to document this reduced prompt as a specified behavior, not an implementation detail

- [ ] **Document minimum env requirements by use case**
  - Add to `SETUP.md`:
    | Use case | Required env |
    |----------|-------------|
    | Quick Check (local) | `CANVAS_TOKEN`, `CANVAS_DOMAIN`, `CANVAS_COURSE_ID` |
    | Deep Audit (local) | Above + `ANTHROPIC_API_KEY` (if C-criteria use direct Claude calls) |
    | Upload to QA portal | Above + `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `IDW_TESTER_ID` |
    | Airtable sync | Above + `AIRTABLE_TOKEN`, `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_ID` |

### What this does NOT change
- `audit_report.py --local-only` behavior is unchanged
- No new audit "mode" is created
- `role_gate.py` enforcement for all non-audit skills is unchanged — no global stubs
- Portal upload still requires full credentials — this just prevents the local paths from breaking when portal credentials are absent

### What this DOES change (explicitly)
- The audit skill's output prompt becomes conditional: 3 options when Supabase is configured, 2 options when it isn't
- `codex-canonical-workflow-spec.md` gets a new § documenting this as a specified variation, not drift

### Estimated effort
- Script audit + lazy-load fixes: 2-3 hours
- `role_gate.py` fallback: 30 min
- Skill + doc updates: 30 min
- Testing (fresh env with no `.env.local`): 1 hour

---

## Phase 3: Navigation Tab Visibility Fix (Low Effort)

IDW-QA already checks tabs via `criterion_evaluator.py:101` (`_api_get("tabs")`), but filters by `visibility == "public"` / label presence. LE QA explicitly checks the `hidden` field — a tab can have `visibility: "public"` but still be `hidden: true` (admin-hidden from students).

- [ ] Update tab parsing in `criterion_evaluator.py` to also reject tabs where `hidden === true`
- Affected criteria: `B-CRC.7` (Syllabus), `B-CRC.8` (Modules), `B-CRC.9` (Resources), `B-CRC.10` (Accessibility), `B-CRC.11` (ASU Course Policies), `B-CRC.12` (Time in AZ)
- Estimated effort: 30 min

---

## Not Porting (Documented Reasons)

| LE QA Feature | Why Not |
|---|---|
| Agent-per-section architecture | IDW-QA's deterministic evaluator is more reliable for B-criteria — agents introduce LLM variability on existence checks |
| Canvas MCP for data access | `canvas_api.py` provides pagination, retry, caching, error handling that MCP doesn't |
| Plugin marketplace packaging | Git clone + `update-idw` skill works; marketplace adds packaging overhead with no user benefit today |
| QA spreadsheet mapping table | Airtable sync already serves this purpose for the LE workflow |
| Emoji status symbols in output | IDW-QA uses structured JSON + HTML reports; emoji is presentation-layer and handled by the report generator |

---

## Appendix A: Parallel C-Criteria (Deferred) {#appendix-a-parallel-c-criteria-deferred}

The original draft included parallel C-criteria evaluation as Phase 3. Codex review correctly identified this as too large and architecturally distinct to ride along as a port:

- C-evaluation currently depends on a single consistent audit pass and output contract
- Batching, parallel agent execution, merge semantics, retry behavior, and partial-failure handling are each non-trivial
- The effort estimate (8-12 hours) was optimistic given the orchestration rewrite required
- Debugging parallel agent failures is qualitatively harder than sequential failures

**Recommendation**: Spin into a separate `codex-parallel-audit-optimization.md` plan after Phases 1-3 land cleanly. The link validator and fallback work are prerequisites — they stabilize the evaluator contract before we change how it's orchestrated.

---

## Tracking

| Phase | Items | Est. Effort | Priority | Status |
|-------|-------|-------------|----------|--------|
| 1. Link Validator | 6 | 6-8 hours | **High** | **Done** |
| 2. No-Supabase Fallback | 4 | 4-5 hours | **Medium** | **Done** |
| 3. Tab Visibility Fix | 1 | 30 min | **Low** | **Done** |
