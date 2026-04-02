#!/usr/bin/env python3
"""Post-push verification — fetches Canvas object and confirms it exists with expected properties.

Called after every Canvas write to replace prompt-only verification steps.

Usage:
    python3 scripts/post_write_verify.py --type page --slug m1-overview
    python3 scripts/post_write_verify.py --type assignment --id 7307765 --expected-points 20
    python3 scripts/post_write_verify.py --type quiz --id 12345 --expected-points 30 --expected-questions 7
    python3 scripts/post_write_verify.py --type discussion --id 67890
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import canvas_api

try:
    from idw_logger import get_logger
    _log = get_logger("post_write_verify")
except ImportError:
    import logging
    _log = logging.getLogger("post_write_verify")


def verify_page(config, slug):
    """Verify a Canvas page exists and has content."""
    page = canvas_api.get_page(config, slug)
    if not page:
        return {"ok": False, "type": "page", "slug": slug, "error": "Page not found"}

    body = page.get("body", "")
    warnings = []
    if not body or len(body.strip()) < 10:
        warnings.append("Page body is empty or very short")
    if not page.get("published", False):
        warnings.append("Page is not published")

    return {
        "ok": True,
        "type": "page",
        "slug": slug,
        "title": page.get("title", ""),
        "published": page.get("published", False),
        "content_length": len(body),
        "canvas_url": f"https://{config['domain']}/courses/{config['course_id']}/pages/{slug}",
        "warnings": warnings,
    }


def verify_assignment(config, assignment_id, expected_points=None):
    """Verify a Canvas assignment exists with expected properties."""
    import requests
    resp = requests.get(
        f"{config['course_url']}/assignments/{assignment_id}",
        headers=config["headers"], timeout=15,
    )
    if resp.status_code != 200:
        return {"ok": False, "type": "assignment", "id": assignment_id,
                "error": f"HTTP {resp.status_code}"}

    a = resp.json()
    warnings = []
    desc = a.get("description", "") or ""
    if len(desc.strip()) < 10:
        warnings.append("Assignment description is empty or very short")
    if not a.get("published", False):
        warnings.append("Assignment is not published")
    if expected_points is not None and a.get("points_possible") != expected_points:
        warnings.append(f"Points mismatch: expected {expected_points}, got {a.get('points_possible')}")
    if not a.get("rubric"):
        warnings.append("No rubric attached")

    return {
        "ok": True,
        "type": "assignment",
        "id": assignment_id,
        "name": a.get("name", ""),
        "points": a.get("points_possible"),
        "published": a.get("published", False),
        "has_rubric": bool(a.get("rubric")),
        "submission_types": a.get("submission_types", []),
        "content_length": len(desc),
        "canvas_url": f"https://{config['domain']}/courses/{config['course_id']}/assignments/{assignment_id}",
        "warnings": warnings,
    }


def verify_quiz(config, quiz_id, expected_points=None, expected_questions=None):
    """Verify a Canvas quiz exists with expected properties."""
    import requests
    resp = requests.get(
        f"{config['course_url']}/quizzes/{quiz_id}",
        headers=config["headers"], timeout=15,
    )
    if resp.status_code != 200:
        return {"ok": False, "type": "quiz", "id": quiz_id,
                "error": f"HTTP {resp.status_code}"}

    q = resp.json()
    warnings = []
    if not q.get("published", False):
        warnings.append("Quiz is not published")
    if expected_points is not None and q.get("points_possible") != expected_points:
        warnings.append(f"Points mismatch: expected {expected_points}, got {q.get('points_possible')}")
    if expected_questions is not None and q.get("question_count", 0) != expected_questions:
        warnings.append(f"Question count mismatch: expected {expected_questions}, got {q.get('question_count')}")
    if q.get("question_count", 0) == 0:
        warnings.append("Quiz has no questions")

    return {
        "ok": True,
        "type": "quiz",
        "id": quiz_id,
        "title": q.get("title", ""),
        "points": q.get("points_possible"),
        "published": q.get("published", False),
        "question_count": q.get("question_count", 0),
        "allowed_attempts": q.get("allowed_attempts"),
        "time_limit": q.get("time_limit"),
        "canvas_url": f"https://{config['domain']}/courses/{config['course_id']}/quizzes/{quiz_id}",
        "warnings": warnings,
    }


def verify_discussion(config, discussion_id):
    """Verify a Canvas discussion topic exists."""
    import requests
    resp = requests.get(
        f"{config['course_url']}/discussion_topics/{discussion_id}",
        headers=config["headers"], timeout=15,
    )
    if resp.status_code != 200:
        return {"ok": False, "type": "discussion", "id": discussion_id,
                "error": f"HTTP {resp.status_code}"}

    d = resp.json()
    warnings = []
    msg = d.get("message", "") or ""
    if len(msg.strip()) < 10:
        warnings.append("Discussion message is empty or very short")
    if not d.get("published", False):
        warnings.append("Discussion is not published")

    return {
        "ok": True,
        "type": "discussion",
        "id": discussion_id,
        "title": d.get("title", ""),
        "published": d.get("published", False),
        "content_length": len(msg),
        "canvas_url": f"https://{config['domain']}/courses/{config['course_id']}/discussion_topics/{discussion_id}",
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(description="Post-push verification")
    parser.add_argument("--type", required=True, choices=["page", "assignment", "quiz", "discussion"])
    parser.add_argument("--slug", help="Page slug")
    parser.add_argument("--id", help="Canvas object ID")
    parser.add_argument("--expected-points", type=float, help="Expected point value")
    parser.add_argument("--expected-questions", type=int, help="Expected question count (quiz only)")
    args = parser.parse_args()

    config = canvas_api.get_config()
    canvas_api.require_course_id(config)

    if args.type == "page":
        if not args.slug:
            print(json.dumps({"ok": False, "error": "Provide --slug for page verification"}))
            sys.exit(1)
        result = verify_page(config, args.slug)
    elif args.type == "assignment":
        if not args.id:
            print(json.dumps({"ok": False, "error": "Provide --id for assignment verification"}))
            sys.exit(1)
        result = verify_assignment(config, args.id, args.expected_points)
    elif args.type == "quiz":
        if not args.id:
            print(json.dumps({"ok": False, "error": "Provide --id for quiz verification"}))
            sys.exit(1)
        result = verify_quiz(config, args.id, args.expected_points, args.expected_questions)
    elif args.type == "discussion":
        if not args.id:
            print(json.dumps({"ok": False, "error": "Provide --id for discussion verification"}))
            sys.exit(1)
        result = verify_discussion(config, args.id)

    # Print human-friendly summary
    if result["ok"]:
        warnings = result.get("warnings", [])
        name = result.get("title") or result.get("name") or result.get("slug", "")
        status = "✓ VERIFIED" if not warnings else f"⚠ VERIFIED with {len(warnings)} warning(s)"
        print(f"{status}: {name}")
        print(f"  URL: {result['canvas_url']}")
        if "content_length" in result:
            print(f"  Content: {result['content_length']} chars")
        if "points" in result and result["points"] is not None:
            print(f"  Points: {result['points']}")
        if "has_rubric" in result:
            print(f"  Rubric: {'Yes' if result['has_rubric'] else 'No'}")
        for w in warnings:
            print(f"  ⚠ {w}")
    else:
        print(f"✗ VERIFICATION FAILED: {result.get('error', 'Unknown error')}")

    print(json.dumps(result))


if __name__ == "__main__":
    main()
