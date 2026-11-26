"""First Light Newsroom 3.4 Research Desk.

Source COVERAGE and exact-attribution audits, not independent truth
adjudication. The newsroom only uses already gathered trusted publisher
RSS material and issuer-authorized official documents. No web crawling,
extra model requests, invented context, or length-padding retries.
"""
from __future__ import annotations

from collections import Counter
import re
from urllib.parse import urlsplit

if __package__:
    from . import newsroom3, research33
else:
    import newsroom3
    import research33

MAX_LEADS = 2
MAX_FACTS_PER_LEAD = 7
MAX_FACT_CHARS = 340
REPORTING_WORDS = re.compile(r"\b(?:will|expects?|scheduled?|plans?|next|upcoming)\b", re.I)
FABRICATED_FIELDWORK = re.compile(
    r"\b(?:I (?:interviewed|spoke (?:directly )?with|witnessed)|"
    r"our (?:reporter|correspondent) (?:on the ground|confirmed)|"
    r"we independently verified|our investigation confirms)\b",
    re.I,
)


def source_coverage(groups):
    """Auditable candidate counts and publisher diversity by news desk.

    More candidate feeds do NOT imply factual corroboration or working
    URLs. Only previously filtered, curated HTTPS source candidates count.
    """
    categories = {}
    all_publishers = set()
    for section in ("world", "business", "science", "tech"):
        stories = list(groups.get(section, []))
        publishers = sorted({
            str(story.get("publisher"))
            for story in stories if story.get("publisher")
        })
        all_publishers.update(publishers)
        categories[section] = {
            "stories": len(stories),
            "publishers": publishers[:12],
            "distinct_publishers": len(publishers),
        }
    notes = []
    if categories["world"]["distinct_publishers"] < 3:
        notes.append("Fewer than three different world-news publishers in candidate pool")
    for category in ("business", "science", "tech"):
        if not categories[category]["stories"]:
            notes.append(f"No fresh {category} publisher RSS candidates")
    return {
        "system": "Newsroom 3.4 source diversity",
        "categories": categories,
        "distinct_publishers_all_categories": len(all_publishers),
        "review_flags": notes,
        "feed_response_health_observed": False,  # RSS failures logged upstream
        "fact_verification_claimed": False,
    }


def _safe_exact_source(card, source_url, publisher, excerpt):
    if not excerpt or not isinstance(excerpt, str):
        raise ValueError("Empty or malformed lead supporting excerpt")
    sources = [
        x for x in card.get("sources", [])
        if x.get("url") == source_url and x.get("publisher") == publisher
    ]
    if len(sources) != 1:
        raise ValueError("Lead excerpt source not uniquely traceable")
    source = sources[0]
    matched = any(
        excerpt == newsroom3.clean(source.get(field), 240)
        for field in ("title", "summary")
    ) or excerpt in newsroom3.clean(source.get("summary"), 900)
    if not matched:
        raise ValueError("Lead claim not a verbatim source excerpt")
    # Base claim provenance was authenticated by RSS ingestion and
    # newsroom3.validate_dossiers before this stage. Do not add a new
    # domain whitelist that would reject synthetic offline fixtures or
    # legitimate issuer-approved future feeds.
    try:
        host = urlsplit(source_url).hostname
    except (ValueError, TypeError):
        host = None
    if not host or not newsroom3.host_ok(source_url, (host,)):
        raise ValueError("Lead excerpt source is not a valid HTTPS URL")
    return source


