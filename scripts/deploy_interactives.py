#!/usr/bin/env python3
"""Deploy interactive HTML files to Canvas: upload to Files, embed iframes in pages.

Usage:
    python deploy_interactives.py <content_data_path> [--output-dir <dir>] [--folder-name <name>]

Requires environment variables:
    CANVAS_TOKEN, CANVAS_DOMAIN, CANVAS_COURSE_ID

The content data file must define ALL_ACTIVITIES with page_slug and page_type fields.
"""

import os
import re
import sys
import json
import time
import argparse
from collections import defaultdict

# Logging
try:
    from idw_logger import get_logger
    _log = get_logger("deploy_interactives")
except ImportError:
    import logging
    _log = logging.getLogger("deploy_interactives")


# Add parent dir to path for canvas_api import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from canvas_api import get_config, require_course_id, upload_file, get_or_create_folder, get_page, update_page


# Iframe height per activity type
IFRAME_HEIGHTS = {
    "dialog_cards": 550,
    "sequencing": 650,
    "fill_blanks": 600,
    "branching": 700,
    "quiz": 650,
}

# Type labels for the subtitle line
TYPE_LABELS = {
    "dialog_cards": "Flashcards",
    "sequencing": "Sequencing Activity",
    "fill_blanks": "Fill-in-the-Blanks",
    "branching": "Branching Scenario",
    "quiz": "Review Quiz",
}

# Estimated time per type
TIME_EST = {
    "dialog_cards": 3,
    "sequencing": 5,
    "fill_blanks": 5,
    "branching": 5,
    "quiz": 5,
}


def create_all_folders(config, folder_name, module_keys):
    """Create top-level folder and per-module subfolders in course files."""
    print("\n=== CREATING FOLDERS ===")
    top_id = get_or_create_folder(config, "", folder_name)
    if not top_id:
        print(f"FATAL: Could not create {folder_name} folder")
        sys.exit(1)

    folder_ids = {}
    for key in sorted(module_keys):
        fid = get_or_create_folder(config, folder_name, key.upper())
        if fid:
            folder_ids[key] = fid
        time.sleep(0.2)

    return folder_ids


def upload_all_files(config, folder_ids, output_root):
    """Upload all HTML files and return {module_key: {filename: file_id}}."""
    print("\n=== UPLOADING FILES ===")
    file_ids = defaultdict(dict)

    for module_key in sorted(folder_ids.keys()):
        folder_id = folder_ids[module_key]
        module_dir = os.path.join(output_root, module_key)

        if not os.path.isdir(module_dir):
            print(f"  SKIP: {module_key} — no output directory")
            continue

        html_files = sorted(f for f in os.listdir(module_dir) if f.endswith(".html"))
        for filename in html_files:
            filepath = os.path.join(module_dir, filename)
            fid = upload_file(config, filepath, folder_id)
            if fid:
                file_ids[module_key][filename] = fid
                print(f"  OK: {module_key}/{filename} → file_id={fid}")
            else:
                print(f"  FAILED: {module_key}/{filename}")
            time.sleep(0.3)

    return dict(file_ids)


def iframe_html(course_id, file_id, activity):
    """Generate the iframe embed block for a Canvas page."""
    act_type = activity["type"]
    title = activity["title"]
    height = IFRAME_HEIGHTS.get(act_type, 600)
    label = TYPE_LABELS.get(act_type, "Interactive Activity")
    minutes = TIME_EST.get(act_type, 5)

    return f'''<div style="margin: 25px 0; padding: 20px; background-color: #f8f4f0; border: 1px solid #ddd; border-radius: 8px;">
  <h3 style="color: #8C1D40; margin: 0 0 5px 0;">{title}</h3>
  <p style="color: #595959; font-size: 14px; margin: 0 0 12px 0;">{label} | ~{minutes} min | Formative (not graded)</p>
  <iframe src="/courses/{course_id}/files/{file_id}/preview"
          width="100%" height="{height}"
          style="border: 1px solid #ccc; border-radius: 6px;"
          sandbox="allow-same-origin allow-scripts allow-forms"
          title="{title}"
          loading="lazy"></iframe>
</div>'''


