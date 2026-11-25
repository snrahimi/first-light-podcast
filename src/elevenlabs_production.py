"""First Light production narrator: ElevenLabs Brian, then Daniel only on eligible faults.

Free plan: noncommercial use with attribution, limited monthly credits.
The pair of classic Default voices retires 2026-12-31. Neither custom
Voice Library IDs nor Gemini Charon is a silent substitute.

Fail closed before publication when audio is incomplete, account credits
are insufficient, or both voices are unavailable. All API error output
is reduced to HTTP status and a category, never logged verbatim.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
from pathlib import Path
import subprocess

import requests

LOG = logging.getLogger("firstlight")
URL = "https://api.elevenlabs.io/v1/text-to-speech/"
SUBSCRIPTION_URL = "https://api.elevenlabs.io/v1/user/subscription"
MODEL = "eleven_flash_v2_5"
OUTPUT_FORMAT = "mp3_44100_128"
VOICE_ORDER = (
    ("Brian", "nPczCjzI2devNBz1zQrb"),
    ("Daniel", "onwK4e9ZLuTAKqWW03F9"),
)
# Conservative, account-agnostic upper bound to prevent runaway charges.
MAX_SCRIPT_CHARS = 8000
MAX_AUDIO_BYTES = 15_000_000
MIN_RAW_AUDIO_BYTES = 60_000
# Flash may cost 0.5-1 credit per character, plan dependent. Use the
# *higher* estimate for preflight rather than assuming any discount.
MAX_EPISODE_CREDIT_BUDGET = 8000

# Conservative per-request delivery presets. Compared with the working
# auditions, Brian gets slightly more dynamic phrasing. Speed stays neutral;
# changing it further requires a reviewed listening test.
VOICE_SETTINGS = {
    "Brian": {
        "stability": 0.58,
        "similarity_boost": 0.78,
        "style": 0.0,
        "speed": 1.0,
        "use_speaker_boost": True,
    },
    "Daniel": {
        "stability": 0.64,
        "similarity_boost": 0.78,
        "style": 0.0,
        "speed": 1.0,
        "use_speaker_boost": True,
    },
}

# Flash v2.5 supports short SSML break tags. Put them only at producer-
# generated section transitions; never inject sound effects, fake voices,
# interview cues, or stage directions into the transcript.
DELIVERY_PAUSES = (
    ("We begin with the leading world developments.", "0.4"),
    ("Elsewhere around the world.", "0.4"),
    ("Now, business and markets.", "0.5"),
    ("And in technology and cybersecurity.", "0.35"),
    ("Now let's turn to business, science and technology.", "0.5"),
    ("And now, a look at the weather in San Antonio.", "0.65"),
    ("For developments and corrections, consult", "0.45"),
    ("That is First Light: World Report.", "0.45"),
    ("That's First Light: World Report.", "0.45"),
)


def delivery_text(spoken_script):
    """Add restrained prosodic pauses without changing any spoken words.

    Reversing the inserted tags and collapsing whitespace must produce
    the exact approved transcript text. All tags count toward API budget.
    """
    if not isinstance(spoken_script, str):
        raise NarratorFailure("narration script is not text")
    # Script is source-gated already; still reject user/source-supplied markup
    # that might be interpreted as instructions by the voice engine.
    if re.search(r"<\s*/?\s*break\b", spoken_script, re.I):
        raise NarratorFailure("untrusted speech markup in narration script")
    result = spoken_script.strip()
    for marker, seconds in DELIVERY_PAUSES:
        boundary = re.compile(
            r"(?<=[.!?])\s+(?=" + re.escape(marker) + r")",
            flags=re.I,
        )
        result = boundary.sub(
            lambda match: f' <break time="{seconds}s" /> ',
            result, count=1,
        )
    if len(result) > MAX_SCRIPT_CHARS:
        raise NarratorFailure("prepared narration exceeds TTS character cap")
    return result


class NarratorFailure(RuntimeError):
    """Safe failure reason and whether a second voice may help."""

    def __init__(self, category, *, can_use_backup=False):
        self.category = category
        self.can_use_backup = can_use_backup
        super().__init__(category)


def _credit_preflight(api_key, length, *, get=requests.get):
    """Check subscription credit headroom before each synthesis request.

    If metadata access or quotas are unavailable, fail instead of issuing
    an unbounded billable request. Never print account data or raw JSON.
    """
    if not 1 <= length <= MAX_SCRIPT_CHARS:
        raise NarratorFailure("script outside capped TTS length")
    if length > MAX_EPISODE_CREDIT_BUDGET:
        raise NarratorFailure("script exceeds single-episode credit budget")
    try:
        res = get(
            SUBSCRIPTION_URL,
            headers={"xi-api-key": api_key, "Accept": "application/json"},
            timeout=(8, 15),
            allow_redirects=False,
        )
        if res.status_code != 200:
            raise NarratorFailure(
                f"credit metadata unavailable (HTTP {res.status_code})"
            )
        data = res.json()
        if not isinstance(data, dict):
            raise ValueError("metadata is not object")
        count, limit = data.get("character_count"), data.get("character_limit")
        if type(count) is not int or type(limit) is not int or count < 0:
            raise ValueError("credit counters unavailable")
        if limit < 0:
            raise ValueError("credit limit unavailable")
        remaining = max(0, limit - count)
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise NarratorFailure("could not verify remaining TTS credits") from None
    # One credit per character is conservative for Flash v2.5.
    if remaining < length:
        raise NarratorFailure(
            "insufficient verified credits for complete narration"
        )
    LOG.info(
        "ElevenLabs preflight confirmed script fits account headroom "
        "(conservative 1 credit/character ceiling); no charges yet"
    )


def _speak(script, name, voice_id, key, *, post=requests.post):
    """One chargeable request per voice, never a hidden automatic retry."""
    try:
        res = post(
            URL + voice_id,
            headers={
                "xi-api-key": key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            params={"output_format": OUTPUT_FORMAT},
            json={
                "text": script,
                "model_id": MODEL,
                "voice_settings": dict(VOICE_SETTINGS[name]),
            },
            timeout=(12, 240),
            allow_redirects=False,
        )
    except (requests.Timeout, requests.ConnectionError):
        raise NarratorFailure(
            "temporary TTS network failure",
            can_use_backup=True,
        ) from None
    except requests.RequestException:
        raise NarratorFailure("TTS HTTP client failure") from None

    status = res.status_code
    if status != 200:
        if status in (401, 402, 403, 429):
            raise NarratorFailure(
                f"account, plan or quota restriction (HTTP {status})"
            )
        if status in (408, 500, 502, 503, 504):
            raise NarratorFailure(
                f"temporary TTS service failure (HTTP {status})",
                can_use_backup=True,
            )
        if status == 404:
            raise NarratorFailure(
                f"requested TTS voice unavailable (HTTP {status})",
                can_use_backup=True,
            )
        raise NarratorFailure(f"TTS request rejected (HTTP {status})")

    audio = res.content
    if str(res.headers.get("Content-Type", "")).lower().split(";")[0] not in (
        "audio/mpeg", "audio/mp3", "application/octet-stream"
    ):
        raise NarratorFailure(
            "provider returned unexpected audio encoding",
            can_use_backup=True,
        )
    if not MIN_RAW_AUDIO_BYTES <= len(audio) <= MAX_AUDIO_BYTES:
        raise NarratorFailure(
            "provider returned incomplete or oversized audio",
            can_use_backup=True,
        )
    if not (
        audio.startswith(b"ID3")
        or (len(audio) > 2 and audio[0] == 0xff
            and audio[1] & 0xe0 == 0xe0)
    ):
        raise NarratorFailure(
            "provider returned unrecognized MP3",
            can_use_backup=True,
        )
    return audio


def _verify_audio(path):
    """Reject corrupt, partial, or implausible raw/normalized recordings."""
    done = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration,bit_rate:stream=codec_name",
         "-of", "json", str(path)],
        check=True, capture_output=True, text=True, timeout=30,
    )
    data = json.loads(done.stdout)
    duration = float(data["format"]["duration"])
    if not any(v.get("codec_name") == "mp3"
               for v in data.get("streams", [])):
        raise ValueError("voice clip has no MP3 stream")
    if not 160 <= duration <= 600:
        raise ValueError("voice clip duration is implausible")
    return duration


def synthesize(script, destination, *, get=requests.get,
               post=requests.post, verify=_verify_audio):
    """Produce one fully verified, normalized MP3 using Brian or Daniel.

    A failure that indicates shared credentials, credits, rate limits, or
    plan restrictions must NOT invoke Daniel, since that would waste credits.
    A temporary voice/request failure allows exactly one backup attempt.
    Both voices use the same script and model; segments cannot be mixed.
    """
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise NarratorFailure("ELEVENLABS_API_KEY is not configured")
    if not isinstance(script, str) or not script.strip():
        raise NarratorFailure("narration script is empty")
    if len(script) > MAX_SCRIPT_CHARS:
        raise NarratorFailure("script exceeds 8000-character TTS cap")
    spoken = delivery_text(script)
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    raw = output.with_name(output.stem + ".tts-raw.partial.mp3")
    converted = output.with_name(output.stem + ".tts-normalized.partial.mp3")
    selected = None
    try:
        for index, (name, vid) in enumerate(VOICE_ORDER):
            raw.unlink(missing_ok=True)
            converted.unlink(missing_ok=True)
            try:
                _credit_preflight(key, len(spoken), get=get)
                raw.write_bytes(_speak(spoken, name, vid, key, post=post))
                verify(raw)
                subprocess.run([
                    "ffmpeg", "-nostdin", "-y", "-hide_banner",
                    "-loglevel", "error",
                    "-i", str(raw), "-af",
                    "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-codec:a", "libmp3lame", "-ar", "44100",
                    "-b:a", "192k", str(converted),
                ], check=True, timeout=240)
                verify(converted)
                if converted.stat().st_size < 65_000:
                    raise ValueError("normalized MP3 unexpectedly small")
                converted.replace(output)
                selected = name
                break
            except NarratorFailure as exc:
                if index == 0 and exc.can_use_backup:
                    LOG.warning(
                        "Brian TTS unavailable (%s); attempting Daniel once",
                        exc.category,
                    )
                    continue
                raise NarratorFailure(
                    f"{name} narration failed: {exc.category}"
                ) from None
            except (ValueError, KeyError, json.JSONDecodeError,
                    OSError, subprocess.CalledProcessError,
                    subprocess.TimeoutExpired) as exc:
                if index == 0:
                    LOG.warning(
                        "Brian audio validation/encoding failed (%s); "
                        "attempting Daniel once",
                        type(exc).__name__,
                    )
                    continue
                raise NarratorFailure(
                    f"Daniel audio failed validation: {type(exc).__name__}"
                ) from None
        if selected is None or not output.exists():
            raise NarratorFailure("Brian and Daniel unavailable")
        LOG.info("Verified narrator: ElevenLabs %s", selected)
        return "ElevenLabs " + selected
    finally:
        raw.unlink(missing_ok=True)
        converted.unlink(missing_ok=True)
