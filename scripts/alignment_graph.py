#!/usr/bin/env python3
"""Alignment graph builder for IDW's audit system.

Builds a structured graph of CLOs → MLOs → Materials/Assessments from
Canvas course data and course-config.json. Supports gap analysis,
coverage metrics, Bloom's progression, and evidence verification.

Usage:
    python alignment_graph.py --build                   # Build graph from Canvas + config
    python alignment_graph.py --validate                # Validate existing graph
    python alignment_graph.py --gaps                    # Show gap analysis
    python alignment_graph.py --query full_matrix       # Query graph
    python alignment_graph.py --summary                 # Print graph summary
    python alignment_graph.py --build --json            # JSON output
    python alignment_graph.py --build --course-id 12345 # Override course ID
"""

import argparse
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]

# Ensure sibling scripts are importable
sys.path.insert(0, str(Path(__file__).parent))

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(PLUGIN_ROOT / ".env")
    load_dotenv(PLUGIN_ROOT / ".env.local", override=True)
except ImportError:
    pass

# Logging
try:
    from idw_logger import get_logger
    _log = get_logger("alignment_graph")
    from idw_metrics import track as _track
except ImportError:
    import logging
    _log = logging.getLogger("alignment_graph")
    def _track(*a, **k): pass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BLOOMS_LEVELS = {
    "Remember": 1, "Understand": 2, "Apply": 3,
    "Analyze": 4, "Evaluate": 5, "Create": 6,
}

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


# ---------------------------------------------------------------------------
# Bloom's utilities
# ---------------------------------------------------------------------------

def classify_blooms(text):
    """Extract leading verb from objective text and classify Bloom's level.

    Returns (verb, blooms_level) or (verb, "Unknown").
    """
    # Strip ID-like prefixes: "1.1:", "M1.1:", "CLO-1:", "2.3:", but NOT plain verbs
    cleaned = re.sub(r'^(?:CLO-?\d+|MLO-?\d+|M\d+[\.\d]*|[\d]+[\.\d]*)\s*[:\-\s]\s*', '', text.strip(), flags=re.IGNORECASE)
    words = cleaned.split()
    if not words:
        return ("", "Unknown")
    raw_verb = words[0].lower()
    # Check the raw verb and common de-conjugations against all Bloom's sets
    candidates = {raw_verb}
    if raw_verb.endswith('es') and len(raw_verb) > 3:
        candidates.add(raw_verb[:-1])   # "analyzes" → "analyze"
        candidates.add(raw_verb[:-2])   # "describes" → "describ" (won't match, harmless)
        candidates.add(raw_verb[:-2] + 'e')  # "evaluates" → "evaluate"
    elif raw_verb.endswith('s') and len(raw_verb) > 3:
        candidates.add(raw_verb[:-1])   # "plans" → "plan"
    for level, verbs in BLOOMS_VERBS.items():
        for candidate in candidates:
            if candidate in verbs:
                return (candidate, level)
    return (raw_verb, "Unknown")


def is_measurable(text):
    """Check if objective uses a measurable verb. Returns (bool, verb)."""
    cleaned = re.sub(r'^[\d.]+[:\s]*|^[A-Z][\w.-]*[:\s]*', '', text.strip())
    words = cleaned.split()
    if not words:
        return (False, "")
    verb = words[0].lower()
    # Check against full verb phrase (e.g., "be aware", "become familiar")
    two_word = " ".join(words[:2]).lower() if len(words) > 1 else ""
    three_word = " ".join(words[:3]).lower() if len(words) > 2 else ""
    for unmeasurable in UNMEASURABLE_VERBS:
        if verb == unmeasurable or two_word == unmeasurable or three_word == unmeasurable:
            return (False, unmeasurable)
    return (True, verb)


# ---------------------------------------------------------------------------
# HTML text extraction helper
# ---------------------------------------------------------------------------

def _strip_html(html_str):
    """Strip HTML tags and decode entities. Returns plain text."""
    if not html_str:
        return ""
    import html as html_module
    text = re.sub(r'<[^>]+>', ' ', html_str)
    text = html_module.unescape(text)
    return ' '.join(text.split()).strip()


# ---------------------------------------------------------------------------
# Slug helper
# ---------------------------------------------------------------------------

def _slugify(text):
    """Convert text to a URL-safe slug."""
    slug = re.sub(r'[^a-z0-9]+', '-', text.lower().strip())
    return slug.strip('-')[:40]


# ---------------------------------------------------------------------------
# CLO extraction
# ---------------------------------------------------------------------------

