import { z } from 'zod';
import { canonicalURL, isDuplicate, isUnknown, safeURL, splitTerms, type Job, type Profile, type Settings } from './core';
import { GeminiError, generateJSON, listModels, rankModels, type WebSource } from './gemini';

/**
 * Automatic job finding: Gemini searches the live web (Google Search grounding) for vacancies
 * in each target market, then screens the new ones against the CV in one batch.
 * Links are kept only when they match a real search result; otherwise they become a web-search link.
 */

const RULES = [
  'You find real, currently open job vacancies for one candidate by searching the web.',
  'Only report vacancies you actually found in search results. Never invent employers, roles, links or dates.',
  'Prefer employer careers pages, LinkedIn, eFinancialCareers, Indeed, Bayt, GulfTalent, Naukrigulf, Rozee and recruiter sites.',
  'Skip expired postings, internships and roles clearly outside the target list.',
  'Return JSON only.',
].join('\n');

const foundSchema = z.object({
  jobs: z
    .array(
      z.object({
        company: z.string().default(''),
        title: z.string().default(''),
        location: z.string().default(''),
        url: z.string().default(''),
        posted: z.string().default(''),
        summary: z.string().default(''),
      }),
    )
    .default([])
    .transform((jobs) => jobs.slice(0, 12)),
});
type Found = z.infer<typeof foundSchema>['jobs'][number];

const screenSchema = z.object({
  results: z.array(z.object({ i: z.coerce.number(), score: z.coerce.number(), reason: z.string().default('') })).default([]),
});

export const dismissKey = (j: Pick<Job, 'company' | 'title' | 'location' | 'url'>) =>
  canonicalURL(j.url) || `${j.company}|${j.title}|${j.location}`.toLowerCase().replace(/\s+/g, ' ').trim();

const host = (u: string) => {
  try {
    return new URL(u).hostname.replace(/^www\./, '').toLowerCase();
  } catch {
    return '';
  }
};

/** A link counts as verified only when its site appears among the search results Gemini actually used. */
export function verifyLink(url: string, sources: WebSource[]) {
  const safe = safeURL(url);
  const h = host(safe);
  if (!h) return false;
  return sources.some((s) => {
    const t = s.title.toLowerCase().replace(/^www\./, '');
    const sh = host(s.uri);
    return (!!t && (h === t || h.endsWith(`.${t}`) || t.endsWith(`.${h}`))) || (!!sh && sh !== 'vertexaisearch.cloud.google.com' && sh === h);
  });
}

export const webSearchLink = (j: Pick<Found, 'company' | 'title' | 'location'>) =>
  `https://www.google.com/search?q=${encodeURIComponent(`${j.title} ${j.company} ${j.location} job`)}`;

type Ctx = { key: string; settings: Settings };

/**
 * Which free models include web search changes as Google retires models, so Ascent tries them in turn
 * and remembers the first that works. Google's own suggestion (3.5 Flash-Lite) goes first.
 */
export const FREE_SEARCH_MODELS = ['gemini-3.5-flash-lite', 'gemini-2.5-flash', 'gemini-2.5-flash-lite'];

export function searchModelOrder(settings: Settings, available: string[] = []) {
  const free = rankModels(available.map((id) => ({ id, displayName: id })))
    .map((m) => m.id)
    .sort((a, b) => Number(/lite/.test(b)) - Number(/lite/.test(a)));
  const preferred = available.length ? FREE_SEARCH_MODELS.filter((id) => available.includes(id)) : FREE_SEARCH_MODELS;
  return [...new Set([settings.searchModel, ...preferred, ...free].filter((m): m is string => !!m))];
}

/** Errors that mean "this model cannot search for free", so the next model is worth trying. */
const TRY_NEXT = new Set(['quota', 'no-free-quota', 'model', 'bad-request', 'permission']);

export async function searchMarket(ctx: Ctx, profile: Profile, market: string, model = ctx.settings.model) {
  const today = new Date().toISOString().slice(0, 10);
  const prompt = [
    `Today is ${today}. Search the web for job vacancies that are open now in ${market}.`,
    `Target roles: ${ctx.settings.roles}.`,
    `Suitable seniority: ${ctx.settings.seniority}. The candidate: ${profile.headline || 'finance professional'}; ${profile.experience
      .slice(0, 3)
      .map((e) => `${e.title} at ${e.company} (${e.dates})`)
      .join('; ')}.`,
    ctx.settings.keywords.trim() ? `Emphasise: ${ctx.settings.keywords}.` : '',
    `Prefer postings from the last ${ctx.settings.ageDays} days.`,
    'Return up to 10 distinct vacancies as {"jobs":[{"company":string,"title":string,"location":string,"url":string,"posted":string,"summary":string}]}.',
    'url: the posting link exactly as found. posted: the date shown on the posting, or "" if not shown. summary: 3–6 sentences on the responsibilities and requirements, from the posting.',
    'If you find nothing suitable, return {"jobs":[]}.',
  ]
    .filter(Boolean)
    .join('\n');
  return generateJSON(ctx.key, model, { system: RULES, prompt, search: true }, foundSchema);
}

