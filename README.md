# First Light: World Report 🎙️ | Version 2

**The world. Before your day.** A 5–7-minute, ad-free, AI-assisted morning
news briefing with important global events, concise business/science/technology
updates, and San Antonio weather. Published ahead of 5 AM Central when
scheduled services are available.

## Editorial improvement: Phases 1 and 2

### Phase 1: Story judgment and sound quality

- Select **approximately seven news stories**, not a fixed dump of 15–16 RSS
  headlines. Lead with two high-impact stories, then short globally diverse
  reports, business, science and technology.
- Use a transparent deterministic ranking algorithm: freshness, source
  diversity, potential significance, geographic diversity and novelty.
- Use a radio-style script outline: informative opening, two explained lead
  stories, quick briefs, actionable local weather, and what to watch.
- Narrate primarily with the **Gemini 3.8 Flash TTS Charon** voice the listener
  selected. If unavailable, use Kokoro FP16 Adam, then Piper locally.
- Apply safe abbreviation expansions to improve pronunciation without
  inventing pronunciations of international names.
- Normalize and encode MP3 at **192 kbps**. The automated checks reject
  invalid/implausibly short MP3s and log true duration and actual narrator.
- The 5–7-minute target is checked; a headline-only source fallback can be
  shorter. No padding with unsourced facts to force a specific length.
- Explain AI assistance at the beginning of the spoken episode and in RSS.

### Phase 2: Source transparency and memory

- Publisher RSS **article URLs are restricted to approved publisher domains**.
  News timestamps are checked; feeds older than 42 hours are not included.
- Cluster closely related headlines from different publishers and preserve
  source links and short descriptions. **Clustering is not proof that a
  factual claim was independently verified**. These are corroborating
  *topic-level* leads for human verification, not article-level fact checks.
- Treat single-source claims as attributed reporting. The Gemini script prompt
  forbids unsourced context, invented market data, quotes or speculative causes.
- The previous seven days of published topic metadata are read from GitHub
  Release notes. Repeated headlines are deprioritized or skipped; possible
  follow-ups include the previous headline/date, but must not be characterized
  as confirmed changes without evidence. The first version 2 run has no
  prior metadata to consult; it builds up over subsequent broadcasts.
- Provide a public [correction request form](../../issues/new/choose) and
  [corrections policy](CORRECTIONS.md). Requests are **not automatically
  checked by a human**; the repository owner must review and resolve them.
- Save an episode's editorial audit, sources and compact previous-episode
  memory in its GitHub Release notes. The notes are **public**.
- Use Open-Meteo with NWS backup and separate NWS alert checks. If the
  forecasts cannot be verified, say so rather than invent weather details.

### Current limitations

The system does **not** have human editors, full-text article fact-checking,
independent interviews, a licensed newswire subscription or a guarantee
against Gemini hallucinations. Short RSS feeds can provide insufficient facts
to explain why something matters; when details are sparse, the script should
remain concise. Important stories require checking linked original sources.
Do not distribute unlicensed publisher text or copyrighted podcast audio.

## Services and cost

- **News sources:** Permitted public BBC, NPR, Guardian and Al Jazeera RSS
  feeds, stored as headline metadata and links.
- **AI script:** Optional Gemini key (default gemini-3.5-flash-lite with a
  free-tier model alternative). A source-attributed template is the backup.
- **AI voice:** Gemini 3.8 Flash TTS Charon. Kokoro FP16 Adam and Piper are
  local backup voices.
- **Weather:** Open-Meteo / National Weather Service.
- **Hosting:** GitHub Releases MP3 archives and GitHub Pages podcast site.
- **Schedule:** 3:30 AM America/Chicago; target listen time 5 AM.

**Costs:** No OpenAI or ElevenLabs APIs are called by the active daily workflow.
The Gemini API **may incur charges** if your Google project has paid billing
enabled. Confirm that your project/model combination really has free-tier
access and sufficient limits. Free quotas and pricing can change. There is no
application-level hard-dollar spend cutoff. GitHub public-repository runner
availability and API quotas also remain subject to provider policies.

## One-time setup

1. Create an API key at https://aistudio.google.com/apikey using an
   appropriately configured **Gemini Free tier** project.
2. Store it as GitHub Actions repository secret **GEMINI_API_KEY** at
   https://github.com/snrahimi/first-light-podcast/settings/secrets/actions .
   Never paste the key into code, chat, Issues, README or Variables.
3. Enable **GitHub Actions** as the Pages build source:
   https://github.com/snrahimi/first-light-podcast/settings/pages
4. From [First Light Daily Podcast (Free)](../../actions/workflows/daily.yml),
   choose **Run workflow** on the main branch.
5. Check the run logs, the edition's GitHub Release, the live player and the
   feed. Automated unit tests are not a substitute for one real end-to-end test.

Expected site after a successful deployment:

- https://snrahimi.github.io/first-light-podcast/
- https://snrahimi.github.io/first-light-podcast/feed.xml
- https://snrahimi.github.io/first-light-podcast/latest.json
- https://snrahimi.github.io/first-light-podcast/latest.mp3

## iPhone automation

Use Shortcuts → Automation → Time of Day **5 AM Daily**. Retrieve
latest.json and verify that its date matches today in America/Chicago
before playing the audio_url; otherwise don't play yesterday's news as
current. Test playback on a locked phone and keep a separate wake-up alarm.
GitHub Actions scheduling and iOS automations are best effort.

## Quality assurance

Run python -m unittest discover -s tests -v and
python -m py_compile src/first_light.py src/editorial.py. The CI job
automatically performs these tests, including simulated provider failures
and checks of story selection, source domains, publication memory,
Gemini audio assembly, and audio QC.

The daily production process inspects the actual MP3 before creating a
Release and includes its narrator, duration, script source, source diversity
and repeat-avoidance statistics in the public latest.json metadata.

If a full production run fails, use its GitHub Actions log to distinguish
source availability, weather outages, Gemini quota, speech production,
GitHub Release publication and Pages artifact deployment.
