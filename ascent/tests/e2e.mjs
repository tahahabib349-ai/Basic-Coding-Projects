// End-to-end walkthrough in a real browser with Google and the job feed simulated.
// Usage: node tests/e2e.mjs [profile.json] [screenshot-dir]
// Needs `npm run build` first. Uses Playwright's Chromium.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import assert from 'node:assert/strict';

const profilePath = process.argv[2];
const shots = process.argv[3];
if (shots) fs.mkdirSync(shots, { recursive: true });

const PORT = 4179;
const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--port', String(PORT), '--strictPort'], { stdio: 'pipe' });
await new Promise((res, rej) => {
  server.stdout.on('data', (d) => String(d).includes(String(PORT)) && res());
  setTimeout(() => rej(new Error('preview server did not start')), 15000);
});
const BASE = `http://localhost:${PORT}/`;

const synthetic = {
  version: 2,
  profile: {
    name: 'Test Candidate',
    headline: 'Project finance',
    cv: 'TEST CANDIDATE\nInvestment Banking Analyst, Example Bank, 2024–present. Project finance modelling, debt sizing, lender materials.\nBSc Finance.',
    authorization: 'NEEDS USER INPUT',
    notice: 'NEEDS USER INPUT',
    salary: 'NEEDS USER INPUT',
    languages: 'English (fluent)',
    experience: [{ company: 'Example Bank', title: 'Investment Banking Analyst', dates: '2024–present' }],
    education: 'BSc Finance',
    certification: '',
  },
  jobs: [],
  activity: [],
  calls: 0,
  usage: 0,
};
const profileFile = profilePath ?? '/tmp/ascent-e2e-profile.json';
if (!profilePath) fs.writeFileSync(profileFile, JSON.stringify(synthetic));

const reasons = {
  role: 'The mandate is infrastructure and project finance advisory, the core of the CV’s project financing work.',
  experience: 'About two years of transaction experience against a stated 2–4 years for Associate entry; at the lower end of the range.',
  skills: 'Three-statement, LBO and debt-sizing models are evidenced; the listing’s request for PF model audit experience is not shown.',
  sector: 'Energy and transport infrastructure experience matches the listing’s sector focus.',
  transactions: 'Closed project and syndicated financings comparable in kind, smaller in ticket size.',
  seniority: 'Senior Analyst title against an Associate role; promotion-stage candidates are typical for this level.',
  education: 'Finance degree meets the stated requirements.',
  location: 'London is a target market. Right to work in the UK is not stated in the profile.',
};
const scores = { role: 92, experience: 74, skills: 84, sector: 90, transactions: 82, seniority: 70, education: 88, location: 72 };
const assessment = {
  components: Object.fromEntries(Object.keys(reasons).map((k) => [k, { score: scores[k], reason: reasons[k] }])),
  strengths: ['Led a syndicated financing through financial close', 'Debt-serviceability sensitivities on a renewable project', 'Concession-document diligence'],
  gaps: ['No UK or European project finance mandates on the CV', 'Associate title expects some team supervision; not evidenced', 'UK right to work not stated'],
  summary: 'A strong fit on sector and deal type: the candidate has run project and syndicated financings end to end. The main gap is seniority and the absence of European mandates; neither is disqualifying for an Associate entry role.',
  authorization: 'NEEDS USER INPUT',
  authorization_reason: 'The listing does not mention sponsorship and the profile does not state UK work authorization.',
};
const listing = `Associate, Infrastructure & Project Finance — London

Northgate Infrastructure Partners advises sponsors and lenders on energy transition, transport and digital infrastructure financings across Europe and the Middle East.

Responsibilities
• Build and review project finance models (debt sizing, DSCR, sculpting)
• Prepare information memoranda and lender presentations
• Coordinate technical, legal and model-audit advisors through financial close

Requirements
• 2–4 years in project finance, infrastructure advisory or leveraged finance
• Strong financial modelling; model audit experience a plus
• Degree in finance, economics or engineering; CFA progress welcome

Closing date: 31 October 2026`;

const letter = `Dear Hiring Team,

I am writing to apply for the Associate, Infrastructure & Project Finance role at Northgate Infrastructure Partners in London.

In my current role I have structured project and syndicated financings, coordinating lenders and advisors through financial close.

I would welcome the chance to discuss how this experience could support your infrastructure financings.

Yours faithfully,`;

