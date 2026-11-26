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
    from . import newsroom3, editorial, research35
else:
    import newsroom3
    import editorial
    import research35

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


def _complete_official_sentences(paragraphs):
    """Use only intact agency sentences, not chopped fragments or headlines.

    Paragraphs were already filtered to the selected release. This is a
    presentation/evidence-quality filter, not additional site scraping.
    """
    result = []
    for paragraph in paragraphs:
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'])", paragraph):
            sentence = sentence.strip()
            if (sentence.endswith((".", "!", "?"))
                    and 45 <= len(sentence) <= 255
                    and len(sentence.split()) >= 8
                    and sentence not in result):
                result.append(sentence)
    return result


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
        # Never cut an official sentence mid-thought. Select the first
        # complete, distinct statements from this article only.
        sentences = _complete_official_sentences(unique[:8])
        kept = []
        for sentence in sentences:
            if len(" ".join(kept + [sentence])) > MAX_CONTEXT_CHARS:
                break
            kept.append(sentence)
        text = " ".join(kept)
        if len(text) < 100:
            return None
        excerpts = kept[:MAX_OFFICIAL_EXCERPTS]
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
    "Deutsche Welle": ("dw.com",),
    "France 24": ("france24.com",),
    "ABC Australia": ("abc.net.au",),
    "PBS News": ("pbs.org",),
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
    """Bounded same-event candidate score, never independent verification."""
    return research35.match_score(headline, candidate_title, candidate_summary)


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
            dossier["event_link35_review"] = {
                "trusted_candidates_examined": 0,
                "same_event_candidates": 0,
                "added_source_reports": 0,
                "method": "event + two distinct subject anchors; no truth check",
            }
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
                dossier["event_link35_review"]["trusted_candidates_examined"] += 1
                score = _topic_match_score(
                    dossier["headline"], title, candidate.get("summary", "")
                )
                # A shared country or organization is not proof of the same
                # event. Match must include enough concrete event context.
                if score <= 0:
                    continue
                dossier["event_link35_review"]["same_event_candidates"] += 1
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
                dossier["event_link35_review"]["added_source_reports"] += 1
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
    for section, chapter in dossiers.items():
        for dossier in chapter:
            dossier["reporting_comparison"] = _reporting_comparison(dossier)
            dossier["official_context"] = []
            dossier["official_page_fetches_attempted"] = 0
            eligible = [
                src for src in dossier["sources"]
                if src.get("primary") and
                _issuer_matches(src["url"], src["publisher"])
            ]
            # Allocate scarce retrieval slots across leads before briefs,
            # rather than allowing one heavily linked story to use all 4.
            per_story_cap = 2 if section == "Top world headlines" else 1
            dossier["official_retrieval35"] = {
                "eligible_issuer_links": len(eligible),
                "attempted": 0,
                "documents_with_complete_excerpts": 0,
                "skipped_due_to_global_or_story_cap": 0,
                "rejected_or_unavailable": 0,
            }
            for idx, source in enumerate(eligible):
                if fetched >= MAX_DOCUMENTS or idx >= per_story_cap:
                    dossier["official_retrieval35"]["skipped_due_to_global_or_story_cap"] += 1
                    continue
                fetched += 1
                dossier["official_page_fetches_attempted"] += 1
                dossier["official_retrieval35"]["attempted"] += 1
                context = get_official_excerpt(
                    source["url"], source["publisher"], get=get,
                    headline=source["title"],
                )
                if context:
                    dossier["official_context"].append(context)
                    dossier["official_retrieval35"]["documents_with_complete_excerpts"] += 1
                    dossier["uncertainties"].append(
                        "The linked issuing-agency page documents its statement "
                        "but is not independent corroboration."
                    )
                else:
                    dossier["official_retrieval35"]["rejected_or_unavailable"] += 1
    return dossiers



