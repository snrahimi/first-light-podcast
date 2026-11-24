# First Light corrections and editorial standards

First Light: World Report is an automated, AI-assisted briefing. Publisher
headlines and short RSS summaries are used to discover stories, but **similar
headlines are not independent fact-checking**. A single-source claim must be
attributed. Important claims should be reviewed against original sources.

## Report an issue

Use the [public correction request form](https://github.com/snrahimi/first-light-podcast/issues/new/choose).
Include episode date, approximate timestamp, inaccurate claim and a reliable
source supporting a correction. Do not include confidential information.

## Correction process

1. Check the claim against the linked publisher report, an independent
   credible source or a primary document. Where disagreement remains,
   explain the uncertainty instead of claiming false certainty.
2. Fix the recording or publish a clearly dated correction note as warranted.
   If republishing the audio under the same episode tag, disclose the revision
   prominently in the release notes, and avoid silently rewriting history.
3. Mark the issue resolved with the corrected wording, supporting sources
   and date. For serious errors, include a correction in the following episode.

**Status:** This process is documented, but requests are not automatically
reviewed or resolved. It relies on the repository owner to review public issues.

## Editorial checks built into production

- News feed source domains are checked against known publisher domains.
- Headline publication times must be recent, with dates preserved in notes.
- Similar reports from different outlets are listed as related evidence,
  not proof that all details agree.
- A seven-day memory of published topics helps avoid repeating unchanged news.
- Gemini scripts are instructed to attribute claims and avoid unsourced
  statistics, quotes, market values and speculative context.
- Extreme script lengths, incomplete audio and implausible durations are blocked.
- Only Gemini Charon is allowed for narration. If Charon cannot produce
  verifiable audio, publishing stops; no alternate voice is substituted.
- Package 2+ publishes operational metadata and automated editorial *flags*
  about duration, evidence depth, repetition and sensitive claims. These are
  not a substitute for human fact checking.
- The free GitHub watchdog checks release presence and essential MP3,
  transcript and audit assets after the scheduled episode time.
- The public 30-day production dashboard reports only metrics actually
  observed and marks older episodes without metadata as unknown.

No automatic system can guarantee a story is free from error. Verify
consequential news with the original linked reporting.


## Release revisions and audit boundaries

Every newly created release contains a revision marker. If a same-date
release is regenerated, its show notes explicitly record the revision number
and UTC time. **The prior MP3, transcript, source-audit JSON and release notes
are archived with revision-numbered filenames before the current files are
replaced.** If archiving fails, replacement is blocked. This revision log
documents publication changes, not an independently reviewed correction.

Corrections to consequential claims require a human investigation, a dated
explanation, and supporting original sources. Never silently change a quote,
claim or attribution and describe the automated source check as verification.
For an auditable correction, link the public correction issue to the
specific revised release and archive the supporting evidence. Release
versioning does not verify the correction's factual accuracy.

## Delivery watchdog

The separate GitHub Actions watchdog runs at 6:15 AM America/Chicago,
checking that the expected daily release and required files exist. A failure
produces a GitHub Actions failure and a deduplicated GitHub issue for review.
An outage or delayed GitHub API response can trigger an alert even when an
episode exists; investigate before assuming publication failed.
