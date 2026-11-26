"""Conservative, reviewable speech-only pronunciation preparation.

Never mutate the source-grounded transcript, headline or evidence ledger.
ElevenLabs Flash v2.5 does not support the same inline SSML phonemes as
Flash v2. Use human-reviewed alias spellings for a short list of difficult
proper names; no guesses for unreviewed people. Contextual clock and
time-zone expansions are deterministic, not inferred from geography.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

LEXICON = Path(__file__).resolve().parents[1] / "config" / "voice_pronunciations.json"
MAX_RULES = 60
MAX_ALIAS_CHARACTERS = 85
# Locale-independent abbreviations after an actual spoken clock time.
GLOBAL_ZONES = {
    "UTC": "Coordinated Universal Time",
    "GMT": "Greenwich Mean Time",
}
# In English-language US broadcasting these explicit labels are unambiguous.
US_ZONES = {
    "EST": "Eastern Standard Time", "EDT": "Eastern Daylight Time",
    "MST": "Mountain Standard Time", "MDT": "Mountain Daylight Time",
    "PST": "Pacific Standard Time", "PDT": "Pacific Daylight Time",
    "ET": "Eastern Time", "MT": "Mountain Time", "PT": "Pacific Time",
}
# CST is also China/Cuba Standard Time, so only expand in verifiably
# San Antonio / NWS local weather context, never in global news.
LOCAL_ZONES = {"CST": "Central Standard Time",
               "CDT": "Central Daylight Time",
               "CT": "Central Time"}
AMBIGUOUS_ZONES = ("IST", "BST", "AST", "GST", "SST", "HST", "CST", "CDT", "CT")
CLOCK_ZONE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?P<clock>(?:0?[1-9]|1[0-2])(?::[0-5]\d)?\s*[AaPp]\.?[Mm]\.?)"
    r"\s*(?P<zone>UTC|GMT|EST|EDT|MST|MDT|PST|PDT|CST|CDT|ET|MT|PT|CT|IST|BST|AST|GST|SST|HST)\b",
    flags=re.IGNORECASE,
)
LOCAL_CONTEXT = re.compile(
    r"(?:National Weather Service|San Antonio|Austin/San Antonio|"
    r"local weather|weather in San Antonio|NWS (?:Austin|San Antonio))",
    re.IGNORECASE,
)
VALID_SPOKEN = re.compile(r"^[A-Za-z][A-Za-z \-']{1,84}$")
LOCAL_WEATHER_START = re.compile(
    r"And now, a look at the weather in San Antonio\.",
    flags=re.IGNORECASE,
)
LOCAL_CITY_NAME = re.compile(r"(?<!\w)San Antonio(?!\w)", flags=re.IGNORECASE)
# A tested-in-code, but not yet human-approved acoustic hypothesis.
# Only the weather segment near the end uses this alternative;
# the opening and all public transcripts keep the original spelling.
LOCAL_CITY_GUIDED_ALIAS = "San An-TOH-nee-oh"


def local_city_pronunciation(text, mode):
    """Restrict the optional weather-section alias to late local coverage."""
    if mode not in ("guided", "original"):
        raise ValueError("Unsupported San Antonio pronunciation mode")
    hit = LOCAL_WEATHER_START.search(text)
    if mode == "original" or not hit:
        return text, False
    # The source script's weather marker is produced by a controlled
    # deterministic template. Limit replacement to this trailing region.
    before, after = text[:hit.start()], text[hit.start():]
    after, replacements = LOCAL_CITY_NAME.subn(
        lambda _: LOCAL_CITY_GUIDED_ALIAS, after
    )
    return before + after, bool(replacements)



def load_glossary(path=LEXICON):
    """Parse and validate trusted *reviewed* alias pairs from repo JSON."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if (not isinstance(raw, dict) or raw.get("version") != 1
            or not isinstance(raw.get("rules"), list)
            or len(raw["rules"]) > MAX_RULES):
        raise ValueError("Pronunciation glossary schema/version invalid")
    result, known = [], set()
    for item in raw["rules"]:
        if not isinstance(item, dict):
            raise ValueError("Pronunciation glossary rule is not a record")
        written, spoken = item.get("written"), item.get("spoken")
        if (not isinstance(written, str) or not isinstance(spoken, str)
                or not 3 <= len(written) <= MAX_ALIAS_CHARACTERS
                or not VALID_SPOKEN.fullmatch(spoken)
                or not written.isprintable()
                or "<" in written or ">" in written
                or written.casefold() == spoken.casefold()):
            raise ValueError("Unsafe pronunciation glossary rule")
        if written.casefold() in known:
            raise ValueError("Duplicate pronunciation glossary term")
        known.add(written.casefold())
        result.append((written, spoken))
    return sorted(result, key=lambda item: -len(item[0]))


