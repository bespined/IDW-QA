#!/usr/bin/env python3
"""Sync local metrics and audit reports to Supabase for the pilot dashboard.

This module is designed to fail silently — if Supabase is not configured or
unreachable, everything still works locally. No tester is ever blocked.

Usage:
    # Sync metrics (called automatically by idw_metrics.py)
    python metrics_sync.py --metrics

    # Upload an audit report file
    python metrics_sync.py --upload-report path/to/report.html

    # Check sync status
    python metrics_sync.py --status

Environment variables (from .env):
    SUPABASE_URL         - Project URL (e.g., https://abcdefg.supabase.co)
    SUPABASE_ANON_KEY    - Public anon key (for DB inserts)
    SUPABASE_SERVICE_KEY - Service role key (for Storage uploads)
"""

import argparse
import hashlib
import json
import os
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path

# SSL context for macOS Python (certifi handles missing system certs)
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

# Logging
try:
    from idw_logger import get_logger
    _log = get_logger("metrics_sync")
except ImportError:
    import logging
    _log = logging.getLogger("metrics_sync")

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _load_env():
    """Load Supabase config from .env file."""
    env_path = PLUGIN_ROOT / ".env"
    config = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()
    return config


def _get_supabase_config():
    """Get Supabase URL and keys. Returns None if not configured."""
    env = _load_env()
    url = env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")
    anon_key = env.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
    service_key = env.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not url or not anon_key:
        return None

    return {
        "url": url.rstrip("/"),
        "anon_key": anon_key,
        "service_key": service_key,
    }


def _get_tester_id():
    """Generate an anonymized tester ID from the Canvas token."""
    env = _load_env()
    token = env.get("CANVAS_TOKEN", "")
    if not token:
        token = env.get("CANVAS_DEV_TOKEN", "unknown")
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def is_configured():
    """Check if Supabase sync is configured."""
    return _get_supabase_config() is not None


