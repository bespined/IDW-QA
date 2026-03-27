#!/usr/bin/env python3
"""Shared Canvas LMS API utilities.

Supports two Canvas instances:
    Production: CANVAS_TOKEN + CANVAS_DOMAIN (default: canvas.asu.edu)
    Dev:        CANVAS_DEV_TOKEN + CANVAS_DEV_DOMAIN (default: asu-dev.instructure.com)

Course ID is passed per-operation, not hardcoded.

Generate a token at: Canvas → Account → Settings → New Access Token
"""

import os
import sys
import time
import requests

# Load .env from plugin root (backward-compatible)
try:
    from dotenv import load_dotenv
    _plugin_root = os.path.join(os.path.dirname(os.path.dirname(__file__)))
    load_dotenv(os.path.join(_plugin_root, '.env'))
    load_dotenv(os.path.join(_plugin_root, '.env.local'), override=True)
except ImportError:
    pass  # Fall back to environment variables

# Logging
try:
    from idw_logger import get_logger
    _log = get_logger("canvas_api")
    from idw_metrics import track as _track
except ImportError:
    import logging
    _log = logging.getLogger("canvas_api")
    def _track(*a, **k): pass


def get_active_instance():
    """Read the active Canvas instance from .env (default: 'prod')."""
    return os.environ.get("CANVAS_ACTIVE_INSTANCE", "prod")


def is_read_only():
    """Check if the plugin is in read-only mode (no writes allowed)."""
    return os.environ.get("CANVAS_READ_ONLY", "").lower() in ("true", "1", "yes")


def _check_write_allowed(config, operation="write"):
    """Guard that blocks all write operations when CANVAS_READ_ONLY=true,
    and logs a prominent warning when writing to production.

    Call this at the top of every function that modifies Canvas data.
    Raises RuntimeError if read-only mode is active.
    """
    if is_read_only():
        msg = f"BLOCKED: {operation} rejected — CANVAS_READ_ONLY is enabled. Disable it in .env to allow writes."
        _log.error(msg)
        raise RuntimeError(msg)
    if config.get("instance") == "prod":
        _log.warning("⚠ PRODUCTION WRITE: %s on %s (course %s)",
                      operation, config.get("domain"), config.get("course_id"))
        # Hard gate: require explicit opt-in for production writes
        if os.environ.get("CANVAS_PROD_WRITES_CONFIRMED") != "true":
            msg = (f"BLOCKED: Production write ({operation}) requires confirmation. "
                   f"Target: {config.get('domain')} course {config.get('course_id')}. "
                   f"Set CANVAS_PROD_WRITES_CONFIRMED=true in .env to allow production writes, "
                   f"or switch to dev instance.")
            _log.error(msg)
            raise RuntimeError(msg)


def switch_instance(target):
    """Switch the active Canvas instance by updating .env.

    Args:
        target: "prod" or "dev"
    """
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if not os.path.exists(env_path):
        _log.error(".env not found at %s", env_path)
        sys.exit(1)

    lines = open(env_path, 'r').readlines()
    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith("CANVAS_ACTIVE_INSTANCE="):
            new_lines.append(f"CANVAS_ACTIVE_INSTANCE={target}\n")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"\nCANVAS_ACTIVE_INSTANCE={target}\n")

    with open(env_path, 'w') as f:
        f.writelines(new_lines)

    # Update in-memory so subsequent calls in the same process pick it up
    os.environ["CANVAS_ACTIVE_INSTANCE"] = target


def get_config(instance=None, course_id=None):
    """Load Canvas API configuration.

    Args:
        instance: "prod" or "dev". If None, reads active instance from .env.
        course_id: Canvas course ID (optional, can be set later per-operation)

    Returns:
        Config dict with token, domain, base_url, headers, and optional course_url.
    """
    if instance is None:
        instance = get_active_instance()

    if instance == "dev":
        token = os.environ.get("CANVAS_DEV_TOKEN")
        domain = os.environ.get("CANVAS_DEV_DOMAIN", "asu-dev.instructure.com")
        if not token:
            _log.error("CANVAS_DEV_TOKEN environment variable not set")
            sys.exit(1)
        # Fall back to dev-specific course ID
        if course_id is None:
            course_id = os.environ.get("CANVAS_DEV_COURSE_ID") or os.environ.get("CANVAS_COURSE_ID")
    else:
        token = os.environ.get("CANVAS_TOKEN")
        domain = os.environ.get("CANVAS_DOMAIN", "canvas.asu.edu")
        if not token:
            _log.error("CANVAS_TOKEN environment variable not set")
            _log.error("Generate a token at: Canvas → Account → Settings → New Access Token")
            sys.exit(1)
        if course_id is None:
            course_id = os.environ.get("CANVAS_COURSE_ID")

    return {
        "token": token,
        "domain": domain,
        "instance": instance,
        "course_id": course_id,
        "base_url": f"https://{domain}/api/v1",
        "course_url": f"https://{domain}/api/v1/courses/{course_id}" if course_id else None,
        "headers": {"Authorization": f"Bearer {token}"},
    }


