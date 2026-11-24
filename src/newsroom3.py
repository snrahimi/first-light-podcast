"""First Light Newsroom 3.0: provenance-first source expansion and evidence cards.

3A: bounded GDELT discovery, plus NASA/BLS/CISA primary-source metadata.
3B: independent topic-level research dossiers, not copied full articles.
3C: per-claim exact supporting excerpts + fail-closed numerical checks.
3D: structured evidence inputs for the LLM writer, with explicit uncertainty.

This module DOES NOT fact-check full articles or manufacture verified assertions.
Automated matching is a discovery signal; it must not be described as editorial
verification. External article bodies are never scraped or republished.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
import html
import logging
import os
import re
from urllib.parse import urlsplit

import feedparser
import requests

if __package__:
    from . import editorial
else:
    import editorial

LOG = logging.getLogger("firstlight.newsroom3")

GDELT_API = "https://api.gdeltproject.org/api/v2/doc/doc"
PRIMARY_RSS = (
    ("world", "United Nations Press Releases", "https://press.un.org/en/rss.xml", "press.un.org"),
    ("science", "NASA News Releases", "https://www.nasa.gov/news-release/feed/", "nasa.gov"),
    ("business", "U.S. Bureau of Labor Statistics", "https://www.bls.gov/feed/bls_latest.rss", "bls.gov"),
)
CISA_KEV = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
# These third-party domains appear only as extra discovery links. We never
# ingest the full article or promote an unverified GDELT lead to sourced news.
DISCOVERY_DOMAINS = frozenset({
    "dw.com", "france24.com", "africanews.com", "thehindu.com",
    "japantimes.co.jp", "abc.net.au", "scmp.com", "reuters.com",
    "apnews.com", "aljazeera.com", "bbc.com", "bbc.co.uk",
    "theguardian.com", "npr.org",
})
DANGEROUS_CLAIMS = re.compile(
    r"\b(independently verified|we verified|fact.checked|confirmed by multiple"
    r" independent sources|our reporting confirms)\b", re.I
)
NUMBER = re.compile(r"(?<![a-zA-Z0-9])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?(?![a-zA-Z0-9])")
USER_AGENT = {"User-Agent": "FirstLightWorldReport/3.0 (source-linked daily briefing)"}


def host_ok(url, domains):
    try:
        p = urlsplit(url)
        host = (p.hostname or "").lower()
        return (p.scheme == "https" and p.username is None
                and p.password is None and p.port in (None, 443)
                and any(host == domain or host.endswith("." + domain)
                        for domain in domains))
    except ValueError:
        return False


def clean(text, limit=230):
    value = re.sub(r"<[^>]*>", " ", str(text or ""))
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= limit:
        return value
    return value[:limit].rsplit(" ", 1)[0].strip()


def _published_utc(parsed):
    try:
        return datetime.fromtimestamp(calendar.timegm(parsed), timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _recent_age(now, published, max_hours=48):
    if published is None:
        return None
    hours = (now.astimezone(timezone.utc) - published).total_seconds() / 3600
    if -1 <= hours <= max_hours:
        return round(max(0, hours), 2)
    return None


def primary_rss_candidates(now, get=requests.get):
    """Read small, official RSS excerpts; do not scrape linked articles."""
    items = {"world": [], "business": [], "science": [], "tech": []}
    for category, publisher, url, domain in PRIMARY_RSS:
        try:
            response = get(url, headers=USER_AGENT, timeout=(8, 14))
            response.raise_for_status()
            if len(response.content) > 1_500_000:
                raise ValueError("Oversized primary RSS")
            feed = feedparser.parse(response.content)
            for entry in feed.entries[:12]:
                link = entry.get("link", "")
                published = _published_utc(
                    entry.get("published_parsed") or entry.get("updated_parsed")
                )
                age = _recent_age(now, published)
                title = clean(entry.get("title"), 175)
                if not title or age is None or not host_ok(link, (domain,)):
                    continue
                items[category].append({
                    "category": category,
                    "publisher": publisher,
                    "title": title,
                    "summary": clean(entry.get("summary"), 180),
                    "url": link,
                    "published": published.isoformat(),
                    "age": age,
                    "provenance": "primary_release_feed",
                })
        except (requests.RequestException, ValueError, TypeError) as exc:
            LOG.warning("Primary source %s currently unavailable (%s)",
                        publisher, type(exc).__name__)
    return items


def cisa_kev_candidates(now, get=requests.get):
    """CISA-maintained catalog; only NEW dateAdded entries, not general advisories."""
    try:
        response = get(CISA_KEV, headers=USER_AGENT, timeout=(8, 18))
        response.raise_for_status()
        if len(response.content) > 10_000_000:
            raise ValueError("Oversized KEV catalog")
        records = response.json().get("vulnerabilities", [])
        found = []
        for record in records[-200:]:
            d = date.fromisoformat(record["dateAdded"])
            age = (now.date() - d).days
            if age < 0 or age > 2:
                continue
            cve = clean(record.get("cveID"), 22)
            name = clean(record.get("vulnerabilityName"), 140)
            description = clean(record.get("shortDescription"), 170)
            if not re.fullmatch(r"CVE-\d{4}-\d{4,8}", cve) or not name:
                continue
            found.append({
                "category": "tech",
                "publisher": "CISA Known Exploited Vulnerabilities",
                "title": f"CISA adds {cve}: {name}",
                "summary": description,
                "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
                "published": d.isoformat(),
                "publication_precision": "date_only",
                "age": age * 24,
                "provenance": "primary_official_catalog",
            })
        return found[-3:]
    except (requests.RequestException, KeyError, ValueError, TypeError) as exc:
        LOG.warning("CISA KEV source currently unavailable (%s)", type(exc).__name__)
        return []


def discover_gdelt(now, get=requests.get):
    """One bounded public DOC 2.0 call. Links only. Not broadcast-ready evidence."""
    if os.getenv("NEWSROOM_GDELT_ENABLED", "true").lower() not in ("1", "true", "yes"):
        return []
    try:
        response = get(
            GDELT_API,
            params={
                "query": '(election OR ceasefire OR disaster OR inflation OR cybersecurity)',
                "mode": "artlist", "format": "json",
                "timespan": "24h", "maxrecords": 45, "sort": "datedesc",
            },
            headers=USER_AGENT, timeout=(8, 16),
        )
        response.raise_for_status()
        if len(response.content) > 900_000:
            raise ValueError("Oversized GDELT discovery result")
        items, urls = [], set()
        for entry in response.json().get("articles", [])[:45]:
            url = str(entry.get("url") or "")
            title = clean(entry.get("title"), 170)
            if not title or url in urls or not host_ok(url, DISCOVERY_DOMAINS):
                continue
            # Some discovery providers omit usable timestamps. No fabricated
            # clock is assigned: this record is never eligible for narration.
            urls.add(url)
            items.append({
                "title": title, "url": url, "publisher_domain": urlsplit(url).hostname,
                "discovery_only": True, "source": "GDELT Project DOC 2.0",
            })
            if len(items) == 18:
                break
        return items
    except (requests.RequestException, ValueError, TypeError) as exc:
        LOG.warning("GDELT discovery unavailable (%s)", type(exc).__name__)
        return []


def collect_source_expansion(now, *, get=requests.get):
    official = primary_rss_candidates(now, get=get)
    official["tech"].extend(cisa_kev_candidates(now, get=get))
    leads = discover_gdelt(now, get=get)
    LOG.info("Newsroom 3 source scan: %d official items, %d GDELT leads",
             sum(map(len, official.values())), len(leads))
    return official, leads


def augment_groups(groups, primary):
    """Preserve existing feeds if official sources fail; keep publisher provenance."""
    merged = {category: list(entries) for category, entries in groups.items()}
    for category, entries in primary.items():
        if category not in merged:
            continue
        known = {(e["publisher"], e["url"], e["title"]) for e in merged[category]}
        for entry in entries:
            identity = (entry["publisher"], entry["url"], entry["title"])
            if identity not in known:
                merged[category].append(entry)
                known.add(identity)
    return merged


def claim_items(story):
    """Claims must quote exact RSS *headline or summary* fragments.

    Records of direct source wording are evidence of what the source *said*,
    NOT independent proof that the reported event occurred as described.
    """
    sources = [{
        "publisher": story["publisher"],
        "url": story["url"],
        "title": story["title"],
        "summary": story.get("short_summary", ""),
        "published": story["published"],
        "primary": story.get("provenance", "").startswith("primary_"),
    }]
    sources.extend({
        "publisher": s["publisher"], "url": s["url"],
        "title": s["title"], "summary": s.get("short_summary", ""),
        "published": s.get("published"),
        "primary": s.get("provenance", "").startswith("primary_"),
    } for s in story.get("related_reports", []))
    claims = []
    for idx, source in enumerate(sources):
        for part in ("title", "summary"):
            statement = clean(source.get(part), 195)
            if len(statement) < 12 or any(
                x["source_url"] == source["url"] and x["evidence"] == statement
                for x in claims
            ):
                continue
            claims.append({
                "id": f"c{idx + 1}{'a' if part == 'title' else 'b'}",
                "claim": statement,
                "evidence": statement,
                "evidence_field": part,
                "source_url": source["url"],
                "publisher": source["publisher"],
                "published": source.get("published"),
                "evidence_status": "primary_statement" if source["primary"]
                                   else "attributed_publisher_report",
                "independently_verified": False,
            })
    return sources, claims


def build_dossiers(edition, gdelt_leads):
    """Curated story cards with excerpts, uncertainty and discovery-only leads."""
    dossiers = {}
    for section, stories in edition["rundown"].items():
        dossiers[section] = []
        for story in stories:
            sources, claims = claim_items(story)
            leads = [
                {"title": lead["title"], "url": lead["url"],
                 "status": "discovery_only_not_evidence"}
                for lead in gdelt_leads
                if editorial.story_similarity(story["title"], lead["title"]) >= .50
            ][:2]
            # Never submit discovery-only material to the spoken-news writer.
            dossier = {
                "category": story["category"],
                "headline": story["title"],
                "previous_coverage": story.get("previous_headline"),
                "previous_date": story.get("previous_date"),
                "source_count": len({x["publisher"] for x in sources}),
                "evidence_depth": story.get("evidence_depth", {}),
                "freshness": {
                    "reported_publication": story.get("published"),
                    "prior_edition_coverage": story.get("coverage_status"),
                    "background_is_not_new_reporting": True,
                },
                "editorial_review": {
                    "sensitive_claims_present": bool(
                        editorial.key_tokens(story["title"]) & set((
                            "killed", "deaths", "casualties", "election",
                            "outbreak", "bombing", "evacuation",
                            "assassination", "genocide", "hostages"
                        ))
                    ),
                    "human_fact_check_completed": False,
                    "automation_cannot_verify_truth": True,
                },
                "sources": sources,
                "claim_ledger": claims[:6],
                "verified_facts": [],  # None without an independent check.
                "uncertainties": [
                    "Feed excerpts alone cannot establish every factual detail",
                    "Related headlines do not prove independent corroboration",
                ],
                "discovery_leads": leads,
                "source_status": (
                    "official_source_statement" if sources[0]["primary"] else
                    "publisher_reports_multiple_topics"
                    if len({x["publisher"] for x in sources}) > 1 else
                    "single_publisher_report"
                ),
            }
            dossiers[section].append(dossier)
    return dossiers


def validate_dossiers(dossiers):
    """Fail closed if a ledger claim cannot be found verbatim in its source."""
    checked = 0
    for chapter in dossiers.values():
        for dossier in chapter:
            if not dossier["claim_ledger"]:
                raise ValueError("No evidence for selected news story")
            for claim in dossier["claim_ledger"]:
                source = next(
                    (s for s in dossier["sources"]
                     if s["url"] == claim["source_url"]
                     and s["publisher"] == claim["publisher"]), None
                )
                if source is None:
                    raise ValueError("Claim lacks its linked publisher source")
                excerpt = clean(source.get(claim["evidence_field"]), 195)
                if excerpt != claim["evidence"] or excerpt != claim["claim"]:
                    raise ValueError("Claim not traceable to original source metadata")
                if not host_ok(claim["source_url"], (urlsplit(claim["source_url"]).hostname,)):
                    raise ValueError("Evidence source has invalid URL")
                if source["primary"]:
                    name = source["publisher"].lower()
                    allowed = (
                        ("nasa.gov",) if "nasa" in name else
                        ("bls.gov",) if "labor statistics" in name else
                        ("cisa.gov",) if "cisa" in name else
                        ("press.un.org",) if "united nations press" in name else ()
                    )
                    if not allowed or not host_ok(source["url"], allowed):
                        raise ValueError("Primary claim does not link to its issuing agency")
                if claim.get("independently_verified") is not False:
                    raise ValueError("Unsupported claim of independent verification")
                checked += 1
    return {"attributed_claims": checked,
            "independently_verified_facts": 0,
            "method": "exact-source-excerpt matching, NOT truth adjudication"}


def _weather_numeric_tokens(weather):
    """Allow provider-supplied weather numerals and our spoken rounding.

    The weather reader uses round() on measured temperature, high, low,
    rain probability and wind. For example, a structured value of 67.2
    becomes "67" in the spoken script. The evidence gate must accept that
    rounding without permitting unrelated invented statistics.
    """
    tokens = set()
    rounded_fields = {
        "temperature_f", "high_f", "low_f",
        "max_rain_percent", "wind_mph",
    }

    def collect(value):
        if value is None or isinstance(value, bool):
            return
        if isinstance(value, dict):
            for item in value.values():
                collect(item)
        elif isinstance(value, (tuple, list)):
            for item in value:
                collect(item)
        elif isinstance(value, (int, float, str)):
            tokens.update(NUMBER.findall(str(value)))

    if not isinstance(weather, dict):
        return tokens
    collect(weather)
    for name in rounded_fields:
        value = weather.get(name)
        if isinstance(value, (float, int)) and not isinstance(value, bool):
            try:
                tokens.add(str(round(value)))
            except (ValueError, OverflowError):
                pass
    return tokens


def script_numeric_gate(script, dossiers, weather, now):
    """Reject new digit-based figures not in supplied evidence or weather.

    Not semantic verification. Spelled-out numerals and paraphrases remain a
    limitation, and substantive claims still need independent editorial review.
    """
    if DANGEROUS_CLAIMS.search(script):
        raise ValueError("Broadcast overclaims independent verification")
    evidence = " ".join(
        claim["evidence"]
        for chapter in dossiers.values()
        for dossier in chapter
        for claim in dossier["claim_ledger"]
    )
    expected = set(NUMBER.findall(evidence))
    for chapter in dossiers.values():
        for dossier in chapter:
            for document in dossier.get("official_context", []):
                for excerpt in document.get("excerpts", []):
                    expected.update(NUMBER.findall(excerpt))
    expected.update(_weather_numeric_tokens(weather))
    expected.update({str(now.year), str(now.day), "3.0", "5", "6", "7"})
    unexpected = sorted(set(NUMBER.findall(script)) - expected)
    if unexpected:
        raise ValueError(
            "Unsupported numeric text in script: " + ", ".join(unexpected[:8])
        )
    return {"numeric_tokens_approved": True,
            "quote_and_qualifier_review": "human review still advised"}


def writer_material(dossiers):
    """Exclude GDELT discovery leads and unsourced conjecture from AI input."""
    return {
        section: [{
            "headline": item["headline"],
            "source_status": item["source_status"],
            "evidence_depth": item.get("evidence_depth", {}),
            "freshness": item.get("freshness", {}),
            "editorial_review": item.get("editorial_review", {}),
            "evidence": [{
                "publisher": c["publisher"], "text": c["claim"],
                "url": c["source_url"], "published": c.get("published"),
                "status": c["evidence_status"],
            } for c in item["claim_ledger"]],
            "uncertainties": item["uncertainties"],
            "previous": (
                {"headline": item["previous_coverage"],
                 "date": item["previous_date"]}
                if item["previous_coverage"] else None
            ),
        } for item in chapter]
        for section, chapter in dossiers.items()
    }


def audit_export(dossiers, metrics, discovery_leads):
    """Public, compact, machine-readable evidence and source audit."""
    return {
        "system": "First Light Newsroom 3.0",
        "corroboration": "Headline/excerpt records only; NOT full-article verification",
        "method": metrics["method"],
        "attributed_claims": metrics["attributed_claims"],
        "independently_verified_facts": 0,
        "dossiers": dossiers,
        "discovery": {
            "source": "The GDELT Project (https://www.gdeltproject.org/)",
            "count": len(discovery_leads),
            "used_as_broadcast_evidence": False,
        },
    }


def audit_notes(dossiers, metrics):
    lines = [
        "NEWSROOM 3.0 EVIDENCE AUDIT",
        "Attribution is not independent factual verification.",
        "Original publisher RSS headlines and brief summaries are the supported evidence.",
        "No full paywalled articles, publisher text, or third-party podcast audio were copied.",
        f"Exact claim-to-excerpt matches: {metrics['attributed_claims']}",
        "Independently fact-checked claims: 0 (not available in this automated edition).",
    ]
    for section, chapter in dossiers.items():
        for item in chapter:
            lines.append(f"\n{section}: {item['headline']}")
            lines.append("Provenance: " + item["source_status"])
            for claim in item["claim_ledger"]:
                lines.append(
                    f"- {claim['publisher']} | {claim['source_url']} | "
                    f"{claim['evidence_status']} | {claim['evidence']}"
                )
    return "\n".join(lines)
