#!/usr/bin/env python3
"""Audited admin operations — enforces role check and logs all tester changes.

Usage:
    python3 scripts/admin_actions.py --register --name "Jane Doe" --email "jane@asu.edu" --role id_assistant
    python3 scripts/admin_actions.py --deactivate --tester-id <uuid>
    python3 scripts/admin_actions.py --change-role --tester-id <uuid> --new-role id
    python3 scripts/admin_actions.py --list-testers
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

try:
    from idw_logger import get_logger
    _log = get_logger("admin_actions")
except ImportError:
    import logging
    _log = logging.getLogger("admin_actions")

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
VALID_ROLES = ("id", "id_assistant", "admin")
AUDIT_LOG = PLUGIN_ROOT / "logs" / "admin_audit.jsonl"


import supabase_client


def _get_supabase_config():
    """Thin wrapper — delegates to supabase_client but keeps (url, key) tuple
    signature for the Auth Admin calls in this file that need raw credentials."""
    return supabase_client.get_config_safe()


def _verify_admin():
    """Verify the caller is an admin. Returns (tester_id, tester_name) or exits."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts/role_gate.py", "--check", "admin"],
        capture_output=True, text=True, cwd=str(PLUGIN_ROOT),
    )
    if result.returncode != 0:
        try:
            data = json.loads(result.stdout)
            print(json.dumps({"ok": False, "error": data.get("error", "Admin role required")}))
        except json.JSONDecodeError:
            print(json.dumps({"ok": False, "error": "Admin role required"}))
        sys.exit(1)

    tester_id = os.getenv("IDW_TESTER_ID", "")
    return tester_id


def _log_audit(action, caller_id, details):
    """Append to admin audit log."""
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "caller_id": caller_id,
        **details,
    }
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    _log.info("Admin audit: %s by %s", action, caller_id)


def register_tester(name, email, role, dry_run=False):
    """Register a new tester. Email is required — it's used for QA portal login."""
    import requests

    if not name or not name.strip():
        return {"ok": False, "error": "Name is required"}
    if not email or not email.strip():
        return {"ok": False, "error": "Email is required — it's used for QA portal login"}
    if role not in VALID_ROLES:
        return {"ok": False, "error": f"Invalid role '{role}'. Must be one of: {', '.join(VALID_ROLES)}"}

    caller_id = _verify_admin()
    url, key = _get_supabase_config()
    if not url:
        return {"ok": False, "error": "Supabase not configured"}

    if dry_run:
        return {"ok": True, "dry_run": True, "name": name, "email": email, "role": role}

    resp = requests.post(
        f"{url}/rest/v1/testers",
        headers={
            "apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": "return=representation",
        },
        json={"name": name, "email": email, "role": role, "is_active": True},
        timeout=15,
    )

    if resp.status_code not in (200, 201):
        return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

    data = resp.json()
    tester_id = data[0]["id"] if isinstance(data, list) else data.get("id")

    # Provision Supabase Auth — invite user by email (same as Vercel route)
    invite_status = "failed"
    invite_error = None
    trimmed_email = email.strip().lower()

    try:
        # Check if auth user already exists
        auth_list_resp = requests.get(
            f"{url}/auth/v1/admin/users",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=15,
        )
        existing_auth = False
        if auth_list_resp.status_code == 200:
            users = auth_list_resp.json().get("users", [])
            existing_auth = any(u.get("email", "").lower() == trimmed_email for u in users)

        if existing_auth:
            invite_status = "existing"
        else:
            invite_resp = requests.post(
                f"{url}/auth/v1/invite",
                headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"email": trimmed_email},
                timeout=15,
            )
            if invite_resp.status_code in (200, 201):
                invite_status = "sent"
            else:
                invite_error = f"HTTP {invite_resp.status_code}: {invite_resp.text[:200]}"
                invite_status = "failed"
    except Exception as e:
        invite_error = str(e)
        invite_status = "failed"

    # If invite failed, rollback the tester row — don't leave half-provisioned accounts
    if invite_status == "failed":
        requests.delete(
            f"{url}/rest/v1/testers?id=eq.{tester_id}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=15,
        )
        return {"ok": False, "error": f"Tester row created but invite failed — rolled back. {invite_error or ''}".strip()}

    _log_audit("register_tester", caller_id, {"new_tester_id": tester_id, "name": name, "email": email, "role": role, "invite_status": invite_status})

    return {"ok": True, "tester_id": tester_id, "name": name, "email": email, "role": role, "invite_status": invite_status}


