#!/usr/bin/env python3
"""DEPRECATED — Superseded by criterion_evaluator.py for all audit operations.

This module is kept for backward compatibility and reference. Do not call
directly for new audits. Use criterion_evaluator.py --quick-check or --full-audit
instead, which produces complete audit JSON with guaranteed field names.

Original purpose: Deterministic check engine for IDW audit.
Consumes alignment graph data + Canvas API data (page HTML, assignments, etc.).
Returns per-criterion results for criteria with check_type="deterministic".
Dispatched by criterion_id from standards.yaml.

Architecture: This module is a standalone rule engine, SEPARATE from
alignment_graph.py. The alignment graph is a data structure; this module
consumes it. Many deterministic checks are NOT alignment checks (e.g.,
heading hierarchy, alt text, link text quality).

Usage:
    from deterministic_checks import run_checks, get_deterministic_ids

    # Get list of criterion IDs that have deterministic checks registered
    det_ids = get_deterministic_ids()

    # Run checks for those IDs
    results = run_checks(det_ids, graph, course_data)
    # results = {"01.1": {criterion_id, status, confidence, evidence, ...}, ...}
"""

import math
import re
from html.parser import HTMLParser
from pathlib import Path

# ── Dispatch table ──────────────────────────────────────────────────────────
# Maps criterion_id → check function.
# Each function: (graph: dict, course_data: dict) → result dict

DISPATCH = {}


def register(criterion_id):
    """Decorator to register a check function for a criterion_id."""
    def wrapper(fn):
        DISPATCH[criterion_id] = fn
        return fn
    return wrapper


def get_deterministic_ids():
    """Return list of criterion IDs that have registered check functions."""
    return list(DISPATCH.keys())


def run_checks(criterion_ids, graph, course_data):
    """Run deterministic checks for the given criterion IDs.

    Args:
        criterion_ids: list of criterion_id strings to check
        graph: alignment graph dict (from alignment_graph.py --build --json)
              Keys: clos, mlos, materials, assessments, gaps, coverage
        course_data: dict with keys:
              pages — list of dicts with 'title' and 'body' (HTML string)
              assignments — list of Canvas assignment dicts
              quizzes — list of Canvas quiz dicts
              discussions — list of Canvas discussion dicts
              modules — list of Canvas module dicts
              tabs — list of Canvas tab dicts (for navigation checks)

    Returns:
        dict mapping criterion_id → result dict
    """
    results = {}
    for cid in criterion_ids:
        fn = DISPATCH.get(cid)
        if fn:
            try:
                results[cid] = fn(graph, course_data)
            except Exception as e:
                results[cid] = _result(cid, "Not Auditable", "High",
                                       f"Check failed with error: {e}")
    return results


def _result(criterion_id, status, confidence, evidence, graph_verified=False, details=None):
    """Build a standard result dict."""
    r = {
        "criterion_id": criterion_id,
        "status": status,
        "confidence": confidence,
        "evidence": evidence,
        "graph_verified": graph_verified,
    }
    if details:
        r["details"] = details
    return r


# ============================================================
# STANDARD 01 — Course-Level Alignment
# ============================================================

@register("01.1")
def check_clo_measurability(graph, course_data):
    """All CLOs use measurable action verbs."""
    clos = graph.get("clos", [])
    if not clos:
        return _result("01.1", "Not Auditable", "High",
                        "No CLOs found in course — cannot evaluate measurability.")
    unmeasurable = [c for c in clos if not c.get("is_measurable", True)]
    total = len(clos)
    if not unmeasurable:
        verbs = ", ".join(c.get("measurable_verb", "?") for c in clos)
        return _result("01.1", "Met", "High",
                        f"All {total} CLOs use measurable verbs: {verbs}",
                        graph_verified=True)
    bad = "; ".join(f'"{c.get("text", "")[:60]}..." uses "{c.get("measurable_verb", "?")}"'
                    for c in unmeasurable)
    if len(unmeasurable) < total:
        return _result("01.1", "Partially Met", "High",
                        f"{len(unmeasurable)} of {total} CLOs use unmeasurable verbs: {bad}",
                        graph_verified=True)
    return _result("01.1", "Not Met", "High",
                    f"All {total} CLOs use unmeasurable verbs: {bad}",
                    graph_verified=True)


# ============================================================
# STANDARD 02 — Module-Level Alignment
# ============================================================

@register("02.1")
def check_mlo_measurability(graph, course_data):
    """All MLOs use measurable action verbs."""
    mlos = graph.get("mlos", [])
    if not mlos:
        return _result("02.1", "Not Auditable", "High",
                        "No MLOs found in course.")
    unmeasurable = [m for m in mlos if not m.get("is_measurable", True)]
    total = len(mlos)
    if not unmeasurable:
        return _result("02.1", "Met", "High",
                        f"All {total} MLOs use measurable verbs.",
                        graph_verified=True)
    ratio = len(unmeasurable) / total
    status = "Not Met" if ratio > 0.5 else "Partially Met"
    return _result("02.1", status, "High",
                    f"{len(unmeasurable)} of {total} MLOs use unmeasurable verbs.",
                    graph_verified=True)


@register("02.2")
def check_mlo_clo_mapping(graph, course_data):
    """Every MLO maps to at least one CLO."""
    mlos = graph.get("mlos", [])
    if not mlos:
        return _result("02.2", "Not Auditable", "High", "No MLOs found.")
    unmapped = [m for m in mlos if not m.get("clo_ids")]
    gaps = graph.get("gaps", {}).get("unmapped_mlos", [])
    unmapped_count = len(unmapped) or len(gaps)
    total = len(mlos)
    if unmapped_count == 0:
        return _result("02.2", "Met", "High",
                        f"All {total} MLOs map to at least one CLO.",
                        graph_verified=True)
    if unmapped_count < total:
        return _result("02.2", "Partially Met", "High",
                        f"{unmapped_count} of {total} MLOs have no CLO mapping.",
                        graph_verified=True)
    return _result("02.2", "Not Met", "High",
                    f"No MLOs are mapped to CLOs ({total} unmapped).",
                    graph_verified=True)


# ============================================================
# STANDARD 04 — Consistent Layout
# ============================================================

