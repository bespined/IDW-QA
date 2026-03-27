#!/usr/bin/env python3
"""Unified Preview — generate a single scrollable HTML document of all staged pages.

Renders every staged Canvas page vertically in one document (like Microsoft Word),
with module/page annotations and a sticky sidebar table of contents.

Usage:
    python unified_preview.py                    # All staged pages
    python unified_preview.py --modules 1 3 5    # Only modules 1, 3, 5
    python unified_preview.py --open             # Generate and open in browser
    python unified_preview.py --filter overview  # Only pages matching keyword
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Logging
try:
    from idw_logger import get_logger
    _log = get_logger("unified_preview")
except ImportError:
    import logging
    _log = logging.getLogger("unified_preview")


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
STAGING_DIR = PLUGIN_ROOT / "staging"
COURSE_TREE = STAGING_DIR / ".course-tree.json"
OUTPUT_FILE = STAGING_DIR / "_unified_preview.html"

# Markers from staging_manager.py
RAW_START = '<!-- RAW_CONTENT_START -->'
RAW_END = '<!-- RAW_CONTENT_END -->'


def extract_raw(html: str) -> str:
    """Extract raw content from a staged file (strip Canvas shell wrapper)."""
    start = html.find(RAW_START)
    end = html.find(RAW_END)
    if start == -1 or end == -1:
        return html
    return html[start + len(RAW_START):end].strip()


def extract_module_number(slug: str) -> int:
    """Extract module number from slug like 'm3-overview' → 3."""
    m = re.match(r'^m(\d+)', slug)
    return int(m.group(1)) if m else 999


def slug_to_title(slug: str) -> str:
    """Convert slug to readable title: 'm1-conclusion-and-reflection-5' → 'Conclusion and Reflection'."""
    # Strip module prefix
    cleaned = re.sub(r'^m\d+-', '', slug)
    # Strip trailing number suffixes (dedup slugs like -2, -5)
    cleaned = re.sub(r'-\d+$', '', cleaned)
    # Convert to title case
    return cleaned.replace('-', ' ').title()


def classify_page_type(slug: str) -> tuple:
    """Return (type_label, color) based on slug pattern."""
    lower = slug.lower()
    if 'overview' in lower:
        return ('Overview', '#0374b5')       # Blue
    elif 'lesson' in lower or 'introduction' in lower:
        return ('Lesson', '#2d8659')          # Green
    elif 'knowledge-check' in lower or 'quiz' in lower:
        return ('Knowledge Check', '#b5540a') # Orange
    elif 'guided-practice' in lower or 'practice' in lower:
        return ('Guided Practice', '#7b2d8b') # Purple
    elif 'conclusion' in lower or 'reflection' in lower:
        return ('Conclusion', '#8C1D40')      # ASU Maroon
    elif 'discussion' in lower:
        return ('Discussion', '#1a6b8a')      # Teal
    elif 'artifact' in lower or 'assignment' in lower:
        return ('Assignment', '#c4602d')      # Burnt Orange
    elif 'resource' in lower:
        return ('Resources', '#4a6741')       # Forest green
    elif 'prepare' in lower:
        return ('Prepare to Learn', '#5c6bc0')# Indigo
    elif 'welcome' in lower or 'syllabus' in lower:
        return ('Orientation', '#455a64')     # Blue-grey
    else:
        return ('Page', '#6a7883')            # Grey


def load_course_tree() -> dict:
    """Load .course-tree.json and build a slug → module metadata map."""
    slug_map = {}
    if not COURSE_TREE.exists():
        return slug_map
    try:
        data = json.loads(COURSE_TREE.read_text(encoding='utf-8'))
        for module in data.get('tree', []):
            mod_name = module.get('name', '')
            mod_pos = module.get('position', 0)
            for item in module.get('items', []):
                page_url = item.get('page_url', '')
                if page_url:
                    slug_map[page_url] = {
                        'module_name': mod_name,
                        'module_position': mod_pos,
                        'title': item.get('title', ''),
                        'type': item.get('type', 'Page'),
                        'published': item.get('published', False),
                    }
    except (json.JSONDecodeError, KeyError):
        pass
    return slug_map


def get_staged_pages(module_filter=None, keyword_filter=None) -> list:
    """Read all staged pages, optionally filtered, sorted by module then position."""
    if not STAGING_DIR.exists():
        return []

    pages = []
    for f in sorted(STAGING_DIR.glob('*.html')):
        if f.name.startswith('.') or f.name.startswith('_'):
            continue

        slug = f.stem
        mod_num = extract_module_number(slug)

        # Module filter
        if module_filter and mod_num not in module_filter:
            continue

        # Keyword filter
        if keyword_filter and keyword_filter.lower() not in slug.lower():
            continue

        html = f.read_text(encoding='utf-8')
        raw = extract_raw(html)

        # Load preflight issues if available
        issues_path = STAGING_DIR / f"{slug}.issues.json"
        preflight = None
        if issues_path.exists():
            try:
                preflight = json.loads(issues_path.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, IOError):
                pass

        pages.append({
            'slug': slug,
            'module_number': mod_num,
            'raw_html': raw,
            'file_size': f.stat().st_size,
            'modified': datetime.fromtimestamp(f.stat().st_mtime),
            'preflight': preflight,
        })

    # Sort by module number, then slug alphabetically
    pages.sort(key=lambda p: (p['module_number'], p['slug']))
    return pages


def _build_toc_page_entry(page: dict) -> str:
    """Build a TOC entry for a page, including preflight issue badges."""
    slug = page['slug']
    type_color = classify_page_type(slug)[1]
    title = _escape(slug_to_title(slug))
    pf = page.get('preflight')

    badge = ''
    if pf and pf.get('total', 0) > 0:
        errors = pf.get('errors', 0)
        warnings = pf.get('warnings', 0)
        if errors > 0:
            badge = f'<span class="pf-badge pf-error" title="{errors} error(s)">{errors}</span>'
        elif warnings > 0:
            badge = f'<span class="pf-badge pf-warn" title="{warnings} warning(s)">{warnings}</span>'
        else:
            badge = f'<span class="pf-badge pf-info" title="{pf["total"]} info">i</span>'
    elif pf and pf.get('total', 0) == 0:
        badge = '<span class="pf-badge pf-pass" title="All checks passed">✓</span>'

    return f"""
            <a class="toc-page" href="#page-{slug}" title="{slug}">
              <span class="toc-type-dot" style="background:{type_color}"></span>
              {title}
              {badge}
            </a>"""


def _build_issue_banner(page: dict) -> str:
    """Build an inline issue banner for a page section in the preview."""
    pf = page.get('preflight')
    if not pf or pf.get('total', 0) == 0:
        return ''

    slug = page['slug']
    errors = pf.get('errors', 0)
    warnings = pf.get('warnings', 0)
    info_count = pf.get('info', 0)
    fixable = pf.get('fixable', 0)

    # Summary line
    parts = []
    if errors:
        parts.append(f'<span style="color:#d32f2f">{errors} error(s)</span>')
    if warnings:
        parts.append(f'<span style="color:#f57c00">{warnings} warning(s)</span>')
    if info_count:
        parts.append(f'<span style="color:#1976d2">{info_count} info</span>')
    summary = " · ".join(parts)
    if fixable:
        summary += f' · <span style="color:#388e3c">{fixable} auto-fixable</span>'

    # Issue list
    issue_rows = []
    for issue in pf.get('issues', []):
        sev = issue.get('severity', 'info')
        icon = {'error': '🔴', 'warning': '⚠️', 'info': 'ℹ️'}.get(sev, '?')
        msg = _escape(issue.get('message', ''))
        loc = _escape(issue.get('location', ''))
        hint = issue.get('fix_hint', '')
        hint_html = f'<div class="pf-hint">{_escape(hint)}</div>' if hint else ''
        issue_rows.append(
            f'<div class="pf-issue pf-{sev}">'
            f'<span class="pf-icon">{icon}</span>'
            f'<div class="pf-detail"><div class="pf-msg">{msg}</div>'
            f'<div class="pf-loc">{loc}</div>{hint_html}</div></div>'
        )

    border_color = '#d32f2f' if errors else '#f57c00' if warnings else '#1976d2'

    return f'''
      <div class="pf-banner" style="border-left:4px solid {border_color}; background:#fff8e1;
           padding:10px 14px; margin:0 0 12px 0; border-radius:4px; font-size:13px;"
           data-slug="{slug}">
        <div style="display:flex; justify-content:space-between; align-items:center; cursor:pointer"
             onclick="this.parentElement.classList.toggle('pf-expanded')">
          <div><strong>Preflight:</strong> {summary}</div>
          <span class="pf-toggle" style="font-size:11px; color:#666">▶ details</span>
        </div>
        <div class="pf-issues" style="display:none; margin-top:8px">
          {''.join(issue_rows)}
        </div>
      </div>'''


def generate_html(pages: list, course_tree: dict) -> str:
    """Generate the unified preview HTML document."""
    timestamp = datetime.now().strftime('%B %d, %Y at %I:%M %p')
    total_pages = len(pages)

    # Group pages by module for sidebar TOC
    modules = {}
    for page in pages:
        mod = page['module_number']
        if mod not in modules:
            modules[mod] = []
        modules[mod].append(page)

    # Build sidebar TOC entries
    toc_entries = []
    for mod_num in sorted(modules.keys()):
        mod_pages = modules[mod_num]
        # Try to get module name from course tree
        mod_name = None
        for p in mod_pages:
            meta = course_tree.get(p['slug'], {})
            if meta.get('module_name'):
                mod_name = meta['module_name']
                break
        if not mod_name:
            mod_name = f'Module {mod_num}' if mod_num < 999 else 'Uncategorized'

        # Clean module name (strip date ranges)
        mod_name_clean = re.sub(r'^\(.*?\)\s*', '', mod_name)

        toc_entries.append(f'''
        <div class="toc-module">
          <div class="toc-module-header" onclick="this.parentElement.classList.toggle('collapsed')">
            <span class="toc-arrow">▾</span>
            <span class="toc-mod-label">M{mod_num}</span>
            {_escape(mod_name_clean)}
          </div>
          <div class="toc-pages">
            {''.join(_build_toc_page_entry(p) for p in mod_pages)}
          </div>
        </div>''')

    # Build page sections
    page_sections = []
    for i, page in enumerate(pages):
        slug = page['slug']
        mod_num = page['module_number']
        meta = course_tree.get(slug, {})
        page_type, type_color = classify_page_type(slug)

        # Use course tree title if available, otherwise derive from slug
        page_title = meta.get('title') or slug_to_title(slug)
        mod_name = meta.get('module_name', f'Module {mod_num}')
        mod_name_clean = re.sub(r'^\(.*?\)\s*', '', mod_name)

        published_badge = ''
        if meta:
            pub = meta.get('published', False)
            published_badge = (
                '<span class="pub-badge pub-yes">Published</span>' if pub
                else '<span class="pub-badge pub-no">Unpublished</span>'
            )

        page_num = i + 1

        page_sections.append(f'''
    <!-- ═══════════════════ PAGE {page_num}/{total_pages} ═══════════════════ -->
    <div class="page-section" id="page-{slug}" data-slug="{slug}">
      <div class="page-header">
        <div class="page-header-top">
          <div class="page-breadcrumb">
            <label class="approval-checkbox" title="Approve this page for push">
              <input type="checkbox" class="page-approve-cb" data-slug="{slug}" onchange="updateApprovalState()">
              <span class="cb-custom"></span>
            </label>
            <span class="breadcrumb-module">Module {mod_num}</span>
            <span class="breadcrumb-sep">›</span>
            <span class="breadcrumb-type" style="color:{type_color}">{_escape(page_type)}</span>
            {published_badge}
          </div>
          <div class="page-counter">
            {page_num} of {total_pages}
            <button class="page-delete-btn" data-slug="{slug}" onclick="deleteStagedPage('{slug}')" title="Remove from staging">🗑</button>
          </div>
        </div>
        <h2 class="page-title">{_escape(page_title)}</h2>
        <div class="page-meta">
          <code class="page-slug">{slug}</code>
          <span class="page-size">{page['file_size'] // 1024}KB</span>
          <span class="page-modified">Modified {page['modified'].strftime('%b %d, %I:%M %p')}</span>
          <span class="save-status saved" data-slug="{slug}">Saved</span>
          <button class="page-push-btn" data-slug="{slug}" onclick="pushSingle('{slug}')" title="Push this page to Canvas">▲ Push</button>
        </div>
      </div>
      {_build_issue_banner(page)}
      <div class="page-canvas-frame">
        <div class="show-content user_content" contenteditable="true" data-slug="{slug}">
          {page['raw_html']}
        </div>
      </div>
    </div>''')

    # Build full HTML document
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Unified Preview — {total_pages} Staged Pages</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
  <style>
    :root {{
      --canvas-bg: #f5f5f5;
      --canvas-surface: #ffffff;
      --canvas-text: #2d3b45;
      --canvas-text-secondary: #6a7883;
      --canvas-link: #0374b5;
      --canvas-border: #c7cdd1;
      --canvas-table-head: #f5f5f5;
      --canvas-code-bg: #f8f8f8;
      --asu-maroon: #8C1D40;
      --asu-gold: #FFC627;
      --sidebar-width: 280px;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: 'Roboto', 'Helvetica Neue', Helvetica, Arial, sans-serif;
      font-size: 16px;
      line-height: 1.6;
      color: var(--canvas-text);
      background: #e8e8e8;
    }}

    /* ── Top Bar ── */
    .top-bar {{
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      height: 52px;
      background: var(--asu-maroon);
      color: white;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 24px;
      z-index: 1000;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }}
    .top-bar-title {{
      font-weight: 500;
      font-size: 15px;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .top-bar-title svg {{ opacity: 0.9; }}
    .top-bar-stats {{
      font-size: 13px;
      opacity: 0.85;
      display: flex;
      gap: 20px;
    }}
    .top-bar-stat {{ display: flex; align-items: center; gap: 5px; }}
    .top-bar-actions {{ display: flex; gap: 8px; }}
    .top-bar-btn {{
      background: rgba(255,255,255,0.15);
      border: 1px solid rgba(255,255,255,0.25);
      color: white;
      padding: 5px 14px;
      border-radius: 4px;
      font-size: 13px;
      cursor: pointer;
      font-family: inherit;
    }}
    .top-bar-btn:hover {{ background: rgba(255,255,255,0.25); }}

    /* ── Sidebar TOC ── */
    .sidebar {{
      position: fixed;
      top: 52px;
      left: 0;
      bottom: 0;
      width: var(--sidebar-width);
      background: #fff;
      border-right: 1px solid var(--canvas-border);
      overflow-y: auto;
      z-index: 900;
      padding: 16px 0;
    }}
    .sidebar-header {{
      padding: 0 16px 12px;
      border-bottom: 1px solid #eee;
      margin-bottom: 8px;
    }}
    .sidebar-header h3 {{
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--canvas-text-secondary);
    }}
    .sidebar-search {{
      width: 100%;
      padding: 7px 10px;
      border: 1px solid var(--canvas-border);
      border-radius: 4px;
      font-size: 13px;
      margin-top: 8px;
      font-family: inherit;
      outline: none;
    }}
    .sidebar-search:focus {{ border-color: var(--canvas-link); }}

    .toc-module {{ margin-bottom: 4px; }}
    .toc-module-header {{
      padding: 8px 16px;
      font-size: 13px;
      font-weight: 500;
      color: var(--canvas-text);
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      user-select: none;
    }}
    .toc-module-header:hover {{ background: #f7f7f7; }}
    .toc-arrow {{
      font-size: 10px;
      transition: transform 0.15s;
      color: var(--canvas-text-secondary);
    }}
    .toc-module.collapsed .toc-arrow {{ transform: rotate(-90deg); }}
    .toc-module.collapsed .toc-pages {{ display: none; }}
    .toc-mod-label {{
      background: var(--asu-maroon);
      color: white;
      font-size: 10px;
      padding: 1px 6px;
      border-radius: 3px;
      font-weight: 600;
    }}
    .toc-pages {{ padding: 2px 0 6px; }}
    .toc-page {{
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 5px 16px 5px 38px;
      font-size: 12.5px;
      color: var(--canvas-text);
      text-decoration: none;
      line-height: 1.3;
    }}
    .toc-page:hover {{ background: #f0f4ff; color: var(--canvas-link); }}
    .toc-page.active {{ background: #e8f0fe; color: var(--canvas-link); font-weight: 500; }}
    .toc-type-dot {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
    }}

    /* ── Preflight Badges (TOC) ── */
    .pf-badge {{
      font-size: 10px;
      font-weight: 700;
      min-width: 16px;
      height: 16px;
      line-height: 16px;
      text-align: center;
      border-radius: 8px;
      padding: 0 4px;
      margin-left: auto;
      flex-shrink: 0;
    }}
    .pf-error {{ background: #ffcdd2; color: #c62828; }}
    .pf-warn {{ background: #fff3e0; color: #e65100; }}
    .pf-info {{ background: #e3f2fd; color: #1565c0; }}
    .pf-pass {{ background: #e8f5e9; color: #2e7d32; font-size: 9px; }}

    /* ── Preflight Banner (inline) ── */
    .pf-banner .pf-issues {{ display: none; }}
    .pf-banner.pf-expanded .pf-issues {{ display: block !important; }}
    .pf-banner.pf-expanded .pf-toggle {{ transform: rotate(90deg); }}
    .pf-issue {{
      display: flex;
      align-items: flex-start;
      gap: 8px;
      padding: 6px 0;
      border-bottom: 1px solid #f0e6c8;
    }}
    .pf-issue:last-child {{ border-bottom: none; }}
    .pf-icon {{ flex-shrink: 0; font-size: 14px; }}
    .pf-detail {{ flex: 1; }}
    .pf-msg {{ font-weight: 500; color: #333; }}
    .pf-loc {{ font-size: 11px; color: #888; font-family: 'JetBrains Mono', monospace; }}
    .pf-hint {{ font-size: 12px; color: #555; margin-top: 2px; font-style: italic; }}
    .pf-error .pf-msg {{ color: #c62828; }}
    .pf-warn .pf-msg {{ color: #e65100; }}

    /* ── Main Content Area ── */
    .main {{
      margin-left: var(--sidebar-width);
      margin-top: 52px;
      padding: 32px 40px 80px;
    }}

    /* ── Page Section (each staged page) ── */
    .page-section {{
      background: var(--canvas-surface);
      border: 1px solid var(--canvas-border);
      border-radius: 6px;
      margin-bottom: 40px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.06);
      scroll-margin-top: 68px;
    }}

    .page-header {{
      padding: 16px 24px;
      border-bottom: 2px solid #eee;
      background: #fafbfc;
      border-radius: 6px 6px 0 0;
    }}
    .page-header-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }}
    .page-breadcrumb {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
    }}
    .breadcrumb-module {{
      background: var(--asu-maroon);
      color: white;
      padding: 2px 10px;
      border-radius: 3px;
      font-weight: 600;
      font-size: 12px;
    }}
    .breadcrumb-sep {{ color: #ccc; font-size: 16px; }}
    .breadcrumb-type {{ font-weight: 500; }}
    .pub-badge {{
      font-size: 11px;
      padding: 1px 8px;
      border-radius: 10px;
      font-weight: 500;
      margin-left: 8px;
    }}
    .pub-yes {{ background: #e6f4ea; color: #1e7e34; }}
    .pub-no {{ background: #fef3e5; color: #b5540a; }}

    .page-counter {{
      font-size: 12px;
      color: var(--canvas-text-secondary);
      font-weight: 500;
    }}
    .page-title {{
      font-size: 1.3em;
      font-weight: 500;
      color: var(--canvas-text);
      margin: 4px 0 8px;
    }}
    .page-meta {{
      display: flex;
      gap: 16px;
      align-items: center;
      font-size: 12px;
      color: var(--canvas-text-secondary);
    }}
    .page-slug {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 11.5px;
      background: var(--canvas-code-bg);
      padding: 2px 8px;
      border-radius: 3px;
      border: 1px solid #e5e5e5;
    }}

    /* ── Canvas Content Frame ── */
    .page-canvas-frame {{
      padding: 24px 32px 32px;
      max-width: 100%;
      overflow-x: auto;
    }}

    /* ── Canvas user_content styles (from canvas-shell.html) ── */
    .show-content h1 {{ font-size: 1.75em; font-weight: 500; margin: 0.5em 0; color: var(--canvas-text); }}
    .show-content h2 {{ font-size: 1.5em; font-weight: 500; margin: 1em 0 0.5em; color: var(--canvas-text); }}
    .show-content h3 {{ font-size: 1.25em; font-weight: 500; margin: 1em 0 0.5em; color: var(--canvas-text); }}
    .show-content h4 {{ font-size: 1.1em; font-weight: 500; margin: 1em 0 0.5em; color: var(--canvas-text); }}
    .show-content h5 {{ font-size: 1em; font-weight: 700; margin: 1em 0 0.5em; }}
    .show-content h6 {{ font-size: 0.9em; font-weight: 700; margin: 1em 0 0.5em; color: var(--canvas-text-secondary); }}
    .show-content p {{ margin: 0 0 1em; }}
    .show-content a {{ color: var(--canvas-link); text-decoration: none; }}
    .show-content a:hover {{ text-decoration: underline; }}
    .show-content ul, .show-content ol {{ margin: 0 0 1em 1.5em; }}
    .show-content li {{ margin: 0.25em 0; }}
    .show-content blockquote {{
      border-left: 4px solid var(--canvas-border);
      margin: 1em 0;
      padding: 0.5em 1em;
      color: var(--canvas-text-secondary);
    }}
    .show-content table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
    .show-content th, .show-content td {{
      border: 1px solid var(--canvas-border);
      padding: 8px 12px;
      text-align: left;
    }}
    .show-content th {{ background: var(--canvas-table-head); font-weight: 500; }}
    .show-content img {{ max-width: 100%; height: auto; }}
    .show-content code {{
      background: var(--canvas-code-bg);
      padding: 2px 6px;
      border-radius: 3px;
      font-size: 0.9em;
    }}
    .show-content pre {{
      background: var(--canvas-code-bg);
      padding: 12px;
      border-radius: 4px;
      overflow-x: auto;
      margin: 1em 0;
    }}
    .show-content pre code {{ background: none; padding: 0; }}
    .show-content hr {{
      border: none;
      border-top: 1px solid var(--canvas-border);
      margin: 1.5em 0;
    }}
    .show-content iframe {{
      max-width: 100%;
      border: 1px solid var(--canvas-border);
      border-radius: 4px;
    }}

    /* ── Approval Checkboxes ── */
    .approval-checkbox {{
      display: flex;
      align-items: center;
      cursor: pointer;
      margin-right: 4px;
    }}
    .approval-checkbox input {{ display: none; }}
    .cb-custom {{
      width: 20px;
      height: 20px;
      border: 2px solid var(--canvas-border);
      border-radius: 4px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.15s;
      background: white;
    }}
    .cb-custom:hover {{ border-color: var(--canvas-link); }}
    .approval-checkbox input:checked + .cb-custom {{
      background: #1e7e34;
      border-color: #1e7e34;
    }}
    .approval-checkbox input:checked + .cb-custom::after {{
      content: '\\2713';
      color: white;
      font-size: 14px;
      font-weight: 700;
    }}
    .page-section.approved {{
      border-color: #1e7e34;
      box-shadow: 0 0 0 2px rgba(30,126,52,0.15), 0 1px 4px rgba(0,0,0,0.06);
    }}
    .page-section.approved .page-header {{
      background: #f0faf3;
      border-bottom-color: #c8e6c9;
    }}

    /* ── Sticky Action Bar ── */
    .action-bar {{
      position: fixed;
      bottom: -80px;
      left: var(--sidebar-width);
      right: 0;
      height: 64px;
      background: white;
      border-top: 2px solid var(--asu-maroon);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 32px;
      z-index: 1000;
      box-shadow: 0 -4px 12px rgba(0,0,0,0.1);
      transition: bottom 0.25s ease;
    }}
    .action-bar.visible {{ bottom: 0; }}
    .action-bar-left {{
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .action-bar-count {{
      font-size: 14px;
      font-weight: 500;
      color: var(--canvas-text);
    }}
    .action-bar-count strong {{
      color: #1e7e34;
      font-size: 18px;
    }}
    .action-bar-select-btns {{
      display: flex;
      gap: 6px;
    }}
    .action-bar-select-btn {{
      background: none;
      border: 1px solid var(--canvas-border);
      color: var(--canvas-text-secondary);
      padding: 4px 10px;
      border-radius: 3px;
      font-size: 12px;
      cursor: pointer;
      font-family: inherit;
    }}
    .action-bar-select-btn:hover {{ background: #f5f5f5; }}
    .action-bar-delete-btn {{
      padding: 6px 14px;
      border-radius: 6px;
      border: 1px solid #c62828;
      background: white;
      color: #c62828;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      transition: background 0.15s, color 0.15s;
    }}
    .action-bar-delete-btn:hover {{ background: #c62828; color: white; }}
    .action-bar-delete-btn:disabled {{ border-color: #ccc; color: #ccc; cursor: not-allowed; background: white; }}
    .action-bar-right {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .push-btn {{
      background: #1e7e34;
      color: white;
      border: none;
      padding: 10px 28px;
      border-radius: 5px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      font-family: inherit;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: background 0.15s;
    }}
    .push-btn:hover {{ background: #166b29; }}
    .push-btn:disabled {{ background: #ccc; cursor: not-allowed; }}
    .push-btn svg {{ stroke: currentColor; fill: none; }}
    .export-btn {{
      background: var(--canvas-link);
      color: white;
      border: none;
      padding: 10px 20px;
      border-radius: 5px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      font-family: inherit;
    }}
    .export-btn:hover {{ background: #025d91; }}

    /* Toast notification */
    .toast {{
      position: fixed;
      top: 68px;
      right: 24px;
      background: #1e7e34;
      color: white;
      padding: 12px 24px;
      border-radius: 6px;
      font-size: 14px;
      font-weight: 500;
      z-index: 2000;
      opacity: 0;
      transform: translateY(-10px);
      transition: all 0.3s;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }}
    .toast.show {{ opacity: 1; transform: translateY(0); }}
    .toast.error {{ background: #c62828; }}

    /* ── Page Separator (visual break between pages) ── */
    .page-separator {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 16px;
      margin: 8px 0 32px;
      color: #bbb;
      font-size: 12px;
    }}
    .page-separator::before,
    .page-separator::after {{
      content: '';
      flex: 1;
      height: 1px;
      background: repeating-linear-gradient(90deg, #ddd 0px, #ddd 4px, transparent 4px, transparent 8px);
    }}

    /* ── Scroll Progress ── */
    .scroll-progress {{
      position: fixed;
      top: 52px;
      left: var(--sidebar-width);
      right: 0;
      height: 3px;
      z-index: 999;
      background: #eee;
    }}
    .scroll-progress-bar {{
      height: 100%;
      background: var(--asu-gold);
      width: 0%;
      transition: width 0.1s;
    }}

    /* ── Back to Top Button ── */
    .back-to-top {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background: var(--asu-maroon);
      color: white;
      border: none;
      cursor: pointer;
      display: none;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 8px rgba(0,0,0,0.2);
      font-size: 20px;
      z-index: 999;
    }}
    .back-to-top.visible {{ display: flex; }}
    .back-to-top:hover {{ background: #6a1530; }}

    /* ── Print Styles ── */
    @media print {{
      .sidebar, .top-bar, .scroll-progress, .back-to-top, .action-bar, .approval-checkbox, .toast, dialog {{ display: none !important; }}
      .main {{ margin-left: 0; margin-top: 0; padding: 0; }}
      .page-section {{ break-inside: avoid; box-shadow: none; border: 1px solid #ccc; margin-bottom: 24px; }}
    }}

    /* ── Responsive ── */
    @media (max-width: 900px) {{
      .sidebar {{ display: none; }}
      .main {{ margin-left: 0; }}
      .scroll-progress {{ left: 0; }}
      .action-bar {{ left: 0; }}
    }}

    /* ── Editing: Formatting Toolbar ── */
    #formatToolbar {{
      position: fixed;
      top: -9999px;
      left: 0;
      background: #2d3b45;
      border-radius: 6px;
      padding: 4px;
      display: flex;
      gap: 2px;
      z-index: 2000;
      box-shadow: 0 4px 16px rgba(0,0,0,0.25);
      opacity: 0;
      transition: opacity 0.15s;
    }}
    #formatToolbar.visible {{ opacity: 1; }}
    #formatToolbar button {{
      background: none;
      border: none;
      color: white;
      width: 32px;
      height: 28px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 13px;
      font-family: inherit;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    #formatToolbar button:hover {{ background: rgba(255,255,255,0.15); }}
    #formatToolbar button.active {{ background: rgba(255,255,255,0.25); }}
    #formatToolbar .tb-sep {{
      width: 1px;
      background: rgba(255,255,255,0.2);
      margin: 2px 4px;
    }}

    /* ── Editing: Save Status ── */
    .save-status {{
      font-size: 11px;
      padding: 1px 8px;
      border-radius: 10px;
      font-weight: 500;
    }}
    .save-status.saved {{ color: #1e7e34; }}
    .save-status.dirty {{ color: #b5540a; }}
    .save-status.saving {{ color: #0374b5; }}

    /* ── Editing: Per-page Push Button ── */
    .page-push-btn {{
      background: var(--asu-maroon);
      color: white;
      border: none;
      padding: 2px 10px;
      border-radius: 3px;
      font-size: 11px;
      cursor: pointer;
      font-family: inherit;
      font-weight: 500;
      opacity: 0.8;
    }}
    .page-push-btn:hover {{ opacity: 1; }}

    /* ── Editing: Contenteditable focus ── */
    .show-content[contenteditable]:focus {{
      outline: 2px solid var(--canvas-link);
      outline-offset: -2px;
      border-radius: 4px;
    }}

    /* ── Drag and Drop ── */
    [data-drag-block] {{
      position: relative;
      transition: transform 0.15s ease, opacity 0.15s ease;
    }}
    .drag-handle-bar {{
      position: absolute;
      left: -32px;
      top: 0;
      width: 24px;
      height: 100%;
      cursor: grab;
      opacity: 0;
      display: flex;
      align-items: flex-start;
      padding-top: 6px;
      justify-content: center;
      transition: opacity 0.2s;
      z-index: 10;
    }}
    [data-drag-block]:hover .drag-handle-bar {{ opacity: 0.4; }}
    .drag-handle-bar:hover {{ opacity: 1 !important; cursor: grab; }}
    .drag-handle-bar::before {{
      content: '';
      display: grid;
      grid-template-columns: repeat(2, 4px);
      grid-template-rows: repeat(3, 4px);
      gap: 2px;
      width: 10px;
      height: 16px;
    }}
    .drag-handle-bar::after {{
      content: none;
    }}
    .drag-handle-dot {{
      display: none;
    }}
    /* Six-dot grip icon via box-shadow */
    .drag-handle-bar::before {{
      content: '';
      width: 4px;
      height: 4px;
      border-radius: 50%;
      background: #999;
      box-shadow:
        6px 0 0 #999,
        0 6px 0 #999,
        6px 6px 0 #999,
        0 12px 0 #999,
        6px 12px 0 #999;
    }}
    .drag-placeholder {{
      border: 2px dashed var(--asu-gold);
      background: rgba(255,198,39,0.08);
      border-radius: 4px;
      min-height: 8px;
      margin: 2px 0;
      transition: height 0.15s ease;
    }}
    [data-drag-block].dragging {{
      opacity: 0.85;
      box-shadow: 0 8px 24px rgba(0,0,0,0.18);
      border-radius: 4px;
      background: white;
      transition: none;
    }}

    /* ── Delete button ── */
    .page-delete-btn {{
      background: none;
      border: 1px solid #ddd;
      cursor: pointer;
      font-size: 14px;
      opacity: 0.7;
      padding: 2px 6px;
      border-radius: 3px;
      transition: all 0.15s;
      vertical-align: middle;
      margin-left: 6px;
    }}
    .page-delete-btn:hover {{ opacity: 1; background: #fde8e8; border-color: #c62828; }}

    /* ── Pushed state ── */
    .page-section.pushed {{
      border-color: var(--asu-maroon);
    }}
    .page-section.pushed .page-header::after {{
      content: '\\2713  Pushed';
      position: absolute;
      right: 24px;
      top: 16px;
      background: var(--asu-maroon);
      color: white;
      padding: 2px 10px;
      border-radius: 3px;
      font-size: 11px;
      font-weight: 600;
    }}
    .page-header {{ position: relative; }}
  </style>
</head>
<body>

  <!-- Top Bar -->
  <header class="top-bar">
    <div class="top-bar-title">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="16" y1="13" x2="8" y2="13"/>
        <line x1="16" y1="17" x2="8" y2="17"/>
      </svg>
      Unified Staging Preview
    </div>
    <div class="top-bar-stats">
      <span class="top-bar-stat">📄 {total_pages} pages</span>
      <span class="top-bar-stat">📦 {len(modules)} modules</span>
      <span class="top-bar-stat">🕐 {timestamp}</span>
    </div>
    <div class="top-bar-actions">
      <button class="top-bar-btn" onclick="window.print()" title="Print / Save PDF">🖨 Print</button>
      <button class="top-bar-btn" onclick="toggleAllModules()" title="Expand/Collapse TOC">☰ TOC</button>
    </div>
  </header>

  <!-- Scroll Progress -->
  <div class="scroll-progress">
    <div class="scroll-progress-bar" id="progressBar"></div>
  </div>

  <!-- Sidebar TOC -->
  <nav class="sidebar">
    <div class="sidebar-header">
      <h3>Table of Contents</h3>
      <input type="text" class="sidebar-search" placeholder="Filter pages..." id="tocSearch" oninput="filterToc(this.value)">
    </div>
    {''.join(toc_entries)}
  </nav>

  <!-- Main Content -->
  <main class="main">
    {''.join(page_sections)}
  </main>

  <!-- Approval Action Bar -->
  <div class="action-bar" id="actionBar">
    <div class="action-bar-left">
      <div class="action-bar-count">
        <strong id="approvedCount">0</strong> of {total_pages} pages approved
      </div>
      <div class="action-bar-select-btns">
        <button class="action-bar-select-btn" onclick="selectAll()">Select All</button>
        <button class="action-bar-select-btn" onclick="selectNone()">Deselect All</button>
        <button class="action-bar-select-btn" onclick="selectByModule()">Select by Module...</button>
        <button class="action-bar-delete-btn" id="deleteSelectedBtn" onclick="deleteSelected()" disabled title="Delete selected staged files (does not affect Canvas)">🗑 Delete Selected</button>
      </div>
    </div>
    <div class="action-bar-right">
      <button class="export-btn" onclick="exportApprovalList()" title="Copy approved slugs to clipboard">📋 Copy Slugs</button>
      <button class="push-btn" id="pushBtn" onclick="pushApproved()" disabled>
        <svg width="16" height="16" viewBox="0 0 24 24" stroke-width="2"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
        Push Approved to Canvas
      </button>
    </div>
  </div>

  <!-- Toast -->
  <div class="toast" id="toast"></div>

  <!-- Formatting Toolbar -->
  <div id="formatToolbar">
    <button onclick="fmt('bold')" title="Bold (Ctrl+B)"><b>B</b></button>
    <button onclick="fmt('italic')" title="Italic (Ctrl+I)"><i>I</i></button>
    <div class="tb-sep"></div>
    <button onclick="fmt('formatBlock','<h2>')" title="Heading 2">H2</button>
    <button onclick="fmt('formatBlock','<h3>')" title="Heading 3">H3</button>
    <button onclick="fmt('formatBlock','<h4>')" title="Heading 4">H4</button>
    <button onclick="fmt('formatBlock','<p>')" title="Paragraph">P</button>
    <div class="tb-sep"></div>
    <button onclick="fmt('insertUnorderedList')" title="Bullet List">&#8226;</button>
    <button onclick="fmt('insertOrderedList')" title="Numbered List">1.</button>
    <div class="tb-sep"></div>
    <button onclick="insertLink()" title="Insert Link">&#128279;</button>
    <div class="tb-sep"></div>
    <button onclick="document.execCommand('undo')" title="Undo">&#8617;</button>
    <button onclick="document.execCommand('redo')" title="Redo">&#8618;</button>
  </div>

  <!-- Module Select Dialog -->
  <dialog id="moduleDialog" style="border:1px solid #ccc;border-radius:8px;padding:24px;min-width:280px;box-shadow:0 8px 32px rgba(0,0,0,0.15)">
    <h3 style="margin:0 0 12px;font-size:15px;color:#2d3b45">Select Module</h3>
    <div id="moduleDialogList" style="display:flex;flex-direction:column;gap:6px;margin-bottom:16px"></div>
    <div style="display:flex;gap:8px;justify-content:flex-end">
      <button onclick="document.getElementById('moduleDialog').close()" style="padding:6px 16px;border:1px solid #ccc;border-radius:4px;background:white;cursor:pointer;font-family:inherit">Cancel</button>
    </div>
  </dialog>

  <!-- Back to Top -->
  <button class="back-to-top" id="backToTop" onclick="window.scrollTo({{top:0,behavior:'smooth'}})">↑</button>

  <script>
    const API_BASE = 'http://localhost:3847';
    const TOTAL_PAGES = {total_pages};

    // ── Scroll progress ──
    window.addEventListener('scroll', () => {{
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      const progress = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
      document.getElementById('progressBar').style.width = progress + '%';
      document.getElementById('backToTop').classList.toggle('visible', scrollTop > 400);
    }});

    // ── TOC highlighting ──
    const pageSections = document.querySelectorAll('.page-section');
    const tocLinks = document.querySelectorAll('.toc-page');
    const observer = new IntersectionObserver((entries) => {{
      entries.forEach(entry => {{
        if (entry.isIntersecting) {{
          const id = entry.target.id;
          tocLinks.forEach(link => {{
            link.classList.toggle('active', link.getAttribute('href') === '#' + id);
          }});
          const activeLink = document.querySelector('.toc-page.active');
          if (activeLink) activeLink.scrollIntoView({{ block: 'nearest', behavior: 'smooth' }});
        }}
      }});
    }}, {{ rootMargin: '-80px 0px -60% 0px', threshold: 0.1 }});
    pageSections.forEach(s => observer.observe(s));

    tocLinks.forEach(link => {{
      link.addEventListener('click', (e) => {{
        e.preventDefault();
        const target = document.querySelector(link.getAttribute('href'));
        if (target) target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
      }});
    }});

    // ── TOC filter ──
    function filterToc(query) {{
      const q = query.toLowerCase();
      document.querySelectorAll('.toc-module').forEach(mod => {{
        const pages = mod.querySelectorAll('.toc-page');
        let anyVisible = false;
        pages.forEach(page => {{
          const text = page.textContent.toLowerCase();
          const visible = !q || text.includes(q);
          page.style.display = visible ? '' : 'none';
          if (visible) anyVisible = true;
        }});
        mod.style.display = anyVisible ? '' : 'none';
        if (q && anyVisible) mod.classList.remove('collapsed');
      }});
    }}

    let allCollapsed = false;
    function toggleAllModules() {{
      allCollapsed = !allCollapsed;
      document.querySelectorAll('.toc-module').forEach(mod => {{
        mod.classList.toggle('collapsed', allCollapsed);
      }});
    }}

    // ── Approval system ──
    function updateApprovalState() {{
      const checkboxes = document.querySelectorAll('.page-approve-cb');
      let count = 0;
      const approved = [];
      checkboxes.forEach(cb => {{
        const section = cb.closest('.page-section');
        if (cb.checked) {{
          count++;
          approved.push(cb.dataset.slug);
          section.classList.add('approved');
        }} else {{
          section.classList.remove('approved');
        }}
      }});
      document.getElementById('approvedCount').textContent = count;
      document.getElementById('pushBtn').disabled = count === 0;
      document.getElementById('deleteSelectedBtn').disabled = count === 0;
      document.getElementById('actionBar').classList.toggle('visible', count > 0);
      localStorage.setItem('idw_approved_pages', JSON.stringify(approved));
    }}

    function selectAll() {{
      document.querySelectorAll('.page-approve-cb').forEach(cb => cb.checked = true);
      updateApprovalState();
    }}
    function selectNone() {{
      document.querySelectorAll('.page-approve-cb').forEach(cb => cb.checked = false);
      updateApprovalState();
    }}
    function selectByModule() {{
      const dialog = document.getElementById('moduleDialog');
      const list = document.getElementById('moduleDialogList');
      list.innerHTML = '';
      const modules = new Map();
      document.querySelectorAll('.page-section').forEach(s => {{
        const slug = s.dataset.slug;
        const modMatch = slug.match(/^m([0-9]+)/);
        const mod = modMatch ? modMatch[1] : '?';
        if (!modules.has(mod)) modules.set(mod, []);
        modules.get(mod).push(slug);
      }});
      [...modules.entries()].sort((a,b) => parseInt(a[0]) - parseInt(b[0])).forEach(([mod, slugs]) => {{
        const btn = document.createElement('button');
        btn.textContent = `Module ${{mod}} (${{slugs.length}} pages)`;
        btn.style.cssText = 'padding:8px 14px;border:1px solid #ddd;border-radius:4px;background:#fafbfc;cursor:pointer;text-align:left;font-family:inherit;font-size:13px';
        btn.onmouseover = () => btn.style.background = '#e8f0fe';
        btn.onmouseout = () => btn.style.background = '#fafbfc';
        btn.onclick = () => {{
          slugs.forEach(slug => {{
            const cb = document.querySelector(`.page-approve-cb[data-slug="${{slug}}"]`);
            if (cb) cb.checked = true;
          }});
          updateApprovalState();
          dialog.close();
        }};
        list.appendChild(btn);
      }});
      dialog.showModal();
    }}

    function exportApprovalList() {{
      const approved = [];
      document.querySelectorAll('.page-approve-cb:checked').forEach(cb => approved.push(cb.dataset.slug));
      if (approved.length === 0) return;
      navigator.clipboard.writeText(approved.join('\\n')).then(() => {{
        showToast(`${{approved.length}} slug(s) copied to clipboard`);
      }});
    }}

    // ── Toast ──
    function showToast(message, isError = false) {{
      const toast = document.getElementById('toast');
      toast.textContent = message;
      toast.classList.toggle('error', isError);
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 4000);
    }}

    // ── Formatting Toolbar ──
    function fmt(command, value) {{
      document.execCommand(command, false, value || null);
    }}

    function insertLink() {{
      const url = prompt('Enter URL:');
      if (url) document.execCommand('createLink', false, url);
    }}

    const toolbar = document.getElementById('formatToolbar');
    let toolbarTimeout;

    function positionToolbar() {{
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || !sel.rangeCount) {{
        toolbar.classList.remove('visible');
        toolbar.style.top = '-9999px';
        return;
      }}
      const el = sel.anchorNode?.parentElement?.closest?.('[contenteditable]');
      if (!el) {{
        toolbar.classList.remove('visible');
        toolbar.style.top = '-9999px';
        return;
      }}
      const rect = sel.getRangeAt(0).getBoundingClientRect();
      toolbar.style.top = (rect.top - 40 + window.scrollY) + 'px';
      toolbar.style.left = Math.max(8, rect.left + rect.width/2 - toolbar.offsetWidth/2) + 'px';
      toolbar.classList.add('visible');
    }}

    document.addEventListener('selectionchange', () => {{
      clearTimeout(toolbarTimeout);
      toolbarTimeout = setTimeout(positionToolbar, 150);
    }});

    // Hide toolbar when clicking outside
    document.addEventListener('mousedown', (e) => {{
      if (!toolbar.contains(e.target) && !e.target.closest('[contenteditable]')) {{
        toolbar.classList.remove('visible');
        toolbar.style.top = '-9999px';
      }}
    }});

    // ── Auto-save ──
    const saveTimers = {{}};

    function markDirty(slug) {{
      const el = document.querySelector(`.save-status[data-slug="${{slug}}"]`);
      if (el) {{ el.textContent = 'Unsaved...'; el.className = 'save-status dirty'; }}
    }}
    function markSaved(slug) {{
      const el = document.querySelector(`.save-status[data-slug="${{slug}}"]`);
      if (el) {{ el.textContent = 'Saved'; el.className = 'save-status saved'; }}
    }}
    function markSaving(slug) {{
      const el = document.querySelector(`.save-status[data-slug="${{slug}}"]`);
      if (el) {{ el.textContent = 'Saving...'; el.className = 'save-status saving'; }}
    }}

    function getCleanHtml(contentEl) {{
      const clone = contentEl.cloneNode(true);
      clone.querySelectorAll('.drag-handle-bar').forEach(h => h.remove());
      clone.querySelectorAll('[data-drag-block]').forEach(el => {{
        el.removeAttribute('data-drag-block');
        el.classList.remove('dragging');
      }});
      return clone.innerHTML;
    }}

    function scheduleSave(slug) {{
      clearTimeout(saveTimers[slug]);
      saveTimers[slug] = setTimeout(() => saveToStaging(slug), 1000);
    }}

    async function saveToStaging(slug) {{
      const el = document.querySelector(`.show-content[data-slug="${{slug}}"]`);
      if (!el) return;
      const html = getCleanHtml(el);
      markSaving(slug);
      try {{
        const resp = await fetch(`${{API_BASE}}/api/staging/${{slug}}`, {{
          method: 'PUT',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ html }})
        }});
        const data = await resp.json();
        if (data.ok) markSaved(slug);
        else {{ markDirty(slug); showToast(`Save failed for ${{slug}}`, true); }}
      }} catch (e) {{
        markDirty(slug);
        showToast(`Save error: ${{e.message}}. Is content-studio running on port 3847?`, true);
      }}
    }}

    async function flushAllSaves() {{
      const promises = [];
      Object.keys(saveTimers).forEach(slug => {{
        clearTimeout(saveTimers[slug]);
        delete saveTimers[slug];
        promises.push(saveToStaging(slug));
      }});
      await Promise.all(promises);
    }}

    // Hook input events on all contenteditable areas
    document.querySelectorAll('.show-content[contenteditable]').forEach(el => {{
      el.addEventListener('input', () => {{
        markDirty(el.dataset.slug);
        scheduleSave(el.dataset.slug);
      }});
    }});

    // Warn before leaving with unsaved changes
    window.addEventListener('beforeunload', (e) => {{
      const hasDirty = document.querySelector('.save-status.dirty');
      if (hasDirty) {{
        e.preventDefault();
        e.returnValue = '';
      }}
    }});

    // ── Push to Canvas ──
    async function pushSingle(slug) {{
      if (!confirm(`Push "${{slug}}" to Canvas?`)) return;
      await flushAllSaves();
      const btn = document.querySelector(`.page-push-btn[data-slug="${{slug}}"]`);
      if (btn) {{ btn.textContent = '\u23F3...'; btn.disabled = true; }}
      try {{
        const resp = await fetch(`${{API_BASE}}/api/push/${{slug}}`, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }}
        }});
        const data = await resp.json();
        if (data.ok) {{
          showToast(`Pushed ${{slug}} to Canvas \u2713`);
          const section = document.getElementById(`page-${{slug}}`);
          if (section) section.classList.add('pushed');
        }} else {{
          showToast(`Push failed: ${{data.error || 'Unknown error'}}`, true);
        }}
      }} catch (e) {{
        showToast(`Push error: ${{e.message}}`, true);
      }} finally {{
        if (btn) {{ btn.textContent = '\u25B2 Push'; btn.disabled = false; }}
      }}
    }}

    async function pushApproved() {{
      const approved = [];
      document.querySelectorAll('.page-approve-cb:checked').forEach(cb => approved.push(cb.dataset.slug));
      if (approved.length === 0) return;
      if (!confirm(`Push ${{approved.length}} page(s) to Canvas?`)) return;

      await flushAllSaves();
      const pushBtn = document.getElementById('pushBtn');
      pushBtn.disabled = true;
      pushBtn.innerHTML = '\u23F3 Pushing...';

      try {{
        const resp = await fetch(`${{API_BASE}}/api/push/batch`, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ slugs: approved }})
        }});
        const data = await resp.json();
        if (data.summary) {{
          showToast(`Pushed ${{data.summary.succeeded}}/${{data.summary.total}} pages to Canvas`);
          data.results.forEach(r => {{
            if (r.ok) {{
              const section = document.getElementById(`page-${{r.slug}}`);
              if (section) section.classList.add('pushed');
            }}
          }});
        }}
      }} catch (e) {{
        showToast(`Push failed: ${{e.message}}`, true);
      }} finally {{
        pushBtn.disabled = false;
        pushBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path d="M12 19V5M5 12l7-7 7 7"/></svg> Push Approved to Canvas';
      }}
    }}

    // ── Delete staged page ──
    async function deleteStagedPage(slug) {{
      if (!confirm(`Remove "${{slug}}" from staging? This only deletes the local staged file — it does NOT delete anything from Canvas.`)) return;
      try {{
        const resp = await fetch(`${{API_BASE}}/api/staging/${{slug}}`, {{
          method: 'DELETE',
          headers: {{ 'Content-Type': 'application/json' }}
        }});
        const data = await resp.json();
        if (data.ok) {{
          // Remove the page section from DOM with animation
          const section = document.getElementById(`page-${{slug}}`);
          if (section) {{
            section.style.transition = 'opacity 0.3s, transform 0.3s';
            section.style.opacity = '0';
            section.style.transform = 'scale(0.95)';
            setTimeout(() => section.remove(), 300);
          }}
          // Remove from TOC
          const tocLink = document.querySelector(`.toc-page[href="#page-${{slug}}"]`);
          if (tocLink) tocLink.remove();
          showToast(`Removed ${{slug}} — reloading preview...`);
          setTimeout(() => rebuildAndReload(), 500);
        }} else {{
          showToast(`Delete failed: ${{data.error || 'Unknown error'}}`, true);
        }}
      }} catch (e) {{
        showToast(`Delete error: ${{e.message}}`, true);
      }}
    }}

    async function rebuildAndReload() {{
      try {{
        await fetch(`${{API_BASE}}/api/rebuild-preview`, {{ method: 'POST' }});
      }} catch(e) {{}}
      window.location.href = '/_unified_preview.html';
    }}

    async function deleteSelected() {{
      const selected = [];
      document.querySelectorAll('.page-approve-cb:checked').forEach(cb => selected.push(cb.dataset.slug));
      if (selected.length === 0) return;
      if (!confirm(`Remove ${{selected.length}} staged file(s) from staging?\\n\\n${{selected.join('\\n')}}\\n\\nThis only deletes local staged files — nothing is removed from Canvas.`)) return;
      let deleted = 0, failed = 0;
      for (const slug of selected) {{
        try {{
          const resp = await fetch(`${{API_BASE}}/api/staging/${{slug}}`, {{
            method: 'DELETE',
            headers: {{ 'Content-Type': 'application/json' }}
          }});
          const data = await resp.json();
          if (data.ok) {{
            const section = document.getElementById(`page-${{slug}}`);
            if (section) {{
              section.style.transition = 'opacity 0.3s, transform 0.3s';
              section.style.opacity = '0';
              section.style.transform = 'scale(0.95)';
              setTimeout(() => section.remove(), 300);
            }}
            const tocLink = document.querySelector(`.toc-page[href="#page-${{slug}}"]`);
            if (tocLink) tocLink.remove();
            deleted++;
          }} else {{ failed++; }}
        }} catch (e) {{ failed++; }}
      }}
      const msg = failed > 0
        ? `Deleted ${{deleted}}, failed ${{failed}} — reloading preview...`
        : `Deleted ${{deleted}} staged file(s) — reloading preview...`;
      showToast(msg, failed > 0);
      setTimeout(() => rebuildAndReload(), 500);
    }}

    // ── Drag and Drop (per page card) ──
    function attachDragHandlesForPage(contentEl) {{
      contentEl.querySelectorAll('.drag-handle-bar').forEach(h => h.remove());
      contentEl.querySelectorAll('[data-drag-block]').forEach(el => el.removeAttribute('data-drag-block'));
      const children = [...contentEl.children];
      children.forEach(child => {{
        if (child.tagName === 'BR' || child.tagName === 'SPAN' || child.classList.contains('drag-handle-bar') || child.classList.contains('drag-placeholder')) return;
        child.setAttribute('data-drag-block', 'true');
        const handle = document.createElement('div');
        handle.className = 'drag-handle-bar';
        handle.setAttribute('contenteditable', 'false');
        child.insertBefore(handle, child.firstChild);
      }});
    }}

    let dragState = {{ target: null, placeholder: null, container: null, animFrame: null }};

    document.addEventListener('mousedown', (e) => {{
      const handle = e.target.closest('.drag-handle-bar');
      if (!handle) return;
      e.preventDefault();
      e.stopPropagation();
      const block = handle.parentElement;
      const container = block.closest('.show-content[contenteditable]');
      if (!container) return;

      container.setAttribute('contenteditable', 'false');

      const rect = block.getBoundingClientRect();
      const containerRect = container.getBoundingClientRect();

      // Create placeholder matching block dimensions
      const placeholder = document.createElement('div');
      placeholder.className = 'drag-placeholder';
      placeholder.style.height = rect.height + 'px';
      container.insertBefore(placeholder, block);

      // Position block as fixed overlay exactly where it was
      block.classList.add('dragging');
      block.style.position = 'fixed';
      block.style.width = rect.width + 'px';
      block.style.zIndex = '1500';
      block.style.top = rect.top + 'px';
      block.style.left = rect.left + 'px';
      block.style.pointerEvents = 'none';
      document.body.appendChild(block);

      dragState = {{
        target: block,
        placeholder,
        container,
        offsetY: e.clientY - rect.top,
        offsetX: e.clientX - rect.left,
        containerLeft: containerRect.left,
        containerWidth: containerRect.width
      }};
    }});

    document.addEventListener('mousemove', (e) => {{
      if (!dragState.target) return;
      e.preventDefault();

      // Use requestAnimationFrame for smooth movement
      if (dragState.animFrame) cancelAnimationFrame(dragState.animFrame);
      dragState.animFrame = requestAnimationFrame(() => {{
        // Move block to follow cursor
        dragState.target.style.top = (e.clientY - dragState.offsetY) + 'px';
        // Keep horizontal position aligned with container
        dragState.target.style.left = dragState.containerLeft + 'px';

        // Find the correct insertion point among siblings
        const siblings = [...dragState.container.querySelectorAll('[data-drag-block]:not(.dragging), .drag-placeholder')];
        let insertBefore = null;
        for (const sib of siblings) {{
          if (sib === dragState.placeholder) continue;
          const r = sib.getBoundingClientRect();
          const midY = r.top + r.height / 2;
          if (e.clientY < midY) {{
            insertBefore = sib;
            break;
          }}
        }}

        // Only move placeholder if position changed
        if (insertBefore) {{
          if (insertBefore !== dragState.placeholder.nextElementSibling) {{
            dragState.container.insertBefore(dragState.placeholder, insertBefore);
          }}
        }} else {{
          // Append at end if past all siblings
          const lastChild = dragState.container.lastElementChild;
          if (lastChild !== dragState.placeholder) {{
            dragState.container.appendChild(dragState.placeholder);
          }}
        }}
      }});
    }});

    document.addEventListener('mouseup', () => {{
      if (!dragState.target) return;
      if (dragState.animFrame) cancelAnimationFrame(dragState.animFrame);

      const block = dragState.target;
      const placeholder = dragState.placeholder;
      const container = dragState.container;

      // Animate block to placeholder position before finalizing
      const placeholderRect = placeholder.getBoundingClientRect();
      block.style.transition = 'top 0.15s ease, left 0.15s ease, opacity 0.15s ease';
      block.style.top = placeholderRect.top + 'px';
      block.style.left = placeholderRect.left + 'px';

      setTimeout(() => {{
        // Clean up styles and insert at placeholder position
        block.classList.remove('dragging');
        block.style.position = '';
        block.style.width = '';
        block.style.zIndex = '';
        block.style.top = '';
        block.style.left = '';
        block.style.transition = '';
        block.style.pointerEvents = '';

        container.insertBefore(block, placeholder);
        placeholder.remove();
        container.setAttribute('contenteditable', 'true');

        const slug = container.dataset.slug;
        if (slug) {{
          markDirty(slug);
          scheduleSave(slug);
        }}
      }}, 160);

      dragState = {{ target: null, placeholder: null, container: null, animFrame: null }};
    }});

    // Attach drag handles on load
    document.querySelectorAll('.show-content[contenteditable]').forEach(el => {{
      attachDragHandlesForPage(el);
    }});

    // ── Restore approvals ──
    (function restoreApprovals() {{
      try {{
        const saved = JSON.parse(localStorage.getItem('idw_approved_pages') || '[]');
        saved.forEach(slug => {{
          const cb = document.querySelector(`.page-approve-cb[data-slug="${{slug}}"]`);
          if (cb) cb.checked = true;
        }});
        updateApprovalState();
      }} catch(e) {{}}
    }})();

    // ── Keyboard shortcuts (updated guard for contenteditable) ──
    document.addEventListener('keydown', (e) => {{
      if (e.target.tagName === 'INPUT' || e.target.isContentEditable) return;

      const sections = [...pageSections];
      const current = sections.findIndex(s => {{
        const rect = s.getBoundingClientRect();
        return rect.top >= 0 && rect.top < window.innerHeight / 2;
      }});
      if (e.key === 'j' && current < sections.length - 1) {{
        sections[Math.max(0, current)].scrollIntoView({{ behavior: 'smooth' }});
      }}
      if (e.key === 'k' && current > 0) {{
        sections[current - 1].scrollIntoView({{ behavior: 'smooth' }});
      }}
      if (e.key === ' ' && !e.metaKey && !e.ctrlKey) {{
        e.preventDefault();
        const idx = Math.max(0, current);
        if (idx < sections.length) {{
          const cb = sections[idx].querySelector('.page-approve-cb');
          if (cb) {{ cb.checked = !cb.checked; updateApprovalState(); }}
        }}
      }}
      if (e.key === 'a' && !e.metaKey && !e.ctrlKey) {{ selectAll(); }}
      if (e.key === 'd' && !e.metaKey && !e.ctrlKey) {{ selectNone(); }}
    }});
  </script>

</body>
</html>'''


def _escape(text: str) -> str:
    """HTML-escape text."""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def main():
    parser = argparse.ArgumentParser(description='Generate unified preview of all staged Canvas pages')
    parser.add_argument('--modules', nargs='+', type=int, help='Only include specific module numbers')
    parser.add_argument('--filter', type=str, help='Filter pages by keyword in slug')
    parser.add_argument('--open', action='store_true', help='Open in default browser after generating')
    parser.add_argument('--output', type=str, help='Custom output path (default: staging/_unified_preview.html)')
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else OUTPUT_FILE

    # Load course tree for metadata
    course_tree = load_course_tree()

    # Get staged pages
    pages = get_staged_pages(
        module_filter=set(args.modules) if args.modules else None,
        keyword_filter=args.filter,
    )

    if not pages:
        print(json.dumps({"ok": False, "error": "No staged pages found matching criteria"}))
        sys.exit(1)

    # Generate HTML
    html = generate_html(pages, course_tree)

    # Write output
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding='utf-8')

    result = {
        "ok": True,
        "path": str(output_path),
        "pages": len(pages),
        "modules": len(set(p['module_number'] for p in pages)),
        "url": f"http://localhost:8111/{output_path.name}" if output_path.parent == STAGING_DIR else None,
    }
    print(json.dumps(result))

    # Open in browser if requested
    if args.open:
        if sys.platform == 'darwin':
            subprocess.run(['open', str(output_path)])
        elif sys.platform == 'linux':
            subprocess.run(['xdg-open', str(output_path)])


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except FileNotFoundError as e:
        _log.exception("Staging directory not found")
        print(f"\nStaging directory not found. Stage some pages first with /staging.")
        sys.exit(1)
    except Exception as e:
        _log.exception("Unexpected error")
        print(f"\nSomething went wrong: {e}")
        print("Check the log at ~/.idw/logs/ for details.")
        sys.exit(1)