def deactivate_tester(tester_id, dry_run=False):
    """Deactivate a tester."""
    import requests

    caller_id = _verify_admin()

    if caller_id == tester_id:
        return {"ok": False, "error": "Cannot deactivate yourself"}

    url, key = _get_supabase_config()
    if not url:
        return {"ok": False, "error": "Supabase not configured"}

    if dry_run:
        return {"ok": True, "dry_run": True, "tester_id": tester_id}

    resp = requests.patch(
        f"{url}/rest/v1/testers?id=eq.{tester_id}",
        headers={
            "apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": "return=representation",
        },
        json={"is_active": False},
        timeout=15,
    )

    if resp.status_code not in (200, 204):
        return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

    _log_audit("deactivate_tester", caller_id, {"tester_id": tester_id})
    return {"ok": True, "tester_id": tester_id, "action": "deactivated"}


def change_role(tester_id, new_role, dry_run=False):
    """Change a tester's role."""
    import requests

    if new_role not in VALID_ROLES:
        return {"ok": False, "error": f"Invalid role '{new_role}'. Must be one of: {', '.join(VALID_ROLES)}"}

    caller_id = _verify_admin()
    url, key = _get_supabase_config()
    if not url:
        return {"ok": False, "error": "Supabase not configured"}

    # Get current role
    from role_gate import _supabase_get
    testers = _supabase_get(url, key, "testers", {"id": f"eq.{tester_id}", "select": "id,name,role"})
    if not testers:
        return {"ok": False, "error": f"Tester {tester_id} not found"}

    old_role = testers[0].get("role")
    name = testers[0].get("name")

    if old_role == new_role:
        return {"ok": False, "error": f"{name} already has role '{new_role}'"}

    if dry_run:
        return {"ok": True, "dry_run": True, "name": name, "old_role": old_role, "new_role": new_role}

    resp = requests.patch(
        f"{url}/rest/v1/testers?id=eq.{tester_id}",
        headers={
            "apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": "return=representation",
        },
        json={"role": new_role},
        timeout=15,
    )

    if resp.status_code not in (200, 204):
        return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

    _log_audit("change_role", caller_id, {
        "tester_id": tester_id, "name": name, "old_role": old_role, "new_role": new_role,
    })
    return {"ok": True, "name": name, "old_role": old_role, "new_role": new_role}


def list_testers():
    """List all testers."""
    url, key = _get_supabase_config()
    if not url:
        return {"ok": False, "error": "Supabase not configured"}

    _verify_admin()
    from role_gate import _supabase_get
    testers = _supabase_get(url, key, "testers", {"order": "role.asc,name.asc"})
    return {"ok": True, "testers": testers or []}


def list_unassigned_sessions():
    """List sessions that need an ID Assistant assigned."""
    from role_gate import _supabase_get

    _verify_admin()
    url, key = _get_supabase_config()
    if not url:
        return {"ok": False, "error": "Supabase not configured"}

    sessions = _supabase_get(url, key, "audit_sessions", {
        "assigned_to": "is.null",
        "status": "in.(in_progress,pending_qa_review)",
        "order": "run_date.desc",
        "select": "id,course_name,course_code,audit_purpose,audit_round,overall_score,run_date,status",
    })
    return {"ok": True, "sessions": sessions or []}


def assign_session(session_id, tester_id, dry_run=False):
    """Assign an ID Assistant to a review session."""
    import requests
    from role_gate import _supabase_get

    caller_id = _verify_admin()
    url, key = _get_supabase_config()
    if not url:
        return {"ok": False, "error": "Supabase not configured"}

    # Verify session exists
    sessions = _supabase_get(url, key, "audit_sessions", {
        "id": f"eq.{session_id}", "select": "id,course_name,status,assigned_to",
    })
    if not sessions:
        return {"ok": False, "error": f"Session {session_id} not found"}
    session = sessions[0]

    # Verify target is an active id_assistant
    if tester_id:
        testers = _supabase_get(url, key, "testers", {
            "id": f"eq.{tester_id}", "select": "id,name,role,is_active",
        })
        if not testers:
            return {"ok": False, "error": f"Tester {tester_id} not found"}
        tester = testers[0]
        if tester.get("role") != "id_assistant":
            return {"ok": False, "error": f"{tester['name']} is not an ID Assistant (role: {tester['role']})"}
        if not tester.get("is_active"):
            return {"ok": False, "error": f"{tester['name']} is deactivated"}
        tester_name = tester["name"]
    else:
        tester_name = None

    if dry_run:
        return {"ok": True, "dry_run": True, "session_id": session_id,
                "course": session.get("course_name"), "assigned_to": tester_name}

    resp = requests.patch(
        f"{url}/rest/v1/audit_sessions?id=eq.{session_id}",
        headers={
            "apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": "return=representation",
        },
        json={"assigned_to": tester_id or None},
        timeout=15,
    )

    if resp.status_code not in (200, 204):
        return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

    _log_audit("assign_session", caller_id, {
        "session_id": session_id, "course": session.get("course_name"),
        "assigned_to": tester_id, "assigned_name": tester_name,
    })

    return {"ok": True, "session_id": session_id, "course": session.get("course_name"),
            "assigned_to": tester_name}


