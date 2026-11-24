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
import calendar
import feedparser
from PIL import Image, ImageDraw, ImageFont

LOG = logging.getLogger("firstlight")
TZ = ZoneInfo("America/Chicago")
ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
SITE = ROOT / "site"
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


def http_json(url, *, params=None, headers=None, timeout=(10, 25), attempts=3):
    """Retry transient weather/network errors without retrying bad requests.

    The connect/read timeouts are separate so an unreliable API cannot hang
    indefinitely. A transient timeout should never cancel the entire episode.
    """
    if attempts < 1:
        raise ValueError("attempts must be positive")
    for attempt in range(attempts):
        try:
            response = requests.get(
                url, params=params, headers=headers, timeout=timeout
            )
            response.raise_for_status()
            return response.json()
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
            if isinstance(exc, requests.HTTPError):
                status = getattr(exc.response, "status_code", None)
                if status is not None and status not in (408, 429) and status < 500:
                    raise
            if attempt == attempts - 1:
                raise
            delay = min(3 * (attempt + 1), 8)
            LOG.warning("Weather request temporary failure, retry %s/%s in %ss: %s",
                        attempt + 1, attempts - 1, delay, type(exc).__name__)
            time.sleep(delay)


WMO = {
    0: "clear", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "rime fog", 51: "light drizzle", 53: "drizzle",
    55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow",
    80: "isolated showers", 81: "rain showers", 82: "heavy showers",
    95: "thunderstorms", 96: "thunderstorms with hail", 99: "severe thunderstorms"
}


def _weather_unavailable(now):
    """Explicit missing values keep the script from making up weather facts."""
    return {
        "location": "San Antonio, Texas",
        "date": now.date().isoformat(),
        "source": "unavailable",
        "conditions": None,
        "temperature_f": None,
        "feels_like_f": None,
        "wind_mph": None,
        "high_f": None,
        "low_f": None,
        "max_rain_percent": None,
        "peak_rain_chance_hours": [],
        "nws_alert_check": "not verified",
        "nws_active_alerts": [],
    }


def _nws_weather_backup(now):
    """Use official NWS period forecasts if Open-Meteo cannot be reached.

    NWS temperatures are *forecasts*, not current measured observations.
    """
    headers = {
        "Accept": "application/geo+json",
        "User-Agent": "FirstLightPodcast/2.0 (daily San Antonio news briefing)",
    }
    points = http_json(
        "https://api.weather.gov/points/29.4241,-98.4936",
        headers=headers, timeout=(8, 12), attempts=2
    )
    forecast_url = points["properties"]["forecast"]
    if (urlsplit(forecast_url).scheme != "https"
            or urlsplit(forecast_url).hostname != "api.weather.gov"):
        raise ValueError("Unexpected NWS forecast URL")
    forecast = http_json(
        forecast_url, headers=headers, timeout=(8, 15), attempts=2
    )
    periods = [
        p for p in forecast.get("properties", {}).get("periods", [])
        if datetime.fromisoformat(p["startTime"]).astimezone(TZ).date() == now.date()
    ]
    if not periods:
        raise ValueError("No NWS forecast periods for today's date")
    daytime = next((p for p in periods if p.get("isDaytime")), None)
    nighttime = next((p for p in periods if not p.get("isDaytime")), None)
    def fahrenheit(period):
        if not period or period.get("temperatureUnit") != "F":
            return None
        value = period.get("temperature")
        return value if isinstance(value, (int, float)) else None
    precip = [
        p.get("probabilityOfPrecipitation", {}).get("value")
        for p in periods
    ]
    precip = [p for p in precip if isinstance(p, (int, float))]
    weather = _weather_unavailable(now)
    weather.update({
        "source": "NWS period forecast",
        "conditions": (daytime or periods[0]).get("shortForecast"),
        "high_f": fahrenheit(daytime),
        "low_f": fahrenheit(nighttime),
        "max_rain_percent": max(precip) if precip else None,
    })
    LOG.info("Using National Weather Service forecast backup for San Antonio")
    return weather


