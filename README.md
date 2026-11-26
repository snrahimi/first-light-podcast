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
- Narrate with **ElevenLabs Brian as primary and Daniel as backup**, using
  the same Flash v2.5 model and complete-script single-call synthesis.
  Quota, billing and authentication failures **do not** trigger Daniel,
  and failed or incomplete audio cannot replace a published episode.
  Gemini Charon is available only through an explicit repository variable
  opt-out, not as an automatic third voice.
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
- **AI voice:** Brian (ElevenLabs Default voice) is the production primary,
  and Daniel is the single backup for eligible voice/transient errors.
  No automatic Gemini, Kokoro, or Piper fallback. Provider plan limits
  and monthly credits may still prevent a new episode.
- **Weather:** Open-Meteo / National Weather Service.
- **Hosting:** GitHub Releases MP3 archives and GitHub Pages podcast site.
- **Schedule:** 3:30 AM America/Chicago; target listen time 5 AM.

**Costs:** The active daily workflow now calls ElevenLabs text-to-speech
using the existing `ELEVENLABS_API_KEY` secret. Every successful narration
uses credits, typically 0.5–1 credit per input character depending on
account/model pricing. On the free plan, **10,000 credits per month is not
enough for a 5–7 minute episode every day**. When the checked credit
allowance cannot cover a full episode at a conservative one-credit-per-
character budget, the workflow stops before TTS. Brian→Daniel backup
does not fix an exhausted account. The production code also caps each
episode at 8,000 characters and at most one API call per approved voice.
No automatic purchase, plan upgrade or rollover-spending approval occurs
in the application. A provider account with Pay As You Go enabled may
have separate billing rules; review them in ElevenLabs directly.
The Gemini writer may incur charges if its project uses paid billing.
GitHub runner availability, provider quotas and scheduling are best effort.

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

**Current selection (November 25, 2026): ElevenLabs Brian first, Daniel
second.** Both classic Default voices were successfully auditioned on
this account. Production verifies remaining ElevenLabs plan allowance
before each synthesis call, generates the **entire script** with a
single voice, checks MP3 validity/duration, normalizes to 192 kbps,
and records the actual narrator in the feed site's metadata.
Only voice-specific/transient failures permit one Daniel attempt.
Account-wide 401/402/403/429 failures, quota exhaustion, and missing
credentials never attempt a second chargeable voice.

These voices are retiring on **December 31, 2026**. Plan and voice
replacement must be chosen ahead of that date. Free-plan generated
audio is strictly **noncommercial with ElevenLabs attribution**:
the podcast homepage, RSS item and GitHub Release notes must show
the attribution when an ElevenLabs episode is produced.
Commercial use requires an eligible paid plan. Do not assume that
the free tier is adequate for the daily publishing schedule.

If either voice fails, or credits run out, the job preserves the
previous published episode. It does not automatically return to Charon.
For an intentional temporary return to Gemini Charon, set GitHub
Actions **repository variable** `FIRST_LIGHT_NARRATOR=charon`
(not a secret). Remove/set `elevenlabs` to restore Brian→Daniel.
Neither change affects the source-based Gemini scriptwriter.

### Historical Charon reliability notes (before November 25, 2026)

The listener rejected Kokoro Adam after the first Newsroom 3.0 production run.
**Charon was previously required.** A partially produced Gemini audio file is never
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

This historical milestone used Gemini Charon and no ElevenLabs narrator.
Since the November 25, 2026 production update, Brian and Daniel are the
approved narrator order. News writing requests remain bounded.

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
the previously approved narrator at that milestone. Brian and Daniel
are the current narrator preference; a shorter accurately attributed episode
may still publish when the supplied sources are too thin.

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


## Optional ElevenLabs free-tier voice audition (manual, noncommercial)

The optional workflow [ElevenLabs Voice Audition (Manual Only)](
.github/workflows/elevenlabs-voice-audition.yml) creates **one**
original ~45-second spoken demo (at most 820 characters) with your
existing ElevenLabs voice, **without** changing the live podcast.

