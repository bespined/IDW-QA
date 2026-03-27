#!/usr/bin/env python3
"""Generate interactive HTML activities for Canvas courses.

Supports 5 activity types:
  - dialog_cards: Flip-card flashcards
  - sequencing: Drag-and-order items
  - fill_blanks: Fill-in-the-blank passages
  - branching: Branching scenario with decision points
  - quiz: Multi-question formative quiz

Usage:
    python generator.py <content_data_path> [--output-dir <dir>]

    content_data_path: Python file containing ALL_ACTIVITIES dict
    --output-dir: Where to write HTML files (default: ./output)

Content data format:
    The content data file must define ALL_ACTIVITIES as a dict:
    {
        "m1": [
            {"type": "dialog_cards", "filename": "m1-vocab.html", "title": "...", "cards": [...]},
            ...
        ],
        "m2": [...],
    }

    See the interactive-content skill for full schema per activity type.
"""

import os
import sys
import json
import argparse
import html as html_module

# Logging
try:
    from idw_logger import get_logger
    _log = get_logger("generator")
except ImportError:
    import logging
    _log = logging.getLogger("generator")

try:
    from idw_metrics import track as _track
except ImportError:
    def _track(*a, **k): pass


# ============================================================
# SHARED CSS (ASU-branded, WCAG 2.1 AA compliant)
# ============================================================
SHARED_CSS = """
:root {
    --asu-maroon: #8C1D40;
    --asu-gold: #FFC627;
    --white: #FFFFFF;
    --bg-light: #f8f4f0;
    --bg-gray: #f5f5f5;
    --text-dark: #333333;
    --text-muted: #595959;
    --success: #28a745;
    --error: #dc3545;
    --border-radius: 8px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background: var(--white);
    color: var(--text-dark);
    font-size: 16px;
    line-height: 1.6;
    padding: 20px;
    max-width: 800px;
    margin: 0 auto;
}
h2 { color: var(--asu-maroon); margin-bottom: 12px; font-size: 1.4em; }
h3 { color: var(--asu-maroon); margin-bottom: 8px; font-size: 1.15em; }
p { margin-bottom: 12px; }
button {
    cursor: pointer;
    font-size: 16px;
    border: none;
    border-radius: var(--border-radius);
    padding: 12px 28px;
    font-weight: 600;
    min-height: 44px;
    min-width: 44px;
    transition: background 0.2s, transform 0.1s;
}
button:focus-visible { outline: 3px solid var(--asu-gold); outline-offset: 2px; }
button:active { transform: scale(0.97); }
.btn-primary { background: var(--asu-maroon); color: var(--white); }
.btn-primary:hover { background: #6d1633; }
.btn-secondary { background: var(--bg-gray); color: var(--text-dark); border: 1px solid #ccc; }
.btn-secondary:hover { background: #e8e8e8; }
.btn-success { background: var(--success); color: var(--white); }
.btn-disabled { background: #ccc; color: #888; cursor: not-allowed; }
.feedback-box {
    padding: 15px 18px; border-radius: var(--border-radius); margin: 15px 0;
    font-size: 15px; line-height: 1.5; display: none;
}
.feedback-correct { background: #d4edda; border-left: 4px solid var(--success); color: #155724; }
.feedback-incorrect { background: #f8d7da; border-left: 4px solid var(--error); color: #721c24; }
.progress-bar {
    background: var(--bg-gray); border-radius: 20px; height: 8px; margin-bottom: 20px; overflow: hidden;
}
.progress-fill {
    background: var(--asu-maroon); height: 100%; border-radius: 20px; transition: width 0.4s ease;
}
.sr-only {
    position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
    overflow: hidden; clip: rect(0,0,0,0); border: 0;
}
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
@media (max-width: 600px) {
    body { padding: 12px; font-size: 15px; }
    button { padding: 10px 20px; font-size: 15px; }
}
"""


# ============================================================
# TEMPLATE: DIALOG CARDS
# ============================================================
def generate_dialog_cards(data):
    cards_json = json.dumps(data["cards"])
    title = html_module.escape(data["title"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
{SHARED_CSS}
.cards-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; margin: 20px 0; }}
.card-container {{ perspective: 1000px; height: 200px; cursor: pointer; }}
.card-inner {{
    position: relative; width: 100%; height: 100%;
    transition: transform 0.5s; transform-style: preserve-3d;
}}
.card-container.flipped .card-inner {{ transform: rotateY(180deg); }}
.card-front, .card-back {{
    position: absolute; width: 100%; height: 100%; backface-visibility: hidden;
    border-radius: var(--border-radius); display: flex; align-items: center;
    justify-content: center; padding: 20px; text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.12);
}}
.card-front {{
    background: var(--asu-maroon); color: var(--white);
    font-size: 1.2em; font-weight: 600;
}}
.card-back {{
    background: var(--white); color: var(--text-dark); border: 2px solid var(--asu-maroon);
    transform: rotateY(180deg); font-size: 0.95em; line-height: 1.5;
    overflow-y: auto; align-items: flex-start;
}}
.card-hint {{ font-size: 12px; color: var(--text-muted); margin-top: 8px; }}
.controls {{ display: flex; gap: 12px; justify-content: center; margin: 20px 0; flex-wrap: wrap; }}
.counter {{ text-align: center; color: var(--text-muted); font-size: 14px; margin-bottom: 8px; }}
@media (prefers-reduced-motion: reduce) {{
    .card-inner {{ transition: none; }}
}}
</style>
</head>
<body>
<h2>{title}</h2>
<p>Click or tap each card to reveal the definition. Use the Shuffle button to test yourself in a different order.</p>
<div class="counter" aria-live="polite"><span id="flipped-count">0</span> of <span id="total-count">0</span> cards reviewed</div>
<div class="progress-bar" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100" aria-label="Cards reviewed" id="progress-bar"><div class="progress-fill" id="progress" style="width:0%"></div></div>
<div class="cards-grid" id="cards-grid" role="group" aria-label="Flashcards"></div>
<div class="controls">
  <button class="btn-secondary" onclick="shuffleCards()" aria-label="Shuffle cards">Shuffle</button>
  <button class="btn-secondary" onclick="resetCards()" aria-label="Reset all cards">Reset</button>
