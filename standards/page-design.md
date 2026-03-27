# Page Design Standards

> **Plugin**: ASU Canvas Course Builder
> **Version**: 0.4.0
> **Purpose**: Reusable HTML/CSS component library for all Canvas page templates and dynamically generated content.

All content-generating skills reference this document when building Canvas page HTML. These are **composable components** — skills choose the right ones for each page type, not a rigid layout.

**Important**: Canvas strips `<style>` blocks, `<script>` tags, and most CSS classes. All styling MUST use inline `style=""` attributes.

---

## Color Palette

| Token | Hex | Usage |
|---|---|---|
| Maroon (primary) | `#8C1D40` | Headings, borders, buttons, accents |
| Maroon (dark) | `#5C0F2D` | Gradient endpoints, hover states |
| Maroon (deepest) | `#2D0618` | Gradient terminus for dramatic headers |
| Gold (accent) | `#FFC627` | Highlights, alert borders, module labels, icons |
| Dark surface | `#1B1B2F` | Audio/media section backgrounds |
| Warm cream | `#FFF8E1` | Left-border alert backgrounds |
| Light warm | `#f8f4f0` | Card backgrounds, info boxes |
| Text primary | `#333333` | Body text |
| Text secondary | `#595959` | Subtitles, metadata (meets 4.5:1 on white) |
| Border light | `#e0e0e0` | Card borders, dividers |
| Video blue | `#1565C0` | Video resource cards |
| Reading purple | `#7B1FA2` | Reading resource cards |
| Reference pink | `#AD1457` | Reference resource cards |
| Success green | `#2E7D32` | Completion indicators |

---

## Components

### 1. Module Header Banner

Full-width gradient banner for Overview pages and major section headers.

```html
<div style="background: linear-gradient(135deg, #8C1D40 0%, #4A0A24 70%, #2D0618 100%); color: white; padding: 35px 30px; border-radius: 10px; margin-bottom: 25px;">
  <p style="color: #FFC627; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 1.5px; margin: 0 0 8px 0;">Module {{MODULE_NUMBER}}</p>
  <h2 style="color: white; margin: 0 0 8px 0; font-size: 28px;">{{MODULE_TITLE}}</h2>
  <p style="color: #f0f0f0; margin: 0; font-size: 16px;">{{MODULE_SUBTITLE}}</p>
</div>
```

**When to use**: Overview page header. Can also be used for course-level banners (Getting Started, Final Assessment).

---

### 2. Audio Overview Section (Dark Theme)

Dark-themed container for audio primer embeds. Uses Canvas inline media embed — never links externally.

```html
<div style="background: linear-gradient(135deg, #1B1B2F 0%, #0d0d1a 100%); border-radius: 10px; padding: 30px; margin: 25px 0;">
  <div style="display: flex; align-items: flex-start; gap: 15px; margin-bottom: 15px;">
    <span style="font-size: 28px;">🎧</span>
    <div>
      <h3 style="color: white; margin: 0 0 6px 0; font-size: 20px;">Audio Overview</h3>
      <p style="color: #b0b0b0; margin: 0; font-size: 14px;">~5 minutes | Listen before the lecture to prime your thinking</p>
    </div>
  </div>
  <div style="margin: 15px 0;">
    <a id="media_comment_{{AUDIO_MEDIA_ID}}" class="instructure_inline_media_comment audio_comment">Audio Primer: Module {{MODULE_NUMBER}}</a>
  </div>
  <!-- Transcript toggle injected here by add_transcripts.py -->
</div>
```

**When to use**: Prepare to Learn pages. Audio MUST be uploaded to Canvas Files first; the `{{AUDIO_MEDIA_ID}}` is the Canvas media object ID from upload.

**Fallback** (when audio is not yet available):
```html
<div style="background: linear-gradient(135deg, #1B1B2F 0%, #0d0d1a 100%); border-radius: 10px; padding: 30px; margin: 25px 0;">
  <div style="display: flex; align-items: flex-start; gap: 15px;">
    <span style="font-size: 28px;">🎧</span>
    <div>
      <h3 style="color: white; margin: 0 0 6px 0; font-size: 20px;">Audio Overview</h3>
      <p style="color: #b0b0b0; margin: 0; font-size: 14px;">Audio primer coming soon</p>
    </div>
  </div>
</div>
```

---

### 3. Left-Border Alert (Top-of-Page Context Setter)

Warm-toned callout with gold left border. Used near the top of a page for framing, big-picture context, or key takeaways.

