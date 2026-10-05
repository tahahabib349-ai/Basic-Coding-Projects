import { z } from 'zod';
import { assessmentSchema, components, defaultSettings, defaultWeights, emptyProfile, recommendations, statuses, type Job, type Profile, type Settings } from './core';

export const STORAGE_KEY = 'ascent-workspace-v2';
export const LEGACY_STORAGE_KEY = 'ascent-workspace-v1';
export const KEY_STORAGE = 'ascent-gemini-key';

export type Activity = { at: string; action: string };
export type Workspace = { version: 2; profile: Profile; settings: Settings; jobs: Job[]; activity: Activity[]; calls: number; usage: number; dismissed: string[]; lastSearch?: string };

export const initialWorkspace: Workspace = { version: 2, profile: emptyProfile, settings: defaultSettings, jobs: [], activity: [], calls: 0, usage: 0, dismissed: [] };

const profileSchema = z.object({
  name: z.string().max(200).default(''),
  headline: z.string().max(500).default(''),
  cv: z.string().max(45000).default(''),
  authorization: z.string().max(4000).default('NEEDS USER INPUT'),
  notice: z.string().max(1000).default('NEEDS USER INPUT'),
  salary: z.string().max(1000).default('NEEDS USER INPUT'),
  languages: z.string().max(1000).default('NEEDS USER INPUT'),
  experience: z.array(z.object({ company: z.string(), title: z.string(), dates: z.string() })).max(30).default([]),
  education: z.string().max(2000).default(''),
  certification: z.string().max(2000).default(''),
});

const weightsSchema = z
  .record(z.number().min(0).max(100))
  .transform((w) => Object.fromEntries(components.map((k) => [k, w[k] ?? defaultWeights[k]])) as Settings['weights']);

const settingsSchema = z.object({
  roles: z.string().default(defaultSettings.roles),
  locations: z.string().default(defaultSettings.locations),
  minScore: z.number().min(0).max(100).default(60),
  excludedCompanies: z.string().default(''),
  excludedRoles: z.string().default(''),
  keywords: z.string().default(''),
  ageDays: z.number().min(0).max(3650).default(45),
  model: z.string().default(''),
  modelOutputLimit: z.number().optional(),
  autoSearch: z.boolean().default(true),
  seniority: z.string().default(defaultSettings.seniority),
  weights: weightsSchema.default(defaultWeights),
});

const jobSchema = z.object({
  id: z.string(),
  company: z.string(),
  title: z.string(),
  location: z.string(),
  url: z.string(),
  description: z.string().max(45000),
  source: z.string(),
  found: z.string(),
  status: z.enum(statuses),
  history: z.array(z.object({ status: z.string(), at: z.string() })),
  notes: z.string().default(''),
  assessment: assessmentSchema.optional(),
  score: z.number().optional(),
  recommendation: z.enum(recommendations).optional(),
  cache: z.string().optional(),
  scoredAt: z.string().optional(),
  scoredWith: z.string().optional(),
  documents: z.array(z.object({ type: z.string(), content: z.string(), at: z.string() })).optional(),
  requirements: z.array(z.string()).optional(),
  deadline: z.string().optional(),
  screen: z.object({ score: z.number(), reason: z.string() }).optional(),
  posted: z.string().optional(),
  linkVerified: z.boolean().optional(),
});

/** Accepts version 2 workspaces and version 1 backups from the earlier Ascent site. */
export const workspaceSchema = z
  .object({
    version: z.union([z.literal(1), z.literal(2)]),
    profile: profileSchema,
    settings: settingsSchema.default(defaultSettings),
    jobs: z.array(jobSchema).max(5000).default([]),
    activity: z.array(z.object({ at: z.string(), action: z.string() })).max(2000).default([]),
    calls: z.number().default(0),
    usage: z.number().default(0),
    dismissed: z.array(z.string()).max(5000).default([]),
    lastSearch: z.string().optional(),
  })
  .transform((w): Workspace => {
    // Model names from the first version were guesses; make the user pick from their real list.
    const settings = w.version === 1 ? { ...w.settings, model: '' } : w.settings;
    return { ...w, version: 2, settings };
  });

export function parseWorkspace(raw: string): Workspace {
  let json: unknown;
  try {
    json = JSON.parse(raw);
  } catch {
    throw new Error('This file is not an Ascent backup (it is not valid JSON).');
  }
  const result = workspaceSchema.safeParse(json);
  if (!result.success) {
    const issue = result.error.issues[0];
    throw new Error(`This file is not a valid Ascent backup${issue ? ` (${issue.path.join('.') || 'file'}: ${issue.message})` : ''}.`);
  }
  return result.data;
}

export function loadWorkspace(): { workspace: Workspace; error?: string } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY) ?? localStorage.getItem(LEGACY_STORAGE_KEY);
    if (!raw) return { workspace: initialWorkspace };
    return { workspace: parseWorkspace(raw) };
  } catch (e) {
    return { workspace: initialWorkspace, error: `Your saved workspace could not be read: ${(e as Error).message} Restore a backup to continue.` };
  }
}

export function saveWorkspace(w: Workspace) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(w));
}

export function loadKey() {
  try {
    return localStorage.getItem(KEY_STORAGE) ?? '';
  } catch {
    return '';
  }
}
export function storeKey(key: string, remember: boolean) {
  try {
    if (remember && key) localStorage.setItem(KEY_STORAGE, key);
    else localStorage.removeItem(KEY_STORAGE);
  } catch {
    /* storage disabled: the key still works for this session */
  }
}

/** Backups never include the API key; it lives under a separate storage entry. */
export const serialise = (w: Workspace) => JSON.stringify(w, null, 2);

export function downloadFile(filename: string, content: string, type = 'text/plain') {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
