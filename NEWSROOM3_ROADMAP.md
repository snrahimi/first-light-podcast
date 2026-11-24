# First Light: Newsroom 3.0 (Phases 3A, 3B, 3C, 3D)

**Status:** Implemented on branch; a passing GitHub CI workflow verifies code
behavior. A new *live* end-to-end podcast production run after merge remains
the required acceptance test. No human fact-checker is supplied.

First Light is a short, AI-assisted broadcast, not an independent newswire.
The automated system now prepares traceable source excerpts for the writer.
**An exact excerpt verifies what a source published; it does NOT independently
verify the real-world truth of the claim.** Related headlines cannot establish
independence of factual reporting.

## 3A — Better discovery and primary sources

- Existing publisher RSS: BBC, NPR, The Guardian, and Al Jazeera.
- Add recent NASA official news-release RSS for science, and Bureau of Labor
  Statistics (BLS) latest-numbers RSS for economic information. Retain short
  attributed headline/description excerpts; do not republish full reports.
- Add CISA's machine-readable Known Exploited Vulnerabilities catalog for
  recent newly-added entries. CISA provides dateAdded (day granularity), not a
  guessed minute-by-minute time.
- Use one keyless, rate-limited, bounded GDELT DOC 2.0 search per episode for
  multilingual international *discovery leads*. Domain-filter and mark these
  as discovery_only. **Never pass GDELT discovery leads as factual evidence**
  to the scriptwriter, and do not redistribute its generated index.
- If a free source times out, fail that optional source closed; retain existing
  trusted RSS sources so the episode can still be produced. Domain checks
  protect publisher identity and forbid plain HTTP article links.

Official references:
- https://www.nasa.gov/rss-feeds/
- https://www.bls.gov/help/hlp_rss.htm
- https://www.cisa.gov/known-exploited-vulnerabilities-catalog
- https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
- https://www.gdeltproject.org/

Publisher feed permissions and source-specific terms still apply. Links are
primarily provided to let listeners read the original reporting.

## 3B — Research dossiers

Each selected story receives a compact structured research card:

- Headline, category, publisher, original source URL, publication timestamp.
- Short exact attributed title/summary statements from the feeds.
- Links to related publisher reports on the same *topic*.
- Source type: publisher report versus official primary-source record.
- Previous episode's headline/date for continuity, with a warning that an
  actual new development has not been confirmed.
- Evidence limitations and explicit uncertainties.
- Optional GDELT leads as separate discovery_only links, not writing material.

Dossiers are generated from source metadata rather than scraping paywalled or
unlicensed article bodies. This limits detail, but protects against invented
context and excessive reproduction of journalism.

## 3C — Claim-level evidence ledger and safeguards

- Each candidate factual excerpt must exactly match one linked publisher or
  official feed headline/description. If a claim diverges from its source text,
  the dossier fails validation before audio generation.
- All claims are tagged attributed_publisher_report or primary_statement;
  none is falsely labeled independently_verified.
- The script is rejected if it adds new *digit-form* figures not present in
  the supplied source/weather data and current publication date, or falsely
  claims that reporting was independently fact-checked.
- Quality controls also validate show identity, script length (for AI-written
  episodes), MP3 codec/bitrate, and plausible audio duration.
- A machine-readable public evidence file ships with the episode:
  **first-light-YYYY-MM-DD-evidence.json** as a GitHub Release asset,
  and **evidence.json** on the latest public GitHub Pages site.
- Public source audit and correction links remain accessible.

**Limits:** The guard does not perform full semantic natural-language
entailment or detect unsupported facts written as *words* instead of digits.
The system cannot assert that every statement is true or corroborated by
independent full-text reporting. Editorial oversight is recommended for
consequential reporting.

## 3D — Higher-quality evidence-scoped script

- Gemini receives only the structured evidence cards, structured weather and
  old-topic context; GDELT discovery results are excluded from the prompt.
