#!/usr/bin/env python3
"""Add expandable text transcripts below media embeds on Canvas wiki pages.

For WCAG 1.2.1 (audio-only) and 1.2.2 (captions), adds a <details> block
with the full transcript text below each video/audio embed on the relevant pages.

Usage:
    python add_transcripts.py <config_json>

Requires environment variables:
    CANVAS_TOKEN, CANVAS_DOMAIN, CANVAS_COURSE_ID

Config JSON format:
    {
        "transcripts_dir": "/path/to/vtt/files",
        "pages": [
            {
                "module": "m1",
                "page_slug": "m1-prepare-to-learn",
                "media_type": "audio",
                "vtt": "m1-audio.vtt",
                "file_id": 12345
            },
            {
                "module": "m1",
                "page_slug": "m1-lesson-lecture-video",
                "media_type": "video",
                "vtt": "m1-video.vtt",
                "file_id": 12346
            }
        ]
    }
"""

import os
import sys
import re
import json
import html
import argparse

# Logging
try:
    from idw_logger import get_logger
    _log = get_logger("add_transcripts")
except ImportError:
    import logging
    _log = logging.getLogger("add_transcripts")


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from canvas_api import get_config, require_course_id, get_page, update_page


def vtt_to_text(vtt_path):
    """Convert VTT file to plain text transcript."""
    with open(vtt_path, "r") as f:
        lines = f.readlines()

    text_lines = []
    for line in lines:
        line = line.strip()
        # Skip WEBVTT header, timestamps, and blank lines
        if not line or line == "WEBVTT" or re.match(r"\d{2}:\d{2}", line):
            continue
        text_lines.append(line)

    # Join and clean up
    text = " ".join(text_lines)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def make_transcript_block(text, media_type="video"):
    """Generate an expandable transcript HTML block."""
    label = "Lecture Video Transcript" if media_type == "video" else "Audio Primer Transcript"
    escaped = html.escape(text)
    # Break into paragraphs every ~300 words for readability
    words = escaped.split()
    paragraphs = []
    for i in range(0, len(words), 300):
        chunk = " ".join(words[i : i + 300])
        paragraphs.append(f"<p>{chunk}</p>")
    content = "\n".join(paragraphs)

    return f'''<details style="margin: 15px 0; border: 1px solid #ddd; border-radius: 6px; padding: 0;">
<summary style="padding: 12px 15px; background-color: #f5f5f5; cursor: pointer; font-weight: bold; color: #8C1D40; border-radius: 6px;">{label} (click to expand)</summary>
<div style="padding: 15px; font-size: 14px; line-height: 1.6; color: #333; max-height: 400px; overflow-y: auto;">
{content}
</div>
</details>'''


def add_transcript_to_page(config, page_slug, vtt_path, media_type, file_id, module):
    """Add transcript block after the media embed on a page. Returns True on success."""
    if not os.path.exists(vtt_path):
        print(f"  ERR {module} {media_type}: VTT not found: {vtt_path}")
        return False

    page = get_page(config, page_slug)
    if not page:
        print(f"  ERR {module} {media_type}: page fetch failed")
        return False

    body = page.get("body", "")

    # Idempotent check
    if "Transcript (click to expand)" in body:
        print(f"  SKIP {module} {media_type}: transcript already exists")
        return True

    # Generate transcript text
    text = vtt_to_text(vtt_path)
    transcript_block = make_transcript_block(text, media_type)

    # Find the media embed and insert after it
    file_str = str(file_id)

    if file_str in body:
        idx = body.index(file_str)
        search_from = idx

        # Find the enclosing block
        patterns_to_try = [
            (r"</a>", "</a>"),
            (r"</iframe>\s*</div>", "</div>"),
            (r"</iframe>", "</iframe>"),
        ]

        best_pos = len(body)
        for pattern, tag in patterns_to_try:
            m = re.search(pattern, body[search_from:])
            if m and (search_from + m.end()) < best_pos:
                best_pos = search_from + m.end()

        if best_pos < len(body):
            body = body[:best_pos] + f"\n{transcript_block}\n" + body[best_pos:]
        else:
            m = re.search(r"(<hr|<h2)", body[idx:])
            if m:
                insert_pos = idx + m.start()
                body = body[:insert_pos] + f"\n{transcript_block}\n" + body[insert_pos:]
            else:
                body += f"\n{transcript_block}\n"
    else:
        print(f"  WARN {module} {media_type}: file ID {file_id} not found on page, appending")
        m = re.search(r"<h2", body)
        if m:
            body = body[: m.start()] + f"\n{transcript_block}\n" + body[m.start() :]
        else:
            body += f"\n{transcript_block}\n"

    if update_page(config, page_slug, body):
        print(f"  OK {module} {media_type}: transcript added to {page_slug}")
        return True
    else:
        print(f"  ERR {module} {media_type}: update failed")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Add expandable text transcripts below media embeds on Canvas pages."
    )
    parser.add_argument(
        "config_json",
        help="Path to JSON config file with page → VTT mappings",
    )
    args = parser.parse_args()

    config = get_config()
    require_course_id(config)

    with open(args.config_json, "r") as f:
        transcript_config = json.load(f)

    transcripts_dir = transcript_config.get("transcripts_dir", ".")
    success = 0
    errors = 0

    for entry in transcript_config.get("pages", []):
        vtt_path = os.path.join(transcripts_dir, entry["vtt"])
        result = add_transcript_to_page(
            config,
            entry["page_slug"],
            vtt_path,
            entry["media_type"],
            entry["file_id"],
            entry["module"],
        )
        if result:
            success += 1
        else:
            errors += 1

    print(f"\n=== DONE === {success} transcripts added, {errors} errors")


if __name__ == "__main__":
    main()
