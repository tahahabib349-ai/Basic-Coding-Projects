import { useState } from 'react';
import { ArrowLeft, Copy, Download, ExternalLink, FileText, RefreshCw, Sparkles, Trash2 } from 'lucide-react';
import { assessFit, draftCoverLetter } from '../lib/ai';
import { cacheKey, componentLabels, components, recommendation, safeURL, statuses, weightedScore, type Job, type Status } from '../lib/core';
import { downloadFile } from '../lib/store';
import { Fact, FitRule, formatDate, formatDateTime, OpenTerm, RecTag, statusLabel, Term, Terms } from '../components/ui';
import { go, useWorkspace } from '../state';

export function JobSheet({ id }: { id: string }) {
  const { ws, update, run, key, busy, notify } = useWorkspace();
  const job = ws.jobs.find((j) => j.id === id);
  const [showListing, setShowListing] = useState(false);

  if (!job)
    return (
      <div className="page">
        <a className="back" href="#/">
          <ArrowLeft size={16} aria-hidden="true" /> Opportunities
        </a>
        <div className="sheet empty">
          <p>This vacancy is no longer in your schedule. It may have been deleted or restored from another backup.</p>
        </div>
      </div>
    );

  const patch = (fn: (j: Job) => Job, action?: string) => update((w) => ({ ...w, jobs: w.jobs.map((j) => (j.id === job.id ? fn(j) : j)) }), action);
  const stale = !!job.assessment && job.cache !== cacheKey(job, ws.profile, ws.settings);
  const totalWeight = components.reduce((s, k) => s + Math.max(0, ws.settings.weights[k] || 0), 0) || 1;
  const listing = safeURL(job.url);
  const ctx = { key, settings: ws.settings };
  const canAnalyse = !!ws.profile.cv.trim();

  const analyse = () =>
    run('Analysing professional fit', async () => {
      if (!canAnalyse) throw new Error('Load your profile first (Profile → Load profile file). Fit is measured against your résumé.');
      const ck = cacheKey(job, ws.profile, ws.settings);
      if (job.cache === ck && job.assessment) {
        notify({ tone: 'info', message: 'The saved analysis is current; nothing has changed since it was made.' });
        return;
      }
      const { data, tokens } = await assessFit(ctx, ws.profile, job);
      const score = weightedScore(data, ws.settings.weights);
      update(
        (w) => ({
          ...w,
          calls: w.calls + 1,
          usage: w.usage + tokens,
          jobs: w.jobs.map((j) =>
            j.id === job.id ? { ...j, assessment: data, score, recommendation: recommendation(score), cache: ck, scoredAt: new Date().toISOString(), scoredWith: ws.settings.model } : j,
          ),
        }),
        `Analysed ${job.company} · ${job.title}: ${score}/100`,
      );
      notify({ tone: 'success', message: `Analysis saved: ${score}/100. Read the evidence and gaps before deciding.` });
    });

  const draft = () =>
    run('Drafting cover letter', async () => {
      if (!canAnalyse) throw new Error('Load your profile first. Drafts use only facts from your résumé.');
      const { data, tokens } = await draftCoverLetter(ctx, ws.profile, job);
      update(
        (w) => ({
          ...w,
          calls: w.calls + 1,
          usage: w.usage + tokens,
          jobs: w.jobs.map((j) => (j.id === job.id ? { ...j, documents: [{ type: 'Cover letter', content: data.content, at: new Date().toISOString() }, ...(j.documents ?? [])] } : j)),
        }),
        `Cover letter drafted · ${job.company}`,
      );
      notify({ tone: 'success', message: 'Draft saved below. Check every statement before you use it.' });
    });

  const setStatus = (status: Status) => {
    if (status === job.status) return;
    if (status === 'APPLIED' && !window.confirm('Have you submitted this application yourself? Ascent only records it; it never submits anything.')) return;
    patch((j) => ({ ...j, status, history: [{ status, at: new Date().toISOString() }, ...j.history] }), `${job.company}: status → ${statusLabel(status)}`);
  };

  const remove = () => {
    if (!window.confirm(`Delete ${job.title} at ${job.company} from your schedule? This cannot be undone (unless you restore a backup).`)) return;
    update((w) => ({ ...w, jobs: w.jobs.filter((j) => j.id !== job.id) }), `Deleted ${job.company} · ${job.title}`);
    go('');
  };

  const a = job.assessment;

  return (
    <div className="page page-sheet">
      <a className="back" href="#/">
        <ArrowLeft size={16} aria-hidden="true" /> Opportunities
      </a>

      <header className="sheet-head">
        <h1>{job.title}</h1>
        <p className="sheet-sub">
          {job.company} · <Fact value={job.location} open="Market unknown" />
        </p>
        <div className="actions">
          <button type="button" className="btn btn-primary" disabled={!!busy} onClick={analyse}>
            {a ? <RefreshCw size={16} aria-hidden="true" /> : <Sparkles size={16} aria-hidden="true" />}
            {a ? (stale ? 'Refresh analysis' : 'Re-run analysis') : 'Analyse fit'}
          </button>
          {listing && (
            <a className="btn" href={listing} target="_blank" rel="noreferrer noopener">
              Open listing <ExternalLink size={15} aria-hidden="true" />
            </a>
          )}
          <button type="button" className="btn btn-quiet btn-danger" onClick={remove}>
            <Trash2 size={16} aria-hidden="true" /> Delete
          </button>
        </div>
      </header>

      <div className="sheet-grid">
        <div className="sheet-main">
          <section className="sheet" aria-labelledby="terms-title">
            <h2 id="terms-title" className="sheet-title">
              Indicative terms
            </h2>
            <Terms>
              <Term label="Employer">{job.company}</Term>
              <Term label="Role">{job.title}</Term>
              <Term label="Market">
                <Fact value={job.location} />
              </Term>
              <Term label="Professional fit">
                {a ? (
                  <div className="fit-block">
                    <FitRule score={job.score} size="lg" />
                    <RecTag value={job.recommendation} />
                    <span className="term-note">
                      {stale ? (
                        <OpenTerm>Profile, listing or preferences changed since this analysis. Refresh it.</OpenTerm>
                      ) : (
                        `Analysed ${formatDateTime(job.scoredAt)}${job.scoredWith ? ` with ${job.scoredWith}` : ''}`
                      )}
                    </span>
                  </div>
                ) : (
                  <OpenTerm>Not analysed. Run “Analyse fit” to score this vacancy against your résumé.</OpenTerm>
                )}
              </Term>
              <Term label="Work authorization" hint="Assessed separately from fit">
                {a ? (
                  <div>
                    {a.authorization === 'NEEDS USER INPUT' || a.authorization === 'UNKNOWN' ? (
                      <OpenTerm>{a.authorization === 'UNKNOWN' ? 'Unknown' : 'NEEDS USER INPUT'}</OpenTerm>
                    ) : (
                      <strong>{statusLabel(a.authorization)}</strong>
                    )}
                    {a.authorization_reason && <p className="term-note">{a.authorization_reason}</p>}
                  </div>
                ) : (
                  <OpenTerm />
                )}
              </Term>
              {a?.summary && <Term label="Summary">{a.summary}</Term>}
              {job.deadline && (
                <Term label="Closing date">
                  <Fact value={job.deadline} />
                </Term>
              )}
              <Term label="Source">
                {job.source}
                {listing && (
                  <>
                    {' · '}
                    <a href={listing} target="_blank" rel="noreferrer noopener" className="inline-link">
                      {new URL(listing).hostname.replace(/^www\./, '')}
                    </a>
                  </>
                )}
              </Term>
              <Term label="Recorded">{formatDate(job.found)}</Term>
            </Terms>
          </section>

          {a && (
            <section className="sheet" aria-labelledby="schedule-title">
              <h2 id="schedule-title" className="sheet-title">
                Fit schedule
              </h2>
              <table className="table fit-table">
                <thead>
                  <tr>
                    <th scope="col">Component</th>
                    <th scope="col" className="num">
                      Weight
                    </th>
                    <th scope="col">Score</th>
                    <th scope="col">Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {components.map((k) => (
                    <tr key={k}>
                      <th scope="row">{componentLabels[k]}</th>
                      <td className="num" data-label="Weight">
                        {Math.round((Math.max(0, ws.settings.weights[k] || 0) / totalWeight) * 100)}%
                      </td>
                      <td data-label="Score">
                        <FitRule score={a.components[k].score} />
                      </td>
                      <td className="evidence">{a.components[k].reason}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th scope="row">Weighted fit</th>
                    <td className="num">100%</td>
                    <td>
                      <FitRule score={job.score} />
                    </td>
                    <td className="evidence">70 and above is “Apply”; 85 and above is “Strong apply”.</td>
                  </tr>
                </tfoot>
              </table>
            </section>
          )}

          {a && (
            <section className="sheet split" aria-label="Strengths and gaps">
              <div>
                <h2 className="sheet-title">Strengths</h2>
                {a.strengths.length ? (
                  <ul className="clauses">
                    {a.strengths.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="term-note">None recorded.</p>
                )}
              </div>
              <div>
                <h2 className="sheet-title">Gaps and open points</h2>
                {a.gaps.length ? (
                  <ul className="clauses clauses-open">
                    {a.gaps.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="term-note">None recorded.</p>
                )}
              </div>
            </section>
          )}

          <section className="sheet" aria-labelledby="materials-title">
            <div className="sheet-title-row">
              <h2 id="materials-title" className="sheet-title">
                Application materials
              </h2>
              <button type="button" className="btn btn-sm" disabled={!!busy} onClick={draft}>
                <FileText size={15} aria-hidden="true" /> Draft cover letter
              </button>
            </div>
            <p className="term-note">Drafts use only facts from your résumé and need your review. Nothing here is sent anywhere.</p>
            {job.documents?.length ? (
              job.documents.map((d, i) => (
                <details className="draft" key={d.at} open={i === 0}>
                  <summary>
                    {d.type} · {formatDateTime(d.at)}
                  </summary>
                  <div className="draft-body">{d.content}</div>
                  <div className="actions">
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() =>
                        navigator.clipboard
                          .writeText(d.content)
                          .then(() => notify({ tone: 'success', message: 'Draft copied.' }))
                          .catch(() => notify({ tone: 'error', message: 'Copy was blocked by the browser. Select the text and copy it manually.' }))
                      }
                    >
                      <Copy size={15} aria-hidden="true" /> Copy
                    </button>
                    <button type="button" className="btn btn-sm" onClick={() => downloadFile(`${job.company.replace(/[^a-z0-9]+/gi, '-')}-cover-letter.txt`, d.content)}>
                      <Download size={15} aria-hidden="true" /> Download .txt
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm btn-quiet btn-danger"
                      onClick={() => {
                        if (window.confirm('Delete this draft?')) patch((j) => ({ ...j, documents: (j.documents ?? []).filter((x) => x.at !== d.at) }), `Draft deleted · ${job.company}`);
                      }}
                    >
                      <Trash2 size={15} aria-hidden="true" /> Delete
                    </button>
                  </div>
                </details>
              ))
            ) : (
              <p className="quiet-empty">No drafts yet.</p>
            )}
          </section>

          <section className="sheet" aria-labelledby="listing-title">
            <div className="sheet-title-row">
              <h2 id="listing-title" className="sheet-title">
                Original listing
              </h2>
              <button type="button" className="btn btn-sm btn-quiet" aria-expanded={showListing} onClick={() => setShowListing((v) => !v)}>
                {showListing ? 'Hide' : 'Show full text'}
              </button>
            </div>
            {job.requirements?.length ? (
              <ul className="clauses">
                {job.requirements.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            ) : null}
            <div className={`listing ${showListing ? 'is-open' : ''}`}>{job.description}</div>
          </section>
        </div>

        <aside className="sheet-side">
          <section className="sheet decision" aria-labelledby="decision-title">
            <h2 id="decision-title" className="sheet-title">
              Your decision
            </h2>
            <label className="field">
              <span className="field-label">Status</span>
              <select value={job.status} onChange={(e) => setStatus(e.target.value as Status)}>
                {statuses.map((s) => (
                  <option key={s} value={s}>
                    {statusLabel(s)}
                  </option>
                ))}
              </select>
            </label>
            <p className="term-note">“Applied” records your own submission. Ascent never applies for you.</p>
            <label className="field">
              <span className="field-label">Notes</span>
              <textarea
                rows={5}
                value={job.notes}
                placeholder="Contacts, referral, deadlines, questions to ask"
                onChange={(e) => patch((j) => ({ ...j, notes: e.target.value }))}
              />
            </label>
            <h3 className="minor-title">Status history</h3>
            <ol className="history">
              {job.history.map((h, i) => (
                <li key={i}>
                  <span>{statusLabel(h.status)}</span>
                  <time dateTime={h.at}>{formatDateTime(h.at)}</time>
                </li>
              ))}
            </ol>
          </section>
        </aside>
      </div>
    </div>
  );
}
