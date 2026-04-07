#!/usr/bin/env python3
"""Centralized remediation event recording — replaces all inline Supabase POSTs across skills.

Records remediation events and clears remediation_requested flags atomically.

Usage:
    # Record events for specific findings
    python3 scripts/remediation_tracker.py --record \
        --finding-ids abc123,def456 \
        --skill bulk-edit \
        --description "Fixed heading hierarchy across 3 pages"

    # With explicit tester ID (otherwise reads from IDW_TESTER_ID env)
    python3 scripts/remediation_tracker.py --record \
        --finding-ids abc123 --skill quiz \
        --description "Updated quiz settings" --tester-id <uuid>

    # Dry run
    python3 scripts/remediation_tracker.py --record \
        --finding-ids abc123,def456 --skill staging \
        --description "Page HTML updated" --dry-run
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

try:
    from idw_logger import get_logger
    _log = get_logger("remediation_tracker")
except ImportError:
    import logging
    _log = logging.getLogger("remediation_tracker")

PLUGIN_ROOT = Path(__file__).resolve().parents[1]

import supabase_client


def _validate_finding_exists(finding_id):
    """Check that a finding exists in Supabase before recording an event."""
    data = supabase_client.get("audit_findings", params={
        "id": f"eq.{finding_id}",
        "select": "id,criterion_id,remediation_requested",
    }, timeout=10)
    return data[0] if data else None


def record_events(finding_ids, skill, description, tester_id=None, dry_run=False):
    """Record remediation events for a list of finding IDs.

    Returns dict with counts of recorded events and cleared flags.
    """
    if not supabase_client.is_configured():
        return {"ok": False, "error": "Supabase not configured — check .env.local"}

    tester_id = tester_id or os.getenv("IDW_TESTER_ID", "")
    if not tester_id:
        _log.warning("No IDW_TESTER_ID set — remediation events will have empty remediated_by")

    recorded = 0
    cleared = 0
    skipped = []
    errors = []

    for fid in finding_ids:
        fid = fid.strip()
        if not fid:
            continue

        # Validate finding exists
        finding = _validate_finding_exists(fid)
        if not finding:
            skipped.append({"id": fid, "reason": "Finding not found in Supabase"})
            _log.warning("Finding %s not found — skipping", fid)
            continue

        if dry_run:
            _log.info("[DRY RUN] Would record event for %s (criterion: %s)",
                       fid, finding.get("criterion_id"))
            recorded += 1
            continue

        # Record remediation event
        result = supabase_client.post("remediation_events", {
            "finding_id": fid,
            "remediated_by": tester_id,
            "skill_used": skill,
            "description": description,
        }, timeout=15)

        if result:
            recorded += 1
            _log.info("Recorded event for %s", fid)
        else:
            errors.append({"id": fid, "error": "POST failed"})
            _log.error("Failed to record event for %s", fid)
            continue

        # Clear remediation_requested flag
        if supabase_client.patch("audit_findings", fid, {"remediation_requested": False}):
            cleared += 1

    return {
        "ok": len(errors) == 0,
        "recorded": recorded,
        "cleared": cleared,
        "skipped": skipped,
        "errors": errors,
        "dry_run": dry_run,
    }


def main():
    parser = argparse.ArgumentParser(description="Centralized remediation event recording")
    parser.add_argument("--record", action="store_true", required=True, help="Record remediation events")
    parser.add_argument("--finding-ids", required=True, help="Comma-separated finding IDs")
    parser.add_argument("--skill", required=True, help="Skill that performed the remediation")
    parser.add_argument("--description", required=True, help="What was fixed")
    parser.add_argument("--tester-id", help="Tester UUID (defaults to IDW_TESTER_ID env)")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing")
    args = parser.parse_args()

    finding_ids = [f.strip() for f in args.finding_ids.split(",") if f.strip()]
    if not finding_ids:
        print(json.dumps({"ok": False, "error": "No finding IDs provided"}))
        sys.exit(1)

    result = record_events(finding_ids, args.skill, args.description,
                           args.tester_id, args.dry_run)

    # Human-friendly output
    if result["ok"]:
        print(f"✓ Recorded {result['recorded']} events, cleared {result['cleared']} flags")
    else:
        print(f"⚠ Recorded {result['recorded']} events with {len(result['errors'])} error(s)")

    if result["skipped"]:
        for s in result["skipped"]:
            print(f"  Skipped: {s['id']} — {s['reason']}")
    if result["errors"]:
        for e in result["errors"]:
            print(f"  Error: {e['id']} — {e['error']}")

    print(json.dumps(result))


if __name__ == "__main__":
    main()
