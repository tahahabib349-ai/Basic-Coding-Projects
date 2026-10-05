import { afterEach, describe, expect, it, vi } from 'vitest';
import { defaultSettings, emptyProfile, type Job } from '../src/lib/core';
import { dismissKey, runDiscovery, verifyLink } from '../src/lib/discovery';

afterEach(() => vi.unstubAllGlobals());

const settings = { ...defaultSettings, model: 'gemini-test-flash', locations: 'London, Dubai' };
const profile = { ...emptyProfile, cv: 'Investment banking analyst, project finance.', headline: 'IB' };
const chunks = [{ web: { uri: 'https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc', title: 'linkedin.com' } }, { web: { uri: 'https://vertexaisearch.cloud.google.com/grounding-api-redirect/def', title: 'careers.northgate.example' } }];
const reply = (payload: unknown, grounding = chunks) =>
  Response.json({ candidates: [{ finishReason: 'STOP', content: { parts: [{ text: JSON.stringify(payload) }] }, groundingMetadata: { groundingChunks: grounding } }], usageMetadata: { totalTokenCount: 500 } });

const job = (over: Partial<{ company: string; title: string; location: string; url: string }>) => ({
  company: 'Northgate Partners',
  title: 'Associate, Project Finance',
  location: 'London',
  url: 'https://www.linkedin.com/jobs/view/123',
  posted: '2 days ago',
  summary: 'Build project finance models, debt sizing and lender materials for infrastructure deals.',
  ...over,
});

describe('link verification', () => {
  it('accepts links whose site was among the search results and rejects invented ones', () => {
    const sources = chunks.map((c) => ({ uri: c.web.uri, title: c.web.title }));
    expect(verifyLink('https://www.linkedin.com/jobs/view/1', sources)).toBe(true);
    expect(verifyLink('https://careers.northgate.example/jobs/9', sources)).toBe(true);
    expect(verifyLink('https://made-up-bank.example/job', sources)).toBe(false);
    expect(verifyLink('javascript:alert(1)', sources)).toBe(false);
  });
});