def require_course_id(config):
    """Exit with error if course_id is not set."""
    if not config["course_id"]:
        _log.error("course_id not set. Pass course_id to get_config() or set CANVAS_COURSE_ID.")
        sys.exit(1)


# ============================================================
# RATE LIMITING & RETRY
# ============================================================
MAX_RETRIES = 3
BASE_DELAY = 1.0  # seconds
INTER_REQUEST_DELAY = 0.25  # seconds between API calls

_last_request_time = 0.0

def _pace():
    """Enforce minimum delay between Canvas API requests."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < INTER_REQUEST_DELAY:
        time.sleep(INTER_REQUEST_DELAY - elapsed)
    _last_request_time = time.time()

FRIENDLY_ERRORS = {
    401: "Authentication failed — check your CANVAS_TOKEN in .env",
    403: "Permission denied — your API token lacks access to this resource",
    404: "Not found — the course, page, or resource doesn't exist (check the ID/slug)",
    409: "Conflict — this resource was modified by someone else; try again",
    422: "Validation error — Canvas rejected the data (check required fields)",
    429: "Rate limited — too many requests; wait a moment and retry",
    500: "Canvas server error — try again in a few minutes",
    502: "Canvas is temporarily unavailable (502) — retry shortly",
    503: "Canvas is under maintenance (503) — retry shortly",
    504: "Canvas request timed out (504) — retry with a smaller batch",
}


def friendly_error(response):
    """Return a user-friendly error string for a failed Canvas API response."""
    status = response.status_code
    default = f"Canvas API error {status}"
    friendly = FRIENDLY_ERRORS.get(status, default)
    # Append Canvas error message if present
    try:
        body = response.json()
        if "errors" in body:
            detail = body["errors"]
            if isinstance(detail, list):
                detail = "; ".join(str(e.get("message", e)) if isinstance(e, dict) else str(e) for e in detail)
            elif isinstance(detail, dict):
                detail = "; ".join(f"{k}: {v}" for k, v in detail.items())
            friendly += f" — {detail}"
        elif "message" in body:
            friendly += f" — {body['message']}"
    except Exception:
        pass
    return friendly


def _request_with_retry(method, url, headers, max_retries=MAX_RETRIES, **kwargs):
    """Execute an HTTP request with exponential backoff on rate limits.

    Retries on HTTP 403, 429, 500, 502, 503, 504. Proactively slows down
    when X-Rate-Limit-Remaining drops below 10. Adds a small inter-request
    delay to avoid bursty traffic.

    Args:
        method: requests function (requests.get, requests.post, etc.)
        url: Target URL
        headers: Authorization headers
        max_retries: Number of retry attempts
        **kwargs: Passed through to requests (json, params, data, etc.)

    Returns:
        requests.Response object
    """
    resp = None
    for attempt in range(max_retries):
        _pace()
        resp = method(url, headers=headers, **kwargs)

        # Proactive rate limit check
        remaining = int(float(resp.headers.get("X-Rate-Limit-Remaining", 700)))
        if remaining < 10:
            time.sleep(2.0)
        elif remaining < 50:
            time.sleep(0.5)

        # Success — add inter-request delay and return
        if resp.status_code in (200, 201):
            time.sleep(INTER_REQUEST_DELAY)
            try:
                from idw_metrics import track
                track("api_call", context={"status_code": resp.status_code})
            except Exception:
                pass
            return resp

        # Token expired — don't retry, give actionable error
        if resp.status_code == 401:
            instance = os.environ.get("CANVAS_ACTIVE_INSTANCE", "prod")
            token_var = "CANVAS_DEV_TOKEN" if instance == "dev" else "CANVAS_TOKEN"
            _log.error("Authentication failed (HTTP 401). Your Canvas API token may have expired.")
            _log.error("→ Regenerate at: Canvas → Account → Settings → New Access Token")
            _log.error("→ Then update %s in your .env file and run /canvas-connect", token_var)
            return resp

        # Retryable errors — exponential backoff
        if resp.status_code in (403, 429, 500, 502, 503, 504):
            if attempt < max_retries - 1:
                delay = BASE_DELAY * (2 ** attempt)
                _log.warning("Rate limit/transient error (HTTP %s), retrying in %.1fs (attempt %d/%d)",
                      resp.status_code, delay, attempt + 1, max_retries)
                time.sleep(delay)
                continue

        # Non-retryable error — return immediately
        _log.warning(friendly_error(resp))
        try:
            from idw_metrics import track
            track("error_occurred", context={"script": "canvas_api.py", "error_type": "http_error", "status_code": resp.status_code})
        except Exception:
            pass
        return resp

    # Retries exhausted
    if resp is not None and resp.status_code not in (200, 201):
        _log.warning(friendly_error(resp))
        try:
            from idw_metrics import track
            track("error_occurred", context={"script": "canvas_api.py", "error_type": "http_error", "status_code": resp.status_code})
        except Exception:
            pass
    return resp


# ============================================================
# PAGINATION
# ============================================================
def paginated_get(url, headers, params=None):
    """Fetch all pages of a paginated Canvas API response."""
    results = []
    while url:
        resp = _request_with_retry(requests.get, url, headers, params=params)
        if resp.status_code != 200:
            friendly = FRIENDLY_ERRORS.get(resp.status_code,
                       f"HTTP {resp.status_code} from Canvas API")
            _log.error("API error in paginated_get: %s — URL: %s", friendly, url)
            raise RuntimeError(f"Canvas API error: {friendly}")
        results.extend(resp.json())
        # Parse Link header for next page
        links = resp.headers.get("Link", "")
        url = None
        for part in links.split(","):
            if 'rel="next"' in part:
                url = part.split("<")[1].split(">")[0]
        params = None  # params only needed for first request
    return results


# ============================================================
# FILE UPLOAD (3-step Canvas process)
# ============================================================
def upload_file(config, filepath, folder_id, content_type="text/html"):
    """Upload a file to Canvas using the 3-step upload process.

    Args:
        config: Canvas API config dict from get_config()
        filepath: Local path to the file to upload
        folder_id: Canvas folder ID to upload into
        content_type: MIME type of the file

    Returns:
        File ID on success, None on failure
    """
    require_course_id(config)
    _check_write_allowed(config, f"upload_file({os.path.basename(filepath)})")
    filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)

    # Step 1: Request upload URL
    resp = requests.post(
        f"{config['course_url']}/files",
        headers=config["headers"],
        json={
            "name": filename,
            "size": filesize,
            "content_type": content_type,
            "parent_folder_id": folder_id,
            "on_duplicate": "overwrite",
        },
    )
    if resp.status_code != 200:
        _log.error("File upload step 1 for %s: HTTP %s %s", filename, resp.status_code, resp.text[:200])
        return None

    upload_info = resp.json()
    upload_url = upload_info["upload_url"]
    upload_params = upload_info.get("upload_params", {})

    # Step 2: POST file to upload URL
    with open(filepath, "rb") as f:
        resp2 = requests.post(
            upload_url,
            data=upload_params,
            files={"file": (filename, f, content_type)},
            allow_redirects=False,
        )

    # Step 3: Confirm upload (handle redirect or direct response)
    if resp2.status_code in (200, 201):
        return resp2.json()["id"]
    elif resp2.status_code in (301, 302, 303):
        confirm_url = resp2.headers.get("Location")
        if confirm_url:
            resp3 = requests.get(confirm_url, headers=config["headers"])
            if resp3.status_code == 200:
                return resp3.json()["id"]
            else:
                _log.error("File upload step 3 for %s: HTTP %s", filename, resp3.status_code)
                return None
    else:
        _log.error("File upload step 2 for %s: HTTP %s %s", filename, resp2.status_code, resp2.text[:200])
        return None


# ============================================================
# PAGE HELPERS
# ============================================================
def get_page(config, page_slug):
    """Fetch a Canvas wiki page by slug. Returns page dict or None."""
    require_course_id(config)
    resp = requests.get(
        f"{config['course_url']}/pages/{page_slug}",
        headers=config["headers"],
    )
    if resp.status_code == 200:
        return resp.json()
    _log.error("Fetching page %s: HTTP %s", page_slug, resp.status_code)
    return None


def update_page(config, page_slug, body):
    """Update a Canvas wiki page's HTML body. Returns True on success."""
    require_course_id(config)
    _check_write_allowed(config, f"update_page({page_slug})")
    resp = requests.put(
        f"{config['course_url']}/pages/{page_slug}",
        headers={**config["headers"], "Content-Type": "application/json"},
        json={"wiki_page": {"body": body}},
    )
    if resp.status_code == 200:
        _track("pages_pushed")
        return True
    _log.error("Updating page %s: HTTP %s %s", page_slug, resp.status_code, resp.text[:200])
    return False