export async function screenJobs(ctx: Ctx, profile: Profile, jobs: Pick<Job, 'company' | 'title' | 'location' | 'description'>[]) {
  const prompt = [
    'Give each vacancy a quick professional-fit score (0–100) for this candidate and one sentence of reasoning. Ignore work authorization.',
    'Shape: {"results":[{"i":number,"score":number,"reason":string}]} with one entry per vacancy, i = its number.',
    'CANDIDATE CV:',
    profile.cv,
    'VACANCIES:',
    JSON.stringify(jobs.map((j, i) => ({ i, company: j.company, title: j.title, location: j.location, summary: j.description.slice(0, 1200) }))),
  ].join('\n');
  return generateJSON(
    ctx.key,
    ctx.settings.model,
    { system: 'You are a finance recruiter screening vacancies against a CV. Use only facts in the CV. Return JSON only.', prompt, outputLimit: ctx.settings.modelOutputLimit },
    screenSchema,
  );
}

export type DiscoveryResult = { found: Job[]; tokens: number; calls: number; searched: string[]; searchModel?: string; stoppedBy?: GeminiError | Error };

const STOP_KINDS = new Set(['no-key', 'invalid-key', 'permission', 'api-disabled', 'referrer-blocked', 'location', 'quota', 'no-free-quota', 'network', 'model']);
const pause = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function runDiscovery(
  ctx: Ctx,
  profile: Profile,
  existing: Job[],
  dismissed: string[],
  onProgress: (text: string) => void,
  options: { pauseMs?: number } = {},
): Promise<DiscoveryResult> {
  const markets = splitTerms(ctx.settings.locations).map((m) => m.replace(/\b\w/g, (c) => c.toUpperCase()));
  const excludedCo = splitTerms(ctx.settings.excludedCompanies);
  const excludedRole = splitTerms(ctx.settings.excludedRoles);
  const skip = new Set(dismissed);
  const result: DiscoveryResult = { found: [], tokens: 0, calls: 0, searched: [] };
  const now = new Date().toISOString();

  let available: string[] = [];
  try {
    available = (await listModels(ctx.key)).map((x) => x.id);
  } catch {
    /* fall back to the known free search models */
  }
  const models = searchModelOrder(ctx.settings, available);
  const refused: string[] = [];
  let m = 0;
  for (const [n, market] of markets.entries()) {
    onProgress(`Searching ${market} (${n + 1} of ${markets.length})`);
    try {
      let reply: Awaited<ReturnType<typeof searchMarket>> | undefined;
      // A model without free search quota answers 429 or 404: move to the next free search model and retry this market.
      while (!reply) {
        try {
          reply = await searchMarket(ctx, profile, market, models[m]);
          result.searchModel = models[m];
        } catch (e) {
          // A model that already searched in this run and now refuses has hit a rate limit, not a missing feature.
          if (!(e instanceof GeminiError) || !TRY_NEXT.has(e.kind) || result.searchModel === models[m]) throw e;
          refused.push(`${models[m]}: ${e.status ?? ''} ${e.reason ?? ''}`.trim());
          onProgress(`Searching ${market}: ${models[m]} can’t search for free, trying another model`);
          if (m < models.length - 1) m += 1;
          else
            throw new GeminiError(
              'no-free-quota',
              `Google refused web search on all ${models.length} free models on your key. Your Google project’s free tier does not currently include web search, so Ascent cannot search through Gemini.`,
              { status: e.status, reason: refused.join(' | '), googleMessage: e.googleMessage },
            );
        }
      }
      const { data, tokens, sources } = reply;
      result.tokens += tokens;
      result.calls += 1;
      result.searched.push(market);
      for (const f of data.jobs) {
        if (isUnknown(f.company) || isUnknown(f.title) || f.summary.trim().length < 20) continue;
        if (excludedCo.some((t) => f.company.toLowerCase().includes(t)) || excludedRole.some((t) => f.title.toLowerCase().includes(t))) continue;
        const verified = verifyLink(f.url, sources);
        const candidate = { company: f.company.trim(), title: f.title.trim(), location: f.location.trim() || market, url: verified ? safeURL(f.url) : webSearchLink(f) };
        if (skip.has(dismissKey(candidate))) continue;
        if ([...existing, ...result.found].some((j) => isDuplicate(j, verified ? candidate : { ...candidate, url: '' }))) continue;
        result.found.push({
          id: crypto.randomUUID(),
          ...candidate,
          description: f.summary.trim(),
          source: 'Web search',
          found: now,
          status: 'DISCOVERED',
          history: [{ status: 'DISCOVERED', at: now }],
          notes: '',
          posted: f.posted.trim() || undefined,
          linkVerified: verified,
        });
      }
    } catch (e) {
      if (e instanceof GeminiError && STOP_KINDS.has(e.kind)) {
        result.stoppedBy = e;
        break;
      }
      // One market failing (an odd answer, a timeout) should not stop the others.
    }
    if (n < markets.length - 1) await pause(options.pauseMs ?? 1500);
  }

  for (let start = 0; start < result.found.length; start += 15) {
    const batch = result.found.slice(start, start + 15);
    onProgress(`Scoring ${result.found.length} new ${result.found.length === 1 ? 'role' : 'roles'} against your CV`);
    try {
      const { data, tokens } = await screenJobs(ctx, profile, batch);
      result.tokens += tokens;
      result.calls += 1;
      for (const r of data.results) {
        const job = batch[r.i];
        if (job) job.screen = { score: Math.max(0, Math.min(100, Math.round(r.score))), reason: r.reason.trim() };
      }
    } catch (e) {
      if (!result.stoppedBy) result.stoppedBy = e as Error;
      break;
    }
  }
  return result;
}
