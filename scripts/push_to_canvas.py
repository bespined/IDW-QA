#!/usr/bin/env python3
"""Atomic Canvas push wrapper — enforces backup → push → clear → verify → remediation trail.

This script replaces all inline Canvas write operations. No content skill should
push directly to Canvas — all writes go through this script.

Usage:
    # Push a staged page (backup → push → clear staging)
    python3 scripts/push_to_canvas.py --type page --slug m1-overview

    # Push multiple staged pages
    python3 scripts/push_to_canvas.py --type page --slugs m1-overview,m2-overview

    # Push an assignment description from file
    python3 scripts/push_to_canvas.py --type assignment --id 7307765 --html-file /tmp/desc.html

    # Push a quiz description
    python3 scripts/push_to_canvas.py --type quiz --id 12345 --html-file /tmp/quiz.html

    # Push with remediation tracking (records events + clears flags)
    python3 scripts/push_to_canvas.py --type page --slug m1-overview \
        --finding-ids abc123,def456 --skill bulk-edit

    # Dry run (validates everything but doesn't write)
    python3 scripts/push_to_canvas.py --type page --slug m1-overview --dry-run
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import canvas_api

try:
    from idw_logger import get_logger
    _log = get_logger("push_to_canvas")
except ImportError:
    import logging
    _log = logging.getLogger("push_to_canvas")

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _get_supabase_config():
    """Load Supabase config from .env + .env.local."""
    try:
        from dotenv import load_dotenv
        load_dotenv(PLUGIN_ROOT / ".env")
        load_dotenv(PLUGIN_ROOT / ".env.local", override=True)
    except ImportError:
        pass
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        return None, None
    return url, key


def _record_remediation_events(finding_ids, skill, description, tester_id):
    """Record remediation events and clear remediation_requested flags."""
    import requests
    url, key = _get_supabase_config()
    if not url:
        _log.warning("Supabase not configured — skipping remediation event recording")
        return 0

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    recorded = 0
    for fid in finding_ids:
        fid = fid.strip()
        if not fid:
            continue

        # Record event
        resp = requests.post(
            f"{url}/rest/v1/remediation_events",
            headers=headers,
            json={
                "finding_id": fid,
                "remediated_by": tester_id,
                "skill_used": skill,
                "description": description,
            },
            timeout=15,
        )
        if resp.status_code in (200, 201):
            recorded += 1
        else:
            _log.error("Failed to record remediation event for %s: %s", fid, resp.status_code)

        # Clear remediation_requested flag
        requests.patch(
            f"{url}/rest/v1/audit_findings?id=eq.{fid}",
            headers=headers,
            json={"remediation_requested": False},
            timeout=15,
        )

    return recorded


def push_page(config, slug, dry_run=False):
    """Push a single staged page: backup → push → clear → verify."""
    import subprocess

    course_id = config["course_id"]

    # 1. Get raw content from staging
    result = subprocess.run(
        [sys.executable, "scripts/staging_manager.py", "--get-raw", "--slug", slug],
        capture_output=True, text=True, cwd=str(PLUGIN_ROOT),
    )
    if result.returncode != 0 or not result.stdout.strip():
        return {"ok": False, "error": f"No staged content for slug: {slug}", "slug": slug}

    raw_html = result.stdout.strip()
    # Handle JSON error prefix from staging_manager
    if raw_html.startswith("{"):
        lines = raw_html.split("\n")
        try:
            first = json.loads(lines[0])
            if not first.get("ok", True):
                return {"ok": False, "error": first.get("error", "Unknown staging error"), "slug": slug}
        except json.JSONDecodeError:
            pass
        raw_html = "\n".join(lines[1:]).strip()

    if not raw_html:
        return {"ok": False, "error": f"Empty content for slug: {slug}", "slug": slug}

    # 2. Backup current Canvas page
    current_page = canvas_api.get_page(config, slug)

    if current_page and current_page.get("body"):
        # Write current body to temp file for backup
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False)
        tmp.write(current_page["body"])
        tmp.close()

        if not dry_run:
            backup_result = subprocess.run(
                [sys.executable, "scripts/backup_manager.py",
                 "--save", "--course-id", str(course_id),
                 "--page-slug", slug, "--html-file", tmp.name,
                 "--diff-summary", "Pre-push backup via push_to_canvas.py"],
                capture_output=True, text=True, cwd=str(PLUGIN_ROOT),
            )
            os.unlink(tmp.name)

            if backup_result.returncode != 0:
                return {"ok": False, "error": f"Backup failed for {slug}: {backup_result.stderr}", "slug": slug}
            _log.info("Backup created for %s", slug)
        else:
            os.unlink(tmp.name)
            _log.info("[DRY RUN] Would backup %s", slug)

    # 3. Push to Canvas
    if not dry_run:
        success = canvas_api.update_page(config, slug, raw_html)
        if not success:
            return {"ok": False, "error": f"Canvas API push failed for {slug}", "slug": slug}
        _log.info("Pushed %s to Canvas", slug)
    else:
        _log.info("[DRY RUN] Would push %s (%d chars)", slug, len(raw_html))

    # 4. Clear staging
    if not dry_run:
        subprocess.run(
            [sys.executable, "scripts/staging_manager.py", "--clear", "--slug", slug],
            capture_output=True, text=True, cwd=str(PLUGIN_ROOT),
        )
        _log.info("Cleared staging for %s", slug)

    # 5. Verify
    canvas_url = f"https://{config['domain']}/courses/{course_id}/pages/{slug}"
    if not dry_run:
        verify_page = canvas_api.get_page(config, slug)
        if not verify_page:
            return {"ok": False, "error": f"Post-push verification failed — page not found: {slug}", "slug": slug}
        content_len = len(verify_page.get("body", ""))
    else:
        content_len = len(raw_html)

    return {
        "ok": True,
        "slug": slug,
        "canvas_url": canvas_url,
        "content_length": content_len,
        "dry_run": dry_run,
    }


def push_assignment(config, assignment_id, html_content, dry_run=False):
    """Push an assignment description to Canvas."""
    import requests

    canvas_api.require_course_id(config)
    canvas_api._check_write_allowed(config, f"push_assignment({assignment_id})")

    if dry_run:
        _log.info("[DRY RUN] Would push assignment %s (%d chars)", assignment_id, len(html_content))
        return {
            "ok": True, "id": assignment_id, "dry_run": True,
            "canvas_url": f"https://{config['domain']}/courses/{config['course_id']}/assignments/{assignment_id}",
        }

    resp = requests.put(
        f"{config['course_url']}/assignments/{assignment_id}",
        headers=config["headers"],
        json={"assignment": {"description": html_content}},
        timeout=15,
    )

    if resp.status_code != 200:
        return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}", "id": assignment_id}

    data = resp.json()
    return {
        "ok": True,
        "id": assignment_id,
        "name": data.get("name"),
        "canvas_url": f"https://{config['domain']}/courses/{config['course_id']}/assignments/{assignment_id}",
        "content_length": len(data.get("description", "")),
    }


def push_quiz(config, quiz_id, html_content, dry_run=False):
    """Push a quiz description to Canvas."""
    import requests

    canvas_api.require_course_id(config)
    canvas_api._check_write_allowed(config, f"push_quiz({quiz_id})")

    if dry_run:
        return {
            "ok": True, "id": quiz_id, "dry_run": True,
            "canvas_url": f"https://{config['domain']}/courses/{config['course_id']}/quizzes/{quiz_id}",
        }

    resp = requests.put(
        f"{config['course_url']}/quizzes/{quiz_id}",
        headers=config["headers"],
        json={"quiz": {"description": html_content}},
        timeout=15,
    )

    if resp.status_code != 200:
        return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}", "id": quiz_id}

    data = resp.json()
    return {
        "ok": True,
        "id": quiz_id,
        "name": data.get("title"),
        "canvas_url": f"https://{config['domain']}/courses/{config['course_id']}/quizzes/{quiz_id}",
    }


def push_discussion(config, topic_id, html_content, dry_run=False):
    """Push a discussion message body to Canvas."""
    import requests

    canvas_api.require_course_id(config)
    canvas_api._check_write_allowed(config, f"push_discussion({topic_id})")

    if dry_run:
        return {
            "ok": True, "id": topic_id, "dry_run": True,
            "canvas_url": f"https://{config['domain']}/courses/{config['course_id']}/discussion_topics/{topic_id}",
        }

    resp = requests.put(
        f"{config['course_url']}/discussion_topics/{topic_id}",
        headers=config["headers"],
        json={"message": html_content},  # discussion body is "message", not "description"
        timeout=15,
    )

    if resp.status_code != 200:
        return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}", "id": topic_id}

    data = resp.json()
    return {
        "ok": True,
        "id": topic_id,
        "name": data.get("title"),
        "canvas_url": f"https://{config['domain']}/courses/{config['course_id']}/discussion_topics/{topic_id}",
    }


def main():
    parser = argparse.ArgumentParser(description="Atomic Canvas push wrapper")
    parser.add_argument("--type", required=True, choices=["page", "assignment", "quiz", "discussion"],
                        help="Content type to push")
    parser.add_argument("--slug", help="Page slug (for --type page, single page)")
    parser.add_argument("--slugs", help="Comma-separated page slugs (for --type page, batch)")
    parser.add_argument("--id", help="Canvas object ID (for assignment/quiz)")
    parser.add_argument("--html-file", help="HTML file to push (for assignment/quiz)")
    parser.add_argument("--finding-ids", help="Comma-separated finding IDs for remediation tracking")
    parser.add_argument("--skill", help="Skill name for remediation tracking")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing")
    args = parser.parse_args()

    config = canvas_api.get_config()
    canvas_api.require_course_id(config)

    # Check read-only mode
    if canvas_api.is_read_only() and not args.dry_run:
        print(json.dumps({"ok": False, "error": "CANVAS_READ_ONLY is enabled. Disable in .env to allow writes."}))
        sys.exit(1)

    results = []

    if args.type == "page":
        slugs = []
        if args.slugs:
            slugs = [s.strip() for s in args.slugs.split(",") if s.strip()]
        elif args.slug:
            slugs = [args.slug]
        else:
            print(json.dumps({"ok": False, "error": "Provide --slug or --slugs for page push"}))
            sys.exit(1)

        for slug in slugs:
            result = push_page(config, slug, dry_run=args.dry_run)
            results.append(result)
            if result["ok"]:
                print(f"✓ {slug} → {result.get('canvas_url', 'N/A')}")
            else:
                print(f"✗ {slug} — {result['error']}")

    elif args.type in ("assignment", "quiz", "discussion"):
        if not args.id:
            print(json.dumps({"ok": False, "error": f"Provide --id for {args.type} push"}))
            sys.exit(1)

        if args.html_file:
            html_content = Path(args.html_file).read_text(encoding="utf-8")
        else:
            html_content = sys.stdin.read()

        if args.type == "assignment":
            result = push_assignment(config, args.id, html_content, dry_run=args.dry_run)
        elif args.type == "quiz":
            result = push_quiz(config, args.id, html_content, dry_run=args.dry_run)
        else:
            result = push_discussion(config, args.id, html_content, dry_run=args.dry_run)

        results.append(result)
        if result["ok"]:
            print(f"✓ {args.type} {args.id} → {result.get('canvas_url', 'N/A')}")
        else:
            print(f"✗ {args.type} {args.id} — {result['error']}")

    # Record remediation events if finding IDs provided
    if args.finding_ids and not args.dry_run:
        all_ok = all(r["ok"] for r in results)
        if all_ok:
            tester_id = os.getenv("IDW_TESTER_ID", "")
            finding_ids = [f.strip() for f in args.finding_ids.split(",") if f.strip()]
            recorded = _record_remediation_events(
                finding_ids, args.skill or "unknown",
                f"Content pushed via push_to_canvas.py ({args.type})", tester_id,
            )
            print(f"  Remediation events recorded: {recorded}/{len(finding_ids)}")

    # Summary
    ok_count = sum(1 for r in results if r["ok"])
    fail_count = len(results) - ok_count
    summary = {"ok": fail_count == 0, "pushed": ok_count, "failed": fail_count, "results": results}
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
