#!/usr/bin/env python3
"""
ID Workbench Pre-Flight Checklist
One-command verification that everything is ready for use.

Usage:
    python preflight.py          # Human-readable output
    python preflight.py --json   # Machine-readable JSON output
"""

import importlib
import json
import os
import platform
import sys
import tempfile
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
STAGING_DIR = PLUGIN_ROOT / "staging"
BACKUP_DIR = Path.home() / ".idw" / "backups"

REQUIRED_SCRIPTS = [
    "canvas_api", "staging_manager", "backup_manager", "diff_engine",
    "course_navigator", "unified_preview", "deploy_interactives",
    "idw_logger", "idw_metrics", "setup_env", "build_checkpoint",
    "audit_pages", "course_content_cache", "template_manager",
    "audit_report", "generator", "metrics_sync",
]

REQUIRED_PACKAGES = ["requests", "dotenv", "bs4", "yaml"]


def check(name, fn):
    """Run a check function, return (status, message)."""
    try:
        ok, msg = fn()
        return ("pass" if ok else "warn", msg)
    except Exception as e:
        return ("fail", str(e))


def check_env():
    env_path = PLUGIN_ROOT / ".env"
    if not env_path.exists():
        return False, ".env file not found — run /canvas-setup"
    content = env_path.read_text()
    if "your_canvas_api_token_here" in content:
        return False, ".env has placeholder token — update CANVAS_TOKEN"
    token = ""
    domain = ""
    active = ""  # Must be outside loop — was resetting on every line iteration
    for line in content.splitlines():
        if line.startswith("CANVAS_TOKEN="):
            token = line.split("=", 1)[1].strip()
        if line.startswith("CANVAS_DOMAIN="):
            domain = line.split("=", 1)[1].strip()
        if line.startswith("CANVAS_ACTIVE_INSTANCE="):
            active = line.split("=", 1)[1].strip()
    if not token:
        return False, ".env missing CANVAS_TOKEN"
    instance = active or "prod"
    return True, f".env configured ({instance}: {domain})"


def check_token():
    sys.path.insert(0, str(SCRIPTS_DIR))
    from canvas_api import get_config
    import requests
    config = get_config()
    headers = {"Authorization": f"Bearer {config['token']}"}
    resp = requests.get(
        f"https://{config['domain']}/api/v1/users/self",
        headers=headers, timeout=10
    )
    if resp.status_code == 200:
        name = resp.json().get("name", "Unknown")
        return True, f"API token valid (authenticated as: {name})"
    return False, f"API token invalid (HTTP {resp.status_code})"


def check_course():
    sys.path.insert(0, str(SCRIPTS_DIR))
    from canvas_api import get_config
    import requests
    config = get_config()
    headers = {"Authorization": f"Bearer {config['token']}"}
    resp = requests.get(
        f"https://{config['domain']}/api/v1/courses/{config['course_id']}",
        headers=headers, timeout=10
    )
    if resp.status_code == 200:
        name = resp.json().get("name", "Unknown")
        return True, f'Course accessible: "{name}" ({config["course_id"]})'
    return False, f"Course {config['course_id']} not accessible (HTTP {resp.status_code})"


def check_python():
    v = sys.version_info
    version_str = f"{v.major}.{v.minor}.{v.micro}"
    if v >= (3, 10):
        return True, f"Python {version_str}"
    return False, f"Python {version_str} — need 3.10+"


def check_packages():
    missing = []
    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        return False, f"Missing packages: {', '.join(missing)}"
    return True, f"Dependencies installed ({len(REQUIRED_PACKAGES)} packages)"


def check_scripts():
    sys.path.insert(0, str(SCRIPTS_DIR))
    failed = []
    for script in REQUIRED_SCRIPTS:
        try:
            importlib.import_module(script)
        except Exception as e:
            failed.append(f"{script} ({type(e).__name__})")
    if failed:
        return False, f"Import errors: {', '.join(failed)}"
    return True, f"All {len(REQUIRED_SCRIPTS)} scripts importable"