const geminiCalls = [];
async function mockGoogle(page) {
  await page.route('https://generativelanguage.googleapis.com/**', async (route) => {
    const req = route.request();
    const key = req.headers()['x-goog-api-key'];
    geminiCalls.push({ url: req.url(), key, body: req.postData() ?? '' });
    if (key !== 'AIzaTEST-valid-key') {
      return route.fulfill({
        status: 400,
        json: { error: { code: 400, status: 'INVALID_ARGUMENT', message: 'API key not valid. Please pass a valid API key.', details: [{ '@type': 'type.googleapis.com/google.rpc.ErrorInfo', reason: 'API_KEY_INVALID' }] } },
      });
    }
    if (req.method() === 'GET')
      return route.fulfill({
        json: {
          models: [
            { name: 'models/gemini-2.5-flash', supportedGenerationMethods: ['generateContent'], outputTokenLimit: 65536 },
            { name: 'models/gemini-3.8-flash', supportedGenerationMethods: ['generateContent'], outputTokenLimit: 65536 },
            { name: 'models/gemini-3.5-flash-lite', supportedGenerationMethods: ['generateContent'] },
            { name: 'models/gemini-3.8-pro', supportedGenerationMethods: ['generateContent'] },
          ],
        },
      });
    const prompt = req.postData() ?? '';
    let payload = { ok: true };
    if (prompt.includes('Extract the facts')) payload = { company: 'Northgate Infrastructure Partners', title: 'Associate, Infrastructure & Project Finance', location: 'London', requirements: ['2–4 years in project finance or infrastructure advisory', 'Strong financial modelling; model audit a plus', 'Finance, economics or engineering degree'], deadline: '31 October 2026', authorization_info: '' };
    if (prompt.includes('Assess the candidate')) payload = assessment;
    if (prompt.includes('cover letter')) payload = { content: letter };
    return route.fulfill({ json: { candidates: [{ finishReason: 'STOP', content: { parts: [{ text: JSON.stringify(payload) }] } }], usageMetadata: { totalTokenCount: 1200 } } });
  });
  await page.route('https://boards-api.greenhouse.io/**', (route) =>
    route.request().url().includes('/jobs')
      ? route.fulfill({
          json: {
            jobs: [
              { id: 11, title: 'Analyst, Infrastructure Debt', location: { name: 'Dubai' }, absolute_url: 'https://boards.greenhouse.io/demo/jobs/11', content: '&lt;p&gt;Infrastructure debt investing across the GCC.&lt;/p&gt;' },
              { id: 12, title: 'Office Manager', location: { name: 'Dubai' }, absolute_url: 'https://boards.greenhouse.io/demo/jobs/12', content: '&lt;p&gt;Facilities.&lt;/p&gt;' },
            ],
          },
        })
      : route.fulfill({ json: { name: 'Demo Capital' } }),
  );
}

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || (fs.existsSync('/opt/pw-browsers/chromium-1194/chrome-linux/chrome') ? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' : undefined) });
const errors = [];
async function newPage(viewport) {
  const ctx = await browser.newContext({ viewport, acceptDownloads: true, deviceScaleFactor: viewport.width < 500 ? 2 : 1 });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => m.type() === 'error' && !m.text().includes('status of 400') && errors.push(m.text())); // the 400 is the deliberate wrong-key step
  page.on('dialog', (d) => d.accept());
  await mockGoogle(page);
  return { ctx, page };
}
const shot = async (page, name, full = true) => shots && page.screenshot({ path: `${shots}/${name}.png`, fullPage: full });
const settle = (page) => page.waitForTimeout(900);

