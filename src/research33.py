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
    from . import newsroom3, editorial
else:
    import newsroom3
    import editorial

LOG = logging.getLogger("firstlight.research33")
MAX_DOCUMENTS = 4
MAX_HTML_BYTES = 850_000
MAX_CONTEXT_CHARS = 1900
MAX_OFFICIAL_EXCERPTS = 4
AGENCY_URLS = {
    "NASA News Releases": ("nasa.gov", "/news-release/"),
    "United Nations Press Releases": ("press.un.org", "/en/"),
    "U.S. Bureau of Labor Statistics": ("bls.gov", "/news.release/"),
}


class _OfficialParagraphs(HTMLParser):
    """Take visible paragraphs and headings, excluding navigation and code."""

    SKIP = {"script", "style", "nav", "footer", "header", "noscript", "svg"}
    TAKE = {"p", "h1", "h2", "h3", "li"}

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


def get_official_excerpt(url, publisher, get=requests.get, headline=None):
    """One eligible public agency web page, with no redirects or PDFs.

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
            LOG.info("Agency context fetch returned HTTP %s for %s",
                     result.status_code, publisher)
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
            LOG.info("Agency context page had no extractable paragraphs: %s",
                     publisher)
            return None
        if headline:
            # Prefer the headline-matching heading/paragraph, then allow a
            # tightly bounded adjacent follow-up which retains at least one
            # substantive subject token. This captures agency next-steps
            # without importing other unrelated releases from listing pages.
            tokens = editorial.key_tokens(headline)
            # An agency name alone is not continuity. Otherwise a paragraph
            # about an unrelated issue involving the same issuer can leak
            # into the briefing after a valid headline anchor.
            subject_tokens = tokens - {
                "nasa", "united", "nations", "security", "council",
                "bureau", "labor", "statistics", "agency", "government",
                "official", "report", "reports", "announces", "press",
            }
            selected, anchored = [], False
            for paragraph in paragraphs[:40]:
                overlap = len(tokens & editorial.key_tokens(paragraph))
                if overlap >= 2:
                    selected.append(paragraph)
                    anchored = True
                elif (anchored and len(selected) < 8
                      and subject_tokens & editorial.key_tokens(paragraph)):
                    selected.append(paragraph)
                elif anchored:
                    # Stop at the first unrelated paragraph instead of
                    # reaching into other story blocks on shared pages.
                    break
                if len(selected) >= 8:
                    break
            paragraphs = selected
            if not paragraphs:
                LOG.info("Official document has no headline-matched excerpts: %s",
                         publisher)
                return None
        # Short, exact fragments from an issuing agency, not a full article.
        # Remove repeated headlines and near-identical paragraphs so the
        # writer has multiple genuinely distinct statements when available.
        unique = []
        for paragraph in paragraphs:
            reduced = paragraph.lower()
            if any(reduced in prev.lower() or prev.lower() in reduced
                   for prev in unique):
                continue
            unique.append(paragraph)
        text = " ".join(unique[:8])[:MAX_CONTEXT_CHARS]
        if len(text) == MAX_CONTEXT_CHARS:
            text = text.rsplit(" ", 1)[0].strip()
        if len(text) < 100:
            return None
        spans = [p[:245].strip() for p in unique[:8] if len(p) >= 35]
        excerpts = [p for p in spans if p in text][:MAX_OFFICIAL_EXCERPTS]
        if not excerpts:
            return None
        return {
            "publisher": publisher,
            "url": url,
            "source_type": "issuing_agency_page",
            "source_text": text,
            "excerpts": excerpts,
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


# Only previously validated source-feed hostnames may contribute enrichment.
# This does not fetch article pages, and source similarity is not corroboration.
PUBLISHER_FEED_HOSTS = {
    "BBC": ("bbc.co.uk", "bbc.com"),
    "NPR": ("npr.org",),
    "Guardian": ("theguardian.com",),
    "The Guardian": ("theguardian.com",),
    "Al Jazeera": ("aljazeera.com",),
}
MAX_RELATED_LEADS = 3
MAX_RELATED_OTHER = 2


def _trusted_feed_candidate(entry):
    publisher = str(entry.get("publisher", ""))
    url = str(entry.get("url", ""))
    if entry.get("provenance", "").startswith("primary_"):
        return _issuer_matches(url, publisher)
    for prefix, hosts in PUBLISHER_FEED_HOSTS.items():
        if publisher.startswith(prefix):
            return newsroom3.host_ok(url, hosts)
    return False


def _topic_match_score(headline, candidate_title, candidate_summary=""):
    """Conservative same-event signal; not factual corroboration.

    High overlap is accepted. A second path handles shorter paraphrased
    headlines only when a concrete event word and another subject token
    overlap, plus supporting summary overlap. A country alone is never
    sufficient to link different events.
    """
    lead = editorial.key_tokens(headline)
    subject = editorial.key_tokens(candidate_title)
    overlap = lead & subject
    base = editorial.story_similarity(headline, candidate_title)
    if len(overlap) >= 4 and base >= 0.65:
        return base
    event_overlap = overlap & editorial.IMPACT_WORDS
    summary_tokens = editorial.key_tokens(candidate_summary) if candidate_summary else set()
    shared_context = lead & summary_tokens
    fraction = len(overlap) / max(1, min(len(lead), len(subject)))
    if (len(overlap) >= 2 and event_overlap and fraction >= 0.35
            and len(overlap | shared_context) >= 3
            and (shared_context or len(overlap) >= 3)):
        return min(0.85, 0.35 + 0.12 * len(overlap) + 0.05 * len(shared_context))
    return 0.0


def link_selected_feed_context(dossiers, groups):
    """Enrich SELECTED stories with short, directly linked feed statements.

    Only high-overlap, same-category headlines from already curated, trusted
    publisher/agency feeds may be attached. No third-party article scraping,
    invented synthesis or independent verification. Prioritize the two
    world leads. Every appended claim passes the existing exact-source gate.
    """
    attached = 0
    for section, chapter in dossiers.items():
        category = {
            "Top world headlines": "world",
            "Around the world": "world",
            "Business and markets": "business",
            "Science": "science",
            "Technology and cybersecurity": "tech",
        }.get(section)
        cap = MAX_RELATED_LEADS if section == "Top world headlines" else MAX_RELATED_OTHER
        options = groups.get(category, []) if category else []
        for dossier in chapter:
            dossier["linked_feed_context_count"] = 0
            known = {src["url"] for src in dossier["sources"]}
            existing_publishers = {src["publisher"] for src in dossier["sources"]}
            matching = []
            for candidate in options:
                title = str(candidate.get("title", ""))
                url = str(candidate.get("url", ""))
                if not title or not url or url in known:
                    continue
                if not _trusted_feed_candidate(candidate):
                    continue
                score = _topic_match_score(
                    dossier["headline"], title, candidate.get("summary", "")
                )
                # A shared country or organization is not proof of the same
                # event. Match must include enough concrete event context.
                if score <= 0:
                    continue
                matching.append((score, candidate))
            matching.sort(
                key=lambda hit: (
                    hit[1]["publisher"] in existing_publishers,
                    -hit[0],
                    hit[1].get("age", 999),
                )
            )
            for _, source in matching:
                if dossier["linked_feed_context_count"] >= cap:
                    break
                url = source["url"]
                if url in known:
                    continue
                publisher = source["publisher"]
                is_primary = source.get("provenance", "").startswith("primary_")
                item = {
                    "publisher": publisher,
                    "url": url,
                    "title": source["title"],
                    "summary": source.get("summary", ""),
                    "published": source.get("published"),
                    "primary": is_primary,
                }
                # Attributed feed excerpts only, never long article content.
                claims = []
                for field in ("title", "summary"):
                    excerpt = newsroom3.clean(item[field], 240)
                    if len(excerpt) < 12 or any(
                        claim["evidence"] == excerpt for claim in claims
                    ):
                        continue
                    claims.append({
                        "id": f"extra_{len(dossier['sources']) + 1}_{field}",
                        "claim": excerpt,
                        "evidence": excerpt,
                        "evidence_field": field,
                        "source_url": url,
                        "publisher": publisher,
                        "published": item["published"],
                        "evidence_status": (
                            "primary_statement" if is_primary
                            else "attributed_publisher_report"
                        ),
                        "independently_verified": False,
                    })
                if not claims:
                    continue
                dossier["sources"].append(item)
                dossier["claim_ledger"].extend(claims)
                known.add(url)
                existing_publishers.add(publisher)
                dossier["linked_feed_context_count"] += 1
                attached += 1
            if dossier["linked_feed_context_count"]:
                dossier["uncertainties"].append(
                    "These related publisher feed excerpts provide additional "
                    "attributed reporting, not independent corroboration."
                )
    LOG.info("Phase 3.3 selected-story context linked %d RSS/agency reports",
             attached)
    return attached


def enrich_dossiers(dossiers, get=requests.get):
    """Attach limited official-page contexts, comparators and explicit limits.

    No single failed API may prevent the original RSS-based episode.
    """
    fetched = 0
    for chapter in dossiers.values():
        for dossier in chapter:
            dossier["reporting_comparison"] = _reporting_comparison(dossier)
            dossier["official_context"] = []
            dossier["official_page_fetches_attempted"] = 0
            for source in dossier["sources"]:
                if fetched >= MAX_DOCUMENTS:
                    break
                if not source.get("primary"):
                    continue
                if not _issuer_matches(source["url"], source["publisher"]):
                    continue
                fetched += 1
                dossier["official_page_fetches_attempted"] += 1
                context = get_official_excerpt(
                    source["url"], source["publisher"], get=get,
                    headline=source["title"],
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
    attempts = sum(
        card.get("official_page_fetches_attempted", 0)
        for chapter in dossiers.values() for card in chapter
    )
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
    related = sum(
        card.get("linked_feed_context_count", 0)
        for chapter in dossiers.values() for card in chapter
    )
    return {
        "official_documents_checked": validated,
        "official_document_fetches_attempted": attempts,
        "official_distinct_excerpts": sum(
            len(doc["excerpts"]) for chapter in dossiers.values()
            for card in chapter for doc in card.get("official_context", [])
        ),
        "selected_story_related_feeds": related,
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
        f"Relevant source-feed reports added to chosen stories: "
        f"{stats['selected_story_related_feeds']}",
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