def extract_clos_from_text(text):
    """Extract CLO-like statements from text using multi-pattern regex.

    Returns list of CLO text strings.
    """
    patterns = [
        r'(?:course[- ]?level\s+)?(?:learning\s+)?objectives?\s*[:\-]\s*\n(.*?)(?=\n\n|\n[A-Z][a-z]+ [A-Z]|\Z)',
        r'(?:course[- ]?level\s+)?(?:learning\s+)?outcomes?\s*[:\-]\s*\n(.*?)(?=\n\n|\n[A-Z][a-z]+ [A-Z]|\Z)',
        r'CLO[s]?\s*[:\-]\s*\n(.*?)(?=\n\n|\n[A-Z][a-z]+ [A-Z]|\Z)',
        r'(?:Upon|After|By)\s+completion.*?(?:able\s+)?to\s*[:\-]\s*\n(.*?)(?=\n\n|\n[A-Z][a-z]+ [A-Z]|\Z)',
        r'(?:students?\s+(?:will|should)\s+be\s+able\s+to)\s*[:\-]?\s*\n(.*?)(?=\n\n|\n[A-Z][a-z]+ [A-Z]|\Z)',
    ]
    clos = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL):
            block = match.group(1).strip()
            for line in block.split('\n'):
                line = line.strip().lstrip('-\u2022*\u00b7\u25aa\u25b8\u25ba1234567890.)\t ')
                if line and len(line) > 15 and not line.startswith('http'):
                    clos.append(line)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for c in clos:
        key = c.lower()[:50]
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique[:20]  # Cap at 20


def extract_clos(config, course_config):
    """Extract CLOs from course-config.json and syllabus page.

    Returns list of CLO dicts for the alignment graph.
    """
    clos = []

    # 1. From course-config.json (declared source)
    for clo_def in course_config.get("clos", []):
        text = clo_def.get("text", "")
        if not text:
            continue
        verb, blooms = classify_blooms(text)
        measurable, _ = is_measurable(text)
        clos.append({
            "id": clo_def.get("id", f"CLO-{len(clos)+1}"),
            "text": text,
            "measurable_verb": verb,
            "is_measurable": measurable,
            "blooms_level": blooms,
            "source": "declared",
            "mlo_ids": [],  # populated later
        })

    # 2. From syllabus page (extracted source)
    if not clos:
        try:
            from canvas_api import get_page
            # Try common syllabus slugs
            for slug in ['syllabus', 'syllabus-and-course-policies', 'welcome-start-here']:
                page = get_page(config, slug)
                if page and page.get('body'):
                    text = _strip_html(page['body'])
                    extracted = extract_clos_from_text(text)
                    for i, clo_text in enumerate(extracted):
                        verb, blooms = classify_blooms(clo_text)
                        measurable, _ = is_measurable(clo_text)
                        clos.append({
                            "id": f"CLO-{i+1}",
                            "text": clo_text,
                            "measurable_verb": verb,
                            "is_measurable": measurable,
                            "blooms_level": blooms,
                            "source": "extracted",
                            "mlo_ids": [],
                        })
                    if clos:
                        break
        except Exception as e:
            _log.warning(f"CLO extraction from syllabus failed: {e}")

    return clos


# ---------------------------------------------------------------------------
# MLO extraction
# ---------------------------------------------------------------------------

def extract_mlos(config, course_config, tree):
    """Extract MLOs from course-config.json and module overview pages.

    Returns list of MLO dicts.
    """
    mlos = []

    # 1. From course-config.json (declared)
    for mod in course_config.get("modules", []):
        mod_num = mod.get("number", 0)
        for obj in mod.get("objectives", []):
            text = obj.get("text", "")
            if not text:
                continue
            verb, blooms = classify_blooms(text)
            measurable, _ = is_measurable(text)
            clo_ref = obj.get("clo", [])
            if isinstance(clo_ref, str):
                clo_ref = [clo_ref]
            mlos.append({
                "id": obj.get("id", f"M{mod_num}.{len(mlos)+1}"),
                "text": text,
                "measurable_verb": verb,
                "is_measurable": measurable,
                "blooms_level": blooms,
                "module": mod_num,
                "clo_ids": clo_ref,
                "source": "declared",
            })

    # 2. From module overview pages (extracted) — only if no declared MLOs
    if not mlos:
        try:
            from canvas_api import get_page
            for module in tree:
                mod_name = module.get("name", "")
                mod_pos = module.get("position", 0)
                # Find the first Page item (usually the overview)
                for item in module.get("items", []):
                    if item.get("type") == "Page" and item.get("page_url"):
                        page = get_page(config, item["page_url"])
                        if page and page.get("body"):
                            text = _strip_html(page["body"])
                            # Look for objectives section
                            obj_match = re.search(
                                r'(?:objectives?|outcomes?|by the end.*?able to)\s*[:\-]?\s*\n(.*?)(?=\n\n[A-Z]|\nAssignment|\nTab |\Z)',
                                text, re.IGNORECASE | re.DOTALL
                            )
                            if obj_match:
                                for line in obj_match.group(1).strip().split('\n'):
                                    line = line.strip().lstrip('-\u2022*\u00b71234567890.)\t ')
                                    if line and len(line) > 15:
                                        verb, blooms = classify_blooms(line)
                                        measurable, _ = is_measurable(line)
                                        mlos.append({
                                            "id": f"M{mod_pos}.{len([m for m in mlos if m['module']==mod_pos])+1}",
                                            "text": line,
                                            "measurable_verb": verb,
                                            "is_measurable": measurable,
                                            "blooms_level": blooms,
                                            "module": mod_pos,
                                            "clo_ids": [],  # inferred later
                                            "source": "extracted",
                                        })
                        break  # Only check first page per module
        except Exception as e:
            _log.warning(f"MLO extraction from pages failed: {e}")

    return mlos


