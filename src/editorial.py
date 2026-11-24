"""First Light newsroom: sourced curation, headline corroboration and episode memory.

This module intentionally makes NO model/API calls. Related headlines from
multiple publishers are leads for verification, NOT proof that any factual
claim is true. Never present token similarity as independent fact-checking.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from difflib import SequenceMatcher
import json
import logging
import re
from urllib.parse import urlparse

import requests

LOG = logging.getLogger("firstlight.editorial")
MEMORY_MARKER = "FIRST_LIGHT_MEMORY_V1:"
STOPWORDS = frozenset("""
a an and are as at be been before by can did do does for from has have had
he her hers him his i in into is it its of on or our over she since some than
that the their them there these this those to up us was were what when where
which while who will with would you your after amid said says latest live
updates breaking reports report new news world today week now more how why
could about across against near around early first second top including
""".split())
IMPACT_WORDS = frozenset("""
election elections war ceasefire peace strikes attack attacks killed deaths
treaty sanctions tariffs central bank inflation recession economy trade
earthquake flood hurricane wildfire tornado evacuation emergency outbreak
pandemic cybersecurity breach vulnerable security research discovery launch
court ruling law legislation rights summit agreement conflict
""".split())
REGION_TERMS = {
    "americas": set("united states america american canada mexico brazil argentina colombia chile peru venezuelan cuba washington".split()),
    "europe": set("europe eu uk britain british france germany italy spain ukraine russia european london paris brussels".split()),
    "middle_east": set("israel gaza iran iraq syria lebanon yemen saudi qatar jordan palestinian".split()),
    "africa": set("africa african sudan egypt nigeria kenya ethiopia congo south africa".split()),
    "asia_pacific": set("china chinese japan japanese korea korean taiwan india pakistan indonesia philippines australia asia singapore".split()),
}


def key_tokens(title):
    words = re.findall(r"[a-z0-9]+", str(title).lower())
    return set(w for w in words if len(w) >= 3 and w not in STOPWORDS)


def story_similarity(a, b):
    """Conservative related-headline heuristic, not claim corroboration."""
    left, right = key_tokens(a), key_tokens(b)
    shared = len(left & right)
    if not left or not right or shared < 3:
        return 0.0
    jaccard = shared / len(left | right)
    seq = SequenceMatcher(None, " ".join(sorted(left)), " ".join(sorted(right))).ratio()
    return max(jaccard, seq * 0.80 if shared >= 4 else 0)


def same_topic(a, b):
    return story_similarity(a, b) >= 0.53


def region(title):
    tokens = key_tokens(title)
    matches = {r: len(tokens & words) for r, words in REGION_TERMS.items()}
    best = max(matches, key=matches.get)
    return best if matches[best] else "other"


def _parse_time(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        return None


def cluster_stories(groups):
    """Keep multiple publisher headlines, not just the first syndication."""
    raw = [
        dict(item, category=category)
        for category, items in groups.items()
        for item in items
        if item.get("title") and item.get("url")
    ]
    raw.sort(key=lambda x: (x.get("age", 999), x["title"]))
    clusters = []
    for candidate in raw:
        category = candidate["category"]
        # Science and tech may overlap, but treat completely separate beats
        # with caution. World / business overlap is allowed only if very close.
        matches = [
            cluster for cluster in clusters
            if any(same_topic(candidate["title"], r["title"]) for r in cluster["reports"])
            and (category == cluster["category"]
                 or story_similarity(candidate["title"], cluster["lead"]["title"]) >= 0.76)
        ]
        cluster = max(matches, key=lambda x: story_similarity(
            candidate["title"], x["lead"]["title"])) if matches else None
        if cluster is None:
            clusters.append({
                "category": category,
                "lead": candidate,
                "reports": [candidate],
            })
        elif not any(r["url"] == candidate["url"] for r in cluster["reports"]):
            cluster["reports"].append(candidate)
            # Prefer informative and fresh lead headlines
            lead = cluster["lead"]
            if len(key_tokens(candidate["title"])) > len(key_tokens(lead["title"])) + 3:
                cluster["lead"] = candidate
    for cluster in clusters:
        cluster["reports"] = sorted(cluster["reports"], key=lambda x: x.get("age", 999))
        publishers = list(dict.fromkeys(r["publisher"] for r in cluster["reports"]))
        cluster["publishers"] = publishers
        cluster["multiple_publishers"] = len(publishers) >= 2
        cluster["region"] = region(cluster["lead"]["title"])
        cluster["id"] = sorted(key_tokens(cluster["lead"]["title"]))[:10]
    return clusters


def read_prior_releases(releases, now, days=7):
    """History embedded as small public metadata comments in release notes."""
    history = []
    for release in releases:
        tag = str(release.get("tag_name", ""))
        if not re.fullmatch(r"first-light-\d{4}-\d{2}-\d{2}", tag):
            continue
        day = _parse_time(tag.replace("first-light-", "") + "T12:00:00+00:00")
        if not day or not (0 < (now.date() - day.date()).days <= days):
            continue
        body = str(release.get("body") or "")
        match = re.search(r"<!--\s*" + MEMORY_MARKER + r"([A-Za-z0-9_-]+)\s*-->", body)
        if not match:
            continue
        try:
            blob = match.group(1)
            payload = json.loads(base64.urlsafe_b64decode(blob + "=" * (-len(blob) % 4)))
            if isinstance(payload.get("topics"), list):
                history.extend([
                    dict(story, date=payload.get("date", day.date().isoformat()))
                    for story in payload["topics"][:12]
                    if isinstance(story, dict) and story.get("title")
                ])
        except (ValueError, TypeError, KeyError):
            LOG.warning("Malformed public editorial memory on release %s", tag)
    return history[:100]


def load_history(repository, token, now, timeout=(8, 15)):
    """Fail safely to a stateless edition if GitHub history is unreachable."""
    if not token or not re.fullmatch(r"[\w.-]+/[\w.-]+", str(repository or "")):
        LOG.warning("Episode memory is unavailable: repository or token missing")
        return []
    try:
        response = requests.get(
            "https://api.github.com/repos/" + repository + "/releases",
            params={"per_page": 20},
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        return read_prior_releases(response.json(), now)
    except (requests.RequestException, ValueError, TypeError) as exc:
        LOG.warning("Could not retrieve past episode memory (%s)", type(exc).__name__)
        return []


def _historical_status(cluster, history):
    """Distinguish repetitive headlines from possible developing events."""
    title = cluster["lead"]["title"]
    similar = sorted(
        ((story_similarity(title, h["title"]), h) for h in history),
        key=lambda x: x[0], reverse=True,
    )
    if not similar or similar[0][0] < 0.53:
        return "new_to_show", None
    similarity, previous = similar[0]
    # Same headline with only tiny wording changes is not a meaningful update.
    return ("repeat" if similarity >= 0.86 else "related_update_unverified"), previous


def _rank(cluster, history):
    published = cluster["lead"]
    age = min(max(float(published.get("age", 42)), 0), 42)
    status, previous = _historical_status(cluster, history)
    score = {
        "world": 45, "business": 40, "science": 38, "tech": 38
    }.get(cluster["category"], 34)
    score += round(18 * (1 - age / 42))
    score += min(len(cluster["publishers"]) - 1, 2) * 8
    score += min(len(key_tokens(published["title"]) & IMPACT_WORDS), 2) * 7
    # Evidence depth is only a modest tiebreaker. High-impact urgent
    # breaking stories must not be excluded because reporting is sparse.
    distinct_excerpts = {
        (report.get("publisher"), str(report.get("summary", "")).strip())
        for report in cluster["reports"] if len(
            str(report.get("summary") or "").strip()) >= 45
    }
    official_statements = sum(
        str(report.get("provenance", "")).startswith("primary_")
        for report in cluster["reports"]
    )
    depth = min(10, len(distinct_excerpts) * 2 + official_statements * 3)
    cluster["evidence_depth"] = {
        "source_publishers": len(cluster["publishers"]),
        "substantive_feed_summaries": len(distinct_excerpts),
        "official_statements": official_statements,
        "ranking_bonus": depth,
        "independently_verified": False,
    }
    score += depth
    score += 5 if cluster["region"] != "other" else 0
    if status == "repeat":
        score -= 50
    elif status == "related_update_unverified":
        score -= 8
    else:
        score += 5
    return score, status, previous


def curate(groups, history, now):
    """Curate two leads, ~2 world briefs, 1 business, 1 science, 1 tech.

    Fairness/diversity are editorial nudges, not invented story relevance.
    Headlines are NOT automatically verified merely by similar wording.
    """
    clusters = cluster_stories(groups)
    for cluster in clusters:
        cluster["score"], cluster["status"], cluster["previous"] = _rank(cluster, history)
    candidates = sorted(
        (x for x in clusters if x["status"] != "repeat"),
        key=lambda x: (-x["score"], x["lead"]["age"], x["lead"]["title"]),
    )
    chosen, chosen_ids, used_regions = [], set(), set()

    def take(category, count, prefer_new_region=False):
        available = [
            c for c in candidates
            if c["category"] in category and id(c) not in chosen_ids
        ]
        if prefer_new_region:
            available.sort(key=lambda c: (
                c["region"] in used_regions, -c["score"], c["lead"]["age"],
            ))
        for item in available[:count]:
            chosen.append(item)
            chosen_ids.add(id(item))
            used_regions.add(item["region"])

    take(("world",), 2)  # Lead stories
    lead = list(chosen)
    take(("world",), 2, prefer_new_region=True)
    world_briefs = list(chosen[len(lead):])
    take(("business",), 1)
    take(("science",), 1)
    take(("tech",), 1)
    if len(chosen) < 6:
        take(("world", "business", "science", "tech"), 7 - len(chosen))
    # Preserve classic rundown while allowing a genuinely important update.
    categories = {
        "Top world headlines": lead,
        "Around the world": world_briefs,
        "Business and markets": [c for c in chosen if c["category"] == "business"],
        "Science": [c for c in chosen if c["category"] == "science"],
        "Technology and cybersecurity": [c for c in chosen if c["category"] == "tech"],
    }
    selected_ids = {id(c) for c in chosen}
    leftovers = [c for c in chosen if c["category"] == "world" and c not in lead + world_briefs]
    categories["Around the world"].extend(leftovers)
    if len(chosen) < 5:
        raise RuntimeError("Too few unique fresh topics for a sourced daily broadcast")
    presentation = {}
    for section, matches in categories.items():
        presentation[section] = [
            {
                "category": item["category"],
                "title": item["lead"]["title"],
                "publisher": item["lead"]["publisher"],
                "published": item["lead"]["published"],
                "url": item["lead"]["url"],
                "short_summary": item["lead"].get("summary", ""),
                "provenance": item["lead"].get("provenance", "publisher_rss"),
                "related_reports": [
                    {
                        "publisher": report["publisher"],
                        "title": report["title"],
                        "short_summary": report.get("summary", ""),
                        "url": report["url"],
                        "provenance": report.get("provenance", "publisher_rss"),
                        "published": report.get("published"),
                    }
                    for report in item["reports"]
                    if report["publisher"] != item["lead"]["publisher"]
                ][:2],
                "source_status": (
                    "multiple publishers with closely related headlines"
                    if item["multiple_publishers"] else
                    "single publisher's feed; attribute claims"
                ),
                "coverage_status": item["status"],
                "previous_headline": (
                    item["previous"].get("title") if item["previous"] else None
                ),
                "previous_date": (
                    item["previous"].get("date") if item["previous"] else None
                ),
                "score": item["score"],
                "evidence_depth": item["evidence_depth"],
                "region": item["region"],
            }
            for item in matches
        ]
    return {
        "date": now.date().isoformat(),
        "rundown": presentation,
        "count": sum(len(v) for v in presentation.values()),
        "related_source_count": sum(c["multiple_publishers"] for c in chosen),
        "history_items_consulted": len(history),
        "repeated_topics_avoided": sum(c["status"] == "repeat" for c in clusters),
    }


def edition_sources(edition):
    result, seen = [], set()
    for section in edition["rundown"].values():
        for story in section:
            for entry in [story, *story["related_reports"]]:
                url = entry["url"]
                if url not in seen and urlparse(url).scheme == "https":
                    seen.add(url)
                    result.append({
                        "title": entry["publisher"] + ": " + entry["title"],
                        "url": url,
                    })
    return result


def memory_note(edition):
    topics = [
        {
            "title": story["title"],
            "category": story["category"],
            "published": story["published"],
        }
        for stories in edition["rundown"].values()
        for story in stories
    ]
    payload = json.dumps(
        {"date": edition["date"], "topics": topics},
        separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return "<!-- " + MEMORY_MARKER + encoded + " -->"


def source_notes(edition):
    lines = [
        "Editorial source notes",
        "Headline similarity is a discovery signal only, not independent verification.",
        "Source links and timestamps are provided for independent reading.",
        "",
    ]
    for name, stories in edition["rundown"].items():
        lines.append(name)
        for story in stories:
            lines.append("- " + story["publisher"] + ": " + story["title"])
            lines.append("  " + story["url"])
            for other in story["related_reports"]:
                lines.append("  Related: " + other["publisher"] + ": " + other["url"])
            lines.append("  Confidence: " + story["source_status"])
            if story["previous_headline"]:
                lines.append("  Previously covered (" + str(story["previous_date"]) +
                             "): " + story["previous_headline"])
    return "\n".join(lines)


def speaking_text(script):
    """Safe expansions for spoken abbreviations. Not a name-pronunciation guess."""
    words = {
        r"\bNWS\b": "National Weather Service",
        r"\bGDP\b": "gross domestic product",
        r"\bU\.S\.(?=\s|$)": "United States",
        r"\bEU\b": "European Union",
        r"\bAI\b": "artificial intelligence",
        r"\bWHO\b": "World Health Organization",
        r"\bIMF\b": "International Monetary Fund",
        r"\bCISA\b": "Cybersecurity and Infrastructure Security Agency",
        r"\bBLS\b": "Bureau of Labor Statistics",
        r"\bU\.N\.(?=\s|$)": "United Nations",
    }
    result = script
    for pattern, replacement in words.items():
        result = re.sub(pattern, replacement, result)
    return result


def script_quality(script, edition, now):
    words = len(script.split())
    if words < 640 or words > 995:
        raise ValueError(f"Episode word count out of bounds: {words}")
    if "First Light" not in script or "San Antonio" not in script:
        raise ValueError("Missing show identity or San Antonio weather segment")
    if now.strftime("%Y") not in script:
        raise ValueError("Date not anchored in episode script")
    if not any(token.lower() in script.lower() for token in ("world", "international")):
        raise ValueError("World coverage missing in script")
    # Important: exact quotation validation requires publisher article text and
    # is NOT achievable from RSS alone. Prompt explicitly forbids invented facts.
    return {"script_words": words, "selected_stories": edition["count"],
            "related_source_count": edition["related_source_count"],
            "history_consulted": edition["history_items_consulted"],
            "repeats_avoided": edition["repeated_topics_avoided"]}
