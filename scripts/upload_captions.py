#!/usr/bin/env python3
"""Upload VTT caption tracks to Canvas media objects.

Usage:
    python upload_captions.py <config_json>

    config_json: Path to JSON file mapping modules to file IDs and VTT paths.

Requires environment variables:
    CANVAS_TOKEN, CANVAS_DOMAIN, CANVAS_COURSE_ID

Config JSON format:
    {
        "transcripts_dir": "/path/to/vtt/files",
        "video_files": {
            "m1": {"file_id": 12345, "vtt": "m1-video.vtt"},
            "m2": {"file_id": 12346, "vtt": "m2-video.vtt"}
        },
        "audio_files": {
            "m1": {"file_id": 12347, "vtt": "m1-audio.vtt"},
            "m2": {"file_id": 12348, "vtt": "m2-audio.vtt"}
        }
    }
"""

import os
import sys
import json
import argparse

# Logging
try:
    from idw_logger import get_logger
    _log = get_logger("upload_captions")
except ImportError:
    import logging
    _log = logging.getLogger("upload_captions")


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from canvas_api import get_config, require_course_id, get_media_entry_id, upload_caption


def process_media_group(config, group_name, media_files, transcripts_dir):
    """Upload captions for a group of media files (video or audio)."""
    success = 0
    errors = 0

    print(f"\n=== {group_name.upper()} CAPTIONS ===")
    for module, info in sorted(media_files.items()):
        file_id = info["file_id"]
        vtt_name = info["vtt"]

        media_id = get_media_entry_id(config, file_id)
        if not media_id:
            print(f"  ERR {module}: no media_entry_id for file {file_id}")
            errors += 1
            continue

        vtt_path = os.path.join(transcripts_dir, vtt_name)
        if not os.path.exists(vtt_path):
            print(f"  ERR {module}: VTT file not found: {vtt_path}")
            errors += 1
            continue

        with open(vtt_path, "r") as f:
            vtt_content = f.read()

        status, text = upload_caption(config, media_id, vtt_content)
        if status in (200, 201):
            print(f"  OK {module}: captions uploaded (media: {media_id})")
            success += 1
        else:
            print(f"  ERR {module}: status {status} - {text}")
            errors += 1

    return success, errors


def main():
    parser = argparse.ArgumentParser(
        description="Upload VTT caption tracks to Canvas media objects."
    )
    parser.add_argument(
        "config_json",
        help="Path to JSON config file with file IDs and VTT mappings",
    )
    args = parser.parse_args()

    config = get_config()
    require_course_id(config)

    with open(args.config_json, "r") as f:
        caption_config = json.load(f)

    transcripts_dir = caption_config.get("transcripts_dir", ".")
    total_success = 0
    total_errors = 0

    if "video_files" in caption_config:
        s, e = process_media_group(config, "video", caption_config["video_files"], transcripts_dir)
        total_success += s
        total_errors += e

    if "audio_files" in caption_config:
        s, e = process_media_group(config, "audio", caption_config["audio_files"], transcripts_dir)
        total_success += s
        total_errors += e

    print(f"\n=== DONE === {total_success} uploaded, {total_errors} errors")


if __name__ == "__main__":
    main()
