"""Test the configured ElevenLabs narrator without an OpenAI API call."""
import os
from pathlib import Path

import requests

key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
voice = os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
if not key:
    raise SystemExit("Missing ELEVENLABS_API_KEY GitHub secret")
if not voice:
    raise SystemExit("Missing ELEVENLABS_VOICE_ID GitHub secret")

script = (
    "Good morning, San Antonio. This is First Light: World Report. "
    "Your daily window onto the world, from the biggest international headlines "
    "to business, science, technology, and the weather right here at home. "
    "The world is already moving, and we're here to help you start the day informed. "
    "This is a narrator test. Your full daily briefing will follow "
    "once the news research service is active. "
    "I'm glad you're here. Now, let's begin."
)

resp = requests.post(
    f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
    params={"output_format": "mp3_44100_128"},
    headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
    json={"model_id": "eleven_flash_v2_5", "text": script,
          "voice_settings": {"stability": 0.62, "similarity_boost": 0.75,
                             "style": 0, "use_speaker_boost": True}},
    timeout=120,
)
if resp.status_code != 200:
    try:
        reason = resp.json().get("detail", {}).get("message") or resp.json().get("detail")
    except ValueError:
        reason = "unknown"
    raise SystemExit(f"ElevenLabs rejected the request: HTTP {resp.status_code}: {str(reason)[:400]}")
if not resp.content.startswith((b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
    raise SystemExit("ElevenLabs response did not look like MP3")
if len(resp.content) < 10_000:
    raise SystemExit("Audio response was unusually short")
out = Path("work/narrator-preview.mp3")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(resp.content)
print(f"Voice test passed. Created MP3 sample of {len(resp.content)} bytes.")
