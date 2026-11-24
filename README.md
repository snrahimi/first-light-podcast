# First Light: World Report 🎙️ Free Edition

Automated 5–7-minute morning world news, business, science, technology and San Antonio weather podcast. Scheduled for 3:30 AM America/Chicago to prepare ahead of 5 AM.

**This active daily workflow does not call paid OpenAI or ElevenLabs APIs.** It uses public news RSS feeds, local Kokoro speech (Piper backup), and optionally Gemini API's Free tier to write a better broadcast script.

## Add your optional Gemini Free tier key

1. Open Google AI Studio: https://aistudio.google.com/apikey
2. Select or create a project with Gemini API Free tier access. Check the project's billing status. Do not enable paid billing if your goal is zero cost.
3. Create an API key and copy it.
4. Open this repository's GitHub Actions Secrets: https://github.com/snrahimi/first-light-podcast/settings/secrets/actions
5. Choose New repository secret. Enter the exact name GEMINI_API_KEY and paste your key into the secret value. Save.
6. Never paste the key into chat, Issues, README files, public code, or GitHub Variables.

The workflow uses model gemini-2.5-flash-lite by default and prompts for approximately 760–890 spoken words. It passes only public RSS headline/summary text and public weather data to Gemini. No private information is sent.

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
- Open-source local Kokoro 82M ONNX speech with Piper TTS fallback, encoded to MP3 with ffmpeg.
- Episode archives in GitHub Releases, a podcast RSS feed and website in GitHub Pages.
- All GitHub Pages and Releases podcast content is **public**, not a private feed.

The old manual ElevenLabs narrator test workflow remains available but is not scheduled. Paid API secrets are not used by the daily workflow; remove them from GitHub if you no longer need them.

## Important limits

Free Gemini quotas/models can change. Free services can throttle or fail. A public news headline feed is not independently fact-checked, and the AI script can contain inaccuracies, so verify consequential reports with the linked original outlets. Publisher terms govern use of their feeds. GitHub Actions public-repository runner usage is normally free within GitHub's current terms, and the repository contents are public.
