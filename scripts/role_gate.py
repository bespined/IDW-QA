#!/usr/bin/env python3
"""Role gating helper — verify user role before executing protected skills.

Checks IDW_TESTER_ID in .env → queries Supabase testers table → returns role info.

Usage:
    python role_gate.py --check admin          # Exits 0 if user is admin, 1 otherwise
    python role_gate.py --check id_assistant   # Exits 0 if user is IDA
    python role_gate.py --check any            # Exits 0 if user exists in testers table
    python role_gate.py --whoami               # Print current user info as JSON
    python role_gate.py --register --name "Jane Doe" --email "jane@asu.edu" --role id_assistant
                                               # Register a new tester (admin only)
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from idw_logger import get_logger
    _log = get_logger("role_gate")
except ImportError:
    import logging
    _log = logging.getLogger("role_gate")

PLUGIN_ROOT = Path(__file__).resolve().parents[1]

# Load .env and .env.local
try:
    from dotenv import load_dotenv
    load_dotenv(PLUGIN_ROOT / ".env")
    load_dotenv(PLUGIN_ROOT / ".env.local")
except ImportError:
    pass


def _get_supabase_config():
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        return None, None
    return url, key


def _supabase_get(url, key, table, params=None):
    """GET from a Supabase table with optional query params."""
    import requests
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    resp = requests.get(
        f"{url}/rest/v1/{table}",
        headers=headers,
        params=params or {},
        timeout=15,
    )
    if resp.status_code == 200:
        return resp.json()
    _log.error("Supabase GET %s failed: %s %s", table, resp.status_code, resp.text[:200])
    return None


def _supabase_post(url, key, table, row):
    """POST a single row to a Supabase table."""
    import requests
    resp = requests.post(
        f"{url}/rest/v1/{table}",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        json=row,
        timeout=15,
    )
    if resp.status_code in (200, 201):
        data = resp.json()
        return data[0] if isinstance(data, list) and data else data
    _log.error("Supabase POST %s failed: %s %s", table, resp.status_code, resp.text[:200])
    return None


def get_current_tester():
    # IDW_TESTER_ID in .env is the local identity anchor — maps this machine to a Supabase testers row
    """Look up the current tester by IDW_TESTER_ID. Returns dict or None."""
    tester_id = os.getenv("IDW_TESTER_ID", "").strip()
    if not tester_id:
        return None

    url, key = _get_supabase_config()
    if not url:
        return None

    rows = _supabase_get(url, key, "testers", {"id": f"eq.{tester_id}", "is_active": "eq.true"})
    if rows and len(rows) > 0:
        return rows[0]
    return None


def check_role(required_role):
    """Check if current tester has the required role.

    Args:
        required_role: 'admin', 'id', 'id_assistant', or 'any'

    Returns:
        (ok: bool, tester: dict|None, message: str)
    """
    tester_id = os.getenv("IDW_TESTER_ID", "").strip()
    if not tester_id:
        return False, None, "IDW_TESTER_ID not set in .env. Add your tester ID to use this skill."

    url, key = _get_supabase_config()
    if not url:
        return False, None, "Supabase credentials not configured. Check .env.local for SUPABASE_URL and SUPABASE_SERVICE_KEY."

    tester = get_current_tester()
    if not tester:
        return False, None, f"Tester ID '{tester_id}' not found or inactive."

    if required_role == "any":
        return True, tester, f"Authenticated as {tester['name']} ({tester['role']})"

    # Admins pass every role check — they need unrestricted access for tester management, RLHF review, and debugging
    if tester["role"] == required_role or tester["role"] == "admin":
        return True, tester, f"Authenticated as {tester['name']} ({tester['role']})"

    return False, tester, f"This skill requires '{required_role}' access. You are '{tester['role']}'."


def register_tester(name, email, role):
    """Register a new tester. Caller must be admin (not enforced here — enforce in skill)."""
    url, key = _get_supabase_config()
    if not url:
        return None, "Supabase credentials not configured."

    row = {"name": name, "role": role}
    if email:
        row["email"] = email

    result = _supabase_post(url, key, "testers", row)
    if result:
        return result, f"Registered {name} as {role} (ID: {result.get('id', '?')})"
    return None, "Failed to register tester — check Supabase logs."


def main():
    parser = argparse.ArgumentParser(description="Role gating for IDW QA skills")
    parser.add_argument("--check", metavar="ROLE", help="Check if current user has this role (admin|id|id_assistant|any)")
    parser.add_argument("--whoami", action="store_true", help="Print current user info")
    parser.add_argument("--register", action="store_true", help="Register a new tester")
    parser.add_argument("--name", help="Tester name (for --register)")
    parser.add_argument("--email", help="Tester email (for --register)")
    parser.add_argument("--role", help="Tester role (for --register): id, id_assistant, admin")
    args = parser.parse_args()

    if args.whoami:
        tester = get_current_tester()
        if tester:
            print(json.dumps(tester, indent=2, default=str))
        else:
            print(json.dumps({"error": "Not authenticated. Set IDW_TESTER_ID in .env."}, indent=2))
            sys.exit(1)

    elif args.check:
        ok, tester, msg = check_role(args.check)
        result = {"authorized": ok, "message": msg}
        if tester:
            result["tester"] = {"id": tester["id"], "name": tester["name"], "role": tester["role"]}
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if ok else 1)

    elif args.register:
        if not args.name or not args.role:
            print(json.dumps({"error": "--name and --role are required for --register"}, indent=2))
            sys.exit(1)
        if args.role not in ("id", "id_assistant", "admin"):
            print(json.dumps({"error": f"Invalid role '{args.role}'. Must be: id, id_assistant, admin"}, indent=2))
            sys.exit(1)
        result, msg = register_tester(args.name, args.email, args.role)
        if result:
            print(json.dumps({"success": True, "message": msg, "tester": result}, indent=2, default=str))
        else:
            print(json.dumps({"success": False, "message": msg}, indent=2))
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
