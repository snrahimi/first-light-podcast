"""Display-only transcript chapters. Spoken/news text is NEVER rewritten.

Parses trusted, known producer transitions and adds a readable page layout.
For generated prose without recognizable transitions, creates neutral
paragraphs rather than inventing story headings or changing source claims.
"""
from __future__ import annotations

import html
import re

# In spoken order, including both fallback and the two-part Gemini writer.
TRANSITIONS = (
    ("We begin with the leading world developments.", "World Headlines", "world"),
    ("Elsewhere around the world.", "Around the World", "around-world"),
    ("Now, business and markets.", "Business & Markets", "business"),
    ("In science.", "Science", "science"),
    ("And in technology and cybersecurity.", "Technology & Cybersecurity", "technology"),
    ("Now let's turn to business, science and technology.", "Business, Science & Technology", "business-science-tech"),
    ("And now, a look at the weather in San Antonio.", "San Antonio Weather", "weather"),
    ("For developments and corrections, consult", "Closing Notes", "closing"),
    ("That is First Light: World Report.", "Sign-Off", "sign-off"),
    ("That's First Light: World Report.", "Sign-Off", "sign-off"),
)
# Case-insensitive search only after sentence boundaries. All punctuation
# stays in the spoken transcript, in exactly its original order.
TRANSITION_RE = re.compile(
    "|".join(r"(?P<m%d>%s)" % (i, re.escape(text))
             for i, (text, _, _) in enumerate(TRANSITIONS)),
    re.IGNORECASE,
)
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z“\"‘'])")
NEW_REPORT = re.compile(
    r"^(?:(?:The\s+)?[A-Z][\w’'-]+(?:\s+[A-Z][\w’'-]+){0,5}"
    r"\s+(?:reports|says|notes|finds|announces):)"
)
# Each paragraph remains reasonably short, even if the generator supplies
# a very long contiguous news segment without explicit chapter markers.
PARAGRAPH_WORD_TARGET = 72
PARAGRAPH_SENTENCE_LIMIT = 4

TRANSCRIPT_CSS = """
/* Readable, source-faithful topical transcript */
.transcript-intro{color:#c4d4e8;font-size:.98rem;margin:.25rem 0 1.25rem}
.transcript-nav{display:flex;flex-wrap:wrap;gap:.5rem;margin:0 0 1.6rem}
.transcript-nav a{color:#d9e8fa;text-decoration:none;border:1px solid #35465c;
  background:#172b43;border-radius:999px;padding:.35rem .8rem;font-size:.82rem}
.transcript-nav a:hover,.transcript-nav a:focus-visible{border-color:#ffc18b;
  color:#ffc18b;outline-offset:3px}
.transcript-section{border-top:1px solid #35465c;padding:1.4rem 0 .65rem;
  scroll-margin-top:1rem}
.transcript-section h3{font-size:clamp(1.1rem,3vw,1.35rem);line-height:1.35;
  letter-spacing:.012em;margin:0 0 1rem;color:#ffd1a5}
.transcript-section p{margin:.0rem 0 1rem;line-height:1.78;overflow-wrap:break-word}
.transcript-section p:last-child{margin-bottom:.5rem}
.transcript-section:first-of-type{border-top:0}
.transcript-content{max-width:70ch}
@media(max-width:600px){
  body{font-size:16px;margin:20px auto;padding:0 17px}
  .transcript-section{padding:1.2rem 0 .45rem}
  .transcript-nav{gap:.4rem}
  .transcript-nav a{font-size:.78rem;padding:.3rem .64rem}
  .transcript-section p{line-height:1.72}
}
"""


def normalized_script(script):
    """Equivalent to the canonical producer's whitespace normalization."""
    return " ".join(str(script or "").split())


def _paragraphs(text):
    """Break at sentence boundaries, prefer new reports and short blocks."""
    sentences = [part.strip() for part in SENTENCE_BREAK.split(text) if part.strip()]
    output, buffer, words = [], [], 0
    for sentence in sentences:
        count = len(sentence.split())
        # Prefer starting a fresh paragraph for the next attributed story,
        # but keep its supporting sentences in the same block.
        starts_story = bool(NEW_REPORT.match(sentence))
        if buffer and (words + count > PARAGRAPH_WORD_TARGET
                       or len(buffer) >= PARAGRAPH_SENTENCE_LIMIT
                       or (starts_story and words >= 8)):
            output.append(" ".join(buffer))
            buffer, words = [], 0
        buffer.append(sentence)
        words += count
    if buffer:
        output.append(" ".join(buffer))
    return output


