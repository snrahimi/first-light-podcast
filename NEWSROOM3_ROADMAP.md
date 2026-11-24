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
- The previously approved Gemini **Charon** narrator remains primary.
  Local Kokoro FP16 Adam and Piper remain no-cloud backups.

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
- Charon narrator actually used and audio target of 5–7 minutes where enough
  supported evidence exists; shorter fallback clearly logged if insufficient.
- Public evidence.json contains original source URLs and no independently
  verified claim counts unless independently validated evidence exists.
- GitHub Release assets, RSS and Pages deployment complete successfully.

## Roadmap after Newsroom 3.0

| Next milestone | Focus | Measurable acceptance |
|---|---|---|
| 3.1 Live operational hardening | Run post-merge end-to-end test; verify quota and publication timing; maintain incident logs | 30 daily checks, >95% published by 4:45 AM Central |
| 3.2 Deeper verified context | Contractually permitted full-text/primary records and human-reviewed claim selection | Major explanatory statements traceable to appropriate evidence |
| 4.0 Listening experience | Beautiful mobile-first site, archives, searchable transcripts, clear source/audit views | 100% episodes have playable audio and source-linked pages |
| 4.1 Podcast distribution | Check byte-range audio and validate feed for Apple/Spotify | Submission passes platform requirements |
| 5.0 Listener personalization | Optional city, topics and lengths, without sacrificing basic world coverage | Settings work without collecting unnecessary personal data |
| 6.0 Growth | Real listener feedback, subscriptions, privacy-conscious stats | Measure retention and corrections without inflated claims |

The first priority is **3.1**, not premature expansion to more voices or
additional platform integrations. Quality first, then audience reach.
