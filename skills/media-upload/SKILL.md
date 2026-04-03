---
name: media-upload
description: "Upload media files (images, videos, PDFs) to Canvas and embed them in pages."
---

## Metric Tracking
When this skill is invoked, immediately run this command before doing anything else:
```bash
python scripts/idw_metrics.py --track skill_invoked --context '{"skill": "media-upload"}'
```
This records usage metrics for the pilot dashboard. Do not skip this step.

## Purpose

Upload local files to a Canvas course's Files area and optionally embed or link them in a page. Handles the 3-step Canvas upload process automatically.

## When to Use

- "Upload this image to Module 3's overview page"
- "Add these PDFs to the course files"
- "Upload a video and embed it in the lesson page"
- "Put this infographic in the Resources folder"

## Required Inputs

- `.env` with Canvas credentials and active instance
- Local file path(s) to upload

## Workflow

### Step 1 — Get File(s) and Destination

Ask: "What file(s) would you like to upload? Provide the file path(s)."

Then ask: "Where should this go?"
- **Course files only** — upload to a folder in Canvas Files (specify folder or default to course root)
- **Embed in a page** — upload and insert into a specific Canvas page

### Step 2 — Determine Folder

If the user specifies a folder path (e.g., "Module 3/Images"), use `canvas_api.get_or_create_folder()`.

If no folder specified, use the course root folder:
```
GET /api/v1/courses/:course_id/folders/root
```

### Step 3 — Upload File

Use `canvas_api.upload_file(config, filepath, folder_id, content_type)`.

This handles the 3-step Canvas upload process:
1. **Notify** — POST to `/courses/:id/files` with name, size, content_type, parent_folder_id
2. **Upload** — POST file data to the returned upload_url
3. **Confirm** — Follow redirect to finalize

Auto-detect content type from extension:
| Extension | Content Type |
|---|---|
| `.png` | `image/png` |
| `.jpg`, `.jpeg` | `image/jpeg` |
| `.gif` | `image/gif` |
| `.svg` | `image/svg+xml` |
| `.mp4` | `video/mp4` |
| `.mov` | `video/quicktime` |
| `.pdf` | `application/pdf` |
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| `.pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` |
| Other | `application/octet-stream` |

### Step 4 — Embed in Page (if requested)

If the user wants the file embedded in a page:

**Images:** Insert `<img>` tag with the file's public URL:
```html
<img src="https://{domain}/courses/{course_id}/files/{file_id}/preview"
     alt="{user-provided alt text}"
     style="max-width: 100%; height: auto;" />
```

**Videos:** Insert Canvas media embed:
```html
<iframe src="https://{domain}/courses/{course_id}/files/{file_id}/preview"
        width="640" height="360"
        allowfullscreen="allowfullscreen"
        style="max-width: 100%;"></iframe>
```

**PDFs/Documents:** Insert a download link:
```html
<a href="https://{domain}/courses/{course_id}/files/{file_id}/download"
   target="_blank" rel="noopener">
   {filename}
</a>
```

Use the staging workflow: fetch current page HTML, insert the embed at the specified location, stage via `staging_manager.py`, preview via unified preview, wait for user approval, then push via `/staging`.

### Step 5 — Verify and Report

After uploading (and embedding, if requested), always:

1. **Confirm the upload** via `GET /api/v1/courses/:id/files/:id` — verify file name, size, and folder.
2. **If embedded in a page**: re-fetch the page body and confirm the embed tag is present in the HTML.
3. **Provide a direct Canvas link**:
   - File: `https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/files/{file_id}`
   - Page (if embedded): `https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/pages/{slug}`
4. **Take a screenshot**: Navigate to the page or file in Canvas and capture a screenshot confirming the media renders — do not skip this. Show it to the user.

Display:
```
Uploaded: image.png (245 KB)
  → Canvas file ID: 12345
  → Folder: Module 3/Images
  → Embedded in: m3-overview (after "Key Concepts" heading)
  → Canvas link: https://canvas.asu.edu/courses/237946/pages/m3-overview
```

## Batch Upload

For multiple files, process sequentially with progress:
```
Uploading 4 files to "Module Resources":
  [1/4] syllabus.pdf (1.2 MB) ✓ → file ID 12345
  [2/4] diagram.png (89 KB) ✓ → file ID 12346
  [3/4] lecture.mp4 (45 MB) ✓ → file ID 12347
  [4/4] notes.docx (156 KB) ✓ → file ID 12348
```