def _resolve_course_code(course_id_or_name):
    """Resolve a course ID or name to a human-readable course code.

    Examples:
        "DEV-2025-LAW524" → "LAW-524"
        "CRJ-201" → "CRJ-201"
        "DEV-CRJ201-DesignStandardsCalibration" → "CRJ-201"
        "224105" → "224105" (numeric IDs pass through)
    """
    import re
    if not course_id_or_name:
        return ""
    s = str(course_id_or_name).strip()

    # Pure numeric course ID — pass through
    if s.isdigit():
        return s

    # Already a clean code like "CRJ-201" or "LAW 524"
    m = re.match(r"^([A-Z]{2,4})[\s-]?(\d{3})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # DEV-prefix patterns: "DEV-2025-LAW524", "DEV-CRJ201-Something"
    # Skip "DEV", skip year-like segments, find the actual course code
    parts = s.split("-")
    for part in parts:
        # Skip DEV, year-like (2025, 2026), and other non-course segments
        if part.upper() in ("DEV", "PROD", "MASTER"):
            continue
        if re.match(r"^\d{4}$", part):  # year like 2025
            continue
        # Match course code pattern: 2-4 letters + 3 digits
        m = re.match(r"^([A-Z]{2,4})(\d{3})", part, re.IGNORECASE)
        if m:
            return f"{m.group(1).upper()}-{m.group(2)}"

    # Fallback: search anywhere in string
    m = re.search(r"([A-Z]{2,4})[\s-]*(\d{3})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    return s


def _calc_active_duration(timestamps, gap_threshold_sec=1800):
    """Calculate active session duration from timestamps.

    Groups timestamps into sessions separated by gaps > gap_threshold_sec (default 30 min).
    Returns sum of active session durations (last - first within each session).
    """
    if not timestamps:
        return 0
    from datetime import datetime as _dt
    parsed = []
    for ts in timestamps:
        try:
            parsed.append(_dt.fromisoformat(ts.replace("Z", "+00:00")))
        except Exception:
            continue
    if not parsed:
        return 0
    parsed.sort()

    total_sec = 0
    session_start = parsed[0]
    prev = parsed[0]
    for t in parsed[1:]:
        gap = (t - prev).total_seconds()
        if gap > gap_threshold_sec:
            # Close current session, start new one
            total_sec += max(0, (prev - session_start).total_seconds())
            session_start = t
        prev = t
    # Close final session
    total_sec += max(0, (prev - session_start).total_seconds())
    # Minimum 60s per session if there were events
    if total_sec == 0 and len(parsed) > 0:
        total_sec = 60
    return int(total_sec)


def _partition_events_by_course(events):
    """Partition events by course, using context fields to determine course.

    Returns dict: { course_key: [events] }
    Events without course context go into a fallback bucket resolved from course-config.json.
    """
    import re
    from collections import defaultdict

    by_course = defaultdict(list)

    # Fallback course from course-config.json
    fallback_course = ""
    config_path = PLUGIN_ROOT / "course-config.json"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            fallback_course = cfg.get("course", {}).get("course_code", "")
            if not fallback_course:
                title = cfg.get("course", {}).get("title", "")
                m = re.match(r"([A-Z]{2,4})\s*(\d{3})", title)
                if m:
                    fallback_course = f"{m.group(1)}-{m.group(2)}"
        except Exception:
            pass

    for ev in events:
        ctx = ev.get("context", {}) or {}
        # Try to find course from context fields
        course_raw = (
            ctx.get("course", "")
            or ctx.get("course_id", "")
            or ctx.get("course_code", "")
            or ""
        )
        course_key = _resolve_course_code(course_raw)
        if not course_key:
            course_key = fallback_course or "unknown"
        by_course[course_key].append(ev)

    return dict(by_course)


def sync_metrics(metrics_data):
    """Sync metrics to Supabase — one row per course.

    Partitions events by course context, calculates active session duration
    (using 30-min gap threshold), and upserts one row per course.

    Args:
        metrics_data: Dict from idw_metrics.get_summary()

    Returns:
        True if all synced, False if any failed.
    """
    config = _get_supabase_config()
    if not config:
        _log.debug("Supabase not configured — skipping metrics sync")
        return False

    try:
        import urllib.request
        import urllib.error

        tester_id = _get_tester_id()
        events = metrics_data.get("events", [])
        env = _load_env()

        # Partition events by course
        by_course = _partition_events_by_course(events)
        all_ok = True

        for course_code, course_events in by_course.items():
            if not course_events:
                continue

            # Calculate per-course totals
            totals = {}
            skill_counts = {}
            script_counts = {}
            error_list = []
            timestamps = []

            for ev in course_events:
                etype = ev.get("type", "")
                ctx = ev.get("context", {}) or {}
                ts = ev.get("timestamp", "")
                if ts:
                    timestamps.append(ts)

                totals[etype] = totals.get(etype, 0) + ev.get("count", 1)

                if etype == "skill_invoked":
                    name = ctx.get("skill", "unknown") if isinstance(ctx, dict) else "unknown"
                    skill_counts[name] = skill_counts.get(name, 0) + ev.get("count", 1)
                elif etype == "api_calls":
                    name = ctx.get("script", "canvas_api") if isinstance(ctx, dict) else "canvas_api"
                    script_counts[name] = script_counts.get(name, 0) + ev.get("count", 1)
                elif etype == "error_occurred":
                    error_list.append({
                        "script": ctx.get("script", "unknown") if isinstance(ctx, dict) else "unknown",
                        "error_type": ctx.get("error_type", "unknown") if isinstance(ctx, dict) else "unknown",
                        "timestamp": ts,
                    })

            # Calculate active session duration (not wall-clock)
            duration_sec = _calc_active_duration(timestamps)

            # Calculate actions (meaningful operations) and hours saved
            MANUAL_MINUTES_PER_ACTION = 20
            actions = (
                totals.get("pages_pushed", 0)
                + totals.get("pages_built", 0)
                + totals.get("audit_run", 0)
                + totals.get("audit_fixes", 0)
                + totals.get("pages_rolled_back", 0)
            )
            hours_saved = round(actions * MANUAL_MINUTES_PER_ACTION / 60, 1)

            row = {
                "tester_id": tester_id,
                "timestamp": max(timestamps) if timestamps else datetime.now(timezone.utc).isoformat(),
                "session_duration_sec": duration_sec,
                "skills_invoked": json.dumps(skill_counts),
                "scripts_run": json.dumps(script_counts),
                "pages_created": totals.get("pages_built", 0),
                "pages_pushed": totals.get("pages_pushed", 0),
                "pages_rolled_back": totals.get("pages_rolled_back", 0),
                "errors": json.dumps(error_list),
                "canvas_instance": env.get("CANVAS_ACTIVE_INSTANCE", "prod"),
                "idw_version": "1.3.0",
                "course_id": course_code,
                "actions": actions,
                "hours_saved": hours_saved,
            }

            # Delete any existing rows for this tester + course to prevent duplication
            # Uses service_key to bypass RLS (anon_key may not have DELETE permission)
            try:
                delete_key = config.get("service_key") or config["anon_key"]
                delete_url = (
                    f"{config['url']}/rest/v1/pilot_metrics"
                    f"?tester_id=eq.{tester_id}&course_id=eq.{course_code}"
                )
                del_req = urllib.request.Request(
                    delete_url,
                    method="DELETE",
                    headers={
                        "apikey": delete_key,
                        "Authorization": f"Bearer {delete_key}",
                    },
                )
                urllib.request.urlopen(del_req, timeout=10, context=_SSL_CTX)
            except Exception:
                pass  # If delete fails, insert will still work

            # Insert the new row
            url = f"{config['url']}/rest/v1/pilot_metrics"
            data = json.dumps(row).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "apikey": config["anon_key"],
                    "Authorization": f"Bearer {config['anon_key']}",
                    "Prefer": "return=minimal",
                },
            )
            with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
                if resp.status in (200, 201):
                    _log.info(f"Metrics synced for {course_code}")
                else:
                    _log.warning(f"Supabase returned {resp.status} for {course_code}")
                    all_ok = False

        return all_ok

    except urllib.error.URLError as e:
        _log.debug(f"Metrics sync failed (network): {e}")
        return False
    except Exception as e:
        _log.debug(f"Metrics sync failed: {e}")
        return False


