import { z } from 'zod';

/** The marker for any fact the user has not supplied. Never replaced by a guess. */
export const NEEDS_INPUT = 'NEEDS USER INPUT';

export const statuses = [
  'DISCOVERED',
  'REVIEWING',
  'STRONG MATCH',
  'PREPARING',
  'NEEDS USER INPUT',
  'READY FOR APPROVAL',
  'APPLIED',
  'ASSESSMENT',
  'INTERVIEW',
  'OFFER',
  'REJECTED',
  'WITHDRAWN',
  'SAVED FOR LATER',
] as const;
export type Status = (typeof statuses)[number];

/** Statuses grouped by where a vacancy is in the process, for the pipeline summary. */
export const stages: { label: string; statuses: Status[] }[] = [
  { label: 'New', statuses: ['DISCOVERED', 'REVIEWING', 'SAVED FOR LATER', 'NEEDS USER INPUT'] },
  { label: 'Preparing', statuses: ['STRONG MATCH', 'PREPARING', 'READY FOR APPROVAL'] },
  { label: 'Applied', statuses: ['APPLIED', 'ASSESSMENT'] },
  { label: 'Interviewing', statuses: ['INTERVIEW', 'OFFER'] },
  { label: 'Closed', statuses: ['REJECTED', 'WITHDRAWN'] },
];

export const components = ['role', 'experience', 'skills', 'sector', 'transactions', 'seniority', 'education', 'location'] as const;
export type Component = (typeof components)[number];

export const componentLabels: Record<Component, string> = {
  role: 'Role alignment',
  experience: 'Experience',
  skills: 'Technical skills',
  sector: 'Sector',
  transactions: 'Transaction record',
  seniority: 'Seniority',
  education: 'Education',
  location: 'Location',
};

export const defaultWeights: Record<Component, number> = {
  role: 20,
  experience: 15,
  skills: 20,
  sector: 10,
  transactions: 10,
  seniority: 10,
  education: 10,
  location: 5,
};

export const recommendations = ['STRONG APPLY', 'APPLY', 'BORDERLINE', 'LOW PRIORITY', 'NOT SUITABLE'] as const;
export type Recommendation = (typeof recommendations)[number];

export const authorizationValues = ['CONFIRMED ELIGIBLE', 'SPONSORSHIP REQUIRED', 'UNKNOWN', 'LIKELY INELIGIBLE', NEEDS_INPUT] as const;

const clampScore = z.coerce.number().transform((n) => Math.max(0, Math.min(100, Math.round(n))));
const text = (max: number) => z.string().transform((s) => s.trim().slice(0, max));
const list = z.array(z.string()).transform((items) => items.map((s) => s.trim()).filter(Boolean).slice(0, 12));

const componentSchema = z.object({ score: clampScore, reason: text(2000).pipe(z.string().min(1)) });

/** What Gemini must return for a fit analysis. Tolerant of small formatting drift, strict on substance. */
export const assessmentSchema = z.object({
  components: z.object({
    role: componentSchema,
    experience: componentSchema,
    skills: componentSchema,
    sector: componentSchema,
    transactions: componentSchema,
    seniority: componentSchema,
    education: componentSchema,
    location: componentSchema,
  }),
  strengths: list,
  gaps: list,
  summary: text(4000),
  authorization: z.enum(authorizationValues).catch(NEEDS_INPUT),
  authorization_reason: text(2000).catch(''),
});
export type Assessment = z.infer<typeof assessmentSchema>;

export const extractedSchema = z.object({
  company: text(250),
  title: text(250),
  location: text(250),
  requirements: list.optional().default([]),
  deadline: text(100).optional().default(''),
  authorization_info: text(2000).optional().default(''),
});
export type Extracted = z.infer<typeof extractedSchema>;

export const coverSchema = z.object({ content: z.string().min(20).max(15000) });

export type Experience = { company: string; title: string; dates: string };
export type Profile = {
  name: string;
  headline: string;
  cv: string;
  authorization: string;
  notice: string;
  salary: string;
  languages: string;
  experience: Experience[];
  education: string;
  certification: string;
};

export type Settings = {
  roles: string;
  locations: string;
  minScore: number;
  excludedCompanies: string;
  excludedRoles: string;
  keywords: string;
  ageDays: number;
  model: string;
  modelOutputLimit?: number;
  autoSearch: boolean;
  seniority: string;
  /** Model used for web search; empty means the free 2.5 Flash default. */
  searchModel?: string;
  weights: Record<Component, number>;
};

export type JobDocument = { type: string; content: string; at: string };
export type Job = {
  id: string;
  company: string;
  title: string;
  location: string;
  url: string;
  description: string;
  source: string;
  found: string;
  status: Status;
  history: { status: string; at: string }[];
  notes: string;
  assessment?: Assessment;
  score?: number;
  recommendation?: Recommendation;
  cache?: string;
  scoredAt?: string;
  scoredWith?: string;
  documents?: JobDocument[];
  requirements?: string[];
  deadline?: string;
  /** Quick screen made when Ascent found the job; the full analysis replaces it. */
  screen?: { score: number; reason: string };
  posted?: string;
  /** False when the link could not be matched to a real search result and points to a web search instead. */
  linkVerified?: boolean;
};

