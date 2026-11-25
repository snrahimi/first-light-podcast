"""No-TTS upgrade of a published First Light GitHub Pages transcript.

Only index.html is reformatted. Download the *existing public* episode,
RSS, cover, audit, health and metadata files and re-deploy their bytes
unchanged. Never synthesize audio, regenerate news or replace GitHub Releases.
This manual repair runs in the same concurrency group as daily production.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

from . import transcript_display

# All files that the daily producer currently writes in SITE/.
PRESERVE = (
    "latest.mp3",
    "feed.xml",
    "latest.json",
    "cover.png",
    "evidence.json",
    "health.json",
    "health.html",
    "memory.json",
)
MAX_FILE_BYTES = {
    "index.html": 2_000_000,
    "latest.mp3": 30_000_000,
    "feed.xml": 2_000_000,
    "latest.json": 500_000,
    "cover.png": 8_000_000,
    "evidence.json": 8_000_000,
    "health.json": 2_000_000,
    "health.html": 2_000_000,
    "memory.json": 2_000_000,
}


def published_base():
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Expected GitHub owner/repository")
    owner, name = repo.split("/")
    if not name.lower().endswith(".github.io"):
        return f"https://{owner.lower()}.github.io/{name}/"
    return f"https://{owner.lower()}.github.io/"


def fetch_published(name, base=None):
    if name not in MAX_FILE_BYTES:
        raise ValueError("Only explicitly allowlisted website files may be fetched")
    url = (base or published_base()).rstrip("/") + "/" + name
    request = Request(url, headers={
        "User-Agent": "FirstLightTranscriptLayoutRefresh/1.0",
        "Accept": "*/*",
    })
    with urlopen(request, timeout=35) as response:
        data = response.read(MAX_FILE_BYTES[name] + 1)
    if not data or len(data) > MAX_FILE_BYTES[name]:
        raise RuntimeError("Published file missing, empty or unexpectedly large: " + name)
    return data


def refresh(destination, *, fetch=fetch_published):
    """Fail closed rather than publish an incomplete/mismatched Pages site."""
    target = Path(destination)
    if target.exists() and any(target.iterdir()):
        raise RuntimeError("Output directory must be empty")
    raw = {name: fetch(name) for name in ("index.html", *PRESERVE)}
    old_html = raw["index.html"].decode("utf-8")
    metadata = json.loads(raw["latest.json"].decode("utf-8"))
    episode_date = metadata.get("date")
    if not isinstance(episode_date, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", episode_date
    ):
        raise RuntimeError("Cannot identify current published episode date")
    if ('latest.mp3?date=' + episode_date) not in old_html:
        raise RuntimeError("Audio on published index does not match latest.json date")
    if len(raw["latest.mp3"]) < 100_000:
        raise RuntimeError("Existing audio is suspiciously small; cannot redeploy")
    if not raw["feed.xml"].lstrip().startswith(b"<?xml"):
        raise RuntimeError("Published RSS does not begin with XML declaration")
    revised = transcript_display.reformat_existing_page(old_html)
    target.mkdir(parents=True, exist_ok=True)
    for name, data in raw.items():
        (target / name).write_bytes(
            revised.encode("utf-8") if name == "index.html" else data
        )
    (target / ".nojekyll").write_bytes(b"")
    for name in PRESERVE:
        if hashlib.sha256((target / name).read_bytes()).digest() != \
                hashlib.sha256(raw[name]).digest():
            raise RuntimeError("Preserved published file was unexpectedly changed")
    return {
        "episode_date": episode_date,
        "layout_updated": revised != old_html,
        "preserved_files": len(PRESERVE),
        "voice_api_requests": 0,
    }


def main():
    result = refresh("site")
    print(
        "Transcript layout refresh: "
        f"episode={result['episode_date']}, "
        f"layout_updated={str(result['layout_updated']).lower()}, "
        f"published_files_preserved={result['preserved_files']}, "
        "ElevenLabs/Gemini calls=0."
    )


if __name__ == "__main__":
    main()
