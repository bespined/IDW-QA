#!/usr/bin/env python3
"""Audit session lifecycle manager — deterministic session creation and status transitions.

Replaces prompt-based audit_purpose inference and session creation with script-enforced logic.

Usage:
    # Create a new audit session (auto-infers purpose from tester role)
    python3 scripts/audit_session_manager.py --create --course-id 252193

    # Create with explicit purpose
    python3 scripts/audit_session_manager.py --create --course-id 252193 --purpose self_audit

    # Submit session for QA review
    python3 scripts/audit_session_manager.py --submit --session-id <uuid>

    # Check session status
    python3 scripts/audit_session_manager.py --status --session-id <uuid>

    # Dry run
    python3 scripts/audit_session_manager.py --create --course-id 252193 --dry-run
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

try:
    from idw_logger import get_logger
    _log = get_logger("audit_session_manager")
except ImportError:
    import logging
    _log = logging.getLogger("audit_session_manager")

PLUGIN_ROOT = Path(__file__).resolve().parents[1]

import supabase_client


def _get_tester_info(tester_id):
    """Fetch tester role and active status."""
    data = supabase_client.get("testers", params={"id": f"eq.{tester_id}", "select": "id,role,is_active,name"})
    return data[0] if data else None


def _get_course_assignments(course_id):
    """Get all tester assignments for a course."""
    return supabase_client.get("tester_course_assignments", params={
        "course_id": f"eq.{course_id}",
        "select": "id,tester_id,status",
    }) or []


def _count_prior_sessions(course_id, purpose):
    """Count prior audit sessions for round numbering."""
    data = supabase_client.get("audit_sessions", params={
        "course_id": f"eq.{course_id}",
        "audit_purpose": f"eq.{purpose}",
        "select": "id",
    })
    return len(data) if data else 0


def infer_audit_purpose(tester_role, tester_id, course_id):
    """Deterministically infer audit_purpose from tester role and course context.

    Rules:
    - id_assistant → REJECTED (IDAs use Vercel review app, not Claude Code)
    - admin → always 'qa_review'
    - id → check if course has assignments owned by OTHER testers
            if yes → 'qa_review' (reviewing someone else's work)
            if no → 'self_audit' (auditing own course)
    """
    if tester_role == "id_assistant":
        return None  # rejected — caller must handle

    if tester_role == "admin":
        return "qa_review"

    if tester_role == "id":
        assignments = _get_course_assignments(course_id)
        other_assignees = [a for a in assignments if a.get("tester_id") != tester_id]
        if other_assignees:
            return "qa_review"
        return "self_audit"

    _log.warning("Unknown role '%s', defaulting to self_audit", tester_role)
    return "self_audit"


def create_session(course_id, purpose=None, audit_mode="full_audit", dry_run=False):
    """Create a new audit session in Supabase.

    Returns session dict with id, purpose, round, status.
    """
    if not supabase_client.is_configured():
        return {"ok": False, "error": "Supabase not configured — check .env.local"}

    tester_id = os.getenv("IDW_TESTER_ID", "")
    if not tester_id:
        return {"ok": False, "error": "IDW_TESTER_ID not set in .env"}

    # Get tester info
    tester = _get_tester_info(tester_id)
    if not tester:
        return {"ok": False, "error": f"Tester {tester_id} not found in Supabase"}
    if not tester.get("is_active"):
        return {"ok": False, "error": f"Tester {tester['name']} is deactivated"}

    # Infer purpose
    if purpose and purpose != "auto":
        audit_purpose = purpose
    else:
        audit_purpose = infer_audit_purpose(tester["role"], tester_id, course_id)

    if audit_purpose is None:
        return {"ok": False, "error": "ID Assistants do not create audit sessions in Claude Code. Use the Vercel review app at https://idw-review-app.vercel.app"}

    # Count prior sessions for round number
    audit_round = _count_prior_sessions(course_id, audit_purpose) + 1

    session_row = {
        "course_id": str(course_id),
        "run_date": datetime.now(timezone.utc).isoformat(),
        "audit_purpose": audit_purpose,
        "audit_round": audit_round,
        "status": "in_progress",
        "auditor_id": tester["name"],
        "plugin_version": "0.9.0",
    }

    if dry_run:
        _log.info("[DRY RUN] Would create session: %s", json.dumps(session_row))
        return {
            "ok": True, "dry_run": True,
            "purpose": audit_purpose, "round": audit_round,
            "tester_role": tester["role"], "tester_name": tester["name"],
        }

    result = supabase_client.post("audit_sessions", session_row, timeout=15)
    if not result:
        return {"ok": False, "error": "Failed to create audit session — check Supabase logs"}

    session_id = result["id"] if isinstance(result, dict) else result[0]["id"]

    return {
        "ok": True,
        "session_id": session_id,
        "purpose": audit_purpose,
        "round": audit_round,
        "status": "in_progress",
        "tester_role": tester["role"],
        "tester_name": tester["name"],
        "review_url": f"https://idw-review-app.vercel.app/session/{session_id}",
    }


def submit_for_review(session_id, dry_run=False):
    """Transition session from in_progress → pending_qa_review."""
    if not supabase_client.is_configured():
        return {"ok": False, "error": "Supabase not configured"}

    # Verify current status
    sessions = supabase_client.get("audit_sessions", params={
        "id": f"eq.{session_id}", "select": "id,status,audit_purpose",
    })
    if not sessions:
        return {"ok": False, "error": f"Session {session_id} not found"}

    session = sessions[0]
    current_status = session.get("status")

    if current_status != "in_progress":
        return {"ok": False, "error": f"Cannot submit — current status is '{current_status}', expected 'in_progress'"}

    if dry_run:
        return {"ok": True, "dry_run": True, "session_id": session_id, "new_status": "pending_qa_review"}

    ok = supabase_client.patch("audit_sessions", session_id, {"status": "pending_qa_review"})
    if ok:
        return {"ok": True, "session_id": session_id, "new_status": "pending_qa_review"}
    return {"ok": False, "error": "Failed to update session status — check Supabase logs"}


def get_session_status(session_id):
    """Get current session status and summary."""
    if not supabase_client.is_configured():
        return {"ok": False, "error": "Supabase not configured"}

    sessions = supabase_client.get("audit_sessions", params={
        "id": f"eq.{session_id}",
    })
    if not sessions:
        return {"ok": False, "error": f"Session {session_id} not found"}

    session = sessions[0]

    # Count findings
    findings = supabase_client.get("audit_findings", params={
        "session_id": f"eq.{session_id}",
        "select": "id,status,remediation_requested",
    }) or []

    return {
        "ok": True,
        "session_id": session_id,
        "status": session.get("status"),
        "purpose": session.get("audit_purpose"),
        "round": session.get("audit_round"),
        "total_findings": len(findings),
        "remediation_requested": sum(1 for f in findings if f.get("remediation_requested")),
        "review_url": f"https://idw-review-app.vercel.app/session/{session_id}",
    }


def main():
    parser = argparse.ArgumentParser(description="Audit session lifecycle manager")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create", action="store_true", help="Create a new session")
    group.add_argument("--submit", action="store_true", help="Submit session for QA review")
    group.add_argument("--status", action="store_true", help="Check session status")

    parser.add_argument("--course-id", help="Canvas course ID")
    parser.add_argument("--purpose", help="Override audit purpose: self_audit, recurring, qa_review, or auto")
    parser.add_argument("--mode", default="full_audit", help="Audit mode: quick_scan, full_audit, guided_review")
    parser.add_argument("--session-id", help="Session UUID (for --submit and --status)")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing")
    args = parser.parse_args()

    if args.create:
        if not args.course_id:
            print(json.dumps({"ok": False, "error": "Provide --course-id for session creation"}))
            sys.exit(1)
        result = create_session(args.course_id, args.purpose, args.mode, args.dry_run)
        if result["ok"]:
            print(f"✓ Session created: {result.get('session_id', 'DRY RUN')}")
            print(f"  Purpose: {result['purpose']} (round {result['round']})")
            print(f"  Tester: {result['tester_name']} ({result['tester_role']})")
            if result.get("review_url"):
                print(f"  Review: {result['review_url']}")
        else:
            print(f"✗ {result['error']}")

    elif args.submit:
        if not args.session_id:
            print(json.dumps({"ok": False, "error": "Provide --session-id for submission"}))
            sys.exit(1)
        result = submit_for_review(args.session_id, args.dry_run)
        if result["ok"]:
            print(f"✓ Session {args.session_id} submitted for QA review")
        else:
            print(f"✗ {result['error']}")

    elif args.status:
        if not args.session_id:
            print(json.dumps({"ok": False, "error": "Provide --session-id"}))
            sys.exit(1)
        result = get_session_status(args.session_id)
        if result["ok"]:
            print(f"Session: {result['session_id']}")
            print(f"  Status: {result['status']}")
            print(f"  Purpose: {result['purpose']} (round {result['round']})")
            print(f"  Findings: {result['total_findings']} ({result['remediation_requested']} pending remediation)")
            print(f"  Review: {result['review_url']}")
        else:
            print(f"✗ {result['error']}")

    print(json.dumps(result))


if __name__ == "__main__":
    main()
