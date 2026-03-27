#!/usr/bin/env python3
"""Course structure template manager — save and load reusable course skeletons.

Ported from Canvas Shadow Editor's template engine.

Storage:
    templates/saved/tmpl-{uuid}.json

Usage:
    python template_manager.py --save --name "Bio 101" --description "8-week bio" --course-id 255160
    python template_manager.py --list
    python template_manager.py --get --template-id tmpl-abc123
    python template_manager.py --delete --template-id tmpl-abc123
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Logging
try:
    from idw_logger import get_logger
    _log = get_logger("template_manager")
except ImportError:
    import logging
    _log = logging.getLogger("template_manager")


# Add scripts dir to path for canvas_api import
sys.path.insert(0, os.path.dirname(__file__))
import canvas_api

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = PLUGIN_ROOT / "templates" / "saved"


def save_template(name, description, course_id, mode=None):
    """Save the current course structure as a reusable template.

    Fetches modules and items from Canvas, then saves as JSON.

    Returns:
        Template dict with id, path, and metadata.
    """
    config = canvas_api.get_config(instance=mode, course_id=course_id)
    canvas_api.require_course_id(config)

    # Fetch course info
    import requests
    resp = requests.get(
        f"{config['course_url']}",
        headers=config["headers"],
        timeout=15,
    )
    course_name = ""
    if resp.status_code == 200:
        course_name = resp.json().get("name", "")

    # Fetch modules with items
    modules = canvas_api.get_modules(config, include_items=True)

    # Build template structure
    structure = []
    total_items = 0
    for mod in modules:
        module_data = {
            "name": mod.get("name", ""),
            "items": [],
        }
        for item in mod.get("items", []):
            item_data = {
                "title": item.get("title", ""),
                "item_type": item.get("type", ""),
                "indent_level": item.get("indent", 0),
                "published": item.get("published", False),
            }
            # Add grading info if available
            details = item.get("content_details", {})
            if details.get("points_possible"):
                item_data["points_possible"] = details["points_possible"]

            module_data["items"].append(item_data)
            total_items += 1
        structure.append(module_data)

    # Generate template ID and save
    template_id = f"tmpl-{uuid.uuid4().hex[:12]}"
    TEMPLATE_ROOT.mkdir(parents=True, exist_ok=True)

    template = {
        "id": template_id,
        "name": name,
        "description": description,
        "source_course_id": str(course_id),
        "source_course_name": course_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "module_count": len(structure),
        "item_count": total_items,
        "structure": structure,
    }

    template_path = TEMPLATE_ROOT / f"{template_id}.json"
    template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    return {
        "id": template_id,
        "path": str(template_path),
        "name": name,
        "module_count": len(structure),
        "item_count": total_items,
    }


def list_templates():
    """List all saved templates (metadata only, no structure).

    Returns:
        List of template summary dicts.
    """
    if not TEMPLATE_ROOT.exists():
        return []

    templates = []
    for f in sorted(TEMPLATE_ROOT.glob("tmpl-*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            templates.append({
                "id": data["id"],
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "source_course_name": data.get("source_course_name", ""),
                "module_count": data.get("module_count", 0),
                "item_count": data.get("item_count", 0),
                "created_at": data.get("created_at", ""),
            })
        except (json.JSONDecodeError, KeyError):
            continue

    return templates


def get_template(template_id):
    """Get full template including structure.

    Returns:
        Full template dict, or None if not found.
    """
    template_path = TEMPLATE_ROOT / f"{template_id}.json"
    if not template_path.exists():
        return None
    return json.loads(template_path.read_text(encoding="utf-8"))


def delete_template(template_id):
    """Delete a template by ID.

    Returns:
        True if deleted, False if not found.
    """
    template_path = TEMPLATE_ROOT / f"{template_id}.json"
    if not template_path.exists():
        return False
    template_path.unlink()
    return True


def main():
    parser = argparse.ArgumentParser(description="Course structure template manager")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--save", action="store_true", help="Save current course as template")
    group.add_argument("--list", action="store_true", help="List saved templates")
    group.add_argument("--get", action="store_true", help="Get full template by ID")
    group.add_argument("--delete", action="store_true", help="Delete a template")

    parser.add_argument("--name", help="Template name (for --save)")
    parser.add_argument("--description", default="", help="Template description (for --save)")
    parser.add_argument("--course-id", help="Canvas course ID (for --save)")
    parser.add_argument("--template-id", help="Template ID (for --get and --delete)")
    parser.add_argument("--mode", choices=["prod", "dev"], help="Canvas instance")

    args = parser.parse_args()

    if args.save:
        if not args.name or not args.course_id:
            parser.error("--save requires --name and --course-id")
        result = save_template(args.name, args.description, args.course_id, args.mode)
        print(json.dumps({"ok": True, **result}))

    elif args.list:
        templates = list_templates()
        print(json.dumps({"ok": True, "count": len(templates), "templates": templates}, indent=2))

    elif args.get:
        if not args.template_id:
            parser.error("--get requires --template-id")
        template = get_template(args.template_id)
        if template is None:
            print(json.dumps({"ok": False, "error": f"Template not found: {args.template_id}"}))
            sys.exit(1)
        print(json.dumps({"ok": True, "template": template}, indent=2))

    elif args.delete:
        if not args.template_id:
            parser.error("--delete requires --template-id")
        deleted = delete_template(args.template_id)
        print(json.dumps({"ok": deleted, "template_id": args.template_id}))


if __name__ == "__main__":
    main()
