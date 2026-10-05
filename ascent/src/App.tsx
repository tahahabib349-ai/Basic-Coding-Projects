import { useEffect, useRef } from 'react';
import { Plus, Radar, Settings as SettingsIcon, Table2, UserRound } from 'lucide-react';
import { NoticeBar } from './components/ui';
import { go, useRoute, useWorkspace } from './state';
import { AddVacancy } from './views/AddVacancy';
import { Discover } from './views/Discover';
import { JobSheet } from './views/JobSheet';
import { Opportunities } from './views/Opportunities';
import { ProfileView } from './views/Profile';
import { SettingsView } from './views/Settings';

const nav = [
  { path: '', label: 'Opportunities', short: 'Schedule', Icon: Table2 },
  { path: 'discover', label: 'Find jobs', short: 'Find jobs', Icon: Radar },
  { path: 'profile', label: 'Profile', short: 'Profile', Icon: UserRound },
  { path: 'settings', label: 'Settings', short: 'Settings', Icon: SettingsIcon },
];

export function Mark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className="mark">
      <path d="M2.5 19.5 9.5 7l3.6 6.1 2.4-3.8 6 10.2Z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}

function GeminiState() {
  const { key, ws } = useWorkspace();
  const ready = !!key && !!ws.settings.model;
  return (
    <a href="#/settings" className={`gemini-state ${ready ? 'is-ready' : 'is-open'}`}>
      <span className="gemini-dot" aria-hidden="true" />
      <span>
        {ready ? 'Gemini ready' : key ? 'Choose a model' : 'Gemini not connected'}
        <small>{ready ? ws.settings.model : 'Open Settings'}</small>
      </span>
    </a>
  );
}

/** Runs the job search once a day, the first time Ascent is opened with everything set up. */
function useDailySearch() {
  const { ws, key, findJobs } = useWorkspace();
  const started = useRef(false);
  const due = !ws.lastSearch || Date.now() - new Date(ws.lastSearch).getTime() > 20 * 3_600_000;
  const ready = ws.settings.autoSearch && !!key && !!ws.settings.model && !!ws.profile.cv.trim();
  useEffect(() => {
    if (started.current || !ready || !due) return;
    const t = setTimeout(() => {
      started.current = true;
      void findJobs('auto');
    }, 800);
    return () => clearTimeout(t);
  }, [ready, due, findJobs]);
}

export default function App() {
  useDailySearch();
  const route = useRoute();
  const section = route[0] ?? '';
  const active = section === 'job' || section === 'add' ? '' : section;

  let view;
  if (section === 'job' && route[1]) view = <JobSheet id={route[1]} />;
  else if (section === 'add') view = <AddVacancy />;
  else if (section === 'discover') view = <Discover />;
  else if (section === 'profile') view = <ProfileView />;
  else if (section === 'settings') view = <SettingsView />;
  else view = <Opportunities />;

  return (
    <div className="app">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <aside className="rail">
        <a href="#/" className="brand">
          <Mark size={26} />
          <span>Ascent</span>
        </a>
        <nav aria-label="Main">
          {nav.map(({ path, label, Icon }) => (
            <a key={path} href={`#/${path}`} className={active === path ? 'is-active' : ''} aria-current={active === path ? 'page' : undefined}>
              <Icon size={18} aria-hidden="true" />
              {label}
            </a>
          ))}
        </nav>
        <div className="rail-foot">
          <GeminiState />
          <p className="rail-note">Ascent prepares. You decide and submit. Nothing is ever sent on your behalf.</p>
        </div>
      </aside>

      <header className="topbar">
        <a href="#/" className="brand">
          <Mark size={22} />
          <span>Ascent</span>
        </a>
        <button type="button" className="btn btn-on-house" onClick={() => go('add')}>
          <Plus size={17} aria-hidden="true" />
          Add vacancy
        </button>
      </header>

      <main id="main" className="main" tabIndex={-1}>
        <NoticeBar />
        {view}
      </main>

      <nav className="tabbar" aria-label="Main">
        {nav.map(({ path, short, Icon }) => (
          <a key={path} href={`#/${path}`} className={active === path ? 'is-active' : ''} aria-current={active === path ? 'page' : undefined}>
            <Icon size={20} aria-hidden="true" />
            <span>{short}</span>
          </a>
        ))}
      </nav>
    </div>
  );
}
