#!/usr/bin/env python3
"""Assignment status manager — enforces ownership and valid state transitions.

Usage:
    python3 scripts/assignment_status.py --update --assignment-id <uuid> --status in_progress
    python3 scripts/assignment_status.py --update --assignment-id <uuid> --status completed
    python3 scripts/assignment_status.py --list
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

try:
    from idw_logger import get_logger
    _log = get_logger("assignment_status")
except ImportError:
    import logging
    _log = logging.getLogger("assignment_status")

PLUGIN_ROOT = Path(__file__).resolve().parents[1]

import supabase_client

# Valid state transitions
VALID_TRANSITIONS = {
    "assigned": ["in_progress"],
    "in_progress": ["completed"],
    "completed": [],  # terminal state — no further transitions
}


def update_status(assignment_id, new_status, dry_run=False):
    """Update assignment status with ownership check and valid transition enforcement."""
    import requests

    if not supabase_client.is_configured():
        return {"ok": False, "error": "Supabase not configured"}

    tester_id = os.getenv("IDW_TESTER_ID", "")
    if not tester_id:
        return {"ok": False, "error": "IDW_TESTER_ID not set"}

    # Fetch assignment
    assignments = supabase_client.get("tester_course_assignments", params={
        "id": f"eq.{assignment_id}",
        "select": "id,tester_id,status,course_id",
    })
    if not assignments:
        return {"ok": False, "error": f"Assignment {assignment_id} not found"}

    assignment = assignments[0]
    current_status = assignment.get("status", "assigned")
    owner_id = assignment.get("tester_id")

    # Check ownership (tester owns it, or caller is admin)
    if owner_id != tester_id:
        # Check if caller is admin
        testers = supabase_client.get("testers", params={
            "id": f"eq.{tester_id}", "select": "role",
        })
        caller_role = testers[0].get("role") if testers else None
        if caller_role != "admin":
            return {"ok": False, "error": f"Assignment belongs to tester {owner_id}, not you. Admin override required."}

    # Check valid transition
    allowed = VALID_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        return {"ok": False, "error": f"Invalid transition: '{current_status}' → '{new_status}'. Allowed: {allowed or 'none (terminal state)'}"}

    if dry_run:
        return {"ok": True, "dry_run": True, "old_status": current_status, "new_status": new_status}

    if not supabase_client.patch("tester_course_assignments", assignment_id, {"status": new_status}):
        return {"ok": False, "error": "Failed to update assignment status"}

    _log.info("Assignment %s: %s → %s (by %s)", assignment_id, current_status, new_status, tester_id)
    return {
        "ok": True,
        "assignment_id": assignment_id,
        "old_status": current_status,
        "new_status": new_status,
        "course_id": assignment.get("course_id"),
    }


def list_assignments():
    """List assignments for the current tester."""
    if not supabase_client.is_configured():
        return {"ok": False, "error": "Supabase not configured"}

    tester_id = os.getenv("IDW_TESTER_ID", "")
    if not tester_id:
        return {"ok": False, "error": "IDW_TESTER_ID not set"}

    assignments = supabase_client.get("tester_course_assignments", params={
        "tester_id": f"eq.{tester_id}",
        "order": "assigned_at.desc",
    })

    return {"ok": True, "assignments": assignments or []}


def main():
    parser = argparse.ArgumentParser(description="Assignment status manager")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--update", action="store_true")
    group.add_argument("--list", action="store_true")

    parser.add_argument("--assignment-id", help="Assignment UUID")
    parser.add_argument("--status", help="New status: in_progress or completed")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.update:
        if not args.assignment_id or not args.status:
            print(json.dumps({"ok": False, "error": "Provide --assignment-id and --status"}))
            sys.exit(1)
        result = update_status(args.assignment_id, args.status, args.dry_run)
        if result["ok"]:
            print(f"✓ {result.get('old_status', '?')} → {result['new_status']}")
        else:
            print(f"✗ {result['error']}")

    elif args.list:
        result = list_assignments()
        if result["ok"]:
            for a in result["assignments"]:
                print(f"  {a.get('status', '?')} | Course {a.get('course_id', '?')} | {a.get('assigned_at', '?')[:10]}")
        else:
            print(f"✗ {result['error']}")

    print(json.dumps(result))


if __name__ == "__main__":
    main()
