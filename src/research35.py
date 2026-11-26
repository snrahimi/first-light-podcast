"""Newsroom 3.5: conservative, explainable same-event RSS matching.

This is a lexical discovery filter, never independent corroboration.
It must reject unrelated announcements sharing only countries, agencies,
or generic news vocabulary. Only previously allowlisted source links are
eligible for attachment; this function never fetches any content.
"""
from __future__ import annotations

from difflib import SequenceMatcher

if __package__:
    from . import editorial
else:
    import editorial

# Modest morphology and newsroom terms, not unreviewed place-name aliases.
ALIASES = {
    "sanctions": "sanction", "sanctioned": "sanction",
    "banking": "bank", "banks": "bank",
    "tariffs": "tariff", "levies": "tariff", "levy": "tariff",
    "elections": "election", "votes": "vote",
    "attacks": "attack", "attacked": "attack",
    "missiles": "missile", "vessels": "vessel", "ships": "vessel",
    "libyan": "libya", "chinese": "china",
    "evacuations": "evacuation", "rescued": "rescue",
    "hostages": "hostage", "storms": "storm",
    "agreements": "agreement", "launches": "launch",
    "reports": "report", "results": "result",
}
EVENTS = frozenset(("""
sanction tariff election vote attack missile flood storm evacuation
rescue hostage ceasefire war treaty agreement summit earthquake outbreak
breach cybersecurity launch research ruling decision negotiation talks
trade strike
""").split())
# Terms which make two headlines *look* related but do not establish
# that they describe the same event or reporting.
GENERIC = frozenset(("""
announces announced say says detail details review reviewing officials
official government governments minister ministers country countries
leader leaders international global regional local meeting meetings
security council committee report result source press new latest news
world update updates plans says top major
""").split())
INCOMPATIBLE_RATE = (
    frozenset(("raise", "raises", "hike", "hikes", "increases")),
    frozenset(("cut", "cuts", "lower", "lowers", "reduces")),
    frozenset(("hold", "holds", "steady", "unchanged", "keeps")),
)
INCOMPATIBLE_TARIFF = (
    frozenset(("impose", "imposes", "introduces", "announces")),
    frozenset(("lift", "lifts", "remove", "removes", "ends")),
)


def tokens(value):
    return {ALIASES.get(word, word) for word in editorial.key_tokens(value)}


def _opposed_actions(a, b):
    """Obvious incompatible outcomes should not silently merge as one event."""
    for groups in (INCOMPATIBLE_RATE, INCOMPATIBLE_TARIFF):
        if any((a & family and b & alternative)
               for family in groups for alternative in groups
               if family is not alternative):
            # Only reject when both titles discuss the same outcome class.
            if groups is INCOMPATIBLE_RATE and not (
                a & {"rate", "rates", "interest"} and
                b & {"rate", "rates", "interest"}
            ):
                continue
            if groups is INCOMPATIBLE_TARIFF and not (
                "tariff" in a and "tariff" in b
            ):
                continue
            return True
    return False


def match_score(lead_title, other_title, other_summary=""):
    """Conservative same-event signal, 0=unmatched; not a truth claim.

    Requires a concrete shared event AND two shared, nongeneric subject
    identifiers. A strong near-identical match with four distinct subject
    tokens is allowed even when the event vocabulary differs. Summary
    words may help distinguish cases but cannot rescue a country-only
    or agency-only headline match.
    """
    a, b = tokens(lead_title), tokens(other_title)
    if not a or not b:
        return 0.0
    if _opposed_actions(a, b):
        return 0.0
    shared = a & b
    anchor = shared - EVENTS - GENERIC
    events = shared & EVENTS
    if not events and len(anchor) < 4:
        return 0.0
    if len(anchor) < 2:
        return 0.0
    union = a | b
    overlap = len(shared) / max(1, len(union))
    # Strong noun overlap without a shared event is allowed only for
    # clearly near-identical wording, not country/organization mentions.
    if not events and (len(anchor) < 4 or overlap < .62):
        return 0.0
    # Event+subject anchors represent a candidate event, not verification.
    summary = tokens(other_summary)
    supporting = len((a & summary) - shared - EVENTS - GENERIC)
    density = .08 * min(4, len(anchor)) + .06 * min(2, len(events))
    bonus = .03 if supporting else 0
    return round(min(.96, .47 + density + .16 * overlap + bonus), 3)


def review_match(lead_title, other_title, other_summary=""):
    score = match_score(lead_title, other_title, other_summary)
    return {
        "same_event_candidate": score > 0,
        "lexical_confidence": score,
        "independently_corrobated": False,
        "method": "event and multiple non-generic subject anchors",
    }