def lead_research_cards(dossiers):
    """Bundle distinct verified-to-source excerpts into a useful lead brief.

    The content verifies only that an attributed publisher/agency supplied
    these exact words, NEVER that events occurred as described.
    """
    result = []
    leads = dossiers.get("Top world headlines", [])
    for index, card in enumerate(leads[:MAX_LEADS]):
        items, used = [], set()
        def add(publisher, url, excerpt, basis):
            raw = str(excerpt or "").strip()
            if not raw:
                return
            if len(raw) > MAX_FACT_CHARS:
                return
            if (publisher, url, raw.casefold()) in used:
                return
            _safe_exact_source(card, url, publisher, raw)
            used.add((publisher, url, raw.casefold()))
            items.append({
                "publisher": publisher,
                "url": url,
                "exact_excerpt": raw,
                "provenance": basis,
                "independently_verified": False,
            })
        for claim in card.get("claim_ledger", []):
            if len(items) >= MAX_FACTS_PER_LEAD:
                break
            add(claim.get("publisher"), claim.get("source_url"),
                claim.get("evidence"), "linked_publisher_statement")
        for extra in card.get("lead_feed_context", []):
            if len(items) >= MAX_FACTS_PER_LEAD:
                break
            # Research 3.3 already exact-validated before arriving here.
            _safe_exact_source(card, extra.get("url"),
                               extra.get("publisher"),
                               extra.get("exact_excerpt"))
            add(extra["publisher"], extra["url"], extra["exact_excerpt"],
                "complete_publisher_rss_sentence")
        official = []
        for document in card.get("official_context", []):
            if not research33._issuer_matches(
                document.get("url", ""), document.get("publisher", "")
            ):
                raise ValueError("Research Desk official document issuer mismatch")
            if not any(
                src["url"] == document.get("url") and
                src["publisher"] == document.get("publisher") and
                src.get("primary")
                for src in card.get("sources", [])
            ):
                raise ValueError("Research Desk official document source missing")
            for excerpt in document.get("excerpts", [])[:3]:
                if excerpt not in document.get("source_text", "") or len(excerpt) > 260:
                    raise ValueError("Research Desk official excerpt not exact")
                if len(official) < 3:
                    official.append({
                        "issuer": document["publisher"],
                        "url": document["url"],
                        "exact_excerpt": excerpt,
                        "provenance": "verified_to_issuer_text_not_independently_true",
                    })
        publishers = {fact["publisher"] for fact in items}
        next_steps = [
            fact for fact in items
            if REPORTING_WORDS.search(fact["exact_excerpt"])
        ][:2]
        flags = []
        if len(publishers) < 2:
            flags.append("Only one publisher's sourced material for this lead")
        if len(items) < 3 and not official:
            flags.append("Limited distinct evidence: brief treatment recommended")
        if card.get("reporting_comparison", {}).get("different_numbers_need_review"):
            flags.append("Different reported numbers: needs human review")
        if card.get("editorial_review", {}).get("sensitive_claims_present"):
            flags.append("Sensitive claim: human review required")
        result.append({
            "lead_number": index + 1,
            "headline": card.get("headline", ""),
            "claims": items,
            "official_issuer_excerpts": official,
            "source_count": len(publishers),
            "source_verified_excerpt_count": len(items) + len(official),
            "attributed_possible_next_steps": next_steps,
            "prior_edition_headline": card.get("previous_coverage"),
            "review_flags": flags,
            "independently_verified_facts": 0,
            "editorial_rule": (
                "Explain only what attached reports or issuing agencies state. "
                "An apparent next step is a source's claim, not a promise. "
                "Previous headlines alone do not establish what changed. "
                "Where evidence is thin, make this lead shorter."
            ),
        })
    return result


def attach_writer_research(material, research_cards):
    """Attach compact, source-traceable prompts, without separate model calls."""
    for index, card in enumerate(research_cards):
        rows = material.get("Top world headlines", [])
        if index >= len(rows):
            raise ValueError("Research Desk lead count differs from material")
        if rows[index].get("headline") != card["headline"]:
            raise ValueError("Research Desk lead order/headline changed")
        rows[index]["research_desk34"] = card
    return material


def editorial_review(script, research_cards, coverage, draft=None):
    """Honest advisory quality checks and one fail-closed fabrication gate."""
    text = str(script or "")
    fabricated = bool(FABRICATED_FIELDWORK.search(text))
    weak = [
        {"lead_number": item["lead_number"], "headline": item["headline"],
         "flags": item["review_flags"]}
        for item in research_cards if item["review_flags"]
    ]
    source_count = sum(item["source_verified_excerpt_count"]
                       for item in research_cards)
    under = (draft or {}).get("under_delivered_sections", [])
    return {
        "system": "Newsroom 3.4 evidence and editorial checks",
        "source_excerpt_provenance_validated": True,
        "underlying_events_independently_fact_checked": False,
        "lead_source_excerpts": source_count,
        "lead_evidence_review": weak,
        "coverage_flags": list(coverage.get("review_flags", [])),
        "under_delivered_writer_sections": under,
        "fabricated_fieldwork_language_detected": fabricated,
        "hard_reject_reason": (
            "fabricated_original_fieldwork_or_independent_verification"
            if fabricated else None
        ),
        "editorial_quality_is_not_truth_verification": True,
    }


def public_notes(coverage, cards, review):
    return "\n".join([
        "NEWSROOM 3.4 RESEARCH DESK",
        "Research confirms source-excerpt provenance, NOT independent truth.",
        f"Candidate publisher diversity: {coverage['distinct_publishers_all_categories']}",
        f"World leads researched: {len(cards)}",
        f"Exact, linked lead excerpts: {review['lead_source_excerpts']}",
        f"Official issuer excerpts: {sum(len(c['official_issuer_excerpts']) for c in cards)}",
        f"Leads requiring further review: {len(review['lead_evidence_review'])}",
        f"Source diversity warnings: {len(review['coverage_flags'])}",
        "No extra model calls, article scraping or invented corroboration.",
    ])
