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


def _get_supabase_config():
    try:
        from dotenv import load_dotenv
        load_dotenv(PLUGIN_ROOT / ".env")
        load_dotenv(PLUGIN_ROOT / ".env.local", override=True)
    except ImportError:
        pass
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    return (url, key) if url and key else (None, None)


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
    """Register a new tester."""
    import requests

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

    _log_audit("register_tester", caller_id, {"new_tester_id": tester_id, "name": name, "email": email, "role": role})

    return {"ok": True, "tester_id": tester_id, "name": name, "email": email, "role": role}


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


def main():
    parser = argparse.ArgumentParser(description="Audited admin operations")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--register", action="store_true")
    group.add_argument("--deactivate", action="store_true")
    group.add_argument("--change-role", action="store_true")
    group.add_argument("--list-testers", action="store_true")

    parser.add_argument("--name", help="Tester name (for --register)")
    parser.add_argument("--email", help="Tester email (for --register)")
    parser.add_argument("--role", help="Role (for --register)")
    parser.add_argument("--tester-id", help="Tester UUID (for --deactivate, --change-role)")
    parser.add_argument("--new-role", help="New role (for --change-role)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.register:
        if not all([args.name, args.email, args.role]):
            print(json.dumps({"ok": False, "error": "Provide --name, --email, --role"}))
            sys.exit(1)
        result = register_tester(args.name, args.email, args.role, args.dry_run)
        if result["ok"]:
            tid = result.get("tester_id", "DRY RUN")
            print(f"✓ Registered {args.name} as {args.role} (ID: {tid})")
            if not args.dry_run:
                print(f"  They need: IDW_TESTER_ID={tid} in their .env")
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

    print(json.dumps(result))


if __name__ == "__main__":
    main()