- The prompt prioritizes a tightly paced 5–7-minute show:
  two lead stories, regional briefs, business, science, technology and weather.
- Natural broadcast flow, concise attribution, verified dates, and a clearly
  disclosed AI-assisted production process.
- If the initial draft has 380–639 words, Gemini may attempt **one additional
  evidence-constrained rewrite**, with lower sampling temperature and an
  explicit prohibition on invented padding. No infinite regeneration loop.
- If the result violates source constraints or length/identity requirements,
  it falls back to an attributed, possibly shorter RSS script. Reliability and
  factual restraint are higher priorities than forcing a length.
- Gemini **Charon** is the sole approved published narrator. If speech
  synthesis is unavailable or hits its quota, the episode is not replaced
  with Kokoro Adam or Piper. The last good published podcast stays available.
  The voice service uses bounded transient retries and per-segment pacing.

### Cost and privacy boundaries

- Official RSS, public CISA JSON and keyless GDELT discovery require no
  purchasing a subscription in this workflow, but provider quotas/availability
  and source rights still apply.
- The script rewrite can **increase Gemini API requests**. Gemini use might
  incur charges if your project is on paid billing. Verify the model's
  free-tier support and billing configuration in Google AI Studio. This code
  is not a billing-enforced spending cap.
- Do not publish credentials or private source data. Episode audits are public.
- Disable optional GDELT calls via environment variable
  NEWSROOM_GDELT_ENABLED=false (GitHub Actions repository variable can be used).

## Delivery acceptance criteria and tests

The automated validation covers:
1. Publisher URL and domain lookalike defenses.
2. Optional GDELT source failure and lead-only behavior.
3. NASA official feed and CISA dateAdded parsing.
4. Source enrichment without deleting regular RSS coverage.
5. Per-claim exact excerpt matching and tamper detection.
6. No unsupported number claims, including date comma punctuation.
7. Bounded Gemini short-script rewrite.
8. Existing weather/network outage recovery, voice tests, MP3 inspection,
   release feed generation, and both supported Python entry points.

After merging, run a **new** GitHub Actions daily workflow on main and verify:
- Successful live source fetch and no accidental paid API calls.
- Expected selection of up to seven topical stories, official primary sources
  used when relevant, and discovery leads *not* read as facts.
- Charon narrator must be used (publication fails otherwise), and audio
  targets 5–7 minutes where enough supported evidence exists. The script
  may be shorter when source metadata is sparse.
- Public evidence.json contains original source URLs and no independently
  verified claim counts unless independently validated evidence exists.
- GitHub Release assets, RSS and Pages deployment complete successfully.

## Integration update: Phases 3.3 then 3.2

