# First Light: World Report — Package 2+ Intelligent Newsroom

Implementation and acceptance ledger. Updated November 24, 2026.

**Scope:** 46 core proposed capabilities plus 7 strongly recommended
operational features. These are *capabilities*, not 53 separate deployable
services. "Implemented" means code exists with offline regression tests or
existing live production evidence. "Partial" means only some safeguards exist.
"Deferred" means not shipped, and is never presented as complete.

## Delivered in Package 2+

| Stage | Work | Pull request | Validation |
|---|---|---|---|
| 2+.1 | Resilient Gemini writer, bounded HTTP 503/5xx and connection retries, 429 fail-fast, same-evidence 12-hour section cache across workflows | #10 | 80 offline tests |
| 2+.2 | Conservative same-event paraphrase matching, evidence-depth curation bonus, freshness and high-stakes review dossiers | #11 | 83 offline tests |
| 2+.3 | Public editorial scorecard, sensitive and disagreement flags, repeated-sentence detection, priority verified severe NWS notices, pronunciation | #12 | 88 offline tests |
| 2+.4 | 30-day publication dashboard, GitHub-only daily delivery watchdog and issue alerts, revision-labelled asset archives, correction request template | #13 | 96 offline tests |

### Core capabilities (46)

| # | Feature | Status | Implemented behavior / limitation |
|---|---|---|---|
| 1 | Smart Gemini 503 retries | Implemented 2+.1 | At most 3 requests per section; bounded delays and server/transport-only retries |
| 2 | Intelligent rate-limit handling | Implemented | 429 is not retried automatically; TTS has its own guarded quota logic |
| 3 | Section-level recovery | Implemented 2+.1 | Completed source-checked sections can be reused by exact evidence fingerprint |
| 4 | Script caching | Partial 2+.1 | 12h source+model prompt-fingerprinted, numerical-gate screened sections; not a human-verified script archive |
| 5 | Alternative Gemini text-model failover | Deferred | Must establish current free-tier eligibility and approve any model/cost implications |
| 6 | Safe fallback | Implemented | Source-attributed shorter RSS readout, no invented filler |
| 7 | Preserve previous audio on same-day rebuilds | Implemented 2+.4 | Revision-labelled MP3/transcript/evidence/notes archived before replacing assets; abort if archive fails |
| 8 | Trusted news aggregation | Implemented | Existing BBC/NPR/Guardian/Al Jazeera + agency feeds |
| 9 | Entity-aware matching | Partial 2+.2 | Headline impact-event and summary-token matching; no comprehensive named-entity recognition yet |
| 10 | Cross-publisher clustering | Implemented | Groups related headlines; never equates similar headlines with independent fact checks |
| 11 | Primary-source research | Partial | Official NASA/UN/BLS page extracts, bounded and publisher-attributed; coverage uneven |
| 12 | Deeper lead-story research | Partial 2+.2 | Prioritized selected leads and matched source excerpts; depth depends on available safe material |
| 13 | Freshness checks | Partial 2+.2 | Feed dates, recent-memory and labeled older coverage; no comprehensive background fact database |
| 14 | Source diversity | Partial | Publisher counts; independence or syndication is not automatically established |
| 15 | Copyright-aware research | Implemented | RSS/headline and bounded agency excerpts only, no full publisher-article scraping |
| 16 | Newsworthiness scoring | Implemented | Significance/freshness/impact and geographic factors |
| 17 | Evidence-depth scoring | Implemented 2+.2 | Modest capped ranking bonus; cannot suppress underreported breaking news |
| 18 | Breaking-news priority | Partial | Impact terms and sensitive-review flags; no live emergency desk |
| 19 | Geographic and subject balance | Implemented | Region diversity and world/business/science/technology rundown |
| 20 | Historical continuity | Implemented | Seven-day previous-edition headline memory |
| 21 | Flexible 7–9 stories | Deferred | Currently usually seven stories; changes require source/length evaluation |
| 22 | Claim-level attribution | Partial | Exact excerpt-to-source ledger; cannot prove arbitrary model paraphrases semantically |
| 23 | Disagreement detection | Partial | Different numeric tokens flagged for review, not proven contradictions |
| 24 | Uncertainty classification | Partial | Official statements, publisher reports, unknown verification status |
| 25 | Evidence sufficiency | Partial | Per-story evidence depth and advisory budgets; no independent reliability score |
| 26 | Public evidence trail | Implemented | Evidence JSON, original source URLs and publication notes |
| 27 | Two-part Gemini writing | Implemented | World leads/briefs then business/science/tech |
| 28 | Deeper lead storytelling | Partial | Advisory lead word budgets and supported detail prompts |
| 29 | Editorial word budgets | Implemented | Story plans; longer writing cannot be forced without source material |
| 30 | Natural transitions | Partial | Writing instructions and template handoffs, requires listening review |
| 31 | Context-rich narration | Partial | Source-led explanations only when evidence allows |
| 32 | Controlled script expansion | Deferred | Additional revision calls would consume quota; not approved as necessary yet |
| 33 | Repetition reduction | Partial 2+.3 | Repeated sentence flags, not automatic rewriting |
| 34 | Consistent broadcast identity | Implemented | Intro, date, AI disclosure, local weather and closing |
| 35 | Unsupported-number checks | Implemented | Strict digit-based source/weather evidence gate, not semantic verification |
| 36 | Attribution and quotation checks | Partial | Structured excerpts and model instructions; no reliable claim-by-claim semantic fact check |
| 37 | Duplicate-story checks | Implemented | Clustered and history-checked before selection |
| 38 | Estimated duration gate | Implemented | Charon ~163 WPM preflight with shortfall warnings |
| 39 | Editorial scorecard | Implemented 2+.3 | Public evidence counts, sensitivity/repetition/uncertainty flags and duration |
| 40 | Safe script acceptance | Partial | Source/number gates and fallback; no bounded correction model loop |
| 41 | Charon-only narration | Implemented | Gemini Charon only; no local narrator fallback |
| 42 | Audio integrity validation | Implemented | MP3 stream, bitrate, duration checked with ffprobe |
| 43 | Actual-duration tracking | Implemented | MP3 probe plus public release health metadata |
| 44 | Source-linked transcripts | Partial | Transcript plus per-episode source/audit links; not every transcript sentence linked |
| 45 | Automatic publishing | Implemented | GitHub Releases, feed XML and Pages |
| 46 | Production health dashboard | Implemented 2+.4 | Public health.json/html and rolling 30-day watchdog summary |