@register("04.1")
def check_getting_started(graph, course_data):
    """Course includes a 'Getting Started' area."""
    modules = course_data.get("modules", [])
    for mod in modules:
        name = (mod.get("name") or "").lower()
        if any(kw in name for kw in ["getting started", "start here", "module 0",
                                      "welcome", "orientation"]):
            return _result("04.1", "Met", "High",
                            f"Getting Started area found: \"{mod.get('name')}\"")
    return _result("04.1", "Not Met", "High",
                    "No Getting Started / Module 0 / Welcome area found in modules.")


@register("04.2")
def check_syllabus_presence(graph, course_data):
    """Course includes a syllabus."""
    pages = course_data.get("pages", [])
    for p in pages:
        title = (p.get("title") or "").lower()
        if "syllabus" in title:
            return _result("04.2", "Met", "High",
                            f"Syllabus page found: \"{p.get('title')}\"")
    # Also check Canvas tabs for syllabus
    tabs = course_data.get("tabs", [])
    for t in tabs:
        if (t.get("id") or "") == "syllabus" or "syllabus" in (t.get("label") or "").lower():
            return _result("04.2", "Met", "High", "Syllabus tab is enabled.")
    return _result("04.2", "Not Met", "High", "No syllabus page or tab found.")


@register("04.5")
def check_module_overviews(graph, course_data):
    """Course includes module overview pages for each module."""
    modules = course_data.get("modules", [])
    pages = course_data.get("pages", [])
    page_titles = [(p.get("title") or "").lower() for p in pages]
    # Count content modules (skip Module 0 / Getting Started)
    content_modules = [m for m in modules if not any(
        kw in (m.get("name") or "").lower()
        for kw in ["getting started", "start here", "module 0", "welcome", "orientation"]
    )]
    if not content_modules:
        return _result("04.5", "Not Auditable", "High", "No content modules found.")
    has_overview = 0
    for mod in content_modules:
        mod_name = (mod.get("name") or "").lower()
        # Check if any page title suggests an overview for this module
        if any("overview" in t and any(word in t for word in mod_name.split()[:3])
               for t in page_titles):
            has_overview += 1
        # Also check module items for overview pages
        for item in mod.get("items", []):
            if "overview" in (item.get("title") or "").lower():
                has_overview += 1
                break
    total = len(content_modules)
    if has_overview >= total:
        return _result("04.5", "Met", "High",
                        f"Overview pages found for all {total} content modules.")
    if has_overview > 0:
        return _result("04.5", "Partially Met", "High",
                        f"Overview pages found for {has_overview} of {total} content modules.")
    return _result("04.5", "Not Met", "High",
                    f"No module overview pages detected across {total} content modules.")


# ============================================================
# STANDARD 06 — Clear Workload Expectations
# ============================================================

@register("06.3")
def check_uniform_module_structure(graph, course_data):
    """Course includes uniform module structure with predictable pacing."""
    modules = course_data.get("modules", [])
    # Support both IDW course-config format (assessments key) and generic module format (items key)
    content_modules = [m for m in modules if m.get("items") or m.get("assessments")]
    if len(content_modules) < 2:
        return _result("06.3", "Not Auditable", "High", "Fewer than 2 content modules.")
    item_counts = [len(m.get("items") or m.get("assessments", [])) for m in content_modules]
    avg = sum(item_counts) / len(item_counts)
    # Check if module sizes are within 50% of average (uniform)
    outliers = [c for c in item_counts if abs(c - avg) > avg * 0.5]
    if not outliers:
        return _result("06.3", "Met", "High",
                        f"All {len(content_modules)} modules have similar structure "
                        f"({min(item_counts)}-{max(item_counts)} items each).")
    return _result("06.3", "Partially Met", "Medium",
                    f"Module sizes vary significantly: {item_counts}. "
                    f"Average is {avg:.0f} items; {len(outliers)} modules deviate >50%.")


@register("06.6")
def check_due_dates_set(graph, course_data):
    """Due dates are set on graded assignments."""
    # Try top-level assignments list (with points+due_at); fall back to module config assessments
    assignments = course_data.get("assignments", [])
    if not assignments:
        # Extract from course-config modules where points are declared
        for mod in course_data.get("modules", []):
            for a in (mod.get("assessments") or mod.get("items") or []):
                if isinstance(a, dict) and (a.get("points") or 0) > 0:
                    assignments.append({
                        "name": a.get("title", ""),
                        "points_possible": a.get("points", 0),
                        "due_at": a.get("due_date") or a.get("due_at"),
                    })
    graded = [a for a in assignments if (a.get("points_possible") or 0) > 0]
    if not graded:
        return _result("06.6", "Not Auditable", "High",
                       "No graded assignments found in course data — due dates require a live API fetch.")
    missing_due = [a for a in graded if not a.get("due_at")]
    if not missing_due:
        return _result("06.6", "Met", "High",
                        f"All {len(graded)} graded assignments have due dates set.")
    if len(missing_due) < len(graded):
        return _result("06.6", "Partially Met", "High",
                        f"{len(missing_due)} of {len(graded)} graded assignments are missing due dates.",
                        details={"missing": [a.get("name") for a in missing_due]})
    return _result("06.6", "Not Met", "High",
                    f"No graded assignments have due dates set ({len(graded)} total).")


# ============================================================
# STANDARD 08 — Assessments Align with Objectives
# ============================================================

@register("08.1")
def check_assessment_objective_alignment(graph, course_data):
    """Each assessment aligns with at least one objective."""
    assessments = graph.get("assessments", [])
    if not assessments:
        return _result("08.1", "Not Auditable", "High", "No assessments in alignment graph.")
    orphans = graph.get("gaps", {}).get("orphan_assessments", [])
    if not orphans:
        return _result("08.1", "Met", "High",
                        f"All {len(assessments)} assessments map to at least one objective.",
                        graph_verified=True)
    if len(orphans) < len(assessments):
        return _result("08.1", "Partially Met", "High",
                        f"{len(orphans)} of {len(assessments)} assessments have no objective mapping.",
                        graph_verified=True,
                        details={"orphans": orphans})
    return _result("08.1", "Not Met", "High",
                    f"No assessments are mapped to objectives ({len(assessments)} total).",
                    graph_verified=True)


