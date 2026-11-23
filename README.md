# First Light: World Report 🎧

An automatically generated, AI-narrated daily world news podcast made for a 5:00 AM wake-up in San Antonio, Texas.

**Status:** Source code deployed. To begin producing audio, finish the one-time settings below. It is *not live* until an Actions run completes and the podcast feed is published.

## What it does

Every day at **3:45 AM America/Chicago**, a GitHub Actions workflow researches the latest news using OpenAI's Responses API with web search, retrieves San Antonio weather from Open-Meteo and NWS, writes an original spoken-word script, synthesizes MP3 narration via ElevenLabs, and publishes an RSS feed, episode transcript, source links and a lightweight website through GitHub Pages. Episode MP3s are archived in GitHub Releases. News coverage: top world headlines, around the world, business and markets, science and tech, and San Antonio weather.

**Important:** Scheduled cloud jobs may run late, APIs can fail, and phone automations aren't guaranteed to activate exactly on time. Keep a separate iPhone wake-up alarm. The workflow fails instead of publishing stale audio when new research or narration fails.

## One-time activation

1. In this repository, go to **Settings → Secrets and variables → Actions**. Add three **repository secrets**:
   - `OPENAI_API_KEY` from [OpenAI API](https://platform.openai.com/api-keys) (separate API billing from ChatGPT)
   - `ELEVENLABS_API_KEY` from [ElevenLabs](https://elevenlabs.io/)
   - `ELEVENLABS_VOICE_ID` for your chosen ElevenLabs English narration voice
2. Go to **Settings → Pages → Build and deployment → Source** and choose **GitHub Actions**.
3. Go to **Actions → First Light Daily Podcast → Run workflow**. This performs a *paid real API run*. Verify it finishes successfully. If the run fails, open its logs; no episode is published when the job fails.
4. Once successful, listen at **https://snrahimi.github.io/first-light-podcast/**. The feed is **https://snrahimi.github.io/first-light-podcast/feed.xml**, newest MP3 **https://snrahimi.github.io/first-light-podcast/latest.mp3**, and machine-readable metadata **https://snrahimi.github.io/first-light-podcast/latest.json**.
5. On iPhone, **Podcasts → Library → … → Follow a Show by URL**, and paste the feed URL. This is for browsing episodes; following a show is **not** enough to make it start playing at 5 AM.
6. In iPhone **Shortcuts → Automation → Time of Day**, set **5:00 AM / Daily / Run Immediately** (if offered). Add actions to fetch `latest.json`, compare its `date` to today's date in `yyyy-MM-dd`, and if equal, fetch `audio_url` and `Play Sound`. If not equal, have the shortcut speak a short unavailable notice. Configure speaker volume and test with the phone locked. See the detailed steps below.

**Secrets must never be pasted into this public repository or chat.** The connected ChatGPT GitHub app cannot configure repository secrets or the Pages source. Only you can perform those GitHub settings steps.

## Detailed iPhone Shortcut

The goal is to avoid waking up to yesterday's episode when an API service is down.

- New personal automation: **Time of Day / 5:00 AM / Daily / Run Immediately**.
- Action **URL** → `https://snrahimi.github.io/first-light-podcast/latest.json`.
- Action **Get Contents of URL**. This should be parsed as a Dictionary.
- Action **Get Dictionary Value** for key `date`. Save that value or use it in the following comparison.
- Action **Current Date** → **Format Date** with format `yyyy-MM-dd`.
- Action **If** the downloaded `date` equals the formatted date:
  - **Get Dictionary Value** `audio_url` from the first downloaded dictionary;
  - **Get Contents of URL** for that URL;
  - **Set Volume** to your preferred volume, then **Play Sound** with downloaded audio.
- **Otherwise**, **Speak Text**: "Today's First Light report isn't ready yet. Your regular alarm will still sound."
- Turn off any confirmation prompt, test once from inside Shortcuts and once as a real timed automation while the phone is locked. Allow network access where prompted and verify that your output speaker isn't unexpectedly routed to Bluetooth.

Optionally, add a second **4:55 AM** automation that checks `latest.json`, downloads today's audio, and saves it locally before the playback automation. That improves reliability with weak morning Wi-Fi but adds iPhone setup complexity.

## Costs and privacy

- OpenAI developer API/web search and ElevenLabs speech synthesis are separately metered services. A roughly 1,500-word daily episode could use around 250,000–350,000 TTS characters per month. Review API pricing and set spend limits before activating.
- **This repository and the GitHub Pages / Releases content are public.** Podcast feed URLs are not private or password-protected.
- The narration is AI-generated and can make mistakes. News sources appear in the show notes and on the site, and critical reports should be verified in their original sources.

## How it works

- `.github/workflows/daily.yml`: schedule, test and publish workflow.
- `src/first_light.py`: research, weather, script, narration, RSS and web publishing.
- `tests/test_first_light.py`: offline smoke tests without paid API calls.
- `requirements.txt`: Python dependencies.

Local tests: `python -m unittest discover -s tests -v`.

This automated audio pipeline is separate from the preexisting ChatGPT scheduled *text* briefing. You may pause the text task later if you only want audio.