# ---------------------------------------------------------------------------
# Materials extraction
# ---------------------------------------------------------------------------

def extract_materials(tree):
    """Extract non-assessment content items from course tree.

    Returns list of material dicts.
    """
    materials = []
    assessment_types = {"Quiz", "Assignment"}

    for module in tree:
        mod_pos = module.get("position", 0)
        for item in module.get("items", []):
            item_type = item.get("type", "")
            title = item.get("title", "")

            # Skip assessments and structural items
            if item_type in assessment_types:
                continue
            if item_type == "SubHeader":
                continue
            if item_type == "Page":
                materials.append({
                    "id": f"mat-m{mod_pos}-{_slugify(title)}",
                    "title": title,
                    "type": "page",
                    "canvas_type": "Page",
                    "module": mod_pos,
                    "mlo_ids": [],
                    "source": "extracted",
                })
            elif item_type == "File":
                materials.append({
                    "id": f"mat-m{mod_pos}-file-{_slugify(title)}",
                    "title": title,
                    "type": "file",
                    "canvas_type": "File",
                    "module": mod_pos,
                    "mlo_ids": [],
                    "source": "extracted",
                })
            elif item_type == "ExternalUrl":
                materials.append({
                    "id": f"mat-m{mod_pos}-url-{_slugify(title)}",
                    "title": title,
                    "type": "external_url",
                    "canvas_type": "ExternalUrl",
                    "module": mod_pos,
                    "mlo_ids": [],
                    "source": "extracted",
                })
            elif item_type == "ExternalTool":
                materials.append({
                    "id": f"mat-m{mod_pos}-tool-{_slugify(title)}",
                    "title": title,
                    "type": "external_tool",
                    "canvas_type": "ExternalTool",
                    "module": mod_pos,
                    "mlo_ids": [],
                    "source": "extracted",
                })
    return materials


# ---------------------------------------------------------------------------
# Assessments extraction
# ---------------------------------------------------------------------------

def extract_assessments(config, course_config, tree):
    """Extract assessments from course tree and config.

    Returns list of assessment dicts.
    """
    assessments = []

    # Build rubric presence lookup from Canvas API
    rubric_map = {}  # canvas_id -> bool (covers assignment IDs and discussion topic IDs)
    try:
        import canvas_api
        assignments_data = canvas_api.get_assignments_with_rubrics(config)
        for a in assignments_data:
            has_rubric = bool(a.get("rubric") or a.get("use_rubric_for_grading"))
            rubric_map[a["id"]] = has_rubric
            # Discussion module items use discussion_topic.id as content_id, not assignment.id
            topic_id = (a.get("discussion_topic") or {}).get("id")
            if topic_id:
                rubric_map[topic_id] = has_rubric
    except Exception:
        pass  # Graceful fallback — rubric_map stays empty, has_rubric defaults to False

    # Build a lookup of declared assessment info from course-config
    declared = {}
    for mod in course_config.get("modules", []):
        mod_num = mod.get("number", 0)
        asmt = mod.get("assessments", {})
        # Handle both dict format (template) and list format (real configs)
        if isinstance(asmt, dict):
            if asmt.get("knowledge_check"):
                declared[f"m{mod_num}-kc"] = {"type": "formative", "mlo_ids": [], "module": mod_num}
            if asmt.get("guided_practice"):
                declared[f"m{mod_num}-gp"] = {"type": "formative", "mlo_ids": [], "module": mod_num}
            if asmt.get("artifact"):
                declared[f"m{mod_num}-artifact"] = {"type": "summative", "mlo_ids": [], "module": mod_num}
            if asmt.get("discussion"):
                declared[f"m{mod_num}-disc"] = {"type": "summative", "mlo_ids": [], "module": mod_num}
        elif isinstance(asmt, list):
            for a in asmt:
                if isinstance(a, dict):
                    atype = a.get("type", "").lower()
                    is_formative = atype in ("quiz", "knowledge_check", "guided_practice", "formative")
                    declared[f"m{mod_num}-{_slugify(a.get('title', atype))}"] = {
                        "type": "formative" if is_formative else "summative",
                        "mlo_ids": [],
                        "module": mod_num,
                    }

    # Walk course tree for actual Canvas items
    for module in tree:
        mod_pos = module.get("position", 0)
        for item in module.get("items", []):
            item_type = item.get("type", "")
            title = item.get("title", "")
            content_id = item.get("content_id", 0)

            if item_type == "Quiz":
                # Classify: exam/test = summative, knowledge check/quiz = formative
                is_summative = any(kw in title.lower() for kw in ["exam", "test", "midterm", "final"])
                assessments.append({
                    "id": f"asmt-m{mod_pos}-{_slugify(title)}",
                    "title": title,
                    "type": "summative" if is_summative else "formative",
                    "canvas_type": "Quiz",
                    "canvas_id": content_id,
                    "module": mod_pos,
                    "points": item.get("points_possible", 0),
                    "mlo_ids": [],
                    "clo_ids": [],
                    "has_rubric": rubric_map.get(content_id, False),
                    "source": "extracted",
                })
            elif item_type == "Assignment":
                assessments.append({
                    "id": f"asmt-m{mod_pos}-{_slugify(title)}",
                    "title": title,
                    "type": "summative",
                    "canvas_type": "Assignment",
                    "canvas_id": content_id,
                    "module": mod_pos,
                    "points": item.get("points_possible", 0),
                    "mlo_ids": [],
                    "clo_ids": [],
                    "has_rubric": rubric_map.get(content_id, False),
                    "source": "extracted",
                })
            elif item_type == "Discussion":
                assessments.append({
                    "id": f"asmt-m{mod_pos}-{_slugify(title)}",
                    "title": title,
                    "type": "summative" if item.get("points_possible", 0) else "formative",
                    "canvas_type": "Discussion",
                    "canvas_id": content_id,
                    "module": mod_pos,
                    "points": item.get("points_possible", 0),
                    "mlo_ids": [],
                    "clo_ids": [],
                    "has_rubric": rubric_map.get(content_id, False),
                    "source": "extracted",
                })

    return assessments