def fetch_weather(now):
    """Retrieve weather with retries, a second provider, and safe missing data."""
    day = now.date().isoformat()
    params = {
        "latitude": 29.4241, "longitude": -98.4936,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
        "hourly": "precipitation_probability",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
        "timezone": "America/Chicago", "forecast_days": 2,
    }
    try:
        data = http_json(
            "https://api.open-meteo.com/v1/forecast",
            params=params, timeout=(10, 25), attempts=3
        )
        if data["daily"]["time"][0] != day:
            raise ValueError("Weather date did not match the production day")
        hourly = data["hourly"]
        periods = [
            {"hour_local": hour[-5:], "rain_percent": chance}
            for hour, chance in zip(hourly["time"], hourly["precipitation_probability"])
            if hour.startswith(day) and chance is not None
        ]
        periods.sort(key=lambda p: p["rain_percent"], reverse=True)
        weather = _weather_unavailable(now)
        weather.update({
            "source": "Open-Meteo",
            "conditions": WMO.get(data["current"].get("weather_code"), "not available"),
            "temperature_f": data["current"].get("temperature_2m"),
            "feels_like_f": data["current"].get("apparent_temperature"),
            "wind_mph": data["current"].get("wind_speed_10m"),
            "high_f": data["daily"]["temperature_2m_max"][0],
            "low_f": data["daily"]["temperature_2m_min"][0],
            "max_rain_percent": data["daily"]["precipitation_probability_max"][0],
            "peak_rain_chance_hours": periods[:4],
        })
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
        LOG.warning("Open-Meteo weather unavailable (%s). Trying NWS backup.", type(exc).__name__)
        try:
            weather = _nws_weather_backup(now)
        except (requests.RequestException, KeyError, IndexError,
                TypeError, ValueError) as backup_exc:
            LOG.warning("NWS forecast backup unavailable (%s). "
                        "Broadcast will explicitly report weather as unavailable.",
                        type(backup_exc).__name__)
            weather = _weather_unavailable(now)
    try:
        nws = http_json(
            "https://api.weather.gov/alerts/active",
            params={"point": "29.4241,-98.4936"},
            headers={
                "Accept": "application/geo+json",
                "User-Agent": "FirstLightPodcast/2.0 (daily San Antonio news briefing)"
            },
            timeout=(8, 12), attempts=2
        )
        weather["nws_alert_check"] = "checked"
        weather["nws_active_alerts"] = [
            f.get("properties", {}).get("headline", "NWS alert")
            for f in nws.get("features", [])[:5]
        ]
    except (requests.RequestException, KeyError, IndexError,
            TypeError, ValueError) as exc:
        LOG.warning("NWS alert check unavailable: %s", type(exc).__name__)
    return weather


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


