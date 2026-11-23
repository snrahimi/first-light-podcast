#!/usr/bin/env python3
"""First Light: World Report daily podcast producer.

OpenAI web search/news script + live weather + ElevenLabs audio + GitHub Releases/Pages.
Both episode hosting and source notes are PUBLIC. Never print secrets.
"""
from __future__ import annotations

import email.utils
import html
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

LOG = logging.getLogger("firstlight")
TZ = ZoneInfo("America/Chicago")
ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
SITE = ROOT / "site"
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-terra")
TITLE = "First Light: World Report"

ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
ET.register_namespace("atom", "http://www.w3.org/2005/Atom")


def required(key):
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError("Missing environment variable: " + key)
    return value


def repo_info():
    repo = required("GITHUB_REPOSITORY")
    if repo.count("/") != 1:
        raise ValueError("Expected owner/repository for GITHUB_REPOSITORY")
    return repo.split("/")


def public_base():
    custom = os.getenv("FEED_BASE_URL", "").strip()
    if custom:
        if not custom.startswith("https://"):
            raise ValueError("FEED_BASE_URL must use https")
        return custom.rstrip("/")
    owner, repo = repo_info()
    suffix = "" if repo.lower() == owner.lower() + ".github.io" else "/" + repo
    return "https://" + owner.lower() + ".github.io" + suffix


def http_json(url, *, params=None, headers=None, timeout=20):
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()


WMO = {
    0: "clear", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "rime fog", 51: "light drizzle", 53: "drizzle",
    55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow",
    80: "isolated showers", 81: "rain showers", 82: "heavy showers",
    95: "thunderstorms", 96: "thunderstorms with hail", 99: "severe thunderstorms"
}


def fetch_weather(now):
    day = now.date().isoformat()
    data = http_json(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": 29.4241, "longitude": -98.4936,
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
            "hourly": "precipitation_probability",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
            "timezone": "America/Chicago", "forecast_days": 2
        }
    )
    if data["daily"]["time"][0] != day:
        raise RuntimeError("Weather date mismatch, not publishing")
    hourly = data["hourly"]
    periods = [
        {"hour_local": hour[-5:], "rain_percent": chance}
        for hour, chance in zip(hourly["time"], hourly["precipitation_probability"])
        if hour.startswith(day) and chance is not None
    ]
    periods.sort(key=lambda p: p["rain_percent"], reverse=True)
    alert_status = "not verified"
    alerts = []
    try:
        nws = http_json(
            "https://api.weather.gov/alerts/active",
            params={"point": "29.4241,-98.4936"},
            headers={
                "Accept": "application/geo+json",
                "User-Agent": "FirstLightPodcast/1.0 (daily podcast)"
            },
            timeout=12
        )
        alert_status = "checked"
        alerts = [
            f.get("properties", {}).get("headline", "NWS alert")
            for f in nws.get("features", [])[:5]
        ]
    except (requests.RequestException, KeyError, ValueError) as exc:
        LOG.warning("NWS alert check unavailable: %s", exc)
    return {
        "location": "San Antonio, Texas", "date": day,
        "conditions": WMO.get(data["current"].get("weather_code"), "not available"),
        "temperature_f": data["current"].get("temperature_2m"),
        "feels_like_f": data["current"].get("apparent_temperature"),
        "wind_mph": data["current"].get("wind_speed_10m"),
        "high_f": data["daily"]["temperature_2m_max"][0],
        "low_f": data["daily"]["temperature_2m_min"][0],
        "max_rain_percent": data["daily"]["precipitation_probability_max"][0],
        "peak_rain_chance_hours": periods[:4],
        "nws_alert_check": alert_status, "nws_active_alerts": alerts
    }


def web_sources(response):
    seen, out = set(), []
    for part in response.model_dump().get("output", []):
        for c in part.get("content", []) or []:
            for annotation in c.get("annotations", []) or []:
                if annotation.get("type") == "url_citation":
                    raw = annotation.get("url_citation") or annotation
                    url = raw.get("url", "")
                    if url.startswith("https://") and url not in seen:
                        seen.add(url)
                        out.append({"url": url, "title": raw.get("title") or urlsplit(url).netloc})
        for s in (part.get("action") or {}).get("sources", []) or []:
            if isinstance(s, dict):
                url = s.get("url", "")
                if url.startswith("https://") and url not in seen:
                    seen.add(url)
                    out.append({"url": url, "title": s.get("title") or urlsplit(url).netloc})
    return out[:35]