```html
<div style="background-color: #FFF8E1; border-left: 4px solid #FFC627; padding: 20px; border-radius: 0 8px 8px 0; margin: 20px 0;">
  <p style="color: #333; line-height: 1.6; margin: 0;">
    <strong>The big idea:</strong> {{CONTEXT_TEXT}}
  </p>
</div>
```

**Variants**:
- **Key question**: `<strong>Key question:</strong> {{QUESTION}}`
- **Why this matters**: `<strong>Why this matters:</strong> {{RELEVANCE_TEXT}}`
- **Before you begin**: `<strong>Before you begin:</strong> {{PREREQ_TEXT}}`

**When to use**: Near the top of any content page — after the header, before the main content. One per page maximum.

---

### 4. Full-Card Alert (Bottom-of-Page Wrap-Up)

Subtle bordered card for wrap-up messages, completion confirmations, or time estimates. Placed near the bottom of a page.

```html
<div style="background-color: #f9f9f9; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; margin: 25px 0;">
  <p style="color: #333; line-height: 1.6; margin: 0;">
    {{WRAP_UP_TEXT}}
  </p>
</div>
```

**Variants**:
- **With emoji prefix**: Add emoji before text (e.g., `⏱ Estimated time: 30 minutes`)
- **With heading**: Add `<h4 style="color: #8C1D40; margin: 0 0 8px 0;">{{HEADING}}</h4>` before paragraph
- **Success/completion** (green accent): Change border to `border: 1px solid #c8e6c9; background-color: #f1f8e9;`

**When to use**: Bottom of a page, before any navigation button. Completion checklists, time estimates, "what's next" notes.

---

### 5. Numbered Concept Items

Numbered cards with maroon circle indicators. Used for key concepts on Lesson pages.

```html
<div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; margin-bottom: 15px; display: flex; gap: 15px; align-items: flex-start;">
  <div style="background-color: #8C1D40; color: white; width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 16px; flex-shrink: 0;">1</div>
  <div style="flex: 1;">
    <h4 style="color: #8C1D40; margin: 0 0 8px 0;">{{CONCEPT_TITLE}}</h4>
    <p style="color: #333; line-height: 1.6; margin: 0;">{{CONCEPT_DESCRIPTION}}</p>
    <!-- Optional key terms callout inside the card -->
    <div style="background-color: #f8f4f0; border-radius: 6px; padding: 12px; margin-top: 12px;">
      <p style="color: #595959; font-size: 13px; margin: 0;"><strong>Key terms:</strong> {{TERMS_LIST}}</p>
    </div>
  </div>
</div>
```

**When to use**: Lesson pages for key concepts (typically 3-5 items). The inner callout (key terms, mechanism, example) is optional per item.

---

### 6. Concept Grid (2-Column Cards)

Two-column card layout for cross-references, connections, or category overviews.

```html
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0;">
  <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
    <h4 style="color: #8C1D40; margin: 0 0 8px 0;">{{CARD_1_TITLE}}</h4>
    <p style="color: #595959; line-height: 1.5; margin: 0; font-size: 14px;">{{CARD_1_TEXT}}</p>
  </div>
  <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
    <h4 style="color: #8C1D40; margin: 0 0 8px 0;">{{CARD_2_TITLE}}</h4>
    <p style="color: #595959; line-height: 1.5; margin: 0; font-size: 14px;">{{CARD_2_TEXT}}</p>
  </div>
  <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
    <h4 style="color: #8C1D40; margin: 0 0 8px 0;">{{CARD_3_TITLE}}</h4>
    <p style="color: #595959; line-height: 1.5; margin: 0; font-size: 14px;">{{CARD_3_TEXT}}</p>
  </div>
  <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
    <h4 style="color: #8C1D40; margin: 0 0 8px 0;">{{CARD_4_TITLE}}</h4>
    <p style="color: #595959; line-height: 1.5; margin: 0; font-size: 14px;">{{CARD_4_TEXT}}</p>
  </div>
</div>
```

**When to use**: Overview pages for "Where This Shows Up" sections, Conclusion pages for cross-module connections. Works with 2 or 4 cards (use `grid-template-columns: 1fr` for single-column fallback on mobile — Canvas handles this via viewport).

---

### 7. Resource Cards (Color-Coded by Type)

Individual resource cards with type-specific color coding. Replace plain tables on Lesson and Resources pages.

