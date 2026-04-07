#!/usr/bin/env python3
"""Staging manager — stage Canvas page HTML locally for preview before push.

Staged pages are wrapped in a Canvas-like shell template for visual preview
via Claude Preview. Content is stored as standalone HTML files.

Usage:
    python staging_manager.py --stage --slug m1-overview --html-file content.html
    python staging_manager.py --stage --slug m1-overview --html-stdin  (reads from stdin)
    python staging_manager.py --list
    python staging_manager.py --get --slug m1-overview
    python staging_manager.py --get-raw --slug m1-overview  (without shell wrapper)
    python staging_manager.py --clear [--slug m1-overview]
    python staging_manager.py --update --slug m1-overview --html-file updated.html
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Logging
try:
    from idw_logger import get_logger
    _log = get_logger("staging_manager")
    from idw_metrics import track as _track
except ImportError:
    import logging
    _log = logging.getLogger("staging_manager")
    def _track(*a, **k): pass



PLUGIN_ROOT = Path(__file__).resolve().parents[1]
STAGING_ROOT = PLUGIN_ROOT / "staging"
SHELL_PATH = PLUGIN_ROOT / "templates" / "canvas-shell.html"

# Marker used to extract raw content from staged files
CONTENT_MARKER = "{{CONTENT}}"
RAW_START = '<!-- RAW_CONTENT_START -->'
RAW_END = '<!-- RAW_CONTENT_END -->'


def _sanitize_folder_name(name):
    """Sanitize a course name for use as a folder name."""
    import re
    name = re.sub(r'[^\w\s\-]', '', name)
    name = re.sub(r'\s+', '-', name.strip())
    return name[:80] or 'unknown-course'


def _get_course_name():
    """Get the active course name from course-config.json, cache, or .env fallback."""
    # Try course-config.json
    config_path = PLUGIN_ROOT / "course-config.json"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            name = cfg.get("course", {}).get("name") or cfg.get("course_name") or cfg.get("name")
            if name:
                return name
        except (json.JSONDecodeError, KeyError):
            pass

    # Try .course-name cache file (written by setup/concierge)
    cache_path = PLUGIN_ROOT / ".course-name"
    if cache_path.exists():
        name = cache_path.read_text(encoding="utf-8").strip()
        if name:
            return name

    # Try fetching from Canvas API (and cache the result)
    course_id = os.environ.get("CANVAS_COURSE_ID", "")
    if course_id:
        try:
            from canvas_api import get_config
            config = get_config()
            import requests
            resp = requests.get(
                f"{config['base_url']}/courses/{course_id}",
                headers=config['headers'],
                timeout=10
            )
            if resp.status_code == 200:
                name = resp.json().get("name", "")
                if name:
                    cache_path.write_text(name, encoding="utf-8")
                    return name
        except (ImportError, OSError, ValueError):
            pass
        return f"course-{course_id}"

    return "unknown-course"


def get_staging_dir():
    """Get the course-specific staging directory.

    Returns staging/{sanitized-course-name}/ based on the active course.
    Creates the directory if it doesn't exist.
    """
    course_name = _get_course_name()
    staging_dir = STAGING_ROOT / _sanitize_folder_name(course_name)
    staging_dir.mkdir(parents=True, exist_ok=True)
    return staging_dir




def _load_shell():
    """Load the Canvas shell template."""
    if not SHELL_PATH.exists():
        _log.error(f"ERROR: Canvas shell template not found at {SHELL_PATH}")
        sys.exit(1)
    return SHELL_PATH.read_text(encoding="utf-8")


def _wrap_content(html_content):
    """Wrap raw HTML content in the Canvas shell template with extraction markers."""
    shell = _load_shell()
    wrapped = f"{RAW_START}\n{html_content}\n{RAW_END}"
    return shell.replace(CONTENT_MARKER, wrapped)


def _extract_raw(staged_html):
    """Extract the raw content from a staged file (strips the shell wrapper)."""
    start_idx = staged_html.find(RAW_START)
    end_idx = staged_html.find(RAW_END)
    if start_idx == -1 or end_idx == -1:
        return staged_html  # No markers — return as-is
    return staged_html[start_idx + len(RAW_START):end_idx].strip()


def stage_page(slug, html_content, validate=True):
    """Write a page to the staging directory wrapped in the Canvas shell.

    Args:
        slug: Page slug (e.g., 'm1-overview')
        html_content: Raw HTML content (without shell wrapper)
        validate: If True (default), run preflight checks and save .issues.json

    Returns:
        Path to the staged file.
    """
    get_staging_dir().mkdir(parents=True, exist_ok=True)
    staged_path = get_staging_dir() / f"{slug}.html"
    full_html = _wrap_content(html_content)
    staged_path.write_text(full_html, encoding="utf-8")

    # Run preflight checks if enabled
    if validate:
        _run_preflight(slug, html_content)

    return str(staged_path)


def _run_preflight(slug, html_content):
    """Run preflight checks on staged content, save issues to sidecar JSON."""
    try:
        from preflight_checks import check_page, summarize_issues, _infer_page_type
    except ImportError:
        _log.debug("preflight_checks not available — skipping validation")
        return

    # Build context from slug and course-config.json if available
    context = {
        "slug": slug,
        "page_type": _infer_page_type("", slug),
    }

    # Try to load objectives from course-config.json
    config_path = PLUGIN_ROOT / "course-config.json"
    if config_path.exists():
        try:
            import json as _json
            cfg = _json.loads(config_path.read_text(encoding="utf-8"))
            context["clos"] = [c.get("text", "") for c in cfg.get("clos", [])]

            # Find module objectives from slug (e.g., "m3-overview" → module 3)
            import re as _re
            m = _re.match(r'^m(\d+)', slug)
            if m:
                mod_num = int(m.group(1))
                context["module_number"] = mod_num
                for mod in cfg.get("modules", []):
                    if mod.get("number") == mod_num:
                        context["objectives"] = [
                            o.get("text", "") for o in mod.get("objectives", [])
                        ]
                        break
        except (json.JSONDecodeError, KeyError, OSError) as e:
            _log.debug(f"Could not load course-config.json for preflight: {e}")

    issues = check_page(html_content, context=context)
    summary = summarize_issues(issues)

    # Write sidecar JSON
    issues_path = get_staging_dir() / f"{slug}.issues.json"
    issues_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Log summary
    if summary["total"] > 0:
        _log.info(f"Preflight: {slug} — {summary['errors']} error(s), "
                  f"{summary['warnings']} warning(s), {summary['info']} info")
    else:
        _log.info(f"Preflight: {slug} — all checks passed")


def list_staged():
    """List all staged page slugs.

    Returns:
        List of slug strings.
    """
    if not get_staging_dir().exists():
        return []
    slugs = []
    for f in sorted(get_staging_dir().glob("*.html")):
        if not f.name.startswith(".") and not f.name.startswith("_"):  # Skip hidden files and generated files like _unified_preview.html
            slugs.append(f.stem)
    return slugs


def get_staged(slug, raw=False):
    """Read the content of a staged file.

    Args:
        slug: Page slug
        raw: If True, return only the raw content (strip shell wrapper)

    Returns:
        HTML content string, or None if not found.
    """
    staged_path = get_staging_dir() / f"{slug}.html"
    if not staged_path.exists():
        return None
    content = staged_path.read_text(encoding="utf-8")
    if raw:
        return _extract_raw(content)
    return content


def update_staged(slug, html_content):
    """Update an existing staged file with new content.

    Args:
        slug: Page slug
        html_content: New raw HTML content

    Returns:
        Path to the updated file, or None if not found.
    """
    staged_path = get_staging_dir() / f"{slug}.html"
    if not staged_path.exists():
        return None
    full_html = _wrap_content(html_content)
    staged_path.write_text(full_html, encoding="utf-8")
    return str(staged_path)


def clear_staged(slug=None):
    """Remove staged files.

    Args:
        slug: If provided, remove only this page. Otherwise, remove all.

    Returns:
        Number of files removed.
    """
    if not get_staging_dir().exists():
        return 0
    if slug:
        staged_path = get_staging_dir() / f"{slug}.html"
        issues_path = get_staging_dir() / f"{slug}.issues.json"
        if staged_path.exists():
            staged_path.unlink()
            if issues_path.exists():
                issues_path.unlink()
            return 1
        return 0
    else:
        count = 0
        for f in get_staging_dir().glob("*.html"):
            if not f.name.startswith(".") and not f.name.startswith("_"):
                f.unlink()
                count += 1
        # Clean up all issues.json files too
        for f in get_staging_dir().glob("*.issues.json"):
            f.unlink()
        return count


def main():
    parser = argparse.ArgumentParser(description="Canvas page staging manager")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--stage", action="store_true", help="Stage a page")
    group.add_argument("--list", action="store_true", help="List staged pages")
    group.add_argument("--get", action="store_true", help="Get staged page (full HTML with shell)")
    group.add_argument("--get-raw", action="store_true", help="Get staged page (raw content only)")
    group.add_argument("--update", action="store_true", help="Update staged content")
    group.add_argument("--clear", action="store_true", help="Clear staged pages")

    parser.add_argument("--slug", help="Page slug")
    parser.add_argument("--html-file", help="Path to HTML content file")
    parser.add_argument("--html-stdin", action="store_true", help="Read HTML from stdin")
    parser.add_argument("--no-validate", action="store_true",
                        help="Skip preflight quality checks when staging")

    args = parser.parse_args()
    _track("skill_invoked", context={"skill": "staging"})

    if args.stage:
        if not args.slug:
            parser.error("--stage requires --slug")
        if args.html_stdin:
            html = sys.stdin.read()
        elif args.html_file:
            try:
                html = open(args.html_file, "r", encoding="utf-8").read()
            except FileNotFoundError:
                print(json.dumps({"ok": False, "error": f"File not found: {args.html_file}"}))
                sys.exit(1)
        else:
            parser.error("--stage requires --html-file or --html-stdin")
        path = stage_page(args.slug, html, validate=not args.no_validate)
        # Include preflight results in output if available
        issues_path = get_staging_dir() / f"{args.slug}.issues.json"
        result = {"ok": True, "path": path, "slug": args.slug}
        if issues_path.exists():
            try:
                result["preflight"] = json.loads(issues_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        print(json.dumps(result))

    elif args.list:
        slugs = list_staged()
        print(json.dumps({"ok": True, "count": len(slugs), "staged": slugs}))

    elif args.get or args.get_raw:
        if not args.slug:
            parser.error("--get/--get-raw requires --slug")
        content = get_staged(args.slug, raw=args.get_raw)
        if content is None:
            print(json.dumps({"ok": False, "error": f"No staged page: {args.slug}"}))
            sys.exit(1)
        print(content)

    elif args.update:
        if not args.slug:
            parser.error("--update requires --slug")
        if args.html_stdin:
            html = sys.stdin.read()
        elif args.html_file:
            try:
                html = open(args.html_file, "r", encoding="utf-8").read()
            except FileNotFoundError:
                print(json.dumps({"ok": False, "error": f"File not found: {args.html_file}"}))
                sys.exit(1)
        else:
            parser.error("--update requires --html-file or --html-stdin")
        path = update_staged(args.slug, html)
        if path is None:
            print(json.dumps({"ok": False, "error": f"No staged page to update: {args.slug}"}))
            sys.exit(1)
        print(json.dumps({"ok": True, "path": path, "slug": args.slug}))

    elif args.clear:
        count = clear_staged(args.slug)
        print(json.dumps({"ok": True, "cleared": count, "slug": args.slug or "all"}))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        _log.exception("Unexpected error")
        print(f"\nSomething went wrong: {e}")
        print("Check the log at ~/.idw/logs/ for details.")
        sys.exit(1)
