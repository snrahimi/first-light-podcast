# First Light: World Report 🎙️ | Version 3

> **Newsroom 3.0:** Source expansion, per-story research dossiers, exact
> claim-to-source evidence ledgers and a safer Gemini scriptwriter are implemented.
> See the [Newsroom 3.0 roadmap and limitations](NEWSROOM3_ROADMAP.md).
> This is an AI-assisted source-attributed briefing, NOT a staffed newsroom
> or a guarantee of independently fact-checked news. GDELT is discovery-only.


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
- Narrate **only** with the approved **Gemini 3.8 Flash TTS Charon** voice.
  The daily workflow never substitutes Kokoro Adam or Piper. If Charon is
  unavailable, publication fails before release or Pages replacement, so
  the previously published episode remains untouched.
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
- Newsroom 3.0 also scans NASA and BLS official release feeds and CISA's
  exploited-vulnerabilities catalog when available. GDELT discovers global
  links only; it is never used as broadcast-ready evidence.
- The evidence ledger ties individual *source excerpts* to URLs. It does not
  independently prove the truth of what a publisher reported. The public
  **evidence.json** file and GitHub Release evidence asset expose this audit.
- Gemini scripts can get one bounded evidence-constrained rewrite if a draft
  is too short; unsupported numeric claims fail automated script review.
  Additional Gemini calls consume API quota and may cost money on paid tiers.
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
- **AI voice:** Gemini 3.8 Flash TTS Charon is mandatory for publication.
  Kokoro Adam and Piper are not used automatically. Speech generation is
  paced between chunks, with at most two retries on transient network
  errors or HTTP 429/5xx. Provider daily quotas may still prevent an episode.
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

## Narrator choice and failure behavior

The listener rejected Kokoro Adam after the first Newsroom 3.0 production run.
**Charon is now required.** A partially produced Gemini audio file is never
used as a complete episode; remaining sections must finish. Transient HTTP
429/5xx and connection errors receive bounded retries. HTTP status and
segment number are logged without raw API response bodies or secrets. If any
segment ultimately fails, the run stops before GitHub Release and GitHub
Pages publication. This preserves the previous podcast rather than silently
switching narrator. The prior live episode may still use Adam until a new
successful Charon-only episode replaces it; changing code does not rewrite
already published audio.

The first Newsroom 3.0 run used Adam because Charon completed only two of
four segments and then returned an unclassified runtime failure. Those older
logs did not record the underlying API status. The new logging makes future
reasons easier to identify. API retries may consume additional Gemini quota;
confirm free-tier access and billing safeguards outside the repository.

## TTS 429 quota diagnostics and efficiency (November 2026)

The first Charon-only Newsroom 3.0 production attempt failed with HTTP 429
on segment 1/4 three times. News collection, NWS weather backup and the
evidence-based script fallback all worked. HTTP 429 is a Google-side quota,
throttling or capacity response, not a Python import or weather bug.

The production workflow now:

- Generates larger sentence-aligned Charon audio sections, default **400 words
  per request instead of 210** (approximately two calls for a 640-word script).
  This reduces requests but may need adjustment if the provider changes audio
  length limits. It does not change the Charon voice/model.
- Reads structured Google QuotaFailure and RetryInfo metadata, when available,
  and logs a safe **daily**, **minute**, or **unknown** category.
- For a known daily limit or cooldown longer than two minutes, **fails fast**
  rather than repeatedly retrying and consuming more requests.
- For a possible short-term 429, makes only **one** final retry, honoring a
  reasonable Retry-After.
- For network and 5xx failures, retains bounded temporary retries.
- Preserves previously published material rather than deploying an unapproved
  narrator. The daily production workflow no longer sets KOKORO_VOICE or
  downloads/caches local speech models.

To inspect project-specific quota, visit
https://aistudio.google.com/rate-limit?timeRange=last-28-days and filter to
Gemini 3.8 Flash TTS, then check RPM, RPD and account tier. Google states
that quotas apply per **project**, not per key; daily request limits reset at
**midnight Pacific time** (2 AM Central while both are on standard or
daylight time). A 429 with no recognizable provider detail remains
**unknown**, so the logs cannot guarantee which dimension was exhausted.
Google docs: https://ai.google.dev/gemini-api/docs/rate-limits

**Free-tier guarantee:** NONE. Gemini 3.8 Flash TTS is listed with free-tier
pricing, but only within the limits assigned to your actual project. If
billing is enabled, provider requests may be billable. The code does not
change the project's billing tier and cannot override Google quotas. Avoid
manual reruns until usage resets; a second API key on the same project does
not reset quota. Each failed production run still leaves the prior episode
in place.

**Next acceptance step:** Inspect your AI Studio quota, then start one fresh
GitHub Actions daily workflow run after the applicable reset. If its new
log explicitly reports quota category=daily or quota category=minute,
use that evidence to guide the next change. Do not try an unapproved
voice or a paid API tier to bypass rate limits.
