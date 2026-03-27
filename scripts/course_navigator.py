#!/usr/bin/env python3
"""Course navigator — fetch and display the full Canvas course tree.

Fetches modules → items (pages, assignments, quizzes, discussions, files,
external tools, text headers) and presents a structured tree view.

Usage:
    python course_navigator.py --tree
    python course_navigator.py --tree --mode dev
    python course_navigator.py --find "module 3 quiz"
    python course_navigator.py --refresh
    python course_navigator.py --json
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# Logging
try:
    from idw_logger import get_logger
    _log = get_logger("course_navigator")
except ImportError:
    import logging
    _log = logging.getLogger("course_navigator")

try:
    from idw_metrics import track as _track
except ImportError:
    def _track(*a, **k): pass


# Add scripts dir to path for canvas_api import
sys.path.insert(0, os.path.dirname(__file__))
import canvas_api

try:
    from requests.exceptions import RequestException as _RequestException
except ImportError:
    _RequestException = None

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PLUGIN_ROOT / "staging"
CACHE_FILE = CACHE_DIR / ".course-tree.json"
CACHE_TTL = 300  # 5 minutes


# Item type display icons (text-based for terminal)
ITEM_ICONS = {
    "Page": "[P]",
    "Assignment": "[A]",
    "Quiz": "[Q]",
    "Discussion": "[D]",
    "File": "[F]",
    "ExternalTool": "[T]",
    "ExternalUrl": "[U]",
    "SubHeader": "---",
}


def fetch_course_tree(config):
    """Fetch the full course tree from Canvas API.

    Returns:
        List of module dicts, each with 'items' list containing
        type, title, indent, published, page_url, etc.
    """
    canvas_api.require_course_id(config)
    modules = canvas_api.get_modules(config, include_items=True)

    tree = []
    for mod in modules:
        module_node = {
            "id": mod["id"],
            "name": mod.get("name", "Untitled Module"),
            "position": mod.get("position", 0),
            "published": mod.get("published", False),
            "items": [],
        }
        for item in mod.get("items", []):
            item_node = {
                "id": item.get("id"),
                "title": item.get("title", ""),
                "type": item.get("type", ""),
                "indent": item.get("indent", 0),
                "published": item.get("published", False),
                "page_url": item.get("page_url", ""),
                "content_id": item.get("content_id"),
                "external_url": item.get("external_url", ""),
                "html_url": item.get("html_url", ""),
            }
            # Add points for graded items
            if item.get("content_details", {}).get("points_possible"):
                item_node["points"] = item["content_details"]["points_possible"]
            module_node["items"].append(item_node)
        tree.append(module_node)

    return tree


def save_cache(tree, course_id):
    """Save tree to local cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_data = {
        "course_id": course_id,
        "fetched_at": time.time(),
        "tree": tree,
    }
    CACHE_FILE.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")


def load_cache(course_id):
    """Load tree from cache if fresh enough. Returns tree or None."""
    if not CACHE_FILE.exists():
        return None
    try:
        cache_data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        if cache_data.get("course_id") != course_id:
            return None
        if time.time() - cache_data.get("fetched_at", 0) > CACHE_TTL:
            return None
        return cache_data["tree"]
    except (json.JSONDecodeError, KeyError):
        return None


def get_tree(config, force_refresh=False):
    """Get course tree (cached or fresh)."""
    course_id = config["course_id"]
    if not force_refresh:
        cached = load_cache(course_id)
        if cached:
            return cached

    tree = fetch_course_tree(config)
    save_cache(tree, course_id)
    return tree


def print_tree(tree):
    """Print a human-readable tree to stdout."""
    for mod in tree:
        pub = "+" if mod["published"] else "-"
        print(f"\n{pub} {mod['name']}")
        for item in mod["items"]:
            icon = ITEM_ICONS.get(item["type"], "[?]")
            indent = "  " * (item["indent"] + 1)
            pub_mark = "" if item["published"] else " (unpublished)"
            points = f" ({item['points']} pts)" if item.get("points") else ""
            slug = f" [{item['page_url']}]" if item.get("page_url") else ""
            print(f"{indent}{icon} {item['title']}{points}{slug}{pub_mark}")


def find_item(tree, query):
    """Search for items matching a query string.

    Supports:
        - "module 3 quiz" → finds quiz items in module 3
        - "m2-overview" → finds by page slug
        - "guided practice" → finds by title substring

    Returns:
        List of matching items with module context.
    """
    query_lower = query.lower().strip()
    results = []

    # Check for "module N [type]" pattern
    mod_match = re.match(r"module\s*(\d+)\s*(.*)", query_lower)
    target_module_num = None
    type_filter = None
    if mod_match:
        target_module_num = int(mod_match.group(1))
        type_hint = mod_match.group(2).strip()
        type_map = {
            "quiz": "Quiz", "quizzes": "Quiz",
            "assignment": "Assignment", "assignments": "Assignment",
            "discussion": "Discussion", "discussions": "Discussion",
            "page": "Page", "pages": "Page",
            "file": "File", "files": "File",
        }
        type_filter = type_map.get(type_hint)

    for mod in tree:
        # Check module number match
        mod_num_match = re.search(r"(\d+)", mod["name"])
        mod_num = int(mod_num_match.group(1)) if mod_num_match else None

        if target_module_num is not None and mod_num != target_module_num:
            continue

        for item in mod["items"]:
            match = False

            # Type filter from "module N type" pattern
            if type_filter and item["type"] == type_filter:
                match = True
            # Slug match
            elif item.get("page_url") and query_lower in item["page_url"].lower():
                match = True
            # Title substring match
            elif query_lower in item["title"].lower():
                match = True
            # If we matched the module but no type filter, include all items
            elif target_module_num is not None and type_filter is None:
                match = True

            if match:
                results.append({
                    "module": mod["name"],
                    "module_id": mod["id"],
                    **item,
                })

    return results


def main():
    parser = argparse.ArgumentParser(description="Canvas course navigator")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tree", action="store_true", help="Display full course tree")
    group.add_argument("--find", metavar="QUERY", help="Search for items")
    group.add_argument("--refresh", action="store_true", help="Force refresh cache and display tree")
    group.add_argument("--json", action="store_true", help="Output full tree as JSON")

    parser.add_argument("--mode", choices=["prod", "dev"], help="Canvas instance")

    args = parser.parse_args()
    _track("skill_invoked", context={"skill": "canvas-nav"})
    config = canvas_api.get_config(instance=args.mode)

    if not config["course_id"]:
        _log.error("ERROR: No course ID set. Run /canvas-setup first.")
        sys.exit(1)

    if args.tree:
        tree = get_tree(config)
        print_tree(tree)
    elif args.refresh:
        tree = get_tree(config, force_refresh=True)
        print_tree(tree)
    elif args.json:
        tree = get_tree(config)
        print(json.dumps(tree, indent=2))
    elif args.find:
        tree = get_tree(config)
        results = find_item(tree, args.find)
        if results:
            for r in results:
                icon = ITEM_ICONS.get(r["type"], "[?]")
                slug = f" [{r['page_url']}]" if r.get("page_url") else ""
                print(f"{icon} {r['title']}{slug}  (in {r['module']})")
        else:
            print(f"No items found matching '{args.find}'")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        if _RequestException and isinstance(e, _RequestException):
            _log.exception("Canvas connection error")
            print("\nCould not connect to Canvas. Check your internet connection and Canvas token.")
            sys.exit(1)
        _log.exception("Unexpected error")
        print(f"\nSomething went wrong: {e}")
        print("Check the log at ~/.idw/logs/ for details.")
        sys.exit(1)
