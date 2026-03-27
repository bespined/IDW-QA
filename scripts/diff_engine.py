#!/usr/bin/env python3
"""Unified diff and summary engine for Canvas page comparisons.

Ported from Canvas Shadow Editor.

Usage:
    python diff_engine.py --file-a old.html --file-b new.html
    python diff_engine.py --file-a old.html --file-b new.html --summary-only
"""

import argparse
import difflib
import sys

# Logging
try:
    from idw_logger import get_logger
    _log = get_logger("diff_engine")
except ImportError:
    import logging
    _log = logging.getLogger("diff_engine")



def unified_diff(original, updated):
    """Generate a unified diff between two strings."""
    diff_lines = difflib.unified_diff(
        original.splitlines(),
        updated.splitlines(),
        fromfile="original",
        tofile="updated",
        lineterm="",
    )
    return "\n".join(diff_lines)


def diff_summary(original, updated):
    """Generate a +/- summary of changes between two strings."""
    original_lines = original.splitlines()
    updated_lines = updated.splitlines()
    matcher = difflib.SequenceMatcher(a=original_lines, b=updated_lines)
    added = removed = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            added += j2 - j1
        elif tag == "delete":
            removed += i2 - i1
        elif tag == "replace":
            removed += i2 - i1
            added += j2 - j1
    return f"+{added} lines / -{removed} lines"


def main():
    parser = argparse.ArgumentParser(description="Diff engine for Canvas pages")
    parser.add_argument("--file-a", required=True, help="Original file")
    parser.add_argument("--file-b", required=True, help="Updated file")
    parser.add_argument("--summary-only", action="store_true",
                        help="Only print the +/- summary")

    args = parser.parse_args()

    try:
        original = open(args.file_a, "r", encoding="utf-8").read()
        updated = open(args.file_b, "r", encoding="utf-8").read()
    except FileNotFoundError as e:
        _log.error(f"ERROR: {e}")
        sys.exit(1)

    if args.summary_only:
        print(diff_summary(original, updated))
    else:
        print(diff_summary(original, updated))
        print()
        print(unified_diff(original, updated))


if __name__ == "__main__":
    main()
