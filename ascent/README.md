# Ascent: personal job-application workspace

A private, approval-first job finder for a finance career move. Ascent searches the web for roles that match your CV in your target markets, scores each one, and lists them for you. You open the strong ones, read the full fit analysis, draft a cover letter, and apply yourself. Ascent never submits anything for you.

It is a single web page with no server. Your profile, vacancies and history are stored in your own browser. Gemini is called directly from your browser with your own free key.

## Using it

1. **Open the site** (GitHub Pages link for this repository).
2. **Load your profile.** On the first screen, click *Load profile file* and choose your private profile file. It stays in this browser only; it is not uploaded anywhere.
3. **Connect Gemini.** Settings → paste your key from [Google AI Studio](https://aistudio.google.com/apikey) → *Save and check connection*. The check runs four steps (key received, Google accepts it, model available, test answer) and tells you exactly which step fails and why.
4. **Let it find jobs.** Once your profile and key are in, Ascent searches every target market (Google Search through Gemini: careers pages, LinkedIn, eFinancialCareers, Bayt, GulfTalent and more) once a day when you open it, or whenever you tap *Search now*. New roles appear under **New** with a quick fit estimate (~78). Tap *Not interested* to drop one for good. Roles you find yourself can still be added with *Add vacancy*.
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

Searching while the app is closed (it searches when you open it), CV tailoring, PDF/Word export, form filling, email tracking. Search results can occasionally be stale or mislabelled: when a posting's link cannot be matched to a real search result, Ascent shows *Find the posting* (a web search) instead of a link, so always confirm on the employer's site.

## For developers

```bash
npm install
npm test            # unit tests (scoring, Gemini error mapping, storage, feeds)
npm run build
node tests/e2e.mjs  # browser walkthrough with Google simulated (needs Playwright Chromium)
npm run dev
```

Vite + React + TypeScript, static output in `dist/`. Deployed by `.github/workflows/deploy-ascent.yml` on pushes to `master`. Never commit personal data or keys: `*.private.json` and `.env*` are ignored. Product context is in `PRODUCT.md`; the visual system in `DESIGN.md`.