def transcript_sections(script):
    """Return heading, anchor and paragraph text, with lossless word order."""
    text = normalized_script(script)
    if not text:
        return []
    breaks = []
    for match in TRANSITION_RE.finditer(text):
        index = match.start()
        # Ignore a chapter keyword inside a quotation or another sentence.
        if index > 0:
            previous = text[:index].rstrip()
            if not previous or previous[-1] not in ".!?":
                continue
        which = next(i for i in range(len(TRANSITIONS))
                     if match.group("m%d" % i) is not None)
        if breaks and index < breaks[-1][0] + len(breaks[-1][3]):
            continue
        title, slug = TRANSITIONS[which][1:3]
        breaks.append((index, title, slug, match.group(0)))
    chunks = []
    if breaks:
        if breaks[0][0]:
            chunks.append(("Introduction", "introduction", text[:breaks[0][0]].strip()))
        for n, (start, title, slug, _) in enumerate(breaks):
            end = breaks[n + 1][0] if n + 1 < len(breaks) else len(text)
            # A second sign-off marker after Closing Notes should remain
            # under the same closing chapter instead of a tiny last block.
            if slug == "sign-off" and chunks and chunks[-1][1] == "closing":
                prev_title, prev_slug, prev_text = chunks.pop()
                chunks.append((prev_title, prev_slug, prev_text + " " + text[start:end].strip()))
            else:
                chunks.append((title, slug, text[start:end].strip()))
    else:
        chunks.append(("Full Briefing", "briefing", text))
    # IDs must stay unique if a section phrase appears more than once.
    counts, out = {}, []
    for title, slug, passage in chunks:
        if not passage:
            continue
        counts[slug] = counts.get(slug, 0) + 1
        slug_id = slug if counts[slug] == 1 else f"{slug}-{counts[slug]}"
        out.append({
            "heading": title,
            "id": "transcript-" + slug_id,
            "paragraphs": _paragraphs(passage),
        })
    return out


def render_transcript(script):
    """Accessible in-page navigation, headings, and escaped paragraphs."""
    sections = transcript_sections(script)
    if not sections:
        return '<p class="transcript-intro">Transcript unavailable.</p>'
    navigation = (
        '<nav class="transcript-nav" aria-label="Transcript topics">'
        + "".join(
            '<a href="#' + section["id"] + '">' +
            html.escape(section["heading"]) + "</a>"
            for section in sections
        )
        + "</nav>"
    )
    body = "".join(
        '<section class="transcript-section" id="' + section["id"] + '">'
        '<h3>' + html.escape(section["heading"]) + '</h3>'
        '<div class="transcript-content">'
        + "".join('<p>' + html.escape(paragraph) + '</p>'
                  for paragraph in section["paragraphs"])
        + "</div></section>"
        for section in sections
    )
    return navigation + '<div class="transcript-chapters">' + body + "</div>"


# The current published site was created by an older web_page() that has
# a single transcript <p>. This adapter allows a presentation-only update
# without generating new speech or changing the original transcript asset.
LEGACY_TRANSCRIPT = re.compile(
    r'<h2>Transcript</h2>\s*<p>(?P<script>.*?)</p>(?=\s*<footer>)',
    re.DOTALL,
)


def reformat_existing_page(page_html):
    """Upgrade the existing published HTML, preserving every other element.

    Refuse ambiguous/unknown layouts rather than overwriting the site with
    incomplete data. An already-formatted page is safe to replay unchanged.
    """
    if ('<h2 id="transcript">Transcript</h2>' in page_html
            and 'class="transcript-chapters"' in page_html):
        return page_html
    matches = list(LEGACY_TRANSCRIPT.finditer(page_html))
    if len(matches) != 1 or page_html.count("</style>") != 1:
        raise ValueError("Existing published transcript structure not recognized")
    raw = html.unescape(matches[0].group("script"))
    replacement = (
        '<h2 id="transcript">Transcript</h2>\n'
        + render_transcript(raw)
    )
    changed = page_html[:matches[0].start()] + replacement + page_html[matches[0].end():]
    return changed.replace("</style>", TRANSCRIPT_CSS + "</style>", 1)