### Strongly recommended extras (7)

| Extra | Status | Implementation |
|---|---|---|
| A. Missed-episode / failure alerts | Implemented 2+.4 | Free 6:15 AM Chicago GitHub watchdog, failure status and one deduplicated issue per local day |
| B. Breaking-news safety checks | Partial 2+.2/2+.3 | Attribution instructions and high-stakes flags; human review is still necessary |
| C. Severe local weather priority | Implemented 2+.3 | Only priority severe NWS alerts from a successfully checked feed appear before the world briefing |
| D. Corrections and revisions | Partial 2+.4 | Issue template, documented human review, archived old assets and revision history; owner must still investigate |
| E. API usage and quota controls | Partial 2+.1/2+.4 | Writer requests/retries/cache hits recorded, hard retry ceilings, 429 fail-fast; provider-level quota/spend accounting not available |
| F. Audio/pronunciation QA | Partial 2+.3 | Common official acronyms and MP3 integrity checks; no full proper-name QA or automated clipping scan |
| G. Rolling 30-day quality report | Implemented 2+.4 | Completeness, Charon duration, fallback, official page and text-request metrics only for releases with health metadata |

## Acceptance roadmap

1. **CI and security:** 2+.1–2+.4 pass offline tests, no hidden paid
   APIs, no narrator substitution, no source-identity bypass.
2. **End-to-end production:** Run once on the merged main branch after
   the next natural feed refresh, avoiding repeated TTS quota use.
3. **Editorial acceptance:** Check selected-source enrichment, relevance,
   script mode, actual Charon duration, repeated wording and sensitivity
   flags in the release notes and evidence JSON. A short safe briefing
   remains allowed and visible.
4. **Delivery monitoring:** Check the 6:15 AM watchdog's GitHub Actions
   summary and issue behavior; do not count an issue as proof of an outage.
5. **Historical acceptance:** Accumulate 30 days of real per-release
   quality metadata, then evaluate 5–7-minute hit rate, fallback frequency,
   source depth and missed deliveries.
6. **Further editorial upgrades:** Add genuinely stronger primary-document
   matching, tested sentence-level attribution and better named-entity
  /event normalization before adding more LLM requests.

## Recommended but not yet implemented

- **Verified free-tier text-model failover.** Do not add a paid model or
  change approved narration providers without explicit consent.
- **Optional 8–9-story expansion and targeted supported script rewrites.**
  Requires further quality checks and strict free-tier request budgets.
- **Human-supported fact review and corrections queue.** Automated scoring
  and matching cannot verify causal claims, casualty counts, election
  statements, quotes, source independence or true contradictions.
- **More extensive legally permitted original-source research.** The
  currently allowlisted agency types leave gaps for many world stories.
- **Per-sentence transcript source references and independent headline
  corroboration.** Existing show notes are source-linked by story, not
  citation-verified sentence by sentence.
- **Provider-side Gemini API quota/spend reconciliation, automatic audio
  clipping detection and proper-name pronunciation review.** Current
  monitoring observes requests and file structure but cannot guarantee
  provider bills or audio articulation.
- **Distribution beyond GitHub Pages/RSS and advanced listener
  personalization.** Intentionally deferred until broadcast reliability,
  editorial depth and release history are validated.

## Operational policy

- **Only Gemini Charon** may narrate.
- **No paid API or additional voice** is automatically enabled.
- **Do not invent claims or pad** scripts to reach 5–7 minutes.
- **No independent fact checks are asserted.** Source and number matching
  are automated provenance controls, not a human editorial judgment.
- **Manual same-day production runs now archive prior released assets.**
- **A failed publication or failed archive must not delete earlier audio.**
- Do not describe an offline CI pass as proof that a live episode reached
  the desired audio duration.
