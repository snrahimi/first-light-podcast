#!/usr/bin/env python3
"""One-time First Light narrator audition: Gemini Charon, Kokoro Adam, Kokoro Heart.

Isolated from the scheduled podcast. Creates separate public MP3 previews
for listening; does not update the active narrator or the live podcast feed.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import subprocess
import wave
from pathlib import Path

import requests

LOG = logging.getLogger("voice-audition")
OUT = Path("voice-samples")
TAG = "first-light-voice-audition-v1"
BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/"
SAMPLE = (
    "Good morning, San Antonio. You're listening to First Light: World Report. "
    "Today, we take you across the globe for the headlines shaping the day, "
    "from international developments to business, science, and technology. "
    "We'll finish with a quick look at your local weather. "
    "This is a preview of our new morning radio narrator. "
    "The world is already moving. Let's bring it into focus."
)


def download_asset(url: str, destination: Path, minimum: int):
    if destination.is_file() and destination.stat().st_size >= minimum:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(destination.name + ".partial")
    with requests.get(url, timeout=(12, 100), stream=True) as response:
        response.raise_for_status()
        with temp.open("wb") as handle:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    handle.write(chunk)
    if temp.stat().st_size < minimum:
        raise RuntimeError("Voice model download incomplete")
    temp.replace(destination)


def mp3_from_wav(wav: Path, mp3: Path):
    subprocess.run([
        "ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(wav),
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-codec:a", "libmp3lame", "-ar", "44100", "-b:a", "192k",
        str(mp3),
    ], check=True, timeout=90)
    if mp3.stat().st_size < 65_000:
        raise RuntimeError("Produced MP3 is unexpectedly small")


def generate_kokoro_previews():
    import numpy as np
    import soundfile as sf
    from kokoro_onnx import Kokoro

    cache = Path.home() / ".cache/first-light/kokoro"
    model = cache / "kokoro-v1.0.fp16.onnx"
    voices = cache / "voices-v1.0.bin"
    download_asset(BASE + model.name, model, 120_000_000)
    download_asset(BASE + voices.name, voices, 10_000_000)
    kokoro = Kokoro(str(model), str(voices))
    output = {}

    for voice, label in [("am_adam", "kokoro-adam"), ("af_heart", "kokoro-heart")]:
        try:
            LOG.info("Synthesizing Kokoro FP16 preview using %s", voice)
            samples, rate = kokoro.create(SAMPLE, voice=voice, speed=1.07, lang="en-us")
            wav_path = OUT / (label + ".wav")
            sf.write(str(wav_path), np.asarray(samples, dtype=np.float32), rate)
            mp3_path = OUT / (label + ".mp3")
            mp3_from_wav(wav_path, mp3_path)
            wav_path.unlink()
            output[label] = "ready"
            LOG.info("Finished preview %s", label)
        except Exception as exc:
            output[label] = "unavailable: " + type(exc).__name__
            LOG.warning("Could not make %s: %s", label, type(exc).__name__)
    return output


def generate_gemini_preview():
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return "unavailable: GEMINI_API_KEY secret is missing"
    # Official Gemini Interactions API response format for 3.8 TTS:
    # result.steps[].content[] with type=audio, base64-encoded WAV data.
    payload = {
        "model": "gemini-3.8-flash-tts",
        "input": [{
            "type": "user_input",
            "content": [{
                "type": "text",
                "text": SAMPLE,
                "annotations": [{
                    "type": "speech_metadata",
                    "style": "Warm, natural, clear American morning news presenter. Calm confidence, relaxed pacing, careful articulation. No dramatic performance."
                }]
            }]
        }],
        "response_format": {"type": "audio"},
        "generation_config": {
            "speech_config": [{"voice": "Charon"}]
        }
    }
    try:
        LOG.info("Requesting single Gemini 3.8 Flash TTS voice preview")
        result = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json=payload, timeout=(12, 135)
        )
        if result.status_code != 200:
            LOG.warning("Gemini TTS returned HTTP %s (no additional API requests)", result.status_code)
            return "unavailable: Gemini TTS HTTP " + str(result.status_code)
        obj = result.json()
        content = [
            part for step in obj.get("steps", [])
            if step.get("type") == "model_output"
            for part in step.get("content", []) or []
            if part.get("type") == "audio" and part.get("data")
        ]
        if not content:
            return "unavailable: Gemini returned no audio in the response"
        audio = base64.b64decode(content[-1]["data"])
        if not audio.startswith(b"RIFF"):
            return "unavailable: Gemini returned unexpected audio format"
        wav_path = OUT / "gemini-charon.wav"
        wav_path.write_bytes(audio)
        with wave.open(str(wav_path), "rb") as handle:
            if handle.getnchannels() != 1 or handle.getnframes() < 10_000:
                return "unavailable: Gemini audio was incomplete"
        mp3_path = OUT / "gemini-charon.mp3"
        mp3_from_wav(wav_path, mp3_path)
        wav_path.unlink()
        LOG.info("Finished Gemini Charon preview")
        return "ready"
    except (requests.RequestException, ValueError, KeyError, OSError,
            subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        LOG.warning("Gemini preview failed: %s", type(exc).__name__)
        return "unavailable: " + type(exc).__name__


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    status = generate_kokoro_previews()
    status["gemini-charon"] = generate_gemini_preview()
    lines = [
        "FIRST LIGHT: WORLD REPORT - NARRATOR AUDITION",
        "",
        "These samples all read the same original First Light intro.",
        "No news episode or scheduled narrator was changed.",
        "",
        "Available MP3 files:",
    ]
    for label, result in status.items():
        lines.append(f"- {label}: {result}")
    lines.extend([
        "", "Gemini: Gemini 3.8 Flash TTS, Charon voice, subject to free-tier API availability.",
        "Kokoro: open FP16 model with Adam and Heart voices.",
        "All audio encoded at 192 kbps MP3 and loudness-normalized.",
        "", "Tell ChatGPT which narrator you prefer before production is changed.",
    ])
    (OUT / "README.txt").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    LOG.info("Voice sample status: %s", json.dumps(status))
    # Even if Gemini is blocked by account plan, publish the working alternatives.
    if not any(value == "ready" for value in status.values()):
        raise RuntimeError("No narrator samples could be generated")
    token = os.getenv("GH_TOKEN", "").strip()
    if not token:
        raise RuntimeError("GH_TOKEN is missing")
    audio_files = sorted(str(p) for p in OUT.glob("*.mp3"))
    cmd_base = ["gh", "release"]
    exists = subprocess.run(cmd_base + ["view", TAG], capture_output=True).returncode == 0
    if exists:
        command = cmd_base + ["upload", TAG] + audio_files + ["--clobber"]
        subprocess.run(command, check=True, timeout=120)
        subprocess.run(cmd_base + ["edit", TAG, "--notes-file", str(OUT / "README.txt")],
                       check=True, timeout=60)
    else:
        command = cmd_base + ["create", TAG] + audio_files + [
            "--title", "First Light: Three narrator previews",
            "--notes-file", str(OUT / "README.txt"), "--latest=false",
        ]
        subprocess.run(command, check=True, timeout=120)
    LOG.info("Preview release published to https://github.com/%s/releases/tag/%s",
             os.getenv("GITHUB_REPOSITORY", ""), TAG)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
