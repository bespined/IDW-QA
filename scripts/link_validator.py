#!/usr/bin/env python3
"""Canvas Link Validator integration.

Triggers the Canvas built-in link validator for a course, polls for completion,
and categorizes results into broken links, broken images, review items, and
false positives.

Ported from LE QA Plugin (dchandarana07/claude-plugins) Phase 0 inline checks.

Usage:
    python3 scripts/link_validator.py --course-id 12345
    python3 scripts/link_validator.py --course-id 12345 --json
    python3 scripts/link_validator.py --course-id 12345 --timeout 90

Programmatic usage:
    from link_validator import run_validation
    result = run_validation(course_id="12345", config=canvas_config)
"""

import argparse
import json
import os
import requests
import sys
import time

# Import shared Canvas API utilities
try:
    sys.path.insert(0, os.path.dirname(__file__))
    from canvas_api import get_config, _request_with_retry, require_course_id
except ImportError:
    print("ERROR: canvas_api.py not found. Run from the plugin root.", file=sys.stderr)
    sys.exit(2)

# Logging
try:
    from idw_logger import get_logger
    _log = get_logger("link_validator")
except ImportError:
    import logging
    _log = logging.getLogger("link_validator")

# ============================================================
# CONSTANTS
# ============================================================
POLL_INTERVAL = 5       # seconds between polls
DEFAULT_TIMEOUT = 60    # seconds total
MAX_POLLS = 12          # max poll attempts

# Issue reasons that are definite failures (Canvas uses these exact strings)
FAIL_REASONS = {"course_mismatch", "unpublished_item", "missing_item", "deleted"}

# URL prefixes that are known Canvas validator false positives
IGNORE_PREFIXES = ("tel:", "mailto:")

# Domains that are typically paywalled, not truly broken
REVIEW_DOMAINS = ("doi.org",)


# ============================================================
# CATEGORIZATION
# ============================================================

def _categorize_issue(issue):
    """Categorize a single flattened link validator issue.

    Each issue has been flattened by _extract_issues and contains:
      - url, reason, image: from the invalid_links entry
      - source_name, source_type, content_url: from the parent page/resource

    Returns a dict with:
        category: "broken_link" | "broken_image" | "review" | "ignored"
        severity: "fail" | "review" | "ignore"
        reason: original reason from Canvas
        url: the problematic URL
        image: whether this is an image issue
        source_url: the Canvas page/content URL where the issue was found
        source_name: the name of the source content
        source_type: the type of source (e.g., "wiki_page", "assignment")
    """
    url = issue.get("url", "")
    reason = issue.get("reason", "unknown")
    is_image = issue.get("image", False)
    source_url = issue.get("content_url", "")
    source_name = issue.get("source_name", "") or issue.get("name", "")
    source_type = issue.get("source_type", "") or issue.get("type", "")

    base = {
        "url": url,
        "reason": reason,
        "image": is_image,
        "source_url": source_url,
        "source_name": source_name,
        "source_type": source_type,
    }

    # Broken images — any image issue is a fail
    if is_image:
        return {**base, "category": "broken_image", "severity": "fail"}

    # Known false positives: tel: and mailto: links
    if any(url.startswith(prefix) for prefix in IGNORE_PREFIXES):
        return {**base, "category": "ignored", "severity": "ignore"}

    # Definite failures: missing, unpublished, cross-course
    if reason in FAIL_REASONS:
        return {**base, "category": "broken_link", "severity": "fail"}

    # Unreachable external links
    if reason == "unreachable":
        # Paywalled domains get REVIEW, not FAIL
        if any(domain in url for domain in REVIEW_DOMAINS):
            return {**base, "category": "review", "severity": "review"}
        # Other unreachable external links
        return {**base, "category": "review", "severity": "review"}

    # Fallback: unknown reason → review
    return {**base, "category": "review", "severity": "review"}