def upload_report(file_path):
    """Upload an audit report file to Supabase Storage.

    Args:
        file_path: Path to the HTML or XLSX report file.

    Returns:
        Public URL of the uploaded file, or None if failed.
    """
    config = _get_supabase_config()
    if not config or not config.get("service_key"):
        _log.debug("Supabase Storage not configured — skipping report upload")
        return None

    file_path = Path(file_path)
    if not file_path.exists():
        _log.warning(f"Report file not found: {file_path}")
        return None

    try:
        import urllib.request
        import urllib.error

        # Determine storage path: audit-reports/{tester_id}/{folder}/{filename}
        tester_id = _get_tester_id()

        # Extract course folder from the path (e.g., "CRJ-201_Fall-2025")
        # Path structure: reports/{course_folder}/{filename}
        parts = file_path.parts
        try:
            reports_idx = parts.index("reports")
            course_folder = parts[reports_idx + 1]
        except (ValueError, IndexError):
            course_folder = "uncategorized"

        storage_path = f"{tester_id}/{course_folder}/{file_path.name}"

        # Determine content type
        suffix = file_path.suffix.lower()
        content_types = {
            ".html": "text/html",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".txt": "text/plain",
        }
        content_type = content_types.get(suffix, "application/octet-stream")

        # Upload to Supabase Storage bucket "audit-reports"
        url = f"{config['url']}/storage/v1/object/audit-reports/{storage_path}"
        file_data = file_path.read_bytes()

        req = urllib.request.Request(
            url,
            data=file_data,
            method="POST",
            headers={
                "Content-Type": content_type,
                "apikey": config["service_key"],
                "Authorization": f"Bearer {config['service_key']}",
                "x-upsert": "true",  # Overwrite if exists
            },
        )

        with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
            if resp.status in (200, 201):
                public_url = f"{config['url']}/storage/v1/object/public/audit-reports/{storage_path}"
                _log.info(f"Report uploaded: {public_url}")
                return public_url
            else:
                _log.warning(f"Storage upload returned {resp.status}")
                return None

    except urllib.error.URLError as e:
        _log.debug(f"Report upload failed (network): {e}")
        return None
    except Exception as e:
        _log.debug(f"Report upload failed: {e}")
        return None