def news_and_script(client, now, weather):
    stamp = now.strftime("%A, %B %d, %Y at %I:%M %p Central")
    prompt = f"""Search live public web sources and prepare carefully attributed research notes
for a 5 AM daily international news broadcast in San Antonio, Texas, as of {stamp}.
Prioritize the last 24 hours and clearly distinguish new developments from older context.
Use Reuters/AP/BBC/FT and dependable primary sources where appropriate.
Verify dates and key claims against multiple independent sources where feasible.
Find 4–6 important TOP WORLD HEADLINES; then geographically varied AROUND THE WORLD
(Europe, Asia, Middle East, Africa, Americas if substantive developments exist);
BUSINESS AND MARKETS (explicitly distinguish market closes, futures, weekends and holidays;
only quote verifiable, date-stamped index values); SCIENCE AND TECH
(including research, space, AI and cybersecurity); and WHAT TO WATCH TODAY.
Return detailed factual RESEARCH NOTES with citations. Include uncertainty.
Never invent prices, quotes, news, or future events.
"""
    result = client.responses.create(
        model=MODEL,
        reasoning={"effort": "low"},
        tools=[{"type": "web_search", "search_context_size": "high"}],
        include=["web_search_call.action.sources"],
        input=prompt,
        max_output_tokens=5700
    )
    notes = result.output_text.strip()
    sources = web_sources(result)
    if len(notes) < 1200 or len(sources) < 4:
        raise RuntimeError(
            f"Insufficient grounded web research ({len(notes)} characters, "
            f"{len(sources)} linked sources). Refusing to publish."
        )
    script_prompt = f"""Write ONLY the spoken narration of today's First Light: World Report.
Date: {stamp}. Target 1,300-1,650 words, an engaging 10-12 minute single-host
newsroom podcast in natural English. Not a bullet list, no markdown, no URLs and
no unspoken production labels. A calm but energetic opening, seamless transitions,
neutral reportage and helpful context. Sections IN ORDER:
1. Top World Headlines (4-6) 2. Around the World
3. Business and Markets 4. Science and Tech 5. San Antonio Weather
6. What to Watch Today and a concise signoff.
Use ONLY factual claims grounded in the following verified research. No imaginary
stocks, comparisons, source quotations, or developments. Qualify breaking events,
distinguish reporting from speculation, and never add figures not in the notes.
For weather use the live structured weather data instead of news reports.
If NWS alerts were not verified, do not say there are no alerts.
Use Fahrenheit and explain rain timing without inventing certainty.
NEWS RESEARCH:
{notes}
SAN ANTONIO WEATHER:
{json.dumps(weather, ensure_ascii=False)}
"""
    generated = client.responses.create(
        model=MODEL, reasoning={"effort": "low"},
        input=script_prompt, max_output_tokens=4300
    )
    script = re.sub(r"\s+", " ", generated.output_text.strip())
    words = len(script.split())
    if words < 1050 or words > 2000:
        raise RuntimeError(f"Unexpected podcast script length: {words} words")
    if "San Antonio" not in script:
        raise RuntimeError("Weather section missing, refusing to publish")
    return notes, sources, script