describe('runDiscovery', () => {
  it('searches each market with Google Search grounding, filters, de-duplicates and screens', async () => {
    const bodies: string[] = [];
    const fetch = vi.fn(async (_url: string, init: RequestInit) => {
      if (init.method === 'GET') return Response.json({ models: [] });
      const body = String(init.body);
      bodies.push(body);
      if (body.includes('quick professional-fit score')) return reply({ results: [{ i: 0, score: 81, reason: 'Strong PF match' }, { i: 1, score: 40, reason: 'Too senior' }] });
      if (body.includes('open now in London'))
        return reply({
          jobs: [
            job({}),
            job({ company: 'Invented Bank', title: 'VP Infrastructure', url: 'https://invented-bank.example/vp' }),
            job({ company: 'Already Saved', title: 'Analyst', url: '' }),
            job({ company: 'Skipped Co', title: 'Analyst', url: 'https://www.linkedin.com/jobs/view/999' }),
            job({ company: 'NEEDS USER INPUT' }),
          ],
        });
      return reply({ jobs: [job({ location: 'Dubai', url: 'https://www.linkedin.com/jobs/view/123' })] });
    });
    vi.stubGlobal('fetch', fetch);

    const existing = [{ company: 'Already Saved', title: 'Analyst', location: 'London', url: '' } as Job];
    const dismissed = [dismissKey({ company: 'Skipped Co', title: 'Analyst', location: 'London', url: 'https://www.linkedin.com/jobs/view/999' })];
    const progress: string[] = [];
    const res = await runDiscovery({ key: 'k', settings }, profile, existing, dismissed, (t) => progress.push(t), { pauseMs: 0 });

    expect(res.searched).toEqual(['London', 'Dubai']);
    expect(res.found.map((j) => j.company)).toEqual(['Northgate Partners', 'Invented Bank']);
    const [real, invented] = res.found;
    expect(real.linkVerified).toBe(true);
    expect(real.url).toBe('https://www.linkedin.com/jobs/view/123');
    expect(real.screen).toEqual({ score: 81, reason: 'Strong PF match' });
    expect(real.source).toBe('Web search');
    expect(invented.linkVerified).toBe(false);
    expect(invented.url).toMatch(/^https:\/\/www\.google\.com\/search\?q=/);
    expect(res.calls).toBe(3);
    expect(progress[0]).toContain('London (1 of 2)');

    const search = JSON.parse(bodies[0]);
    expect(search.tools).toEqual([{ google_search: {} }]);
    expect(search.generationConfig.responseMimeType).toBeUndefined();
    const screen = JSON.parse(bodies.at(-1)!);
    expect(screen.tools).toBeUndefined();
    expect(screen.generationConfig.responseMimeType).toBe('application/json');
  });

  it('stops at a quota limit, keeps what it found and reports why', async () => {
    let n = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_u: string, init: RequestInit) => {
        if (init.method === 'GET') return Response.json({ models: [] });
        if (String(init.body).includes('quick professional-fit')) return reply({ results: [{ i: 0, score: 70, reason: 'ok' }] });
        n += 1;
        if (n === 1) return reply({ jobs: [job({})] });
        return Response.json({ error: { code: 429, status: 'RESOURCE_EXHAUSTED', message: 'Quota exceeded', details: [{ '@type': 'RetryInfo', retryDelay: '40s' }] } }, { status: 429 });
      }),
    );
    const res = await runDiscovery({ key: 'k', settings }, profile, [], [], () => {}, { pauseMs: 0 });
    expect(res.found).toHaveLength(1);
    expect(res.found[0].screen?.score).toBe(70);
    expect(res.stoppedBy).toMatchObject({ kind: 'quota' });
  });

  it('tries each free model until Google allows web search, then remembers it', async () => {
    const urls: string[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init: RequestInit) => {
        if (init.method === 'GET')
          return Response.json({ models: ['gemini-3.8-flash', 'gemini-3.5-flash-lite', 'gemini-3.6-flash', 'gemini-3.8-pro'].map((id) => ({ name: `models/${id}`, supportedGenerationMethods: ['generateContent'] })) });
        urls.push(url);
        if (String(init.body).includes('quick professional-fit')) return reply({ results: [{ i: 0, score: 75, reason: 'ok' }] });
        if (url.includes('/gemini-3.5-flash-lite:')) return Response.json({ error: { code: 429, status: 'RESOURCE_EXHAUSTED', message: 'Quota exceeded, limit: 0' } }, { status: 429 });
        if (url.includes('/gemini-3.8-flash:')) return Response.json({ error: { code: 429, status: 'RESOURCE_EXHAUSTED', message: 'You exceeded your current quota' } }, { status: 429 });
        return reply({ jobs: [job({})] });
      }),
    );
    const res = await runDiscovery({ key: 'k', settings: { ...settings, locations: 'London' } }, profile, [], [], () => {}, { pauseMs: 0 });
    expect(urls.slice(0, 3).map((u) => u.match(/models\/([^:]+)/)![1])).toEqual(['gemini-3.5-flash-lite', 'gemini-3.8-flash', 'gemini-3.6-flash']);
    expect(urls.join()).not.toContain('pro');
    expect(res.searchModel).toBe('gemini-3.6-flash');
    expect(res.found).toHaveLength(1);
    expect(res.stoppedBy).toBeUndefined();
  });

  it('explains when no free model can search', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_u: string, init: RequestInit) =>
        init.method === 'GET'
          ? Response.json({ models: [{ name: 'models/gemini-3.8-flash', supportedGenerationMethods: ['generateContent'] }] })
          : Response.json({ error: { code: 429, status: 'RESOURCE_EXHAUSTED', message: 'You exceeded your current quota' } }, { status: 429 }),
      ),
    );
    const res = await runDiscovery({ key: 'k', settings: { ...settings, locations: 'London' } }, profile, [], [], () => {}, { pauseMs: 0 });
    expect(res.stoppedBy?.message).toContain('does not currently include web search');
    expect(res.found).toHaveLength(0);
  });
});
