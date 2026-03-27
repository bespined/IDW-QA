#!/usr/bin/env python3
"""Timestamped backup and rollback manager for Canvas pages.

Ported from Canvas Shadow Editor.

Storage layout:
    backups/{course_id}/{ISO_timestamp}/{page_slug}.html
    backups/{course_id}/{ISO_timestamp}/metadata.json

Usage:
    python backup_manager.py --save --course-id 12345 --page-slug m1-overview --html-file page.html --diff-summary "+5 / -2"
    python backup_manager.py --list --course-id 12345
    python backup_manager.py --get --course-id 12345 --timestamp 20260312T150000Z --page-slug m1-overview
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Logging
try:
    from idw_logger import get_logger
    _log = get_logger("backup_manager")
    from idw_metrics import track as _track
except ImportError:
    import logging
    _log = logging.getLogger("backup_manager")
    def _track(*a, **k): pass



PLUGIN_ROOT = Path(__file__).resolve().parents[1]
BACKUP_ROOT = PLUGIN_ROOT / "backups"


def _checksum(content):
    """SHA256 checksum of content string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def save_backup(course_id, page_slug, html, diff_summary_text=""):
    """Save a pre-change HTML backup with metadata.

    Returns:
        Path to the saved HTML file.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = BACKUP_ROOT / str(course_id) / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    html_path = backup_dir / f"{page_slug}.html"
    html_path.write_text(html, encoding="utf-8")

    metadata_path = backup_dir / "metadata.json"
    entry = {
        "page_slug": page_slug,
        "checksum": _checksum(html),
        "diff_summary": diff_summary_text,
    }

    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    else:
        metadata = {"course_id": str(course_id), "timestamp": timestamp, "pages": []}

    metadata["pages"].append(entry)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    _track("backup_created")
    return str(html_path)


def find_backup(course_id, page_slug, timestamp=None):
    """Find a backup HTML file. Returns path string.

    If timestamp is provided, returns the exact backup.
    Otherwise, returns the most recent backup for the page.
    """
    course_dir = BACKUP_ROOT / str(course_id)
    if not course_dir.exists():
        raise FileNotFoundError("No backups found for course")

    if timestamp:
        candidate = course_dir / timestamp / f"{page_slug}.html"
        if not candidate.exists():
            raise FileNotFoundError("Backup not found for timestamp")
        return str(candidate)

    backups = sorted(course_dir.glob(f"*/{page_slug}.html"), reverse=True)
    if not backups:
        raise FileNotFoundError("No backups found for page")
    return str(backups[0])


def list_backups(course_id):
    """List all backups for a course, newest first.

    Returns:
        List of dicts with timestamp, page_slug, diff_summary, checksum, size_bytes.
    """
    course_dir = BACKUP_ROOT / str(course_id)
    if not course_dir.exists():
        return []

    entries = []
    for meta_path in sorted(course_dir.glob("*/metadata.json"), reverse=True):
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            timestamp = metadata.get("timestamp", meta_path.parent.name)
            for page in metadata.get("pages", []):
                html_path = meta_path.parent / f"{page['page_slug']}.html"
                entries.append({
                    "timestamp": timestamp,
                    "page_slug": page["page_slug"],
                    "diff_summary": page.get("diff_summary", ""),
                    "checksum": page.get("checksum", ""),
                    "has_html": html_path.exists(),
                    "size_bytes": html_path.stat().st_size if html_path.exists() else 0,
                })
        except (json.JSONDecodeError, KeyError):
            continue

    return entries


def get_backup_html(course_id, timestamp, page_slug):
    """Read the HTML content of a specific backup."""
    html_path = BACKUP_ROOT / str(course_id) / timestamp / f"{page_slug}.html"
    if not html_path.exists():
        raise FileNotFoundError(f"Backup not found: {course_id}/{timestamp}/{page_slug}")
    return html_path.read_text(encoding="utf-8")


def get_batch_backup(course_id, timestamp):
    """Get all page backups from a single timestamp (batch rollback).

    Returns:
        List of dicts with page_slug, html, checksum for each page in the batch.
    """
    backup_dir = BACKUP_ROOT / str(course_id) / timestamp
    if not backup_dir.exists():
        raise FileNotFoundError(f"No backup found at {course_id}/{timestamp}")

    metadata_path = backup_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"No metadata found at {course_id}/{timestamp}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    results = []
    for page in metadata.get("pages", []):
        slug = page["page_slug"]
        html_path = backup_dir / f"{slug}.html"
        if html_path.exists():
            results.append({
                "page_slug": slug,
                "html": html_path.read_text(encoding="utf-8"),
                "checksum": page.get("checksum", ""),
                "diff_summary": page.get("diff_summary", ""),
            })

    return results


def list_batch_timestamps(course_id):
    """List all backup timestamps with page counts, newest first.

    Returns:
        List of dicts with timestamp, page_count, page_slugs.
    """
    course_dir = BACKUP_ROOT / str(course_id)
    if not course_dir.exists():
        return []

    batches = []
    for meta_path in sorted(course_dir.glob("*/metadata.json"), reverse=True):
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            timestamp = metadata.get("timestamp", meta_path.parent.name)
            pages = metadata.get("pages", [])
            batches.append({
                "timestamp": timestamp,
                "page_count": len(pages),
                "page_slugs": [p["page_slug"] for p in pages],
            })
        except (json.JSONDecodeError, KeyError):
            continue

    return batches


def main():
    parser = argparse.ArgumentParser(description="Canvas page backup manager")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--save", action="store_true", help="Save a backup")
    group.add_argument("--list", action="store_true", help="List backups for a course")
    group.add_argument("--get", action="store_true", help="Get backup HTML content")
    group.add_argument("--batch-get", action="store_true", help="Get all pages from a timestamp")
    group.add_argument("--batch-list", action="store_true", help="List batch timestamps")

    parser.add_argument("--course-id", required=True, help="Canvas course ID")
    parser.add_argument("--page-slug", help="Page slug (required for --save and --get)")
    parser.add_argument("--html-file", help="HTML file to backup (required for --save)")
    parser.add_argument("--diff-summary", default="", help="Diff summary string")
    parser.add_argument("--timestamp", help="Backup timestamp (required for --get)")

    args = parser.parse_args()

    if args.save:
        if not args.page_slug or not args.html_file:
            parser.error("--save requires --page-slug and --html-file")
        try:
            html = open(args.html_file, "r", encoding="utf-8").read()
        except FileNotFoundError:
            _log.error(f"ERROR: File not found: {args.html_file}")
            sys.exit(1)
        path = save_backup(args.course_id, args.page_slug, html, args.diff_summary)
        print(json.dumps({"ok": True, "path": path}))

    elif args.list:
        entries = list_backups(args.course_id)
        print(json.dumps({"ok": True, "count": len(entries), "backups": entries}, indent=2))

    elif args.get:
        if not args.page_slug or not args.timestamp:
            parser.error("--get requires --page-slug and --timestamp")
        try:
            html = get_backup_html(args.course_id, args.timestamp, args.page_slug)
            print(html)
        except FileNotFoundError as e:
            print(json.dumps({"ok": False, "error": str(e)}))
            sys.exit(1)

    elif args.batch_get:
        if not args.timestamp:
            parser.error("--batch-get requires --timestamp")
        try:
            pages = get_batch_backup(args.course_id, args.timestamp)
            print(json.dumps({
                "ok": True,
                "timestamp": args.timestamp,
                "page_count": len(pages),
                "pages": [{"page_slug": p["page_slug"], "checksum": p["checksum"]} for p in pages],
            }, indent=2))
        except FileNotFoundError as e:
            print(json.dumps({"ok": False, "error": str(e)}))
            sys.exit(1)

    elif args.batch_list:
        batches = list_batch_timestamps(args.course_id)
        print(json.dumps({"ok": True, "count": len(batches), "batches": batches}, indent=2))


if __name__ == "__main__":
    main()