# ---------------------------------------------------------------------------
# Relationship wiring
# ---------------------------------------------------------------------------

def wire_declared_relationships(clos, mlos, materials, assessments):
    """Wire relationships from declared data (course-config.json MLO->CLO mappings).

    Mutates the lists in place.
    """
    # Build CLO lookup
    clo_map = {c["id"]: c for c in clos}

    # Wire MLO -> CLO (bidirectional)
    for mlo in mlos:
        for clo_id in mlo.get("clo_ids", []):
            if clo_id in clo_map:
                if mlo["id"] not in clo_map[clo_id]["mlo_ids"]:
                    clo_map[clo_id]["mlo_ids"].append(mlo["id"])

    # Wire materials -> MLOs by module co-location
    # (materials in the same module as MLOs are assumed to support those MLOs)
    mlos_by_module = {}
    for mlo in mlos:
        mod = mlo["module"]
        if mod not in mlos_by_module:
            mlos_by_module[mod] = []
        mlos_by_module[mod].append(mlo["id"])

    for mat in materials:
        mod = mat["module"]
        if mod in mlos_by_module and not mat["mlo_ids"]:
            mat["mlo_ids"] = mlos_by_module[mod]
            mat["source"] = "inferred"  # module co-location inference

    # Wire assessments -> MLOs by module co-location
    for asmt in assessments:
        mod = asmt["module"]
        if mod in mlos_by_module and not asmt["mlo_ids"]:
            asmt["mlo_ids"] = mlos_by_module[mod]
            asmt["source"] = "inferred"
        # Wire assessments -> CLOs through MLOs
        for mlo_id in asmt["mlo_ids"]:
            mlo = next((m for m in mlos if m["id"] == mlo_id), None)
            if mlo:
                for clo_id in mlo.get("clo_ids", []):
                    if clo_id not in asmt["clo_ids"]:
                        asmt["clo_ids"].append(clo_id)


# ---------------------------------------------------------------------------
# Gap analysis
# ---------------------------------------------------------------------------

def analyze_gaps(graph):
    """Identify structural gaps in the alignment graph."""
    clos = graph.get("clos", [])
    mlos = graph.get("mlos", [])
    materials = graph.get("materials", [])
    assessments = graph.get("assessments", [])

    # All MLO IDs that have at least one assessment
    assessed_mlo_ids = set()
    for a in assessments:
        assessed_mlo_ids.update(a.get("mlo_ids", []))

    # All MLO IDs that have at least one material
    materialed_mlo_ids = set()
    for m in materials:
        materialed_mlo_ids.update(m.get("mlo_ids", []))

    # CLOs without any MLO
    unmapped_clos = [c["id"] for c in clos if not c.get("mlo_ids")]

    # MLOs without any CLO
    unmapped_mlos = [m["id"] for m in mlos if not m.get("clo_ids")]

    # Materials with no MLO connection
    orphan_materials = [m["id"] for m in materials if not m.get("mlo_ids")]

    # Assessments with no MLO connection
    orphan_assessments = [a["id"] for a in assessments if not a.get("mlo_ids")]

    # CLOs where no summative assessment traces back
    summative_clo_ids = set()
    for a in assessments:
        if a["type"] == "summative":
            summative_clo_ids.update(a.get("clo_ids", []))
    clos_without_summative = [c["id"] for c in clos if c["id"] not in summative_clo_ids]

    # Modules with no formative assessment
    formative_modules = set()
    for a in assessments:
        if a["type"] == "formative":
            formative_modules.add(a["module"])
    all_modules = set(m["module"] for m in mlos) | set(m["module"] for m in materials)
    modules_without_formative = sorted(all_modules - formative_modules)

    return {
        "unmapped_clos": unmapped_clos,
        "unmapped_mlos": unmapped_mlos,
        "orphan_materials": orphan_materials,
        "orphan_assessments": orphan_assessments,
        "clos_without_summative": clos_without_summative,
        "modules_without_formative": modules_without_formative,
    }


