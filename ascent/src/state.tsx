import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { runDiscovery } from './lib/discovery';
import { describeError } from './lib/gemini';
import { loadKey, loadWorkspace, saveWorkspace, storeKey, type Workspace } from './lib/store';

export type Notice = { tone: 'error' | 'success' | 'info'; message: string; detail?: string };

type Ctx = {
  ws: Workspace;
  update: (mutate: (w: Workspace) => Workspace, action?: string) => void;
  replace: (w: Workspace, action: string) => void;
  key: string;
  setKey: (key: string, remember: boolean) => void;
  remembered: boolean;
  busy: string;
  run: (label: string, fn: () => Promise<void>) => Promise<void>;
  notice: Notice | null;
  notify: (n: Notice | null) => void;
  storageError: string;
  /** Progress text while the automatic job search runs; empty when idle. */
  searching: string;
  findJobs: (trigger: 'auto' | 'manual') => Promise<void>;
};

const WorkspaceContext = createContext<Ctx | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [initial] = useState(loadWorkspace);
  const [ws, setWs] = useState<Workspace>(initial.workspace);
  const [storageError, setStorageError] = useState(initial.error ?? '');
  const [blocked, setBlocked] = useState(!!initial.error);
  const [key, setKeyState] = useState(loadKey);
  const [remembered, setRemembered] = useState(() => !!loadKey());
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState<Notice | null>(initial.error ? { tone: 'error', message: initial.error } : null);
  const busyRef = useRef('');
  const [searching, setSearching] = useState('');
  const searchingRef = useRef(false);
  const latest = useRef({ ws, key });
  latest.current = { ws, key };

  useEffect(() => {
    if (blocked) return;
    try {
      saveWorkspace(ws);
      setStorageError('');
    } catch {
      setStorageError('This browser would not save your changes (storage full or disabled). Export a backup now.');
    }
  }, [ws, blocked]);

  const update = useCallback((mutate: (w: Workspace) => Workspace, action?: string) => {
    setWs((w) => {
      const next = mutate(w);
      return action ? { ...next, activity: [{ at: new Date().toISOString(), action }, ...w.activity].slice(0, 1000) } : next;
    });
  }, []);

  const replace = useCallback((w: Workspace, action: string) => {
    setBlocked(false);
    setWs({ ...w, activity: [{ at: new Date().toISOString(), action }, ...w.activity].slice(0, 1000) });
  }, []);

  const setKey = useCallback((value: string, remember: boolean) => {
    setKeyState(value);
    setRemembered(remember && !!value);
    storeKey(value, remember);
  }, []);

  const run = useCallback(async (label: string, fn: () => Promise<void>) => {
    if (busyRef.current) return;
    busyRef.current = label;
    setBusy(label);
    setNotice(null);
    try {
      await fn();
    } catch (e) {
      setNotice({ tone: 'error', ...describeError(e) });
    } finally {
      busyRef.current = '';
      setBusy('');
    }
  }, []);

  const findJobs = useCallback(
    async (trigger: 'auto' | 'manual') => {
      if (searchingRef.current) return;
      const { ws: w, key: k } = latest.current;
      if (!k || !w.settings.model) {
        if (trigger === 'manual') setNotice({ tone: 'error', message: 'Connect Gemini in Settings first; Ascent uses it to search for jobs.' });
        return;
      }
      if (!w.profile.cv.trim()) {
        if (trigger === 'manual') setNotice({ tone: 'error', message: 'Load your profile first; jobs are matched against your CV.' });
        return;
      }
      searchingRef.current = true;
      setSearching('Starting job search');
      try {
        const res = await runDiscovery({ key: k, settings: w.settings }, w.profile, w.jobs, w.dismissed, setSearching);
        const at = new Date().toISOString();
        const best = res.found.filter((j) => (j.screen?.score ?? 0) >= w.settings.minScore).length;
        setWs((cur) => ({
          ...cur,
          jobs: [...res.found, ...cur.jobs],
          calls: cur.calls + res.calls,
          usage: cur.usage + res.tokens,
          lastSearch: res.searched.length ? at : cur.lastSearch,
          activity: [
            { at, action: `Job search: ${res.found.length} new ${res.found.length === 1 ? 'role' : 'roles'} in ${res.searched.length} ${res.searched.length === 1 ? 'market' : 'markets'}` },
            ...cur.activity,
          ].slice(0, 1000),
        }));
        if (res.stoppedBy) {
          const d = describeError(res.stoppedBy);
          setNotice({
            tone: 'error',
            message: `${res.found.length ? `Found ${res.found.length} new roles, then the search stopped: ` : 'The job search stopped: '}${d.message}`,
            detail: d.detail,
          });
        } else
          setNotice({
            tone: res.found.length ? 'success' : 'info',
            message: res.found.length
              ? `Found ${res.found.length} new ${res.found.length === 1 ? 'role' : 'roles'}${best ? `, ${best} scoring ${w.settings.minScore}+` : ''}. They are under “New”.`
              : 'No new roles since the last search. Ascent will look again tomorrow.',
          });
      } catch (e) {
        setNotice({ tone: 'error', ...describeError(e) });
      } finally {
        searchingRef.current = false;
        setSearching('');
      }
    },
    [],
  );

  const value = useMemo(
    () => ({ ws, update, replace, key, setKey, remembered, busy, run, notice, notify: setNotice, storageError, searching, findJobs }),
    [ws, update, replace, key, setKey, remembered, busy, run, notice, storageError, searching, findJobs],
  );
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error('useWorkspace outside provider');
  return ctx;
}

/** Minimal hash router: #/, #/job/<id>, #/add, #/discover, #/profile, #/settings */
export function useRoute() {
  const read = () => window.location.hash.replace(/^#\/?/, '').split('/').filter(Boolean);
  const [parts, setParts] = useState(read);
  useEffect(() => {
    const on = () => {
      setParts(read());
      window.scrollTo(0, 0);
    };
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  return parts;
}

export const go = (path: string) => {
  window.location.hash = path.startsWith('#') ? path : `#/${path.replace(/^\//, '')}`;
};
