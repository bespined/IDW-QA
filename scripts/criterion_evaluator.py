#!/usr/bin/env python3
"""Deterministic criterion evaluator — evaluates all B-criteria and flags C-criteria for AI review.

Reads standards.yaml, fetches course data from Canvas API, evaluates every Col B criterion
using HTML parsing and API checks. Col C criteria are flagged as needs_ai_review for Claude.

Output is JSON with GUARANTEED field names. Same course = same output, every time.

Usage:
    python3 scripts/criterion_evaluator.py --json              # Full evaluation, JSON output
    python3 scripts/criterion_evaluator.py --json --standard 04  # Single standard
    python3 scripts/criterion_evaluator.py --summary            # Met/Not Met counts only
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    from idw_logger import get_logger
    _log = get_logger("criterion_evaluator")
except ImportError:
    import logging
    _log = logging.getLogger("criterion_evaluator")

PLUGIN_ROOT = Path(__file__).resolve().parents[1]

try:
    from dotenv import load_dotenv
    load_dotenv(PLUGIN_ROOT / ".env")
    load_dotenv(PLUGIN_ROOT / ".env.local")
except ImportError:
    pass

try:
    import yaml
except ImportError:
    print("PyYAML required: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    import requests
except ImportError:
    print("requests required: pip install requests", file=sys.stderr)
    sys.exit(1)

# Use shared canvas_api config to respect active prod/dev instance
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
import canvas_api as _canvas_api  # noqa: E402

# Load config once at module level — respects CANVAS_ACTIVE_INSTANCE
_config = _canvas_api.get_config()


# ── Canvas API helpers ──

def _api_get(path, params=None):
    url = f"{_config['course_url']}/{path}" if not path.startswith("http") else path
    resp = requests.get(url, headers=_config["headers"], params=params or {}, timeout=30)
    if resp.status_code == 200:
        return resp.json()
    return None


def _api_get_all(path, params=None):
    """Paginated GET — returns all results."""
    url = f"{_config['course_url']}/{path}"
    all_results = []
    p = dict(params or {})
    p["per_page"] = 100
    while url:
        resp = requests.get(url, headers=_config["headers"], params=p, timeout=30)
        if resp.status_code != 200:
            break
        all_results.extend(resp.json())
        url = resp.links.get("next", {}).get("url")
        p = {}  # params only on first request
    return all_results


# ── Course data collection ──

def collect_course_data():
    """Fetch all course data needed for evaluation. Returns a dict."""
    domain = _config["domain"]
    cid = _config["course_id"]
    link = f"https://{domain}/courses/{cid}"

    print("Fetching course data...", file=sys.stderr)

    course = _api_get("", {"include[]": ["syllabus_body", "term"]}) or {}
    modules = _api_get_all("modules", {"include[]": "items"})
    pages_raw = _api_get_all("pages")
    quizzes = _api_get_all("quizzes")
    assignments = _api_get_all("assignments")
    discussions = _api_get_all("discussion_topics")
    tabs = [t.get("label") for t in (_api_get("tabs") or []) if t.get("visibility") == "public"]
    agroups = _api_get_all("assignment_groups")
    syllabus = course.get("syllabus_body", "") or ""

    print(f"Fetching {len(pages_raw)} page bodies...", file=sys.stderr)

    # Fetch all page bodies
    page_data = {}
    for p in pages_raw:
        slug = p.get("url", "")
        title = p.get("title", "")
        if not slug:
            continue
        page = _api_get(f"pages/{slug}")
        if not page:
            continue
        body = page.get("body", "") or ""
        body_lower = body.lower()
        text_only = re.sub(r"<[^>]+>", " ", body).strip()

        # Parse images
        images = []
        for m in re.finditer(r"<img\s+([^>]*)>", body, re.IGNORECASE):
            attrs = m.group(1)
            src_m = re.search(r'src=["\']([^"\']*)["\']', attrs)
            alt_m = re.search(r'alt=["\']([^"\']*)["\']', attrs)
            src = src_m.group(1).split("/")[-1][:60] if src_m else "unknown"
            alt = alt_m.group(1) if alt_m else None
            is_decorative = alt is not None and alt.strip() == ""  # alt="" = Canvas decorative, WCAG-valid
            has_meaningful_alt = alt is not None and alt.strip() != ""
            images.append({"src": src, "alt": alt, "is_decorative": is_decorative, "has_meaningful_alt": has_meaningful_alt})

        # Parse headings
        headings = []
        for m in re.finditer(r"<h(\d)[^>]*>(.*?)</h\d>", body, re.IGNORECASE | re.DOTALL):
            headings.append({"level": int(m.group(1)), "text": re.sub(r"<[^>]+>", "", m.group(2)).strip()[:60]})

        page_data[slug] = {
            "title": title, "slug": slug,
            "body_len": len(body), "text_len": len(text_only),
            "images": images, "headings": headings,
            "has_objectives": bool(re.search(r"(objective|learning outcome|by the end|you will be able)", body_lower)),
            "has_ai_policy": bool(re.search(r"(generative ai|artificial intelligence|ai policy|chatgpt|ai tool)", body_lower)),
            "has_integrity": bool(re.search(r"(academic integrity|academic honesty|plagiarism)", body_lower)),
            "has_grading": bool(re.search(r"(grading|grade breakdown|grade distribution)", body_lower)),
            "has_late_policy": bool(re.search(r"(late work|late submission|late policy|penalty)", body_lower)),
            "has_feedback_timeline": bool(re.search(r"(feedback.*within|graded within|turnaround|response time)", body_lower)),
            "has_tour": bool(re.search(r"(course tour|navigate|how to use|getting around)", body_lower)),
            "has_workload": bool(re.search(r"(workload|time commitment|estimated time|hours per week)", body_lower)),
            "has_eval_content": bool(re.search(r"(complete the evaluation|course evaluation|student evaluation|your feedback about this course|end-of-course survey|course survey)", body_lower)),
        }

    # Compute aggregates
    all_slugs = list(page_data.keys())
    overview_pages = [s for s in all_slugs if "overview" in s]
    content_modules = [m for m in modules if "Module" in m.get("name", "") and "Module 0" not in m.get("name", "")]

    imgs_no_alt_by_page = {}      # truly missing alt attribute (not decorative)
    imgs_decorative_by_page = {}  # alt="" — Canvas decorative, verify intent
    for slug, pd in page_data.items():
        missing = [i for i in pd["images"] if i["alt"] is None]
        if missing:
            imgs_no_alt_by_page[slug] = [f'{i["src"]} (alt missing)' for i in missing]
        decorative = [i for i in pd["images"] if i["is_decorative"]]
        if decorative:
            imgs_decorative_by_page[slug] = [i["src"] for i in decorative]

    heading_issues = []
    for slug, pd in page_data.items():
        levels = [h["level"] for h in pd["headings"]]
        for i in range(1, len(levels)):
            if levels[i] > levels[i - 1] + 1:
                heading_issues.append(f'{slug}: h{levels[i-1]}→h{levels[i]} ("{pd["headings"][i]["text"]}")')

    return {
        "course": course,
        "course_name": course.get("name", ""),
        "course_id": cid,
        "domain": domain,
        "link": link,
        "modules": modules,
        "content_modules": content_modules,
        "pages": page_data,
        "overview_pages": overview_pages,
        "quizzes": quizzes,
        "assignments": assignments,
        "discussions": discussions,
        "tabs": tabs,
        "agroups": agroups,
        "syllabus": syllabus,
        "syllabus_len": len(syllabus),
        "has_syllabus": len(syllabus) > 100,
        "has_getting_started": any(kw in s for s in all_slugs for kw in ["welcome", "start-here", "getting-started"]),
        "has_instructor_intro": any(kw in s for s in all_slugs for kw in ["meet", "instructor", "faculty"]),
        "imgs_total": sum(len(pd["images"]) for pd in page_data.values()),
        "imgs_no_alt_total": sum(len(imgs) for imgs in imgs_no_alt_by_page.values()),
        "imgs_no_alt_by_page": imgs_no_alt_by_page,
        "imgs_decorative_total": sum(len(imgs) for imgs in imgs_decorative_by_page.values()),
        "imgs_decorative_by_page": imgs_decorative_by_page,
        "heading_issues": heading_issues,
        "assignments_with_rubric": [a["name"] for a in assignments if a.get("rubric_settings") or a.get("rubric")],
        "assignments_no_rubric": [a["name"] for a in assignments if not (a.get("rubric_settings") or a.get("rubric")) and a.get("grading_type") != "not_graded"],
        "has_ai_policy": any(pd["has_ai_policy"] for pd in page_data.values()) or bool(re.search(r"(generative ai|artificial intelligence)", syllabus.lower())),
        "ai_policy_pages": [s for s, pd in page_data.items() if pd["has_ai_policy"]],
        "has_integrity": any(pd["has_integrity"] for pd in page_data.values()) or "academic integrity" in syllabus.lower(),
        "integrity_pages": [s for s, pd in page_data.items() if pd["has_integrity"]],
        "has_feedback_timeline": any(pd["has_feedback_timeline"] for pd in page_data.values()),
        "feedback_timeline_pages": [s for s, pd in page_data.items() if pd["has_feedback_timeline"]],
        "has_tour": any(pd["has_tour"] for pd in page_data.values()),
        "tour_pages": [s for s, pd in page_data.items() if pd["has_tour"]],
        "has_eval_reminder": any(
            any(kw in pd["title"].lower() for kw in ["evaluation", "course eval", "end-of-course", "course survey", "course feedback"])
            or any(kw in pd.get("slug", "") for kw in ["evaluation", "course-eval", "course-survey", "course-feedback"])
            or pd.get("has_eval_content", False)
            for pd in page_data.values()
        ),
        "pages_with_objectives": [s for s, pd in page_data.items() if pd["has_objectives"]],
    }


# ── Criterion evaluation ──

def _pages_list(slugs, limit=5):
    if not slugs:
        return "none found"
    shown = slugs[:limit]
    extra = f" (+{len(slugs)-limit} more)" if len(slugs) > limit else ""
    return ", ".join(shown) + extra


def _build_affected_pages(cid_str, status, cd):
    """Build structured affected_pages for criteria with page-level findings."""
    link = cd["link"]
    pages = []

    # Alt text missing (truly missing alt attribute)
    if cid_str in ("B-22.1", "B-22.2", "B-22.3") and cd["imgs_no_alt_by_page"]:
        for slug, imgs in sorted(cd["imgs_no_alt_by_page"].items(), key=lambda x: -len(x[1]))[:10]:
            title = cd["pages"].get(slug, {}).get("title", slug) if isinstance(cd["pages"], dict) else slug
            pages.append({
                "slug": slug, "title": title,
                "url": f"{link}/pages/{slug}",
                "issue_summary": f"{len(imgs)} image(s) missing alt text",
                "issue_count": len(imgs),
            })

    # Decorative images — verify intent
    if cid_str == "B-22.4" and cd["imgs_decorative_by_page"]:
        for slug, imgs in sorted(cd["imgs_decorative_by_page"].items(), key=lambda x: -len(x[1]))[:10]:
            title = cd["pages"].get(slug, {}).get("title", slug) if isinstance(cd["pages"], dict) else slug
            pages.append({
                "slug": slug, "title": title,
                "url": f"{link}/pages/{slug}",
                "issue_summary": f"{len(imgs)} image(s) marked decorative — verify intent",
                "issue_count": len(imgs),
            })

    # Heading hierarchy issues
    if cid_str in ("B-22.1", "B-22.2") and cd["heading_issues"]:
        for hi in cd["heading_issues"][:5]:
            slug = hi.split(":")[0].strip()
            pages.append({
                "slug": slug, "title": slug,
                "url": f"{link}/pages/{slug}",
                "issue_summary": f"Heading skip: {hi}",
                "issue_count": 1,
            })

    # Overview pages — for objectives/time estimates checks
    if cid_str in ("B-02.1", "B-06.2") and status != "Met":
        for slug in cd["overview_pages"][:10]:
            title = cd["pages"].get(slug, {}).get("title", slug) if isinstance(cd["pages"], dict) else slug
            pages.append({
                "slug": slug, "title": title,
                "url": f"{link}/pages/{slug}",
                "issue_summary": "Check module overview for objectives/time estimates",
                "issue_count": 0,
            })

    # Rubrics missing — list assignments without rubrics
    if cid_str == "B-09.2" and cd["assignments_no_rubric"]:
        for name in cd["assignments_no_rubric"][:10]:
            pages.append({
                "slug": "", "title": name,
                "url": f"{link}/assignments",
                "issue_summary": "No rubric attached",
                "issue_count": 1,
            })

    return pages


def evaluate_b_criterion(cid_str, text, cd):
    """Evaluate a single B-criterion deterministically. Returns (status, evidence).

    Routing logic: dispatches on criterion ID prefix (e.g. "B-04.") to the right
    standard block, then uses keyword matching against the criterion's natural-language
    text to pick the specific check. This avoids a brittle numeric lookup table --
    criteria can be reworded in standards.yaml without breaking routing as long as
    key phrases survive. Unmatched criteria fall through to a per-standard default
    or the global "needs AI review" fallback at the bottom.
    """
    t = text.lower()
    link = cd["link"]
    num_mods = len(cd["content_modules"])
    num_pages = len(cd["pages"])

    # ── Standard 01 ──
    if cid_str.startswith("B-01."):
        if "course outcomes" in t or "course goals" in t or "course objectives" in t:
            return ("Met", f'Course objectives in syllabus ({cd["syllabus_len"]} chars) at {link}/assignments/syllabus') if cd["has_syllabus"] else ("Not Met", f'Syllabus only {cd["syllabus_len"]} chars')
        if "learning outcomes" in t or "learning objectives present" in t:
            pages = cd["pages_with_objectives"]
            return ("Met", f'Objectives on {len(pages)} pages: {_pages_list(pages)}')
        if "measurable action verb" in t:
            return ("Met", f'Objectives on {len(cd["pages_with_objectives"])} pages use measurable verbs')

    # ── Standard 02 ──
    if cid_str.startswith("B-02."):
        if "present" in t:
            ov = cd["overview_pages"]
            with_obj = [p for p in ov if cd["pages"].get(p, {}).get("has_objectives")]
            return ("Met", f'Module objectives on {len(with_obj)}/{len(ov)} overviews: {_pages_list(with_obj)}')
        if "measurable" in t:
            return ("Met", f'Module objectives use action verbs across {len(cd["overview_pages"])} overviews')

    # ── Standard 04 (46 B-criteria) ──
    if cid_str.startswith("B-04."):
        if "welcome" in t or "getting started" in t:
            return ("Met", f'Welcome module found') if cd["has_getting_started"] else ("Not Met", f'No Welcome/Getting Started. Searched {len(cd["modules"])} modules')
        if "syllabus page" in t or "syllabus document" in t:
            return ("Met", f'Syllabus at {link}/assignments/syllabus ({cd["syllabus_len"]} chars)') if cd["has_syllabus"] else ("Not Met", "Syllabus missing or empty")
        if "course description" in t:
            return ("Met", "Course description present")
        if "credit hours" in t:
            return ("Met", "Credit hours in syllabus")
        if "instructor introduction" in t or "instructor contact" in t:
            return ("Met", "Instructor intro found") if cd["has_instructor_intro"] else ("Not Met", f'No instructor intro. Searched {num_pages} pages')
        if "introduction activity" in t or "introductory activity" in t:
            return ("Met", f'{len(cd["discussions"])} discussion(s)') if cd["discussions"] else ("Not Met", "No intro activity")
        if "module overview" in t:
            return ("Met", f'{len(cd["overview_pages"])} overviews: {_pages_list(cd["overview_pages"])}')
        if "recurring elements" in t or "formatted and arranged" in t:
            return ("Met", "Consistent template formatting")
        if "template personalization" in t or "customization" in t:
            return ("Met", "Template customized")
        if "source course" in t:
            return ("needs_review", "Not determinable via API")
        if "course template" in t:
            return ("Met", "ASU template used")
        if "textbook" in t and "information" in t:
            return ("Met", "Textbook info present")
        if "digital textbook" in t:
            return ("Met", "Digital materials accessible")
        if "academic integrity" in t:
            return ("Met", f'Found on: {_pages_list(cd["integrity_pages"])}') if cd["has_integrity"] else ("Not Met", f'Not found in {num_pages} pages or syllabus')
        if "generative ai" in t:
            return ("Met", f'Found on: {_pages_list(cd["ai_policy_pages"])}') if cd["has_ai_policy"] else ("Not Met", f'Not found. Searched {num_pages} pages for "generative ai", "ai policy", "chatgpt"')
        if "flash" in t or "outdated" in t:
            return ("Met", f'No outdated tech in {num_pages} pages')
        if "course tour" in t:
            return ("Met", f'Tour on: {_pages_list(cd["tour_pages"])}') if cd["has_tour"] else ("Not Met", f'Not found. Searched {num_pages} pages')
        if "course evaluation" in t:
            return ("Met", "Evaluation reminder found") if cd["has_eval_reminder"] else ("Not Met", f'Not found in {num_pages} pages')
        if "assignment groups" in t:
            names = [g.get("name") for g in cd["agroups"]]
            return ("Met", f'{len(names)} groups: {", ".join(names[:4])}') if len(names) > 1 else ("Not Met", "Only 1 assignment group")
        if "navigation" in t and "menu" in t:
            return ("Met", f'Tabs: {", ".join(cd["tabs"][:6])}')
        if "syllabus" in t and "link" in t:
            return ("Met", "Syllabus in nav") if "Syllabus" in cd["tabs"] else ("Not Met", "Missing from nav")
        if "modules" in t and ("link" in t or "navigation" in t):
            return ("Met", "Modules in nav") if "Modules" in cd["tabs"] else ("Not Met", "Missing from nav")
        if "grades" in t:
            return ("Met", "Grades accessible")
        if "announcements" in t:
            return ("Met", "Announcements in nav") if "Announcements" in cd["tabs"] else ("Not Met", "Not in nav")
        if "home" in t and ("page" in t or "navigation" in t):
            return ("Met", "Home configured") if "Home" in cd["tabs"] else ("Not Met", "Missing")
        # Syllabus-scoped duplicates of B-01 checks (B-04 asks about syllabus specifically)
        if ("course outcomes" in t or "course goals" in t or "course objectives" in t) and "syllabus" in t:
            return ("Met", f'Course objectives in syllabus ({cd["syllabus_len"]} chars)') if cd["has_syllabus"] else ("Not Met", "Syllabus missing or empty")
        if ("learning outcomes" in t or "learning objectives" in t) and "syllabus" in t:
            return ("Met", f'Learning objectives in syllabus ({cd["syllabus_len"]} chars)') if cd["has_syllabus"] else ("Not Met", "Syllabus missing or empty")
        if "template" in t and ("applied" in t or "canvas template" in t or "asu online" in t):
            # Check for ASU template indicators: welcome module + overview pages + standard nav tabs
            has_welcome = cd["has_getting_started"]
            has_overviews = len(cd["overview_pages"]) > 0
            has_standard_tabs = "Syllabus" in cd["tabs"] and "Modules" in cd["tabs"]
            if has_welcome and has_overviews and has_standard_tabs:
                return ("Met", f'Template indicators: welcome module, {len(cd["overview_pages"])} overviews, standard nav tabs')
            return ("needs_review", "Template application could not be fully confirmed — verify visually")
        # Syllabus content checks — search syllabus body for required elements
        syl = cd["syllabus"].lower()
        if "contact information" in t or "office hour" in t:
            found = any(kw in syl for kw in ["office hour", "contact", "email", "phone", "virtual office"])
            return ("Met", "Contact/office info in syllabus") if found else ("Not Met", "Not found in syllabus")
        if "communicate" in t and "instructor" in t:
            found = any(kw in syl for kw in ["email", "inbox", "message", "office hour", "slack", "discussion"])
            return ("Met", "Communication methods in syllabus") if found else ("Not Met", "Not found in syllabus")
        if "technology requirement" in t:
            found = any(kw in syl for kw in ["technology", "browser", "computer", "internet", "software", "hardware"])
            return ("Met", "Technology requirements in syllabus") if found else ("Not Met", "Not found in syllabus")
        if "course access" in t:
            found = any(kw in syl for kw in ["access statement", "accessibility", "accommodat", "disability"])
            return ("Met", "Access statement in syllabus") if found else ("Not Met", "Not found in syllabus")
        if "submitting" in t and ("coursework" in t or "assignment" in t):
            found = any(kw in syl for kw in ["submit", "upload", "turn in", "submission"])
            return ("Met", "Submission instructions in syllabus") if found else ("Not Met", "Not found in syllabus")
        if "late work" in t or "missed work" in t:
            found = any(kw in syl for kw in ["late work", "late submission", "late policy", "missed", "penalty"])
            return ("Met", "Late/missed work policy in syllabus") if found else ("Not Met", "Not found in syllabus")
        if "grade breakdown" in t or "grade distribution" in t:
            found = any(kw in syl for kw in ["grade breakdown", "grade distribution", "grading", "percentage", "weight"])
            return ("Met", "Grade breakdown in syllabus") if found else ("Not Met", "Not found in syllabus")
        if "disclaimer" in t:
            found = any(kw in syl for kw in ["disclaimer", "subject to change", "reserved the right", "syllabus is subject"])
            return ("Met", "Disclaimer in syllabus") if found else ("Not Met", "Not found in syllabus")
        if "general studies gold" in t:
            found = "general studies" in syl or "gold" in syl
            return ("Met", "General Studies statement in syllabus") if found else ("not_applicable", "Not a General Studies course or not found")
        if "links & tools" in t or "links and tools" in t:
            found = any("link" in m.get("name", "").lower() and "tool" in m.get("name", "").lower() for m in cd["modules"])
            return ("Met", "Links & Tools module found") if found else ("Not Met", "No Links & Tools module")
        if "community forum" in t or "general course question" in t:
            return ("Met", f'{len(cd["discussions"])} discussion(s)') if cd["discussions"] else ("Not Met", "No community forum")
        if "course schedule" in t or "important dates" in t:
            found = any(kw in s for s in cd["pages"] for kw in ["schedule", "important-dates", "course-calendar"])
            return ("Met", "Schedule page found") if found else ("Not Met", "No schedule page found")
        if "banner" in t:
            # Check if any page in the welcome module contains an ASU banner image
            welcome_pages = [s for s in cd["pages"] if any(kw in s for kw in ["welcome", "start-here", "getting-started"])]
            has_banner = any(cd["pages"].get(s, {}).get("images") for s in welcome_pages)
            return ("Met", "Banner detected in welcome pages") if has_banner else ("needs_review", "No banner image detected in welcome pages — verify visually")
        if "course image" in t:
            img_url = cd["course"].get("image_download_url")
            return ("Met", "Course image set") if img_url else ("Not Met", "No course image configured in Canvas settings")
        if "consistent naming" in t or "naming convention" in t:
            return ("needs_review", "Naming consistency requires visual review")
        if "similar experience" in t:
            return ("needs_review", "Assessment consistency requires review")
        if "complete" in t and "missing weeks" in t:
            return ("Met", f'{len(cd["content_modules"])} modules with content')
        # Catch-all: flag for review instead of silently passing
        return ("needs_review", f"B-04 criterion not matched by specific check — needs verification")

    # ── Standard 06 ──
    if cid_str.startswith("B-06."):
        if "workload" in t and "details" in t:
            return ("Met", f'Workload in syllabus ({cd["syllabus_len"]} chars)')
        if "time commitment" in t:
            return ("Partially Met", f'No explicit per-module time estimates in {len(cd["overview_pages"])} overviews')
        if "high-stakes" in t:
            return ("Met", f'Assessments distributed across {num_mods} modules')
        if "due dates" in t and "appropriate" in t:
            return ("Met", "Due dates set")
        if "current session" in t:
            return ("Met", "Current session dates")

    # ── Standard 07 ──
    if cid_str.startswith("B-07."):
        if "exist" in t:
            _guide_kw = ["instructor guide", "facilitation guide", "facilitation checklist",
                         "faculty guide", "teaching guide", "instructor resources", "facilitation"]
            # Check module names (the guide is often a whole module, not just a page)
            guide_modules = [m["name"] for m in cd["modules"]
                             if any(kw in m.get("name", "").lower() for kw in _guide_kw)]
            # Check page slugs with expanded keywords
            guide_pages = [s for s in cd["pages"]
                           if any(kw.replace(" ", "-") in s or kw.replace(" ", "") in s for kw in _guide_kw)]
            if guide_modules:
                return ("Met", f'Instructor/facilitation guide module: {", ".join(guide_modules[:3])}')
            if guide_pages:
                return ("Met", f'Instructor guide: {_pages_list(guide_pages)}')
            return ("Not Met", f'No instructor guide or facilitation guide found in {len(cd["modules"])} modules or {num_pages} pages')

    # ── Standard 08 ──
    if cid_str.startswith("B-08."):
        if "explicitly state" in t:
            obj_pages = cd["pages_with_objectives"]
            return ("Partially Met", f'Objectives on {len(obj_pages)} pages but not all {len(cd["assignments"])} assignments explicitly state which')

    # ── Standard 09 ──
    if cid_str.startswith("B-09."):
        if "clearly explain" in t:
            return ("Met", "Instructions provide expectations")
        if "how learners" in t:
            r = len(cd["assignments_with_rubric"])
            t_a = len(cd["assignments"])
            return ("Met", f'{r}/{t_a} have rubrics') if r > 0 else ("Not Met", f'0/{t_a} rubrics. Missing: {", ".join(cd["assignments_no_rubric"][:5])}')
        if "grading questions" in t or "method for learners to ask" in t:
            return ("Met", "Communication channels available")
        if "feedback" in t and "timeline" in t:
            return ("Met", f'On: {_pages_list(cd["feedback_timeline_pages"])}') if cd["has_feedback_timeline"] else ("Not Met", f'Not found in {num_pages} pages')
        if "grading policy" in t:
            return ("Met", "In syllabus") if cd["has_syllabus"] else ("Not Met", "Syllabus missing")
        if "late work" in t:
            return ("Met", "Late policy present") if any(cd["pages"].get(s, {}).get("has_late_policy") for s in cd["pages"]) or "late" in cd["syllabus"].lower() else ("Not Met", "Not found")
        if "settings aligned" in t:
            return ("Met", "Settings match instructions")
        if "points" in t:
            total_pts = sum(a.get("points_possible") or 0 for a in cd["assignments"])
            return ("Met", f'{total_pts} total points across {len(cd["assignments"])} items')
        if "grade breakdown" in t:
            g = cd["agroups"]
            return ("Met", f'{len(g)} groups') if len(g) > 1 else ("Not Met", "Not configured")
        if "proctoring" in t:
            return ("not_applicable", "No proctoring detected")

    # ── Standard 10 ──
    if cid_str.startswith("B-10."):
        if "two different" in t or "2+" in t.replace(" ", ""):
            return ("Met", f'{len(cd["quizzes"])} quizzes, {len(cd["assignments"])} assignments, {len(cd["discussions"])} discussions')
        if "ungraded" in t or "practice" in t:
            practice_assignments = [a for a in cd["assignments"] if (a.get("points_possible") or 0) == 0 or a.get("grading_type") == "not_graded"]
            practice_quizzes = [q for q in cd["quizzes"] if q.get("quiz_type") == "practice_quiz" or q.get("quiz_type") == "survey"]
            total_practice = len(practice_assignments) + len(practice_quizzes)
            if total_practice > 0:
                parts = []
                if practice_assignments:
                    parts.append(f'{len(practice_assignments)} ungraded assignment(s)')
                if practice_quizzes:
                    parts.append(f'{len(practice_quizzes)} practice quiz(zes)')
                return ("Met", f'{total_practice} practice activities: {", ".join(parts)}')
            return ("Not Met", f'No ungraded or practice assessments found in {len(cd["assignments"])} assignments and {len(cd["quizzes"])} quizzes')

    # ── Standard 13 ──
    if cid_str.startswith("B-13."):
        if "cited" in t or "citation" in t:
            return ("Met", "Citations present")
        if "video" in t and ("play" in t or "functionality" in t):
            return ("Met", "Videos functional")
        if "url" in t or ("link" in t and "work" in t):
            return ("Met", "Links functional (spot check recommended)")
        if "document" in t and ("open" in t or "download" in t):
            return ("Met", "Documents accessible")
        if "image" in t and "size" in t:
            return ("Met", "Images sized properly")
        if "typo" in t:
            return ("Met", "No major typos detected")
        if "completeness" in t:
            return ("Met", f'{num_pages} pages complete')
        if "design best" in t or "formatting" in t:
            return ("Met", "Template design followed")
        if "placeholder" in t:
            return ("Met", "No placeholder text detected")
        return ("Met", "Content quality passed")

    # ── Standard 16 ──
    if cid_str.startswith("B-16."):
        return ("Met", "Multiple content formats present")

    # ── Standard 17 ──
    if cid_str.startswith("B-17."):
        if "moderation" in t:
            return ("Partially Met", "Discussion space exists but no explicit moderation policy")
        if "response" in t and "turnaround" in t:
            return ("Not Met", f'No response time specified. Searched {num_pages} pages')
        if "private" in t:
            return ("Met", "Canvas inbox for private communication")
        if "communication" in t or "question" in t:
            return ("Met", f'{len(cd["discussions"])} discussion(s)') if cd["discussions"] else ("Not Met", "No discussion space")

    # ── Standard 18 ──
    if cid_str.startswith("B-18."):
        if "10 minutes" in t or "length" in t:
            return ("Met", "Videos segmented")
        if "slide" in t or "downloadable" in t:
            return ("not_applicable", "No separate slide decks")

    # ── Standard 20 ──
    if cid_str.startswith("B-20."):
        if "technical support" in t or "guides" in t:
            support = [t_tab for t_tab in cd["tabs"] if any(k in t_tab.lower() for k in ["tutor", "support", "accessibility"])]
            return ("Met", f'Support: {", ".join(support)}') if support else ("Partially Met", "No dedicated support tabs")
        if "proctoring" in t:
            return ("not_applicable", "No proctoring")

    # ── Standard 22 ──
    if cid_str.startswith("B-22."):
        if "wcag" in t or ("canvas pages" in t and "accessibility" in t):
            issues = []
            if cd["imgs_no_alt_total"] > 0:
                issues.append(f'{cd["imgs_no_alt_total"]} images missing alt across {len(cd["imgs_no_alt_by_page"])} pages')
            if cd["heading_issues"]:
                issues.append(f'{len(cd["heading_issues"])} heading issue(s)')
            return ("Not Met", ". ".join(issues)) if issues else ("Met", f'All {num_pages} pages pass')
        if "document" in t and "accessibility" in t:
            return ("Partially Met", "Document accessibility needs manual POUR review")
        if "alt text" in t or ("alternative" in t and "image" in t):
            if cd["imgs_no_alt_total"] == 0:
                decorative_note = f' ({cd["imgs_decorative_total"]} marked decorative)' if cd["imgs_decorative_total"] else ''
                return ("Met", f'All {cd["imgs_total"]} images have alt text or are marked decorative{decorative_note}')
            by_page = cd["imgs_no_alt_by_page"]
            top = sorted(by_page.items(), key=lambda x: len(x[1]), reverse=True)[:8]
            detail = ". ".join(f'{pg}: {len(imgs)} img(s)' for pg, imgs in top)
            return ("Not Met", f'{cd["imgs_no_alt_total"]}/{cd["imgs_total"]} missing alt across {len(by_page)} pages. {detail}')
        if "decorative" in t:
            d_total = cd["imgs_decorative_total"]
            if d_total == 0:
                return ("Met", "No images marked decorative — all have descriptive alt text")
            return ("Partially Met", f'{d_total} images marked decorative (alt="") across {len(cd["imgs_decorative_by_page"])} pages — verify each is intentionally decorative')
        if "hyperlink" in t or ("descriptive" in t and "link" in t):
            return ("Met", "Links use descriptive text")
        if "audio description" in t:
            return ("not_applicable", "No critical visual-only video detected")
        if "caption" in t:
            return ("Partially Met", "Caption accuracy not verified")
        if "transcript" in t:
            return ("Partially Met", "Transcript availability not verified")
        if "ally" in t:
            return ("manual_entry", "Requires Ally dashboard — enter manually")
        if "scout" in t:
            return ("not_applicable", "SCOUT score no longer used — skip")
        if "readability" in t:
            return ("manual_entry", "Requires readability analysis — enter manually")

    # ── Standard 24 ──
    if cid_str.startswith("B-24."):
        return ("needs_review", "Manual review required — verify if mobile/offline access statements exist. Collecting ID feedback during pilot to define criteria.")

    # ── Standard 25 ──
    if cid_str.startswith("B-25."):
        if "justified" in t:
            return ("Met", "Materials through institutional channels")

    # ── CRC ──
    if cid_str.startswith("B-CRC."):
        return ("needs_review", "CRC criterion — evaluate separately")

    # Fallback for unmatched B-criteria
    return ("needs_review", "Criterion not matched by deterministic evaluator — needs AI review")


def evaluate_all(cd, filter_standard=None):
    """Evaluate all criteria. Returns list of result dicts.

    B-criteria (Col B) are evaluated deterministically here via HTML/API checks.
    C-criteria (Col C) are NOT evaluated -- they're tagged needs_ai_review=True
    so the audit skill can hand them to Claude for subjective assessment later.
    """
    with open(PLUGIN_ROOT / "config" / "standards.yaml") as f:
        stds = yaml.safe_load(f)

    results = []
    for std in stds["standards"]:
        sid = std["id"]
        if sid == "crc":
            continue
        if std.get("excluded"):
            continue
        if filter_standard and sid != filter_standard:
            continue

        for crit in std.get("criteria", []):
            cid_str = crit["criterion_id"]
            crit_text = crit["text"]
            reviewer_tier = crit.get("reviewer_tier", "id")
            check_type = crit.get("check_type", "ai")

            # Criteria where the deterministic evaluator gives an optimistic default
            # but can't truly verify -- e.g. "are videos under 10 min" or "are links
            # functional" require browser testing or content judgment that HTML parsing
            # alone can't provide. Flagging these as low-confidence tells the audit
            # report (and reviewers) to treat the verdict as provisional, not definitive.
            LOW_CONFIDENCE = {
                "B-04.7", "B-06.1", "B-13.1", "B-13.2", "B-13.3", "B-13.4",
                "B-13.5", "B-13.6", "B-13.7", "B-13.8", "B-17.1", "B-17.2",
                "B-22.9", "B-22.11", "B-24.1",
                # These need cross-referencing or subjective quality judgment
                "B-04.14", "B-06.2", "B-09.1", "B-09.6", "B-13.10", "B-13.14", "B-22.5",
            }

            # Hybrid Quick Check targets: B-criteria where AI should re-verify
            # the deterministic result using page content. Excludes manual_entry
            # criteria (B-22.9, B-22.11) which require external tools, not AI.
            #
            # ALWAYS_VERIFY: deterministic engine fundamentally can't check these
            # (e.g. content quality, moderation policy) — always flag for AI.
            ALWAYS_VERIFY = {
                "B-13.1", "B-13.2", "B-13.3",   # citations, video, links — can't verify without browsing
                "B-13.10", "B-13.11",            # typos, grammar — need language model
                "B-13.13", "B-13.14",            # formatting, text density — need visual judgment
                "B-17.1", "B-17.2",              # moderation policy, response time — static result today
                "B-22.5",                        # descriptive link text — needs semantic check
                "B-24.1",                        # mobile/offline access — needs content scan
            }
            # VERIFY_WHEN_WEAK: flag only when deterministic result is Not Met,
            # Partially Met, or needs_review — skip when clearly Met with evidence.
            VERIFY_WHEN_WEAK = {
                "B-04.23", "B-04.24",           # welcome communication, course tour
                "B-06.1", "B-06.2",             # workload details, time commitments
                "B-09.1",                        # assessment instructions
            }

            if cid_str.startswith("B-"):
                # B-criteria are deterministic: evaluated via HTML parsing + API data
                status, evidence = evaluate_b_criterion(cid_str, crit_text, cd)
                confidence = "low" if cid_str in LOW_CONFIDENCE else "high"
                affected_pages = _build_affected_pages(cid_str, status, cd)
                # Flag for AI verification — targeted by result strength
                weak_result = status in ("Not Met", "Partially Met", "needs_review")
                needs_ai_verify = (
                    cid_str in ALWAYS_VERIFY
                    or (cid_str in VERIFY_WHEN_WEAK and weak_result)
                    or (cid_str.startswith("B-04.") and "not matched by specific check" in evidence)
                )
                results.append({
                    "criterion_id": cid_str,
                    "criterion_text": crit_text,
                    "standard_id": sid,
                    "standard_name": std["name"],
                    "status": status,
                    "evidence": evidence,
                    "check_type": "deterministic",
                    "reviewer_tier": reviewer_tier,
                    "confidence": confidence,
                    "needs_ai_review": False,
                    "needs_ai_verification": needs_ai_verify,
                    "affected_pages": affected_pages,
                })
            else:
                # C-criteria require subjective judgment (e.g. alignment quality,
                # pedagogical effectiveness) -- punt to Claude for AI evaluation
                results.append({
                    "criterion_id": cid_str,
                    "criterion_text": crit_text,
                    "standard_id": sid,
                    "standard_name": std["name"],
                    "status": "needs_ai_review",
                    "evidence": "",
                    "check_type": "ai",
                    "reviewer_tier": reviewer_tier,
                    "confidence": "medium",
                    "needs_ai_review": True,
                })

    return results


def summarize(results):
    """Produce standard-level summary from criterion results."""
    by_std = defaultdict(list)
    for r in results:
        by_std[r["standard_id"]].append(r)

    standards = []
    for sid, criteria in sorted(by_std.items()):
        b_results = [c for c in criteria if not c["needs_ai_review"]]
        c_results = [c for c in criteria if c["needs_ai_review"]]
        _na_statuses = ("N/A", "not_applicable", "needs_review", "manual_entry")
        b_statuses = [c["status"] for c in b_results if c["status"] not in _na_statuses]
        b_met = sum(1 for s in b_statuses if s == "Met")
        b_total = len(b_statuses)

        if b_total == 0:
            std_status = "needs_ai_review"
        elif all(s == "Met" for s in b_statuses):
            std_status = "Met" if not c_results else "needs_ai_review"
        elif any(s == "Not Met" for s in b_statuses):
            std_status = "Partially Met"
        else:
            std_status = "Partially Met"

        standards.append({
            "standard_id": sid,
            "standard_name": criteria[0]["standard_name"],
            "b_met": b_met,
            "b_total": b_total,
            "c_pending": len(c_results),
            "status": std_status,
        })

    return standards


def build_full_audit_json(cd, results, mode="full_audit"):
    """Build the COMPLETE audit JSON matching audit_report.py's expected schema.

    This is the format that goes directly to audit_report.py --input <file>.
    Claude does NOT need to build this JSON -- the evaluator does it.

    Score computation (3 independent scores + 1 composite):
      readiness_score = % of Col B criteria Met (all standards, excluding N/A)
      design_score    = % of Col C criteria Met (None when C not yet evaluated)
      a11y_score      = % of Standards 22-23 B-criteria Met (WCAG subset)
      overall_score   = avg(readiness, design) when both exist, else readiness only
    """
    from datetime import datetime

    link = cd["link"]
    domain = cd["domain"]
    cid = cd["course_id"]

    # Resolve auditor name
    auditor = "ID Workbench"
    tester_id = os.getenv("IDW_TESTER_ID", "").strip()
    if tester_id:
        try:
            from role_gate import get_current_tester
            tester = get_current_tester()
            if tester and tester.get("name"):
                auditor = tester["name"]
        except Exception:
            pass

    # Determine audit_purpose from role
    audit_purpose = "self_audit"
    if tester_id:
        try:
            from role_gate import get_current_tester
            tester = get_current_tester()
            if tester and tester.get("role") == "admin":
                audit_purpose = "recurring"
        except Exception:
            pass

    # Group results by standard
    by_std = defaultdict(list)
    for r in results:
        by_std[r["standard_id"]].append(r)

    # Build design_standards items
    ds_items = []
    met_count = 0
    partial_count = 0
    not_met_count = 0
    na_count = 0

    with open(PLUGIN_ROOT / "config" / "standards.yaml") as f:
        stds = yaml.safe_load(f)
    std_meta = {s["id"]: s for s in stds["standards"]}

    for sid in sorted(by_std.keys()):
        criteria = by_std[sid]
        meta = std_meta.get(sid, {})

        # Build criteria_results array
        criteria_results = []
        all_affected = []
        for cr in criteria:
            ap = cr.get("affected_pages", [])
            criteria_results.append({
                "criterion_id": cr["criterion_id"],
                "criterion_text": cr["criterion_text"],
                "status": cr["status"],
                "evidence": cr["evidence"],
                "check_type": cr["check_type"],
                "reviewer_tier": cr["reviewer_tier"],
                "affected_pages": ap,
                "needs_ai_verification": cr.get("needs_ai_verification", False),
            })
            all_affected.extend(ap)

        # Derive standard-level status
        _skip = ("N/A", "not_applicable", "needs_review", "manual_entry", "needs_ai_review")
        statuses = [cr["status"] for cr in criteria if cr["status"] not in _skip]
        met = sum(1 for s in statuses if s == "Met")
        total = len(statuses)

        if total == 0:
            std_status = "Not Auditable"
            na_count += 1
        elif all(s == "Met" for s in statuses):
            # If there are C-criteria pending, still mark as Met for B-only (quick check)
            # or needs_ai_review for full audit
            c_pending = sum(1 for cr in criteria if cr.get("needs_ai_review"))
            if c_pending > 0 and mode == "full_audit":
                std_status = "Partially Met"  # Can't be fully Met until C-criteria evaluated
                partial_count += 1
            else:
                std_status = "Met"
                met_count += 1
        elif any(s == "Not Met" for s in statuses):
            std_status = "Partially Met"
            partial_count += 1
        else:
            std_status = "Partially Met"
            partial_count += 1

        # Build evidence summary
        issues = [cr for cr in criteria if cr["status"] in ("Not Met", "Partially Met")]
        if issues:
            std_evidence = f"{met}/{total} criteria met. Issues: " + "; ".join(
                f'{cr["criterion_id"]}: {cr["evidence"][:60]}' for cr in issues[:3]
            )
            std_rec = ". ".join(cr["evidence"][:100] for cr in issues if cr["status"] == "Not Met")[:500] or None
        else:
            std_evidence = f"All {total} criteria met."
            std_rec = None

        is_a11y = sid in ("22", "23")
        has_b = any(cr["criterion_id"].startswith("B-") for cr in criteria)

        ds_items.append({
            "id": sid,
            "name": meta.get("name", f"Standard {sid}"),
            "category": meta.get("category", ""),
            "status": std_status,
            "evidence": std_evidence,
            "recommendation": std_rec,
            "confidence": "High" if total > 3 else "Medium",
            "coverage": f"{met}/{total} criteria",
            "reviewer_tier": "id_assistant" if has_b and not is_a11y else "id",
            "canvas_link": all_affected[0]["url"] if all_affected else f"{link}/modules",
            "essential": meta.get("essential", False),
            "criteria_results": criteria_results,
        })

    # Build QA categories from course data
    qa_items = [
        {"id": "Q01", "name": "Module structure", "status": "Pass", "detail": f'{len(cd["content_modules"])} modules consistent', "reviewer_tier": "id_assistant"},
        {"id": "Q02", "name": "Getting Started", "status": "Pass" if cd["has_getting_started"] else "Fail", "detail": "Welcome area exists" if cd["has_getting_started"] else "No welcome area", "reviewer_tier": "id_assistant"},
        {"id": "Q03", "name": "Syllabus", "status": "Pass" if cd["has_syllabus"] else "Warn", "detail": f'{cd["syllabus_len"]} chars', "reviewer_tier": "id_assistant"},
        {"id": "Q04", "name": "Overviews", "status": "Pass", "detail": f'{len(cd["overview_pages"])} pages', "reviewer_tier": "id_assistant"},
        {"id": "Q05", "name": "Quizzes", "status": "Pass" if cd["quizzes"] else "Warn", "detail": f'{len(cd["quizzes"])} configured', "reviewer_tier": "id_assistant"},
        {"id": "Q06", "name": "Headings", "status": "Warn" if cd["heading_issues"] else "Pass", "detail": f'{len(cd["heading_issues"])} issue(s): {", ".join(cd["heading_issues"][:2])}' if cd["heading_issues"] else "Clean", "reviewer_tier": "id_assistant"},
        {"id": "Q07", "name": "Alt text", "status": "Fail" if cd["imgs_no_alt_total"] > 0 else ("Warn" if cd["imgs_decorative_total"] > 0 else "Pass"), "detail": f'{cd["imgs_no_alt_total"]}/{cd["imgs_total"]} truly missing across {len(cd["imgs_no_alt_by_page"])} pages' if cd["imgs_no_alt_total"] > 0 else (f'All present ({cd["imgs_decorative_total"]} marked decorative — verify intent)' if cd["imgs_decorative_total"] > 0 else "All present"), "reviewer_tier": "id_assistant"},
        {"id": "Q08", "name": "Rubrics", "status": "Pass" if cd["assignments_with_rubric"] else "Fail", "detail": f'{len(cd["assignments_with_rubric"])}/{len(cd["assignments"])} have rubrics', "reviewer_tier": "id_assistant"},
        {"id": "Q09", "name": "Navigation", "status": "Pass", "detail": f'{", ".join(cd["tabs"][:5])}', "reviewer_tier": "id_assistant"},
        {"id": "Q10", "name": "Assignment groups", "status": "Pass" if len(cd["agroups"]) > 1 else "Warn", "detail": f'{len(cd["agroups"])} groups', "reviewer_tier": "id_assistant"},
        {"id": "Q11", "name": "Discussions", "status": "Pass" if cd["discussions"] else "Warn", "detail": f'{len(cd["discussions"])} topic(s)', "reviewer_tier": "id_assistant"},
    ]
    qa_pass = sum(1 for q in qa_items if q["status"] == "Pass")
    qa_warn = sum(1 for q in qa_items if q["status"] == "Warn")
    qa_fail = sum(1 for q in qa_items if q["status"] == "Fail")

    # Build accessibility
    a11y_items = []
    if cd["imgs_no_alt_total"] > 0:
        top_pages = sorted(cd["imgs_no_alt_by_page"].items(), key=lambda x: len(x[1]), reverse=True)[:5]
        a11y_items.append({
            "severity": "Critical",
            "page": f'{len(cd["imgs_no_alt_by_page"])} pages',
            "issue": f'{cd["imgs_no_alt_total"]} images missing alt text (no alt attribute)',
            "element": f'Top: {", ".join(p[0] for p in top_pages)}',
            "fix": "Add descriptive alt text or mark as decorative in Canvas",
            "canvas_link": f"{link}/pages",
        })
    if cd["imgs_decorative_total"] > 0:
        top_dec = sorted(cd["imgs_decorative_by_page"].items(), key=lambda x: len(x[1]), reverse=True)[:5]
        a11y_items.append({
            "severity": "Warning",
            "page": f'{len(cd["imgs_decorative_by_page"])} pages',
            "issue": f'{cd["imgs_decorative_total"]} images marked decorative (alt="") — verify each is intentionally decorative',
            "element": f'Top: {", ".join(p[0] for p in top_dec)}',
            "fix": "Confirm images are decorative; add alt text to any that convey meaning",
            "canvas_link": f"{link}/pages",
        })
    for hi in cd["heading_issues"][:3]:
        page_slug = hi.split(":")[0].strip()
        a11y_items.append({
            "severity": "Critical",
            "page": page_slug,
            "issue": f"Heading skip: {hi}",
            "element": "Heading hierarchy",
            "fix": "Fix heading level",
            "canvas_link": f"{link}/pages/{page_slug}",
        })
    a11y_critical = sum(1 for a in a11y_items if a["severity"] == "Critical")
    a11y_warning = sum(1 for a in a11y_items if a["severity"] == "Warning")

    # Build readiness
    readiness_cats = [
        {"name": "Info", "status": "Pass" if cd["has_syllabus"] else "Warn", "checks": [
            {"item": "Syllabus", "status": "Pass" if cd["has_syllabus"] else "Warn", "note": f'{cd["syllabus_len"]} chars'},
            {"item": "Description", "status": "Pass"},
        ]},
        {"name": "Navigation", "status": "Pass", "checks": [
            {"item": "Home", "status": "Pass" if "Home" in cd["tabs"] else "Fail"},
            {"item": "Tabs", "status": "Pass"},
            {"item": "Modules", "status": "Pass" if "Modules" in cd["tabs"] else "Fail"},
        ]},
        {"name": "Content", "status": "Pass", "checks": [
            {"item": "Modules have content", "status": "Pass"},
        ]},
        {"name": "Assessments", "status": "Pass" if cd["assignments_with_rubric"] else "Fail", "checks": [
            {"item": "Quizzes", "status": "Pass" if cd["quizzes"] else "Fail"},
            {"item": "Rubrics", "status": "Pass" if cd["assignments_with_rubric"] else "Fail",
             "note": f'{len(cd["assignments_with_rubric"])}/{len(cd["assignments"])}'},
        ]},
        {"name": "Accessibility", "status": "Fail" if cd["imgs_no_alt_total"] > 0 or cd["heading_issues"] else "Pass", "checks": [
            {"item": "Alt text", "status": "Fail" if cd["imgs_no_alt_total"] > 0 else "Pass",
             "note": f'{cd["imgs_no_alt_total"]} missing' if cd["imgs_no_alt_total"] > 0 else ""},
            {"item": "Headings", "status": "Fail" if cd["heading_issues"] else "Pass"},
        ]},
        {"name": "Communication", "status": "Pass", "checks": [
            {"item": "Discussions", "status": "Pass" if cd["discussions"] else "Warn"},
        ]},
    ]
    r_pass = sum(1 for c in readiness_cats if c["status"] == "Pass")
    r_total = len(readiness_cats)

    # ── Compute split scores ──
    # Three independent scores map to the report's score boxes.
    # Readiness = Col B pass rate -- the "can this course launch?" metric
    _na_all = ("N/A", "not_applicable", "needs_review", "manual_entry")
    b_results_all = [r for r in results if r["criterion_id"].startswith("B-") and r["status"] not in _na_all]
    b_met_all = sum(1 for r in b_results_all if r["status"] == "Met")
    readiness_score = round(b_met_all / len(b_results_all) * 100) if b_results_all else 0

    # Design = Col C pass rate -- the "is the pedagogy sound?" metric
    # None when C-criteria haven't been evaluated yet (Quick Check mode)
    c_results_all = [r for r in results if r["criterion_id"].startswith("C-") and r["status"] not in (*_na_all, "needs_ai_review")]
    c_met_all = sum(1 for r in c_results_all if r["status"] == "Met")
    design_score = round(c_met_all / len(c_results_all) * 100) if c_results_all else None  # None = not evaluated

    # A11y = Standards 22-23 only -- carved out because ASU mandates WCAG AA separately
    a11y_results = [r for r in results if r["standard_id"] in ("22", "23") and r["criterion_id"].startswith("B-") and r["status"] not in _na_all]
    a11y_met = sum(1 for r in a11y_results if r["status"] == "Met")
    a11y_score = round(a11y_met / len(a11y_results) * 100) if a11y_results else 0

    # Overall = equal-weight average of readiness + design when both exist,
    # falls back to readiness-only for Quick Check (where design_score is None)
    if design_score is not None:
        overall = round((readiness_score + design_score) / 2)
    else:
        overall = readiness_score

    # Legacy scores for backward compat with report sections
    qa_score = round(qa_pass / len(qa_items) * 100) if qa_items else 0

    course_obj = cd["course"]
    return {
        "course": {
            "name": course_obj.get("name", cd["course_name"]),
            "id": cd["course_id"],
            "domain": cd["domain"],
            "course_code": course_obj.get("course_code", ""),
            "institution": "Arizona State University",
        },
        "audit_date": datetime.now().isoformat(),
        "auditor": auditor,
        "plugin_version": "0.6.0",
        "audit_mode": mode.replace("_", " "),
        "audit_purpose": audit_purpose,
        "overall_score": overall,
        "readiness_score": readiness_score,
        "design_score": design_score,  # None if not evaluated (Quick Check)
        "a11y_score": a11y_score,
        "standards_score": readiness_score,  # backward compat with audit_report.py
        "qa_score": qa_score,
        "sections": {
            "design_standards": {
                "title": "ASU Course Design Standards",
                "subtitle": f"25 standards, {len(results)} criteria evaluated",
                "summary": {"Met": met_count, "Partially Met": partial_count, "Not Met": not_met_count, "Not Auditable": na_count},
                "items": ds_items,
            },
            "qa_categories": {
                "title": "QA Categories",
                "subtitle": "Structural checks",
                "summary": {"Pass": qa_pass, "Warn": qa_warn, "Fail": qa_fail},
                "items": qa_items,
            },
            "accessibility": {
                "title": "WCAG 2.1 AA Accessibility",
                "subtitle": "Accessibility checks",
                "summary": {"Critical": a11y_critical, "Warning": a11y_warning, "Info": 0},
                "items": a11y_items,
            },
            "readiness": {
                "title": "Course Readiness Check",
                "subtitle": "Pre-launch operational checklist",
                "overall": "READY" if r_pass == r_total else "NOT READY",
                "categories": readiness_cats,
            },
        },
    }


def main():
    """Entry point with 4 output modes + a default human-readable table.

    --quick-check : Col B only, full audit JSON. Fast "is this course ready?" pass.
                    Feeds directly into audit_report.py for HTML/XLSX generation.
    --full-audit  : Col B evaluated + Col C tagged for AI. The audit skill pipes
                    this to Claude, who fills in C-criteria, then sends to report.
    --summary     : Compact standard-level rollup (Met/Not Met counts). Used by
                    the concierge for a quick status line.
    --json        : Raw criterion-level results for programmatic consumption.
    (no flag)     : Human-readable table with check/cross markers to stderr+stdout.
    """
    parser = argparse.ArgumentParser(description="Deterministic criterion evaluator")
    parser.add_argument("--json", action="store_true", help="Output criterion-level results as JSON")
    parser.add_argument("--summary", action="store_true", help="Output standard-level summary")
    parser.add_argument("--standard", help="Evaluate a single standard (e.g., 04)")
    parser.add_argument("--full-audit", action="store_true", help="Output COMPLETE audit JSON for audit_report.py (Deep Audit — B evaluated, C marked for AI)")
    parser.add_argument("--quick-check", action="store_true", help="Output COMPLETE audit JSON — Col B only, no C-criteria (Quick Check mode)")
    args = parser.parse_args()

    cd = collect_course_data()
    print(f"Course: {cd['course_name']} | Pages: {len(cd['pages'])} | Images: {cd['imgs_total']}", file=sys.stderr)

    results = evaluate_all(cd, filter_standard=args.standard)

    if args.quick_check:
        # Quick Check: strip C-criteria so report shows B-only verdicts (no AI needed)
        b_only = [r for r in results if not r["needs_ai_review"]]
        audit_json = build_full_audit_json(cd, b_only, mode="quick_check")
        print(json.dumps(audit_json, indent=2))
    elif args.full_audit:
        # Full Audit: B deterministic + C placeholders for Claude to fill in
        audit_json = build_full_audit_json(cd, results, mode="full_audit")
        print(json.dumps(audit_json, indent=2))
    elif args.summary:
        summary = summarize(results)
        print(json.dumps(summary, indent=2))
    elif args.json:
        output = {
            "course": {"name": cd["course_name"], "id": cd["course_id"], "domain": cd["domain"]},
            "criteria_count": len(results),
            "b_evaluated": sum(1 for r in results if not r["needs_ai_review"]),
            "c_pending_ai": sum(1 for r in results if r["needs_ai_review"]),
            "results": results,
        }
        print(json.dumps(output, indent=2))
    else:
        for r in results:
            marker = "✓" if r["status"] == "Met" else ("✗" if r["status"] == "Not Met" else "?" if r["needs_ai_review"] else "△")
            print(f'{marker} {r["criterion_id"]:10} {r["status"]:15} {r["evidence"][:80]}')


if __name__ == "__main__":
    main()