/** Public source ships no personal data. The user's résumé arrives through a private profile file. */
export const emptyProfile: Profile = {
  name: '',
  headline: '',
  cv: '',
  authorization: NEEDS_INPUT,
  notice: NEEDS_INPUT,
  salary: NEEDS_INPUT,
  languages: NEEDS_INPUT,
  experience: [],
  education: '',
  certification: '',
};

export const defaultSettings: Settings = {
  roles:
    'Investment Banking Analyst/Associate, Project Finance, Infrastructure Finance, Leveraged Finance, Acquisition Finance, Structured Finance, Corporate Finance, Private Equity, Infrastructure Private Equity, Investment Analyst, M&A, Debt Advisory',
  locations: 'London, Dubai, Abu Dhabi, Riyadh, Doha, Singapore, Hong Kong, Pakistan',
  minScore: 60,
  excludedCompanies: '',
  excludedRoles: '',
  keywords: '',
  ageDays: 30,
  model: '',
  autoSearch: true,
  seniority: 'Analyst, Senior Analyst, Associate',
  weights: defaultWeights,
};

export const isUnknown = (value: string | undefined | null) => !value || !value.trim() || value.trim().toUpperCase() === NEEDS_INPUT;

export function safeURL(value: string) {
  try {
    const u = new URL(value.trim());
    return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : '';
  } catch {
    return '';
  }
}

export function canonicalURL(value: string) {
  const safe = safeURL(value);
  if (!safe) return '';
  const u = new URL(safe);
  for (const k of [...u.searchParams.keys()]) {
    if (k.startsWith('utm_') || ['ref', 'source', 'src', 'trk', 'gh_src'].includes(k)) u.searchParams.delete(k);
  }
  u.hash = '';
  return u.toString().replace(/\/$/, '');
}

type JobIdentity = Pick<Job, 'company' | 'title' | 'location' | 'url'>;
export function isDuplicate(a: JobIdentity, b: JobIdentity) {
  const norm = (s: string) => s.toLowerCase().replace(/\s+/g, ' ').trim();
  const urlA = canonicalURL(a.url);
  if (urlA && urlA === canonicalURL(b.url)) return true;
  return (['company', 'title', 'location'] as const).every((k) => norm(a[k]) === norm(b[k]));
}

export function weightedScore(a: Assessment, w: Record<string, number>) {
  let sum = 0;
  let total = 0;
  for (const k of components) {
    const n = Number(w[k]);
    if (Number.isFinite(n) && n > 0) {
      sum += a.components[k].score * n;
      total += n;
    }
  }
  if (!total) throw new Error('At least one scoring weight must be above zero.');
  return Math.round(sum / total);
}

export function recommendation(score: number): Recommendation {
  if (score >= 85) return 'STRONG APPLY';
  if (score >= 70) return 'APPLY';
  if (score >= 55) return 'BORDERLINE';
  if (score >= 35) return 'LOW PRIORITY';
  return 'NOT SUITABLE';
}

/** Changes to these inputs make a saved analysis stale. The model choice does not. */
export function cacheKey(job: Pick<Job, 'description' | 'title' | 'company' | 'location'>, profile: Profile, settings: Settings) {
  return JSON.stringify([job.description, job.title, job.company, job.location, profile, settings.roles, settings.locations, settings.keywords, settings.weights]);
}

const entities: Record<string, string> = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', ndash: '–', mdash: '—', rsquo: '’', lsquo: '‘', rdquo: '”', ldquo: '“', hellip: '…', bull: '•' };
function decodeEntities(s: string) {
  return s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, code: string) => {
    if (code[0] === '#') {
      const n = code[1].toLowerCase() === 'x' ? parseInt(code.slice(2), 16) : parseInt(code.slice(1), 10);
      return Number.isFinite(n) ? String.fromCodePoint(n) : m;
    }
    return entities[code.toLowerCase()] ?? m;
  });
}

/** Turns feed HTML (including Greenhouse's entity-escaped HTML) into plain text. Never renders it. */
export function htmlToText(input: string) {
  let s = decodeEntities(input);
  s = s
    .replace(/<(script|style)[\s\S]*?<\/\1>/gi, '')
    .replace(/<li[^>]*>/gi, '\n• ')
    .replace(/<\/(p|div|li|ul|ol|h[1-6]|tr|section)>/gi, '\n')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<[^>]*>/g, '');
  s = decodeEntities(s);
  return s
    .replace(/[ \t ]+/g, ' ')
    .replace(/ *\n */g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

export const splitTerms = (s: string) =>
  s
    .split(',')
    .map((x) => x.trim().toLowerCase())
    .filter(Boolean);

/** Removes surrounding whitespace and one pair of matching quotes, which copy-paste often adds. */
export function normalizeAPIKey(value: string) {
  const key = value.trim();
  const pairs: Record<string, string> = { '"': '"', "'": "'", '“': '”', '‘': '’', '`': '`' };
  if (key.length > 1 && pairs[key[0]] === key[key.length - 1]) return key.slice(1, -1).trim();
  return key;
}