# More complete RSS descriptions are collected ONLY from already trusted
# publisher feeds. This step uses no article pages, new network calls or
# source metadata not already in the exact evidence ledger.
MAX_LEAD_DETAIL_PER_STORY = 4
MAX_LEAD_DETAIL_PER_PUBLISHER = 2
MAX_LEAD_DETAIL_SENTENCE = 340
MAX_LEAD_DETAIL_TOTAL = 980


def _complete_rss_sentences(summary):
    """Bounded, complete publisher-supplied RSS sentences; no clipped tails."""
    text = newsroom3.clean(summary, 900)
    if not text:
        return []
    # We accept only sentence-final punctuation, never silently complete
    # truncated feed text or paraphrase third-party prose as a new source.
    chunks = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'])", text)
    return [
        part.strip() for part in chunks
        if part.strip().endswith((".", "!", "?"))
        and 10 <= len(part.split()) <= 65
        and len(part) <= MAX_LEAD_DETAIL_SENTENCE
        and len(part) >= 65
    ]


def enrich_lead_feed_context(dossiers):
    """Add complete, traceable *extra* RSS sentences for two world leads.

    This does not retrieve publisher article bodies, claim corroboration,
    or authorize invented background. Extra sentences must exist exactly
    in an already attached publisher/official RSS source description.
    """
    for section, chapter in dossiers.items():
        for dossier in chapter:
            dossier["lead_feed_context"] = []
            if section != "Top world headlines":
                continue
            already = [str(c.get("evidence") or "").lower()
                       for c in dossier.get("claim_ledger", [])]
            used = set()
            by_publisher = {}
            total = 0
            for source in dossier["sources"]:
                if len(dossier["lead_feed_context"]) >= MAX_LEAD_DETAIL_PER_STORY:
                    break
                publisher = str(source.get("publisher", ""))
                if by_publisher.get(publisher, 0) >= MAX_LEAD_DETAIL_PER_PUBLISHER:
                    continue
                if not _trusted_feed_candidate({
                    "publisher": publisher,
                    "url": source["url"],
                    "provenance": ("primary_official_catalog"
                                   if source.get("primary") else "publisher_rss"),
                }):
                    continue
                for sentence in _complete_rss_sentences(source.get("summary")):
                    if (len(dossier["lead_feed_context"]) >= MAX_LEAD_DETAIL_PER_STORY
                            or by_publisher.get(publisher, 0) >= MAX_LEAD_DETAIL_PER_PUBLISHER
                            or total + len(sentence) > MAX_LEAD_DETAIL_TOTAL):
                        break
                    low = sentence.casefold()
                    if low in used or any(low in excerpt for excerpt in already):
                        continue
                    # Compare only genuine substantive content, not whether
                    # source spelling resembles the selected headline.
                    significant = editorial.key_tokens(sentence)
                    if significant and any(
                        len(significant & editorial.key_tokens(prev)) /
                        max(1, len(significant | editorial.key_tokens(prev))) > .84
                        for prev in used
                    ):
                        continue
                    dossier["lead_feed_context"].append({
                        "publisher": publisher,
                        "url": source["url"],
                        "exact_excerpt": sentence,
                        "source_type": "trusted_rss_description",
                        "status": "publisher_report_not_independent_verification",
                    })
                    used.add(low)
                    by_publisher[publisher] = by_publisher.get(publisher, 0) + 1
                    total += len(sentence)
            if dossier["lead_feed_context"]:
                dossier["uncertainties"].append(
                    "Additional complete RSS sentences are attributed "
                    "publisher descriptions, not independently verified facts."
                )
    return sum(len(card["lead_feed_context"])
               for chapter in dossiers.values() for card in chapter)


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
            for detail in dossier.get("lead_feed_context", []):
                source = next((
                    src for src in dossier["sources"]
                    if src["url"] == detail.get("url")
                    and src["publisher"] == detail.get("publisher")
                ), None)
                exact = detail.get("exact_excerpt")
                if (source is None or not isinstance(exact, str)
                        or exact not in newsroom3.clean(source.get("summary"), 900)
                        or exact not in _complete_rss_sentences(source.get("summary"))
                        or detail.get("source_type") != "trusted_rss_description"
                        or detail.get("status") !=
                           "publisher_report_not_independent_verification"
                        or not _trusted_feed_candidate({
                            "publisher": source["publisher"], "url": source["url"],
                            "provenance": ("primary_release_feed"
                                           if source.get("primary") else "publisher_rss"),
                        })):
                    raise ValueError(
                        "Additional lead detail is not exactly traceable "
                        "to trusted publisher feed source metadata"
                    )
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
        "official_eligible_urls": sum(
            card.get("official_retrieval35", {}).get("eligible_issuer_links", 0)
            for chapter in dossiers.values() for card in chapter
        ),
        "official_urls_rejected_or_unavailable": sum(
            card.get("official_retrieval35", {}).get("rejected_or_unavailable", 0)
            for chapter in dossiers.values() for card in chapter
        ),
        "official_urls_skipped_by_cap": sum(
            card.get("official_retrieval35", {}).get(
                "skipped_due_to_global_or_story_cap", 0
            ) for chapter in dossiers.values() for card in chapter
        ),
        "official_distinct_excerpts": sum(
            len(doc["excerpts"]) for chapter in dossiers.values()
            for card in chapter for doc in card.get("official_context", [])
        ),
        "selected_story_related_feeds": related,
        "event_link35": {
            "trusted_candidates_examined": sum(
                card.get("event_link35_review", {}).get(
                    "trusted_candidates_examined", 0
                ) for chapter in dossiers.values() for card in chapter
            ),
            "same_event_candidates": sum(
                card.get("event_link35_review", {}).get(
                    "same_event_candidates", 0
                ) for chapter in dossiers.values() for card in chapter
            ),
            "added_source_reports": related,
            "independent_corroboration_established": False,
        },
        "lead_feed_context_sentences": sum(
            len(card.get("lead_feed_context", []))
            for chapter in dossiers.values() for card in chapter
        ),
        "lead_feed_context_method": "verbatim complete trusted RSS descriptions, no article scraping",
        "independent_fact_checks": 0,
        "comparison": "publisher-excerpt comparison only; numbers require review",
    }


