# First Light: World Report 🎙️ Free Edition

Automated 5–7-minute morning world news, business, science, technology and San Antonio weather podcast. Scheduled for 3:30 AM America/Chicago to prepare ahead of 5 AM.

**The daily workflow uses no OpenAI or ElevenLabs APIs.** It uses public news RSS feeds, optional Gemini for the script, **Gemini 3.8 Flash TTS with the Charon voice as the preferred narrator**, and free local Kokoro FP16 (Adam) / Piper when Gemini narration is unavailable. Gemini use is subject to your project's billing configuration and applicable free limits.

## Add your optional Gemini Free tier key

1. Open Google AI Studio: https://aistudio.google.com/apikey
2. Select or create a project with Gemini API Free tier access. Check the project's billing status. Do not enable paid billing if your goal is zero cost.
3. Create an API key and copy it.
4. Open this repository's GitHub Actions Secrets: https://github.com/snrahimi/first-light-podcast/settings/secrets/actions
5. Choose New repository secret. Enter the exact name GEMINI_API_KEY and paste your key into the secret value. Save.
6. Never paste the key into chat, Issues, README files, public code, or GitHub Variables.

The workflow uses the newer `gemini-3.5-flash-lite` by default, and tries `gemini-3.1-flash-lite` when the selected model is unavailable (HTTP 404). Older Gemini 2.5 models can return HTTP 404 for newly created API projects. The workflow and prompts for approximately 760–890 spoken words. It passes only public RSS headline/summary text and public weather data to Gemini. No private information is sent.

If Gemini quota is exhausted, the model is unavailable, or the key is absent, a simpler, attributed, no-API script is used automatically. The fallback is less polished and might be shorter than 5 minutes. The spoken episode still uses free local narration.

Google may use Gemini Free tier content to improve products under its terms. A key attached to a paid Gemini project could incur charges; use a Free tier project and check the usage dashboard. Current info: https://ai.google.dev/gemini-api/docs/pricing

## First episode

1. Enable GitHub Pages at https://github.com/snrahimi/first-light-podcast/settings/pages and select GitHub Actions as its build source.
2. Open https://github.com/snrahimi/first-light-podcast/actions/workflows/daily.yml and choose Run workflow.
3. Check the workflow logs and verify that a fresh GitHub Release contains an MP3. A production run can fail if RSS/voice model downloads are unreachable, source coverage is sparse, or Pages hasn't been configured.
4. Once successfully deployed, visit https://snrahimi.github.io/first-light-podcast/ and check https://snrahimi.github.io/first-light-podcast/feed.xml

## iPhone wake-up playback

Add a Daily 5:00 AM personal automation in Apple Shortcuts. Retrieve https://snrahimi.github.io/first-light-podcast/latest.json, verify the date matches today in San Antonio, download audio_url, set volume and Play Sound. Test on a locked phone with your actual audio routing. Keep a separate phone alarm: GitHub scheduling or iOS automations may run late or fail.

## How the audio is produced

- Live headlines from BBC, NPR, Guardian and Al Jazeera news RSS, with date filters and linked sources; no copied full articles.
- Local San Antonio forecast from Open-Meteo plus an attempted National Weather Service alert check.
- Original narration generated using optional Free tier Gemini API or a simple attributed headline fallback.
- Preferred narration: the selected Gemini Charon voice via the configured `GEMINI_API_KEY`. Free local Kokoro FP16 voice `am_adam`, then Piper, are fallback narrators. Audio uses MP3 192 kbps with loudness normalization.
- Episode archives in GitHub Releases, a podcast RSS feed and website in GitHub Pages.
- All GitHub Pages and Releases podcast content is **public**, not a private feed.

The legacy ElevenLabs voice-test workflow was removed because the active podcast uses only free local voices. The daily workflow never uses paid OpenAI or ElevenLabs APIs; remove those legacy API secrets from GitHub if they are no longer needed.

## Important limits

Free Gemini quotas/models can change. Free services can throttle or fail. A public news headline feed is not independently fact-checked, and the AI script can contain inaccuracies, so verify consequential reports with the linked original outlets. Publisher terms govern use of their feeds. GitHub Actions public-repository runner usage is normally free within GitHub's current terms, and the repository contents are public.

## Weather service reliability

Open-Meteo requests have bounded connection/read timeouts and retry temporary network failures. If Open-Meteo remains unreachable, the script attempts an official National Weather Service period forecast. If both providers are unavailable, the podcast explicitly says weather could not be verified and does **not** invent temperatures, wind or precipitation. National Weather Service alert checks are separate and can also be unavailable. This allows the episode to continue even if a weather provider is temporarily down.

GitHub Actions were upgraded to Node.js 24-compatible releases for the daily pipeline and source validation.

## GitHub Pages artifact indexing fix

The upload can succeed before GitHub's Actions API reports the `github-pages` artifact to the deployment step. The production workflow grants `actions: read` and waits for the uploaded artifact to become visible (up to 90 seconds) before calling `deploy-pages@v5`. A separate `punycode` Node warning is nonfatal and originates within action dependencies.

## Gemini Charon voice and usage

The Charon audition was approved as the default daily narrator. The production workflow synthesizes the narration in sentence-aligned sections with the same model and voice configuration used in the audition, combines the resulting WAV sections, and encodes a 192 kbps MP3. If Gemini audio generation fails, Kokoro FP16 and then Piper run locally. **Google Gemini requests may incur charges if the API key is linked to a paid billing project**. Inspect the billing tier and usage limits of the project before enabling daily production. Free-tier availability and quotas can change.
