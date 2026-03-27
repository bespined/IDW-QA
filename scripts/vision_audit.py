#!/usr/bin/env python3
"""Vision audit helper — download and prepare images for vision-based accessibility analysis.

Extracts image URLs from Canvas page HTML, downloads them locally, and outputs
a JSON manifest for Claude Code's vision analysis.

Usage:
    python vision_audit.py --page-slug m1-overview --output vision_data.json
    python vision_audit.py --html-file page.html --output vision_data.json
    python vision_audit.py --page-slug m1-overview --semantic --output vision_data.json

The --semantic flag adds alt text vs image content comparison fields to the manifest,
enabling Claude Code to read each image and detect mismatches.
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urljoin, urlparse

# Logging
try:
    from idw_logger import get_logger
    _log = get_logger("vision_audit")
except ImportError:
    import logging
    _log = logging.getLogger("vision_audit")


import requests

# Add scripts dir to path for canvas_api import
sys.path.insert(0, os.path.dirname(__file__))
import canvas_api

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MIN_IMAGE_SIZE = 50  # px — skip tiny icons/spacers
MAX_IMAGES = 15  # per page to avoid overwhelming analysis


def extract_image_urls(html_body, base_url=""):
    """Parse HTML and extract all <img> src attributes with alt text.

    Returns:
        List of dicts: {src, alt, context_text}
    """
    images = []
    # Match <img> tags with src and optional alt
    img_pattern = re.compile(
        r'<img\s+[^>]*?src=["\']([^"\']+)["\'][^>]*?>',
        re.IGNORECASE | re.DOTALL,
    )
    alt_pattern = re.compile(r'alt=["\']([^"\']*)["\']', re.IGNORECASE)
    width_pattern = re.compile(r'width=["\']?(\d+)', re.IGNORECASE)
    height_pattern = re.compile(r'height=["\']?(\d+)', re.IGNORECASE)

    for match in img_pattern.finditer(html_body):
        full_tag = match.group(0)
        src = match.group(1)

        # Resolve relative URLs
        if base_url and not src.startswith(("http://", "https://", "data:")):
            src = urljoin(base_url, src)

        # Skip data URIs and tiny tracking pixels
        if src.startswith("data:"):
            continue

        # Check dimensions if available
        w_match = width_pattern.search(full_tag)
        h_match = height_pattern.search(full_tag)
        if w_match and int(w_match.group(1)) < MIN_IMAGE_SIZE:
            continue
        if h_match and int(h_match.group(1)) < MIN_IMAGE_SIZE:
            continue

        # Extract alt text
        alt_match = alt_pattern.search(full_tag)
        alt_text = alt_match.group(1) if alt_match else None

        # Get surrounding text for context (100 chars before and after)
        start = max(0, match.start() - 100)
        end = min(len(html_body), match.end() + 100)
        context = re.sub(r'<[^>]+>', ' ', html_body[start:end]).strip()
        context = re.sub(r'\s+', ' ', context)[:200]

        images.append({
            "src": src,
            "alt": alt_text,
            "has_alt": alt_text is not None,
            "alt_empty": alt_text == "" if alt_text is not None else False,
            "context_text": context,
        })

    return images[:MAX_IMAGES]


def download_image(url, headers=None, output_dir=None):
    """Download an image to a local temp file.

    Args:
        url: Image URL
        headers: Optional auth headers (for Canvas-hosted images)
        output_dir: Directory to save to (default: temp dir)

    Returns:
        Local file path, or None on failure.
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="canvas_vision_")

    try:
        resp = requests.get(url, headers=headers or {}, timeout=15, stream=True)
        if resp.status_code != 200:
            return None

        # Determine filename from URL or content-disposition
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path) or "image.png"
        # Sanitize filename
        filename = re.sub(r'[^\w\-.]', '_', filename)

        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        # Check file size — skip if too small (likely a 1x1 pixel)
        if os.path.getsize(filepath) < 100:
            os.unlink(filepath)
            return None

        return filepath

    except requests.exceptions.RequestException:
        return None