def enrich_writer_material(dossiers, existing):
    """Pass short exact primary-source excerpts, NEVER full article bodies."""
    for section, chapter in dossiers.items():
        for idx, dossier in enumerate(chapter):
            writer = existing[section][idx]
            writer["feed_detail_context"] = [
                {
                    "publisher": detail["publisher"],
                    "url": detail["url"],
                    "exact_excerpt": detail["exact_excerpt"],
                    "status": "publisher_claim_not_independently_verified",
                }
                for detail in dossier.get("lead_feed_context", [])
            ]
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
        f"Trusted extra reports considered for same-event matching: "
        f"{stats['event_link35']['trusted_candidates_examined']}",
        f"Same-event candidates found: "
        f"{stats['event_link35']['same_event_candidates']}",
        f"Official issuer URLs eligible: {stats['official_eligible_urls']}; "
        f"unavailable or unsuitable: {stats['official_urls_rejected_or_unavailable']}; "
        f"skipped by bounded budget: {stats['official_urls_skipped_by_cap']}",
        "Lexical same-event matching is not independent corroboration.",
        f"Additional complete lead-story RSS sentences: "
        f"{stats['lead_feed_context_sentences']}",
        "These are source-attributed RSS descriptions, not full verified reporting.",
        "No independently verified factual claims are implied.",
    ]
    for category, chapter in dossiers.items():
        for dossier in chapter:
            for detail in dossier.get("lead_feed_context", []):
                lines.append(
                    f"{category} extra RSS context: {detail['publisher']} | "
                    f"{detail['url']} | {detail['exact_excerpt']}"
                )
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