Setup: Both `ELEVENLABS_VOICE_ID` and `ELEVENLABS_API_KEY` must be set
as **GitHub Actions repository secrets**. The source code never reads or
prints their values. Do not move them into repository variables or source
files. In GitHub Actions, open **ElevenLabs Voice Audition (Manual Only)**,
select **main** and **mode = diagnose_only** (the default), then click
**Run workflow**. This makes at most two **GET metadata** requests and
generates no speech or credit charges. It reports only broad plan/voice
categories, not the API key, voice ID, account balance or raw API errors.
Read-only checks can be unavailable if the API key is limited to TTS-only
permissions; this means "unknown", not necessarily a valid voice.

If the selected voice is eligible and you wish to spend credits, run the
workflow again with **mode = generate_sample**. On successful synthesis,
download the artifact `first-light-elevenlabs-review-sample`, containing
an MP3, example script and credit-safe metadata. The artifact expires
after **one day**. In a **public GitHub repository**, authenticated GitHub users
with repository read access may be able to download this sample. It is
not distributed via the podcast feed, Pages or Releases. The sample
includes a required ElevenLabs attribution file. The daily workflow
is unchanged.

The test uses `eleven_flash_v2_5` and MP3 44.1kHz/128kbps, which is
normally available on the free tier when the selected voice is eligible.
Voice permissions, available credits and model access are decided by
ElevenLabs and may produce HTTP 402/403/429. This test does **not**
automatically retry or switch models. Read-only diagnosis never spends voice-generation credits. Only an
explicit generate_sample run attempts to synthesize audio, typically
costing 0.5-1 credit per character if eligible.
The code rejects a known free-tier Voice Library mismatch before
generating audio. HTTP 402 means either a credit, billing or plan
restriction; the error reason is summarized from allowlisted API codes,
without exposing raw provider response data. A community Voice Library
voice cannot be synthesized using ElevenLabs' free API, even if it
works inside the ElevenLabs website. Choose an API-eligible premade
voice or upgrade only after assessing the account terms.

**License:** Free-plan generated speech is restricted to **noncommercial
use with attribution**. This is a noncommercial voice evaluation only, not approved
for distribution or monetization. To use ElevenLabs in the published
First Light podcast, first verify the selected voice's commercial
license and pay for the appropriate plan. A separate reviewed change
would be required to replace Gemini Charon.


## Compare free API-compatible ElevenLabs voices (manual, no production changes)

Use [ElevenLabs Free Voice Comparison (Manual Only)](
.github/workflows/elevenlabs-free-voice-compare.yml) on **main**.
Select **discover_only** first. It uses authenticated GET metadata requests
to find only your account's listed **Default** voices from a small First
Light shortlist: Daniel (British male newsreader), Brian (warm male
narrator), Chris (approachable male), and Alice (polished female). It also
counts any personally generated **Voice Design** voices, without printing
their private IDs or names. This mode uses **zero TTS generation credits**.

**Important: Default voices are scheduled to disappear on December 31,
2026 and are available only to accounts created before March 2026.**
The Infinity replacements are **Voice Library** voices, not guaranteed
free-API substitutes. ElevenLabs blocks Voice Library voices through
the free-tier API, even when they are playable on its site. A listed
Default voice is an eligibility hint, *not* proof that synthesis will work.

If discovery lists an eligible classic voice, rerun with
**mode = audition_one** and **candidate = daniel, brian, chris or alice**.
The code checks the actual account's default-voice list before sending
a single bounded **737-character** Flash v2.5 synthesis request. One
run samples one voice only, and the MP3 is uploaded as a short-lived
GitHub Actions artifact, **never** to the podcast feed or public site.
Multiple auditions consume more credits. Unavailable/paid/community
voices are blocked before a synthesis request when the metadata
identifies them.

