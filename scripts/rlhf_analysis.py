#!/usr/bin/env python3
"""RLHF Analysis — aggregate finding_feedback for agreement rates and trends.

Queries Supabase to produce analysis of how well the AI audit aligns with
human reviewers, broken down by standard, reviewer, criterion, and time period.

Usage:
    python rlhf_analysis.py --summary              # Overall stats + top issues
    python rlhf_analysis.py --by-standard           # Agreement rate per standard
    python rlhf_analysis.py --by-reviewer           # Stats per reviewer
    python rlhf_analysis.py --by-criterion          # Agreement rate per criterion_id
    python rlhf_analysis.py --trends                # Weekly agreement trend
    python rlhf_analysis.py --low-agreement [--threshold 70]  # Standards below threshold
    python rlhf_analysis.py --corrections           # List all incorrect findings with corrections
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from idw_logger import get_logger
    _log = get_logger("rlhf_analysis")
except ImportError:
    import logging
    _log = logging.getLogger("rlhf_analysis")

PLUGIN_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, os.path.dirname(__file__))
import supabase_client


def _normalize_decision(decision):
    """Map old decision values to normalized ones."""
    mapping = {
        "approved": "correct",
        "rejected": "incorrect",
        "false_positive": "correct",
        "correct": "correct",
        "incorrect": "incorrect",
        "not_applicable": "not_applicable",
    }
    return mapping.get(decision, decision)


def _fetch_all_feedback():
    """Fetch all feedback with joined finding data."""
    if not supabase_client.is_configured():
        print(json.dumps({"error": "Supabase credentials not configured."}))
        sys.exit(1)

    feedback = supabase_client.get("finding_feedback", params={
        "select": "id,finding_id,reviewer_name,reviewer_tier,decision,corrected_finding,correction_note,reviewed_at,audit_findings(standard_id,finding_type,criterion_id,category,ai_verdict,session_id)",
        "order": "reviewed_at.desc",
    })
    if feedback is None:
        print(json.dumps({"error": "Failed to fetch feedback data."}))
        sys.exit(1)

    # Normalize decisions
    for fb in feedback:
        fb["_normalized"] = _normalize_decision(fb.get("decision", ""))

    return feedback


def analysis_summary(feedback):
    """Overall summary stats."""
    total = len(feedback)
    if total == 0:
        return {"total_reviews": 0, "message": "No feedback data yet."}

    agreed = sum(1 for fb in feedback if fb["_normalized"] == "correct")
    disagreed = sum(1 for fb in feedback if fb["_normalized"] == "incorrect")
    na = sum(1 for fb in feedback if fb["_normalized"] == "not_applicable")
    substantive = agreed + disagreed  # exclude N/A from agreement calc

    agreement_rate = round(agreed / substantive * 100) if substantive > 0 else 0

    # Unique reviewers
    reviewers = set(fb.get("reviewer_name", "?") for fb in feedback if fb.get("reviewer_name"))

    # Unique standards reviewed
    standards = set()
    for fb in feedback:
        af = fb.get("audit_findings")
        if af and af.get("standard_id"):
            standards.add(af["standard_id"])

    return {
        "total_reviews": total,
        "agreed": agreed,
        "disagreed": disagreed,
        "not_applicable": na,
        "agreement_rate_pct": agreement_rate,
        "target_rate_pct": 85,
        "gap_pct": max(0, 85 - agreement_rate),
        "unique_reviewers": len(reviewers),
        "unique_standards_reviewed": len(standards),
    }


def analysis_by_standard(feedback):
    """Agreement rate per standard_id."""
    by_std = defaultdict(lambda: {"agreed": 0, "disagreed": 0, "na": 0, "total": 0})

    for fb in feedback:
        af = fb.get("audit_findings") or {}
        sid = af.get("standard_id", "unknown")
        bucket = by_std[sid]
        bucket["total"] += 1
        norm = fb["_normalized"]
        if norm == "correct":
            bucket["agreed"] += 1
        elif norm == "incorrect":
            bucket["disagreed"] += 1
        elif norm == "not_applicable":
            bucket["na"] += 1

    result = []
    for sid, counts in sorted(by_std.items()):
        substantive = counts["agreed"] + counts["disagreed"]
        rate = round(counts["agreed"] / substantive * 100) if substantive > 0 else None
        result.append({
            "standard_id": sid,
            "total": counts["total"],
            "agreed": counts["agreed"],
            "disagreed": counts["disagreed"],
            "not_applicable": counts["na"],
            "agreement_rate_pct": rate,
        })

    # Sort by agreement rate ascending (worst first)
    result.sort(key=lambda x: (x["agreement_rate_pct"] is None, x["agreement_rate_pct"] or 0))
    return result


def analysis_by_reviewer(feedback):
    """Stats per reviewer."""
    by_rev = defaultdict(lambda: {"agreed": 0, "disagreed": 0, "na": 0, "total": 0, "first": None, "last": None})

    for fb in feedback:
        name = fb.get("reviewer_name", "unknown")
        bucket = by_rev[name]
        bucket["total"] += 1
        norm = fb["_normalized"]
        if norm == "correct":
            bucket["agreed"] += 1
        elif norm == "incorrect":
            bucket["disagreed"] += 1
        elif norm == "not_applicable":
            bucket["na"] += 1

        ts = fb.get("reviewed_at", "")
        if ts:
            if bucket["first"] is None or ts < bucket["first"]:
                bucket["first"] = ts
            if bucket["last"] is None or ts > bucket["last"]:
                bucket["last"] = ts

    result = []
    for name, counts in sorted(by_rev.items(), key=lambda x: x[1]["total"], reverse=True):
        substantive = counts["agreed"] + counts["disagreed"]
        rate = round(counts["agreed"] / substantive * 100) if substantive > 0 else None
        result.append({
            "reviewer": name,
            "total": counts["total"],
            "agreed": counts["agreed"],
            "disagreed": counts["disagreed"],
            "not_applicable": counts["na"],
            "agreement_rate_pct": rate,
            "first_review": counts["first"],
            "last_review": counts["last"],
        })
    return result


def analysis_by_criterion(feedback):
    """Agreement rate per criterion_id."""
    by_crit = defaultdict(lambda: {"agreed": 0, "disagreed": 0, "na": 0, "total": 0, "standard_id": None})

    for fb in feedback:
        af = fb.get("audit_findings") or {}
        cid = af.get("criterion_id", "unknown")
        bucket = by_crit[cid]
        bucket["total"] += 1
        bucket["standard_id"] = af.get("standard_id")
        norm = fb["_normalized"]
        if norm == "correct":
            bucket["agreed"] += 1
        elif norm == "incorrect":
            bucket["disagreed"] += 1
        elif norm == "not_applicable":
            bucket["na"] += 1

    result = []
    for cid, counts in sorted(by_crit.items()):
        substantive = counts["agreed"] + counts["disagreed"]
        rate = round(counts["agreed"] / substantive * 100) if substantive > 0 else None
        result.append({
            "criterion_id": cid,
            "standard_id": counts["standard_id"],
            "total": counts["total"],
            "agreed": counts["agreed"],
            "disagreed": counts["disagreed"],
            "not_applicable": counts["na"],
            "agreement_rate_pct": rate,
        })

    result.sort(key=lambda x: (x["agreement_rate_pct"] is None, x["agreement_rate_pct"] or 0))
    return result


def analysis_trends(feedback):
    """Weekly agreement trend."""
    by_week = defaultdict(lambda: {"agreed": 0, "disagreed": 0, "total": 0})

    for fb in feedback:
        ts = fb.get("reviewed_at", "")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            # ISO week start (Monday)
            week_start = dt - timedelta(days=dt.weekday())
            week_key = week_start.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            continue

        bucket = by_week[week_key]
        bucket["total"] += 1
        norm = fb["_normalized"]
        if norm == "correct":
            bucket["agreed"] += 1
        elif norm == "incorrect":
            bucket["disagreed"] += 1

    result = []
    for week, counts in sorted(by_week.items()):
        substantive = counts["agreed"] + counts["disagreed"]
        rate = round(counts["agreed"] / substantive * 100) if substantive > 0 else None
        result.append({
            "week_of": week,
            "total": counts["total"],
            "agreed": counts["agreed"],
            "disagreed": counts["disagreed"],
            "agreement_rate_pct": rate,
        })
    return result


def analysis_corrections(feedback):
    """All findings marked incorrect with their corrections."""
    corrections = []
    for fb in feedback:
        if fb["_normalized"] != "incorrect":
            continue
        af = fb.get("audit_findings") or {}
        corrections.append({
            "finding_id": fb.get("finding_id"),
            "standard_id": af.get("standard_id"),
            "criterion_id": af.get("criterion_id"),
            "ai_verdict": af.get("ai_verdict"),
            "reviewer": fb.get("reviewer_name"),
            "corrected_finding": fb.get("corrected_finding"),
            "correction_note": fb.get("correction_note"),
            "reviewed_at": fb.get("reviewed_at"),
        })
    return corrections


def main():
    parser = argparse.ArgumentParser(description="RLHF analysis for IDW QA audit feedback")
    parser.add_argument("--summary", action="store_true", help="Overall summary stats")
    parser.add_argument("--by-standard", action="store_true", help="Agreement rate per standard")
    parser.add_argument("--by-reviewer", action="store_true", help="Stats per reviewer")
    parser.add_argument("--by-criterion", action="store_true", help="Agreement rate per criterion")
    parser.add_argument("--trends", action="store_true", help="Weekly agreement trend")
    parser.add_argument("--low-agreement", action="store_true", help="Standards below threshold")
    parser.add_argument("--threshold", type=int, default=70, help="Agreement threshold %% (default: 70)")
    parser.add_argument("--corrections", action="store_true", help="List all incorrect findings with corrections")
    args = parser.parse_args()

    # Default to --summary if nothing specified
    if not any([args.summary, args.by_standard, args.by_reviewer, args.by_criterion,
                args.trends, args.low_agreement, args.corrections]):
        args.summary = True

    feedback = _fetch_all_feedback()

    output = {}

    if args.summary:
        output["summary"] = analysis_summary(feedback)

    if args.by_standard:
        output["by_standard"] = analysis_by_standard(feedback)

    if args.by_reviewer:
        output["by_reviewer"] = analysis_by_reviewer(feedback)

    if args.by_criterion:
        output["by_criterion"] = analysis_by_criterion(feedback)

    if args.trends:
        output["trends"] = analysis_trends(feedback)

    if args.low_agreement:
        by_std = analysis_by_standard(feedback)
        output["low_agreement"] = [
            s for s in by_std
            if s["agreement_rate_pct"] is not None and s["agreement_rate_pct"] < args.threshold
        ]
        output["threshold"] = args.threshold

    if args.corrections:
        output["corrections"] = analysis_corrections(feedback)

    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