def prepare_vision_audit_data(config, page_slug):
    """Fetch a Canvas page, extract images, download them, return audit data.

    Returns:
        List of dicts: {src, local_path, current_alt, has_alt, context_text}
    """
    canvas_api.require_course_id(config)
    page = canvas_api.get_page(config, page_slug)
    if not page:
        return []

    html_body = page.get("body", "")
    base_url = f"https://{config['domain']}/courses/{config['course_id']}/"

    images = extract_image_urls(html_body, base_url)

    # Download each image
    output_dir = tempfile.mkdtemp(prefix=f"canvas_vision_{page_slug}_")
    results = []
    for img in images:
        # Use Canvas auth headers for Canvas-hosted images
        headers = {}
        if config["domain"] in img["src"]:
            headers = config["headers"]

        local_path = download_image(img["src"], headers, output_dir)

        results.append({
            "src": img["src"],
            "local_path": local_path,
            "current_alt": img["alt"],
            "has_alt": img["has_alt"],
            "alt_empty": img["alt_empty"],
            "context_text": img["context_text"],
            "downloaded": local_path is not None,
        })

    return results


def main():
    parser = argparse.ArgumentParser(description="Vision audit data preparation")
    parser.add_argument("--page-slug", help="Canvas page slug to audit")
    parser.add_argument("--html-file", help="Local HTML file to audit")
    parser.add_argument("--output", default="-", help="Output JSON file (default: stdout)")
    parser.add_argument("--mode", choices=["prod", "dev"], help="Canvas instance")
    parser.add_argument("--semantic", action="store_true",
                        help="Add semantic analysis fields for alt text vs image content comparison")
    parser.add_argument("--max-images", type=int, default=None,
                        help="Override max images to process (default: 15)")

    args = parser.parse_args()

    if args.max_images:
        global MAX_IMAGES
        MAX_IMAGES = args.max_images

    if args.page_slug:
        config = canvas_api.get_config(instance=args.mode)
        results = prepare_vision_audit_data(config, args.page_slug)
    elif args.html_file:
        html = open(args.html_file, "r", encoding="utf-8").read()
        images = extract_image_urls(html)
        # Download images without Canvas auth
        output_dir = tempfile.mkdtemp(prefix="canvas_vision_")
        results = []
        for img in images:
            local_path = download_image(img["src"], output_dir=output_dir)
            results.append({
                "src": img["src"],
                "local_path": local_path,
                "current_alt": img["alt"],
                "has_alt": img["has_alt"],
                "alt_empty": img["alt_empty"],
                "context_text": img["context_text"],
                "downloaded": local_path is not None,
            })
    else:
        parser.error("Provide --page-slug or --html-file")
        return

    # Add semantic analysis fields if requested
    if args.semantic:
        for img in results:
            if img["downloaded"] and img["local_path"]:
                img["semantic_analysis"] = {
                    "image_file": img["local_path"],
                    "current_alt": img["current_alt"],
                    "instruction": (
                        "Read this image file. Describe what the image shows in 1-2 sentences. "
                        "Then compare your description to the current alt text. "
                        "Rate the match as: 'good' (alt accurately describes the image), "
                        "'partial' (alt is vaguely correct but missing key details), "
                        "'mismatch' (alt describes something different from the image), "
                        "or 'decorative' (image is decorative/spacer and should have empty alt). "
                        "If the alt text is missing or empty, suggest appropriate alt text."
                    ),
                    "semantic_match": None,  # To be filled by Claude Code
                    "suggested_alt": None,   # To be filled by Claude Code
                }

    output = json.dumps({
        "ok": True,
        "image_count": len(results),
        "downloaded_count": sum(1 for r in results if r["downloaded"]),
        "semantic_mode": args.semantic,
        "images": results,
    }, indent=2)

    if args.output == "-":
        print(output)
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Vision audit data saved to {args.output}")


if __name__ == "__main__":
    main()
