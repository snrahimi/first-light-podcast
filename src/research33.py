"""Stage 3.3: bounded, primary-document context for source-led daily news.

This does not scrape publisher articles, chase arbitrary discovery links,
or claim independent factual verification. It checks the stated issuing
agency and retains short exact quotations from public agency web pages.
"""
from __future__ import annotations

import logging
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

import requests

if __package__:
    from . import newsroom3
else:
    import newsroom3

LOG = logging.getLogger("firstlight.research33")
MAX_DOCUMENTS = 3
MAX_HTML_BYTES = 850_000
MAX_CONTEXT_CHARS = 1400
AGENCY_URLS = {
    "NASA News Releases": ("nasa.gov", "/news-release/"),
    "United Nations Press Releases": ("press.un.org", "/en/"),
    "U.S. Bureau of Labor Statistics": ("bls.gov", "/news.release/"),
}


class _OfficialParagraphs(HTMLParser):
    """Take visible paragraphs and headings, excluding navigation and code."""

    SKIP = {"script", "style", "nav", "footer", "header", "noscript", "svg"}
    TAKE = {"p", "h1", "h2"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.active = []
        self.buffer = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.SKIP:
            self.skip_depth += 1
        if not self.skip_depth and tag in self.TAKE:
            self.active.append(tag)
            self.buffer.append("")

    def handle_data(self, data):
        if not self.skip_depth and self.active and self.buffer:
            self.buffer[-1] += data

    def handle_endtag(self, tag):
        tag = tag.lower()
        if not self.skip_depth and self.active and tag == self.active[-1]:
            self.active.pop()
            val = newsroom3.clean(self.buffer.pop(), 420)
            if len(val) >= 32 and not val.lower().startswith(
                ("sign up", "subscribe", "read more", "share this", "image:")
            ):
                self.parts.append(val)
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1


def _issuer_matches(url, publisher):
    allow = AGENCY_URLS.get(publisher)
    if not allow or not newsroom3.host_ok(url, (allow[0],)):
        return False
    path = urlsplit(url).path.lower()
    return path.startswith(allow[1])


def get_official_excerpt(url, publisher, get=requests.get):
    """One eligible public NASA/BLS web page, with no redirects or PDFs.

    The source link is already from an agency feed and is rechecked here.
    No third-party publisher body text is read. This is a small excerpt,
    NOT a comprehensive retrieval or independent fact check.
    """
    if not _issuer_matches(url, publisher):
        return None
    try:
        result = get(
            url, timeout=(5, 12), allow_redirects=False,
            headers=newsroom3.USER_AGENT,
        )
        if result.status_code != 200:
            return None
        if not newsroom3.host_ok(getattr(result, "url", url),
                                 (AGENCY_URLS[publisher][0],)):
            return None
        data = result.content
        if len(data) > MAX_HTML_BYTES:
            return None
        content_type = result.headers.get("Content-Type", "text/html").lower()
        if "text/html" not in content_type:
            return None
        parser = _OfficialParagraphs()
        parser.feed(data.decode("utf-8", errors="replace"))
        paragraphs = []
        for item in parser.parts:
            if item not in paragraphs:
                paragraphs.append(item)
        if not paragraphs:
            return None
        # Keep excerpts of *agency* reporting rather than the whole page.
        text = " ".join(paragraphs[:8])[:MAX_CONTEXT_CHARS]
        text = text.rsplit(" ", 1)[0].strip() if len(text) == MAX_CONTEXT_CHARS else text
        if len(text) < 100:
            return None
        spans = [p[:260].strip() for p in paragraphs[:5] if len(p) >= 35]
        return {
            "publisher": publisher,
            "url": url,
            "source_type": "issuing_agency_page",
            "source_text": text,
            "excerpts": [p for p in spans if p in text][:3],
            "status": "attributed_official_document_not_independently_verified",
        }
    except (requests.RequestException, ValueError, TypeError, UnicodeError) as exc:
        LOG.warning("Official context unavailable for %s (%s)",
                    publisher, type(exc).__name__)
        return None


def _reporting_comparison(dossier):
    """Cautiously flag divergent numbers across publisher snippets for review.

    Different figures need not conflict: they may concern different facts.
    Never assert a contradiction or independent factual corroboration.
    """
    by_outlet = {}
    for item in dossier["sources"]:
        text = f"{item.get('title', '')} {item.get('summary', '')}"
        by_outlet.setdefault(item["publisher"], set()).update(
            newsroom3.NUMBER.findall(text)
        )
    distinct = {p: sorted(vals) for p, vals in by_outlet.items() if vals}
    has_variation = (
        len(distinct) > 1 and
        len({tuple(values) for values in distinct.values()}) > 1
    )
    return {
        "publisher_count": len(by_outlet),
        "independent_reporting_established": False,
        "different_numbers_need_review": has_variation,
        "source_numbers_for_review": distinct if has_variation else {},
        "limits": (
            "Outlet independence and underlying factual claims are not "
            "established from feed excerpts."
        ),
    }


def enrich_dossiers(dossiers, get=requests.get):
    """Attach limited official-page contexts, comparators and explicit limits.

    No single failed API may prevent the original RSS-based episode.
    """
    fetched = 0
    for chapter in dossiers.values():
        for dossier in chapter:
            dossier["reporting_comparison"] = _reporting_comparison(dossier)
            dossier["official_context"] = []
            for source in dossier["sources"]:
                if fetched >= MAX_DOCUMENTS:
                    break
                if not source.get("primary"):
                    continue
                if not _issuer_matches(source["url"], source["publisher"]):
                    continue
                fetched += 1
                context = get_official_excerpt(
                    source["url"], source["publisher"], get=get
                )
                if context:
                    dossier["official_context"].append(context)
                    dossier["uncertainties"].append(
                        "The linked issuing-agency page documents its statement "
                        "but is not independent corroboration."
                    )
    return dossiers


def validate_research(dossiers):
    """Check document provenance and exact extraction without pretending truth."""
    validated = 0
    for chapter in dossiers.values():
        for dossier in chapter:
            comparison = dossier.get("reporting_comparison", {})
            if comparison.get("independent_reporting_established") is not False:
                raise ValueError("Research may not assert independently verified reporting")
            for doc in dossier.get("official_context", []):
                if not _issuer_matches(doc["url"], doc["publisher"]):
                    raise ValueError("Official document domain/issuer mismatch")
                if doc["status"] != "attributed_official_document_not_independently_verified":
                    raise ValueError("Official source cannot be labeled independently verified")
                if not any(s["url"] == doc["url"] and
                           s["publisher"] == doc["publisher"] and
                           s["primary"] for s in dossier["sources"]):
                    raise ValueError("Document is not traceable to a selected official feed")
                if not doc["excerpts"] or any(
                    excerpt not in doc["source_text"] or len(excerpt) > 260
                    for excerpt in doc["excerpts"]
                ):
                    raise ValueError("Official context excerpt lacks exact supporting text")
                validated += 1
    return {
        "official_documents_checked": validated,
        "independent_fact_checks": 0,
        "comparison": "publisher-excerpt comparison only; numbers require review",
    }


def enrich_writer_material(dossiers, existing):
    """Pass short exact primary-source excerpts, NEVER full article bodies."""
    for section, chapter in dossiers.items():
        for idx, dossier in enumerate(chapter):
            writer = existing[section][idx]
            writer["official_context"] = [
                {
                    "agency": doc["publisher"], "url": doc["url"],
                    "quoted_excerpt": excerpt,
                    "status": "official_agency_says_not_independently_verified",
                }
                for doc in dossier.get("official_context", [])
                for excerpt in doc["excerpts"]
            ]
            writer["comparison_note"] = (
                "Publisher excerpts contain different numbers; do NOT reconcile "
                "without matching what each figure describes."
                if dossier["reporting_comparison"]["different_numbers_need_review"]
                else "Multiple outlets may share a reporting source."
            )
    return existing


def research_notes(dossiers, stats):
    lines = [
        "PHASE 3.3 OFFICIAL-DOCUMENT CONTEXT",
        f"Linked official pages inspected: {stats['official_documents_checked']}",
        "No independently verified factual claims are implied.",
    ]
    for category, chapter in dossiers.items():
        for dossier in chapter:
            for doc in dossier.get("official_context", []):
                lines.extend([
                    f"{category}: {dossier['headline']}",
                    f"Agency: {doc['publisher']}",
                    f"Original page: {doc['url']}",
                    *[f"Agency excerpt: {quote}" for quote in doc["excerpts"]],
                ])
            if dossier["reporting_comparison"]["different_numbers_need_review"]:
                lines.append(
                    "Review note: differing source numbers require manual "
                    "context checks; no contradiction is automatically inferred."
                )
    return "\n".join(lines)