def get_all_pages(config):
    """Fetch all wiki pages for a course. Returns list of page dicts."""
    require_course_id(config)
    return paginated_get(
        f"{config['course_url']}/pages?per_page=100",
        config["headers"],
    )


# ============================================================
# FOLDER HELPERS
# ============================================================
def get_or_create_folder(config, parent_path, folder_name):
    """Find or create a folder under parent_path. Returns folder ID or None."""
    require_course_id(config)
    full_path = f"{parent_path}/{folder_name}" if parent_path else folder_name

    # Check if folder exists
    resp = requests.get(
        f"{config['course_url']}/folders/by_path/{full_path}",
        headers=config["headers"],
    )
    if resp.status_code == 200:
        folder = resp.json()
        _log.info("Found folder: %s (id=%s)", full_path, folder["id"])
        return folder["id"]

    # Create it (write operation)
    _check_write_allowed(config, f"create_folder({full_path})")
    resp = requests.post(
        f"{config['course_url']}/folders",
        headers=config["headers"],
        json={"name": folder_name, "parent_folder_path": parent_path},
    )
    if resp.status_code in (200, 201):
        folder = resp.json()
        _log.info("Created folder: %s (id=%s)", full_path, folder["id"])
        return folder["id"]
    else:
        _log.error("Creating folder %s: HTTP %s %s", full_path, resp.status_code, resp.text[:200])
        return None


