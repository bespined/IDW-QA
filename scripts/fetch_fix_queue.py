#!/usr/bin/env python3
"""Fetch the fix queue — findings where remediation has been requested.

Queries Supabase audit_findings where remediation_requested=true,
optionally filtered by course_id. Returns actionable items with
session context and any reviewer feedback.

Usage:
    python fetch_fix_queue.py                          # All pending remediations
    python fetch_fix_queue.py --course-id 12345        # For a specific course
    python fetch_fix_queue.py --session-id <uuid>      # For a specific audit session
    python fetch_fix_queue.py --with-feedback           # Include reviewer feedback on each finding
    python fetch_fix_queue.py --summary                 # Just counts by standard/category
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from idw_logger import get_logger
    _log = get_logger("fetch_fix_queue")
except ImportError:
    import logging
    _log = logging.getLogger("fetch_fix_queue")

PLUGIN_ROOT = Path(__file__).resolve().parents[1]

try:
    from dotenv import load_dotenv
    load_dotenv(PLUGIN_ROOT / ".env")
    load_dotenv(PLUGIN_ROOT / ".env.local")
except ImportError:
    pass


def _get_supabase_config():
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        return None, None
    return url, key


def _supabase_get(url, key, table, params=None):
    import requests
    resp = requests.get(
        f"{url}/rest/v1/{table}",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        params=params or {},
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json()
    _log.error("GET %s failed: %s %s", table, resp.status_code, resp.text[:200])
    return None


def fetch_fix_queue(course_id=None, session_id=None, with_feedback=False):
    """Fetch findings where remediation_requested=true.

    Returns list of dicts with finding + session info, sorted by standard_id.
    """
    url, key = _get_supabase_config()
    if not url:
        return {"error": "Supabase credentials not configured."}

    # Build query params
    params = {
        "remediation_requested": "eq.true",
        "order": "standard_id.asc,page_title.asc",
        "select": "id,session_id,finding_type,standard_id,page_url,page_title,ai_verdict,ai_reasoning,content_excerpt,confidence_tier,reviewer_tier,canvas_link,page_slug,module_id,criterion_id,category,created_at",
    }
    if course_id:
        # Need to join through audit_sessions to filter by course
        params["select"] = f"{params['select']},audit_sessions!inner(course_id,course_name,course_code,run_date)"
        params["audit_sessions.course_id"] = f"eq.{course_id}"
    if session_id:
        params["session_id"] = f"eq.{session_id}"

    findings = _supabase_get(url, key, "audit_findings", params)
    if findings is None:
        return {"error": "Failed to fetch fix queue."}

    if not findings:
        return {"findings": [], "count": 0, "message": "No remediation items in the queue."}

    # Optionally enrich with feedback
    if with_feedback and findings:
        finding_ids = [f["id"] for f in findings]
        # Fetch feedback for these findings (latest per finding)
        feedback_params = {
            "finding_id": f"in.({','.join(finding_ids)})",
            "order": "reviewed_at.desc",
        }
        feedback = _supabase_get(url, key, "finding_feedback", feedback_params) or []

        # Group by finding_id (take latest)
        fb_map = {}
        for fb in feedback:
            fid = fb["finding_id"]
            if fid not in fb_map:
                fb_map[fid] = fb

        for f in findings:
            f["latest_feedback"] = fb_map.get(f["id"])

    return {
        "findings": findings,
        "count": len(findings),
    }


def summarize_queue(findings):
    """Summarize fix queue by standard and category."""
    by_standard = {}
    by_category = {}
    for f in findings:
        sid = f.get("standard_id", "unknown")
        cat = f.get("category", "unknown")
        by_standard[sid] = by_standard.get(sid, 0) + 1
        by_category[cat] = by_category.get(cat, 0) + 1

    return {
        "total": len(findings),
        "by_standard": dict(sorted(by_standard.items())),
        "by_category": dict(sorted(by_category.items())),
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch remediation fix queue from Supabase")
    parser.add_argument("--course-id", help="Filter by Canvas course ID")
    parser.add_argument("--session-id", help="Filter by audit session ID")
    parser.add_argument("--with-feedback", action="store_true", help="Include latest reviewer feedback")
    parser.add_argument("--summary", action="store_true", help="Show counts only")
    args = parser.parse_args()

    result = fetch_fix_queue(
        course_id=args.course_id,
        session_id=args.session_id,
        with_feedback=args.with_feedback,
    )

    if "error" in result:
        print(json.dumps(result, indent=2))
        sys.exit(1)

    if args.summary and result.get("findings"):
        summary = summarize_queue(result["findings"])
        print(json.dumps(summary, indent=2))
    else:
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
