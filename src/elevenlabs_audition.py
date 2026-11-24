"""Single-call, manual-only ElevenLabs sample for noncommercial voice comparison.

This is NOT wired into the daily producer or public podcast feeds.
Only invoke with two repository secrets from the manual audition workflow.
Do not log, print, or persist the credentials.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess

import requests

MODEL = "eleven_flash_v2_5"
OUTPUT_FORMAT = "mp3_44100_128"
MAX_CHARACTERS = 820
MAX_AUDIO_BYTES = 3_000_000

# Original demonstration text; no actual news events are asserted.
SAMPLE = (
    "Good morning, San Antonio. This is First Light: World Report, "
    "a calm, clear look at the stories shaping our world. "
    "Ahead, we will explore international diplomacy, global markets, "
    "advances in science, and the latest developments in cybersecurity. "
    "Our reporting separates official statements from claims attributed "
    "to publishers, and we note when important details are still uncertain. "
    "From Washington to London, from Tokyo to Nairobi, each story "
    "deserves context, care, and an easy-to-follow explanation. "
    "We will also keep an eye on local weather before your day gets underway. "
    "Whether you're making coffee, heading into work, or starting "
    "the morning on the road, thank you for joining us. "
    "This is First Light. The world, before your day."
)


def audition_payload(text=SAMPLE):
    """Reject long or empty text *before* any billable request."""
    if not isinstance(text, str) or not 90 <= len(text.split()) <= 160:
        raise ValueError("Audition must be a 90-160-word original script")
    if len(text) > MAX_CHARACTERS:
        raise ValueError("Audition exceeds strict 820-character budget")
    return {
        "text": text,
        "model_id": MODEL,
        "voice_settings": {
            "stability": 0.62,
            "similarity_boost": 0.78,
        },
    }


def request_sample(api_key, voice_id, *, post=requests.post):
    """Exactly one API request. Fail closed on errors, quotas and audio issues.

    The request is limited by script length, contains no sensitive content,
    does not follow redirects, and will not retry a rejected paid request.
    """
    if not api_key or not voice_id:
        raise RuntimeError("Both ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID are required")
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", voice_id):
        raise ValueError("ELEVENLABS_VOICE_ID has an invalid format")
    payload = audition_payload()
    response = post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        params={"output_format": OUTPUT_FORMAT},
        json=payload,
        timeout=(10, 85),
        allow_redirects=False,
    )
    if response.status_code != 200:
        # Do not log the HTTP response body: it may contain account metadata.
        raise RuntimeError(
            f"ElevenLabs audition returned HTTP {response.status_code}; "
            "no retry and no production change"
        )
    content_type = str(response.headers.get("Content-Type", "")).lower()
    audio = response.content
    if not content_type.startswith("audio/"):
        raise RuntimeError("ElevenLabs returned a non-audio response")
    if not 50_000 <= len(audio) <= MAX_AUDIO_BYTES:
        raise RuntimeError("ElevenLabs response has unexpected audio size")
    if not (audio.startswith(b"ID3") or (
        len(audio) > 2 and audio[0] == 0xff and audio[1] & 0xe0 == 0xe0
    )):
        raise RuntimeError("ElevenLabs response is not recognized MP3")
    return audio


def inspect_mp3(path):
    """Use ffprobe to check output duration and codec before retaining it."""
    done = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_name", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, timeout=15,
    )
    data = json.loads(done.stdout)
    if not any(stream.get("codec_name") == "mp3"
               for stream in data.get("streams", [])):
        raise RuntimeError("Audition output is not an MP3")
    duration = float(data["format"]["duration"])
    if not 20 <= duration <= 90:
        raise RuntimeError("Audition audio duration outside 20-90 seconds")
    return round(duration, 1)


def main():
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    voice = os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
    # Validate preconditions before making any billable request.
    audition_payload()
    if not key or not voice:
        raise RuntimeError("Configure both ElevenLabs repository secrets first")
    output = Path("voice-audition")
    output.mkdir(exist_ok=True)
    audio = request_sample(key, voice)
    target = output / "first-light-elevenlabs-free-test.mp3"
    temp = output / "audition.partial"
    try:
        temp.write_bytes(audio)
        duration = inspect_mp3(temp)
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    (output / "script.txt").write_text(SAMPLE + "\n", encoding="utf-8")
    (output / "attribution.txt").write_text(
        "Generated with ElevenLabs. Noncommercial voice evaluation only.\n",
        encoding="utf-8",
    )
    (output / "metadata.json").write_text(
        json.dumps({
            "purpose": "Noncommercial, manual-only voice comparison",
            "production_changed": False,
            "model": MODEL,
            "audio_format": OUTPUT_FORMAT,
            "sample_characters": len(SAMPLE),
            "sample_words": len(SAMPLE.split()),
            "audio_seconds": duration,
            "api_calls": 1,
            "note": "Free-tier use requires attribution; no public release.",
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Voice sample verified: {duration:.1f}s; "
        "one ElevenLabs request; audition artifact only; Charon unchanged."
    )


if __name__ == "__main__":
    main()
