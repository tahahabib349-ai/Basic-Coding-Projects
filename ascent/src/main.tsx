import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource-variable/hanken-grotesk';
import '@fontsource-variable/source-serif-4';
import './styles.css';
import App from './App';
import { WorkspaceProvider } from './state';

/** Browsers keep serving a saved copy after an update. Compare with the published version and reload once if stale. */
async function refreshIfStale() {
  try {
    const r = await fetch(`./version.json?t=${Date.now()}`, { cache: 'no-store' });
    if (!r.ok) return;
    const { build } = (await r.json()) as { build?: string };
    if (!build || build === __BUILD__) return;
    if (sessionStorage.getItem('ascent-reloaded-for') === build) return;
    sessionStorage.setItem('ascent-reloaded-for', build);
    // A new query string makes the browser fetch the page again instead of reusing its saved copy.
    window.location.replace(`${window.location.pathname}?v=${encodeURIComponent(build.split(' ')[0] + Date.now())}${window.location.hash}`);
  } catch {
    /* offline or storage blocked: keep the current copy */
  }
}
if (import.meta.env.PROD) {
  void refreshIfStale();
  document.addEventListener('visibilitychange', () => document.visibilityState === 'visible' && void refreshIfStale());
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <WorkspaceProvider>
      <App />
    </WorkspaceProvider>
  </StrictMode>,
);
