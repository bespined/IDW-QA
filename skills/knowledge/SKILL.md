# /knowledge — Course Content Cache & Search

Build a local text cache of all course content (Canvas pages + uploaded files) so Claude Code can search and reference course material without re-fetching from Canvas each session.

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python scripts/idw_metrics.py --track skill_invoked --context '{"skill": "knowledge"}'
```
This records usage metrics for the pilot dashboard. Do not skip this step.

## Prerequisites

- Canvas connected (`/canvas-connect`)
- Optional: `pymupdf`, `python-docx`, `python-pptx` for file text extraction

## How It Works

Unlike a traditional knowledge engine with embeddings, this skill uses a simple file-based cache:
1. **Dump**: Downloads all Canvas pages as HTML + plain text to `content_cache/{course_id}/pages/`
2. **Extract**: Optionally downloads course files (PDF, DOCX, PPTX, TXT) and extracts text to `content_cache/{course_id}/files/`
3. **Search**: Claude Code reads and greps the cache files directly — no embedding API needed

This is intentionally simple. Claude Code's large context window + native file reading provides the understanding layer.

## Commands

### Build Cache (Full Dump)
```bash
cd scripts && python3 course_content_cache.py dump --course-id <ID>
```

### With File Extraction
```bash
cd scripts && python3 course_content_cache.py dump --course-id <ID> --include-files
```

### Refresh (Only Updated Pages)
```bash
cd scripts && python3 course_content_cache.py refresh --course-id <ID>
```

### Check Status
```bash
cd scripts && python3 course_content_cache.py status --course-id <ID>
```

## Use Cases

1. **"What does the syllabus say about late work?"** → Cache the course, grep for "late" in cached files
2. **"Are learning objectives consistent across modules?"** → Read all cached page `.txt` files, compare objectives
3. **"Find all references to [topic]"** → Grep the `content_cache/` directory
4. **"Summarize the course structure"** → Read all cached pages, generate a summary

## Cache Structure

```
content_cache/
  {course_id}/
    metadata.json           # Timestamps, page list, file list
    pages/
      m1-overview.html      # Raw HTML from Canvas
      m1-overview.txt       # Plain text version
      m1-readings.html
      m1-readings.txt
      ...
    files/
      Syllabus.pdf.txt      # Extracted text from uploaded PDF
      Week3_Slides.pptx.txt # Extracted text from uploaded PPTX
      ...
```

## Refresh Strategy

- `dump` always fetches all pages (full refresh)
- `refresh` only fetches pages updated since the last dump timestamp
- The cache persists between sessions — no need to rebuild each time
- Run `refresh` at the start of a session if the course may have changed

## Integration with Other Skills

- Use before `/audit` to have full course context
- Use before `/course-build` to reference existing content
- Use before `/bulk-edit` to understand what needs changing
- Pair with `/course-plan-import` to compare imported syllabus against actual course content
