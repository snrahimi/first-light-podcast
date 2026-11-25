"""HTML presentation and editorial-fallback regression tests, no web or TTS."""
import html
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

from src import transcript_display
from src.first_light import (
    _complete_fallback_excerpt,
    fallback_readout,
    web_page,
)
from src import broadcast32


EXAMPLE = (
    "Good morning, San Antonio. It's Wednesday. This is First Light: World "
    "Report. We begin with the leading world developments. "
    "According to one publisher, the first update is developing. "
    "A second publication describes another development. "
    "Elsewhere around the world. A report from another region follows. "
    "Now, business and markets. Two central banks released statements. "
    "In science. Researchers announced a new finding. "
    "And in technology and cybersecurity. A government issued an alert. "
    "And now, a look at the weather in San Antonio. "
    "The forecast high is near 59 degrees. "
    "For developments and corrections, consult the linked original reporting. "
    "That is First Light: World Report. Thanks for listening."
)


class ParagraphText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_paragraph = False
        self.paragraphs = []
    def handle_starttag(self, tag, attrs):
        if tag == "p":
            self.in_paragraph = True
            self.paragraphs.append("")
    def handle_endtag(self, tag):
        if tag == "p":
            self.in_paragraph = False
    def handle_data(self, data):
        if self.in_paragraph:
            self.paragraphs[-1] += data