def sync_audit_score(course_id, score):
    """Sync an audit score to the most recent pilot_metrics row for this course.

    Logic:
      - If the latest row for this tester+course has audit_score_before=NULL,
        set audit_score_before = score (first audit).
      - If it has audit_score_before set but audit_score_after=NULL,
        set audit_score_after = score (post-fix audit).
      - Otherwise, create a new row with audit_score_before = score.

    Returns:
        True if synced, False if skipped/failed.
    """
    config = _get_supabase_config()
    if not config:
        return False

    try:
        import urllib.request
        import urllib.error

        tester_id = _get_tester_id()

        # 1. Query the latest row for this tester + course
        query_url = (
            f"{config['url']}/rest/v1/pilot_metrics"
            f"?tester_id=eq.{tester_id}"
            f"&course_id=eq.{course_id}"
            f"&order=timestamp.desc&limit=1"
            f"&select=id,audit_score_before,audit_score_after"
        )
        req = urllib.request.Request(
            query_url,
            headers={
                "apikey": config["anon_key"],
                "Authorization": f"Bearer {config['anon_key']}",
            },
        )
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
            rows = json.loads(resp.read().decode("utf-8"))

        if rows:
            row = rows[0]
            row_id = row["id"]

            if row.get("audit_score_before") is None:
                # First audit — set audit_score_before
                patch_field = "audit_score_before"
            elif row.get("audit_score_after") is None:
                # Post-fix audit — set audit_score_after
                patch_field = "audit_score_after"
            else:
                # Both already set — create a new row with this as audit_score_before
                patch_field = None

            if patch_field:
                patch_url = f"{config['url']}/rest/v1/pilot_metrics?id=eq.{row_id}"
                patch_data = json.dumps({patch_field: score}).encode("utf-8")
                patch_req = urllib.request.Request(
                    patch_url,
                    data=patch_data,
                    method="PATCH",
                    headers={
                        "Content-Type": "application/json",
                        "apikey": config["anon_key"],
                        "Authorization": f"Bearer {config['anon_key']}",
                        "Prefer": "return=minimal",
                    },
                )
                with urllib.request.urlopen(patch_req, timeout=10, context=_SSL_CTX) as patch_resp:
                    if patch_resp.status in (200, 204):
                        _log.info(f"Audit score synced: {patch_field}={score} for {course_id}")
                        return True
                return False

        # No existing row — create one with audit_score_before
        env = _load_env()
        new_row = {
            "tester_id": tester_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "audit_score_before": score,
            "canvas_instance": env.get("CANVAS_ACTIVE_INSTANCE", "prod"),
            "idw_version": "1.3.0",
            "course_id": course_id,
        }
        post_url = f"{config['url']}/rest/v1/pilot_metrics"
        post_data = json.dumps(new_row).encode("utf-8")
        post_req = urllib.request.Request(
            post_url,
            data=post_data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "apikey": config["anon_key"],
                "Authorization": f"Bearer {config['anon_key']}",
                "Prefer": "return=minimal",
            },
        )
        with urllib.request.urlopen(post_req, timeout=10, context=_SSL_CTX) as post_resp:
            if post_resp.status in (200, 201):
                _log.info(f"Audit score synced (new row): before={score} for {course_id}")
                return True
        return False

    except Exception as e:
        _log.debug(f"Audit score sync failed: {e}")
        return False


def get_status():
    """Check sync configuration and connectivity."""
    config = _get_supabase_config()
    status = {
        "configured": config is not None,
        "url": config["url"] if config else None,
        "has_anon_key": bool(config and config.get("anon_key")),
        "has_service_key": bool(config and config.get("service_key")),
        "tester_id": _get_tester_id() if config else None,
    }

    if config:
        # Test connectivity by querying the actual table
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{config['url']}/rest/v1/pilot_metrics?select=id&limit=1",
                headers={
                    "apikey": config["anon_key"],
                    "Authorization": f"Bearer {config['anon_key']}",
                },
            )
            with urllib.request.urlopen(req, timeout=5, context=_SSL_CTX) as resp:
                status["connected"] = resp.status == 200
        except Exception as e:
            status["connected"] = False
            status["error"] = str(e)
    else:
        status["connected"] = False

    return status


def main():
    parser = argparse.ArgumentParser(description="Sync IDW metrics to Supabase")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--metrics", action="store_true", help="Sync current metrics summary")
    group.add_argument("--upload-report", type=str, help="Upload an audit report file")
    group.add_argument("--status", action="store_true", help="Check sync configuration")
    args = parser.parse_args()

    if args.status:
        status = get_status()
        print(json.dumps(status, indent=2))
        return

    if args.metrics:
        sys.path.insert(0, str(Path(__file__).parent))
        from idw_metrics import get_summary
        summary = get_summary()
        ok = sync_metrics(summary)
        print(json.dumps({"synced": ok}))
        return

    if args.upload_report:
        url = upload_report(args.upload_report)
        print(json.dumps({"uploaded": url is not None, "url": url}))
        return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        _log.exception("Unexpected error in metrics sync")
        print(f"\nMetrics sync error: {e}")
        sys.exit(1)