def main():
    parser = argparse.ArgumentParser(description="Audited admin operations")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--register", action="store_true")
    group.add_argument("--deactivate", action="store_true")
    group.add_argument("--change-role", action="store_true")
    group.add_argument("--list-testers", action="store_true")
    group.add_argument("--list-unassigned", action="store_true", help="List sessions needing ID Assistant assignment")
    group.add_argument("--assign-session", action="store_true", help="Assign ID Assistant to a review session")

    parser.add_argument("--name", help="Tester name (for --register)")
    parser.add_argument("--email", help="Tester email (for --register)")
    parser.add_argument("--role", help="Role (for --register)")
    parser.add_argument("--tester-id", help="Tester UUID (for --deactivate, --change-role, --assign-session)")
    parser.add_argument("--new-role", help="New role (for --change-role)")
    parser.add_argument("--session-id", help="Session UUID (for --assign-session)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.register:
        if not all([args.name, args.email, args.role]):
            print(json.dumps({"ok": False, "error": "Provide --name, --email, --role"}))
            sys.exit(1)
        result = register_tester(args.name, args.email, args.role, args.dry_run)
        if result["ok"]:
            tid = result.get("tester_id", "DRY RUN")
            role = result.get("role", args.role)
            inv = result.get("invite_status", "")
            print(f"✓ Registered {args.name} as {role} (ID: {tid})")
            if not args.dry_run:
                if inv == "sent":
                    print(f"  ✓ Login invite sent to {args.email}")
                elif inv == "existing":
                    print(f"  ✓ Auth user already exists for {args.email} — can log in immediately")
                if role in ("id", "admin"):
                    print(f"\n  Claude Code setup (add to plugin .env):")
                    print(f"  IDW_TESTER_ID={tid}")
                else:
                    print(f"\n  This user only needs the QA portal — no Claude Code setup required.")
        else:
            print(f"✗ {result['error']}")

    elif args.deactivate:
        if not args.tester_id:
            print(json.dumps({"ok": False, "error": "Provide --tester-id"}))
            sys.exit(1)
        result = deactivate_tester(args.tester_id, args.dry_run)
        if result["ok"]:
            print(f"✓ Deactivated tester {args.tester_id}")
        else:
            print(f"✗ {result['error']}")

    elif args.change_role:
        if not args.tester_id or not args.new_role:
            print(json.dumps({"ok": False, "error": "Provide --tester-id and --new-role"}))
            sys.exit(1)
        result = change_role(args.tester_id, args.new_role, args.dry_run)
        if result["ok"]:
            print(f"✓ Changed {result.get('name', args.tester_id)}: {result.get('old_role')} → {result.get('new_role')}")
        else:
            print(f"✗ {result['error']}")

    elif args.list_testers:
        result = list_testers()
        if result["ok"]:
            for t in result["testers"]:
                active = "✓" if t.get("is_active") else "✗"
                print(f"  {active} {t.get('name', '?')} | {t.get('email', '?')} | {t.get('role', '?')}")
        else:
            print(f"✗ {result['error']}")

    elif args.list_unassigned:
        result = list_unassigned_sessions()
        if result["ok"]:
            sessions = result["sessions"]
            if not sessions:
                print("All sessions are assigned. Nothing to do.")
            else:
                print(f"Unassigned Sessions ({len(sessions)}):")
                for s in sessions:
                    score = f"{s.get('overall_score')}%" if s.get('overall_score') is not None else "—"
                    date = (s.get('run_date') or '')[:10]
                    print(f"  {s.get('course_name', '?')} | {s.get('audit_purpose', '?')} | Round {s.get('audit_round', '?')} | {score} | {date} | {s['id'][:8]}...")
        else:
            print(f"✗ {result['error']}")

    elif args.assign_session:
        if not args.session_id or not args.tester_id:
            print(json.dumps({"ok": False, "error": "Provide --session-id and --tester-id"}))
            sys.exit(1)
        result = assign_session(args.session_id, args.tester_id, args.dry_run)
        if result["ok"]:
            print(f"✓ Assigned {result.get('assigned_to', 'N/A')} to session for {result.get('course', 'N/A')}")
        else:
            print(f"✗ {result['error']}")

    print(json.dumps(result))


if __name__ == "__main__":
    main()
