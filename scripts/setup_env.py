#!/usr/bin/env python3
"""Canvas plugin setup validation helper.

Used by the /canvas-setup skill to test API connectivity,
validate configuration, list courses, and verify course IDs.

Supports --mode prod|dev to switch between Canvas instances.

Usage:
    python setup_env.py --test                         Test prod API connectivity
    python setup_env.py --test --mode dev              Test dev API connectivity
    python setup_env.py --validate                     Check .env completeness
    python setup_env.py --list-courses                 List user's courses (prod)
    python setup_env.py --list-courses --mode dev      List dev courses
    python setup_env.py --verify-course ID             Verify a specific course ID
    python setup_env.py --verify-course ID --mode dev  Verify on dev instance
"""

import argparse
import json
import os
import sys

# Logging
try:
    from idw_logger import get_logger
    _log = get_logger("setup_env")
except ImportError:
    import logging
    _log = logging.getLogger("setup_env")


import requests

# Load .env from plugin root (backward-compatible)
try:
    from dotenv import load_dotenv
    _plugin_root = os.path.join(os.path.dirname(os.path.dirname(__file__)))
    load_dotenv(os.path.join(_plugin_root, '.env'))
    load_dotenv(os.path.join(_plugin_root, '.env.local'), override=True)
except ImportError:
    pass  # Fall back to environment variables


def get_env(mode=None):
    """Load Canvas credentials from environment.

    Args:
        mode: "prod" (default) or "dev". Selects which token/domain pair to use.
    """
    if mode is None:
        mode = os.environ.get("CANVAS_ACTIVE_INSTANCE", "prod")

    if mode == "dev":
        return {
            "token": os.environ.get("CANVAS_DEV_TOKEN"),
            "domain": os.environ.get("CANVAS_DEV_DOMAIN", "asu-dev.instructure.com"),
            "course_id": os.environ.get("CANVAS_DEV_COURSE_ID") or os.environ.get("CANVAS_COURSE_ID"),
            "mode": "dev",
        }
    else:
        return {
            "token": os.environ.get("CANVAS_TOKEN"),
            "domain": os.environ.get("CANVAS_DOMAIN", "canvas.asu.edu"),
            "course_id": os.environ.get("CANVAS_COURSE_ID"),
            "mode": "prod",
        }


def test_connection(mode=None):
    """Test API token by fetching authenticated user info."""
    env = get_env(mode)
    token_var = "CANVAS_DEV_TOKEN" if env["mode"] == "dev" else "CANVAS_TOKEN"
    if not env["token"]:
        print(json.dumps({"ok": False, "error": f"{token_var} not set"}))
        return False

    try:
        resp = requests.get(
            f"https://{env['domain']}/api/v1/users/self",
            headers={"Authorization": f"Bearer {env['token']}"},
            timeout=15,
        )
        if resp.status_code == 200:
            user = resp.json()
            print(json.dumps({
                "ok": True,
                "user_name": user.get("name", "Unknown"),
                "user_id": user.get("id"),
                "domain": env["domain"],
                "mode": env["mode"],
            }))
            return True
        else:
            print(json.dumps({
                "ok": False,
                "error": f"HTTP {resp.status_code}",
                "detail": resp.text[:200],
            }))
            return False
    except requests.exceptions.ConnectionError:
        print(json.dumps({"ok": False, "error": f"Cannot connect to {env['domain']}"}))
        return False
    except requests.exceptions.Timeout:
        print(json.dumps({"ok": False, "error": "Request timed out"}))
        return False


SUPPORTED_CONFIG_VERSIONS = ["1.0", "1.1", "1.2"]