def synthesize(script, destination):
    if len(script) > 39000:
        raise RuntimeError("Script exceeds ElevenLabs Flash 2.5 request character limit")
    voice_id = required("ELEVENLABS_VOICE_ID")
    api_key = required("ELEVENLABS_API_KEY")
    url = "https://api.elevenlabs.io/v1/text-to-speech/" + voice_id
    for attempt in range(3):
        try:
            r = requests.post(
                url, params={"output_format": "mp3_44100_128"},
                headers={"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
                json={"text": script, "model_id": "eleven_flash_v2_5",
                      "voice_settings": {"stability": 0.62, "similarity_boost": 0.75,
                                         "style": 0, "use_speaker_boost": True}},
                timeout=240
            )
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep((attempt + 1) * 8)
                continue
            r.raise_for_status()
            if (not r.content.startswith((b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"))
                    or len(r.content) < 80_000):
                raise RuntimeError("Narration response was not a valid-length MP3")
            destination.write_bytes(r.content)
            return
        except requests.Timeout:
            if attempt == 2:
                raise
            time.sleep((attempt + 1) * 8)


def run_gh(*args, check=True):
    return subprocess.run(["gh", *args], text=True, capture_output=True, check=check)


def publish_release(day, mp3, transcript, notes):
    tag = "first-light-" + day
    title = f"{TITLE} | {day}"
    if run_gh("release", "view", tag, check=False).returncode == 0:
        run_gh("release", "upload", tag, str(mp3), str(transcript), "--clobber")
        run_gh("release", "edit", tag, "--title", title, "--notes-file", str(notes))
    else:
        run_gh("release", "create", tag, str(mp3), str(transcript),
               "--title", title, "--notes-file", str(notes), "--latest")


def list_releases(day):
    owner, repo = repo_info()
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + required("GH_TOKEN"),
        "X-GitHub-Api-Version": "2022-11-28"
    }
    for attempt in range(4):
        releases = http_json(f"https://api.github.com/repos/{owner}/{repo}/releases",
                             params={"per_page": 50}, headers=headers)
        eps = [
            r for r in releases
            if re.fullmatch(r"first-light-\d{4}-\d{2}-\d{2}", r.get("tag_name", ""))
            and not r.get("draft")
        ]
        eps.sort(key=lambda r: r["tag_name"], reverse=True)
        if any(r["tag_name"] == "first-light-" + day for r in eps):
            return eps[:30]
        time.sleep(3 + attempt * 3)
    raise RuntimeError("Today's new GitHub Release is not visible in API yet")


def xml_feed(releases, base):
    rss = ET.Element("rss", {"version": "2.0"})
    ch = ET.SubElement(rss, "channel")
    def txt(node, tag, content):
        ET.SubElement(node, tag).text = str(content)
    txt(ch, "title", TITLE)
    txt(ch, "link", base + "/")
    txt(ch, "language", "en-us")
    txt(ch, "description",
        "Daily AI-narrated news from around the world, markets, science, tech and San Antonio weather.")
    txt(ch, "{http://www.itunes.com/dtds/podcast-1.0.dtd}author", "First Light")
    txt(ch, "{http://www.itunes.com/dtds/podcast-1.0.dtd}explicit", "false")
    txt(ch, "{http://www.itunes.com/dtds/podcast-1.0.dtd}category", "News")
    ET.SubElement(ch, "{http://www.itunes.com/dtds/podcast-1.0.dtd}image",
                  {"href": base + "/cover.png"})
    ET.SubElement(ch, "{http://www.w3.org/2005/Atom}link",
                  {"href": base + "/feed.xml", "rel": "self", "type": "application/rss+xml"})
    for release in releases:
        audio = next((a for a in release.get("assets", [])
                      if a.get("name", "").endswith(".mp3")), None)
        if audio is None:
            continue
        item = ET.SubElement(ch, "item")
        day = release["tag_name"].replace("first-light-", "")
        txt(item, "title", f"{TITLE} | {day}")
        txt(item, "link", release.get("html_url", base))
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = release["tag_name"]
        txt(item, "description", "Today's global headlines, markets, science, technology and San Antonio weather. "
            + "Full source links and transcript: " + base + "/")
        txt(item, "{http://www.itunes.com/dtds/podcast-1.0.dtd}explicit", "false")
        date_value = release.get("published_at") or release.get("created_at")
        if date_value:
            dt = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
            txt(item, "pubDate", email.utils.format_datetime(dt))
        ET.SubElement(item, "enclosure", {
            "url": audio["browser_download_url"], "length": str(audio["size"]), "type": "audio/mpeg"
        })
    return ET.ElementTree(rss)


def cover(path):
    size = 1500
    im = Image.new("RGB", (size, size), "#081525")
    d = ImageDraw.Draw(im)
    for y in range(size):
        proximity = max(0, 1 - abs(y - 1050) / 550)
        tone = (int(11 + proximity * 75), int(27 + proximity * 38),
                int(49 + proximity * 22))
        d.line((0, y, size, y), fill=tone)
    d.ellipse((560, 805, 940, 1185), fill="#ffc18b")
    d.rectangle((0, 1090, size, size), fill="#0a182c")
    d.line((105, 1090, 1395, 1090), fill="#ffb884", width=8)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font = (ImageFont.truetype(font_path, 142) if Path(font_path).exists()
            else ImageFont.load_default())
    d.text((92, 130), "FIRST LIGHT", fill="#fff4eb", font=font)
    smaller = (ImageFont.truetype(font_path, 82) if Path(font_path).exists()
               else ImageFont.load_default())
    d.text((105, 340), "WORLD REPORT", fill="#ffc18b", font=smaller)
    d.text((105, 1350), "THE WORLD. BEFORE YOUR DAY.", fill="#ffffff", font=smaller)
    im.save(path, format="PNG")


def web_page(day, sources, transcript):
    links = "".join(
        f'<li><a href="{html.escape(s["url"], quote=True)}" rel="noopener noreferrer">'
        f'{html.escape(s["title"])}</a></li>'
        for s in sources
    )
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>First Light: World Report</title><style>
body{{background:#0a1729;color:#edf2f8;font:18px/1.65 system-ui,sans-serif;
max-width:770px;margin:40px auto;padding:0 20px}}a{{color:#ffc18b}}
h1{{font-size:clamp(2rem,7vw,3.6rem);line-height:1.12}}img{{width:165px;border-radius:18px}}
audio{{display:block;width:100%;margin:30px 0}}
.subtitle{{color:#b7c6d7}}footer{{font-size:14px;color:#b7c6d7;margin:50px 0}}
</style></head><body>
<img src="cover.png" alt="First Light cover artwork">
<h1>First Light:<br>World Report</h1>
<p class="subtitle">Daily world news, business, science, tech & San Antonio weather</p>
<h2>{html.escape(day)}</h2>
<audio controls preload="metadata" src="latest.mp3?date={day}"></audio>
<p><a href="latest.mp3?date={day}">Download this episode</a> ·
<a href="feed.xml">Subscribe with RSS</a></p>
<h2>Sources</h2><ol>{links}</ol>
<h2>Transcript</h2><p>{html.escape(transcript)}</p>
<footer>AI narration may contain errors. Follow linked original reporting.
Keep a separate wake-up alarm: publication and iPhone automation are best effort.</footer>
</body></html>"""


def main():
    now = datetime.now(TZ)
    day = now.date().isoformat()
    for variable in ("OPENAI_API_KEY", "ELEVENLABS_API_KEY",
                     "ELEVENLABS_VOICE_ID", "GH_TOKEN", "GITHUB_REPOSITORY"):
        required(variable)
    WORK.mkdir(parents=True, exist_ok=True)
    SITE.mkdir(parents=True, exist_ok=True)

    weather = fetch_weather(now)
    client = OpenAI(api_key=required("OPENAI_API_KEY"), timeout=160, max_retries=2)
    research, sources, script = news_and_script(client, now, weather)
    sources += [
        {"title": "Open-Meteo San Antonio weather", "url": "https://open-meteo.com/en/docs"},
        {"title": "National Weather Service alerts", "url": "https://api.weather.gov/alerts/active"}
    ]

    transcript = WORK / f"first-light-{day}.txt"
    transcript.write_text(script, encoding="utf-8")
    notes = WORK / f"first-light-{day}-sources.md"
    notes.write_text(
        f"First Light: World Report | {day}\n\nAI-generated news and weather briefing.\n\n"
        + "\n".join(f"- {s['title']}: {s['url']}" for s in sources)
        + "\n\nVerify consequential claims against linked original reporting.",
        encoding="utf-8"
    )
    mp3 = WORK / f"first-light-{day}.mp3"
    synthesize(script, mp3)
    publish_release(day, mp3, transcript, notes)
    releases = list_releases(day)
    base = public_base()

    xml_feed(releases, base).write(SITE / "feed.xml", encoding="utf-8", xml_declaration=True)
    cover(SITE / "cover.png")
    shutil.copyfile(mp3, SITE / "latest.mp3")
    (SITE / "latest.json").write_text(
        json.dumps({"date": day, "title": TITLE, "audio_url": base + "/latest.mp3?date=" + day,
                    "published_at": datetime.now(timezone.utc).isoformat()}, indent=2),
        encoding="utf-8"
    )
    (SITE / "index.html").write_text(web_page(day, sources, script), encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    LOG.info("Episode %s published to release, Pages files ready for %s", day, base)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        main()
    except Exception:
        LOG.exception("Production failed; not publishing a new Pages site")
        sys.exit(1)
