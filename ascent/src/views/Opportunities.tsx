import { useMemo, useState } from 'react';
import { ArrowRight, Check, Plus, Search } from 'lucide-react';
import { recommendations, splitTerms, stages, type Job } from '../lib/core';
import { FitRule, formatDate, formatDateTime, OpenTerm, RecTag, recommendationLabel, StatusTag } from '../components/ui';
import { ProfileImportButton } from '../components/ProfileImport';
import { go, useWorkspace } from '../state';

function Setup() {
  const { ws, key } = useWorkspace();
  const hasProfile = !!ws.profile.cv.trim();
  const connected = !!key && !!ws.settings.model;
  if (hasProfile && connected && ws.jobs.length) return null;
  const steps = [
    {
      label: 'Your profile',
      done: hasProfile,
      doneText: `${ws.profile.name || 'Résumé'} loaded`,
      open: 'Not loaded',
      action: <ProfileImportButton className="btn btn-sm" />,
      help: 'Load the private profile file you were given. It stays in this browser only.',
    },
    {
      label: 'Gemini connection',
      done: connected,
      doneText: `Connected · ${ws.settings.model}`,
      open: key ? 'Model not chosen' : 'Not connected',
      action: (
        <a className="btn btn-sm" href="#/settings">
          Open Settings
        </a>
      ),
      help: 'Paste your free Google AI Studio key and run the connection check.',
    },
    {
      label: 'First vacancy',
      done: ws.jobs.length > 0,
      doneText: `${ws.jobs.length} recorded`,
      open: 'None yet',
      action: (
        <a className="btn btn-sm" href="#/add">
          Add vacancy
        </a>
      ),
      help: 'Paste a real listing from LinkedIn, a bank’s careers site or an employer feed.',
    },
  ];
  return (
    <section className="sheet setup" aria-labelledby="setup-title">
      <h2 id="setup-title" className="sheet-title">
        Before your first analysis
      </h2>
      <dl className="terms">
        {steps.map((s) => (
          <div className="term" key={s.label}>
            <dt>{s.label}</dt>
            <dd className="setup-row">
              <span className="setup-state">
                {s.done ? (
                  <span className="done">
                    <Check size={16} aria-hidden="true" />
                    {s.doneText}
                  </span>
                ) : (
                  <OpenTerm>{s.open}</OpenTerm>
                )}
                {!s.done && <span className="term-note">{s.help}</span>}
              </span>
              {!s.done && s.action}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export function Opportunities() {
  const { ws } = useWorkspace();
  const [stage, setStage] = useState(-1);
  const [query, setQuery] = useState('');
  const [market, setMarket] = useState('');
  const [rec, setRec] = useState('');
  const [sort, setSort] = useState<'newest' | 'fit' | 'employer'>('newest');
  const [aboveMin, setAboveMin] = useState(false);

  const markets = useMemo(() => [...new Set(ws.jobs.map((j) => j.location).filter(Boolean))].sort(), [ws.jobs]);
  const excludedCo = splitTerms(ws.settings.excludedCompanies);
  const excludedRole = splitTerms(ws.settings.excludedRoles);

  const rows = ws.jobs
    .filter((j) => {
      const q = query.trim().toLowerCase();
      if (stage >= 0 && !stages[stage].statuses.includes(j.status)) return false;
      if (q && !`${j.company} ${j.title} ${j.location}`.toLowerCase().includes(q)) return false;
      if (market && j.location !== market) return false;
      if (rec === 'none' ? !!j.recommendation : rec && j.recommendation !== rec) return false;
      if (aboveMin && (j.score === undefined || j.score < ws.settings.minScore)) return false;
      return true;
    })
    .sort((a, b) =>
      sort === 'fit' ? (b.score ?? -1) - (a.score ?? -1) : sort === 'employer' ? a.company.localeCompare(b.company) : b.found.localeCompare(a.found),
    );

  const count = (i: number) => ws.jobs.filter((j) => stages[i].statuses.includes(j.status)).length;
  const strong = ws.jobs.filter((j) => j.recommendation === 'STRONG APPLY').length;
  const awaiting = ws.jobs.filter((j) => j.status === 'READY FOR APPROVAL').length;
  const unscored = ws.jobs.filter((j) => !j.assessment).length;
  const filtersOn = stage >= 0 || !!query || !!market || !!rec || aboveMin;
  const isExcluded = (j: Job) => excludedCo.some((t) => j.company.toLowerCase().includes(t)) || excludedRole.some((t) => j.title.toLowerCase().includes(t));

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Schedule of opportunities</h1>
          <p className="lede">
            {ws.jobs.length === 0
              ? 'Every vacancy you record appears here, with its fit, recommendation and status.'
              : [
                  `${ws.jobs.length} ${ws.jobs.length === 1 ? 'vacancy' : 'vacancies'}`,
                  strong && `${strong} strong apply`,
                  awaiting && `${awaiting} awaiting your approval`,
                  unscored && `${unscored} not yet analysed`,
                ]
                  .filter(Boolean)
                  .join(' · ')}
          </p>
        </div>
        <button type="button" className="btn btn-primary hide-mobile" onClick={() => go('add')}>
          <Plus size={17} aria-hidden="true" />
          Add vacancy
        </button>
      </header>

      <Setup />

      {ws.jobs.length > 0 && (
        <section className="sheet schedule" aria-label="Opportunities">
          <div className="stage-tabs" role="tablist" aria-label="Stage">
            <button type="button" role="tab" aria-selected={stage === -1} className={stage === -1 ? 'is-active' : ''} onClick={() => setStage(-1)}>
              All <span className="count">{ws.jobs.length}</span>
            </button>
            {stages.map((s, i) => (
              <button type="button" role="tab" key={s.label} aria-selected={stage === i} className={stage === i ? 'is-active' : ''} onClick={() => setStage(i)}>
                {s.label} <span className="count">{count(i)}</span>
              </button>
            ))}
          </div>

          <div className="filters">
            <label className="search">
              <Search size={16} aria-hidden="true" />
              <input type="search" placeholder="Employer, role or market" aria-label="Search vacancies" value={query} onChange={(e) => setQuery(e.target.value)} />
            </label>
            <select aria-label="Market" value={market} onChange={(e) => setMarket(e.target.value)}>
              <option value="">All markets</option>
              {markets.map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
            <select aria-label="Recommendation" value={rec} onChange={(e) => setRec(e.target.value)}>
              <option value="">All recommendations</option>
              {recommendations.map((r) => (
                <option key={r} value={r}>
                  {recommendationLabel(r)}
                </option>
              ))}
              <option value="none">Not analysed</option>
            </select>
            <select aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value as typeof sort)}>
              <option value="newest">Newest first</option>
              <option value="fit">Highest fit</option>
              <option value="employer">Employer A–Z</option>
            </select>
            <label className="check">
              <input type="checkbox" checked={aboveMin} onChange={(e) => setAboveMin(e.target.checked)} />
              Fit {ws.settings.minScore}+ only
            </label>
          </div>

          {rows.length ? (
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Employer and role</th>
                  <th scope="col">Market</th>
                  <th scope="col" className="num">
                    Fit
                  </th>
                  <th scope="col">Recommendation</th>
                  <th scope="col">Status</th>
                  <th scope="col" className="num">
                    Recorded
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((j) => (
                  <tr key={j.id} onClick={() => go(`job/${j.id}`)} className={isExcluded(j) ? 'is-muted' : ''}>
                    <td className="cell-main">
                      <a href={`#/job/${j.id}`} onClick={(e) => e.stopPropagation()}>
                        <strong>{j.company}</strong>
                        <span>{j.title}</span>
                      </a>
                      {isExcluded(j) && <span className="term-note">Matches an exclusion in Settings</span>}
                    </td>
                    <td className="cell-market" data-label="Market">
                      {j.location}
                    </td>
                    <td className="num cell-fit" data-label="Fit">
                      <FitRule score={j.score} />
                    </td>
                    <td className="cell-rec" data-label="Recommendation">
                      <RecTag value={j.recommendation} />
                    </td>
                    <td className="cell-status" data-label="Status">
                      <StatusTag value={j.status} />
                    </td>
                    <td className="num cell-date" data-label="Recorded">
                      {formatDate(j.found)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty">
              <p>No vacancies match {filtersOn ? 'these filters' : 'this stage'}.</p>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => {
                  setStage(-1);
                  setQuery('');
                  setMarket('');
                  setRec('');
                  setAboveMin(false);
                }}
              >
                Clear filters
              </button>
            </div>
          )}
        </section>
      )}

      {ws.activity.length > 0 && (
        <section className="activity" aria-labelledby="activity-title">
          <h2 id="activity-title">Record of activity</h2>
          <ol>
            {ws.activity.slice(0, 6).map((a, i) => (
              <li key={i}>
                <time dateTime={a.at}>{formatDateTime(a.at)}</time>
                <span>{a.action}</span>
              </li>
            ))}
          </ol>
          {ws.jobs.length === 0 && (
            <a className="link-button" href="#/add">
              Record your first vacancy <ArrowRight size={14} aria-hidden="true" />
            </a>
          )}
        </section>
      )}
    </div>
  );
}