def categorize_results(raw_issues):
    """Categorize all link validator issues.

    Returns:
        dict with keys: issues (list), summary (counts), link_status, image_status
    """
    categorized = [_categorize_issue(issue) for issue in raw_issues]

    broken_links = [i for i in categorized if i["category"] == "broken_link"]
    broken_images = [i for i in categorized if i["category"] == "broken_image"]
    review_items = [i for i in categorized if i["category"] == "review"]
    ignored = [i for i in categorized if i["category"] == "ignored"]

    # Determine overall statuses
    if broken_links:
        link_status = "FAIL"
    elif review_items:
        link_status = "REVIEW"
    else:
        link_status = "PASS"

    image_status = "FAIL" if broken_images else "PASS"

    return {
        "issues": categorized,
        "broken_links": broken_links,
        "broken_images": broken_images,
        "review_items": review_items,
        "ignored": ignored,
        "summary": {
            "total": len(categorized),
            "broken_links": len(broken_links),
            "broken_images": len(broken_images),
            "review": len(review_items),
            "ignored": len(ignored),
        },
        "link_status": link_status,
        "image_status": image_status,
    }


# ============================================================
# AFFECTED PAGES BUILDER
# ============================================================

def build_affected_pages(categorized_issues, course_link, pages_dict=None):
    """Transform categorized issues into the IDW-QA affected_pages contract.

    Groups issues by source page, producing objects matching:
        {slug, title, url, issue_summary, issue_count}

    Args:
        categorized_issues: list of categorized issue dicts (from categorize_results)
        course_link: base course URL (e.g., https://canvas.asu.edu/courses/12345)
        pages_dict: optional dict of {slug: {title: ...}} for title lookup

    Returns:
        dict mapping criterion_id to list of affected_page objects
    """
    if pages_dict is None:
        pages_dict = {}

    # Group issues by source content and by which criteria they affect
    # B-13.3: broken links (non-image fails)
    # B-13.4: unpublished items (documents not visible)
    # B-13.5: broken images
    criteria_issues = {
        "B-13.3": [],  # broken links
        "B-13.4": [],  # documents not appearing
        "B-13.5": [],  # broken images
    }

    for issue in categorized_issues:
        if issue["severity"] == "ignore":
            continue
        if issue["category"] == "broken_image":
            criteria_issues["B-13.5"].append(issue)
        elif issue["category"] == "broken_link":
            criteria_issues["B-13.3"].append(issue)
            # unpublished_item specifically affects B-13.4 (documents in student view)
            if issue["reason"] == "unpublished_item":
                criteria_issues["B-13.4"].append(issue)
        elif issue["category"] == "review":
            # Review items count toward B-13.3 (links)
            criteria_issues["B-13.3"].append(issue)

    result = {}
    for cid, issues in criteria_issues.items():
        if not issues:
            result[cid] = []
            continue

        # Group by source page
        by_source = {}
        for issue in issues:
            # Extract slug from source_url or use source_name as fallback
            slug = _extract_slug(issue.get("source_url", ""))
            if slug not in by_source:
                by_source[slug] = {
                    "slug": slug,
                    "issues": [],
                    "source_name": issue.get("source_name", slug),
                    "source_type": issue.get("source_type", ""),
                }
            by_source[slug]["issues"].append(issue)

        pages = []
        for slug, group in sorted(by_source.items(), key=lambda x: -len(x[1]["issues"])):
            issue_list = group["issues"]
            # Build issue summary
            reasons = {}
            for iss in issue_list:
                r = iss["reason"]
                reasons[r] = reasons.get(r, 0) + 1
            summary_parts = [f"{count} {reason}" for reason, count in reasons.items()]
            category_label = "broken image(s)" if cid == "B-13.5" else "broken link(s)"
            issue_summary = f"{len(issue_list)} {category_label}: {', '.join(summary_parts)}"

            # Title lookup
            title = group["source_name"]
            if slug in pages_dict:
                page_info = pages_dict[slug]
                if isinstance(page_info, dict):
                    title = page_info.get("title", title)

            # Build page URL from content_url or fall back to pages/{slug}
            raw_content_url = ""
            for iss in issue_list:
                if iss.get("source_url"):
                    raw_content_url = iss["source_url"]
                    break
            if raw_content_url:
                # Canvas content_url is relative (e.g., /courses/123/pages/slug/edit)
                # Strip /edit suffix and make absolute
                clean_url = raw_content_url.rstrip("/")
                if clean_url.endswith("/edit"):
                    clean_url = clean_url[:-5]
                if clean_url.startswith("/"):
                    # Extract domain from course_link
                    domain_part = "/".join(course_link.split("/")[:3])
                    page_url = f"{domain_part}{clean_url}"
                else:
                    page_url = clean_url
            elif "wiki_page" in group.get("source_type", "") or "page" in group.get("source_type", ""):
                page_url = f"{course_link}/pages/{slug}"
            else:
                page_url = f"{course_link}/pages/{slug}"

            pages.append({
                "slug": slug,
                "title": title,
                "url": page_url,
                "issue_summary": issue_summary,
                "issue_count": len(issue_list),
            })

        result[cid] = pages[:10]  # Cap at 10 pages per criterion (consistent with other affected_pages)

    return result


