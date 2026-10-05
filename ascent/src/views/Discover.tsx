import { useState } from 'react';
import { ExternalLink, LoaderCircle, Search } from 'lucide-react';
import { isDuplicate, safeURL, splitTerms } from '../lib/core';
import { providers, readFeed, type FeedJob, type Provider } from '../lib/feeds';
import { Field, formatDateTime } from '../components/ui';
import { useWorkspace } from '../state';
import { reviewVacancy } from './AddVacancy';

const DEFAULT_KEYWORDS = 'finance, investment, analyst, associate, infrastructure, project finance, private equity, m&a, debt, leveraged, structured, corporate development';

let lastResult: { jobs: FeedJob[]; provider: Provider; board: string } | null = null;

export function Discover() {
  const { ws, run, busy, notify, update, key, searching, findJobs } = useWorkspace();
  const ready = !!key && !!ws.settings.model && !!ws.profile.cv.trim();
  const newFinds = ws.jobs.filter((j) => j.source.startsWith('Web search') && j.status === 'DISCOVERED').length;
  const [provider, setProvider] = useState<Provider>(lastResult?.provider ?? 'greenhouse');
  const [board, setBoard] = useState(lastResult?.board ?? '');
  const [jobs, setJobs] = useState<FeedJob[]>(lastResult?.jobs ?? []);
  const [keywords, setKeywords] = useState(DEFAULT_KEYWORDS);

  const terms = splitTerms(keywords);
  const excludedCo = splitTerms(ws.settings.excludedCompanies);
  const excludedRole = splitTerms(ws.settings.excludedRoles);
  const shown = jobs.filter(
    (j) =>
      (!terms.length || terms.some((t) => `${j.title} ${j.description}`.toLowerCase().includes(t))) &&
      !excludedCo.some((t) => j.company.toLowerCase().includes(t)) &&
      !excludedRole.some((t) => j.title.toLowerCase().includes(t)),
  );

  const find = () =>
    run('Reading the employer’s public job feed', async () => {
      const out = await readFeed(provider, board);
      setJobs(out.jobs);
      lastResult = { jobs: out.jobs, provider, board };
      notify({ tone: 'success', message: `${out.jobs.length} open roles at ${out.company}${out.truncated ? ' (first 500 shown)' : ''}. Review each before recording it.` });
    });

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Find jobs</h1>
          <p className="lede">Ascent searches the web for open roles that match your CV, scores each one, and puts them in your schedule under “New”. You only decide which to pursue.</p>
        </div>
      </header>

      <section className="sheet form-sheet" aria-labelledby="auto-title">
        <div className="sheet-title-row">
          <h2 id="auto-title" className="sheet-title">
            Automatic search
          </h2>
          <button type="button" className="btn btn-primary" disabled={!!searching || !ready} onClick={() => findJobs('manual')}>
            {searching ? <LoaderCircle size={16} className="spin" aria-hidden="true" /> : <Search size={16} aria-hidden="true" />}
            {searching ? 'Searching…' : 'Search now'}
          </button>
        </div>
        {searching && <p className="search-progress">{searching}…</p>}
        <dl className="terms">
          <div className="term">
            <dt>Looks for</dt>
            <dd>{ws.settings.roles}</dd>
          </div>
          <div className="term">
            <dt>Level</dt>
            <dd>{ws.settings.seniority}</dd>
          </div>
          <div className="term">
            <dt>In</dt>
            <dd>{ws.settings.locations}</dd>
          </div>
          <div className="term">
            <dt>Where it searches</dt>
            <dd>
              Google Search through your Gemini key ({ws.settings.searchModel || 'gemini-2.5-flash'}): employer careers pages, LinkedIn, eFinancialCareers, Indeed, Bayt, GulfTalent, Rozee and recruiters.
            </dd>
          </div>
          <div className="term">
            <dt>Last search</dt>
            <dd>
              {ws.lastSearch ? formatDateTime(ws.lastSearch) : 'Not run yet'}
              {newFinds > 0 && (
                <>
                  {' · '}
                  <a className="inline-link" href="#/">
                    {newFinds} new {newFinds === 1 ? 'role' : 'roles'} waiting
                  </a>
                </>
              )}
            </dd>
          </div>
        </dl>
        <label className="check">
          <input type="checkbox" checked={ws.settings.autoSearch} onChange={(e) => update((w) => ({ ...w, settings: { ...w.settings, autoSearch: e.target.checked } }), e.target.checked ? 'Daily search on' : 'Daily search off')} />
          Search automatically once a day when I open Ascent
        </label>
        <p className="term-note">
          Change roles, level and markets in <a className="inline-link" href="#/settings">Settings</a>. A full search uses about {ws.settings.locations.split(',').filter((x) => x.trim()).length + 1} Gemini requests, well within the free daily allowance. Ascent finds and prepares; you apply.
        </p>
      </section>

      <section className="sheet form-sheet" aria-labelledby="boards-title">
        <h2 id="boards-title" className="sheet-title">
          Specific employer’s job board
        </h2>
        <p className="term-note">Optional. Some employers publish every opening on Greenhouse or Lever, job-board services behind their careers pages. If a firm’s careers link contains greenhouse.io or lever.co, paste it here to see all its roles.</p>
        <div className="discover-grid">
          <Field label="Job board">
            <select value={provider} onChange={(e) => setProvider(e.target.value as Provider)}>
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Employer board name or careers link" hint={`The word after ${providers.find((p) => p.id === provider)?.hint}`}>
            <input
              value={board}
              onChange={(e) => setBoard(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && board.trim() && find()}
              placeholder="e.g. a board name or full link"
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
            />
          </Field>
          <button type="button" className="btn btn-primary discover-go" disabled={!!busy || !board.trim()} onClick={find}>
            <Search size={16} aria-hidden="true" /> Find roles
          </button>
        </div>
        <Field label="Show roles mentioning any of" hint="Comma separated. Clear it to see every role on the board." wide>
          <input value={keywords} onChange={(e) => setKeywords(e.target.value)} />
        </Field>
        <p className="term-note">
          Covers employers that publish on Greenhouse or Lever. For LinkedIn, Workday, bank careers sites and recruiters, open the listing and use Add vacancy. Posting dates are often missing and are never guessed.
        </p>
      </section>

      {jobs.length > 0 && (
        <section className="sheet" aria-labelledby="results-title">
          <div className="sheet-title-row">
            <h2 id="results-title" className="sheet-title">
              Roles found
            </h2>
            <span className="term-note">
              {shown.length} of {jobs.length} match your keywords
            </span>
          </div>
          {shown.length ? (
            <ul className="feed">
              {shown.map((j, i) => {
                const saved = ws.jobs.find((x) => isDuplicate(x, { ...j, location: j.location || 'NEEDS USER INPUT' }));
                const link = safeURL(j.url);
                return (
                  <li key={`${j.url}-${i}`}>
                    <div>
                      <strong>{j.title}</strong>
                      <span>
                        {j.company} · {j.location || 'Market not stated'}
                        {j.updated && ` · updated ${new Date(j.updated).toLocaleDateString('en-GB')}`}
                      </span>
                      {link && (
                        <a href={link} target="_blank" rel="noreferrer noopener" className="inline-link">
                          Employer listing <ExternalLink size={13} aria-hidden="true" />
                        </a>
                      )}
                    </div>
                    {saved ? (
                      <a className="btn btn-sm btn-quiet" href={`#/job/${saved.id}`}>
                        Already recorded
                      </a>
                    ) : (
                      <button type="button" className="btn btn-sm" onClick={() => reviewVacancy({ company: j.company, title: j.title, location: j.location, url: j.url, description: j.description, source: j.source })}>
                        Review and record
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="empty">
              <p>No roles on this board mention your keywords.</p>
              <button type="button" className="btn btn-sm" onClick={() => setKeywords('')}>
                Show all {jobs.length}
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