---

### Browser Automation (Claude in Chrome)

Use Claude in Chrome for media tasks that go beyond the Canvas Files API — external media platforms, visual embed verification, and rich content editor interactions.

**MCP Tools**: `navigate`, `computer`, `read_page`, `get_page_text`, `javascript_tool`, `tabs_context_mcp`

**Where It Fits**:
- **External media hosts**: Upload videos to platforms like YouTube, Kaltura/MediaSpace, or Vimeo when the instructor wants hosted video rather than Canvas-native — navigate the upload UI, fill metadata fields, and retrieve the embed code
- **Canvas Rich Content Editor**: When embedding media requires interacting with the RCE (e.g., inserting via the media button, adjusting embed sizing), drive the editor UI directly
- **Embed verification**: After embedding media in a Canvas page, navigate to the published page and take a screenshot to verify the embed renders correctly (video plays, image displays, PDF viewer loads)
- **Thumbnail/preview capture**: Navigate to a video URL and capture a screenshot to use as a thumbnail or preview image on the Canvas page
- **Captioning platforms**: Navigate to auto-captioning services (YouTube Studio, 3Play Media) to download or verify caption files for uploaded videos

**When to Use Browser vs. API**:
| Task | Approach |
|---|---|
| Upload file to Canvas Files | Canvas REST API (3-step upload) |
| Upload to YouTube/Kaltura | Claude in Chrome (browser UI) |
| Embed in Canvas page | Canvas API (HTML update) |
| Verify embed renders | Claude in Chrome (screenshot) |
| Download captions from host | Claude in Chrome (navigate + download) |

---

### Google Drive Integration

Use the Google Drive MCP connector to find media files stored on institutional shared drives, then download and upload them to Canvas.

**MCP Tools**:
- `google_drive_search` — Search for images, videos, slide decks, PDFs, and other media files across shared drives by name, type, or folder
- `google_drive_fetch` — Fetch file metadata (name, size, mime type, download URL) to prepare for upload to Canvas

**Drive → Canvas Upload Workflow**:
1. **Search** — `google_drive_search` to find the file by name, type, or folder
2. **Fetch metadata** — `google_drive_fetch` to get the download URL and mime type
3. **Download locally** — Use Python `requests` or `curl` to download to a temp path (e.g., `/tmp/media/filename.png`)
4. **Upload to Canvas** — Use the standard 3-step Canvas upload with the local temp file
5. **Clean up** — Remove the temp file after successful upload

```python
# Example: Drive file → Canvas upload
import requests, os
# Step 1-2: google_drive_search + google_drive_fetch give us metadata
drive_url = "https://drive.google.com/..."  # from google_drive_fetch
local_path = f"/tmp/media/{filename}"
# Step 3: Download
os.makedirs("/tmp/media", exist_ok=True)
r = requests.get(drive_url, stream=True)
with open(local_path, 'wb') as f:
    for chunk in r.iter_content(8192):
        f.write(chunk)
# Step 4: Upload to Canvas using canvas_api.upload_file()
# Step 5: os.remove(local_path)
```

**Where It Fits**:
- **Locating media**: When an instructor says "upload the diagram from the shared drive," search Drive to find it by name rather than requiring a local file path
- **Batch media discovery**: Search a Drive folder for all images/videos to bulk-upload to a Canvas course's Files area
- **Version checking**: Use Drive metadata to confirm the latest version of a media file before uploading
- **Mixed sources**: Combine local files and Drive files in the same batch upload — local files go directly, Drive files are downloaded first

**Local Files vs Drive Files**:
| Source | Workflow |
|---|---|
| Local file path | Direct 3-step Canvas upload |
| Google Drive | Search → fetch metadata → download to /tmp → 3-step Canvas upload |
| Both in same batch | Process each by source type, unified progress display |

---

## Error Handling

| Error | Resolution |
|---|---|
| File not found | Check path, ask user to verify |
| Permission denied | Check Canvas role has "Manage Files" permission |
| Upload timeout | Retry once; if still failing, report and suggest smaller file |
| Quota exceeded | Report remaining storage, suggest alternatives |