def _extract_slug(content_url):
    """Extract a page slug from a Canvas content URL.

    Canvas content_url formats (from link validator):
        /courses/123/pages/module-1-overview/edit → module-1-overview
        /courses/123/assignments/67890 → assignments-67890
        /courses/123/quizzes/111 → quizzes-111
        https://canvas.asu.edu/courses/12345/pages/slug → slug
        "" → unknown
    """
    if not content_url:
        return "unknown"

    # Strip trailing /edit (Canvas content_urls often end with /edit)
    clean = content_url.rstrip("/")
    if clean.endswith("/edit"):
        clean = clean[:-5]

    # Try to extract /pages/{slug}
    if "/pages/" in clean:
        return clean.split("/pages/")[-1].split("?")[0].split("#")[0]

    # For other content types, use the type + ID
    parts = clean.rstrip("/").split("/")
    if len(parts) >= 2:
        return f"{parts[-2]}-{parts[-1]}"

    return "unknown"


# ============================================================
# VALIDATION RUNNER
# ============================================================

def run_validation(course_id, config=None, timeout=DEFAULT_TIMEOUT):
    """Run the Canvas link validator for a course.

    Args:
        course_id: Canvas course ID (str or int)
        config: canvas_api config dict (if None, loads from env)
        timeout: max seconds to wait for validation

    Returns:
        dict with:
            status: "completed" | "timeout" | "error"
            results: categorized results (if completed)
            raw_issues: original Canvas issues list
            error: error message (if error)
    """
    if config is None:
        config = get_config(course_id=str(course_id))

    course_id = str(course_id)
    base_url = config["base_url"]
    headers = config["headers"]
    url = f"{base_url}/courses/{course_id}/link_validation"

    _log.info("Starting link validation for course %s", course_id)

    # Step 1: Check if validation already completed
    try:
        resp = _request_with_retry(requests.get, url, headers)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("workflow_state") == "completed":
                _log.info("Link validation already completed — using cached results")
                raw_issues = _extract_issues(data)
                categorized = categorize_results(raw_issues)
                return {
                    "status": "completed",
                    "results": categorized,
                    "raw_issues": raw_issues,
                }
    except Exception as e:
        _log.warning("Error checking existing validation: %s", e)

    # Step 2: Trigger validation
    try:
        _log.info("Triggering link validation...")
        trigger_headers = {**headers, "Content-Length": "0"}
        trigger_resp = _request_with_retry(
            requests.post, url, trigger_headers,
            data="",  # Empty body required
        )
        # Canvas may return 200 or 202 for trigger
        if trigger_resp.status_code not in (200, 202):
            _log.warning("Trigger returned status %d", trigger_resp.status_code)
    except Exception as e:
        _log.warning("Error triggering validation: %s — will poll anyway", e)

    # Step 3: Poll for completion
    start_time = time.time()
    polls = 0
    while polls < MAX_POLLS and (time.time() - start_time) < timeout:
        time.sleep(POLL_INTERVAL)
        polls += 1
        _log.info("Polling link validation (attempt %d/%d)...", polls, MAX_POLLS)

        try:
            resp = _request_with_retry(requests.get, url, headers)
            if resp.status_code == 200:
                data = resp.json()
                state = data.get("workflow_state", "")
                if state == "completed":
                    _log.info("Link validation completed after %d polls", polls)
                    raw_issues = _extract_issues(data)
                    categorized = categorize_results(raw_issues)
                    return {
                        "status": "completed",
                        "results": categorized,
                        "raw_issues": raw_issues,
                    }
                elif state in ("running", "queued", ""):
                    continue
                else:
                    _log.warning("Unexpected workflow_state: %s", state)
                    continue
        except Exception as e:
            _log.warning("Poll error: %s", e)

    _log.warning("Link validation timed out after %d seconds", timeout)
    return {
        "status": "timeout",
        "results": None,
        "raw_issues": [],
        "error": f"Link validation did not complete within {timeout}s",
    }