# ---------------------------------------------------------------------------
# Coverage calculation
# ---------------------------------------------------------------------------

def calculate_coverage(graph):
    """Calculate coverage metrics."""
    clos = graph.get("clos", [])
    mlos = graph.get("mlos", [])
    materials = graph.get("materials", [])
    assessments = graph.get("assessments", [])

    # CLO assessment coverage: for each CLO, what fraction of its MLOs have assessments
    clo_coverage = {}
    for clo in clos:
        mlo_ids = clo.get("mlo_ids", [])
        if not mlo_ids:
            clo_coverage[clo["id"]] = 0.0
            continue
        assessed = sum(1 for mid in mlo_ids
                       if any(mid in a.get("mlo_ids", []) for a in assessments))
        clo_coverage[clo["id"]] = round(assessed / len(mlo_ids), 2)

    # MLO material coverage
    mlo_coverage = {}
    for mlo in mlos:
        has_material = any(mlo["id"] in m.get("mlo_ids", []) for m in materials)
        mlo_coverage[mlo["id"]] = 1.0 if has_material else 0.0

    # Bloom's progression: average level per module should be non-decreasing
    module_blooms = {}
    for mlo in mlos:
        mod = mlo["module"]
        level = BLOOMS_LEVELS.get(mlo["blooms_level"], 0)
        if level > 0:
            if mod not in module_blooms:
                module_blooms[mod] = []
            module_blooms[mod].append(level)

    avg_by_module = {}
    for mod in sorted(module_blooms.keys()):
        vals = module_blooms[mod]
        avg_by_module[mod] = round(sum(vals) / len(vals), 2)

    # Check non-decreasing trend (allow small dips)
    avgs = [avg_by_module[m] for m in sorted(avg_by_module.keys())]
    progression = True
    if len(avgs) >= 3:
        # Allow the first module to be higher (intro may use varied levels)
        # Check that last third avg >= first third avg
        third = max(1, len(avgs) // 3)
        early_avg = sum(avgs[:third]) / third
        late_avg = sum(avgs[-third:]) / third
        progression = late_avg >= early_avg - 0.5  # Allow 0.5 tolerance

    return {
        "clo_assessment_coverage": clo_coverage,
        "mlo_material_coverage": mlo_coverage,
        "blooms_progression": progression,
        "blooms_by_module": avg_by_module,
    }


# ---------------------------------------------------------------------------
# Evidence verification (QAI port)
# ---------------------------------------------------------------------------

def verify_evidence(evidence_text, corpus_text):
    """Verify that an evidence quote actually exists in course content.

    QAI port: catches AI hallucinated evidence.
    """
    if not evidence_text or not corpus_text:
        return True
    clean_evidence = " ".join(evidence_text.split()).strip().lower()
    if len(clean_evidence) < 8:
        return True  # Too short to verify meaningfully
    clean_corpus = " ".join(corpus_text.split()).strip().lower()
    return clean_evidence in clean_corpus


def coverage_status(found_modules, total_modules, criterion_scope="module"):
    """Determine Met/Partially Met/Not Met based on evidence coverage spread.

    QAI port: coverage-aware status.
    """
    if criterion_scope == "module":
        if total_modules <= 1:
            required = total_modules
        elif total_modules <= 3:
            required = 2
        else:
            required = max(2, math.ceil(total_modules * 0.6))
        if found_modules >= required:
            return "Met"
        elif found_modules > 0:
            return "Partially Met"
        else:
            return "Not Met"
    elif criterion_scope == "page":
        required = max(1, math.ceil(total_modules * 0.4))  # total_modules is total_pages here
        if found_modules >= required:
            return "Met"
        elif found_modules > 0:
            return "Partially Met"
        else:
            return "Not Met"
    return "Met"  # course-level: any evidence counts


def degrade_confidence(confidence):
    """Downgrade confidence one level. QAI port."""
    return {"High": "Medium", "Medium": "Low", "Low": "Low"}.get(confidence, "Low")


# ---------------------------------------------------------------------------
# Graph validation
# ---------------------------------------------------------------------------

def validate_graph(graph):
    """Validate structural integrity. Returns list of issue dicts."""
    issues = []
    clo_ids = {c["id"] for c in graph.get("clos", [])}
    mlo_ids = {m["id"] for m in graph.get("mlos", [])}

    # Check for duplicate IDs
    all_ids = []
    for collection in ["clos", "mlos", "materials", "assessments"]:
        for item in graph.get(collection, []):
            if item["id"] in all_ids:
                issues.append({"level": "error", "message": f"Duplicate ID: {item['id']}", "node_id": item["id"]})
            all_ids.append(item["id"])

    # Check dangling references
    for mlo in graph.get("mlos", []):
        for cid in mlo.get("clo_ids", []):
            if cid not in clo_ids:
                issues.append({"level": "error", "message": f"MLO {mlo['id']} references non-existent CLO {cid}", "node_id": mlo["id"]})

    for mat in graph.get("materials", []):
        for mid in mat.get("mlo_ids", []):
            if mid not in mlo_ids:
                issues.append({"level": "warning", "message": f"Material {mat['id']} references non-existent MLO {mid}", "node_id": mat["id"]})

    for asmt in graph.get("assessments", []):
        for mid in asmt.get("mlo_ids", []):
            if mid not in mlo_ids:
                issues.append({"level": "warning", "message": f"Assessment {asmt['id']} references non-existent MLO {mid}", "node_id": asmt["id"]})

    # Check CLOs without MLOs (warning)
    for clo in graph.get("clos", []):
        if not clo.get("mlo_ids"):
            issues.append({"level": "warning", "message": f"CLO {clo['id']} has no MLO mappings", "node_id": clo["id"]})

    # Check unmeasurable verbs
    for clo in graph.get("clos", []):
        if not clo.get("is_measurable", True):
            issues.append({"level": "warning", "message": f"CLO {clo['id']} uses unmeasurable verb: '{clo.get('measurable_verb', '')}'", "node_id": clo["id"]})
    for mlo in graph.get("mlos", []):
        if not mlo.get("is_measurable", True):
            issues.append({"level": "warning", "message": f"MLO {mlo['id']} uses unmeasurable verb: '{mlo.get('measurable_verb', '')}'", "node_id": mlo["id"]})

    return issues


# ---------------------------------------------------------------------------
# Query engine
# ---------------------------------------------------------------------------

def query_graph(graph, query_type):
    """Answer structured queries against the graph. Returns formatted text."""
    if query_type == "unmapped_clos":
        gaps = graph.get("gaps", {})
        items = gaps.get("unmapped_clos", [])
        if not items:
            return "All CLOs are mapped to at least one MLO."
        lines = ["CLOs with no MLO mappings:"]
        for cid in items:
            clo = next((c for c in graph["clos"] if c["id"] == cid), None)
            if clo:
                lines.append(f"  {cid}: {clo['text'][:80]}")
        return "\n".join(lines)

    elif query_type == "orphan_assessments":
        gaps = graph.get("gaps", {})
        items = gaps.get("orphan_assessments", [])
        if not items:
            return "All assessments are mapped to at least one MLO."
        lines = ["Assessments with no MLO connection:"]
        for aid in items:
            asmt = next((a for a in graph["assessments"] if a["id"] == aid), None)
            if asmt:
                lines.append(f"  {asmt['title']} (Module {asmt['module']}, {asmt['type']})")
        return "\n".join(lines)

    elif query_type == "clo_coverage":
        coverage = graph.get("coverage", {}).get("clo_assessment_coverage", {})
        if not coverage:
            return "No CLO coverage data available."
        lines = ["CLO Assessment Coverage:"]
        for cid, pct in coverage.items():
            clo = next((c for c in graph["clos"] if c["id"] == cid), None)
            text = clo["text"][:60] if clo else "?"
            bar = "\u2588" * int(pct * 10) + "\u2591" * (10 - int(pct * 10))
            lines.append(f"  {cid}: {bar} {pct*100:.0f}%  {text}")
        return "\n".join(lines)

    elif query_type == "blooms_progression":
        blooms = graph.get("coverage", {}).get("blooms_by_module", {})
        prog = graph.get("coverage", {}).get("blooms_progression", None)
        if not blooms:
            return "No Bloom's data available."
        lines = [f"Bloom's Progression ({'\u2713 Non-decreasing' if prog else '\u26a0 Not progressive'}):"]
        level_names = {v: k for k, v in BLOOMS_LEVELS.items()}
        for mod in sorted(blooms.keys(), key=lambda x: int(x) if str(x).isdigit() else x):
            avg = blooms[mod]
            nearest = level_names.get(round(avg), f"~{avg}")
            bar = "\u2593" * int(avg) + "\u2591" * (6 - int(avg))
            lines.append(f"  Module {mod}: {bar} {avg:.1f} ({nearest})")
        return "\n".join(lines)

    elif query_type == "full_matrix":
        clos = graph.get("clos", [])
        mlos = graph.get("mlos", [])
        assessments = graph.get("assessments", [])
        if not clos:
            return "No CLOs in graph."
        lines = ["CLO -> MLO -> Assessment Matrix:", ""]
        for clo in clos:
            lines.append(f"  {clo['id']}: {clo['text'][:70]}")
            for mlo_id in clo.get("mlo_ids", []):
                mlo = next((m for m in mlos if m["id"] == mlo_id), None)
                if mlo:
                    lines.append(f"    \u2514\u2500 {mlo['id']} [{mlo['blooms_level']}]: {mlo['text'][:60]}")
                    # Find assessments for this MLO
                    for asmt in assessments:
                        if mlo_id in asmt.get("mlo_ids", []):
                            lines.append(f"        \u2514\u2500 {asmt['title'][:50]} ({asmt['type']}, {asmt['canvas_type']})")
            if not clo.get("mlo_ids"):
                lines.append(f"    \u2514\u2500 (no MLOs mapped)")
            lines.append("")
        return "\n".join(lines)

    else:
        return f"Unknown query type: {query_type}. Available: unmapped_clos, orphan_assessments, clo_coverage, blooms_progression, full_matrix"


# ---------------------------------------------------------------------------
# Build orchestrator
# ---------------------------------------------------------------------------

def build_graph(config, course_config):
    """Build complete alignment graph from Canvas + config."""
    from course_navigator import fetch_course_tree

    _log.info("Building alignment graph...")
    tree = fetch_course_tree(config)

    clos = extract_clos(config, course_config)
    _log.info(f"Extracted {len(clos)} CLOs")

    mlos = extract_mlos(config, course_config, tree)
    _log.info(f"Extracted {len(mlos)} MLOs")

    materials = extract_materials(tree)
    _log.info(f"Extracted {len(materials)} materials")

    assessments = extract_assessments(config, course_config, tree)
    _log.info(f"Extracted {len(assessments)} assessments")

    # Wire declared relationships
    wire_declared_relationships(clos, mlos, materials, assessments)

    graph = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "auto-extracted",
        "clos": clos,
        "mlos": mlos,
        "materials": materials,
        "assessments": assessments,
    }

    graph["gaps"] = analyze_gaps(graph)
    graph["coverage"] = calculate_coverage(graph)

    # Track metrics
    try:
        _track("alignment_graph_built", context={
            "clos": len(clos),
            "mlos": len(mlos),
            "materials": len(materials),
            "assessments": len(assessments),
            "gaps": sum(len(v) for v in graph["gaps"].values() if isinstance(v, list)),
        })
    except Exception:
        pass

    return graph