class TranscriptLayoutTests(unittest.TestCase):
    def test_fallback_topics_split_into_readable_linked_sections(self):
        blocks = transcript_display.transcript_sections(EXAMPLE)
        labels = [b["heading"] for b in blocks]
        self.assertEqual(labels, [
            "Introduction",
            "World Headlines",
            "Around the World",
            "Business & Markets",
            "Science",
            "Technology & Cybersecurity",
            "San Antonio Weather",
            "Closing Notes",
        ])
        markup = transcript_display.render_transcript(EXAMPLE)
        self.assertEqual(markup.count('<section class="transcript-section"'), 8)
        self.assertIn('href="#transcript-weather"', markup)
        self.assertIn('id="transcript-business"', markup)
        self.assertIn('aria-label="Transcript topics"', markup)

    def test_no_word_or_punctuation_is_added_removed_by_layout(self):
        blocks = transcript_display.transcript_sections(EXAMPLE)
        output = " ".join(
            p for part in blocks for p in part["paragraphs"]
        )
        self.assertEqual(output, transcript_display.normalized_script(EXAMPLE))

    def test_no_known_markers_still_creates_readable_paragraphs(self):
        unstructured = ("A publisher says the investigation has begun. "
                        "Authorities have not given a timetable. "
                        "No outcome is confirmed. " * 8)
        blocks = transcript_display.transcript_sections(unstructured)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["heading"], "Full Briefing")
        self.assertGreaterEqual(len(blocks[0]["paragraphs"]), 3)
        self.assertEqual(
            " ".join(blocks[0]["paragraphs"]),
            transcript_display.normalized_script(unstructured),
        )

    def test_web_page_html_escapes_untrusted_news_words(self):
        evil = (
            'Good morning, San Antonio. '
            'We begin with the leading world developments. '
            'An outlet says <img src=x onerror="alert(1)"> & some news.'
        )
        page = web_page("2026-11-25", [], evil)
        self.assertNotIn('<img src=x onerror=', page)
        self.assertIn("&lt;img src=x onerror=", page)
        self.assertIn("some news", page)
        self.assertIn('<h2 id="transcript">Transcript</h2>', page)
        self.assertIn("transcript-section", page)
        self.assertIn("@media(max-width:600px)", page)

    def test_synthetic_news_words_cannot_inject_nav_or_header(self):
        evil = "Today, <script>throw Error('oops')</script> in one source."
        markup = transcript_display.render_transcript(evil)
        self.assertNotIn("<script>", markup)
        self.assertIn("&lt;script&gt;", markup)

    def test_story_paragraphs_prefer_reporter_boundaries(self):
        text = (
            "Now, business and markets. Several central banks shared figures. "
            "Further details remain unconfirmed. "
            "BBC Business reports: A separate economic update is underway. "
            "The published figures have not yet been independently checked."
        )
        blocks = transcript_display.transcript_sections(text)
        self.assertEqual(blocks[0]["heading"], "Business & Markets")
        self.assertGreaterEqual(len(blocks[0]["paragraphs"]), 2)

    def test_generated_writer_mixed_beats_and_weather_grouped(self):
        mixed = (
            "Good morning, San Antonio. This is First Light: World Report. "
            "A sourced international report follows. "
            "Now let's turn to business, science and technology. "
            "A business report follows. A technology update follows. "
            "And now, a look at the weather in San Antonio. "
            "Conditions are partly cloudy. That's First Light: World Report."
        )
        sections = transcript_display.transcript_sections(mixed)
        self.assertEqual([s["heading"] for s in sections], [
            "Introduction", "Business, Science & Technology",
            "San Antonio Weather", "Sign-Off",
        ])
        self.assertEqual(
            " ".join(p for s in sections for p in s["paragraphs"]),
            transcript_display.normalized_script(mixed),
        )

    def test_existing_site_refresh_is_idempotent_and_keeps_audio_metadata(self):
        old = (
            '<!doctype html><html lang="en"><head><style>body{color:#fff}'
            '</style></head><body>'
            '<audio src="latest.mp3?date=2026-11-25"></audio>'
            '<a href="feed.xml">RSS</a>'
            '<h2>Transcript</h2><p>'
            + html.escape(EXAMPLE) +
            '</p><footer>Original footer</footer></body></html>'
        )
        modified = transcript_display.reformat_existing_page(old)
        self.assertEqual(
            transcript_display.reformat_existing_page(modified), modified
        )
        self.assertIn('src="latest.mp3?date=2026-11-25"', modified)
        self.assertIn('href="feed.xml"', modified)
        self.assertIn("Original footer", modified)
        self.assertIn("transcript-weather", modified)
        self.assertNotIn("<h2>Transcript</h2><p>", modified)

    def test_ambiguous_old_site_refused(self):
        with self.assertRaisesRegex(ValueError, "not recognized"):
            transcript_display.reformat_existing_page("<html>unsupported</html>")

    def test_fallback_excludes_truncated_rss_excerpts(self):
        clipped = ("The report describes a daylong siege that followed "
                   "an earlier security response, and then police began a")
        self.assertEqual(_complete_fallback_excerpt(clipped), "")
        valid = (
            "An official statement confirms that the committee reviewed "
            "the application. Further details are expected next week, "
            "according to the announcement, which then became inco"
        )
        self.assertEqual(
            _complete_fallback_excerpt(valid),
            "An official statement confirms that the committee reviewed "
            "the application."
        )

    def test_fallback_no_fragment_read_aloud(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        fake = {
            "rundown": {
                "Top world headlines": [{
                    "publisher": "Example Journal",
                    "title": "Authorities completed a safety inspection",
                    "short_summary": (
                        "The summary says the work is completed, but "
                        "more people are waiting for a"
                    ),
                    "coverage_status": "new",
                }],
            }
        }
        weather = {
            "source": "unavailable",
            "nws_alert_check": "not verified",
        }
        readout = fallback_readout(
            datetime(2026, 11, 25, tzinfo=ZoneInfo("America/Chicago")),
            fake, weather,
        )
        self.assertIn("Example Journal reports:", readout)
        self.assertNotIn("waiting for a", readout)
        self.assertNotIn("In its summary", readout)
        self.assertIn("That is First Light: World Report.", readout)

    def test_editorial_prompt_is_original_single_anchor_source_led(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        material = {
            "Top world headlines": [{
                "headline": "Safety officials issued a notice",
                "evidence": [{"publisher": "Example", "text": (
                    "An agency statement says the notice went out"
                )}]
            }]
        }
        prompt = broadcast32._prompt(
            datetime(2026, 11, 25, tzinfo=ZoneInfo("America/Chicago")),
            "world", material, 300
        )
        for phrase in (
            "complete STORIES", "fictional", "never paraphrase",
            "supported", "what remains unknown"
        ):
            self.assertIn(phrase.lower(), prompt.lower())
        self.assertNotIn("MICHEL MARTIN", prompt)
        self.assertNotIn("UP FIRST", prompt)


if __name__ == "__main__":
    unittest.main()