@register("08.3")
def check_rubric_presence(graph, course_data):
    """Graded assignments/discussions have rubrics."""
    assessments = graph.get("assessments", [])
    summative = [a for a in assessments if a.get("type") == "summative"]
    if not summative:
        return _result("08.3", "Not Auditable", "High", "No summative assessments found.")
    missing = [a for a in summative if not a.get("has_rubric")]
    if not missing:
        return _result("08.3", "Met", "High",
                        f"All {len(summative)} summative assessments have rubrics.",
                        graph_verified=True)
    if len(missing) < len(summative):
        names = ", ".join(a.get("title", "?")[:40] for a in missing[:5])
        return _result("08.3", "Partially Met", "High",
                        f"{len(missing)} of {len(summative)} summative assessments lack rubrics: {names}",
                        graph_verified=True)
    return _result("08.3", "Not Met", "High",
                    f"None of the {len(summative)} summative assessments have rubrics.",
                    graph_verified=True)


# ============================================================
# STANDARD 10 — Varied Assessments
# ============================================================

@register("10.1")
def check_assessment_variety(graph, course_data):
    """Course includes at least two different types of assessments."""
    assessments = graph.get("assessments", [])
    if not assessments:
        return _result("10.1", "Not Auditable", "High", "No assessments found.")
    types = set(a.get("canvas_type", "") for a in assessments)
    types.discard("")
    if len(types) >= 2:
        return _result("10.1", "Met", "High",
                        f"Course uses {len(types)} assessment types: {', '.join(sorted(types))}.",
                        graph_verified=True)
    return _result("10.1", "Not Met", "High",
                    f"Course uses only {len(types)} assessment type(s): {', '.join(types) or 'none'}.")


# ============================================================
# STANDARD 11 — Cognitive Skills Development
# ============================================================

@register("11.1")
def check_blooms_in_objectives(graph, course_data):
    """Bloom's Taxonomy levels are evident in module objectives."""
    mlos = graph.get("mlos", [])
    if not mlos:
        return _result("11.1", "Not Auditable", "High", "No MLOs found.")
    with_blooms = [m for m in mlos if m.get("blooms_level")]
    if len(with_blooms) == len(mlos):
        levels = set(m.get("blooms_level") for m in mlos)
        return _result("11.1", "Met", "High",
                        f"All {len(mlos)} MLOs have identifiable Bloom's levels: {sorted(levels)}.",
                        graph_verified=True)
    if with_blooms:
        return _result("11.1", "Partially Met", "Medium",
                        f"{len(with_blooms)} of {len(mlos)} MLOs have identifiable Bloom's levels.")
    return _result("11.1", "Not Met", "Medium",
                    "No MLOs have identifiable Bloom's Taxonomy levels.")


# ============================================================
# STANDARD 12 — Materials Align with Objectives
# ============================================================

@register("12.1")
def check_material_mlo_mapping(graph, course_data):
    """Each material maps to at least one MLO."""
    materials = graph.get("materials", [])
    if not materials:
        return _result("12.1", "Not Auditable", "High", "No materials in alignment graph.")
    orphans = graph.get("gaps", {}).get("orphan_materials", [])
    if not orphans:
        return _result("12.1", "Met", "High",
                        f"All {len(materials)} materials map to at least one MLO.",
                        graph_verified=True)
    ratio = len(orphans) / len(materials)
    status = "Partially Met" if ratio < 0.5 else "Not Met"
    return _result("12.1", status, "High",
                    f"{len(orphans)} of {len(materials)} materials have no MLO mapping.",
                    graph_verified=True)


@register("12.3")
def check_material_variety(graph, course_data):
    """Materials provide multiple formats per module (UDL)."""
    materials = graph.get("materials", [])
    if not materials:
        return _result("12.3", "Not Auditable", "High", "No materials found.")
    # Group by module
    by_module = {}
    for m in materials:
        mod = m.get("module", 0)
        if mod not in by_module:
            by_module[mod] = set()
        by_module[mod].add(m.get("canvas_type", "Page"))
    if not by_module:
        return _result("12.3", "Not Auditable", "High", "Cannot determine module grouping.")
    single_type = [mod for mod, types in by_module.items() if len(types) < 2]
    if not single_type:
        return _result("12.3", "Met", "High",
                        f"All {len(by_module)} modules have varied material types.",
                        graph_verified=True)
    if len(single_type) < len(by_module):
        return _result("12.3", "Partially Met", "Medium",
                        f"{len(single_type)} of {len(by_module)} modules use only one material type.")
    return _result("12.3", "Not Met", "Medium",
                    f"All {len(by_module)} modules use only one material type.")


# ============================================================
# STANDARD 16 — Universally Designed Media
# ============================================================

@register("16.2")
def check_media_format_variety(graph, course_data):
    """At least two different content formats in the course."""
    materials = graph.get("materials", [])
    pages = course_data.get("pages", [])
    formats = set()
    # Check material types from graph
    for m in materials:
        ct = (m.get("canvas_type") or "").lower()
        if ct in ("page", "wiki_page"):
            formats.add("text")
        elif ct in ("file",):
            formats.add("document")
        elif ct in ("externalurl", "external_url"):
            formats.add("external")
    # Check page HTML for video/audio embeds
    for p in pages:
        body = p.get("body") or ""
        if re.search(r"<(video|iframe|embed)", body, re.I):
            formats.add("video")
        if re.search(r"<audio", body, re.I):
            formats.add("audio")
        if re.search(r"class=[\"'][^\"']*interactive|h5p|sortable|draggable", body, re.I):
            formats.add("interactive")
    if len(formats) >= 2:
        return _result("16.2", "Met", "High",
                        f"Course uses {len(formats)} content formats: {', '.join(sorted(formats))}.")
    return _result("16.2", "Not Met", "High",
                    f"Only {len(formats)} format(s) detected: {', '.join(formats) or 'none'}. "
                    "Need at least 2 (text, video, audio, interactive, etc.).")


# ============================================================
# STANDARD 17 — Open Space for Learner Questions
# ============================================================

@register("17.1")
def check_community_forum(graph, course_data):
    """Course has a community/Q&A discussion space."""
    discussions = course_data.get("discussions", [])
    for d in discussions:
        title = (d.get("title") or "").lower()
        if any(kw in title for kw in ["q&a", "question", "community", "forum",
                                       "ask", "help", "lounge", "cafe"]):
            return _result("17.1", "Met", "High",
                            f"Community space found: \"{d.get('title')}\"")
    return _result("17.1", "Not Met", "High",
                    "No community forum / Q&A discussion found.")