# ============================================================
# MEDIA HELPERS
# ============================================================
def get_media_entry_id(config, file_id):
    """Get the media_entry_id for a Canvas file. Returns string or None."""
    require_course_id(config)
    resp = requests.get(
        f"{config['course_url']}/files/{file_id}",
        headers=config["headers"],
    )
    if resp.status_code == 200:
        return resp.json().get("media_entry_id")
    return None


def upload_caption(config, media_entry_id, vtt_content, locale="en", kind="subtitles"):
    """Upload a VTT caption track to a Canvas media object.

    Returns (status_code, response_text).
    """
    _check_write_allowed(config, f"upload_caption({media_entry_id})")
    resp = requests.put(
        f"{config['base_url']}/media_objects/{media_entry_id}/media_tracks",
        headers=config["headers"],
        json=[{
            "locale": locale,
            "content": vtt_content,
            "kind": kind,
        }],
    )
    return resp.status_code, resp.text[:200]


# ============================================================
# CONTENT MIGRATION (course-to-course transfer)
# ============================================================
def create_content_migration(config_dest, source_course_id, select=None):
    """Start a course copy migration into the destination course.

    Args:
        config_dest: Config for the destination course (must have course_id set)
        source_course_id: Canvas ID of the source course to copy from
        select: Optional dict of content to copy selectively, e.g.
                {"modules": {"1234": True}, "pages": {"5678": True}}
                If None, copies everything.

    Returns:
        Migration dict on success, None on failure.
    """
    require_course_id(config_dest)
    _check_write_allowed(config_dest, f"content_migration(source={source_course_id})")
    payload = {
        "migration_type": "course_copy_importer",
        "settings": {"source_course_id": str(source_course_id)},
    }
    if select:
        payload["select"] = select

    resp = _request_with_retry(
        requests.post,
        f"{config_dest['course_url']}/content_migrations",
        config_dest["headers"],
        json=payload,
    )
    if resp.status_code in (200, 201):
        return resp.json()
    _log.error("Creating migration: HTTP %s %s", resp.status_code, resp.text[:200])
    return None


