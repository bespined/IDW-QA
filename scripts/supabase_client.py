"""Centralised Supabase helpers for IDW-QA scripts.

Every script that talks to Supabase should import from here instead of
rolling its own config-loader / REST wrapper.  Auth-admin operations
(invite, listUsers) stay in admin_actions.py — this module only covers
PostgREST data access and Storage uploads.
"""

from __future__ import annotations

import os
from pathlib import Path

import requests

try:
    from idw_logger import get_logger
    _log = get_logger("supabase_client")
except ImportError:
    import logging
    _log = logging.getLogger("supabase_client")

# ---------------------------------------------------------------------------
# .env loading — idempotent, called once on first config access
# ---------------------------------------------------------------------------
_env_loaded = False


def _ensure_env() -> None:
    global _env_loaded
    if _env_loaded:
        return
    try:
        from dotenv import load_dotenv
        plugin_root = Path(__file__).resolve().parent.parent
        load_dotenv(plugin_root / ".env.local")
        load_dotenv(plugin_root / ".env")
    except ImportError:
        pass
    _env_loaded = True


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def get_config() -> tuple[str, str]:
    """Return (supabase_url, service_key).  Raises ValueError if not set."""
    _ensure_env()
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env.local"
        )
    return url, key


def get_config_safe() -> tuple[str | None, str | None]:
    """Return (url, key) or (None, None) if not configured."""
    try:
        return get_config()
    except ValueError:
        return None, None


def is_configured() -> bool:
    url, key = get_config_safe()
    return bool(url and key)


# ---------------------------------------------------------------------------
# Shared headers
# ---------------------------------------------------------------------------

def _headers(key: str, *, prefer: str | None = None) -> dict[str, str]:
    h: dict[str, str] = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


# ---------------------------------------------------------------------------
# PostgREST helpers
# ---------------------------------------------------------------------------

def get(table: str, *, params: dict | None = None,
        timeout: int = 15) -> list[dict] | None:
    """GET rows from a Supabase table.  Returns list or None on error."""
    url, key = get_config()
    resp = requests.get(
        f"{url}/rest/v1/{table}",
        headers=_headers(key),
        params=params or {},
        timeout=timeout,
    )
    if resp.status_code == 200:
        return resp.json()
    _log.error("Supabase GET %s failed: %s %s", table,
               resp.status_code, resp.text[:200])
    return None


def post(table: str, rows: dict | list[dict], *,
         timeout: int = 30) -> list[dict] | dict | None:
    """POST row(s) to a Supabase table.  Returns inserted data or None."""
    url, key = get_config()
    resp = requests.post(
        f"{url}/rest/v1/{table}",
        headers=_headers(key, prefer="return=representation"),
        json=rows,
        timeout=timeout,
    )
    if resp.status_code in (200, 201):
        data = resp.json()
        # Single-row insert returns a one-element list — unwrap for callers
        # that passed a dict.
        if isinstance(rows, dict) and isinstance(data, list) and len(data) == 1:
            return data[0]
        return data
    _log.error("Supabase POST %s failed: %s %s", table,
               resp.status_code, resp.text[:200])
    return None


def patch(table: str, row_id: str, updates: dict, *,
          timeout: int = 15) -> bool:
    """PATCH a single row by id.  Returns True on success."""
    url, key = get_config()
    resp = requests.patch(
        f"{url}/rest/v1/{table}?id=eq.{row_id}",
        headers=_headers(key),
        json=updates,
        timeout=timeout,
    )
    if resp.status_code in (200, 204):
        return True
    _log.error("Supabase PATCH %s/%s failed: %s %s", table, row_id,
               resp.status_code, resp.text[:200])
    return False


# ---------------------------------------------------------------------------
# Storage helper
# ---------------------------------------------------------------------------

def upload_file(bucket: str, path_in_bucket: str, local_path: str, *,
                content_type: str | None = None,
                timeout: int = 60) -> str | None:
    """Upload a file to Supabase Storage.  Returns public URL or None."""
    url, key = get_config()
    if content_type is None:
        content_type = (
            "text/html" if local_path.endswith(".html")
            else "application/octet-stream"
        )
    with open(local_path, "rb") as f:
        resp = requests.post(
            f"{url}/storage/v1/object/{bucket}/{path_in_bucket}",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": content_type,
                "x-upsert": "true",
            },
            data=f,
            timeout=timeout,
        )
    if resp.status_code in (200, 201):
        return f"{url}/storage/v1/object/public/{bucket}/{path_in_bucket}"
    _log.error("Supabase upload %s failed: %s %s", path_in_bucket,
               resp.status_code, resp.text[:200])
    return None