#### Video Resource (Blue)
```html
<div style="border: 1px solid #BBDEFB; border-radius: 8px; padding: 20px; margin-bottom: 15px; background-color: #E3F2FD;">
  <div style="display: flex; align-items: flex-start; gap: 12px;">
    <span style="font-size: 20px;">🎬</span>
    <div style="flex: 1;">
      <p style="color: #1565C0; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 4px 0;">Video</p>
      <h4 style="margin: 0 0 6px 0;"><a href="{{RESOURCE_URL}}" target="_blank" rel="noopener noreferrer" style="color: #333; text-decoration: none;">{{RESOURCE_TITLE}} <span style="position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0;">(opens in new tab)</span></a></h4>
      <p style="color: #595959; font-size: 13px; margin: 0 0 4px 0;">{{AUTHOR_OR_SOURCE}} &middot; {{DURATION}}</p>
      <p style="color: #333; line-height: 1.5; margin: 0; font-size: 14px;">{{RESOURCE_DESCRIPTION}}</p>
    </div>
  </div>
</div>
```

#### Reading Resource (Purple)
```html
<div style="border: 1px solid #CE93D8; border-radius: 8px; padding: 20px; margin-bottom: 15px; background-color: #F3E5F5;">
  <div style="display: flex; align-items: flex-start; gap: 12px;">
    <span style="font-size: 20px;">📖</span>
    <div style="flex: 1;">
      <p style="color: #7B1FA2; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 4px 0;">Reading</p>
      <h4 style="margin: 0 0 6px 0;"><a href="{{RESOURCE_URL}}" target="_blank" rel="noopener noreferrer" style="color: #333; text-decoration: none;">{{RESOURCE_TITLE}} <span style="position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0;">(opens in new tab)</span></a></h4>
      <p style="color: #595959; font-size: 13px; margin: 0 0 4px 0;">{{AUTHOR_OR_SOURCE}}</p>
      <p style="color: #333; line-height: 1.5; margin: 0; font-size: 14px;">{{RESOURCE_DESCRIPTION}}</p>
    </div>
  </div>
</div>
```

#### Reference Resource (Pink)
```html
<div style="border: 1px solid #F48FB1; border-radius: 8px; padding: 20px; margin-bottom: 15px; background-color: #FCE4EC;">
  <div style="display: flex; align-items: flex-start; gap: 12px;">
    <span style="font-size: 20px;">📋</span>
    <div style="flex: 1;">
      <p style="color: #AD1457; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 4px 0;">Reference</p>
      <h4 style="margin: 0 0 6px 0;"><a href="{{RESOURCE_URL}}" target="_blank" rel="noopener noreferrer" style="color: #333; text-decoration: none;">{{RESOURCE_TITLE}} <span style="position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0;">(opens in new tab)</span></a></h4>
      <p style="color: #595959; font-size: 13px; margin: 0 0 4px 0;">{{SOURCE}}</p>
      <p style="color: #333; line-height: 1.5; margin: 0; font-size: 14px;">{{RESOURCE_DESCRIPTION}}</p>
    </div>
  </div>
</div>
```

**When to use**: Lesson pages (replacing the plain resource table), Resources pages, any page listing external materials.

---

### 8. CTA Button (Primary Action)

Maroon call-to-action button for primary actions (start quiz, submit assignment, open external tool).

```html
<div style="text-align: center; margin: 30px 0;">
  <a href="{{ACTION_URL}}"
     style="display: inline-block; background-color: #8C1D40; color: white; padding: 15px 40px; border-radius: 6px; text-decoration: none; font-size: 18px; font-weight: bold;">
    {{BUTTON_TEXT}} →
  </a>
</div>
```

**When to use**: One per page maximum for the primary action. Quiz launch, assignment submission, external tool links.

---

### 9. Navigation Button

"Continue to next page" navigation. Consistent across all page types.

```html
<div style="text-align: center; margin: 30px 0; padding-top: 20px; border-top: 1px solid #e0e0e0;">
  <a href="{{NEXT_PAGE_URL}}"
     style="display: inline-block; background-color: #8C1D40; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-size: 16px; font-weight: 600;">
    Continue to {{NEXT_PAGE_TITLE}} →
  </a>
</div>
```

**When to use**: Bottom of every page except the last page in a module (Conclusion). Optional — Canvas sidebar navigation also works, but this gives a clear next step.

---

### 10. Left-Border Info Box (Maroon)

General-purpose info box with maroon left border. More neutral than the gold alert — for details, not framing.