def _replace_names(text, rules):
    """Avoid partial matches: 'Kyiv' yes, 'Kyivan' no."""
    used = []
    output = text
    for written, spoken in rules:
        pattern = re.compile(
            r"(?<!\w)" + re.escape(written) + r"(?!\w)",
            flags=re.IGNORECASE,
        )
        count = len(pattern.findall(output))
        if count:
            output = pattern.sub(lambda _: spoken, output)
            used.append(written)
    return output, used


def _replace_clock_zones(text):
    """Only pronounce reliable time-zone readings in *clock* contexts.

    The ambiguous CST/CDT/CT abbreviations require local San Antonio/NWS
    context within the same sentence-like block, not merely somewhere in
    a globally oriented script. Other ambiguous codes remain unchanged.
    """
    expanded, left_ambiguous = [], []
    def replace(m):
        zone = m.group("zone").upper()
        reading = GLOBAL_ZONES.get(zone) or US_ZONES.get(zone)
        if zone in LOCAL_ZONES:
            # Look only inside a narrow local weather or NWS statement,
            # never use "San Antonio" from the opening paragraphs.
            prefix = text[max(0, m.start() - 270):m.start()]
            # Bound to a single topic block. A weather or NWS notice may
            # contain multiple sentences, hence look for weather anchors
            # in the trailing 270 chars, excluding unrelated recent topics.
            nearest = max(
                prefix.lower().rfind("and now, a look at the weather"),
                prefix.lower().rfind("national weather service"),
                prefix.lower().rfind("before the world news, an important local weather"),
            )
            local = nearest >= 0 or (
                "san antonio" in prefix.lower()
                and any(term in prefix.lower()
                        for term in ("forecast", "weather", "warning", "alert"))
            )
            if local:
                reading = LOCAL_ZONES[zone]
        if not reading:
            left_ambiguous.append(zone)
            return m.group(0)
        expanded.append(zone)
        return m.group("clock") + " " + reading
    return CLOCK_ZONE.sub(replace, text), expanded, left_ambiguous


def prepare(script, *, rules=None, san_antonio_mode=None):
    """Return TTS-only speech text, plus review-only metadata.

    The original script is never mutated. Known pronunciations are
    automatically applied as plain text aliases, no unsupported phoneme
    tags or SSML scripts are injected by the glossary.
    """
    if not isinstance(script, str):
        raise ValueError("Pronunciation input must be a string")
    pairs = load_glossary() if rules is None else list(rules)
    names, applied = _replace_names(script, pairs)
    mode = (os.getenv("FIRST_LIGHT_SAN_ANTONIO_PRONUNCIATION", "guided")
            if san_antonio_mode is None else san_antonio_mode)
    weather_names, local_alias_applied = local_city_pronunciation(names, mode)
    spoken, zones, ambiguous = _replace_clock_zones(weather_names)
    return spoken, {
        "san_antonio_weather_alias_applied": local_alias_applied,
        "san_antonio_mode": mode,
        "explicit_city_or_name_rules_applied": applied,
        "expanded_time_zone_codes": zones,
        "unresolved_time_zone_codes": sorted(set(ambiguous)),
        "source_transcript_unchanged": True,
        "human_listening_review_required": True,
    }