**More durable free-plan alternative:** ElevenLabs offers three free
Voice Design slots for creating personally owned generated voices.
Create one in ElevenLabs under **Voices → My Voices → Add a new voice →
Voice Design** (the preview consumes credits). To test that voice in
this repository without overwriting your existing
`ELEVENLABS_VOICE_ID`, save its ID as a *separate* GitHub Actions secret
`ELEVENLABS_AUDITION_VOICE_ID`. Then select **audition_one** and
**candidate = custom**. This path requires read-only API confirmation
that the voice belongs to your account and was generated with Voice
Design, not borrowed from the Voice Library.

Both types of auditions use the same short original script and
`eleven_flash_v2_5` synthesis settings for a fair listening comparison.
Do not use ElevenLabs Free outputs for commercial podcast distribution.
Free samples require attribution; artifacts are retained one day and
may be downloaded by people with repository read access. Gemini Charon
remains the **only** production voice. No automatic substitution occurs.

Reference: [Default voice retirement](https://elevenlabs.io/docs/help-center/product/voices/my-voices/what-are-default-voices),
[Voice Library access](https://elevenlabs.io/docs/eleven-creative/voices/voice-library),
[Voice Design](https://elevenlabs.io/docs/eleven-creative/voices/voice-design).


## ElevenLabs narrator configuration (November 25, 2026)

- **Primary:** Brian, classic Default ID `nPczCjzI2devNBz1zQrb`.
- **Backup:** Daniel, classic Default ID `onwK4e9ZLuTAKqWW03F9`.
- **Model:** `eleven_flash_v2_5`.
- **Credentials:** GitHub Actions secret `ELEVENLABS_API_KEY` already
  exists. Existing `ELEVENLABS_VOICE_ID` remains unchanged and is **not**
  used by the production pipeline; its Voice Library restrictions do not
  affect Brian and Daniel.
- **Optional setting:** repository variable `FIRST_LIGHT_NARRATOR` uses
  `elevenlabs` by default, or `charon` for an explicit switch back.
- **Publication:** Full-episode verification before any release or Pages
  update. Only the selected narrator is recorded, with free-plan attribution.
- **Quota:** Free 10,000 credit monthly cap will not support daily 5–7
  minute shows. This is a functional pilot, not a financially sustainable
  full-month rollout. We will need sufficient ElevenLabs capacity or an
  explicitly selected alternate narrator/plan. Neither is purchased
  automatically.
- **Retirement:** Both classic voices end December 31, 2026. Plan a
  permitted replacement before then.

[ElevenLabs free-plan licensing](https://elevenlabs.io/docs/overview/administration/billing)
· [Default voice retirement](https://elevenlabs.io/docs/help-center/product/voices/my-voices/what-are-default-voices)

## November 25, 2026: original broadcast storytelling and readable transcripts

**What we're borrowing as editorial principles:** strong news leads, an
intelligible story arc (reported development → sourced context → what is
actually known to come next), meaningful transitions, depth for two world
leads, concise distinct briefs, and a quick conversational sign-off.
This is an **original one-presenter** newsroom format, not an imitation
of an existing broadcaster's language, journalists, interview format,
production cues, or sound design. No unsourced claims, invented quotes,
fabricated conversations, or invented reasons why a development matters.

The Gemini writing prompts for First Light now explicitly prioritize
whole stories, coherent transitions and an informative lead sentence.
The original news evidence gate and word-budget limitations remain in
place. If Gemini writing fails, the deterministic source-only script
**omits** truncated publisher summaries instead of reading a chopped-off
sentence as news, and keeps its own source attribution. It may then be
shorter; the system never pads with unsupported details.

The **web transcript** is presentation-only: chapters for Introduction,
World Headlines, Around the World, Business & Markets, Science,
Technology & Cybersecurity, San Antonio Weather and Closing Notes when
those spoken markers exist. Generated news text with fewer distinct
transition markers gets correspondingly broader sections, plus
readable paragraphs. The wording of the spoken script, MP3 and plain
transcript asset are unchanged by the display renderer.

The site has linked topic navigation, accessible HTML headings,
readable paragraphs, a 70-character text measure, mobile-friendly
typography, and HTML escaping of publisher content. **No chapter
timestamps** are invented because the current audio has no source-grounded
word-level time alignment.

### Refresh the existing published transcript without spending credits

Run [Refresh Published Transcript Layout (No TTS)](
.github/workflows/refresh-transcript-layout.yml) from GitHub Actions
on the **main** branch, using **Run workflow**. It fetches the currently
published site's exact MP3, RSS, source evidence, JSON metadata, cover
and other generated site files, then changes **only index.html**. It
refuses to deploy if required published assets are missing or the audio
doesn't match the current episode date. All non-HTML site file bytes
are checked for unchanged hashes before deployment. The workflow
uses the daily production lock and no Gemini/ElevenLabs APIs.
It does not create a new GitHub Release or rewrite old episodes.

Future daily broadcasts automatically use the new web transcript
renderer and the improved original storytelling prompts. Scripts still
depend on available RSS/official-source evidence: an AI-generated
script is not independently fact-checked simply because it sounds polished.


## Editorial Quality 3.1: selection, depth and Brian delivery (November 2026)

First Light aims to be an original, engaging *single-host* news briefing.
The highest-priority world stories should be important and well explained,
not just catchy headlines. No material from another broadcaster's
transcripts is included in production scripts or prompts.

### More discriminating story selection

- Historical-repeat suppression, significance, source variety and geographic
  diversity remain the primary factors in the story rundown.
- A new capped **0–6 point explainer-readiness bonus** rewards complete,
  distinct RSS reporting rather than raw headline length.
  Incomplete/abruptly clipped summaries do not receive this additional
  bonus. A major breaking development can still make the lead slot when
  reporting is sparse.
- The selector applies a stronger soft penalty against assigning
  two near-identical world headlines to the lead slots.
- Story metadata records its complete-summary count separately from
  source-publisher counts. Multiple similar publisher headlines are
  **not** treated as independent verification.

### More disciplined story depth

- Story plans label **supported explainer** versus **brief only**.
  Sparse world leads get a shorter advisory word budget rather than an
  invitation to invent background or consequences. Complete attributed
  evidence and actual official documents can support longer reporting.
- New advisory, non-gating presentation diagnostics track formulaic
  attribution, detectable section cues, and leads with limited context.
  A style score is not a substitute for accuracy checks. The review
  appears in the public latest.json metadata, alongside the existing
  quality and evidence audits.
- The Gemini writer still produces **two bounded sections** and is subject
  to the same numeric evidence checks. No additional model calls.

### More natural, cost-aware Brian delivery

- Duration planning now uses **approximately 153 words/minute**, based on
  Brian's measured 115-word/45-second audition, not Charon's historical
  163 WPM. Full episode timing remains governed by actual MP3 inspection.
- Brian uses slightly less rigid voice stability (**0.58**), similarity
  **0.78**, style **0**, and neutral speed **1.0**. Daniel keeps a steadier
  **0.64** stability profile as backup. These are proposed presets,
  not yet proven better by a listening comparison.
- Very short **Flash v2.5-compatible SSML pauses** are inserted at a few
  existing story-section boundaries. They are restricted to known
  transitions and remain absent from the public/plain transcript.
  No new facts, spoken words, music or fictional interview cues.
- The code counts **all SSML markup characters** in the conservative
  credit/character preflight. No extra TTS requests; existing Brian to
  Daniel quota safeguards and fail-closed behavior remain.

Offline tests check source fidelity, caps, timing estimates, no TTS
calls during tests, and that removing inserted pauses yields the
original spoken script. After deployment, evaluate one normally
scheduled broadcast for pacing, proper-noun pronunciation, story depth
and attribution before tuning further. Both voices are subject to
December 31, 2026 retirement and current plan limits.

References: [ElevenLabs pause guidance](https://elevenlabs.io/docs/help-center/product/core-capabilities/text-to-speech/how-can-i-add-pauses),
[voice speed settings](https://elevenlabs.io/docs/help-center/product/core-capabilities/text-to-speech/can-i-change-the-pace-of-the-voice).

## One-time editorial audio preview (requested November 25, 2026)

Use the **First Light Editorial Audio Preview (Unpublished)** GitHub
Actions workflow to review the new editorial writing and Brian delivery,
without releasing a replacement episode.

- The initial guarded preview runs **once**, when the workflow is first
  merged onto main with the exact commit marker. Other code commits do
  not trigger more previews; future manual reruns require workflow_dispatch.
- Runs all offline regression tests first. Then checks current sources,
  weather, memory, story selection, evidence, editorial script and QA
  metrics, followed by real Brian narration using the existing
  credit preflight and Daniel fallback if applicable.
- Real TTS **consumes credits** if the account has enough for the
  complete script. If insufficient, the TTS attempt is safely blocked
  and the transcript remains in the artifact for inspection.
- **Read-only repository permissions:** no writes to GitHub Releases,
  Pages, RSS, the published site or today's current MP3.
- The one-day Actions artifact named
  **first-light-unpublished-editorial-preview** contains the full
  source-grounded text, sources, diagnostics, readable HTML transcript,
  and the MP3 if speech synthesis and audio verification succeed.
- Public repository artifacts may be accessible to repository readers;
  free-plan ElevenLabs evaluation is noncommercial with attribution.
- Automated checks do not constitute independent factual verification.
  Listening remains necessary to evaluate pronunciation and storytelling.

## Newsroom 3.2: Pronunciation and evidence-backed lead stories

### Pronunciation review

The original transcript and fact-checked story evidence are **never**
modified by pronunciation fixes. Only Brian and Daniel's speech-only
payload is rewritten before ElevenLabs narration, and the current
conservative TTS credit preflight counts the actual modified text.

The small JSON glossary is at **config/voice_pronunciations.json**.
A reviewed rule consists of the original written city/person name,
a plain-language spoken alias, its category, and a source note. The
first city review candidates are Kyiv and Cartagena. An alias changes
whole-word/whole-name matches only, with safeguards against injected
SSML, control characters and duplicate terms.

**Do not guess unfamiliar people's names.** Check an authoritative
reading or the speaker's preferred pronunciation first, then commit a
reviewed new entry. Test the resulting sound: a plausible written
respelling does not guarantee the voice will pronounce it naturally.

For dates and time zones: a code is expanded only beside an actual
12-hour clock time. UTC and GMT, and common US Eastern/Mountain/Pacific
codes, get readable full names. CST/CDT/CT have several global meanings
and are expanded ONLY when the surrounding text is identified as local
San Antonio/National Weather Service weather reporting. Ambiguous IST,
BST and others remain unchanged instead of being guessed.

The unpublished test's **pronunciation_review** JSON lists which
approved names and clock time-zone expansions were applied, and which
abbreviations need human verification. Flash v2.5 uses plain aliases;
it does not support the same inline phoneme tags as Flash v2.

### Deeper world leads without padded reporting

- Trusted publisher RSS summaries retain up to **720 normalized
  characters**, rather than discarding text after 260.
- The two leading world stories may receive a maximum of four additional
  **complete** publisher summary sentences per story. No new network
  requests and no article-body scraping or copied full articles.
- Every added line must match its trusted original publisher feed
  summary **exactly**. Truncated fragments, suspicious links,
  duplicate sentences and missing source metadata are rejected.
- The added evidence may inform a longer story arc when genuinely
  meaningful. It never establishes independent factual verification,
  and an episode may still be below five minutes if reporting is thin.
- The existing numeric gate recognizes additional claims only after
  source validation. This does not grant authority to unsupported
  numbers or invented quotations.
- Edition metadata now counts extra complete RSS sentences available
  for lead narration, and the original article/link list remains visible.

This update does **not** change the primary narrator (Brian),
eligible backup (Daniel), the current free-plan cap, voice retirement
date, publication schedule or current podcast assets. All live audio
testing remains opt-in and subject to remaining voice credits.


## Newsroom 3.3: stronger openings, careful follow-ups, pacing, local pronunciation

This editorial and presentation pass is designed for a **single narrator**,
Brian, with Daniel as the existing eligible backup. We are adapting useful
newsroom principles, not copying any other news podcast's script or format.

**20-second opening.** The existing first Gemini source-gated writer
request is now instructed to begin with a labelled 20–36-word PREVIEW of
the actual two leading stories, then STORY: and its regular narrative.
The writer's output is parsed: the markers are never spoken or published.
Unstructured or invalid previews are rejected as hooks and the world
story simply plays normally. There is **no additional model call** and
all preview claims pass the same current-source numeric checks. The
AI-assistance/source disclaimer stays in the spoken introduction.

**What changed since the last episode.** Prior release headlines remain
low-confidence editorial memory, not historical evidence of events.
Story research includes a deterministic 'possibly continuing story'
advisory when earlier coverage exists. The prompt explicitly forbids
claiming progress or news changes just because two headlines differ.
The only valid reason to say a development changed is current-day
source material that actually describes that development. No automatic
independent verification is claimed.

**Editorial pacing.** Two world leads get the strongest opportunity for
supported explanation, while around-the-world briefs cap at 88 advisory
words and business/science/tech briefs at 112. Word caps are never
minimums. The script stays shorter if actual sources are too thin.
The editorial pacing plan is preserved in writer diagnostics. Audio
runtime is still checked against the real MP3 after synthesis.

**Episode packaging.** The two source-linked world lead headlines also
generate a bounded, source-faithful editorial episode title. It appears
on the site, in latest.json, and on **new** RSS items through a versioned
title marker in each GitHub Release. The canonical RSS GUID, episode
audio URL and earlier episode titles remain unchanged. HTML and XML
escaping protect against unsafe source strings. No fake source material
or chapter timestamps are invented.

**San Antonio weather pronunciation.** The reported issue concerned
Brian saying the city name near the end. The TTS-only renderer now
offers a tentative, reversible weather-section reading:
'San An-TOH-nee-oh'. The actual intro, episode transcript, RSS and
website still say **San Antonio**. It only targets the controlled
weather marker and later local-weather references, not ordinary world
news quotations or the greeting. This is an **audio hypothesis**,
not a confirmed pronunciation fix. After listening to an unpublished
preview, set repository Actions variable
FIRST_LIGHT_SAN_ANTONIO_PRONUNCIATION to 'original' to revert it,
or 'guided' (default) to retry it. Both daily and preview workflows
honor that variable. Additional personal names are never guessed.

**Acceptance.** The offline suite tests cold-open parsing, safe
continuity, source-linked titles, weather-only city alias and reversal,
stable podcast GUIDs, Brian/Daniel selection, zero extra model calls,
and nonpublication during test previews. A one-time, guarded,
unpublished 3.3 preview may run on merge after CI; it uses live provider
credits **only when the existing budget check permits it**. Its artifact
expires after a day and can be listened to before further production
changes. The audio and public episode are never overwritten by preview.


## Newsroom 3.4: Research Desk and legacy voice transition audit

### Research Desk: stronger but evidence-faithful reporting

- Source discovery now includes four additional HTTPS RSS news providers:
  **Deutsche Welle, France 24, ABC Australia World and PBS News**.
  Their story URLs must resolve to the actual publisher's allowed
  domain before they can enter the source selection pool.
- Existing per-feed byte limits, freshness windows, minimum-source
  requirements, per-publisher caps, duplicate removal and machine
  evidence checks remain in force.
- `src/research34.py` builds **up to two lead-story research cards**
  from already curated claims, extra *complete* RSS sentences, and
  issuer-authorized official-document extracts. It checks links and
  exact supporting text. No additional page scraping or model calls.
- Claims are labeled as what publishers/issuing agencies **said**.
  Exact source matching is not proof the underlying event occurred.
  No claim is labeled independently fact-checked.
- The existing two Gemini writing calls receive the lead research
  cards and explicit instructions not to invent causes, consequences,
  quotes, interviews, or future outcomes.
- After drafting, a deterministic editorial check flags thin sourcing,
  repeated reporting, source diversity and short sections. Wording
  that falsely claims First Light personally conducted interviews or
  independent fact checks is rejected, forcing the source-only
  fallback. A length target is never a license to pad with fake news.
- New diagnostics appear in latest.json and in the **unpublished
  editorial audio preview** artifact, plus the release evidence notes.

Public-source RSS coverage is not a substitute for field reporting.
If major primary feeds fail, the episode is short or skipped rather
than invented. New RSS publishers are accepted only if their links
and attribution pass the existing checks.

### ElevenLabs replacement-voice audit: no production changes

ElevenLabs documents that original Default voices retire **December
31, 2026**. Its recommended successors are:

| Production now | Proposed replacement | Replacement voice ID |
| --- | --- | --- |
| Brian | Sawyer - Midnight Storyteller | 8dEUmyPMdDdK91vboYih |
| Daniel | Finley - Articulate Anchor | fnYMz3F5gMEDGMWcH1ex |

These replacements are in the **ElevenLabs Voice Library**, which
ElevenLabs restricts for Free-tier API access. They may appear in the
web application while the GitHub TTS API cannot use them.

Open **ElevenLabs Voice Retirement Read-only Audit and Manual Auditions**
under GitHub Actions:

1. Select `audit_only` first. The workflow makes only three
   authenticated GET requests: subscription, Sawyer metadata and
   Finley metadata. It logs only plan/access categories, not secrets,
   raw responses, or exact balances. The one-time branch merge can run
   this same **read-only** audit automatically.
2. If the API key reports an eligible **paid** plan and at least
   one full audition's conservative credit allowance, run
   `audition_one` with either `sawyer` or `finley`. This issues
   exactly one bounded Flash v2.5 request with the existing original
   sample, then checks the MP3 via ffprobe. The result stays in a
   short-lived, unpublished Actions artifact. A disallowed free plan,
   missing metadata, or missing credits stops before TTS.
3. Listen to both recordings and check narrative character, city and
   person names, technical acronyms, San Antonio and local weather
   pronunciation. Human acceptance must be **explicit**, and a
   publishing/commercial license must be confirmed *before* any
   production transition. Passing technical audio checks is not
   listening approval.

**Production will remain Brian primary, Daniel backup** unless a
separate, specifically approved future PR changes it. No credentials
or production voices are rewritten by this feature.

### Licensing and realistic credit capacity

Current published monthly tiers (November 2026; confirm at checkout):

- Free: $0, 10,000 credits; noncommercial audio with attribution.
- Starter: $6, 30,000 credits; includes a commercial license.
- Creator: $22, 121,000 credits.
- Pro: $99, 600,000 credits.
- Flash v2.5 API usage may cost around 0.5–1 credit per character,
  depending on the plan/route. Treat 1 credit/character as a
  conservative budget until the user account confirms actual use.
- A 5–7-minute daily episode might use roughly 4,000–6,000
  characters: 120,000–180,000 input characters across 30 days,
  about 60,000–180,000 credits depending on the discount.
  These are planning scenarios, **not** promises of exact prices or
  enough credits. Starter is too small for that scenario, and
  Creator is enough only in the lower-credit scenarios. Backups
  and failed retries may consume additional credits.

Sources: [ElevenLabs Default-voice retirement](
https://elevenlabs.io/docs/help-center/product/voices/my-voices/what-are-default-voices),
[ElevenLabs pricing](https://elevenlabs.io/pricing),
[Voice Library API limitations](
https://elevenlabs.io/docs/overview/capabilities/voices).

The initial Research Desk changes and auditing code run offline tests
before merging. An optional one-shot **unpublished** newsroom preview
can validate actual generation without touching Releases, RSS or Pages.
No paid upgrade, automatic library voice audition or production voice
switch is performed.