# ---------------------------------------------------------------------------
# Save / Load
# ---------------------------------------------------------------------------

def save_graph(graph, config_path=None):
    """Save alignment graph into course-config.json."""
    if config_path is None:
        config_path = Path.cwd() / "course-config.json"
    config_path = Path(config_path)

    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        data = {}

    data["alignment_graph"] = graph
    config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    _log.info(f"Graph saved to {config_path}")


def load_graph(config_path=None):
    """Load alignment graph from course-config.json. Returns None if absent."""
    if config_path is None:
        config_path = Path.cwd() / "course-config.json"
    config_path = Path(config_path)

    if not config_path.exists():
        return None
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return data.get("alignment_graph")
    except (json.JSONDecodeError, KeyError):
        return None


# ---------------------------------------------------------------------------
# Inference context builder
# ---------------------------------------------------------------------------

def prepare_inference_context(graph):
    """Build structured prompt context for Claude to infer missing relationships.

    Used during audit conversations.
    """
    lines = ["ALIGNMENT GRAPH \u2014 CURRENT STATE", ""]

    lines.append(f"CLOs ({len(graph.get('clos', []))}):")
    for c in graph.get("clos", []):
        mapped = ", ".join(c.get("mlo_ids", [])) or "(unmapped)"
        lines.append(f"  {c['id']} [{c['blooms_level']}]: {c['text'][:80]} -> MLOs: {mapped}")

    lines.append(f"\nMLOs ({len(graph.get('mlos', []))}):")
    for m in graph.get("mlos", []):
        clos = ", ".join(m.get("clo_ids", [])) or "(unmapped)"
        lines.append(f"  {m['id']} [M{m['module']}, {m['blooms_level']}]: {m['text'][:80]} -> CLOs: {clos}")

    lines.append(f"\nAssessments ({len(graph.get('assessments', []))}):")
    for a in graph.get("assessments", []):
        mlos = ", ".join(a.get("mlo_ids", [])) or "(unmapped)"
        lines.append(f"  {a['title'][:50]} [M{a['module']}, {a['type']}, {a['canvas_type']}] -> MLOs: {mlos}")

    gaps = graph.get("gaps", {})
    if any(v for v in gaps.values() if isinstance(v, list) and v):
        lines.append("\nGAPS DETECTED:")
        for gap_type, items in gaps.items():
            if isinstance(items, list) and items:
                lines.append(f"  {gap_type}: {', '.join(str(i) for i in items)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Alignment Graph Builder for IDW Audit")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build", action="store_true", help="Build graph from Canvas + config")
    group.add_argument("--validate", action="store_true", help="Validate existing graph")
    group.add_argument("--gaps", action="store_true", help="Show gap analysis")
    group.add_argument("--query", type=str, help="Query: unmapped_clos, orphan_assessments, clo_coverage, blooms_progression, full_matrix")
    group.add_argument("--summary", action="store_true", help="Print graph summary")
    parser.add_argument("--course-id", type=str, help="Override Canvas course ID")
    parser.add_argument("--mode", type=str, help="Canvas instance: prod or dev")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--config", type=str, help="Path to course-config.json")
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else Path.cwd() / "course-config.json"

    if args.build:
        from canvas_api import get_config
        config = get_config(instance=args.mode, course_id=args.course_id)
        course_config = {}
        if config_path.exists():
            course_config = json.loads(config_path.read_text(encoding="utf-8"))

        graph = build_graph(config, course_config)
        save_graph(graph, config_path)

        issues = validate_graph(graph)
        errors = [i for i in issues if i["level"] == "error"]
        warnings = [i for i in issues if i["level"] == "warning"]

        is_empty = (len(graph["clos"]) == 0 and len(graph["assessments"]) == 0)
        if is_empty:
            _log.warning(
                "Alignment graph is empty (0 CLOs, 0 assessments). "
                "Ensure course-config.json has CLOs defined and the course "
                "has at least one assessment item."
            )
        result = {
            "ok": not is_empty and len(errors) == 0,
            "empty": is_empty,
            "clos": len(graph["clos"]),
            "mlos": len(graph["mlos"]),
            "materials": len(graph["materials"]),
            "assessments": len(graph["assessments"]),
            "gaps": {k: len(v) for k, v in graph["gaps"].items() if isinstance(v, list)},
            "errors": len(errors),
            "warnings": len(warnings),
        }
        print(json.dumps(result, indent=2))

    elif args.validate:
        graph = load_graph(config_path)
        if not graph:
            print(json.dumps({"ok": False, "error": "No alignment graph found. Run --build first."}))
            sys.exit(1)
        issues = validate_graph(graph)
        if args.json:
            print(json.dumps({"ok": len([i for i in issues if i["level"] == "error"]) == 0, "issues": issues}))
        else:
            if not issues:
                print("\u2713 Graph is structurally valid. No issues found.")
            else:
                for issue in issues:
                    icon = "\u2717" if issue["level"] == "error" else "\u26a0"
                    print(f"  {icon} [{issue['level'].upper()}] {issue['message']}")

    elif args.gaps:
        graph = load_graph(config_path)
        if not graph:
            print(json.dumps({"ok": False, "error": "No alignment graph found. Run --build first."}))
            sys.exit(1)
        gaps = graph.get("gaps", {})
        if args.json:
            print(json.dumps(gaps, indent=2))
        else:
            has_gaps = False
            for gap_type, items in gaps.items():
                if isinstance(items, list) and items:
                    has_gaps = True
                    print(f"\n{gap_type.replace('_', ' ').title()} ({len(items)}):")
                    for item in items:
                        print(f"  \u2022 {item}")
            if not has_gaps:
                print("\u2713 No gaps detected. Full alignment coverage.")

    elif args.query:
        graph = load_graph(config_path)
        if not graph:
            print(json.dumps({"ok": False, "error": "No alignment graph found. Run --build first."}))
            sys.exit(1)
        result = query_graph(graph, args.query)
        print(result)

    elif args.summary:
        graph = load_graph(config_path)
        if not graph:
            print(json.dumps({"ok": False, "error": "No alignment graph found. Run --build first."}))
            sys.exit(1)
        print(f"Alignment Graph \u2014 Generated {graph.get('generated_at', 'unknown')}")
        print(f"  CLOs: {len(graph.get('clos', []))}")
        print(f"  MLOs: {len(graph.get('mlos', []))}")
        print(f"  Materials: {len(graph.get('materials', []))}")
        print(f"  Assessments: {len(graph.get('assessments', []))}")
        coverage = graph.get("coverage", {})
        if coverage:
            clo_cov = coverage.get("clo_assessment_coverage", {})
            avg_cov = sum(clo_cov.values()) / len(clo_cov) * 100 if clo_cov else 0
            print(f"  Avg CLO Coverage: {avg_cov:.0f}%")
            print(f"  Bloom's Progression: {'\u2713' if coverage.get('blooms_progression') else '\u26a0 Not progressive'}")
        gaps = graph.get("gaps", {})
        total_gaps = sum(len(v) for v in gaps.values() if isinstance(v, list))
        print(f"  Gaps: {total_gaps}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        _log.exception("Unexpected error")
        print(f"\nError: {e}")
        sys.exit(1)