RSS_FEEDS = [
    ("world", "BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("world", "NPR World", "https://feeds.npr.org/1004/rss.xml"),
    ("world", "The Guardian World", "https://www.theguardian.com/world/rss"),
    ("world", "Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("business", "BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("business", "NPR Business", "https://feeds.npr.org/1006/rss.xml"),
    ("business", "Guardian Business", "https://www.theguardian.com/uk/business/rss"),
    ("science", "BBC Science", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
    ("science", "NPR Science", "https://feeds.npr.org/1007/rss.xml"),
    ("tech", "BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("tech", "Guardian Technology", "https://www.theguardian.com/uk/technology/rss"),
]

def tidy(text, limit=220):
    text = re.sub(r"<[^>]*>", " ", str(text or ""))
    text = html.unescape(text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rsplit(" ", 1)[0] if len(text) > limit else text

def rss_news(now):
    result = {"world": [], "business": [], "science": [], "tech": []}
    working = 0
    allstories = []
    for section, name, feedurl in RSS_FEEDS:
        try:
            resp = requests.get(feedurl, timeout=16,
                 headers={"User-Agent": "FirstLightPodcast/2.0 (personal news briefing)"})
            resp.raise_for_status()
            if len(resp.content) > 2_000_000:
                raise ValueError("Oversized RSS feed")
            parsed = feedparser.parse(resp.content)
            if not parsed.entries:
                raise ValueError("No stories")
            working += 1
            for story in parsed.entries[:18]:
                title = tidy(story.get("title"), 180)
                link = story.get("link", "")
                timestamp = story.get("published_parsed") or story.get("updated_parsed")
                if not title or not link.startswith("https://") or not timestamp:
                    continue
                dt = datetime.fromtimestamp(calendar.timegm(timestamp), timezone.utc)
                age = (now.astimezone(timezone.utc)-dt).total_seconds()/3600
                if age < -1 or age > 42:
                    continue
                allstories.append({
                    "category": section, "publisher": name,
                    "title": title, "summary": tidy(story.get("summary"), 200),
                    "url": link, "published": dt.isoformat(), "age": age
                })
        except (requests.RequestException, ValueError, TypeError, OverflowError) as exc:
            LOG.warning("Feed %s unavailable: %s", name, exc)
    if working < 4:
        raise RuntimeError("Fewer than four working news feeds; no episode published")
    unique = set()
    for group in result:
        count_per_source = {}
        for story in sorted((s for s in allstories if s["category"]==group),
                             key=lambda x: x["age"]):
            identity = re.sub(r"[^a-z0-9]", "", story["title"].lower())[:85]
            if identity in unique or count_per_source.get(story["publisher"],0)>=4:
                continue
            unique.add(identity)
            count_per_source[story["publisher"]] = count_per_source.get(story["publisher"],0)+1
            result[group].append(story)
            if len(result[group]) >= (9 if group=="world" else 5):
                break
    if len(result["world"]) < 5 or len(result["business"]) < 2 or (
         len(result["science"])+len(result["tech"]) < 2):
        raise RuntimeError("Too few recent cross-category headlines; no episode published")
    return result

def selected_stories(groups):
    return {
       "Top world headlines": groups["world"][:5],
       "Around the world": groups["world"][5:8],
       "Business and markets": groups["business"][:3],
       "Science and tech": groups["science"][:2] + groups["tech"][:2],
    }

def weather_narration(w):
    """Never invent a number when weather APIs are unreachable."""
    lines = ["And now, a look at the weather in San Antonio."]
    source = w.get("source")
    condition = w.get("conditions")
    temp = w.get("temperature_f")
    high = w.get("high_f")
    low = w.get("low_f")
    rain = w.get("max_rain_percent")
    wind = w.get("wind_mph")
    if source == "unavailable":
        lines.append(
            "The live forecast services are temporarily unavailable, "
            "so I can't confirm today's temperatures or rain chances. "
            "Please check your local National Weather Service forecast before heading out."
        )
    else:
        if temp is not None:
            lines.append(f"It's currently around {round(temp)} degrees.")
        if condition:
            prefix = "The forecast calls for" if source == "NWS period forecast" else "Conditions are"
            lines.append(f"{prefix} {condition}.")
        if high is not None:
            lines.append(f"Today's forecast high is near {round(high)} degrees.")
        if low is not None:
            lines.append(f"The forecast low is near {round(low)}.")
        if rain is not None:
            lines.append(f"The maximum forecast chance of rain is about {round(rain)} percent.")
        if wind is not None:
            lines.append(f"Winds are near {round(wind)} miles per hour.")
        if rain is not None and rain >= 20 and w.get("peak_rain_chance_hours"):
            hour = w["peak_rain_chance_hours"][0]["hour_local"]
            lines.append(f"The hourly forecast has a higher rain chance near {hour} local time.")
    if w.get("nws_alert_check") == "checked":
        alerts = w.get("nws_active_alerts") or []
        if alerts:
            lines.append("The National Weather Service lists an active alert: " +
                         ". ".join(alerts) + ".")
        else:
            lines.append("No active National Weather Service alerts were found in this check.")
    else:
        lines.append("The official alert feed could not be verified. Check local weather warnings.")
    return " ".join(lines)


def fallback_readout(now, stories, weather):
    # Fact-limited, original attributed headline roundup if free Gemini unavailable.
    text=[
        f"Good morning, San Antonio. Today is {now.strftime('%A, %B %d, %Y')}. "
        "You're listening to First Light: World Report, your morning window on "
        "what's happening around the world. The following is a recently published "
        "headline roundup rather than independent investigative reporting. "
        "Every story's original source is linked in the episode notes, and "
        "breaking details may change throughout the day."
    ]
    openers={
        "Top world headlines":"First, the top world headlines.",
        "Around the world":"Now, some developments from around the world.",
        "Business and markets":"Turning to business and markets.",
        "Science and tech":"On to science and technology."
    }
    outros=[
        "The original report contains more background.",
        "Follow the original source for the latest updates.",
        "More information may come out as this story develops.",
        "The source is linked in today's episode notes."
    ]
    index=0
    for section, items in selected_stories(stories).items():
        text.append(openers[section])
        for item in items:
            line=f"{item['publisher']} reports: {item['title'].rstrip('.!')}. "
            summary=item["summary"].rstrip(".! ")
            if summary and summary.lower() not in item["title"].lower() and item["title"].lower() not in summary.lower():
                line+=f"The short news-feed description adds: {tidy(summary,100)}. "
            line+=outros[index%len(outros)]
            text.append(line)
            index+=1
    text.extend([
        "For markets, we won't invent index movements, stock prices or futures "
        "before we can verify the time and figures. The business headlines are "
        "sourced from recent published reports. On holidays and weekends, "
        "remember that the last U.S. trading session may be days earlier.",
        weather_narration(weather),
        "The stories worth watching today are those still developing. "
        "Major updates may follow official announcements, market openings, "
        "new research releases and on-the-ground reporting. "
        "Revisit the original sources for new facts rather than assuming "
        "a morning headline tells the entire story.",
        "Thanks for spending part of your morning with First Light: World Report. "
        "Stay informed, keep asking questions, and have a great day."
    ])
    return re.sub(r"\s+", " ", " ".join(text))

def optional_gemini_script(now, stories, weather):
    key = os.getenv("GEMINI_API_KEY","").strip()
    if not key:
        LOG.info("No Gemini key; using a source-attributed, no-API fallback.")
        return None
    # Only public RSS headlines and short excerpts are transmitted to Gemini.
    # Never send financial/personal information, credentials, or full articles.
    material={}
    for section, entries in selected_stories(stories).items():
        material[section]=[
           {"publisher":e["publisher"],"title":e["title"],
            "short_summary":e["summary"],"published":e["published"]}
           for e in entries
        ]
    prompt=f"""Write the complete original 5–7 minute SPOKEN RADIO SCRIPT for
First Light: World Report dated {now.strftime('%A, %B %d, %Y')}, waking up in
San Antonio. Target 760–890 spoken words, conversational, clear,
friendly, professional and politically neutral.
Return ONLY actual narration: no markdown, bullets, raw links or editorial notes.
Organize with smooth transitions: top world headlines, around the world,
business and markets, science and tech, San Antonio weather, what to watch,
and a concise upbeat signoff. Open with a good morning and full date.
Base ALL factual claims solely on the attributed RSS source metadata and
structured weather below. Do not add imagined context, explanations, market
levels, quotes, speculation, statistics, event outcomes, or timelines.
Use original wording; do not reproduce article text. Attribute stories
to publishers. If facts are sparse, be shorter rather than invent facts.
Do not give U.S. stock index figures because no verified values were supplied.
If NWS alerts weren't verified, don't claim there aren't any.
When weather values are null, say they are unavailable and do not invent values.
Only use weather numbers supplied below. All temperatures Fahrenheit.
News:
{json.dumps(material,ensure_ascii=False)}
San Antonio live weather:
{json.dumps(weather,ensure_ascii=False)}
"""
    model=os.getenv("GEMINI_MODEL","gemini-3.5-flash-lite")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+",model):
        LOG.warning("Invalid Gemini model name; using headline-only fallback")
        return None
    # Newer Gemini Flash-Lite models provide Free tier access where eligible.
    # If the selected model is unavailable to this project, try one other
    # publicly documented free-tier model. Never call a paid AI API.
    candidates=[model]
    if model != "gemini-3.1-flash-lite":
        candidates.append("gemini-3.1-flash-lite")
    for selected_model in candidates:
        try:
            response=requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent",
                headers={"x-goog-api-key":key,"Content-Type":"application/json"},
                json={"contents":[{"parts":[{"text":prompt}]}],
                      "generationConfig":{"temperature":0.2,"maxOutputTokens":3600}},
                timeout=100
            )
            if response.status_code==404:
                LOG.warning("Gemini model %s is unavailable (HTTP 404), trying another free-tier model",
                            selected_model)
                continue
            if response.status_code in (401,403,429):
                LOG.warning("Gemini rejected request with HTTP %d, using sourced RSS fallback",
                            response.status_code)
                return None
            response.raise_for_status()
            data=response.json()
            script=" ".join(p.get("text","") for p in data["candidates"][0]["content"]["parts"])
            script=re.sub(r"\s+"," ",script.strip())
            if not 650 <= len(script.split()) <= 990 or "San Antonio" not in script or "First Light" not in script:
                LOG.warning("Gemini %s returned an unsuitable script, falling back to RSS",selected_model)
                return None
            LOG.info("Gemini script produced with model %s (%s words)",selected_model,len(script.split()))
            return script
        except (requests.RequestException,ValueError,KeyError,IndexError) as exc:
            LOG.warning("Gemini model %s failed; RSS fallback: %s",
                        selected_model,str(exc)[:140])
            return None
    LOG.warning("No accessible Gemini model for this project; using sourced RSS fallback")
    return None

def news_and_script(_client,now,weather):
    groups=rss_news(now)
    selected=selected_stories(groups)
    sources=[
        {"url":item["url"],"title":item["publisher"]+": "+item["title"]}
        for section in selected.values() for item in section
    ]
    script=optional_gemini_script(now,groups,weather)
    mode="Gemini free-tier script" if script else "attributed RSS fallback"
    if script is None:
        script=fallback_readout(now,groups,weather)
    LOG.info("News script mode: %s; %s words",mode,len(script.split()))
    notes="Original sourced headlines and independent local weather. "+mode
    return notes,sources,script

def _tts_asset(url,path,min_size):
    if path.exists() and path.stat().st_size>=min_size:
        return
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".partial")
    with requests.get(url,stream=True,timeout=120) as r:
        r.raise_for_status()
        with tmp.open("wb") as f:
            for block in r.iter_content(1024*1024):
                if block:
                    f.write(block)
    if tmp.stat().st_size<min_size:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("Voice model downloaded incompletely")
    tmp.replace(path)

def _tts_segments(text, maxlen=230):
    # Limit each Kokoro utterance to a short phrase/sentence.
    result=[]
    current=""
    for sentence in re.split(r"(?<=[.!?])\s+",text):
        while len(sentence)>maxlen:
            boundary=sentence.rfind(" ",0,maxlen)
            boundary=boundary if boundary>70 else maxlen
            if current:
                result.append(current)
                current=""
            result.append(sentence[:boundary].strip())
            sentence=sentence[boundary:].strip()
        if current and len(current)+len(sentence)+1>maxlen:
            result.append(current)
            current=""
        current=(current+" "+sentence).strip()
    if current:
        result.append(current)
    return [x for x in result if x]

def _tts_kokoro(script,destination):
    import numpy as np
    import soundfile as sf
    from kokoro_onnx import Kokoro
    base="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/"
    cache=Path.home()/".cache/first-light/kokoro"
    model=cache/"kokoro-v1.0.int8.onnx"
    voices=cache/"voices-v1.0.bin"
    _tts_asset(base+model.name,model,50_000_000)
    _tts_asset(base+voices.name,voices,100_000)
    engine=Kokoro(str(model),str(voices))
    chunks=[]
    rate=None
    for segment in _tts_segments(script):
        wave_data,new_rate=engine.create(segment,voice=os.getenv("KOKORO_VOICE","am_michael"),
                                         speed=1.05,lang="en-us")
        if rate is None:
            rate=new_rate
        if rate!=new_rate:
            raise RuntimeError("Speech sample rate mismatch")
        chunks.append(np.asarray(wave_data,dtype=np.float32).reshape(-1))
        chunks.append(np.zeros(int(rate*0.12),dtype=np.float32))
    if not chunks:
        raise RuntimeError("No Kokoro speech output")
    sf.write(str(destination),np.concatenate(chunks),rate)

def _tts_piper(script,destination):
    import wave
    from piper import PiperVoice
    model=Path.home()/".cache/first-light/piper/en_US-lessac-medium.onnx"
    base="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/"
    _tts_asset(base+model.name,model,10_000_000)
    _tts_asset(base+model.name+".json",model.with_suffix(".onnx.json"),100)
    speaker=PiperVoice.load(str(model))
    with wave.open(str(destination),"wb") as wav:
        speaker.synthesize_wav(script,wav)

def synthesize(script,destination):
    """Local CPU TTS only. Never calls ElevenLabs."""
    wav=WORK/"narration.wav"
    try:
        _tts_kokoro(script,wav)
        LOG.info("Using free local Kokoro voice")
    except Exception as err:
        LOG.warning("Kokoro unavailable (%s), falling back to free Piper",str(err)[:150])
        _tts_piper(script,wav)
    subprocess.run(["ffmpeg","-nostdin","-y","-hide_banner","-loglevel","error",
                    "-i",str(wav),"-codec:a","libmp3lame","-b:a","112k",str(destination)],
                    check=True,timeout=240)
    if destination.stat().st_size < 50_000:
        raise RuntimeError("Generated audio unexpectedly small")

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
    for variable in ("GH_TOKEN", "GITHUB_REPOSITORY"):
        required(variable)
    WORK.mkdir(parents=True, exist_ok=True)
    SITE.mkdir(parents=True, exist_ok=True)

    weather = fetch_weather(now)
    research, sources, script = news_and_script(None, now, weather)
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