```html
<div style="background-color: #f8f4f0; border-left: 4px solid #8C1D40; padding: 20px; border-radius: 0 8px 8px 0; margin-bottom: 20px;">
  <h4 style="color: #8C1D40; margin: 0 0 10px 0;">{{HEADING}}</h4>
  <p style="color: #333; line-height: 1.6; margin: 0;">{{CONTENT}}</p>
</div>
```

**When to use**: Quiz details, assignment scenarios, learning objectives. The existing maroon-bordered boxes in current templates.

---

### 11. Video Placeholder

Styled placeholder for lesson pages when lecture video is not yet available.

```html
<div style="border: 2px dashed #ccc; border-radius: 10px; padding: 40px 30px; margin: 25px 0; text-align: center; background-color: #fafafa;">
  <p style="font-size: 32px; margin: 0 0 10px 0;">📹</p>
  <h3 style="color: #8C1D40; margin: 0 0 8px 0;">Lecture Video Coming Soon</h3>
  <p style="color: #595959; margin: 0; font-size: 14px;">Module {{MODULE_NUMBER}}: {{MODULE_TITLE}} &middot; ~{{ESTIMATED_DURATION}} minutes</p>
  <p style="color: #595959; margin: 8px 0 0 0; font-size: 13px;">Covers: {{OBJECTIVES_SUMMARY}}</p>
</div>
```

**When to use**: Lesson pages when the instructor hasn't recorded the lecture yet. Used by the `lecture-support` skill's placeholder mode.

---

### 12. Interactive Activity Container

Styled wrapper for embedded HTML interactive activities (iframes).

```html
<div style="margin: 25px 0; padding: 20px; background-color: #f8f4f0; border: 1px solid #ddd; border-radius: 8px;">
  <h3 style="color: #8C1D40; margin: 0 0 5px 0;">{{ACTIVITY_TITLE}}</h3>
  <p style="color: #595959; font-size: 14px; margin: 0 0 12px 0;">{{ACTIVITY_TYPE}} | ~{{DURATION}} min | Formative (not graded)</p>
  <iframe src="/courses/{{COURSE_ID}}/files/{{FILE_ID}}/preview"
          width="100%" height="550"
          style="border: 1px solid #ccc; border-radius: 6px;"
          sandbox="allow-same-origin allow-scripts allow-forms"
          title="{{ACTIVITY_TITLE}}"
          loading="lazy"></iframe>
</div>
```

**When to use**: Prepare to Learn pages (dialog cards), Guided Practice pages (all interactive types).

---

## Component Composition Guidelines

### Overview Page
1. Module Header Banner
2. Left-Border Alert ("Why this matters" or welcome text)
3. Left-Border Info Box (Learning Objectives)
4. Module Roadmap (table — keep existing table pattern)
5. Concept Grid (professional/clinical connections)
6. Full-Card Alert (estimated time + "complete in order" note)

### Prepare to Learn Page
1. Page heading + subtitle
2. Left-Border Alert (intro framing)
3. Audio Overview Section (Dark Theme)
4. Interactive Activity Container (dialog cards)
5. "What to Think About" questions
6. Full-Card Alert (transition note)

### Lesson Page
1. Page heading + subtitle
2. Left-Border Alert (key question or big idea)
3. Video embed (or Video Placeholder)
4. Numbered Concept Items (3-5)
5. Resource Cards (color-coded by type)
6. Full-Card Alert (review reminder)

### Knowledge Check Page
1. Page heading + subtitle
2. Left-Border Info Box (quiz details: questions, points, attempts)
3. Left-Border Alert (tips for success — gold border)
4. Topics covered list
5. CTA Button (start quiz)

### Guided Practice Page
1. Page heading + subtitle
2. Left-Border Alert (formative note)
3. Instructions
4. Interactive Activity Containers (1-2 activities)
5. "After You Practice" reflection
6. CTA Button (submit)

### Create an Artifact Page
1. Page heading + subtitle
2. Left-Border Info Box (scenario/context)
3. Task list (ordered)
4. Submission requirements
5. Rubric summary table
6. Left-Border Alert (tips for success — gold border)
7. CTA Button (submit)

### Conclusion Page
1. Page heading + subtitle
2. Left-Border Info Box (key takeaways)
3. Discussion link + CTA Button
4. Self-assessment table
5. Concept Grid (connections forward)
6. Full-Card Alert (completion checklist — green accent)

### Resources Page
1. Module Header Banner (or simple heading)
2. Resource Cards grouped by type (Video, Reading, Reference)
3. Full-Card Alert (course-specific help info)