# ============================================================
# STANDARD 21 — Technical and Academic Support
# ============================================================

@register("21.1")
def check_support_resources(graph, course_data):
    """IT support, accessibility, and academic resources are provided."""
    pages = course_data.get("pages", [])
    found = []
    for p in pages:
        body = (p.get("body") or "").lower()
        title = (p.get("title") or "").lower()
        if any(kw in title or kw in body for kw in ["support", "resources", "help desk",
                                                      "accessibility", "tutoring", "library"]):
            found.append(p.get("title"))
    if found:
        return _result("21.1", "Met", "High",
                        f"Support resource pages found: {', '.join(found[:3])}.")
    return _result("21.1", "Not Met", "High",
                    "No IT support, accessibility, or academic resource pages found.")


@register("21.2")
def check_support_early(graph, course_data):
    """Support resources are highlighted early in the course."""
    modules = course_data.get("modules", [])
    if not modules:
        return _result("21.2", "Not Auditable", "High", "No modules found.")
    # Check first 2 modules for support-related items
    early_modules = modules[:2]
    for mod in early_modules:
        for item in mod.get("items", []):
            title = (item.get("title") or "").lower()
            if any(kw in title for kw in ["support", "resources", "help", "accessibility"]):
                return _result("21.2", "Met", "High",
                                f"Support resources found early: \"{item.get('title')}\" in {mod.get('name')}.")
    return _result("21.2", "Partially Met", "Medium",
                    "Support resources not found in the first two modules. "
                    "They may exist elsewhere in the course.")


# ============================================================
# STANDARD 22 — Material Accessibility (HTML-based checks)
# ============================================================

class _HeadingParser(HTMLParser):
    """Extract heading levels from HTML."""
    def __init__(self):
        super().__init__()
        self.headings = []

    def handle_starttag(self, tag, attrs):
        if re.match(r"h[1-6]$", tag):
            self.headings.append(int(tag[1]))


class _ImgAltParser(HTMLParser):
    """Extract images and their alt text."""
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            d = dict(attrs)
            self.images.append({
                "src": d.get("src", ""),
                "alt": d.get("alt"),
                "role": d.get("role", ""),
            })


class _LinkTextParser(HTMLParser):
    """Extract link text from HTML."""
    def __init__(self):
        super().__init__()
        self.links = []
        self._in_a = False
        self._text = ""
        self._href = ""

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._in_a = True
            self._text = ""
            self._href = dict(attrs).get("href", "")

    def handle_data(self, data):
        if self._in_a:
            self._text += data

    def handle_endtag(self, tag):
        if tag == "a" and self._in_a:
            self._in_a = False
            self.links.append({"text": self._text.strip(), "href": self._href})


@register("22.1")
def check_heading_hierarchy(graph, course_data):
    """Pages use proper heading hierarchy (no skipped levels)."""
    pages = course_data.get("pages", [])
    if not pages:
        return _result("22.1", "Not Auditable", "High", "No pages to check.")
    violations = []
    for p in pages:
        body = p.get("body") or ""
        if not body:
            continue
        parser = _HeadingParser()
        try:
            parser.feed(body)
        except (ValueError, AssertionError):
            continue
        headings = parser.headings
        for i in range(1, len(headings)):
            if headings[i] > headings[i - 1] + 1:
                violations.append(
                    f"\"{p.get('title', '?')}\": h{headings[i-1]} → h{headings[i]} (skipped level)")
                break  # one violation per page is enough
    if not violations:
        return _result("22.1", "Met", "High",
                        f"All {len(pages)} pages have proper heading hierarchy.")
    if len(violations) <= len(pages) // 3:
        return _result("22.1", "Partially Met", "High",
                        f"Heading hierarchy issues on {len(violations)} page(s): "
                        f"{'; '.join(violations[:3])}")
    return _result("22.1", "Not Met", "High",
                    f"Heading hierarchy issues on {len(violations)} page(s): "
                    f"{'; '.join(violations[:3])}")


def _check_alt_text(graph, course_data):
    """Check all images have alt text (shared logic for 22.1/22.2)."""
    pages = course_data.get("pages", [])
    total_images = 0
    missing_alt = []
    for p in pages:
        body = p.get("body") or ""
        if not body:
            continue
        parser = _ImgAltParser()
        try:
            parser.feed(body)
        except (ValueError, AssertionError):
            continue
        for img in parser.images:
            # Skip decorative images (role="presentation" or alt="")
            if img.get("role") == "presentation":
                continue
            total_images += 1
            if img.get("alt") is None:  # alt="" is acceptable for decorative
                missing_alt.append(f"\"{p.get('title', '?')}\": {img.get('src', '?')[:40]}")
    return total_images, missing_alt


def _check_link_text(graph, course_data):
    """Check links don't use 'click here' or bare URLs as text."""
    pages = course_data.get("pages", [])
    BAD_PATTERNS = re.compile(
        r"^(click here|here|link|read more|more|https?://|www\.)$", re.I
    )
    bad_links = []
    total_links = 0
    for p in pages:
        body = p.get("body") or ""
        if not body:
            continue
        parser = _LinkTextParser()
        try:
            parser.feed(body)
        except (ValueError, AssertionError):
            continue
        for link in parser.links:
            text = link.get("text", "").strip()
            if not text or not link.get("href"):
                continue
            total_links += 1
            if BAD_PATTERNS.match(text):
                bad_links.append(f"\"{p.get('title', '?')}\": \"{text}\"")
    return total_links, bad_links


# Note: 22.1 already handles heading hierarchy above.
# Alt text and link text are sub-checks of 22.2 (FRAME expectations).
# We register them as part of 22.2 since that criterion covers the broad
# accessibility requirements (alt text, captions, transcripts, etc.).


# ============================================================
# TEXT SEARCH HELPERS (used by keyword-based checks below)
# ============================================================

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
    """Return plain text from an HTML string."""
    if not html:
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(html)
        return parser.get_text()
    except (ValueError, AssertionError):
        return re.sub(r"<[^>]+>", " ", html)