The work was implemented and merged in separate, CI-validated pull requests:
- [Phase 3.3 research integration](https://github.com/snrahimi/first-light-podcast/pull/5): official UN Press, NASA and BLS source discovery; up to three limited official-page excerpts; exact source checks and cautious cross-outlet comparison. These are **attributed official statements**, NOT independent factual verification. Third-party articles and GDELT leads are not fetched as factual source texts.
- [Phase 3.2 broadcast composition](https://github.com/snrahimi/first-light-podcast/pull/6): two bounded Gemini text requests with non-overlapping assignments (world news versus business/science/technology), controlled opening, deterministic San Antonio weather and closing; full numeric evidence checks, conservative fallback, and a calibrated 163-words/minute Charon duration estimate.

Observed baseline prior to the changes: 657-word Charon narration took about 242 seconds. The new script target is approximately 925 words (about 5:40 at that measured pace), **only when source evidence supports the content**. The code reports a shorter honest script rather than padding it with imagined context. Audio duration is measured after speech synthesis, not assumed from word count.

Human verification, licensed independent full-text investigations, and editorial sign-off are **not** supplied by this system. This remains an AI-assisted attributed morning briefing with published provenance and corrections.

## Live acceptance result: November 24, 2026 (UTC)

[Full production workflow](https://github.com/snrahimi/first-light-podcast/actions/runs/45330983846) ran on main with actual feeds, Google text generation, Gemini Charon speech, GitHub Release publication and GitHub Pages deployment. The workflow completed successfully.

- **Audio:** Gemini Charon, two of two narration segments, measured duration 252 seconds (4:12), MP3 ~192 kbps. This was an acceptable technical release but **not** within our 5–7-minute editorial objective.
- **Script:** Source-attributed deterministic fallback, 629 words. The first Phase 3.2 Gemini world section failed its acceptance gate; it therefore did not get an on-air two-part segmented script on this run.
- **Discovery:** 18 official feed items, zero GDELT discovery leads (optional service timed out). BLS feed was unavailable. The selected story audit contained 16 attributed claim snippets, not independently verified facts.
- **Deeper context:** 0 official webpages successfully inspected from chosen story URLs. The Phase 3.3 feature is implemented but its extra-document benefit was not demonstrated in this run.
- **Publication:** GitHub Release, evidence JSON, transcript, podcast RSS and GitHub Pages deployment completed.

[Follow-up PR #7](https://github.com/snrahimi/first-light-podcast/pull/7) adds safe section-word diagnostics, accepts genuinely useful shorter drafts when the complete evidence and broadcast quality gates pass, and reports how many agency document fetches were attempted. It passed offline tests but **has not yet passed a new live episode test**.

These distinctions matter: an end-to-end production success is not the same thing as reaching the editorial duration, independent verification, or research-enrichment goals. None of those gaps should be disguised by filler.


## Follow-up milestone: selected-story evidence and length preflight

After the November 24, 2026 live run confirmed Phase 3.2 and Charon
publication worked but yielded a 529-word, 3:08 episode:

1. Enrich the selected leads with high-overlap attributed RSS headlines
   and summaries from the *existing trusted feeds*, including primary
   agency statements when relevant. Cap extra source links per story,
   reject unrelated/impersonated sources, and audit every excerpt.
2. Tell the two-part Gemini writer what distinct evidence supports each
   story, with advisory lead/brief word budgets and hard instructions
   against padding, speculation or fabricated consequences.
3. Warn before narration when estimated Charon runtime is below five
   minutes. Publish the shortfall and exact new-source counts in latest.json
   so a short result is visible, not mistaken for a completed duration goal.

This is a code milestone; a fresh live run is still required to confirm
how much usable extra reporting is actually found and whether the
published narration reaches the target.

## Roadmap after Newsroom 3.0

| Milestone | Status | Next acceptance checkpoint |
|---|---|---|
| 3.1 Charon-only reliability | Code completed, one successful Charon baseline broadcast | Confirm quota headroom and ≥95% on-time delivery across 30 days |
| 3.3 Deeper official-source context | Implemented, live page enrichment not yet successful | Diagnose zero additional agency pages; expand legally usable documents; add a human fact-review procedure |
| 3.2 Segmented broadcast writing | Implemented, latest live episode used fallback | Validate the #7 fixes with a fresh run; achieve evidence-supported 5–7-minute scripts without repetitive filler |
| 3.4 Quality operations | Planned | Automatic missed-episode alert, measured duration trends, pronunciation review and correction tracking |
| 4.0 Listening experience | Planned | Mobile-first website, searchable archive, accessible player and source-linked transcripts |
| 4.1 Podcast distribution | Planned | Validate audio byte-range and RSS with Apple Podcasts and Spotify |
| 5.0 Personalization | Planned | Optional city, topic and listening-length preferences with privacy safeguards |
| 6.0 Audience growth | Planned | Privacy-conscious listening metrics, feedback and sustainable distribution |

**Immediate sequence:** validate a live Phase 3.2+3.3 episode, review its facts and actual duration, and tune from measured results. Avoid new voices, new paid APIs, or claims of independent fact-checking without evidence.