try {
  const { ctx, page } = await newPage({ width: 1440, height: 960 });
  await page.goto(BASE);
  await page.getByRole('heading', { name: 'Schedule of opportunities' }).waitFor();
  await shot(page, 'desktop-01-first-run');

  // 1. Load the private profile file
  await page.locator('input[type=file]').first().setInputFiles(profileFile);
  await page.getByText('Profile loaded for').waitFor();

  // 2. Wrong key → Google's specific error is shown, not a generic one
  await page.goto(BASE + '#/settings');
  await page.getByPlaceholder('Paste the key from Google AI Studio').fill('  "wrong-key"  ');
  await page.getByRole('button', { name: 'Save and check connection' }).click();
  await page.getByText('Google does not recognise this API key').waitFor();
  assert(geminiCalls.at(-1).key === 'wrong-key', 'quotes and spaces should be stripped before sending');
  await shot(page, 'desktop-02-settings-bad-key');

  // 3. Right key → model listed and chosen, test answer passes
  await page.getByPlaceholder('Paste the key from Google AI Studio').fill('AIzaTEST-valid-key');
  await page.getByRole('button', { name: 'Save and check connection' }).click();
  await page.getByText('Gemini answered correctly').waitFor();
  assert.equal(await page.locator('select').first().inputValue(), 'gemini-3.8-flash');
  await settle(page);
  await shot(page, 'desktop-03-settings-connected');

  // 4. Add a vacancy, fill fields with Gemini, record it
  await page.goto(BASE + '#/add');
  await page.getByPlaceholder(/Paste the whole listing/).fill(listing);
  await page.getByRole('button', { name: 'Fill fields with Gemini' }).click();
  await page.getByText('Fields filled from the listing').waitFor();
  assert.equal(await page.getByLabel('Employer').inputValue(), 'Northgate Infrastructure Partners');
  await shot(page, 'desktop-04-add-vacancy');
  await page.getByRole('button', { name: 'Record vacancy' }).click();
  await page.getByRole('heading', { name: 'Associate, Infrastructure & Project Finance' }).waitFor();

  // 5. Analyse fit, draft a letter, change status
  await page.getByRole('button', { name: 'Analyse fit' }).click();
  await page.getByText('Analysis saved').waitFor();
  await page.getByRole('button', { name: 'Draft cover letter' }).click();
  await page.getByText('Draft saved below').waitFor();
  await page.getByLabel('Status').selectOption('READY FOR APPROVAL');
  await settle(page);
  await shot(page, 'desktop-05-term-sheet');
  const score = await page.locator('.fit-lg .fit-num').textContent();
  assert.equal(score, '83');

  // 6. Duplicate detection
  await page.goto(BASE + '#/add');
  await page.getByPlaceholder(/Paste the whole listing/).fill(listing);
  await page.getByLabel('Employer').fill('Northgate Infrastructure Partners');
  await page.getByLabel('Role').fill('Associate, Infrastructure & Project Finance');
  await page.getByLabel('Market').fill('London');
  await page.getByRole('button', { name: 'Record vacancy' }).click();
  await page.getByText('already in your schedule').waitFor();

  // 7. Discover from a Greenhouse board, import one
  await page.goto(BASE + '#/discover');
  await page.getByLabel(/Employer board name/).fill('https://boards.greenhouse.io/demo');
  await page.getByRole('button', { name: 'Find roles' }).click();
  await page.getByText('2 open roles at Demo Capital').waitFor();
  assert.equal(await page.locator('.feed li').count(), 1, 'keyword filter should hide the office manager role');
  await shot(page, 'desktop-06-discover');
  await page.getByRole('button', { name: 'Review and record' }).click();
  await page.getByRole('button', { name: 'Record vacancy' }).click();
  await page.getByRole('heading', { name: 'Analyst, Infrastructure Debt' }).waitFor();

  // 8. Persistence across reload; key remembered; filters
  await page.goto(BASE);
  await page.reload();
  await page.getByText('2 vacancies').waitFor();
  assert.equal(await page.locator('.schedule tbody tr').count(), 2);
  await page.getByText('Gemini ready').waitFor();
  await page.getByRole('tab', { name: /Preparing/ }).click();
  assert.equal(await page.locator('.schedule tbody tr').count(), 1);
  await page.getByRole('tab', { name: /All/ }).click();
  await settle(page);
  await shot(page, 'desktop-07-schedule');

  // 9. Backup excludes the key; restore replaces the workspace
  const [download] = await Promise.all([page.waitForEvent('download'), page.goto(BASE + '#/settings').then(() => page.getByRole('button', { name: 'Export backup' }).click())]);
  const backupPath = '/tmp/ascent-e2e-backup.json';
  await download.saveAs(backupPath);
  const backup = fs.readFileSync(backupPath, 'utf8');
  assert(!backup.includes('AIzaTEST'), 'backup must not contain the key');
  assert.equal(JSON.parse(backup).jobs.length, 2);
  await page.getByRole('button', { name: 'Erase workspace' }).click();
  await page.goto(BASE);
  await page.getByRole('heading', { name: 'Before your first analysis' }).waitFor();
  await page.goto(BASE + '#/settings');
  await page.locator('input[type=file]').last().setInputFiles(backupPath);
  await page.getByText('Backup restored: 2 vacancies').waitFor();

  // Profile page with open terms
  await page.goto(BASE + '#/profile');
  await page.getByRole('heading', { name: 'Personal answers' }).waitFor();
  await shot(page, 'desktop-08-profile');
  await ctx.close();

  // Mobile pass on the same data
  if (shots) {
    const m = await newPage({ width: 390, height: 844 });
    await m.page.goto(BASE + '#/settings');
    await m.page.locator('input[type=file]').last().setInputFiles(backupPath);
    await m.page.getByText('Backup restored').waitFor();
    await m.page.goto(BASE);
    await settle(m.page);
    await shot(m.page, 'mobile-01-schedule');
    await m.page.locator('.schedule tbody tr').filter({ hasText: 'Northgate' }).click();
    await settle(m.page);
    await shot(m.page, 'mobile-02-term-sheet');
    await m.page.goto(BASE + '#/settings');
    await settle(m.page);
    await shot(m.page, 'mobile-03-settings');
    await m.ctx.close();
  }

  const leaked = geminiCalls.filter((c) => c.url.includes('AIza') || c.body.includes('AIza'));
  assert.equal(leaked.length, 0, 'key must travel only in the header');
  assert.deepEqual(errors, [], `browser errors: ${errors.join('\n')}`);
  console.log(`E2E passed: ${geminiCalls.length} simulated Google calls, profile import, bad/good key, extract, analyse (83/100), letter, status, duplicate, discover, reload persistence, filters, backup/erase/restore.`);
} finally {
  await browser.close();
  server.kill();
}