def _search_text(text, keywords):
    """Case-insensitive keyword search. Returns (found, excerpt)."""
    text_lower = text.lower()
    for kw in keywords:
        idx = text_lower.find(kw.lower())
        if idx != -1:
            start = max(0, idx - 60)
            end = min(len(text), idx + len(kw) + 60)
            return True, text[start:end].strip()
    return False, ""


def _search_pages(course_data, keywords):
    """Search all page bodies. Returns (found, excerpt, page_title)."""
    for page in course_data.get("pages", []):
        body = _strip_html(page.get("body") or "")
        found, excerpt = _search_text(body, keywords)
        if found:
            return True, excerpt, page.get("title", "Unknown Page")
    return False, "", ""


def _search_syllabus(course_data, keywords):
    """Search the syllabus page for keywords. Returns (found, excerpt)."""
    for page in course_data.get("pages", []):
        if "syllabus" in (page.get("title") or "").lower():
            body = _strip_html(page.get("body") or "")
            found, excerpt = _search_text(body, keywords)
            if found:
                return True, excerpt
    return False, ""


def _search_all(course_data, keywords):
    """Search syllabus, pages, assignments, discussions. Returns (found, excerpt, source)."""
    found, excerpt = _search_syllabus(course_data, keywords)
    if found:
        return True, excerpt, "Syllabus"
    found, excerpt, title = _search_pages(course_data, keywords)
    if found:
        return True, excerpt, f"Page: {title}"
    for a in course_data.get("assignments", []):
        body = _strip_html(a.get("description") or "")
        found, excerpt = _search_text(body, keywords)
        if found:
            return True, excerpt, f"Assignment: {a.get('name', 'Unknown')}"
    for d in course_data.get("discussions", []):
        body = _strip_html(d.get("message") or "")
        found, excerpt = _search_text(body, keywords)
        if found:
            return True, excerpt, f"Discussion: {d.get('title', 'Unknown')}"
    return False, "", ""


def _page_title_match(course_data, keywords):
    """Check if any page title contains a keyword. Returns (found, title)."""
    for page in course_data.get("pages", []):
        title = (page.get("title") or "").lower()
        for kw in keywords:
            if kw.lower() in title:
                return True, page.get("title", "")
    return False, ""


# ============================================================
# STANDARD 04 — Consistent Layout (continued: 04.3, 04.4)
# ============================================================

@register("04.3")
def check_instructor_intro(graph, course_data):
    """Course includes an instructor introduction page with contact info."""
    kw_title = ["instructor", "facilitator", "professor", "about your instructor",
                "meet your instructor", "about me"]
    found, title = _page_title_match(course_data, kw_title)
    if found:
        page = next((p for p in course_data.get("pages", [])
                     if p.get("title") == title), None)
        if page:
            body = _strip_html(page.get("body") or "")
            has_contact, _ = _search_text(body, ["email", "@", "office hour", "contact"])
            if has_contact:
                return _result("04.3", "Met", "High",
                               f"Instructor intro page '{title}' found with contact info.")
            return _result("04.3", "Partially Met", "Medium",
                           f"Instructor page '{title}' found but no contact info detected.")
    return _result("04.3", "Not Met", "High",
                   "No instructor introduction page found.")


@register("04.4")
def check_intro_activity(graph, course_data):
    """Course includes a course introduction activity or discussion for learners."""
    kw = ["introduction", "introductions", "icebreaker", "introduce yourself", "getting to know"]
    for d in course_data.get("discussions", []):
        title = (d.get("title") or "").lower()
        if any(k in title for k in kw):
            return _result("04.4", "Met", "High",
                           f"Introduction discussion found: '{d.get('title')}'")
    for a in course_data.get("assignments", []):
        name = (a.get("name") or "").lower()
        if any(k in name for k in kw):
            return _result("04.4", "Met", "High",
                           f"Introduction activity found: '{a.get('name')}'")
    return _result("04.4", "Not Met", "High",
                   "No introduction activity or discussion for learners found.")


# ============================================================
# STANDARD 06 — Clear Workload Expectations (continued)
# ============================================================

@register("06.1")
def check_workload_pacing(graph, course_data):
    """Course includes workload, pacing, and relevant policy details."""
    kw = ["workload", "pacing", "work ahead", "late policy", "late assignment",
          "deadline", "special circumstance", "time management", "flexibility",
          "make-up", "extension"]
    found, excerpt, source = _search_all(course_data, kw)
    if found:
        return _result("06.1", "Met", "High",
                       f"Workload/pacing info found in {source}: '…{excerpt[:100]}…'")
    return _result("06.1", "Not Met", "High",
                   "No workload, pacing, or deadline policy found in syllabus or pages.")


@register("06.2")
def check_time_commitments(graph, course_data):
    """Course schedules clearly indicate estimated time commitments for activities."""
    kw = ["hours per week", "estimated time", "time commitment", "credit hour",
          "hours of work", "minutes per", "expected hours", "weekly hours",
          "hours per module", "time to complete", "approximately"]
    found, excerpt, source = _search_all(course_data, kw)
    if found:
        return _result("06.2", "Met", "High",
                       f"Time commitment info found in {source}: '…{excerpt[:100]}…'")
    return _result("06.2", "Not Met", "Medium",
                   "No estimated time commitments found in course schedules or syllabus.")


@register("06.5")
def check_high_stakes_early(graph, course_data):
    """High-stakes applied assessments are introduced at the beginning of the course."""
    assignments = course_data.get("assignments", [])
    if not assignments:
        return _result("06.5", "Not Auditable", "High", "No assignments found.")
    total_pts = sum(float(a.get("points_possible") or 0) for a in assignments)
    if total_pts == 0:
        return _result("06.5", "Not Auditable", "Medium",
                       "All assignments have 0 points — cannot assess.")
    high_stakes = [a for a in assignments
                   if float(a.get("points_possible") or 0) / total_pts >= 0.15]
    if not high_stakes:
        return _result("06.5", "Met", "High",
                       "No single assessment exceeds 15% of total grade.")
    modules = course_data.get("modules", [])
    if not modules:
        return _result("06.5", "Not Auditable", "Medium",
                       "Cannot map assessments to modules.")
    late_threshold = max(1, int(len(modules) * 0.7))
    late_high_stakes = []
    for idx, mod in enumerate(modules):
        if idx < late_threshold:
            continue
        item_ids = {str(item.get("content_id", "")) for item in (mod.get("items") or [])}
        for a in high_stakes:
            if str(a.get("id", "")) in item_ids:
                pct = float(a.get("points_possible") or 0) / total_pts * 100
                late_high_stakes.append(
                    f"'{a.get('name', '')}' ({pct:.0f}% of grade) in {mod.get('name', '')}")
    if not late_high_stakes:
        return _result("06.5", "Met", "High",
                       f"{len(high_stakes)} high-stakes assessment(s) not concentrated in final modules.")
    return _result("06.5", "Not Met", "Medium",
                   f"High-stakes assessments concentrated late: {'; '.join(late_high_stakes[:3])}")