def validate_env(mode=None):
    """Check that .env has all required variables and course-config.json is valid."""
    env = get_env(mode)
    missing = []
    token_var = "CANVAS_DEV_TOKEN" if env["mode"] == "dev" else "CANVAS_TOKEN"
    domain_var = "CANVAS_DEV_DOMAIN" if env["mode"] == "dev" else "CANVAS_DOMAIN"

    if not env["token"]:
        missing.append(token_var)
    if not env["domain"]:
        missing.append(domain_var)
    if not env["course_id"]:
        missing.append("CANVAS_COURSE_ID")

    # Check for course-config.json in current directory
    config_status = "not_found"
    config_version = None
    config_path = os.path.join(os.getcwd(), "course-config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                config_data = json.load(f)
            config_version = config_data.get("config_version", "1.0")
            if config_version in SUPPORTED_CONFIG_VERSIONS:
                config_status = "valid"
            else:
                config_status = "unsupported_version"
        except (json.JSONDecodeError, OSError):
            config_status = "invalid_json"

    if missing:
        print(json.dumps({
            "ok": False,
            "missing": missing,
            "message": f"Missing: {', '.join(missing)}",
            "course_config": config_status,
            "config_version": config_version,
            "mode": env["mode"],
        }))
        return False
    else:
        print(json.dumps({
            "ok": True,
            "message": "All required variables set",
            "domain": env["domain"],
            "course_id": env["course_id"],
            "course_config": config_status,
            "config_version": config_version,
            "mode": env["mode"],
        }))
        return True


def list_courses(mode=None):
    """List user's active courses."""
    env = get_env(mode)
    token_var = "CANVAS_DEV_TOKEN" if env["mode"] == "dev" else "CANVAS_TOKEN"
    if not env["token"]:
        print(json.dumps({"ok": False, "error": f"{token_var} not set"}))
        return False

    try:
        courses = []
        url = f"https://{env['domain']}/api/v1/courses"
        params = {"per_page": 50, "enrollment_state": "active"}
        headers = {"Authorization": f"Bearer {env['token']}"}

        while url:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code != 200:
                print(json.dumps({
                    "ok": False,
                    "error": f"HTTP {resp.status_code}",
                    "detail": resp.text[:200],
                }))
                return False
            courses.extend(resp.json())
            # Parse Link header for next page
            links = resp.headers.get("Link", "")
            url = None
            for part in links.split(","):
                if 'rel="next"' in part:
                    url = part.split("<")[1].split(">")[0]
            params = None  # Only needed for first request

        # Format course list
        course_list = []
        for c in courses:
            if isinstance(c, dict) and c.get("name"):
                course_list.append({
                    "id": c["id"],
                    "name": c["name"],
                    "code": c.get("course_code", ""),
                    "term": c.get("term", {}).get("name", "") if isinstance(c.get("term"), dict) else "",
                })

        print(json.dumps({
            "ok": True,
            "count": len(course_list),
            "courses": course_list,
            "mode": env["mode"],
            "domain": env["domain"],
        }))
        return True
    except requests.exceptions.RequestException as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return False


def verify_course(course_id, mode=None):
    """Verify a course ID exists and user has access."""
    env = get_env(mode)
    token_var = "CANVAS_DEV_TOKEN" if env["mode"] == "dev" else "CANVAS_TOKEN"
    if not env["token"]:
        print(json.dumps({"ok": False, "error": f"{token_var} not set"}))
        return False

    try:
        resp = requests.get(
            f"https://{env['domain']}/api/v1/courses/{course_id}",
            headers={"Authorization": f"Bearer {env['token']}"},
            timeout=15,
        )
        if resp.status_code == 200:
            course = resp.json()
            # Check enrollment role — warn if not Teacher/Designer/TA
            role_ok, role_msg = check_enrollment_role(env, course_id)
            role_warning = None
            if role_ok is False:
                role_warning = role_msg
            print(json.dumps({
                "ok": True,
                "course_id": course["id"],
                "name": course.get("name", "Unknown"),
                "code": course.get("course_code", ""),
                "mode": env["mode"],
                "domain": env["domain"],
                "role_warning": role_warning,
            }))
            return True
        elif resp.status_code == 404:
            print(json.dumps({"ok": False, "error": f"Course {course_id} not found"}))
            return False
        elif resp.status_code == 401:
            print(json.dumps({"ok": False, "error": "Not authorized — check your API token"}))
            return False
        else:
            print(json.dumps({
                "ok": False,
                "error": f"HTTP {resp.status_code}",
                "detail": resp.text[:200],
            }))
            return False
    except requests.exceptions.RequestException as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return False


def check_enrollment_role(env, course_id):
    """Verify user has Teacher, Designer, or TA role in the course.

    Returns:
        (True, None) — sufficient role found
        (False, message) — insufficient role; message explains what was found
        (None, message) — could not verify (API error); non-blocking
    """
    try:
        resp = requests.get(
            f"https://{env['domain']}/api/v1/courses/{course_id}/enrollments",
            headers={"Authorization": f"Bearer {env['token']}"},
            params={"user_id": "self", "per_page": 50},
            timeout=15,
        )
        if resp.status_code != 200:
            return None, f"Could not verify enrollment role (HTTP {resp.status_code})"
        enrollments = resp.json()
        allowed_roles = {"TeacherEnrollment", "DesignerEnrollment", "TaEnrollment"}
        roles = [e.get("type", "") for e in enrollments if isinstance(e, dict)]
        if not roles:
            return None, "No enrollments found for this user in this course"
        if not any(r in allowed_roles for r in roles):
            role_list = ", ".join(roles) or "unknown"
            return False, (
                f"Your role in this course is: {role_list}. "
                "IDW requires Teacher, TA, or Designer access to create or edit content. "
                "Audit and read-only operations will still work."
            )
        return True, None
    except Exception as e:
        return None, f"Enrollment check failed: {e}"


def main():
    parser = argparse.ArgumentParser(description="Canvas plugin setup helper")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--test", action="store_true", help="Test API connectivity")
    group.add_argument("--validate", action="store_true", help="Validate .env completeness")
    group.add_argument("--list-courses", action="store_true", help="List user's courses")
    group.add_argument("--verify-course", metavar="ID", help="Verify a course ID")

    parser.add_argument("--mode", choices=["prod", "dev"],
                        help="Canvas instance: prod (default) or dev")

    args = parser.parse_args()

    if args.test:
        success = test_connection(args.mode)
    elif args.validate:
        success = validate_env(args.mode)
    elif args.list_courses:
        success = list_courses(args.mode)
    elif args.verify_course:
        success = verify_course(args.verify_course, args.mode)
    else:
        parser.print_help()
        success = False

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
