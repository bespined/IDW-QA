#!/usr/bin/env python3
"""Airtable Sync — push approved audit findings to Airtable (one row per course).

Aggregates per-criterion findings from Supabase into one Airtable row, mapping
criterion_id (B-04.1) directly to Airtable column names. Standard-level ratings
and notes are derived from criteria.

Usage:
    python airtable_sync.py --session-id <uuid>           # Sync one session
    python airtable_sync.py --course-id <canvas_id>       # Sync latest session for a course
    python airtable_sync.py --pending                      # Sync all approved-but-unsynced sessions
    python airtable_sync.py --dry-run --session-id <uuid>  # Preview without writing
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from idw_logger import get_logger
    _log = get_logger("airtable_sync")
except ImportError:
    import logging
    _log = logging.getLogger("airtable_sync")

PLUGIN_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, os.path.dirname(__file__))
import supabase_client


# ── Config ──

def _get_config():
    # Airtable config still loaded from env (supabase_client handles Supabase config)
    supabase_client._ensure_env()
    return {
        "airtable_token": os.getenv("AIRTABLE_TOKEN", ""),
        "airtable_base_id": os.getenv("AIRTABLE_BASE_ID", ""),
        "airtable_table": "Course Audits",
    }


# ── Airtable helpers ──

def _at_find_record(token, base_id, table, course_name):
    import requests
    resp = requests.get(
        f"https://api.airtable.com/v0/{base_id}/{table}",
        headers={"Authorization": f"Bearer {token}"},
        params={"filterByFormula": f'{{Course Name}}="{course_name}"', "maxRecords": 1},
        timeout=15,
    )
    if resp.status_code == 200:
        records = resp.json().get("records", [])
        return records[0] if records else None
    return None


def _at_upsert(token, base_id, table, record_id, fields):
    import requests
    if record_id:
        resp = requests.patch(
            f"https://api.airtable.com/v0/{base_id}/{table}/{record_id}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"fields": fields},
            timeout=30,
        )
    else:
        resp = requests.post(
            f"https://api.airtable.com/v0/{base_id}/{table}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"fields": fields},
            timeout=30,
        )
    if resp.status_code in (200, 201):
        return resp.json()
    _log.error("Airtable upsert: %s %s", resp.status_code, resp.text[:300])
    return None


def _at_get_field_map(token, base_id):
    # Discover column names from the Airtable metadata API because field names include human labels (e.g. "B-04.1 Layout: Getting Started*") that we can't hardcode
    """Fetch Airtable table schema and build criterion_id -> field_name mapping."""
    import requests
    resp = requests.get(
        f"https://api.airtable.com/v0/meta/bases/{base_id}/tables",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if resp.status_code != 200:
        return {}, [], []

    tables = resp.json().get("tables", [])
    course_table = next((t for t in tables if t["name"] == "Course Audits"), None)
    if not course_table:
        return {}, [], []

    all_fields = [f["name"] for f in course_table["fields"]]

    # Build criterion mapping: B-04.1 -> "B-04.1 Layout: Getting Started*"
    crit_map = {}
    for fname in all_fields:
        if fname.startswith(("B-", "C-")):
            crit_id = fname.split(" ", 1)[0]
            crit_map[crit_id] = fname

    # Build rating field mapping: find fields ending with "— Rating"
    rating_fields = [f for f in all_fields if "— Rating" in f]

    # Build notes field mapping: find fields ending with "— Notes"
    notes_fields = [f for f in all_fields if "— Notes" in f]

    return crit_map, rating_fields, notes_fields


# ── Helpers ──

def _strip_html(text):
    clean = re.sub(r'<[^>]+>', '', text or '')
    return re.sub(r'\s+', ' ', clean).strip()


def _verdict_to_yes_no(verdict):
    """Map finding verdict to Yes/No/N/A for criterion columns."""
    v = (verdict or "").lower().replace("_", " ")
    if v in ("met", "pass", "yes"):
        return "Yes"
    if v in ("not auditable", "n/a", "not applicable"):
        return "N/A"
    return "No"


def _verdict_to_rating(verdict):
    """Map verdict to standard-level rating."""
    v = (verdict or "").lower().replace("_", " ")
    if v in ("met", "pass"):
        return "Met"
    if v in ("partially met",):
        return "Partially Met"
    if v in ("not met", "fail"):
        return "Not Met"
    if v in ("not auditable",):
        return "Not Auditable"
    return "Not Met"


def _find_rating_field(rating_fields, std_id):
    """Find the Airtable rating field for a standard ID."""
    padded = std_id.zfill(2)
    for f in rating_fields:
        if f" {padded}. " in f:
            return f
    return None


def _find_notes_field(notes_fields, std_id):
    """Find the Airtable notes field for a standard ID."""
    padded = std_id.zfill(2)
    for f in notes_fields:
        if f" {padded}. " in f or f"{padded}. " in f:
            return f
    return None


def _generate_notes(findings, feedback_map=None):
    # When an IDA marked a finding as 'incorrect', prefer their correction_note over AI reasoning so Airtable reflects human judgment
    """Generate high-level notes from findings for a standard.

    If IDA corrected a finding, use their correction_note instead of AI reasoning.
    """
    def _effective_verdict(f):
        fid = f.get("id", "")
        fb = feedback_map.get(fid) if feedback_map else None
        if fb and fb.get("decision") == "incorrect" and fb.get("corrected_finding"):
            return fb["corrected_finding"]
        return f.get("ai_verdict", "")

    def _effective_reasoning(f):
        fid = f.get("id", "")
        fb = feedback_map.get(fid) if feedback_map else None
        if fb and fb.get("decision") == "incorrect" and fb.get("correction_note"):
            return _strip_html(fb["correction_note"])
        return _strip_html(f.get("ai_reasoning") or "")

    failing = [f for f in findings if _verdict_to_yes_no(_effective_verdict(f)) == "No"]
    if not failing:
        return "All criteria met. No issues found."

    issues = []
    for f in failing[:5]:
        reasoning = _effective_reasoning(f)
        cid = f.get("criterion_id", "")
        if reasoning:
            issues.append(f"{cid}: {reasoning}")

    return "\n".join(issues)


# ── Core ──

def build_airtable_row(session, findings, crit_map, rating_fields, notes_fields, feedback_map=None):
    # Flow: group findings by standard → map each criterion to its Airtable column via crit_map → derive standard-level rating from criteria verdicts → generate notes
    """Build Airtable field values from session + per-criterion findings."""
    fields = {}

    # Metadata
    fields["Course Name"] = session.get("course_name") or session.get("course_code") or "Unknown"
    fields["Course Code"] = session.get("course_code") or ""
    fields["Term"] = session.get("term") or ""
    fields["Audit Date"] = (session.get("run_date") or "")[:10]
    # Auditor name
    auditor = session.get("auditor_id") or "ID Workbench"
    fields["Auditor"] = auditor
    fields["Overall Score"] = session.get("overall_score") or 0
    fields["Session Status"] = "Complete"

    # Group findings by standard_id
    by_std = {}
    for f in findings:
        sid = (f.get("standard_id") or "").zfill(2)
        if sid not in by_std:
            by_std[sid] = []
        by_std[sid].append(f)

    met_count = 0
    total_standards = 0
    essential_ids = {"01", "02", "06", "08", "12", "22", "23"}
    essential_met = 0

    for sid, std_findings in sorted(by_std.items()):
        if not sid or sid == "00":
            continue

        total_standards += 1

        # Map per-criterion findings to Airtable columns
        # If IDA corrected the AI (decision='incorrect'), use the corrected verdict
        for f in std_findings:
            cid = f.get("criterion_id", "")
            if not cid or cid not in crit_map:
                continue
            fid = f.get("id", "")
            fb = feedback_map.get(fid) if feedback_map else None
            if fb and fb.get("decision") == "incorrect" and fb.get("corrected_finding"):
                # IDA corrected this finding — use their verdict
                fields[crit_map[cid]] = _verdict_to_yes_no(fb["corrected_finding"])
            else:
                fields[crit_map[cid]] = _verdict_to_yes_no(f.get("ai_verdict", ""))

        # Derive standard-level rating from criteria
        # Same logic: prefer IDA corrections over AI verdicts
        def _effective_verdict(f):
            fid = f.get("id", "")
            fb = feedback_map.get(fid) if feedback_map else None
            if fb and fb.get("decision") == "incorrect" and fb.get("corrected_finding"):
                return fb["corrected_finding"]
            return f.get("ai_verdict", "")

        verdicts = [_verdict_to_yes_no(_effective_verdict(f)) for f in std_findings]
        verdicts_excl_na = [v for v in verdicts if v != "N/A"]

        if not verdicts_excl_na:
            rating = "Not Auditable"
        elif all(v == "Yes" for v in verdicts_excl_na):
            rating = "Met"
            met_count += 1
            if sid in essential_ids:
                essential_met += 1
        elif any(v == "No" for v in verdicts_excl_na):
            yes_count = sum(1 for v in verdicts_excl_na if v == "Yes")
            if yes_count > len(verdicts_excl_na) / 2:
                rating = "Partially Met"
            else:
                rating = "Not Met"
        else:
            rating = "Met"
            met_count += 1
            if sid in essential_ids:
                essential_met += 1

        # Set rating field
        rf = _find_rating_field(rating_fields, sid)
        if rf:
            fields[rf] = rating

        # Set notes field
        nf = _find_notes_field(notes_fields, sid)
        if nf:
            fields[nf] = _generate_notes(std_findings, feedback_map)

    # Summary counts
    fields["Standards Met"] = f"{met_count}/{total_standards} Standards Met"
    fields["Essential Standards Met"] = f"{essential_met}/{len(essential_ids)} Essential Standards Met"

    return fields


def sync_session(session_id, dry_run=False):
    """Sync a single audit session to Airtable."""
    cfg = _get_config()
    if not supabase_client.is_configured():
        return {"error": "Supabase credentials not configured"}
    if not cfg["airtable_token"] or not cfg["airtable_base_id"]:
        return {"error": "Airtable credentials not configured"}

    # Get Airtable schema mapping
    crit_map, rating_fields, notes_fields = _at_get_field_map(cfg["airtable_token"], cfg["airtable_base_id"])
    if not crit_map:
        _log.warning("No criterion mapping found — syncing standard-level only")

    # Fetch session
    sessions = supabase_client.get("audit_sessions", params={"id": f"eq.{session_id}"})
    if not sessions:
        return {"error": f"Session {session_id} not found"}
    session = sessions[0]

    # Fetch findings
    findings = supabase_client.get("audit_findings", params={
        "session_id": f"eq.{session_id}", "order": "standard_id.asc"})
    if findings is None:
        return {"error": "Failed to fetch findings"}

    # Fetch latest feedback per finding
    feedback_map = {}
    if findings:
        finding_ids = [f["id"] for f in findings]
        all_fb = supabase_client.get("finding_feedback", params={
            "finding_id": f"in.({','.join(finding_ids)})", "order": "reviewed_at.desc"})
        if all_fb:
            for fb in all_fb:
                fid = fb["finding_id"]
                if fid not in feedback_map:
                    feedback_map[fid] = fb

    # Build row
    fields = build_airtable_row(session, findings, crit_map, rating_fields, notes_fields, feedback_map)

    if dry_run:
        # Count populated B/C fields
        bc_filled = sum(1 for k in fields if k.startswith(("B-", "C-")))
        return {"dry_run": True, "fields_total": len(fields), "criteria_filled": bc_filled,
                "finding_count": len(findings), "fields": fields}

    # Find or create Airtable record
    course_name = fields.get("Course Name", "Unknown")
    existing = _at_find_record(cfg["airtable_token"], cfg["airtable_base_id"],
                               cfg["airtable_table"], course_name)
    record_id = existing["id"] if existing else None

    result = _at_upsert(cfg["airtable_token"], cfg["airtable_base_id"],
                        cfg["airtable_table"], record_id, fields)

    if result:
        if not supabase_client.patch("audit_sessions", session_id,
                                    {"airtable_synced_at": datetime.now(timezone.utc).isoformat()}):
            _log.warning("Failed to stamp airtable_synced_at on session %s", session_id)
        action = "updated" if record_id else "created"
        bc_filled = sum(1 for k in fields if k.startswith(("B-", "C-")))
        return {"ok": True, "action": action, "record_id": result.get("id"), "course": course_name,
                "findings_synced": len(findings), "criteria_filled": bc_filled}

    return {"error": "Airtable upsert failed"}


def sync_pending():
    """Sync all sessions that are qa_approved but not yet synced."""
    sessions = supabase_client.get("audit_sessions", params={
        "status": "eq.qa_approved", "airtable_synced_at": "is.null",
        "order": "run_date.desc"})
    if not sessions:
        return {"synced": 0, "message": "No pending sessions to sync"}

    results = []
    for s in sessions:
        r = sync_session(s["id"])
        results.append(r)
    return {"synced": len([r for r in results if r.get("ok")]), "results": results}


def main():
    parser = argparse.ArgumentParser(description="Sync audit findings to Airtable")
    parser.add_argument("--session-id", help="Sync a specific audit session")
    parser.add_argument("--course-id", help="Sync latest session for a Canvas course ID")
    parser.add_argument("--pending", action="store_true", help="Sync all approved-but-unsynced sessions")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to Airtable")
    args = parser.parse_args()

    if args.session_id:
        result = sync_session(args.session_id, dry_run=args.dry_run)
    elif args.course_id:
        sessions = supabase_client.get("audit_sessions", params={
            "course_id": f"eq.{args.course_id}", "order": "run_date.desc", "limit": "1"})
        if sessions:
            result = sync_session(sessions[0]["id"], dry_run=args.dry_run)
        else:
            result = {"error": f"No sessions found for course {args.course_id}"}
    elif args.pending:
        result = sync_pending()
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
