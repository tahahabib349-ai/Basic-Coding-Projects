import { useRef } from 'react';
import { Upload } from 'lucide-react';
import { parseWorkspace } from '../lib/store';
import { useWorkspace } from '../state';

/** Loads only the profile from a private profile file or any Ascent backup. Jobs and settings stay as they are. */
export function ProfileImportButton({ className = 'btn', label = 'Load profile file' }: { className?: string; label?: string }) {
  const { run, update, notify } = useWorkspace();
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <button type="button" className={className} onClick={() => input.current?.click()}>
        <Upload size={16} aria-hidden="true" />
        {label}
      </button>
      <input
        ref={input}
        type="file"
        accept="application/json,.json"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = '';
          if (!file) return;
          void run('Reading profile file', async () => {
            if (file.size > 20_000_000) throw new Error('That file is too large to be an Ascent profile.');
            const incoming = parseWorkspace(await file.text());
            if (!incoming.profile.cv.trim()) throw new Error('That file has no résumé text in it.');
            update((w) => ({ ...w, profile: incoming.profile }), `Profile loaded from ${file.name}`);
            notify({ tone: 'success', message: `Profile loaded for ${incoming.profile.name || 'you'}. Check the open points marked [●] on the Profile page.` });
          });
        }}
      />
    </>
  );
}
