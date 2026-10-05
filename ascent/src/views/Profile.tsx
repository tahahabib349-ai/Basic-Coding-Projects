import { useEffect, useState } from 'react';
import { Plus, X } from 'lucide-react';
import { isUnknown, NEEDS_INPUT, type Profile } from '../lib/core';
import { Field, OpenTerm } from '../components/ui';
import { ProfileImportButton } from '../components/ProfileImport';
import { useWorkspace } from '../state';

const answers: { key: 'authorization' | 'notice' | 'salary' | 'languages'; label: string; hint: string }[] = [
  { key: 'authorization', label: 'Work authorization and sponsorship', hint: 'By country, e.g. “UK: requires sponsorship. UAE: requires employment visa.”' },
  { key: 'notice', label: 'Notice period', hint: 'As in your current contract' },
  { key: 'salary', label: 'Salary expectations', hint: 'Only used when a form asks; never guessed' },
  { key: 'languages', label: 'Languages', hint: 'With level, e.g. “English (fluent), Urdu (native)”' },
];

export function ProfileView() {
  const { ws, update, notify } = useWorkspace();
  const [draft, setDraft] = useState<Profile>(ws.profile);
  useEffect(() => setDraft(ws.profile), [ws.profile]);
  const dirty = JSON.stringify(draft) !== JSON.stringify(ws.profile);
  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const openCount = answers.filter((a) => isUnknown(draft[a.key])).length;

  const save = () => {
    if (draft.cv.trim() && draft.cv.trim().length < 30) return notify({ tone: 'error', message: 'The master résumé looks incomplete. Paste the full text.' });
    const clean = { ...draft, experience: draft.experience.filter((x) => x.company.trim() || x.title.trim()) };
    for (const a of answers) if (!clean[a.key].trim()) clean[a.key] = NEEDS_INPUT;
    update((w) => ({ ...w, profile: clean }), 'Profile updated');
    notify({ tone: 'success', message: 'Profile saved. Saved analyses are marked for refresh where it matters.' });
  };

  return (
    <div className="page page-narrow">
      <header className="page-head">
        <div>
          <h1>Profile</h1>
          <p className="lede">The facts every analysis and draft is built from. Anything you have not confirmed stays an open point.</p>
        </div>
        <ProfileImportButton />
      </header>

      <section className="sheet form-sheet" aria-labelledby="id-title">
        <h2 id="id-title" className="sheet-title">
          Candidate
        </h2>
        <div className="form-grid">
          <Field label="Full name">
            <input value={draft.name} onChange={(e) => set('name', e.target.value)} autoComplete="name" />
          </Field>
          <Field label="Headline">
            <input value={draft.headline} onChange={(e) => set('headline', e.target.value)} placeholder="e.g. Investments · Project Finance · Private Equity" />
          </Field>
          <Field label="Education">
            <input value={draft.education} onChange={(e) => set('education', e.target.value)} />
          </Field>
          <Field label="Certification">
            <input value={draft.certification} onChange={(e) => set('certification', e.target.value)} />
          </Field>
        </div>
      </section>

      <section className="sheet form-sheet" aria-labelledby="answers-title">
        <div className="sheet-title-row">
          <h2 id="answers-title" className="sheet-title">
            Personal answers
          </h2>
          {openCount > 0 ? <OpenTerm>{openCount} open</OpenTerm> : <span className="term-note">All answered</span>}
        </div>
        <p className="term-note">Work authorization is judged separately from fit, so leaving it open never lowers a score.</p>
        {answers.map((a) => {
          const unknown = isUnknown(draft[a.key]);
          return (
            <Field key={a.key} label={a.label} hint={a.hint} wide>
              <textarea
                rows={2}
                className={unknown ? 'is-open' : ''}
                value={unknown ? '' : draft[a.key]}
                placeholder={`[●] ${NEEDS_INPUT}`}
                onChange={(e) => set(a.key, e.target.value)}
              />
            </Field>
          );
        })}
      </section>

      <section className="sheet form-sheet" aria-labelledby="exp-title">
        <div className="sheet-title-row">
          <h2 id="exp-title" className="sheet-title">
            Experience
          </h2>
          <button type="button" className="btn btn-sm" onClick={() => set('experience', [{ company: '', title: '', dates: '' }, ...draft.experience])}>
            <Plus size={15} aria-hidden="true" /> Add role
          </button>
        </div>
        {draft.experience.length === 0 && <p className="quiet-empty">No roles yet. Load your profile file, or add them here.</p>}
        <ol className="experience">
          {draft.experience.map((x, i) => (
            <li key={i}>
              {(['company', 'title', 'dates'] as const).map((k) => (
                <input
                  key={k}
                  aria-label={`${k === 'company' ? 'Employer' : k === 'title' ? 'Title' : 'Dates'}, role ${i + 1}`}
                  placeholder={k === 'company' ? 'Employer' : k === 'title' ? 'Title' : 'Dates'}
                  value={x[k]}
                  onChange={(e) => set('experience', draft.experience.map((v, n) => (n === i ? { ...v, [k]: e.target.value } : v)))}
                />
              ))}
              <button type="button" className="icon-button" aria-label={`Remove role ${i + 1}`} onClick={() => set('experience', draft.experience.filter((_, n) => n !== i))}>
                <X size={16} />
              </button>
            </li>
          ))}
        </ol>
      </section>

      <section className="sheet form-sheet" aria-labelledby="cv-title">
        <h2 id="cv-title" className="sheet-title">
          Master résumé
        </h2>
        <p className="term-note">The single source of truth for matching and drafting. Keep it consistent with the roles above.</p>
        <textarea className="cv" aria-labelledby="cv-title" value={draft.cv} onChange={(e) => set('cv', e.target.value)} placeholder="Paste your full résumé text, or load your profile file." />
      </section>

      <div className={`savebar ${dirty ? 'is-dirty' : ''}`} aria-hidden={!dirty}>
        <span>Unsaved changes</span>
        <button type="button" className="btn btn-quiet" tabIndex={dirty ? 0 : -1} onClick={() => setDraft(ws.profile)}>
          Discard
        </button>
        <button type="button" className="btn btn-primary" tabIndex={dirty ? 0 : -1} onClick={save}>
          Save profile
        </button>
      </div>
    </div>
  );
}
