# Ascent: personal job-application workspace

A private, approval-first workspace for a finance career move. Record vacancies, have Gemini score your professional fit against your résumé (with evidence and gaps), draft cover letters, and track every application. Ascent never submits anything for you.

It is a single web page with no server. Your profile, vacancies and history are stored in your own browser. Gemini is called directly from your browser with your own free key.

## Using it

1. **Open the site** (GitHub Pages link for this repository).
2. **Load your profile.** On the first screen, click *Load profile file* and choose your private profile file. It stays in this browser only; it is not uploaded anywhere.
3. **Connect Gemini.** Settings → paste your key from [Google AI Studio](https://aistudio.google.com/apikey) → *Save and check connection*. The check runs four steps (key received, Google accepts it, model available, test answer) and tells you exactly which step fails and why.
4. **Add a vacancy.** Paste the full listing. *Fill fields with Gemini* is optional.
5. **Analyse fit.** On the vacancy's page, read the fit schedule, strengths, and gaps. Work authorization is assessed separately and never lowers the fit score.
6. **Decide.** Change the status yourself. "Applied" only records that *you* submitted.

Items shown as **[●] highlighted** are open points: facts Ascent does not have and will never guess.

## Phone and laptop

Data does not sync between devices. Use Settings → *Export backup* on one device and *Restore backup* on the other. Backups contain your résumé, so keep them private. They never contain your API key.

Backups from the earlier ChatGPT-hosted Ascent (version 1) can be restored here too.

## Staying at $0

- Use a key from a Google project on the **Free tier** (AI Studio shows the tier next to each key). On the free tier Google stops at the quota rather than charging you.
- The model list shows only Flash and Flash-Lite models by default (the free-tier models).
- Ascent never enables billing and never switches to a paid model. GitHub Pages hosting is free.

## When something goes wrong

Every error says what Google or the browser reported. Click *Technical details* for the HTTP status and Google's own message. Common cases:

| Message | What to do |
|---|---|
| Google does not recognise this API key | Copy the key again from AI Studio |
| Could not reach Google | Office networks sometimes block it; try phone data |
| No free quota on this model | Choose another Flash model in Settings |
| Free request limit reached | Wait for the time Google states |
| Key restricted to other websites | Allow this site in Google Cloud → Credentials, or remove the restriction |

## Not built yet

Internet-wide or scheduled job search, CV tailoring, PDF/Word export, form filling, email tracking. Discover covers employers that publish on Greenhouse or Lever.

## For developers

```bash
npm install
npm test            # unit tests (scoring, Gemini error mapping, storage, feeds)
npm run build
node tests/e2e.mjs  # browser walkthrough with Google simulated (needs Playwright Chromium)
npm run dev
```

Vite + React + TypeScript, static output in `dist/`. Deployed by `.github/workflows/deploy-ascent.yml` on pushes to `master`. Never commit personal data or keys: `*.private.json` and `.env*` are ignored. Product context is in `PRODUCT.md`; the visual system in `DESIGN.md`.
