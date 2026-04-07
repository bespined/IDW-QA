#!/usr/bin/env python3
"""WCAG 2.1 AA accessibility audit of Canvas course pages.

Usage:
    python audit_pages.py [--output <report_path>]

Requires environment variables:
    CANVAS_TOKEN, CANVAS_DOMAIN, CANVAS_COURSE_ID

Checks:
    - Images missing alt text
    - Heading hierarchy skips (e.g., h2 → h4)
    - Generic link text ("click here", "here", "link")
    - Low contrast inline colors (WCAG 2.1 AA: 4.5:1 normal, 3:1 large text)
"""

import os
import sys
import re
import time
import argparse
from html.parser import HTMLParser
from collections import defaultdict

# Logging
try:
    from idw_logger import get_logger
    _log = get_logger("audit_pages")
except ImportError:
    import logging
    _log = logging.getLogger("audit_pages")


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from canvas_api import get_config, require_course_id, get_all_pages, get_page


# ============================================================
# WCAG 2.1 CONTRAST RATIO CALCULATION
# ============================================================
def _hex_to_rgb(hex_color):
    """Convert 3- or 6-digit hex color to (r, g, b) tuple (0-255)."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _relative_luminance(r, g, b):
    """Calculate WCAG 2.1 relative luminance from RGB (0-255)."""
    srgb = []
    for c in (r, g, b):
        c_lin = c / 255.0
        srgb.append(c_lin / 12.92 if c_lin <= 0.04045 else ((c_lin + 0.055) / 1.055) ** 2.4)
    return 0.2126 * srgb[0] + 0.7152 * srgb[1] + 0.0722 * srgb[2]


def contrast_ratio(hex_fg, hex_bg="#FFFFFF"):
    """Calculate WCAG contrast ratio between two hex colors.

    Returns contrast ratio (1.0 to 21.0) or None if colors are invalid.
    """
    fg_rgb = _hex_to_rgb(hex_fg)
    bg_rgb = _hex_to_rgb(hex_bg)
    if fg_rgb is None or bg_rgb is None:
        return None
    lum_fg = _relative_luminance(*fg_rgb)
    lum_bg = _relative_luminance(*bg_rgb)
    lighter = max(lum_fg, lum_bg)
    darker = min(lum_fg, lum_bg)
    return (lighter + 0.05) / (darker + 0.05)


# WCAG 2.1 AA thresholds
CONTRAST_NORMAL_TEXT = 4.5  # Normal text (< 18pt or < 14pt bold)
CONTRAST_LARGE_TEXT = 3.0   # Large text (≥ 18pt or ≥ 14pt bold)

# Regex for hex colors in inline styles
_COLOR_RE = re.compile(r'(?:^|;|\s)color\s*:\s*(#[0-9a-fA-F]{3,6})\b')


class AccessibilityAuditor(HTMLParser):
    """HTML parser that checks for common WCAG 2.1 AA accessibility issues."""

    def __init__(self):
        super().__init__()
        self.issues = []
        self.headings = []  # (level, text)
        self.in_a = False
        self.a_text = ""
        self.a_attrs = {}
        self.current_data = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        # Check images for alt text (missing OR empty)
        if tag == "img":
            alt = attrs_dict.get("alt")
            src = attrs_dict.get("src", "unknown")[:80]
            if alt is None:
                self.issues.append(f"IMG missing alt: {src}")
            elif alt.strip() == "":
                # Empty alt is valid for decorative images but flag for review
                self.issues.append(f"IMG empty alt (decorative?): {src}")

        # Track headings
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append((int(tag[1]), ""))
            self.current_data = ""

        # Track links
        if tag == "a":
            self.in_a = True
            self.a_text = ""
            self.a_attrs = attrs_dict

        # Check inline color contrast (WCAG 2.1 AA)
        style = attrs_dict.get("style", "")
        if style:
            match = _COLOR_RE.search(style)
            if match:
                hex_color = match.group(1)
                ratio = contrast_ratio(hex_color)
                if ratio is not None:
                    # Use large-text threshold for headings, normal for everything else
                    threshold = CONTRAST_LARGE_TEXT if tag in ("h1", "h2", "h3") else CONTRAST_NORMAL_TEXT
                    if ratio < threshold:
                        self.issues.append(
                            f"Low contrast {hex_color} on <{tag}> "
                            f"(ratio {ratio:.1f}:1, need {threshold:.1f}:1)"
                        )

    def handle_data(self, data):
        self.current_data += data
        if self.in_a:
            self.a_text += data
        if self.headings and self.headings[-1][1] == "":
            level = self.headings[-1][0]
            self.headings[-1] = (level, data.strip())

    def handle_endtag(self, tag):
        if tag == "a" and self.in_a:
            text = self.a_text.strip().lower()
            if text in ("click here", "here", "link", "read more", "more"):
                href = self.a_attrs.get("href", "")[:60]
                self.issues.append(f"Generic link text '{text}' -> {href}")
            self.in_a = False

        # Check heading hierarchy
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            if len(self.headings) >= 2:
                prev_level = self.headings[-2][0]
                curr_level = self.headings[-1][0]
                if curr_level > prev_level + 1:
                    self.issues.append(
                        f"Heading skip: h{prev_level} -> h{curr_level} "
                        f"('{self.headings[-1][1][:40]}')"
                    )


def audit_course(config, output_path=None):
    """Run WCAG audit on all pages in a Canvas course."""
    require_course_id(config)

    print("Fetching all pages...")
    pages = get_all_pages(config)
    print(f"Found {len(pages)} pages\n")

    if not pages:
        print("\n⚠️  WARNING: No pages found in this course.")
        print("   Possible causes:")
        print("   • Wrong course ID in .env")
        print("   • Course has no published pages")
        print("   • API token lacks read access")
        print("\nAudit cannot run on an empty course. Verify your course connection and retry.")
        sys.exit(1)
    elif len(pages) < 3:
        print(f"⚠️  Only {len(pages)} page(s) found — this may not be the right course.")
        print("   Proceeding with audit, but verify your course ID in .env.\n")

    all_issues = defaultdict(list)
    summary = {"pages": 0, "issues": 0, "pages_with_issues": 0}

    for page_info in sorted(pages, key=lambda p: p["url"]):
        slug = page_info["url"]
        page = get_page(config, slug)
        if not page:
            continue

        body = page.get("body", "") or ""
        if not body.strip():
            continue

        summary["pages"] += 1
        auditor = AccessibilityAuditor()
        try:
            auditor.feed(body)
        except Exception as e:
            print(f"  Parse error on {slug}: {e}")
            continue

        if auditor.issues:
            all_issues[slug] = auditor.issues
            summary["pages_with_issues"] += 1
            summary["issues"] += len(auditor.issues)
            print(f"  {slug}: {len(auditor.issues)} issue(s)")
            for issue in auditor.issues:
                print(f"    - {issue}")

        time.sleep(0.15)

    # Print report
    print(f"\n{'=' * 60}")
    print(f"WCAG 2.1 AA AUDIT REPORT")
    print(f"{'=' * 60}")
    print(f"Pages scanned: {summary['pages']}")
    print(f"Pages with issues: {summary['pages_with_issues']}")
    print(f"Total issues: {summary['issues']}")

    if all_issues:
        print(f"\n--- Issues by type ---")
        type_counts = defaultdict(int)
        for slug, issues in all_issues.items():
            for issue in issues:
                if "IMG missing alt" in issue:
                    type_counts["Missing alt text"] += 1
                elif "IMG empty alt" in issue:
                    type_counts["Empty alt text (review needed)"] += 1
                elif "Heading skip" in issue:
                    type_counts["Heading hierarchy skip"] += 1
                elif "Generic link text" in issue:
                    type_counts["Generic link text"] += 1
                elif "Low contrast" in issue:
                    type_counts["Low contrast color"] += 1
                else:
                    type_counts["Other"] += 1
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")
    else:
        print("\nNo issues found!")

    # Save report
    if output_path:
        with open(output_path, "w") as f:
            f.write(f"WCAG 2.1 AA Audit Report - Canvas Course {config['course_id']}\n")
            f.write(f"Pages: {summary['pages']} | Issues: {summary['issues']}\n\n")
            for slug, issues in sorted(all_issues.items()):
                f.write(f"{slug}:\n")
                for issue in issues:
                    f.write(f"  - {issue}\n")
                f.write("\n")
        print(f"\nReport saved to: {output_path}")

    return summary, all_issues


def _build_txt_report_path():
    """Build a timestamped, course-scoped path for the text audit report."""
    import json
    from pathlib import Path
    from datetime import datetime as _dt
    plugin_root = Path(__file__).resolve().parents[1]
    config_path = plugin_root / "course-config.json"
    course_code, term = "UNKNOWN", "No-Term"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            title = cfg.get("course", {}).get("title", "")
            course_code = cfg.get("course", {}).get("course_code", "")
            term = cfg.get("course", {}).get("term", "")
            if not course_code and title:
                m = re.match(r"([A-Z]{2,4})\s*(\d{3})", title)
                if m:
                    course_code = f"{m.group(1)}-{m.group(2)}"
            course_code = course_code or "UNKNOWN"
            term = term or "No-Term"
        except (json.JSONDecodeError, KeyError, OSError):
            pass
    folder_name = f"{course_code}_{term}".replace(" ", "-")
    timestamp = _dt.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"{course_code}_{term}_{timestamp}_AI-Audit.txt".replace(" ", "-")
    report_dir = plugin_root / "reports" / folder_name
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir / filename


def main():
    parser = argparse.ArgumentParser(
        description="WCAG 2.1 AA accessibility audit of Canvas course pages."
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to save audit report (default: auto-named in reports/)",
    )
    args = parser.parse_args()

    output_path = args.output or str(_build_txt_report_path())
    config = get_config()
    audit_course(config, output_path)
    _log.info(f"Audit text report saved: {output_path}")


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
