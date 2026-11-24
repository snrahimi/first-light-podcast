"""Offline tests for bounded official-document research and provenance."""
import unittest
from types import SimpleNamespace

from src import research33, newsroom3


def nasa_dossier():
    url = "https://www.nasa.gov/news-release/example-announcement/"
    return {
        "headline": "NASA announces an instrument test",
        "uncertainties": [],
        "sources": [{
            "publisher": "NASA News Releases",
            "url": url,
            "primary": True,
            "title": "NASA announces an instrument test",
            "summary": "The agency describes a test of an instrument.",
        }],
        "claim_ledger": [{
            "claim": "NASA announces an instrument test",
            "evidence": "NASA announces an instrument test",
            "publisher": "NASA News Releases",
            "source_url": url,
        }],
    }


def html_response(url, body, status=200, kind="text/html"):
    return SimpleNamespace(
        status_code=status, url=url,
        headers={"Content-Type": kind},
        content=body.encode("utf-8"),
    )


DOCUMENT = """<html><head><title>News</title>
<style>.junk{color:red}</style></head><body>
<nav><p>Important unrelated fake headline</p></nav>
<main>
<h1>NASA shares results from a spacecraft instrument test</h1>
<p>NASA engineers completed an instrument trial at a research facility.
The release describes measured temperatures and the next planned evaluation
of the component before flight testing.</p>
<p>The agency says the new test results will inform the next design review,
and that no flight date has yet been announced by the program.</p>
</main>
<footer><p>Subscribe to a newsletter</p></footer></body></html>"""


class PrimaryResearchTests(unittest.TestCase):
    def test_bounded_agency_page_extract_and_provenance(self):
        item = nasa_dossier()
        dossier = {"Science": [item]}
        calls = []
        def fake_get(url, **kw):
            calls.append((url, kw))
            return html_response(url, DOCUMENT)
        research33.enrich_dossiers(dossier, get=fake_get)
        stats = research33.validate_research(dossier)
        self.assertEqual(stats["official_documents_checked"], 1)
        self.assertEqual(stats["independent_fact_checks"], 0)
        self.assertFalse(calls[0][1]["allow_redirects"])
        doc = item["official_context"][0]
        self.assertIn("NASA engineers completed", doc["source_text"])
        self.assertNotIn("Important unrelated fake headline", doc["source_text"])
        self.assertLessEqual(len(doc["source_text"]), research33.MAX_CONTEXT_CHARS)
        self.assertTrue(all(x in doc["source_text"] for x in doc["excerpts"]))

    def test_official_document_not_found_does_not_break_rundown(self):
        item = nasa_dossier()
        d = {"Science": [item]}
        research33.enrich_dossiers(d, get=lambda url, **kw:
                                   html_response(url, "Not available", 404))
        self.assertEqual(research33.validate_research(d)["official_documents_checked"], 0)
        self.assertEqual(item["official_context"], [])

    def test_reject_redirect_and_wrong_issuer(self):
        item = nasa_dossier()
        bad = "https://nasa.gov.attacker.example/news-release/no"
        self.assertIsNone(research33.get_official_excerpt(
            bad, "NASA News Releases", get=lambda *args, **kw:
            self.fail("No fetch should occur for a fake NASA host")))
        self.assertIsNone(research33.get_official_excerpt(
            item["sources"][0]["url"], "NASA News Releases",
            get=lambda url, **kw: html_response(
                "https://evil.example/redirected", DOCUMENT)))
        self.assertIsNone(research33.get_official_excerpt(
            item["sources"][0]["url"], "NASA News Releases",
            get=lambda url, **kw: html_response(url, DOCUMENT, 301)))

    def test_reject_pdf_and_oversized_html(self):
        url = nasa_dossier()["sources"][0]["url"]
        self.assertIsNone(research33.get_official_excerpt(
            url, "NASA News Releases",
            get=lambda u, **kw: html_response(u, DOCUMENT, kind="application/pdf")))
        self.assertIsNone(research33.get_official_excerpt(
            url, "NASA News Releases",
            get=lambda u, **kw: html_response(u, "A" * 900_000)))

    def test_exact_source_and_agency_identity_required(self):
        dossier = {"Science": [nasa_dossier()]}
        research33.enrich_dossiers(
            dossier, get=lambda url, **kw: html_response(url, DOCUMENT))
        dossier["Science"][0]["official_context"][0]["excerpts"][0] = (
            "Invented finding unsupported by the agency"
        )
        with self.assertRaisesRegex(ValueError, "exact supporting text"):
            research33.validate_research(dossier)

    def test_different_numbers_are_flags_not_proven_contradictions(self):
        item = nasa_dossier()
        item["sources"].append({
            "publisher": "Outlet B",
            "url": "https://example.org/news",
            "title": "Researchers discuss 31 instruments",
            "summary": "",
            "primary": False,
        })
        item["sources"][0]["title"] = "NASA reports 12 instruments"
        research33.enrich_dossiers({"Science": [item]},
                                   get=lambda url, **kw: html_response(url, DOCUMENT))
        x = item["reporting_comparison"]
        self.assertTrue(x["different_numbers_need_review"])
        self.assertFalse(x["independent_reporting_established"])
        self.assertIn("31", x["source_numbers_for_review"]["Outlet B"])

    def test_writer_uses_short_official_excerpts_not_full_document(self):
        item = nasa_dossier()
        d = {"Science": [item]}
        research33.enrich_dossiers(d, get=lambda url, **kw:
                                   html_response(url, DOCUMENT))
        material = {"Science": [{"headline": item["headline"], "evidence": []}]}
        out = research33.enrich_writer_material(d, material)
        self.assertTrue(out["Science"][0]["official_context"])
        self.assertNotIn("source_text", str(out))
        self.assertIn("not_independently_verified", str(out))

    def test_un_press_release_issuer_restricted(self):
        url = "https://press.un.org/en/2026/sgsm-example.doc.htm"
        self.assertTrue(research33._issuer_matches(
            url, "United Nations Press Releases"))
        self.assertFalse(research33._issuer_matches(
            "https://press.un.org.attacker.example/en/2026/report",
            "United Nations Press Releases"))
        self.assertFalse(research33._issuer_matches(
            "https://press.un.org/not-news/report",
            "United Nations Press Releases"))

    def test_only_three_official_retrievals_per_edition(self):
        d = {"Science": [nasa_dossier() for _ in range(8)]}
        calls = []
        def fake_get(url, **kw):
            calls.append(url)
            return html_response(url, DOCUMENT)
        research33.enrich_dossiers(d, get=fake_get)
        self.assertEqual(len(calls), 3)


if __name__ == "__main__":
    unittest.main()