</div>
<script>
const CARDS = {cards_json};
let flippedSet = new Set();
function render(cards) {{
    const grid = document.getElementById('cards-grid');
    grid.innerHTML = '';
    document.getElementById('total-count').textContent = cards.length;
    cards.forEach((c, i) => {{
        const container = document.createElement('div');
        container.className = 'card-container';
        container.setAttribute('tabindex', '0');
        container.setAttribute('role', 'button');
        container.setAttribute('aria-label', 'Flashcard ' + (i+1) + ' of ' + cards.length + ': ' + c.front + '. Press Enter to flip.');
        container.innerHTML = '<div class="card-inner"><div class="card-front">' + c.front +
            '</div><div class="card-back">' + c.back + '</div></div>';
        container.addEventListener('click', () => flipCard(container, i));
        container.addEventListener('keydown', e => {{ if(e.key==='Enter'||e.key===' ') {{ e.preventDefault(); flipCard(container, i); }} }});
        grid.appendChild(container);
    }});
    updateProgress();
}}
function flipCard(el, idx) {{
    el.classList.toggle('flipped');
    if(el.classList.contains('flipped')) flippedSet.add(idx); else flippedSet.delete(idx);
    updateProgress();
}}
function updateProgress() {{
    const total = CARDS.length;
    const pct = Math.round(flippedSet.size/total*100);
    document.getElementById('flipped-count').textContent = flippedSet.size;
    document.getElementById('progress').style.width = pct+'%';
    document.getElementById('progress-bar').setAttribute('aria-valuenow', pct);
}}
function shuffleCards() {{
    const arr = [...CARDS];
    for(let i=arr.length-1;i>0;i--){{ const j=Math.floor(Math.random()*(i+1));[arr[i],arr[j]]=[arr[j],arr[i]]; }}
    flippedSet.clear();
    render(arr);
}}
function resetCards() {{ flippedSet.clear(); render(CARDS); }}
render(CARDS);
</script>
</body></html>"""


# ============================================================
# TEMPLATE: SEQUENCING
# ============================================================
def generate_sequencing(data):
    items_json = json.dumps(data["items"])
    title = html_module.escape(data["title"])
    instruction = html_module.escape(data["instruction"])
    fb_correct = json.dumps(data["feedback_correct"])
    fb_incorrect = json.dumps(data["feedback_incorrect"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
{SHARED_CSS}
.seq-container {{ display: flex; gap: 20px; margin: 20px 0; flex-wrap: wrap; }}
.slots-col, .items-col {{ flex: 1; min-width: 250px; }}
.slot {{
    min-height: 52px; border: 2px dashed #ccc; border-radius: var(--border-radius);
    padding: 12px 16px; margin-bottom: 10px; display: flex; align-items: center;
    gap: 10px; transition: border-color 0.2s;
}}
.slot-num {{
    background: var(--asu-maroon); color: var(--white); width: 28px; height: 28px;
    border-radius: 50%; display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 14px; flex-shrink: 0;
}}
.slot.filled {{ border-color: var(--asu-maroon); border-style: solid; background: #fdf6f8; cursor: pointer; }}
.slot.correct {{ border-color: var(--success); background: #d4edda; }}
.slot.incorrect {{ border-color: var(--error); background: #f8d7da; }}
.item-card {{
    background: var(--white); border: 2px solid var(--asu-maroon); border-radius: var(--border-radius);
    padding: 12px 16px; margin-bottom: 10px; cursor: pointer;
    transition: background 0.2s, transform 0.1s; min-height: 44px;
}}
.item-card:hover {{ background: #fdf6f8; }}
.item-card:focus-visible {{ outline: 3px solid var(--asu-gold); outline-offset: 2px; }}
.item-card.selected {{ background: var(--asu-gold); border-color: var(--asu-gold); color: var(--text-dark); }}
.item-card.used {{ opacity: 0.4; pointer-events: none; }}
.controls {{ display: flex; gap: 12px; justify-content: center; margin: 20px 0; flex-wrap: wrap; }}
.slot-text {{ font-size: 15px; }}
</style>
</head>
<body>
<h2>{title}</h2>
<p>{instruction}</p>
<p style="color:var(--text-muted);font-size:14px;">Click an item on the right, then click a numbered slot on the left to place it. Click a filled slot to remove it.</p>
<div class="seq-container">
  <div class="slots-col" id="slots" role="list" aria-label="Answer slots"></div>
  <div class="items-col" id="items" role="listbox" aria-label="Available items"></div>
</div>
<div class="controls">
  <button class="btn-primary" id="check-btn" onclick="checkAnswer()">Check Answer</button>
  <button class="btn-secondary" id="retry-btn" onclick="retry()" style="display:none">Try Again</button>
  <button class="btn-secondary" id="show-btn" onclick="showAnswer()" style="display:none">Show Answer</button>
  <button class="btn-secondary" onclick="resetAll()">Reset</button>
</div>
<div class="feedback-box" id="feedback" role="alert"></div>
<script>
const ITEMS = {items_json};
const FB_CORRECT = {fb_correct};
const FB_INCORRECT = {fb_incorrect};
let selectedItem = null;
let placements = new Array(ITEMS.length).fill(null);
let attempts = 0;
let shuffled = [];
function init() {{
    shuffled = [...ITEMS].sort(() => Math.random() - 0.5);
    const slotsEl = document.getElementById('slots');
    const itemsEl = document.getElementById('items');
    slotsEl.innerHTML = '';
    itemsEl.innerHTML = '';
    placements = new Array(ITEMS.length).fill(null);
    selectedItem = null;
    attempts = 0;
    document.getElementById('feedback').style.display = 'none';
    document.getElementById('check-btn').style.display = '';
    document.getElementById('retry-btn').style.display = 'none';
    document.getElementById('show-btn').style.display = 'none';
    for (let i = 0; i < ITEMS.length; i++) {{
        const slot = document.createElement('div');
        slot.className = 'slot';
        slot.setAttribute('role', 'listitem');
        slot.setAttribute('tabindex', '0');
        slot.setAttribute('aria-label', 'Position ' + (i+1) + ', empty');
        slot.innerHTML = '<span class="slot-num">' + (i+1) + '</span><span class="slot-text" id="slot-text-'+i+'"></span>';
        slot.addEventListener('click', () => slotClick(i));
        slot.addEventListener('keydown', e => {{ if(e.key==='Enter'||e.key===' ') {{ e.preventDefault(); slotClick(i); }} }});
        slotsEl.appendChild(slot);
    }}
    shuffled.forEach((item, idx) => {{
        const card = document.createElement('div');
        card.className = 'item-card';
        card.setAttribute('tabindex', '0');
        card.setAttribute('role', 'option');
        card.setAttribute('data-idx', idx);
        card.textContent = item.text;
        card.addEventListener('click', () => selectItem(idx, card));
        card.addEventListener('keydown', e => {{ if(e.key==='Enter'||e.key===' ') {{ e.preventDefault(); selectItem(idx, card); }} }});
        itemsEl.appendChild(card);
    }});
}}
function selectItem(idx, el) {{
    document.querySelectorAll('.item-card').forEach(c => c.classList.remove('selected'));
    if (selectedItem === idx) {{ selectedItem = null; return; }}
    selectedItem = idx;
    el.classList.add('selected');
}}
function slotClick(slotIdx) {{
    if (placements[slotIdx] !== null) {{
        const removedIdx = placements[slotIdx];
        placements[slotIdx] = null;
        document.getElementById('slot-text-'+slotIdx).textContent = '';
        const slot = document.querySelectorAll('.slot')[slotIdx];
        slot.classList.remove('filled','correct','incorrect');
        slot.setAttribute('aria-label', 'Position '+(slotIdx+1)+', empty');
        document.querySelectorAll('.item-card')[removedIdx].classList.remove('used');
        return;
    }}
    if (selectedItem === null) return;
    placements[slotIdx] = selectedItem;
    document.getElementById('slot-text-'+slotIdx).textContent = shuffled[selectedItem].text;
    const slot = document.querySelectorAll('.slot')[slotIdx];
    slot.classList.add('filled');
    slot.setAttribute('aria-label', 'Position '+(slotIdx+1)+': '+shuffled[selectedItem].text);
    document.querySelectorAll('.item-card')[selectedItem].classList.add('used');
    document.querySelectorAll('.item-card').forEach(c => c.classList.remove('selected'));
    selectedItem = null;
}}
function checkAnswer() {{
    if (placements.some(p => p === null)) {{
        const fb = document.getElementById('feedback');
        fb.style.display = 'block';
        fb.className = 'feedback-box feedback-incorrect';
        fb.innerHTML = 'Please place all items in the slots before checking your answer.';
        return;
    }}
    attempts++;
    let allCorrect = true;
    placements.forEach((itemIdx, slotIdx) => {{
        const slot = document.querySelectorAll('.slot')[slotIdx];
        if (shuffled[itemIdx].position === slotIdx + 1) {{
            slot.classList.add('correct');
            slot.classList.remove('incorrect');
        }} else {{
            slot.classList.add('incorrect');
            slot.classList.remove('correct');
            allCorrect = false;
        }}
    }});
    const fb = document.getElementById('feedback');
    fb.style.display = 'block';
    if (allCorrect) {{
        fb.className = 'feedback-box feedback-correct';
        fb.innerHTML = '<strong>Correct!</strong> ' + FB_CORRECT;
        document.getElementById('check-btn').style.display = 'none';
    }} else {{
        fb.className = 'feedback-box feedback-incorrect';
        fb.innerHTML = '<strong>Not quite.</strong> ' + FB_INCORRECT;
        document.getElementById('retry-btn').style.display = '';
        document.getElementById('check-btn').style.display = 'none';
        if (attempts >= 2) document.getElementById('show-btn').style.display = '';
    }}
}}
function retry() {{
    placements.forEach((_, i) => {{
        const slot = document.querySelectorAll('.slot')[i];
        if (slot.classList.contains('incorrect')) {{
            const itemIdx = placements[i];
            placements[i] = null;
            document.getElementById('slot-text-'+i).textContent = '';
            slot.classList.remove('filled','incorrect');
            slot.setAttribute('aria-label', 'Position '+(i+1)+', empty');
            document.querySelectorAll('.item-card')[itemIdx].classList.remove('used');
        }}
    }});
    document.getElementById('feedback').style.display = 'none';
    document.getElementById('retry-btn').style.display = 'none';
    document.getElementById('check-btn').style.display = '';
}}
function showAnswer() {{
    placements = new Array(ITEMS.length).fill(null);
    document.querySelectorAll('.item-card').forEach(c => c.classList.add('used'));
    ITEMS.forEach(item => {{
        const slotIdx = item.position - 1;
        const shuffIdx = shuffled.findIndex(s => s.text === item.text);
        placements[slotIdx] = shuffIdx;
        document.getElementById('slot-text-'+slotIdx).textContent = item.text;
        const slot = document.querySelectorAll('.slot')[slotIdx];
        slot.classList.add('filled','correct');
        slot.classList.remove('incorrect');
        slot.setAttribute('aria-label', 'Position '+(slotIdx+1)+': '+item.text);
    }});
    const fb = document.getElementById('feedback');
    fb.style.display = 'block';
    fb.className = 'feedback-box feedback-correct';
    fb.innerHTML = '<strong>Answer revealed.</strong> ' + FB_CORRECT;
    document.getElementById('check-btn').style.display = 'none';
    document.getElementById('retry-btn').style.display = 'none';
    document.getElementById('show-btn').style.display = 'none';
}}
function resetAll() {{ init(); }}
init();
</script>
</body></html>"""


