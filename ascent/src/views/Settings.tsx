import { useEffect, useRef, useState } from 'react';
import { Check, CircleAlert, Download, Eye, EyeOff, ExternalLink, LoaderCircle, Trash2, Upload } from 'lucide-react';
import { testConnection } from '../lib/ai';
import { componentLabels, components, normalizeAPIKey, type Settings } from '../lib/core';
import { describeError, listModels, rankModels, type ModelInfo } from '../lib/gemini';
import { downloadFile, initialWorkspace, parseWorkspace, serialise } from '../lib/store';
import { Field, OpenTerm } from '../components/ui';
import { useWorkspace } from '../state';

type StepState = { state: 'idle' | 'run' | 'pass' | 'fail' | 'warn'; text: string; detail?: string };
const idle: StepState = { state: 'idle', text: 'Not checked' };
const stepLabels = ['Key entered', 'Google accepts the key', 'Model available', 'Test answer'];

let modelCache: ModelInfo[] | null = null;

function StepMark({ s }: { s: StepState }) {
  if (s.state === 'run') return <LoaderCircle size={16} className="spin" aria-label="Checking" />;
  if (s.state === 'pass') return <Check size={16} aria-label="Passed" className="ok" />;
  if (s.state === 'fail') return <CircleAlert size={16} aria-label="Failed" className="bad" />;
  if (s.state === 'warn') return <CircleAlert size={16} aria-label="Warning" className="warn" />;
  return <span className="step-dot" aria-hidden="true" />;
}

function Connection() {
  const { ws, update, key, setKey, remembered, busy, run } = useWorkspace();
  const [value, setValue] = useState(key);
  const [show, setShow] = useState(false);
  const [remember, setRemember] = useState(remembered || !key);
  const [steps, setSteps] = useState<StepState[]>([idle, idle, idle, idle]);
  const [models, setModels] = useState<ModelInfo[]>(modelCache ?? []);
  const [showAll, setShowAll] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const setStep = (i: number, s: StepState) => setSteps((all) => all.map((x, n) => (n === i ? s : n > i && s.state === 'fail' ? idle : x)));
  const options = showAll ? models : rankModels(models);
  const chooseModel = (id: string, list = models) => {
    const info = list.find((m) => m.id === id);
    update((w) => ({ ...w, settings: { ...w.settings, model: id, modelOutputLimit: info?.outputTokenLimit } }), `Model set to ${id}`);
  };

  const check = () =>
    run('Checking the Gemini connection', async () => {
      // Read the field itself so browser autofill that skipped React's onChange is still seen.
      const k = normalizeAPIKey(input.current?.value ?? value);
      setValue(k);
      setSteps([idle, idle, idle, idle]);
      if (!k) {
        setStep(0, { state: 'fail', text: 'The key field is empty. Paste your key from Google AI Studio.' });
        return;
      }
      setKey(k, remember);
      setStep(0, { state: 'pass', text: `${k.length} characters received` });

      setStep(1, { state: 'run', text: 'Asking Google…' });
      let list: ModelInfo[];
      try {
        list = await listModels(k);
      } catch (e) {
        const d = describeError(e);
        setStep(1, { state: 'fail', text: d.message, detail: d.detail });
        return;
      }
      modelCache = list;
      setModels(list);
      const free = rankModels(list);
      setStep(1, { state: 'pass', text: `Accepted. ${list.length} models available to your project, ${free.length} on the free tier (Flash and Flash-Lite).` });

      let model = ws.settings.model;
      if (!model || !list.some((m) => m.id === model)) {
        const pick = free[0] ?? list[0];
        if (!pick) {
          setStep(2, { state: 'fail', text: 'Your project lists no text models. Create a fresh key in Google AI Studio.' });
          return;
        }
        const was = model;
        model = pick.id;
        chooseModel(model, list);
        setStep(2, { state: 'pass', text: was ? `“${was}” is not offered to your project, so ${model} was selected.` : `${model} selected (newest free-tier Flash).` });
      } else setStep(2, { state: 'pass', text: `${model} is available.` });

      setStep(3, { state: 'run', text: `Sending a one-line test to ${model}…` });
      try {
        const { tokens } = await testConnection(k, model);
        update((w) => ({ ...w, calls: w.calls + 1, usage: w.usage + tokens }), `Gemini connection verified · ${model}`);
        setStep(3, { state: 'pass', text: `Gemini answered correctly. Ascent is ready.` });
      } catch (e) {
        const d = describeError(e);
        setStep(3, { state: 'fail', text: d.message, detail: d.detail });
      }
    });

  return (
    <section className="sheet form-sheet" aria-labelledby="gemini-title">
      <div className="sheet-title-row">
        <h2 id="gemini-title" className="sheet-title">
          Gemini connection
        </h2>
        <a className="inline-link" href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer noopener">
          Get a free key <ExternalLink size={13} aria-hidden="true" />
        </a>
      </div>
      <Field
        label="API key"
        hint={remember ? 'Saved in this browser on this device only. Never in backups, never on GitHub.' : 'Kept for this visit only; forgotten when you close or refresh the page.'}
        wide
      >
        <span className="key-input">
          <input
            ref={input}
            type={show ? 'text' : 'password'}
            name="gemini-api-key"
            autoComplete="off"
            spellCheck={false}
            autoCapitalize="off"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && check()}
            placeholder="Paste the key from Google AI Studio"
          />
          <button type="button" className="icon-button" aria-label={show ? 'Hide key' : 'Show key'} onClick={() => setShow((v) => !v)}>
            {show ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </span>
      </Field>
      <label className="check">
        <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
        Remember the key on this device
      </label>
      <div className="actions">
        <button type="button" className="btn btn-primary" disabled={!!busy} onClick={check}>
          Save and check connection
        </button>
        {key && (
          <button
            type="button"
            className="btn btn-quiet"
            onClick={() => {
              setKey('', false);
              setValue('');
              setSteps([idle, idle, idle, idle]);
            }}
          >
            Forget key
          </button>
        )}
      </div>

      <ol className="steps" aria-live="polite">
        {steps.map((s, i) => (
          <li key={i} className={`step step-${s.state}`}>
            <StepMark s={s} />
            <div>
              <strong>{stepLabels[i]}</strong>
              <span>{s.text}</span>
              {s.detail && <code className="notice-detail">{s.detail}</code>}
            </div>
          </li>
        ))}
      </ol>

      <div className="form-grid">
        <Field label="Model" hint={models.length ? 'Listed live from your Google project.' : 'Run the check to list the models your key can use.'}>
          <select value={ws.settings.model} onChange={(e) => chooseModel(e.target.value)}>
            {!ws.settings.model && <option value="">Not chosen</option>}
            {ws.settings.model && !options.some((m) => m.id === ws.settings.model) && <option value={ws.settings.model}>{ws.settings.model}</option>}
            {options.map((m) => (
              <option key={m.id} value={m.id}>
                {m.id}
              </option>
            ))}
          </select>
        </Field>
        <div className="usage">
          <span className="field-label">Usage recorded</span>
          <span>
            {ws.calls.toLocaleString()} successful requests · {ws.usage.toLocaleString()} tokens
          </span>
        </div>
      </div>
      {models.length > 0 && (
        <label className="check">
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
          Show every model, including ones without free quota
        </label>
      )}
      <p className="term-note">
        Your $0 limit: keep the key’s Google project on the Free tier (AI Studio shows the tier beside each key). On the free tier Google stops at the quota instead of charging. Ascent never enables billing or switches to a paid
        model.
      </p>
    </section>
  );
}

