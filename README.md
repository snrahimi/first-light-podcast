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

## Phases 3.3 and 3.2: source-led six-minute writing

These upgrades were implemented in sequence with separate GitHub checks.

- Stage 3.3: add official UN Press RSS to NASA/BLS/CISA discovery, retrieve up
  to three carefully bounded official-page excerpts from allowlisted agency
  sources, label agency statements as claims rather than independent
  confirmation, and flag numerical differences between publishers for review.
  RSS matching is still not independent fact-checking; no licensed press
  articles or GDELT-discovered pages are scraped.
- Stage 3.2: divide AI scriptwriting into two non-overlapping topical calls,
  one for world developments and one for economy/science/technology. The
  opening, official weather and signoff are controlled by the program.
  Script numbers must be present in cited excerpts or measured weather,
  including source-excerpt rounding allowed by prior regression coverage.
- Spoken duration is estimated from the actual measured Charon reading rate
  (about 163 words/minute, based on the prior 657-word 241.9-second episode).
  About 925 words should yield around 5:40, but source constraints outrank
  duration goals. A short episode is allowed when verified context is sparse.
  The post-production MP3 inspection remains the authority for actual timing.
- A failed Gemini writing request, implausible section, invented digit-form
  statistic, or invalid script goes to the source-attributed deterministic
  fallback. All published audio remains **Gemini Charon exclusively**.
- The production pipeline sends at most two script requests to the selected
  writing model by default. This does not eliminate TTS quotas or guarantee
  that calls are free on a billed Google project.

See [Newsroom 3.0 Roadmap](NEWSROOM3_ROADMAP.md) for release milestones and
limitations. A successful offline test run does not replace a live podcast
production run and an editorial listen-through.

## Follow-up: source depth and duration preflight

The November 24 live acceptance run was published successfully with
Gemini Charon and a Phase 3.2 segmented script, but the 529-word audio
was only 3:08 long. A request for more words is not a verification method.

The next implementation connects the **already selected** stories to
additional same-category, high-overlap, directly linked RSS snippets from
the existing trusted publisher and official-agency feed lists. The two
world leads receive priority. Source/domain matching, small excerpt
limits, and the exact claim-to-source ledger are enforced *before*
using the new context for speechwriting.

This is reporting *attribution*, **not** independent corroboration. No
publisher article body is scraped, no unlicensed full-text material is
copied, and discovery-only GDELT entries are excluded.

The scriptwriter now gets a per-story plan derived from the number
of distinct attributed excerpts and available official passages, with
separate budgets for leads and supporting reports. It is instructed
to add specific details or consequences *only* when excerpts support
them, not to pad narration or invent explanatory history.

A Charon duration preflight runs **before narration**. Its estimate is
based on a measured ~163 words/minute, so it is approximate. The
log and public latest.json include the projected duration, number of
shortfall seconds and count of extra *supported* words needed for five
minutes. **A short, safe episode may still publish:** failure to reach
five minutes is reported rather than concealed by made-up news. Actual
MP3 duration remains authoritative.

The enhancements do not change Gemini API request count (still two
text-writing calls), the required Charon voice, billing, or the
normal GitHub Actions daily schedule.

## Package 2+: Intelligent Newsroom

[Full 53-feature implementation roadmap and acceptance ledger](PACKAGE2PLUS_ROADMAP.md)

Package 2+ adds:

- **Writer resilience:** a maximum of three text requests per section on
  temporary 5xx/connection faults, 429 fail-fast, and source+model
  fingerprinted, 12-hour cached sections between GitHub Actions runs.
- **Source-first editorial intelligence:** selected-story paraphrase/event
  matching, modest evidence-aware ranking, provenance/freshness metadata,
  explicit sensitivity and uncertain-fact review markers.
- **Broadcast quality controls:** Charon speaking-time preflight, public
  editorial scorecard, repetition and numeric-disagreement review flags,
  priority severe NWS announcements when the alert feed was checked, and
  a compact official-acronym pronunciation list.
- **GitHub-only operations:** public health.json and health.html rolling
  production reports, daily 6:15 AM America/Chicago delivery watchdog, one
  deduplicated GitHub issue per failed daily check, a public correction
  request template, and versioned backup audio/transcript/audit/notes on
  same-date regeneration. A failed archive blocks replacement.

The daily producer remains on the free-data path and only Gemini Charon
may narrate. New writing requests are bounded, not unlimited. No paid
provider, extra voice or broad web scraper has been enabled.

**Important:** Phase 2+ code and offline tests do not prove that the
next live broadcast will reach five minutes or be independently fact
checked. The initial release archive and rolling reporting start with
newly produced episodes; older health metrics may be unavailable. Check
[the living roadmap](PACKAGE2PLUS_ROADMAP.md) for capabilities still
partial or deferred.

## Package 2+.5: reliability and editorial depth

[Full feature list and acceptance plan](PACKAGE2PLUS_ROADMAP.md)

Package 2+.5 adds a bounded GitHub release-memory retry with a public seven-day
Pages `memory.json` recovery file (after the first successful new-version
publication), longer but capped Gemini 5xx retry backoff, and a source-led
fallback that can speak additional *already audited* feed excerpts instead of
repeating generic qualifications. News selection now prefers distinct world
events when scores are comparable and higher-impact economic business news
over isolated private luxury listings.

Actions avoids saving an empty script cache, but retains valid completed
sections across failed runs. RSS explicitly links the current episode MP3,
not an older revision archive.

Google's public pricing page lists `gemini-3.1-flash-lite` as a Free Tier
candidate for scriptwriting. **It is not enabled as automatic failover**:
availability, daily quotas, project billing and data-use terms must be checked
for the actual Google project and approved by the owner. Gemini Charon remains
the only approved narrator, and a shorter accurately attributed episode may
still publish when the supplied sources are too thin.

See [Google Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)
and [rate-limit documentation](https://ai.google.dev/gemini-api/docs/rate-limits).


## Package 2+.6: stronger source-backed story development

The producer retains longer *short RSS summaries* and can capture more
distinct, headline-anchored excerpts from selected allowlisted issuing-agency
pages. It may link a few additional **same-event** source-feed reports
from already trusted RSS sources. It does **not** scrape news article bodies
or independently verify publisher claims. Publisher text remains source
material to paraphrase, not wording to copy verbatim.

The two existing Gemini writing sections now receive evidence-weighted
story budgets and explicit instructions to explain distinct supported
details rather than simply reading headlines. Under-delivery below 65%
of an evidence-backed advisory section budget is flagged in public
editorial QA, with **no extra writing requests**. The observed 5–7 minute
target may still be missed when supporting evidence is too sparse.

World leads now use a soft publisher-diversity tie-breaker. Economic
policy and international macroeconomic developments get a modest ranking
bonus. Neither heuristic replaces human news judgment.

Full scope, acceptance limits, and remaining gaps:
[Package 2+ roadmap](PACKAGE2PLUS_ROADMAP.md).
