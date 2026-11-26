"""Newsroom 3.6: conservative official-release editorial-value audit.

This is a source-comparison heuristic for unpublished review. It measures
whether an already accepted official excerpt contributes distinct wording
beyond the lead's RSS evidence. It is NOT a fact check, relevance proof,
or authorization to speak new claims.
"""
from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z][a-z0-9-]{2,}", re.I)
_STOP = frozenset("""
the and for from that this with have has had were was are being been
into about after before amid under over more than says said report reports
reported says officials official agency agencies news release releases
according statement statements today yesterday tomorrow their there which
these those they them will would could should also announced announces
announcing details says new latest press following including during
""".split())
MAX_ROWS = 12
MAX_EXCERPT = 260


def _terms(value):
    return {term.lower() for term in _TOKEN.findall(str(value or ""))}
           if term.lower() not in _STOP}


def review_official_context(lead_cards):
    """Audit accepted, attributed lead excerpts; never fetch or rewrite content.

    'Novel' means distinct lexical detail versus already attached publisher
    claims, not a verified event, genuine explanatory usefulness, or a
    recommendation to include it in the broadcast.
    """
    result = []
    used = 0
    for card in list(lead_cards or [])[:2]:
        baseline = " ".join(
            str(claim.get("exact_excerpt", ""))
            for claim in card.get("claims", [])
            if isinstance(claim, dict)
        )
        baseline_terms = _terms(card.get("headline", "") + " " + baseline)
        rows = []
        for item in card.get("official_issuer_excerpts", []):
            if used >= MAX_ROWS:
                break
            if not isinstance(item, dict):
                continue
            quote = item.get("exact_excerpt")
            if not isinstance(quote, str) or not quote or len(quote) > MAX_EXCERPT:
                continue
            issuer, url = item.get("issuer", ""), item.get("url", "")
            if not issuer or not isinstance(url, str) or not url.startswith("https://"):
                continue
            terms = _terms(quote)
            distinct = sorted(terms - baseline_terms)
            # A candidate for editorial attention, not an automatic usable fact.
            candidate = len(quote.split()) >= 10 and len(distinct) >= 3
            rows.append({
                "issuer": issuer,
                "url": url,
                "status": ("distinct_detail_candidate" if candidate
                           else "limited_additional_detail"),
                "new_content_terms": len(distinct),
                "editorial_human_review_required": True,
                "source_verified_not_fact_checked": True,
            })
            used += 1
        result.append({
            "headline": card.get("headline", ""),
            "official_excerpts_compared": len(rows),
            "distinct_detail_candidates": sum(
                row["status"] == "distinct_detail_candidate" for row in rows
            ),
            "comparison": rows,
        })
    return {
        "method": "lexical novelty compared with attributed RSS excerpts",
        "official_excerpts_compared": sum(
            c["official_excerpts_compared"] for c in result
        ),
        "distinct_detail_candidates": sum(
            c["distinct_detail_candidates"] for c in result
        ),
        "leads": result,
        "independent_factual_verification": False,
        "proven_editorial_usefulness": False,
        "automatic_broadcast_approval": False,
        "human_review_needed": True,
    }