function Preferences() {
  const { ws, update, notify } = useWorkspace();
  const [d, setD] = useState<Settings>(ws.settings);
  useEffect(() => setD(ws.settings), [ws.settings]);
  const dirty = JSON.stringify({ ...d, model: '' }) !== JSON.stringify({ ...ws.settings, model: '' });
  const total = components.reduce((s, k) => s + Math.max(0, d.weights[k] || 0), 0);
  const text = (k: 'roles' | 'locations' | 'excludedCompanies' | 'excludedRoles' | 'keywords') => ({ value: d[k], onChange: (e: { target: { value: string } }) => setD({ ...d, [k]: e.target.value }) });

  const save = () => {
    if (total <= 0) return notify({ tone: 'error', message: 'Give at least one scoring component a weight above zero.' });
    update((w) => ({ ...w, settings: { ...d, model: w.settings.model, modelOutputLimit: w.settings.modelOutputLimit } }), 'Preferences updated');
    notify({ tone: 'success', message: 'Preferences saved. Analyses that depend on them are marked for refresh.' });
  };

  return (
    <>
      <section className="sheet form-sheet" aria-labelledby="pref-title">
        <h2 id="pref-title" className="sheet-title">
          Career preferences
        </h2>
        <Field label="Target roles" hint="Comma separated. Passed to every analysis." wide>
          <textarea rows={3} {...text('roles')} />
        </Field>
        <Field label="Target markets" hint="Comma separated." wide>
          <textarea rows={2} {...text('locations')} />
        </Field>
        <div className="form-grid">
          <Field label="Exclude employers" hint="Hidden in Discover, greyed in your schedule">
            <input {...text('excludedCompanies')} />
          </Field>
          <Field label="Exclude roles containing" hint="e.g. intern, sales, retail">
            <input {...text('excludedRoles')} />
          </Field>
          <Field label="Extra keywords" hint="Skills or sectors to emphasise">
            <input {...text('keywords')} />
          </Field>
          <Field label="Minimum fit you act on" hint="Used by the “Fit only” filter">
            <input type="number" min={0} max={100} value={d.minScore} onChange={(e) => setD({ ...d, minScore: Math.max(0, Math.min(100, Number(e.target.value) || 0)) })} />
          </Field>
        </div>
      </section>

      <section className="sheet form-sheet" aria-labelledby="weights-title">
        <div className="sheet-title-row">
          <h2 id="weights-title" className="sheet-title">
            Scoring weights
          </h2>
          <button type="button" className="btn btn-sm btn-quiet" onClick={() => setD({ ...d, weights: initialWorkspace.settings.weights })}>
            Reset to default
          </button>
        </div>
        <table className="table weights">
          <thead>
            <tr>
              <th scope="col">Component</th>
              <th scope="col" className="num">
                Points
              </th>
              <th scope="col" className="num">
                Share
              </th>
            </tr>
          </thead>
          <tbody>
            {components.map((k) => (
              <tr key={k}>
                <th scope="row">{componentLabels[k]}</th>
                <td className="num">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    aria-label={`${componentLabels[k]} points`}
                    value={d.weights[k]}
                    onChange={(e) => setD({ ...d, weights: { ...d.weights, [k]: Math.max(0, Math.min(100, Number(e.target.value) || 0)) } })}
                  />
                </td>
                <td className="num">{total ? Math.round((Math.max(0, d.weights[k]) / total) * 100) : 0}%</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="term-note">Points are converted to shares of 100%. Changing them marks saved analyses for refresh.</p>
      </section>

      <div className={`savebar ${dirty ? 'is-dirty' : ''}`} aria-hidden={!dirty}>
        <span>Unsaved preferences</span>
        <button type="button" className="btn btn-quiet" tabIndex={dirty ? 0 : -1} onClick={() => setD(ws.settings)}>
          Discard
        </button>
        <button type="button" className="btn btn-primary" tabIndex={dirty ? 0 : -1} onClick={save}>
          Save preferences
        </button>
      </div>
    </>
  );
}

function Data() {
  const { ws, replace, run, notify, storageError } = useWorkspace();
  const file = useRef<HTMLInputElement>(null);
  const stamp = new Date().toISOString().slice(0, 10);
  return (
    <section className="sheet form-sheet" aria-labelledby="data-title">
      <h2 id="data-title" className="sheet-title">
        Data and backups
      </h2>
      <p className="term-note">
        Everything is stored in this browser on this device. It does not sync between your phone and laptop: export a backup on one and restore it on the other. Clearing browser data erases the local copy. Backups contain your
        résumé, so keep them private. They never contain your API key.
      </p>
      {storageError && <OpenTerm>{storageError}</OpenTerm>}
      <div className="actions">
        <button type="button" className="btn" onClick={() => downloadFile(`ascent-backup-${stamp}.json`, serialise(ws), 'application/json')}>
          <Download size={16} aria-hidden="true" /> Export backup
        </button>
        <button type="button" className="btn" onClick={() => file.current?.click()}>
          <Upload size={16} aria-hidden="true" /> Restore backup
        </button>
        <button
          type="button"
          className="btn btn-quiet btn-danger"
          onClick={() => {
            if (!window.confirm('Erase your profile, every vacancy and all history from this browser? Export a backup first if you may need them.')) return;
            replace(initialWorkspace, 'Workspace erased');
            notify({ tone: 'success', message: 'Workspace erased from this browser.' });
          }}
        >
          <Trash2 size={16} aria-hidden="true" /> Erase workspace
        </button>
      </div>
      <input
        ref={file}
        type="file"
        hidden
        accept="application/json,.json"
        onChange={(e) => {
          const f = e.target.files?.[0];
          e.target.value = '';
          if (!f) return;
          void run('Restoring backup', async () => {
            if (f.size > 20_000_000) throw new Error('That file is too large to be an Ascent backup.');
            const restored = parseWorkspace(await f.text());
            if (!window.confirm(`Replace this browser’s workspace with ${f.name}? It holds ${restored.jobs.length} vacancies${restored.profile.name ? ` for ${restored.profile.name}` : ''}.`)) return;
            replace(restored, `Restored from ${f.name}`);
            notify({ tone: 'success', message: `Backup restored: ${restored.jobs.length} vacancies.` });
          });
        }}
      />
    </section>
  );
}

export function SettingsView() {
  return (
    <div className="page page-narrow">
      <header className="page-head">
        <div>
          <h1>Settings</h1>
          <p className="lede">Your Gemini connection, what you are looking for, and how fit is weighted.</p>
        </div>
      </header>
      <Connection />
      <Preferences />
      <Data />
    </div>
  );
}
