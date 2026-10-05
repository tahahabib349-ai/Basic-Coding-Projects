import { useState } from 'react';
import { ArrowLeft, Sparkles } from 'lucide-react';
import { extractListing } from '../lib/ai';
import { isDuplicate, isUnknown, safeURL, type Job } from '../lib/core';
import { Field } from '../components/ui';
import { go, useWorkspace } from '../state';

type Draft = { company: string; title: string; location: string; url: string; description: string; source: string; requirements?: string[]; deadline?: string };
const blank: Draft = { company: '', title: '', location: '', url: '', description: '', source: 'Manual paste' };

let pending: Draft | null = null;
/** Discover hands a feed vacancy to this page for review before it is saved. */
export function reviewVacancy(d: Omit<Draft, 'requirements' | 'deadline'>) {
  pending = d;
  go('add');
}

export function AddVacancy() {
  const { ws, update, run, key, busy, notify } = useWorkspace();
  const [form, setForm] = useState<Draft>(() => {
    const d = pending ?? blank;
    pending = null;
    return d;
  });
  const set = (k: keyof Draft) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const fromFeed = form.source !== 'Manual paste';

  const extract = () =>
    run('Reading the listing with Gemini', async () => {
      const { data, tokens } = await extractListing({ key, settings: ws.settings }, form.description);
      update((w) => ({ ...w, calls: w.calls + 1, usage: w.usage + tokens }), `Listing read with ${ws.settings.model}`);
      setForm((f) => ({
        ...f,
        company: isUnknown(data.company) ? f.company : data.company,
        title: isUnknown(data.title) ? f.title : data.title,
        location: isUnknown(data.location) ? f.location : data.location,
        requirements: data.requirements,
        deadline: data.deadline,
      }));
      notify({ tone: 'success', message: 'Fields filled from the listing. Check them, then save. Your pasted text is kept unchanged.' });
    });

  const save = () => {
    const c = { ...form, company: form.company.trim(), title: form.title.trim(), location: form.location.trim() || 'NEEDS USER INPUT', url: form.url.trim() };
    if (!c.company || !c.title) return notify({ tone: 'error', message: 'Add the employer and the role before saving.' });
    if (c.description.trim().length < 30) return notify({ tone: 'error', message: 'Paste the job description (at least a few sentences); fit is judged from it.' });
    if (c.description.length > 45000) return notify({ tone: 'error', message: 'The description is over 45,000 characters. Remove boilerplate such as benefits and legal text.' });
    if (c.url && !safeURL(c.url)) return notify({ tone: 'error', message: 'The job link must start with https:// or http://.' });
    const existing = ws.jobs.find((j) => isDuplicate(j, c));
    if (existing) {
      notify({ tone: 'error', message: `This vacancy is already in your schedule (${existing.company} · ${existing.title}). Opening it.` });
      return go(`job/${existing.id}`);
    }
    const now = new Date().toISOString();
    const job: Job = { id: crypto.randomUUID(), ...c, found: now, status: 'DISCOVERED', history: [{ status: 'DISCOVERED', at: now }], notes: '' };
    update((w) => ({ ...w, jobs: [job, ...w.jobs] }), `Recorded ${job.company} · ${job.title}`);
    notify({ tone: 'success', message: 'Vacancy recorded. Run “Analyse fit” when you are ready.' });
    go(`job/${job.id}`);
  };

  return (
    <div className="page page-narrow">
      <a className="back" href={fromFeed ? '#/discover' : '#/'}>
        <ArrowLeft size={16} aria-hidden="true" /> {fromFeed ? 'Discover' : 'Opportunities'}
      </a>
      <header className="page-head">
        <div>
          <h1>Add a vacancy</h1>
          <p className="lede">Paste the full listing from the employer’s page or LinkedIn. Gemini can fill the fields, or type them yourself at no quota cost.</p>
        </div>
      </header>

      <section className="sheet form-sheet">
        <Field label="Job description" hint={`${form.description.length.toLocaleString()} characters`} wide>
          <textarea className="tall" value={form.description} onChange={set('description')} placeholder="Paste the whole listing: responsibilities, requirements, location, closing date…" />
        </Field>
        <div className="actions">
          <button type="button" className="btn" disabled={!!busy || form.description.trim().length < 30} onClick={extract}>
            <Sparkles size={16} aria-hidden="true" /> Fill fields with Gemini
          </button>
        </div>
        <div className="form-grid">
          <Field label="Employer">
            <input value={form.company} onChange={set('company')} autoComplete="off" />
          </Field>
          <Field label="Role">
            <input value={form.title} onChange={set('title')} autoComplete="off" />
          </Field>
          <Field label="Market" hint="City or country, as the listing states it">
            <input value={form.location} onChange={set('location')} autoComplete="off" />
          </Field>
          <Field label="Job link" hint="Optional">
            <input type="url" inputMode="url" value={form.url} onChange={set('url')} placeholder="https://" autoComplete="off" />
          </Field>
        </div>
        {form.requirements && form.requirements.length > 0 && (
          <div className="extracted">
            <span className="field-label">Key requirements found</span>
            <ul className="clauses">
              {form.requirements.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </div>
        )}
        <div className="actions actions-end">
          <a className="btn btn-quiet" href={fromFeed ? '#/discover' : '#/'}>
            Cancel
          </a>
          <button type="button" className="btn btn-primary" disabled={!!busy} onClick={save}>
            Record vacancy
          </button>
        </div>
      </section>
    </div>
  );
}