# ============================================================
# TEMPLATE: FILL IN THE BLANKS
# ============================================================
def generate_fill_blanks(data):
    title = html_module.escape(data["title"])
    instruction = html_module.escape(data["instruction"])
    passages_json = json.dumps(data["passages"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
{SHARED_CSS}
.passage {{
    background: var(--bg-light); border-left: 4px solid var(--asu-maroon);
    padding: 20px; border-radius: 0 var(--border-radius) var(--border-radius) 0;
    margin: 20px 0; line-height: 1.8; font-size: 16px;
}}
.blank-input {{
    border: none; border-bottom: 2px solid var(--asu-maroon); background: transparent;
    font-size: 16px; padding: 2px 8px; min-width: 120px; max-width: 200px;
    font-family: inherit; color: var(--text-dark);
}}
.blank-input:focus {{ outline: none; border-bottom-color: var(--asu-gold); border-bottom-width: 3px; }}
.blank-input.correct {{ border-bottom-color: var(--success); background: #d4edda; }}
.blank-input.incorrect {{ border-bottom-color: var(--error); background: #f8d7da; }}
.hint {{ font-size: 13px; color: var(--error); margin-top: 4px; display: none; font-style: italic; }}
.passage-feedback {{
    margin-top: 12px; padding: 12px; border-radius: var(--border-radius);
    background: #d4edda; border-left: 4px solid var(--success); display: none;
    font-size: 15px; line-height: 1.5;
}}
.controls {{ display: flex; gap: 12px; justify-content: center; margin: 20px 0; flex-wrap: wrap; }}
</style>
</head>
<body>
<h2>{title}</h2>
<p>{instruction}</p>
<div id="passages-container"></div>
<div class="controls">
  <button class="btn-primary" id="check-btn" onclick="checkAll()">Check Answers</button>
  <button class="btn-secondary" id="retry-btn" onclick="retryIncorrect()" style="display:none">Try Again</button>
  <button class="btn-secondary" id="show-btn" onclick="showAll()" style="display:none">Show Answers</button>
</div>
<script>
const PASSAGES = {passages_json};
let attempts = 0;
function init() {{
    const container = document.getElementById('passages-container');
    container.innerHTML = '';
    attempts = 0;
    document.getElementById('check-btn').style.display = '';
    document.getElementById('retry-btn').style.display = 'none';
    document.getElementById('show-btn').style.display = 'none';
    PASSAGES.forEach((p, pi) => {{
        const div = document.createElement('div');
        div.className = 'passage';
        let html = '';
        p.segments.forEach((seg, si) => {{
            if (seg.type === 'text') {{
                html += seg.value;
            }} else {{
                const id = 'blank-'+pi+'-'+si;
                html += '<input type="text" class="blank-input" id="'+id+'" data-passage="'+pi+'" data-seg="'+si+'" aria-label="'+seg.hint+'" autocomplete="off" spellcheck="false">';
                html += '<span class="hint" role="status" id="hint-'+pi+'-'+si+'">Hint: '+seg.hint+'</span>';
            }}
        }});
        html += '<div class="passage-feedback" aria-live="polite" id="pfb-'+pi+'">'+p.feedback+'</div>';
        div.innerHTML = html;
        container.appendChild(div);
    }});
}}
function normalize(s) {{ return s.trim().toLowerCase().replace(/[^a-z0-9\u03b1-\u03c9\u0391-\u03a9\u207a\u207b\u208a\u208b+\\-\\/]/g, ''); }}
function checkAll() {{
    attempts++;
    let allCorrect = true;
    PASSAGES.forEach((p, pi) => {{
        let passageCorrect = true;
        p.segments.forEach((seg, si) => {{
            if (seg.type !== 'blank') return;
            const input = document.getElementById('blank-'+pi+'-'+si);
            const val = normalize(input.value);
            const correct = seg.answers.some(a => normalize(a) === val);
            if (correct) {{
                input.classList.add('correct');
                input.classList.remove('incorrect');
                input.readOnly = true;
                document.getElementById('hint-'+pi+'-'+si).style.display = 'none';
            }} else {{
                input.classList.add('incorrect');
                input.classList.remove('correct');
                document.getElementById('hint-'+pi+'-'+si).style.display = 'block';
                allCorrect = false;
                passageCorrect = false;
            }}
        }});
        if (passageCorrect) document.getElementById('pfb-'+pi).style.display = 'block';
    }});
    if (allCorrect) {{
        document.getElementById('check-btn').style.display = 'none';
    }} else {{
        document.getElementById('retry-btn').style.display = '';
        document.getElementById('check-btn').style.display = 'none';
        if (attempts >= 2) document.getElementById('show-btn').style.display = '';
    }}
}}
function retryIncorrect() {{
    document.querySelectorAll('.blank-input.incorrect').forEach(el => {{
        el.value = '';
        el.classList.remove('incorrect');
    }});
    document.querySelectorAll('.hint').forEach(h => h.style.display = 'none');
    document.getElementById('retry-btn').style.display = 'none';
    document.getElementById('check-btn').style.display = '';
}}
function showAll() {{
    PASSAGES.forEach((p, pi) => {{
        p.segments.forEach((seg, si) => {{
            if (seg.type !== 'blank') return;
            const input = document.getElementById('blank-'+pi+'-'+si);
            input.value = seg.answers[0];
            input.classList.add('correct');
            input.classList.remove('incorrect');
            input.readOnly = true;
            document.getElementById('hint-'+pi+'-'+si).style.display = 'none';
        }});
        document.getElementById('pfb-'+pi).style.display = 'block';
    }});
    document.getElementById('check-btn').style.display = 'none';
    document.getElementById('retry-btn').style.display = 'none';
    document.getElementById('show-btn').style.display = 'none';
}}
init();
</script>
</body></html>"""


# ============================================================
# TEMPLATE: BRANCHING SCENARIO
# ============================================================
def generate_branching(data):
    title = html_module.escape(data["title"])
    nodes_json = json.dumps(data["nodes"])
    endpoints_json = json.dumps(data["endpoints"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
{SHARED_CSS}
.scenario-box {{
    background: var(--bg-light); border-left: 4px solid var(--asu-maroon);
    padding: 20px; border-radius: 0 var(--border-radius) var(--border-radius) 0;
    margin: 15px 0; font-size: 16px; line-height: 1.6;
}}
.option-card {{
    border: 2px solid #ddd; border-radius: var(--border-radius);
    padding: 14px 18px; margin: 10px 0; cursor: pointer;
    transition: border-color 0.2s, background 0.2s; min-height: 44px;
}}
.option-card:hover {{ border-color: var(--asu-maroon); background: #fdf6f8; }}
.option-card:focus-visible {{ outline: 3px solid var(--asu-gold); outline-offset: 2px; }}
.option-card.selected {{ border-color: var(--asu-maroon); background: #fdf6f8; }}
.option-card.correct-choice {{ border-color: var(--success); background: #d4edda; }}
.option-card.incorrect-choice {{ border-color: var(--error); background: #f8d7da; }}
.option-card.disabled {{ pointer-events: none; opacity: 0.7; }}
.option-label {{ font-weight: 600; color: var(--asu-maroon); margin-right: 8px; }}
.breadcrumb {{
    display: flex; gap: 8px; align-items: center; margin: 15px 0;
    font-size: 13px; color: var(--text-muted); flex-wrap: wrap;
}}
.breadcrumb span {{ background: var(--bg-gray); padding: 4px 10px; border-radius: 12px; }}
.breadcrumb span.active {{ background: var(--asu-maroon); color: var(--white); }}
.breadcrumb .arrow {{ background: none; padding: 0; }}
.endpoint {{
    text-align: center; padding: 30px; border: 2px solid var(--asu-maroon);
    border-radius: var(--border-radius); margin: 20px 0;
}}
.endpoint h3 {{ margin-bottom: 10px; }}
.score {{ font-size: 2em; color: var(--asu-maroon); font-weight: 700; margin: 10px 0; }}
.controls {{ display: flex; gap: 12px; justify-content: center; margin: 20px 0; flex-wrap: wrap; }}
</style>
</head>
<body>
<h2>{title}</h2>
<div class="breadcrumb" id="breadcrumb" aria-label="Progress"></div>
<div id="content-area"></div>
<div class="controls" id="controls"></div>
<script>
const NODES = {nodes_json};
const ENDPOINTS = {endpoints_json};
let currentNode = 0;
let score = 0;
let history = [];
function renderNode(idx) {{
    currentNode = idx;
    const node = NODES[idx];
    const area = document.getElementById('content-area');
    const controls = document.getElementById('controls');
    const bc = document.getElementById('breadcrumb');
    bc.innerHTML = '';
    for (let i = 0; i <= idx; i++) {{
        if (i > 0) {{ const arrow = document.createElement('span'); arrow.className='arrow'; arrow.textContent='\u2192'; bc.appendChild(arrow); }}
        const s = document.createElement('span');
        s.textContent = 'Decision ' + (i+1);
        if (i === idx) s.className = 'active';
        bc.appendChild(s);
    }}
    let html = '<div class="scenario-box">' + node.scenario + '</div>';
    html += '<h3>' + node.question + '</h3>';
    html += '<div role="radiogroup" aria-label="Choose your answer">';
    const labels = ['A','B','C','D'];
    node.options.forEach((opt, oi) => {{
        html += '<div class="option-card" tabindex="0" role="radio" aria-checked="false" data-idx="'+oi+'" onclick="selectOption('+idx+','+oi+')">';
        html += '<span class="option-label">' + labels[oi] + '.</span> ' + opt.text + '</div>';
    }});
    html += '</div>';
    html += '<div class="feedback-box" id="option-feedback" role="alert"></div>';
    area.innerHTML = html;
    controls.innerHTML = '<button class="btn-primary" id="continue-btn" onclick="advance()" style="display:none">Continue</button>';
}}
function selectOption(nodeIdx, optIdx) {{
    const node = NODES[nodeIdx];
    const opt = node.options[optIdx];
    document.querySelectorAll('.option-card').forEach(c => {{
        c.classList.add('disabled');
        c.setAttribute('aria-checked', 'false');
    }});
    const selected = document.querySelectorAll('.option-card')[optIdx];
    selected.setAttribute('aria-checked', 'true');
    if (opt.correct) {{
        selected.classList.add('correct-choice');
        score++;
    }} else {{
        selected.classList.add('incorrect-choice');
        node.options.forEach((o, i) => {{
            if (o.correct) document.querySelectorAll('.option-card')[i].classList.add('correct-choice');
        }});
    }}
    const fb = document.getElementById('option-feedback');
    fb.style.display = 'block';
    fb.className = 'feedback-box ' + (opt.correct ? 'feedback-correct' : 'feedback-incorrect');
    fb.innerHTML = opt.feedback;
    history.push({{ nodeIdx, optIdx, correct: opt.correct }});
    document.getElementById('continue-btn').style.display = '';
    document.getElementById('continue-btn').focus();
}}
function advance() {{
    if (currentNode + 1 < NODES.length) {{
        renderNode(currentNode + 1);
    }} else {{
        renderEndpoint();
    }}
}}
function renderEndpoint() {{
    const total = NODES.length;
    const ep = ENDPOINTS.find(e => score >= e.minScore) || ENDPOINTS[ENDPOINTS.length-1];
    const area = document.getElementById('content-area');
    const controls = document.getElementById('controls');
    const bc = document.getElementById('breadcrumb');
    bc.innerHTML = '';
    area.innerHTML = '<div class="endpoint"><h3>' + ep.title + '</h3><div class="score">' + score + '/' + total + '</div><p>' + ep.message + '</p></div>';
    controls.innerHTML = '<button class="btn-primary" onclick="restart()">Try Again</button>';
}}
function restart() {{ score = 0; history = []; renderNode(0); }}
document.addEventListener('keydown', function(e) {{
    if ((e.key === 'Enter' || e.key === ' ') && e.target.getAttribute('role') === 'radio') {{
        e.preventDefault();
        e.target.click();
    }}
}});
renderNode(0);
</script>
</body></html>"""


# ============================================================
# TEMPLATE: QUIZ (QUESTION SET)
# ============================================================
def generate_quiz(data):
    title = html_module.escape(data["title"])
    questions_json = json.dumps(data["questions"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
{SHARED_CSS}
.question-container {{ margin: 20px 0; }}
.stem {{ font-size: 16px; margin-bottom: 15px; line-height: 1.6; }}
.option {{
    border: 2px solid #ddd; border-radius: var(--border-radius);
    padding: 12px 16px; margin: 8px 0; cursor: pointer;
    transition: border-color 0.2s, background 0.2s; min-height: 44px;
    display: flex; align-items: center; gap: 10px;
}}
.option:hover {{ border-color: var(--asu-maroon); background: #fdf6f8; }}
.option:focus-visible {{ outline: 3px solid var(--asu-gold); outline-offset: 2px; }}
.option.selected {{ border-color: var(--asu-maroon); background: #fdf6f8; }}
.option.correct-ans {{ border-color: var(--success); background: #d4edda; }}
.option.incorrect-ans {{ border-color: var(--error); background: #f8d7da; }}
.option.disabled {{ pointer-events: none; opacity: 0.8; }}
.option-marker {{
    width: 24px; height: 24px; border-radius: 50%; border: 2px solid #ccc;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
    font-size: 13px; font-weight: 700; color: var(--text-muted);
}}
.option.selected .option-marker {{ border-color: var(--asu-maroon); color: var(--asu-maroon); }}
.tf-group {{ display: flex; gap: 12px; margin: 10px 0; }}
.tf-btn {{
    flex: 1; padding: 14px; border: 2px solid #ddd; border-radius: var(--border-radius);
    background: var(--white); font-size: 16px; font-weight: 600; cursor: pointer;
    min-height: 44px; transition: border-color 0.2s;
}}
.tf-btn:hover {{ border-color: var(--asu-maroon); }}
.tf-btn:focus-visible {{ outline: 3px solid var(--asu-gold); outline-offset: 2px; }}
.tf-btn.selected {{ border-color: var(--asu-maroon); background: #fdf6f8; }}
.tf-btn.correct-ans {{ border-color: var(--success); background: #d4edda; }}
.tf-btn.incorrect-ans {{ border-color: var(--error); background: #f8d7da; }}
.result-box {{
    text-align: center; padding: 30px; border: 2px solid var(--asu-maroon);
    border-radius: var(--border-radius); margin: 20px 0;
}}
.result-score {{ font-size: 2.5em; color: var(--asu-maroon); font-weight: 700; }}
.nav-dots {{
    display: flex; justify-content: center; gap: 8px; margin: 15px 0;
}}
.nav-dot {{
    width: 24px; height: 24px; min-width: 24px; min-height: 24px; border-radius: 50%; background: #ddd;
    cursor: pointer; transition: background 0.2s;
}}
.nav-dot.active {{ background: var(--asu-maroon); }}
.nav-dot.answered {{ background: var(--asu-gold); }}
.controls {{ display: flex; gap: 12px; justify-content: center; margin: 20px 0; flex-wrap: wrap; }}
</style>
</head>
<body>
<h2>{title}</h2>
<div class="progress-bar" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100" aria-label="Quiz progress" id="progress-bar"><div class="progress-fill" id="progress" style="width:0%"></div></div>
<div class="nav-dots" id="nav-dots" role="tablist" aria-label="Question navigation"></div>
<div class="question-container" id="question-area"></div>
<div class="feedback-box" id="feedback" role="alert"></div>
<div class="controls" id="controls"></div>
<div class="result-box" id="result" style="display:none"></div>
<script>
const QS = {questions_json};
let currentQ = 0;
let answers = new Array(QS.length).fill(null);
let checked = new Array(QS.length).fill(false);
let score = 0;
function initDots() {{
    const dots = document.getElementById('nav-dots');
    dots.innerHTML = '';
    QS.forEach((_, i) => {{
        const d = document.createElement('div');
        d.className = 'nav-dot' + (i === 0 ? ' active' : '');
        d.setAttribute('role', 'tab');
        d.setAttribute('tabindex', '0');
        d.setAttribute('aria-label', 'Question ' + (i+1));
        d.addEventListener('click', () => goTo(i));
        dots.appendChild(d);
    }});
}}
function renderQ(idx) {{
    currentQ = idx;
    const q = QS[idx];
    const area = document.getElementById('question-area');
    const fb = document.getElementById('feedback');
    const controls = document.getElementById('controls');
    fb.style.display = 'none';
    document.getElementById('result').style.display = 'none';
    const pct = Math.round((idx+1)/QS.length*100);
    document.getElementById('progress').style.width = pct+'%';
    document.getElementById('progress-bar').setAttribute('aria-valuenow', pct);
    document.querySelectorAll('.nav-dot').forEach((d,i) => {{
        d.classList.toggle('active', i === idx);
        d.classList.toggle('answered', answers[i] !== null);
    }});
    let html = '<p class="stem"><strong>Question '+(idx+1)+' of '+QS.length+':</strong> '+q.stem+'</p>';
    if (q.type === 'mc') {{
        const labels = ['A','B','C','D','E'];
        html += '<div role="radiogroup" aria-label="Answer options">';
        q.options.forEach((opt, oi) => {{
            let cls = 'option';
            if (checked[idx]) {{
                cls += ' disabled';
                if (opt.correct) cls += ' correct-ans';
                else if (answers[idx] === oi) cls += ' incorrect-ans';
            }} else if (answers[idx] === oi) cls += ' selected';
            html += '<div class="'+cls+'" tabindex="0" role="radio" aria-checked="'+(answers[idx]===oi)+'"'
                + (checked[idx]?'':' onclick="pickMC('+oi+')"')
                + '><span class="option-marker">'+labels[oi]+'</span><span>'+opt.text+'</span></div>';
        }});
        html += '</div>';
    }} else {{
        html += '<div class="tf-group" role="radiogroup" aria-label="True or False">';
        ['True','False'].forEach((lbl, ti) => {{
            let cls = 'tf-btn';
            const val = ti === 0;
            const isChecked = answers[idx] === val;
            if (checked[idx]) {{
                if (val === q.correct) cls += ' correct-ans';
                else if (answers[idx] === val) cls += ' incorrect-ans';
            }} else if (isChecked) cls += ' selected';
            html += '<button class="'+cls+'" role="radio" aria-checked="'+isChecked+'"'+(checked[idx]?'':' onclick="pickTF('+val+')"')+'>'+lbl+'</button>';
        }});
        html += '</div>';
    }}
    area.innerHTML = html;
    if (checked[idx]) {{
        showFeedback(idx);
        controls.innerHTML = idx < QS.length-1 ? '<button class="btn-primary" onclick="goTo('+(idx+1)+')">Next Question</button>' : '<button class="btn-primary" onclick="showResults()">See Results</button>';
    }} else {{
        controls.innerHTML = '<button class="btn-primary" onclick="submitQ()">Submit</button>';
    }}
}}
function pickMC(oi) {{ answers[currentQ] = oi; renderQ(currentQ); }}
function pickTF(val) {{ answers[currentQ] = val; renderQ(currentQ); }}
function submitQ() {{
    if (answers[currentQ] === null) {{
        const fb = document.getElementById('feedback');
        fb.style.display = 'block';
        fb.className = 'feedback-box feedback-incorrect';
        fb.innerHTML = 'Please select an answer before submitting.';
        return;
    }}
    checked[currentQ] = true;
    const q = QS[currentQ];
    let correct;
    if (q.type === 'mc') correct = q.options[answers[currentQ]].correct;
    else correct = answers[currentQ] === q.correct;
    if (correct) score++;
    renderQ(currentQ);
}}
function showFeedback(idx) {{
    const q = QS[idx];
    const fb = document.getElementById('feedback');
    let correct, fbText;
    if (q.type === 'mc') {{
        correct = q.options[answers[idx]].correct;
        fbText = q.options[answers[idx]].feedback;
    }} else {{
        correct = answers[idx] === q.correct;
        fbText = correct ? q.feedback_true : q.feedback_false;
    }}
    fb.style.display = 'block';
    fb.className = 'feedback-box ' + (correct ? 'feedback-correct' : 'feedback-incorrect');
    fb.innerHTML = (correct ? '<strong>Correct!</strong> ' : '<strong>Not quite.</strong> ') + fbText;
}}
function goTo(idx) {{ renderQ(idx); }}
function showResults() {{
    document.getElementById('question-area').innerHTML = '';
    document.getElementById('feedback').style.display = 'none';
    const r = document.getElementById('result');
    r.style.display = 'block';
    r.innerHTML = '<h3>Quiz Complete</h3><div class="result-score">'+score+'/'+QS.length+'</div>'
        + '<p style="color:var(--text-muted);">This is a formative review \u2014 use it to identify areas for further study.</p>';
    document.getElementById('controls').innerHTML = '<button class="btn-primary" onclick="restart()">Try Again</button>';
}}
function restart() {{
    score = 0; answers = new Array(QS.length).fill(null); checked = new Array(QS.length).fill(false);
    initDots(); renderQ(0);
}}
document.addEventListener('keydown', function(e) {{
    if ((e.key === 'Enter' || e.key === ' ') && e.target.getAttribute('role') === 'radio') {{
        e.preventDefault();
        e.target.click();
    }}
}});
initDots(); renderQ(0);
</script>
</body></html>"""


# ============================================================
# TEMPLATE DISPATCH
# ============================================================
GENERATORS = {
    "dialog_cards": generate_dialog_cards,
    "sequencing": generate_sequencing,
    "fill_blanks": generate_fill_blanks,
    "branching": generate_branching,
    "quiz": generate_quiz,
}


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Generate interactive HTML activities for Canvas courses."
    )
    parser.add_argument(
        "content_data",
        help="Path to Python file containing ALL_ACTIVITIES dict",
    )
    parser.add_argument(
        "--output-dir",
        default="./output",
        help="Directory to write HTML files (default: ./output)",
    )
    args = parser.parse_args()
    _track("skill_invoked", context={"skill": "interactive-content"})

    # Import content data from the provided path
    import importlib.util
    spec = importlib.util.spec_from_file_location("content_data", args.content_data)
    content_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(content_module)
    ALL_ACTIVITIES = content_module.ALL_ACTIVITIES

    output_root = os.path.abspath(args.output_dir)
    total = 0
    errors = 0

    for module_key, activities in sorted(ALL_ACTIVITIES.items()):
        module_dir = os.path.join(output_root, module_key)
        os.makedirs(module_dir, exist_ok=True)

        for activity in activities:
            act_type = activity["type"]
            filename = activity["filename"]

            gen_func = GENERATORS.get(act_type)
            if not gen_func:
                _log.error(f"  ERROR: Unknown type '{act_type}' for {filename}")
                errors += 1
                continue

            try:
                html_content = gen_func(activity)
                filepath = os.path.join(module_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(html_content)
                print(f"  OK: {module_key}/{filename} ({act_type})")
                total += 1
            except Exception as e:
                _log.error(f"  ERROR: {module_key}/{filename} — {e}")
                errors += 1

    print(f"\n=== GENERATION COMPLETE ===")
    print(f"  Generated: {total}")
    print(f"  Errors: {errors}")
    print(f"  Output: {output_root}")


if __name__ == "__main__":
    main()