# ============================================================
# STANDARD 07 — Instructor Guide
# ============================================================

@register("07.1")
def check_instructor_guide_present(graph, course_data):
    """Course includes an instructor guide with setup and strategy notes."""
    kw = ["instructor guide", "instructor notes", "facilitator guide",
          "teaching guide", "faculty guide", "course setup"]
    found, title = _page_title_match(course_data, kw)
    if found:
        return _result("07.1", "Met", "High", f"Instructor guide found: '{title}'")
    for page in course_data.get("pages", []):
        if not page.get("published", True):
            ptitle = (page.get("title") or "").lower()
            if any(k in ptitle for k in kw):
                return _result("07.1", "Met", "High",
                               f"Instructor guide found (unpublished): '{page.get('title')}'")
    return _result("07.1", "Not Met", "Medium",
                   "No instructor/facilitator guide page found.")


@register("07.2")
def check_instructor_guide_tools(graph, course_data):
    """Instructor guide documents specialized tools and partnerships."""
    kw_guide = ["instructor guide", "facilitator guide", "teaching guide", "faculty guide"]
    found, guide_title = _page_title_match(course_data, kw_guide)
    if not found:
        return _result("07.2", "Not Met", "Medium",
                       "No instructor guide found — cannot verify tool documentation.")
    guide_page = next((p for p in course_data.get("pages", [])
                       if p.get("title") == guide_title), None)
    if guide_page:
        body = _strip_html(guide_page.get("body") or "")
        found_tool, excerpt = _search_text(
            body, ["tool", "software", "platform", "technology",
                   "partnership", "integration", "LTI"])
        if found_tool:
            return _result("07.2", "Met", "High",
                           f"Instructor guide documents tools: '…{excerpt[:100]}…'")
    return _result("07.2", "Partially Met", "Medium",
                   "Instructor guide found but no tool/technology documentation detected.")


# ============================================================
# STANDARD 08 — Assessments Align with Objectives (continued)
# ============================================================

@register("08.2")
def check_assessment_instructions_objectives(graph, course_data):
    """Assessment instructions explicitly state which objectives are evaluated."""
    obj_kw = ["objective", "learning outcome", "CLO", "MLO",
              "course outcome", "module outcome", "by the end", "after completing"]
    assignments = course_data.get("assignments", [])
    if not assignments:
        return _result("08.2", "Not Auditable", "High", "No assignments found.")
    with_obj = sum(1 for a in assignments
                   if _search_text(_strip_html(a.get("description") or ""), obj_kw)[0])
    total = len(assignments)
    if with_obj >= math.ceil(total * 0.8):
        return _result("08.2", "Met", "High",
                       f"{with_obj}/{total} assessments reference objectives in instructions.")
    if with_obj > 0:
        return _result("08.2", "Partially Met", "Medium",
                       f"Only {with_obj}/{total} assessments reference objectives.")
    return _result("08.2", "Not Met", "High",
                   "No assessments explicitly reference learning objectives in instructions.")


# ============================================================
# STANDARD 09 — Clear Grading Criteria
# ============================================================

@register("09.3")
def check_grading_contact(graph, course_data):
    """A method for learners to ask grading questions is provided."""
    kw = ["grading question", "grade appeal", "grade concern",
          "contact me", "contact your instructor", "email me",
          "office hours", "inbox", "academic support", "grading policy"]
    found, excerpt, source = _search_all(course_data, kw)
    if found:
        return _result("09.3", "Met", "High",
                       f"Grading contact method found in {source}: '…{excerpt[:100]}…'")
    return _result("09.3", "Not Met", "Medium",
                   "No method for learners to ask grading questions found.")


@register("09.4")
def check_feedback_timeline(graph, course_data):
    """Estimated timeline for assessment feedback is provided in the course."""
    kw = ["feedback within", "graded within", "turnaround", "feedback by",
          "expect feedback", "business day", "within 48", "within 72",
          "within a week", "grade within", "returned within"]
    found, excerpt, source = _search_all(course_data, kw)
    if found:
        return _result("09.4", "Met", "High",
                       f"Feedback timeline found in {source}: '…{excerpt[:100]}…'")
    return _result("09.4", "Not Met", "Medium",
                   "No estimated feedback timeline found in course.")


# ============================================================
# STANDARD 11 — Cognitive Skills Development (continued)
# ============================================================

_BLOOMS_RANK = {"Remember": 1, "Understand": 2, "Apply": 3,
                "Analyze": 4, "Evaluate": 5, "Create": 6}