def check_migration_progress(config, migration_id):
    """Poll a content migration for its current status.

    Returns:
        Migration dict with 'workflow_state' (queued, running, completed, failed).
    """
    require_course_id(config)
    resp = requests.get(
        f"{config['course_url']}/content_migrations/{migration_id}",
        headers=config["headers"],
    )
    if resp.status_code == 200:
        return resp.json()
    return {"workflow_state": "unknown", "error": resp.text[:200]}


# ============================================================
# DELETE OPERATIONS — guarded with backup + write check
# Course deletion is intentionally excluded (admin-only action).
# ============================================================

def delete_page(config, page_slug):
    """Delete a single page from Canvas.

    Safety: checks write permission, backs up page content before deletion.
    Returns the deleted page dict on success, None on failure.
    """
    _check_write_allowed(config, f"delete_page:{page_slug}")
    require_course_id(config)

    # Fetch current page content for backup
    resp = requests.get(
        f"{config['course_url']}/pages/{page_slug}",
        headers=config["headers"],
    )
    if resp.status_code != 200:
        _log.error("Cannot fetch page '%s' for backup before delete: HTTP %s", page_slug, resp.status_code)
        return None

    page_data = resp.json()
    body = page_data.get("body", "")

    # Backup before deleting
    try:
        from backup_manager import save_backup
        save_backup(config.get("course_id", "unknown"), page_slug, body, "PRE-DELETE BACKUP")
        _log.info("Backed up page '%s' before deletion", page_slug)
    except Exception as e:
        _log.warning("Could not backup page '%s' before delete: %s", page_slug, e)

    # Delete
    del_resp = requests.delete(
        f"{config['course_url']}/pages/{page_slug}",
        headers=config["headers"],
    )
    if del_resp.status_code in (200, 204):
        _log.info("Deleted page '%s'", page_slug)
        _track("page_deleted", page_slug=page_slug)
        return page_data
    _log.error("Delete page '%s' failed: HTTP %s %s", page_slug, del_resp.status_code, del_resp.text[:200])
    return None


def delete_module(config, module_id):
    """Delete a module and all its items from Canvas.

    Safety: checks write permission, logs module name and item count.
    Returns the deleted module dict on success, None on failure.
    """
    _check_write_allowed(config, f"delete_module:{module_id}")
    require_course_id(config)

    # Fetch module info for logging
    resp = requests.get(
        f"{config['course_url']}/modules/{module_id}",
        headers=config["headers"],
    )
    module_info = resp.json() if resp.status_code == 200 else {}
    module_name = module_info.get("name", f"ID:{module_id}")
    items_count = module_info.get("items_count", "?")
    _log.warning("Deleting module '%s' (%s items)", module_name, items_count)

    del_resp = requests.delete(
        f"{config['course_url']}/modules/{module_id}",
        headers=config["headers"],
    )
    if del_resp.status_code in (200, 204):
        _log.info("Deleted module '%s' (ID: %s)", module_name, module_id)
        _track("module_deleted", module_name=module_name, module_id=module_id)
        return module_info
    _log.error("Delete module '%s' failed: HTTP %s %s", module_name, del_resp.status_code, del_resp.text[:200])
    return None


def delete_module_item(config, module_id, item_id):
    """Delete a single item from a module.

    Safety: checks write permission.
    Returns True on success, False on failure.
    """
    _check_write_allowed(config, f"delete_module_item:{module_id}/{item_id}")
    require_course_id(config)

    del_resp = requests.delete(
        f"{config['course_url']}/modules/{module_id}/items/{item_id}",
        headers=config["headers"],
    )
    if del_resp.status_code in (200, 204):
        _log.info("Deleted item %s from module %s", item_id, module_id)
        return True
    _log.error("Delete item %s failed: HTTP %s", item_id, del_resp.status_code)
    return False