def find_injection_point(body, page_type):
    """Find the insertion index in page HTML based on page type."""
    markers_by_type = {
        "prepare": [
            "<h2>What to Think About</h2>",
            "<h2>Think About This Before the Lecture</h2>",
            "<h2>Reflection Questions</h2>",
        ],
        "guided": [
            "<h2>Scenario 1",
            "<h2>Instructions</h2>",
        ],
        "conclusion": [
            '<h2 style="color: #8C1D40; margin-top: 0;">Discussion',
            "<h2>Connections Forward</h2>",
            '<h2 style="color: #8C1D40;">Self-Assessment</h2>',
        ],
    }

    markers = markers_by_type.get(page_type, [])
    for m in markers:
        idx = body.find(m)
        if idx >= 0:
            return idx, m

    # Fallback chain: no standard marker found
    # Try the last </div> in the body (end of content wrapper)
    div_matches = list(re.finditer(r"</div>", body))
    if div_matches:
        last_div = div_matches[-1]
        return last_div.end(), "fallback:end-of-content"

    # Try the last </section>
    sec_matches = list(re.finditer(r"</section>", body))
    if sec_matches:
        last_sec = sec_matches[-1]
        return last_sec.end(), "fallback:end-of-content"

    # Absolute fallback: append at the very end
    return len(body), "fallback:end-of-content"


def patch_pages(config, file_ids, activities_by_page):
    """Update Canvas pages with iframe embeds."""
    print("\n=== PATCHING PAGES ===")
    results = {}

    for page_slug, activities in activities_by_page.items():
        page = get_page(config, page_slug)
        if not page:
            results[page_slug] = False
            continue

        body = page.get("body", "")

        # Idempotent check
        existing = sum(1 for a in activities if a["filename"] in body or a["title"] in body)
        if existing == len(activities):
            print(f"  SKIP: {page_slug} — already has all {len(activities)} iframe(s)")
            results[page_slug] = True
            continue

        page_type = activities[0]["page_type"]
        inject_idx, marker = find_injection_point(body, page_type)

        if marker and marker.startswith("fallback:"):
            _log.warning(
                f"No standard marker found for {page_slug} (type={page_type})"
                " — using fallback injection at end of content"
            )

        if inject_idx is None:
            _log.error(f"  ERROR: {page_slug} — no injection marker found for page_type={page_type}")
            results[page_slug] = False
            continue

        iframe_blocks = []
        for activity in activities:
            module_key = activity["filename"].split("-")[0]
            fid = file_ids.get(module_key, {}).get(activity["filename"])
            if not fid:
                _log.error(f"  ERROR: No file_id for {activity['filename']}")
                continue
            iframe_blocks.append(iframe_html(config["course_id"], fid, activity))

        if not iframe_blocks:
            results[page_slug] = False
            continue

        combined_html = "\n".join(iframe_blocks) + "\n"
        new_body = body[:inject_idx] + combined_html + body[inject_idx:]

        if update_page(config, page_slug, new_body):
            print(f"  OK: {page_slug} — {len(iframe_blocks)} iframe(s) inserted")
            results[page_slug] = True
        else:
            results[page_slug] = False

        time.sleep(0.3)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Deploy interactive HTML files to Canvas."
    )
    parser.add_argument(
        "content_data",
        help="Path to Python file containing ALL_ACTIVITIES dict",
    )
    parser.add_argument(
        "--output-dir",
        default="./output",
        help="Directory containing generated HTML files (default: ./output)",
    )
    parser.add_argument(
        "--folder-name",
        default="H5P",
        help="Canvas folder name for uploads (default: H5P)",
    )
    args = parser.parse_args()

    config = get_config()
    require_course_id(config)

    # Import content data
    import importlib.util
    spec = importlib.util.spec_from_file_location("content_data", args.content_data)
    content_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(content_module)
    ALL_ACTIVITIES = content_module.ALL_ACTIVITIES

    # Collect activities grouped by page_slug
    activities_by_page = defaultdict(list)
    module_keys = set()
    for module_key, activities in sorted(ALL_ACTIVITIES.items()):
        module_keys.add(module_key)
        for activity in activities:
            activities_by_page[activity["page_slug"]].append(activity)

    print(f"Total activities: {sum(len(v) for v in ALL_ACTIVITIES.values())}")
    print(f"Pages to patch: {len(activities_by_page)}")

    folder_ids = create_all_folders(config, args.folder_name, module_keys)
    file_ids = upload_all_files(config, folder_ids, os.path.abspath(args.output_dir))
    total_uploaded = sum(len(v) for v in file_ids.values())
    print(f"\nFiles uploaded: {total_uploaded}")

    results = patch_pages(config, file_ids, activities_by_page)

    # Summary
    print("\n\n=== DEPLOYMENT SUMMARY ===")
    print(f"Folders: {len(folder_ids)}")
    print(f"Files uploaded: {total_uploaded}")
    ok_pages = sum(1 for v in results.values() if v)
    print(f"Pages patched: {ok_pages}/{len(activities_by_page)}")

    # Save file IDs
    id_file = os.path.join(os.path.abspath(args.output_dir), "file_ids.json")
    with open(id_file, "w") as f:
        json.dump(file_ids, f, indent=2)
    print(f"\nFile IDs saved to: {id_file}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        _log.exception("Unexpected error")
        print(f"\nSomething went wrong: {e}")
        print("Check the log at ~/.idw/logs/ for details.")
        sys.exit(1)