@register("11.3")
def check_blooms_progression(graph, course_data):
    """Bloom's Taxonomy levels show progression through the course."""
    mlos = graph.get("mlos", [])
    if not mlos:
        return _result("11.3", "Not Auditable", "High", "No MLOs found in graph.")
    from collections import defaultdict
    by_module = defaultdict(list)
    for mlo in mlos:
        mod = mlo.get("module_id") or mlo.get("module", "unknown")
        level = mlo.get("bloom_level") or mlo.get("blooms_level")
        if level and level in _BLOOMS_RANK:
            by_module[mod].append(_BLOOMS_RANK[level])
    module_max = [(mod, max(lvls)) for mod, lvls in sorted(by_module.items()) if lvls]
    valid = [(mod, lvl) for mod, lvl in module_max if lvl > 0]
    if len(valid) < 2:
        return _result("11.3", "Not Auditable", "Medium",
                       "Insufficient modules with Bloom's-classified MLOs.")
    third = max(1, len(valid) // 3)
    first_avg = sum(lvl for _, lvl in valid[:third]) / third
    last_avg = sum(lvl for _, lvl in valid[-third:]) / third
    summary = "; ".join(f"M{i+1}={lvl}" for i, (_, lvl) in enumerate(valid))
    if last_avg >= first_avg - 0.5:
        return _result("11.3", "Met", "High",
                       f"Bloom's levels show adequate progression: {summary}",
                       graph_verified=True)
    return _result("11.3", "Not Met", "Medium",
                   f"Bloom's levels do not show clear progression "
                   f"(first-third avg={first_avg:.1f}, last-third avg={last_avg:.1f}): {summary}",
                   graph_verified=True)


@register("11.4")
def check_blooms_mix(graph, course_data):
    """Assessments have a mix of lower- and higher-order Bloom's levels."""
    mlos = graph.get("mlos", [])
    if not mlos:
        return _result("11.4", "Not Auditable", "Medium",
                       "No MLO Bloom's level data in graph.")
    levels = [_BLOOMS_RANK[m.get("bloom_level") or m.get("blooms_level")]
              for m in mlos
              if (m.get("bloom_level") or m.get("blooms_level")) in _BLOOMS_RANK]
    if not levels:
        return _result("11.4", "Not Auditable", "Medium",
                       "No Bloom's level data found in MLOs.")
    lower = [l for l in levels if l <= 3]
    higher = [l for l in levels if l > 3]
    if lower and higher:
        return _result("11.4", "Met", "High",
                       f"MLOs span lower-order ({len(lower)}) and higher-order ({len(higher)}) Bloom's levels.",
                       graph_verified=True)
    if lower:
        return _result("11.4", "Not Met", "Medium",
                       f"MLOs only cover lower-order Bloom's levels ({len(lower)} instances). "
                       "No Analyze/Evaluate/Create detected.",
                       graph_verified=True)
    return _result("11.4", "Not Met", "Medium",
                   f"MLOs only cover higher-order Bloom's levels ({len(higher)} instances). "
                   "No Remember/Understand/Apply foundation detected.",
                   graph_verified=True)


# ============================================================
# STANDARD 13 — High-Quality Content
# ============================================================

@register("13.2")
def check_citations_present(graph, course_data):
    """Outside materials are cited with necessary publisher permissions noted."""
    CITATION_RE = re.compile(
        r"(\(\d{4}\)|\bet al\b|https?://doi\.org|Retrieved from|Published by|"
        r"Copyright|©|\bISBN\b|\bDOI:\s*10\.|CC BY|Creative Commons)",
        re.IGNORECASE
    )
    pages = course_data.get("pages", [])
    if not pages:
        return _result("13.2", "Not Auditable", "High", "No pages to check for citations.")
    pages_with_citations = [p.get("title", "Unknown")
                            for p in pages
                            if CITATION_RE.search(_strip_html(p.get("body") or ""))]
    total = len(pages)
    if len(pages_with_citations) >= total * 0.5:
        return _result("13.2", "Met", "High",
                       f"Citation patterns found in {len(pages_with_citations)}/{total} pages.")
    if pages_with_citations:
        return _result("13.2", "Partially Met", "Medium",
                       f"Citations detected in only {len(pages_with_citations)}/{total} pages: "
                       f"{', '.join(pages_with_citations[:3])}")
    return _result("13.2", "Not Met", "Medium",
                   "No citation patterns detected in course pages.")


# ============================================================
# STANDARD 17 — Open Space for Learner Questions (continued)
# ============================================================

@register("17.2")
def check_moderation_policy(graph, course_data):
    """A clear moderation policy for the community space is visible."""
    kw = ["policy", "guidelines", "rules", "expectations", "moderation",
          "netiquette", "code of conduct", "respectful", "professional conduct"]
    for d in course_data.get("discussions", []):
        body = _strip_html(d.get("message") or "")
        found, excerpt = _search_text(body, kw)
        if found:
            return _result("17.2", "Met", "High",
                           f"Moderation policy in discussion '{d.get('title', '')}': '…{excerpt[:80]}…'")
    found, excerpt, source = _search_pages(course_data, kw[:4])
    if found:
        return _result("17.2", "Met", "High",
                       f"Community guidelines found in {source}.")
    return _result("17.2", "Not Met", "Medium",
                   "No moderation policy or community guidelines detected.")


@register("17.3")
def check_private_channels(graph, course_data):
    """Instructions note that personal inquiries should be directed to private channels."""
    kw = ["email me", "private message", "inbox", "direct message",
          "personal inquiry", "personal question", "privately",
          "do not post personal", "send me an email", "contact me directly"]
    found, excerpt, source = _search_all(course_data, kw)
    if found:
        return _result("17.3", "Met", "High",
                       f"Private channel instructions in {source}: '…{excerpt[:80]}…'")
    return _result("17.3", "Not Met", "Medium",
                   "No instructions directing personal inquiries to private channels.")


# ============================================================
# STANDARD 18 — Instructor-Created Media
# ============================================================

_VIDEO_RE = re.compile(
    r'(?:iframe[^>]+(?:playposit|kaltura|youtube|vimeo|mediasite|panopto|brightcove)'
    r'|<video\b|data-mediaid)',
    re.IGNORECASE
)


@register("18.1")
def check_instructor_media_present(graph, course_data):
    """Course contains instructor-created media (videos)."""
    pages = course_data.get("pages", [])
    pages_with_video = [p.get("title", "Unknown")
                        for p in pages if _VIDEO_RE.search(p.get("body") or "")]
    if len(pages_with_video) >= 3:
        return _result("18.1", "Met", "High",
                       f"Video embeds in {len(pages_with_video)} pages: "
                       f"{', '.join(pages_with_video[:3])}…")
    if pages_with_video:
        return _result("18.1", "Partially Met", "Medium",
                       f"Video embeds found in only {len(pages_with_video)} page(s): "
                       f"{', '.join(pages_with_video)}.")
    return _result("18.1", "Not Met", "Medium",
                   "No instructor-created video embeds detected in course pages.")


@register("18.2")
def check_faculty_introduced_early(graph, course_data):
    """All featured faculty are introduced early in the course."""
    kw_title = ["instructor", "facilitator", "professor", "about your instructor",
                "meet your instructor", "about me", "faculty"]
    found, title = _page_title_match(course_data, kw_title)
    if not found:
        return _result("18.2", "Not Met", "Medium",
                       "No instructor/faculty introduction page detected.")
    modules = course_data.get("modules", [])
    if modules:
        for mod in modules[:2]:
            for item in (mod.get("items") or []):
                if title.lower() in (item.get("title") or "").lower():
                    return _result("18.2", "Met", "High",
                                   f"Faculty intro '{title}' in early module '{mod.get('name')}'.")
    return _result("18.2", "Partially Met", "Medium",
                   f"Faculty intro page '{title}' found but not confirmed in first two modules.")


@register("18.5")
def check_slides_with_media(graph, course_data):
    """Slides and relevant learning materials are provided alongside media."""
    PDF_OR_SLIDES_RE = re.compile(
        r'(?:\.pdf|\.pptx?|\.docx?|slides|transcript|handout|notes)',
        re.IGNORECASE
    )
    pages = course_data.get("pages", [])
    pages_with_video = [p for p in pages if _VIDEO_RE.search(p.get("body") or "")]
    if not pages_with_video:
        return _result("18.5", "Not Auditable", "Medium",
                       "No video embeds found — cannot check for companion materials.")
    with_slides = sum(1 for p in pages_with_video
                      if PDF_OR_SLIDES_RE.search(p.get("body") or ""))
    total = len(pages_with_video)
    if with_slides >= math.ceil(total * 0.8):
        return _result("18.5", "Met", "High",
                       f"{with_slides}/{total} video pages also link slides/transcripts.")
    if with_slides > 0:
        return _result("18.5", "Partially Met", "Medium",
                       f"Only {with_slides}/{total} video pages include companion materials.")
    return _result("18.5", "Not Met", "Medium",
                   f"{total} video page(s) found but no linked slides, transcripts, or notes.")


# ============================================================
# STANDARD 20 — Tool Integration
# ============================================================

@register("20.2")
def check_tech_support_docs(graph, course_data):
    """Technical support and guides are provided to learners for tools."""
    kw = ["technical support", "tech support", "troubleshoot", "trouble accessing",
          "having trouble", "help guide", "how to use", "student tutorial",
          "technical help", "tool guide", "getting help", "need help"]
    found, excerpt, source = _search_all(course_data, kw)
    if found:
        return _result("20.2", "Met", "High",
                       f"Technical support docs found in {source}: '…{excerpt[:100]}…'")
    return _result("20.2", "Not Met", "Medium",
                   "No technical support guides or troubleshooting instructions detected.")


# ============================================================
# STANDARD 22 — Material Accessibility (continued: 22.2)
# ============================================================

@register("22.2")
def check_frame_expectations(graph, course_data):
    """Course meets FRAME expectations: alt text on images, accessible documents."""
    total_images, missing_alt = _check_alt_text(graph, course_data)
    if total_images == 0:
        return _result("22.2", "Not Auditable", "Medium",
                       "No images found in pages — cannot assess FRAME alt text expectations.")
    if not missing_alt:
        return _result("22.2", "Met", "High",
                       f"All {total_images} images have alt text. "
                       "PDF accessibility requires manual verification.")
    pct_missing = len(missing_alt) / total_images
    if pct_missing <= 0.2:
        return _result("22.2", "Partially Met", "High",
                       f"{len(missing_alt)}/{total_images} images missing alt text: "
                       f"{'; '.join(missing_alt[:3])}")
    return _result("22.2", "Not Met", "High",
                   f"{len(missing_alt)}/{total_images} images missing alt text: "
                   f"{'; '.join(missing_alt[:3])}")


# ============================================================
# STANDARD 24 — Mobile Optimization
# ============================================================

@register("24.3")
def check_mobile_signals(graph, course_data):
    """Course signals which elements can be accessed on a mobile device."""
    kw = ["mobile", "smartphone", "phone", "tablet", "app", "on the go",
          "mobile-friendly", "access on your phone", "mobile device"]
    found, excerpt, source = _search_all(course_data, kw)
    if found:
        return _result("24.3", "Met", "High",
                       f"Mobile signaling found in {source}: '…{excerpt[:80]}…'")
    return _result("24.3", "Not Met", "Low",
                   "No mobile compatibility signals or guidance found in course content.")


# ============================================================
# STANDARD 25 — Low-Cost Resources
# ============================================================

@register("25.1")
def check_oer_indicators(graph, course_data):
    """There is evidence that OER or low-cost materials were prioritized."""
    kw = ["open educational resource", "OER", "creative commons", "CC BY",
          "openly licensed", "free textbook", "open access", "open textbook",
          "no cost", "zero cost", "free resource"]
    found, excerpt, source = _search_all(course_data, kw)
    if found:
        return _result("25.1", "Met", "High",
                       f"OER/low-cost indicators found in {source}: '…{excerpt[:100]}…'")
    return _result("25.1", "Not Met", "Low",
                   "No OER or open licensing indicators found.")


@register("25.2")
def check_cost_justification(graph, course_data):
    """If items require student cost, they are justified in the syllabus."""
    COST_RE = re.compile(
        r"\$\d+|purchase|buy\b|required textbook|required book|course fee|student cost",
        re.IGNORECASE
    )
    JUSTIFICATION_RE = re.compile(
        r"required for|essential|no alternative|only available|necessary because|"
        r"low.cost alternative|OER not available|could not find",
        re.IGNORECASE
    )
    for page in course_data.get("pages", []):
        if "syllabus" in (page.get("title") or "").lower():
            body = _strip_html(page.get("body") or "")
            if not COST_RE.search(body):
                return _result("25.2", "Met", "High",
                               "No required student costs detected in syllabus.")
            if JUSTIFICATION_RE.search(body):
                return _result("25.2", "Met", "High",
                               "Required costs in syllabus with justification present.")
            return _result("25.2", "Partially Met", "Medium",
                           "Required cost items in syllabus but no cost justification found.")
    return _result("25.2", "Not Auditable", "Medium",
                   "No syllabus page found — cannot check cost justification.")


# ============================================================
# CLI (for standalone testing)
# ============================================================

if __name__ == "__main__":
    print(f"Deterministic checks registered: {len(DISPATCH)}")
    for cid in sorted(DISPATCH.keys()):
        fn = DISPATCH[cid]
        doc = (fn.__doc__ or "").strip().split("\n")[0]
        print(f"  {cid}: {doc}")