def _extract_issues(data):
    """Extract and flatten issues from Canvas link validation response.

    Canvas returns a nested structure where each issue is a *page/resource*
    containing an `invalid_links` array:

        {
          "issues": [
            {
              "name": "Page Title",
              "type": "wiki_page",
              "content_url": "/courses/123/pages/slug/edit",
              "invalid_links": [
                {"url": "https://broken.com", "reason": "unreachable"},
                {"url": "/courses/456/files/789", "reason": "course_mismatch", "image": true}
              ]
            }
          ]
        }

    We flatten this into a list of individual link issues, each carrying
    the parent page's name, type, and content_url.
    """
    # The response may be wrapped in a progress object
    issues_list = None
    if "issues" in data:
        issues_list = data["issues"]
    elif "results" in data:
        results = data["results"]
        if isinstance(results, dict) and "issues" in results:
            issues_list = results["issues"]

    if not issues_list:
        return []

    # Flatten: each page-level issue contains invalid_links
    flat = []
    for page_issue in issues_list:
        source_name = page_issue.get("name", "")
        source_type = page_issue.get("type", "")
        content_url = page_issue.get("content_url", "")

        invalid_links = page_issue.get("invalid_links", [])
        if not invalid_links:
            # Old format: the issue itself might be a flat link
            if "url" in page_issue or "reason" in page_issue:
                flat.append(page_issue)
            continue

        for link in invalid_links:
            flat.append({
                **link,
                "source_name": source_name,
                "source_type": source_type,
                "content_url": content_url,
            })

    return flat


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Run Canvas link validator and categorize results"
    )
    parser.add_argument("--course-id", required=True, help="Canvas course ID")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"Max seconds to wait (default: {DEFAULT_TIMEOUT})")
    args = parser.parse_args()

    result = run_validation(course_id=args.course_id, timeout=args.timeout)

    if args.json:
        # For JSON output, include everything except raw_issues (redundant with categorized)
        output = {
            "status": result["status"],
            "link_validation": result.get("results"),
            "error": result.get("error"),
        }
        print(json.dumps(output, indent=2))
    else:
        # Human-readable output
        if result["status"] == "completed":
            r = result["results"]
            s = r["summary"]
            print(f"Link Validation: {result['status'].upper()}")
            print(f"  Total issues:   {s['total']}")
            print(f"  Broken links:   {s['broken_links']}")
            print(f"  Broken images:  {s['broken_images']}")
            print(f"  Needs review:   {s['review']}")
            print(f"  Ignored:        {s['ignored']}")
            print(f"  Link status:    {r['link_status']}")
            print(f"  Image status:   {r['image_status']}")

            if r["broken_links"]:
                print("\nBroken Links:")
                for issue in r["broken_links"]:
                    print(f"  {issue['source_name']} ({issue['source_type']})")
                    print(f"    → {issue['reason']}: {issue['url']}")

            if r["broken_images"]:
                print("\nBroken Images:")
                for issue in r["broken_images"]:
                    print(f"  {issue['source_name']} ({issue['source_type']})")
                    print(f"    → {issue['reason']}: {issue['url']}")

            if r["review_items"]:
                print("\nNeeds Review:")
                for issue in r["review_items"]:
                    print(f"  {issue['source_name']} ({issue['source_type']})")
                    print(f"    → {issue['reason']}: {issue['url']}")
        elif result["status"] == "timeout":
            print(f"Link validation timed out: {result.get('error', '')}", file=sys.stderr)
        else:
            print(f"Link validation error: {result.get('error', '')}", file=sys.stderr)

    # Exit codes: 0 = clean, 1 = failures found, 2 = error/timeout
    if result["status"] != "completed":
        sys.exit(2)
    elif result["results"]["summary"]["broken_links"] > 0 or result["results"]["summary"]["broken_images"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
