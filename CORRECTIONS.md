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
- The requested Gemini Charon voice is logged, with a clearly documented local
  fallback when TTS quota or service access fails.

No automatic system can guarantee a story is free from error. Verify
consequential news with the original linked reporting.

