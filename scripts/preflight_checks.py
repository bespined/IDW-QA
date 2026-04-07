#!/usr/bin/env python3
"""Preflight checks — lightweight content-type validation for shift-left quality.

Runs a SUBSET of quality checks against partial data (one page, one assessment,
one module) without requiring the full course. Designed to fire during content
creation and staging, not just during full audits.

Reuses HTML parsers from deterministic_checks.py and Bloom's utilities from
alignment_graph.py.

Usage:
    # As a library (imported by staging_manager, skills, etc.)
    from preflight_checks import check_page, check_module, Issue

    issues = check_page(html, context={"page_type": "overview", "objectives": [...]})

    # As CLI (for testing / manual runs)
    python preflight_checks.py --check-page --html-file staging/m1-overview.html
    python preflight_checks.py --check-module --module 1 --config course-config.json
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

# Logging
try:
    from idw_logger import get_logger
    _log = get_logger("preflight_checks")
except ImportError:
    import logging
    _log = logging.getLogger("preflight_checks")

# Bloom's utilities — import from alignment_graph if available
try:
    from alignment_graph import (
        BLOOMS_VERBS, UNMEASURABLE_VERBS, classify_blooms, is_measurable
    )
except ImportError:
    # Fallback definitions if alignment_graph not available
    BLOOMS_VERBS = {
        "Remember": {"list", "define", "identify", "name", "recall", "recognize", "state", "label", "match", "select"},
        "Understand": {"describe", "explain", "summarize", "paraphrase", "classify", "discuss", "interpret", "compare", "contrast", "distinguish", "articulate"},
        "Apply": {"apply", "demonstrate", "solve", "use", "implement", "execute", "illustrate", "calculate", "practice", "operate"},
        "Analyze": {"analyze", "compare", "contrast", "differentiate", "distinguish", "examine", "categorize", "deconstruct", "investigate", "organize"},
        "Evaluate": {"evaluate", "assess", "critique", "judge", "justify", "defend", "argue", "appraise", "prioritize", "recommend"},
        "Create": {"create", "design", "develop", "compose", "construct", "formulate", "propose", "plan", "produce", "synthesize"},
    }
    UNMEASURABLE_VERBS = {
        "understand", "learn", "know", "be aware", "realize",
        "appreciate", "become familiar", "gain knowledge", "be exposed",
    }

    def classify_blooms(text):
        cleaned = re.sub(r'^(?:CLO-?\d+|MLO-?\d+|M\d+[\.\d]*|[\d]+[\.\d]*)\s*[:\-\s]\s*', '', text.strip(), flags=re.IGNORECASE)
        words = cleaned.split()
        if not words:
            return ("", "Unknown")
        raw_verb = words[0].lower()
        candidates = {raw_verb}
        if raw_verb.endswith('es') and len(raw_verb) > 3:
            candidates.add(raw_verb[:-1])
            candidates.add(raw_verb[:-2] + 'e')
        elif raw_verb.endswith('s') and len(raw_verb) > 3:
            candidates.add(raw_verb[:-1])
        for level, verbs in BLOOMS_VERBS.items():
            for candidate in candidates:
                if candidate in verbs:
                    return (candidate, level)
        return (raw_verb, "Unknown")

    def is_measurable(text):
        cleaned = re.sub(r'^[\d.]+[:\s]*|^[A-Z][\w.-]*[:\s]*', '', text.strip())
        words = cleaned.split()
        if not words:
            return (False, "")
        verb = words[0].lower()
        two_word = " ".join(words[:2]).lower() if len(words) > 1 else ""
        for unmeasurable in UNMEASURABLE_VERBS:
            if verb == unmeasurable or two_word == unmeasurable:
                return (False, unmeasurable)
        return (True, verb)


BLOOMS_RANK = {"Remember": 1, "Understand": 2, "Apply": 3,
               "Analyze": 4, "Evaluate": 5, "Create": 6}


# ── Issue dataclass ────────────────────────────────────────────────────────

@dataclass
class Issue:
    """A quality issue found during preflight checks."""
    criterion_id: str       # Maps to standards.yaml (e.g., "22.1")
    severity: str           # "error" | "warning" | "info"
    message: str            # Human-readable, no jargon
    location: str           # Where in the content (e.g., "line 14", "image 2")
    fixable: bool           # Can IDW auto-fix this?
    fix_hint: Optional[str] = None  # Suggestion if not auto-fixable

    def to_dict(self):
        return asdict(self)


# ── HTML Parsers (reused from deterministic_checks.py pattern) ─────────────

class _HeadingParser(HTMLParser):
    """Extract heading levels and their line positions from HTML."""
    def __init__(self):
        super().__init__()
        self.headings = []  # [(level, line, text)]
        self._in_heading = False
        self._heading_level = 0
        self._heading_text = ""
        self._heading_line = 0

    def handle_starttag(self, tag, attrs):
        if re.match(r"h[1-6]$", tag):
            self._in_heading = True
            self._heading_level = int(tag[1])
            self._heading_text = ""
            self._heading_line = self.getpos()[0]

    def handle_data(self, data):
        if self._in_heading:
            self._heading_text += data

    def handle_endtag(self, tag):
        if self._in_heading and re.match(r"h[1-6]$", tag):
            self._in_heading = False
            self.headings.append((self._heading_level, self._heading_line,
                                  self._heading_text.strip()))


class _ImgParser(HTMLParser):
    """Extract images with alt text, src, and line position."""
    def __init__(self):
        super().__init__()
        self.images = []  # [{"src", "alt", "role", "line"}]

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            d = dict(attrs)
            self.images.append({
                "src": d.get("src", ""),
                "alt": d.get("alt"),
                "role": d.get("role", ""),
                "line": self.getpos()[0],
            })


class _LinkParser(HTMLParser):
    """Extract link text and href with line position."""
    BAD_TEXT = re.compile(
        r"^(click here|here|link|read more|more|https?://|www\.)$", re.I
    )

    def __init__(self):
        super().__init__()
        self.links = []  # [{"text", "href", "line"}]
        self._in_a = False
        self._text = ""
        self._href = ""
        self._line = 0

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._in_a = True
            self._text = ""
            d = dict(attrs)
            self._href = d.get("href", "")
            self._line = self.getpos()[0]

    def handle_data(self, data):
        if self._in_a:
            self._text += data

    def handle_endtag(self, tag):
        if tag == "a" and self._in_a:
            self._in_a = False
            self.links.append({
                "text": self._text.strip(),
                "href": self._href,
                "line": self._line,
            })


class _VideoEmbedParser(HTMLParser):
    """Detect video embeds (iframe, video, embed) and transcript placeholders."""
    def __init__(self):
        super().__init__()
        self.video_embeds = []  # [{"type", "src", "line"}]
        self._full_text = ""

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "iframe":
            src = d.get("src", "")
            if any(host in src.lower() for host in
                   ["youtube", "vimeo", "wistia", "kaltura", "panopto",
                    "instructuremedia", "playposit", "arc.net"]):
                self.video_embeds.append({"type": "iframe", "src": src,
                                          "line": self.getpos()[0]})
        elif tag == "video":
            self.video_embeds.append({"type": "video", "src": d.get("src", ""),
                                      "line": self.getpos()[0]})

    def handle_data(self, data):
        self._full_text += data

    def has_transcript_placeholder(self):
        """Check if the page contains transcript-related text."""
        text_lower = self._full_text.lower()
        return any(kw in text_lower for kw in
                   ["transcript", "caption", "closed caption", "subtitles",
                    "text alternative", "audio description"])


class _TextExtractor(HTMLParser):
    """Extract plain text from HTML."""
    def __init__(self):
        super().__init__()
        self._parts = []

    def handle_data(self, data):
        self._parts.append(data)

    def get_text(self):
        return " ".join(self._parts)


def _strip_html(html):
    if not html:
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(html)
        return parser.get_text()
    except (ValueError, AssertionError):
        return re.sub(r"<[^>]+>", " ", html)


# ── Placeholder detection ─────────────────────────────────────────────────

PLACEHOLDER_PATTERNS = [
    re.compile(r"\[TODO[:\s].*?\]", re.I),
    re.compile(r"\[TBD\]", re.I),
    re.compile(r"\[PLACEHOLDER\]", re.I),
    re.compile(r"\[INSERT\s.*?\]", re.I),
    re.compile(r"\[FACULTY[:\s].*?\]", re.I),
    re.compile(r"\[UPDATE[:\s].*?\]", re.I),
    re.compile(r"\[\s*Instructors?[:\s].*?\]", re.I),      # [Instructors: ...] and [ Instructors: ...]
    re.compile(r"\[\s*Note\s+for\s+Instructors?", re.I),   # [ Note for Instructors: ...] (ASU template)
    re.compile(r"Lorem ipsum", re.I),
    re.compile(r"\[YOUR\s.*?\]", re.I),
    # ASU Canvas template-specific placeholders
    re.compile(r"\[ASU\s+\d+[:\s]", re.I),                 # [ASU 123: Title]
    re.compile(r"\[Title\]", re.I),                         # bare [Title] placeholder
    re.compile(r"\[Learning Materials or Topic\]", re.I),
    re.compile(r"\[Name of Assessment\]", re.I),
    re.compile(r"\[time in hours", re.I),                   # [time in hours/minutes]
    re.compile(r"background-color:\s*#fbeeb8", re.I),       # Yellow highlight = instructor-only placeholder
    re.compile(r"\[specify\s", re.I),                       # [Specify ...]
    re.compile(r"\[add\s.*?\]", re.I),                      # [Add ...]
    re.compile(r"\[LINK\s+TO\]", re.I),                     # [LINK TO ...]
]


def _find_placeholders(text):
    """Find placeholder text patterns. Returns list of (match_text, approx_position)."""
    found = []
    for pat in PLACEHOLDER_PATTERNS:
        for m in pat.finditer(text):
            found.append((m.group(), m.start()))
    return found


# ═══════════════════════════════════════════════════════════════════════════
# CHECK FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def check_page(html: str, context: dict = None) -> list:
    """Run preflight checks on a single page's HTML content.

    Args:
        html: Raw HTML content of the page (not wrapped in Canvas shell)
        context: Optional dict with keys:
            page_type: str — "overview", "lesson", "knowledge-check", etc.
            module_number: int
            objectives: list of objective text strings
            clos: list of CLO text strings
            slug: str — page slug

    Returns:
        List of Issue objects.
    """
    if not html or not html.strip():
        return [Issue("22.1", "warning", "Page has no content.", "entire page",
                       False, "Add content to this page before publishing.")]

    ctx = context or {}
    issues = []

    # ── 1. Heading hierarchy (Standard 22.1) ──────────────────────────────
    hp = _HeadingParser()
    try:
        hp.feed(html)
    except (ValueError, AssertionError):
        pass

    headings = hp.headings
    if headings:
        # Check for H1 in body (Canvas pages shouldn't have H1; Canvas uses it for title)
        h1s = [h for h in headings if h[0] == 1]
        if h1s:
            for level, line, text in h1s:
                issues.append(Issue(
                    "22.1", "warning",
                    f"H1 found in page body — Canvas uses H1 for the page title. Use H2 instead.",
                    f"line {line}: \"{text[:50]}\"",
                    True, "Change <h1> to <h2>."
                ))

        # Check for skipped levels
        for i in range(1, len(headings)):
            prev_level = headings[i - 1][0]
            curr_level = headings[i][0]
            if curr_level > prev_level + 1:
                issues.append(Issue(
                    "22.1", "error",
                    f"Heading level skipped: H{prev_level} jumps to H{curr_level}.",
                    f"line {headings[i][1]}: \"{headings[i][2][:50]}\"",
                    True,
                    f"Change <h{curr_level}> to <h{prev_level + 1}>."
                ))

    # ── 2. Image alt text (Standard 22.2 / FRAME) ────────────────────────
    ip = _ImgParser()
    try:
        ip.feed(html)
    except (ValueError, AssertionError):
        pass

    for idx, img in enumerate(ip.images):
        if img.get("role") == "presentation":
            continue  # Decorative, skip
        if img.get("alt") is None:
            src_short = img.get("src", "?")[:40]
            issues.append(Issue(
                "22.2", "error",
                f"Image missing alt text.",
                f"line {img['line']}: {src_short}",
                False,  # Never auto-generate alt text
                "Add descriptive alt text, or alt=\"\" if decorative."
            ))
        elif img.get("alt") == "":
            # Empty alt = decorative. Fine, but flag if it looks like a content image
            src = img.get("src", "").lower()
            if not any(kw in src for kw in ["icon", "spacer", "bullet", "divider",
                                             "decoration", "background"]):
                issues.append(Issue(
                    "22.2", "info",
                    "Image has empty alt text (marked decorative). Verify this isn't a content image.",
                    f"line {img['line']}: {img.get('src', '?')[:40]}",
                    False, "If this conveys meaning, add descriptive alt text."
                ))

    # ── 3. Link text quality (Standard 22.2) ─────────────────────────────
    lp = _LinkParser()
    try:
        lp.feed(html)
    except (ValueError, AssertionError):
        pass

    for link in lp.links:
        text = link.get("text", "").strip()
        href = link.get("href", "")
        if not text and href:
            issues.append(Issue(
                "22.2", "error",
                "Link has no visible text — inaccessible to screen readers.",
                f"line {link['line']}: href=\"{href[:40]}\"",
                False, "Add descriptive link text."
            ))
        elif text and _LinkParser.BAD_TEXT.match(text):
            issues.append(Issue(
                "22.2", "warning",
                f"Non-descriptive link text: \"{text}\".",
                f"line {link['line']}",
                False,
                "Replace with text describing the link destination."
            ))

    # ── 4. Video transcript/caption placeholder (Standards 16, 18, 22) ────
    vp = _VideoEmbedParser()
    try:
        vp.feed(html)
    except (ValueError, AssertionError):
        pass

    if vp.video_embeds and not vp.has_transcript_placeholder():
        for embed in vp.video_embeds:
            issues.append(Issue(
                "16.2", "warning",
                "Video embed found but no transcript or caption reference on this page.",
                f"line {embed['line']}: {embed['type']} ({embed['src'][:40]})",
                False,
                "Add a transcript section below the video or link to captions."
            ))

    # ── 5. Placeholder text detection ────────────────────────────────────
    plain_text = _strip_html(html)
    placeholders = _find_placeholders(html)  # Search raw HTML to catch attrs too
    placeholders += _find_placeholders(plain_text)

    # Deduplicate by match text
    seen = set()
    for match_text, pos in placeholders:
        if match_text not in seen:
            seen.add(match_text)
            issues.append(Issue(
                "04.5", "error",
                f"Placeholder text found: {match_text}",
                f"near position {pos}",
                False,
                "Replace placeholder with actual content before publishing."
            ))

    # ── 6. Objective measurability (if page_type is overview) ─────────────
    page_type = ctx.get("page_type", "").lower()
    if page_type == "overview" and ctx.get("objectives"):
        for obj_text in ctx["objectives"]:
            measurable, verb = is_measurable(obj_text)
            if not measurable:
                issues.append(Issue(
                    "02.1", "error",
                    f"Objective uses unmeasurable verb \"{verb}\".",
                    f"objective: \"{obj_text[:60]}\"",
                    False,
                    "Replace with a measurable Bloom's verb (e.g., Analyze, Evaluate, Create)."
                ))

    # ── 7. Table accessibility (Standard 22) ─────────────────────────────
    issues.extend(_check_tables(html))

    return issues


def _check_tables(html: str) -> list:
    """Check tables for accessibility: <th> elements, scope attributes."""
    issues_list = []
    # Simple regex check for tables missing <th>
    table_pattern = re.compile(r"<table[^>]*>(.*?)</table>", re.DOTALL | re.I)
    for i, match in enumerate(table_pattern.finditer(html)):
        table_html = match.group(1)
        if "<th" not in table_html.lower():
            issues_list.append(Issue(
                "22.2", "warning",
                f"Table {i + 1} has no header cells (<th>).",
                f"table {i + 1}",
                True,
                "Add <th scope='col'> or <th scope='row'> to header cells."
            ))
        elif 'scope=' not in table_html.lower():
            issues_list.append(Issue(
                "22.2", "info",
                f"Table {i + 1} has headers but no scope attribute.",
                f"table {i + 1}",
                True,
                "Add scope='col' or scope='row' to <th> elements."
            ))
    return issues_list


# ═══════════════════════════════════════════════════════════════════════════
# ASSESSMENT CHECKS
# ═══════════════════════════════════════════════════════════════════════════

def check_assessment(assessment_data: dict, context: dict = None) -> list:
    """Run preflight checks on an assignment/assessment.

    Args:
        assessment_data: dict with keys from Canvas API:
            name, description (HTML), points_possible, submission_types,
            rubric (list of criteria), due_at, has_rubric_association
        context: Optional dict:
            module_number, objectives (list of text), clos, bloom_target (str)

    Returns:
        List of Issue objects.
    """
    ctx = context or {}
    issues = []
    name = assessment_data.get("name", "Untitled")

    # ── Rubric check (Standard 08.3) ─────────────────────────────────────
    has_rubric = (assessment_data.get("rubric") or
                  assessment_data.get("has_rubric_association") or
                  assessment_data.get("has_rubric", False))
    if not has_rubric:
        issues.append(Issue(
            "08.3", "error",
            f"Assignment \"{name}\" has no rubric attached.",
            f"assessment: {name}",
            False,
            "Create and attach a rubric with criteria aligned to objectives."
        ))

    # ── Points set (Standard 09) ─────────────────────────────────────────
    points = assessment_data.get("points_possible")
    if points is None or points == 0:
        issues.append(Issue(
            "09.1", "warning",
            f"Assignment \"{name}\" has no points set.",
            f"assessment: {name}",
            False,
            "Set points_possible to reflect the assessment weight."
        ))

    # ── Due date check (Standard 06.6) ───────────────────────────────────
    if not assessment_data.get("due_at"):
        issues.append(Issue(
            "06.6", "warning",
            f"Assignment \"{name}\" has no due date.",
            f"assessment: {name}",
            False,
            "Set a due date before publishing."
        ))

    # ── Bloom's level check (Standard 11) ────────────────────────────────
    bloom_target = ctx.get("bloom_target")
    if bloom_target and assessment_data.get("description"):
        # Check if the description/prompt suggests the right cognitive level
        desc_text = _strip_html(assessment_data["description"])
        verb, level = classify_blooms(desc_text)
        if level != "Unknown" and bloom_target != "Unknown":
            target_rank = BLOOMS_RANK.get(bloom_target, 0)
            actual_rank = BLOOMS_RANK.get(level, 0)
            if actual_rank < target_rank - 1:
                issues.append(Issue(
                    "11.1", "warning",
                    f"Assignment prompt uses \"{verb}\" ({level}) but module targets {bloom_target}.",
                    f"assessment: {name}",
                    False,
                    f"Consider using verbs at the {bloom_target} level or higher."
                ))

    # ── Description accessibility ────────────────────────────────────────
    desc_html = assessment_data.get("description", "")
    if desc_html:
        page_issues = check_page(desc_html, context=ctx)
        # Re-tag location to include assessment name
        for issue in page_issues:
            issue.location = f"assessment \"{name}\" > {issue.location}"
        issues.extend(page_issues)

    return issues


def check_quiz(quiz_data: dict, context: dict = None) -> list:
    """Run preflight checks on a quiz.

    Args:
        quiz_data: dict with keys from Canvas API:
            title, description, points_possible, allowed_attempts,
            time_limit, shuffle_answers, questions (list)
        context: Optional dict:
            module_number, objectives, bloom_target

    Returns:
        List of Issue objects.
    """
    ctx = context or {}
    issues = []
    title = quiz_data.get("title", "Untitled Quiz")

    # ── Attempt settings (Standard 10) ───────────────────────────────────
    attempts = quiz_data.get("allowed_attempts", -1)
    if attempts == 1:
        issues.append(Issue(
            "10.1", "info",
            f"Quiz \"{title}\" allows only 1 attempt. Consider multiple attempts for formative assessments.",
            f"quiz: {title}",
            False,
            "Set allowed_attempts to 2-3 for knowledge checks."
        ))

    # ── Question feedback check ──────────────────────────────────────────
    questions = quiz_data.get("questions", [])
    missing_feedback = 0
    for i, q in enumerate(questions):
        answers = q.get("answers", [])
        for a in answers:
            if not a.get("comments") and not a.get("comments_html"):
                missing_feedback += 1
                break  # Count once per question

    if missing_feedback > 0 and questions:
        severity = "error" if missing_feedback > len(questions) // 2 else "warning"
        issues.append(Issue(
            "10.2", severity,
            f"{missing_feedback} of {len(questions)} questions missing answer feedback.",
            f"quiz: {title}",
            False,
            "Add feedback explaining why each answer is correct or incorrect."
        ))

    # ── Question variety (Standard 10.1) ─────────────────────────────────
    if questions:
        q_types = set(q.get("question_type", "unknown") for q in questions)
        if len(q_types) == 1 and len(questions) > 3:
            issues.append(Issue(
                "10.1", "info",
                f"All {len(questions)} questions are the same type. Consider mixing question formats.",
                f"quiz: {title}",
                False,
                "Use 2-3 different question types (multiple choice, matching, short answer, etc.)."
            ))

    # ── Due date (Standard 06.6) ─────────────────────────────────────────
    if not quiz_data.get("due_at"):
        issues.append(Issue(
            "06.6", "warning",
            f"Quiz \"{title}\" has no due date.",
            f"quiz: {title}",
            False, "Set a due date before publishing."
        ))

    # ── Bloom's check on questions ───────────────────────────────────────
    bloom_target = ctx.get("bloom_target")
    if bloom_target and questions:
        low_level_count = 0
        for q in questions:
            q_text = q.get("question_text", "") or q.get("question_name", "")
            plain = _strip_html(q_text)
            verb, level = classify_blooms(plain)
            if level in ("Remember", "Understand") and bloom_target in ("Apply", "Analyze", "Evaluate", "Create"):
                low_level_count += 1

        if low_level_count > len(questions) // 2:
            issues.append(Issue(
                "11.4", "warning",
                f"Most questions test lower-order thinking but module targets {bloom_target}.",
                f"quiz: {title}",
                False,
                f"Include scenario-based questions at the {bloom_target} level."
            ))

    return issues


def check_discussion(discussion_data: dict, context: dict = None) -> list:
    """Run preflight checks on a discussion topic.

    Args:
        discussion_data: dict with keys from Canvas API:
            title, message (HTML), assignment (nested), require_initial_post
        context: Optional dict:
            module_number, objectives, bloom_target

    Returns:
        List of Issue objects.
    """
    ctx = context or {}
    issues = []
    title = discussion_data.get("title", "Untitled Discussion")

    # ── Post-first setting (Standard 17) ─────────────────────────────────
    if not discussion_data.get("require_initial_post", False):
        issues.append(Issue(
            "17.1", "warning",
            f"Discussion \"{title}\" doesn't require initial post before viewing replies.",
            f"discussion: {title}",
            False,
            "Enable 'require initial post' so students share original ideas first."
        ))

    # ── Rubric check (graded discussions) ────────────────────────────────
    assignment = discussion_data.get("assignment")
    if assignment:
        has_rubric = (assignment.get("rubric") or
                      assignment.get("has_rubric_association", False))
        if not has_rubric:
            issues.append(Issue(
                "08.3", "error",
                f"Graded discussion \"{title}\" has no rubric.",
                f"discussion: {title}",
                False,
                "Attach a rubric with criteria for initial post quality and peer engagement."
            ))

        # Points check
        points = assignment.get("points_possible")
        if points is None or points == 0:
            issues.append(Issue(
                "09.1", "warning",
                f"Graded discussion \"{title}\" has no points set.",
                f"discussion: {title}",
                False, "Set points_possible."
            ))

    # ── Prompt quality heuristic (Standards 08, 17) ──────────────────────
    message = discussion_data.get("message", "")
    if message:
        plain = _strip_html(message)
        words = plain.split()

        # Too short? Probably placeholder
        if len(words) < 20:
            issues.append(Issue(
                "17.1", "warning",
                f"Discussion prompt is very short ({len(words)} words). May be a placeholder.",
                f"discussion: {title}",
                False,
                "Expand the prompt with scenario context and clear expectations."
            ))

        # Check for recall-only prompt
        recall_signals = ["what is", "what are", "define ", "list the", "name the"]
        plain_lower = plain.lower()
        if any(sig in plain_lower for sig in recall_signals):
            bloom_target = ctx.get("bloom_target", "")
            if bloom_target in ("Apply", "Analyze", "Evaluate", "Create"):
                issues.append(Issue(
                    "11.1", "info",
                    f"Discussion prompt may be recall-level but module targets {bloom_target}.",
                    f"discussion: {title}",
                    False,
                    "Consider rephrasing to require analysis, evaluation, or application."
                ))

    # ── Description accessibility ────────────────────────────────────────
    if message:
        page_issues = check_page(message, context=ctx)
        for issue in page_issues:
            issue.location = f"discussion \"{title}\" > {issue.location}"
        issues.extend(page_issues)

    return issues


# ═══════════════════════════════════════════════════════════════════════════
# MODULE-LEVEL CHECK (ORCHESTRATOR)
# ═══════════════════════════════════════════════════════════════════════════

def check_module(module_data: dict, context: dict = None) -> list:
    """Run preflight checks on an entire module's contents.

    Args:
        module_data: dict with keys:
            name: str — module name
            number: int — module number
            items: list of module items (dicts with type, title, etc.)
            pages: list of page dicts (title, body HTML)
            assignments: list of assignment dicts
            quizzes: list of quiz dicts
            discussions: list of discussion dicts
        context: Optional dict:
            objectives: list of objective texts for this module
            clos: list of CLO texts
            bloom_target: expected Bloom's level for this module

    Returns:
        List of Issue objects.
    """
    ctx = context or {}
    issues = []
    mod_name = module_data.get("name", "Unknown Module")
    mod_num = module_data.get("number", 0)

    # ── Module overview page present (Standard 04.5) ─────────────────────
    pages = module_data.get("pages", [])
    has_overview = any(
        "overview" in (p.get("title", "").lower() or p.get("slug", "").lower())
        for p in pages
    )
    if not has_overview and mod_num > 0:
        issues.append(Issue(
            "04.5", "warning",
            f"Module {mod_num} has no overview page.",
            f"module: {mod_name}",
            False,
            "Add a module overview page with objectives, topics, and time estimates."
        ))

    # ── Objectives listed (Standard 02) ──────────────────────────────────
    objectives = ctx.get("objectives", [])
    if not objectives and mod_num > 0:
        issues.append(Issue(
            "02.1", "warning",
            f"No learning objectives found for Module {mod_num}.",
            f"module: {mod_name}",
            False,
            "Define 2-5 measurable learning objectives in course-config.json."
        ))
    else:
        for obj in objectives:
            measurable, verb = is_measurable(obj)
            if not measurable:
                issues.append(Issue(
                    "02.1", "error",
                    f"Objective uses unmeasurable verb \"{verb}\".",
                    f"module {mod_num} objective: \"{obj[:60]}\"",
                    False,
                    "Replace with a measurable Bloom's verb."
                ))

    # ── Assessment variety (Standard 10.1) ───────────────────────────────
    assignments = module_data.get("assignments", [])
    quizzes = module_data.get("quizzes", [])
    discussions = module_data.get("discussions", [])
    assessment_types = set()
    if assignments:
        assessment_types.add("assignment")
    if quizzes:
        assessment_types.add("quiz")
    if discussions:
        assessment_types.add("discussion")

    if len(assessment_types) < 2 and mod_num > 0:
        issues.append(Issue(
            "10.1", "info",
            f"Module {mod_num} has only {len(assessment_types)} assessment type(s). Consider adding variety.",
            f"module: {mod_name}",
            False,
            "A typical module includes a quiz, a discussion, and an assignment."
        ))

    # ── Run individual checks on each content piece ──────────────────────
    for page in pages:
        page_type = _infer_page_type(page.get("title", ""), page.get("slug", ""))
        page_ctx = {**ctx, "page_type": page_type, "module_number": mod_num}
        body = page.get("body") or page.get("html") or ""
        if body:
            page_issues = check_page(body, context=page_ctx)
            for issue in page_issues:
                issue.location = f"page \"{page.get('title', '?')}\" > {issue.location}"
            issues.extend(page_issues)

    for assignment in assignments:
        a_issues = check_assessment(assignment, context=ctx)
        issues.extend(a_issues)

    for quiz in quizzes:
        q_issues = check_quiz(quiz, context=ctx)
        issues.extend(q_issues)

    for discussion in discussions:
        d_issues = check_discussion(discussion, context=ctx)
        issues.extend(d_issues)

    return issues


def _infer_page_type(title: str, slug: str = "") -> str:
    """Infer the page type from title or slug."""
    combined = (title + " " + slug).lower()
    if "overview" in combined:
        return "overview"
    elif "lesson" in combined or "introduction" in combined:
        return "lesson"
    elif "knowledge" in combined or "quiz" in combined:
        return "knowledge-check"
    elif "practice" in combined:
        return "guided-practice"
    elif "artifact" in combined or "assignment" in combined:
        return "assignment"
    elif "conclusion" in combined or "reflection" in combined:
        return "conclusion"
    elif "discussion" in combined:
        return "discussion"
    elif "prepare" in combined:
        return "prepare-to-learn"
    elif "resource" in combined:
        return "resources"
    return "page"


# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def summarize_issues(issues: list) -> dict:
    """Produce a summary dict from a list of Issues.

    Returns:
        {
            "total": int,
            "errors": int,
            "warnings": int,
            "info": int,
            "fixable": int,
            "by_criterion": {criterion_id: count},
            "issues": [issue.to_dict() for each]
        }
    """
    errors = sum(1 for i in issues if i.severity == "error")
    warnings = sum(1 for i in issues if i.severity == "warning")
    info = sum(1 for i in issues if i.severity == "info")
    fixable = sum(1 for i in issues if i.fixable)

    by_criterion = {}
    for i in issues:
        by_criterion[i.criterion_id] = by_criterion.get(i.criterion_id, 0) + 1

    return {
        "total": len(issues),
        "errors": errors,
        "warnings": warnings,
        "info": info,
        "fixable": fixable,
        "by_criterion": by_criterion,
        "issues": [i.to_dict() for i in issues],
    }


def format_scorecard(module_name: str, issues: list) -> str:
    """Format issues as a compact terminal scorecard.

    Returns a multi-line string for display in conversation.
    """
    summary = summarize_issues(issues)
    lines = []
    lines.append(f"{module_name} — Quick Check")
    lines.append("━" * min(60, len(lines[0]) + 10))

    if not issues:
        lines.append("✅ All checks passed — no issues found.")
        return "\n".join(lines)

    # Group by criterion, show each
    seen_criteria = set()
    for issue in sorted(issues, key=lambda i: (
        {"error": 0, "warning": 1, "info": 2}.get(i.severity, 3),
        i.criterion_id)):

        icon = {"error": "🔴", "warning": "⚠️", "info": "ℹ️"}.get(issue.severity, "?")
        lines.append(f"{icon} {issue.message}")
        if issue.fix_hint:
            lines.append(f"   ↳ {issue.fix_hint}")

    lines.append("━" * min(60, len(lines[0]) + 10))
    parts = []
    if summary["errors"]:
        parts.append(f"{summary['errors']} error(s)")
    if summary["warnings"]:
        parts.append(f"{summary['warnings']} warning(s)")
    if summary["info"]:
        parts.append(f"{summary['info']} info")
    if summary["fixable"]:
        parts.append(f"{summary['fixable']} auto-fixable")
    lines.append(", ".join(parts) if parts else "No issues.")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Preflight quality checks for Canvas content")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check-page", action="store_true",
                       help="Check a single HTML page")
    group.add_argument("--check-module", action="store_true",
                       help="Check a module (requires --module and --config)")

    parser.add_argument("--html-file", help="Path to HTML file to check")
    parser.add_argument("--html-stdin", action="store_true", help="Read HTML from stdin")
    parser.add_argument("--module", type=int, help="Module number for --check-module")
    parser.add_argument("--config", help="Path to course-config.json")
    parser.add_argument("--slug", help="Page slug (for context)")
    parser.add_argument("--page-type", help="Page type override (overview, lesson, etc.)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.check_page:
        if args.html_stdin:
            html = sys.stdin.read()
        elif args.html_file:
            try:
                html = Path(args.html_file).read_text(encoding="utf-8")
            except FileNotFoundError:
                print(json.dumps({"ok": False, "error": f"File not found: {args.html_file}"}))
                sys.exit(1)
        else:
            parser.error("--check-page requires --html-file or --html-stdin")

        # Strip Canvas shell wrapper if present
        raw_start = '<!-- RAW_CONTENT_START -->'
        raw_end = '<!-- RAW_CONTENT_END -->'
        start_idx = html.find(raw_start)
        end_idx = html.find(raw_end)
        if start_idx != -1 and end_idx != -1:
            html = html[start_idx + len(raw_start):end_idx].strip()

        context = {}
        if args.slug:
            context["slug"] = args.slug
            context["page_type"] = args.page_type or _infer_page_type("", args.slug)
        if args.page_type:
            context["page_type"] = args.page_type

        # Load objectives from config if available
        if args.config:
            try:
                cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
                context["clos"] = [c.get("text", "") for c in cfg.get("clos", [])]
            except (json.JSONDecodeError, KeyError, OSError):
                pass

        issues = check_page(html, context=context)
        summary = summarize_issues(issues)

        if args.json:
            print(json.dumps({"ok": True, **summary}, indent=2))
        else:
            print(format_scorecard(args.slug or "Page", issues))

    elif args.check_module:
        if not args.module:
            parser.error("--check-module requires --module")
        if not args.config:
            parser.error("--check-module requires --config")

        try:
            cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"Cannot load config: {e}"}))
            sys.exit(1)

        # Find the module in config
        mod_num = args.module
        mod_config = None
        for m in cfg.get("modules", []):
            if m.get("number") == mod_num:
                mod_config = m
                break

        if not mod_config:
            print(json.dumps({"ok": False, "error": f"Module {mod_num} not found in config"}))
            sys.exit(1)

        # Build context from config
        context = {
            "objectives": [o.get("text", "") for o in mod_config.get("objectives", [])],
            "clos": [c.get("text", "") for c in cfg.get("clos", [])],
            "module_number": mod_num,
        }

        # Build module_data from staged pages
        staging_dir = Path(__file__).resolve().parents[1] / "staging"
        pages = []
        if staging_dir.exists():
            for f in staging_dir.glob(f"m{mod_num}-*.html"):
                if not f.name.startswith("_"):
                    raw_html = f.read_text(encoding="utf-8")
                    # Strip shell wrapper
                    raw_start = '<!-- RAW_CONTENT_START -->'
                    raw_end = '<!-- RAW_CONTENT_END -->'
                    si = raw_html.find(raw_start)
                    ei = raw_html.find(raw_end)
                    if si != -1 and ei != -1:
                        raw_html = raw_html[si + len(raw_start):ei].strip()
                    pages.append({
                        "title": f.stem,
                        "slug": f.stem,
                        "body": raw_html,
                    })

        module_data = {
            "name": mod_config.get("title", f"Module {mod_num}"),
            "number": mod_num,
            "pages": pages,
            "assignments": [],
            "quizzes": [],
            "discussions": [],
        }

        issues = check_module(module_data, context=context)
        summary = summarize_issues(issues)

        if args.json:
            print(json.dumps({"ok": True, **summary}, indent=2))
        else:
            mod_name = f"Module {mod_num}: {mod_config.get('title', '')}"
            print(format_scorecard(mod_name, issues))


if __name__ == "__main__":
    main()