def check_staging_writable():
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    test_file = STAGING_DIR / "_preflight_test.tmp"
    try:
        test_file.write_text("test")
        test_file.unlink()
        return True, "Staging directory writable"
    except Exception as e:
        return False, f"Staging not writable: {e}"


def check_backup_writable():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    test_file = BACKUP_DIR / "_preflight_test.tmp"
    try:
        test_file.write_text("test")
        test_file.unlink()
        return True, "Backup directory writable"
    except Exception as e:
        return False, f"Backup not writable: {e}"


def check_safety_mode():
    """Report read-only status and active instance."""
    read_only = os.environ.get("CANVAS_READ_ONLY", "").lower() in ("true", "1", "yes")
    instance = os.environ.get("CANVAS_ACTIVE_INSTANCE", "prod")
    parts = []
    if read_only:
        parts.append("READ-ONLY mode active (writes blocked)")
    else:
        parts.append("Writes enabled")
    parts.append(f"instance={instance}")
    if instance == "prod" and not read_only:
        return True, f"Safety: {', '.join(parts)} — production writes allowed"
    return True, f"Safety: {', '.join(parts)}"


def check_course_config():
    cfg_path = PLUGIN_ROOT / "course-config.json"
    if not cfg_path.exists():
        return False, "course-config.json not found (optional — created during build)"
    try:
        data = json.loads(cfg_path.read_text())
        title = data.get("course", {}).get("title", "untitled")
        return True, f'course-config.json loaded ("{title}")'
    except json.JSONDecodeError:
        return False, "course-config.json exists but has invalid JSON"


def check_metrics_sync():
    """Check if Supabase metrics sync is configured (optional)."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        from metrics_sync import is_configured, get_status
        if not is_configured():
            return True, "Metrics sync: not configured (local only — optional)"
        status = get_status()
        if status.get("connected"):
            parts = ["Metrics sync: connected to Supabase"]
            if status.get("has_service_key"):
                parts.append("+ report uploads enabled")
            return True, " ".join(parts)
        else:
            return True, "Metrics sync: configured but cannot reach Supabase (will retry)"
    except Exception as e:
        return True, f"Metrics sync: check skipped ({e})"


def main():
    use_json = "--json" in sys.argv

    checks = [
        (".env configuration", check_env),
        ("Canvas API token", check_token),
        ("Course access", check_course),
        ("Python version", check_python),
        ("Python packages", check_packages),
        ("Script imports", check_scripts),
        ("Staging directory", check_staging_writable),
        ("Backup directory", check_backup_writable),
        ("Safety mode", check_safety_mode),
        ("Course config", check_course_config),
        ("Metrics sync", check_metrics_sync),
    ]

    results = []
    for name, fn in checks:
        status, msg = check(name, fn)
        results.append({"name": name, "status": status, "message": msg})

    if use_json:
        counts = {"pass": 0, "warn": 0, "fail": 0}
        for r in results:
            counts[r["status"]] += 1
        ready = counts["fail"] == 0
        print(json.dumps({
            "ready": ready,
            "results": results,
            "summary": counts,
        }, indent=2))
    else:
        icons = {"pass": "\033[32m  \u2713\033[0m", "warn": "\033[33m  \u26a0\033[0m", "fail": "\033[31m  \u2717\033[0m"}
        print()
        print("ID Workbench Pre-Flight Check")
        print("\u2550" * 40)
        passed = warned = failed = 0
        for r in results:
            icon = icons[r["status"]]
            print(f"{icon} {r['message']}")
            if r["status"] == "pass":
                passed += 1
            elif r["status"] == "warn":
                warned += 1
            else:
                failed += 1
        print()
        if failed == 0:
            label = "\033[32mREADY\033[0m"
        else:
            label = "\033[31mNOT READY\033[0m"
        print(f"Result: {passed} passed, {warned} warning(s), {failed} failed \u2014 {label}")
        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"\nPre-flight check failed: {e}")
        sys.exit(1)