def delete_assignment(config, assignment_id):
    """Delete an assignment from Canvas.

    Safety: checks write permission, logs assignment name.
    Returns the deleted assignment dict on success, None on failure.
    """
    _check_write_allowed(config, f"delete_assignment:{assignment_id}")
    require_course_id(config)

    resp = requests.get(
        f"{config['course_url']}/assignments/{assignment_id}",
        headers=config["headers"],
    )
    assignment_info = resp.json() if resp.status_code == 200 else {}
    assignment_name = assignment_info.get("name", f"ID:{assignment_id}")

    del_resp = requests.delete(
        f"{config['course_url']}/assignments/{assignment_id}",
        headers=config["headers"],
    )
    if del_resp.status_code in (200, 204):
        _log.info("Deleted assignment '%s' (ID: %s)", assignment_name, assignment_id)
        _track("assignment_deleted", name=assignment_name)
        return assignment_info
    _log.error("Delete assignment '%s' failed: HTTP %s %s", assignment_name, del_resp.status_code, del_resp.text[:200])
    return None


def delete_quiz(config, quiz_id):
    """Delete a quiz from Canvas.

    Safety: checks write permission, logs quiz name.
    Returns the deleted quiz dict on success, None on failure.
    """
    _check_write_allowed(config, f"delete_quiz:{quiz_id}")
    require_course_id(config)

    resp = requests.get(
        f"{config['course_url']}/quizzes/{quiz_id}",
        headers=config["headers"],
    )
    quiz_info = resp.json() if resp.status_code == 200 else {}
    quiz_name = quiz_info.get("title", f"ID:{quiz_id}")

    del_resp = requests.delete(
        f"{config['course_url']}/quizzes/{quiz_id}",
        headers=config["headers"],
    )
    if del_resp.status_code in (200, 204):
        _log.info("Deleted quiz '%s' (ID: %s)", quiz_name, quiz_id)
        _track("quiz_deleted", name=quiz_name)
        return quiz_info
    _log.error("Delete quiz '%s' failed: HTTP %s %s", quiz_name, del_resp.status_code, del_resp.text[:200])
    return None


def delete_discussion(config, topic_id):
    """Delete a discussion topic from Canvas.

    Safety: checks write permission, logs topic name.
    Returns the deleted topic dict on success, None on failure.
    """
    _check_write_allowed(config, f"delete_discussion:{topic_id}")
    require_course_id(config)

    resp = requests.get(
        f"{config['course_url']}/discussion_topics/{topic_id}",
        headers=config["headers"],
    )
    topic_info = resp.json() if resp.status_code == 200 else {}
    topic_name = topic_info.get("title", f"ID:{topic_id}")

    del_resp = requests.delete(
        f"{config['course_url']}/discussion_topics/{topic_id}",
        headers=config["headers"],
    )
    if del_resp.status_code in (200, 204):
        _log.info("Deleted discussion '%s' (ID: %s)", topic_name, topic_id)
        _track("discussion_deleted", name=topic_name)
        return topic_info
    _log.error("Delete discussion '%s' failed: HTTP %s %s", topic_name, del_resp.status_code, del_resp.text[:200])
    return None


# ============================================================
# MODULE & ITEM HELPERS
# ============================================================
def get_modules(config, include_items=False):
    """Fetch all modules for a course. Optionally include items."""
    require_course_id(config)
    params = {"per_page": 100}
    if include_items:
        params["include[]"] = "items"
    return paginated_get(
        f"{config['course_url']}/modules",
        config["headers"],
        params=params,
    )


def get_module_items(config, module_id):
    """Fetch all items in a module."""
    require_course_id(config)
    return paginated_get(
        f"{config['course_url']}/modules/{module_id}/items?per_page=100",
        config["headers"],
    )


def get_assignments_with_rubrics(config):
    """Fetch all assignments for the course with rubric data included.

    Canvas includes ``rubric`` (array of criteria) and ``use_rubric_for_grading``
    fields when ``include[]=rubric`` is requested.  Returns a list of assignment
    dicts that can be used to build a rubric presence lookup.
    """
    require_course_id(config)
    return paginated_get(
        f"{config['course_url']}/assignments",
        config["headers"],
        params={"per_page": 100, "include[]": "rubric"},
    )


# ============================================================
# CLI ENTRY POINT
# ============================================================
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check-write":
        instance = get_active_instance()
        read_only = is_read_only()
        config = get_config()
        domain = config.get("domain", "unknown")
        print(f"Instance: {instance}")
        print(f"Domain: {domain}")
        print(f"Read-only: {read_only}")
        if read_only:
            print("STATUS: BLOCKED — writes are disabled (CANVAS_READ_ONLY=true)")
            sys.exit(1)
        else:
            print(f"STATUS: WRITES ENABLED on {domain} ({instance})")
            sys.exit(0)
