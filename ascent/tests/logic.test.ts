import { afterEach, describe, expect, it, vi } from 'vitest';
import { assessmentSchema, cacheKey, components, defaultSettings, emptyProfile, htmlToText, isDuplicate, normalizeAPIKey, recommendation, safeURL, weightedScore } from '../src/lib/core';
import { explainGoogleError, generateJSON, GeminiError, isFreeTierTextModel, listModels, parseJSONText, rankModels } from '../src/lib/gemini';
import { assessFit, testConnection } from '../src/lib/ai';
import { boardFromInput, readFeed } from '../src/lib/feeds';
import { parseWorkspace, initialWorkspace } from '../src/lib/store';
import { z } from 'zod';

const assessment = {
  components: Object.fromEntries(components.map((k) => [k, { score: 80, reason: 'Evidence from the CV' }])),
  strengths: ['Debt structuring'],
  gaps: ['UK work authorization unknown'],
  summary: 'Good professional fit.',
  authorization: 'NEEDS USER INPUT',
  authorization_reason: 'Not supplied',
};

const geminiReply = (payload: unknown, finishReason = 'STOP') =>
  Response.json({ candidates: [{ finishReason, content: { parts: [{ text: 'thinking…', thought: true }, { text: typeof payload === 'string' ? payload : JSON.stringify(payload) }] } }], usageMetadata: { totalTokenCount: 321 } });

afterEach(() => vi.unstubAllGlobals());

describe('core', () => {
  it('weights, thresholds and URL safety', () => {
    const a = assessmentSchema.parse(assessment);
    expect(weightedScore(a, defaultSettings.weights)).toBe(80);
    expect(recommendation(85)).toBe('STRONG APPLY');
    expect(recommendation(70)).toBe('APPLY');
    expect(recommendation(34)).toBe('NOT SUITABLE');
    expect(safeURL('javascript:alert(1)')).toBe('');
    expect(() => weightedScore(a, Object.fromEntries(components.map((k) => [k, 0])))).toThrow();
  });

  it('assessment schema clamps scores, coerces strings and tolerates odd authorization values', () => {
    const odd = { ...assessment, components: { ...assessment.components, role: { score: '140', reason: ' ok ' } }, authorization: 'maybe' };
    const parsed = assessmentSchema.parse(odd);
    expect(parsed.components.role).toEqual({ score: 100, reason: 'ok' });
    expect(parsed.authorization).toBe('NEEDS USER INPUT');
    expect(assessmentSchema.safeParse({ ...assessment, components: {} }).success).toBe(false);
  });

  it('detects duplicates by canonical URL or by employer/role/market', () => {
    expect(isDuplicate({ company: 'A', title: 'X', location: 'London', url: 'https://ex.com/job?utm_source=li' }, { company: 'B', title: 'Y', location: 'Dubai', url: 'https://ex.com/job/' })).toBe(true);
    expect(isDuplicate({ company: ' A ', title: 'Analyst', location: 'London', url: '' }, { company: 'a', title: 'analyst', location: ' london', url: '' })).toBe(true);
    expect(isDuplicate({ company: 'A', title: 'Analyst', location: 'London', url: '' }, { company: 'A', title: 'Associate', location: 'London', url: '' })).toBe(false);
  });

  it('marks analyses stale when the profile changes but not when the model changes', () => {
    const job = { description: 'd', title: 't', company: 'c', location: 'l' };
    const k = cacheKey(job, emptyProfile, defaultSettings);
    expect(cacheKey(job, emptyProfile, { ...defaultSettings, model: 'other' })).toBe(k);
    expect(cacheKey(job, { ...emptyProfile, cv: 'new' }, defaultSettings)).not.toBe(k);
  });

  it('normalises pasted keys without judging their format', () => {
    expect(normalizeAPIKey('  “opaque-key”  ')).toBe('opaque-key');
    expect(normalizeAPIKey(' "AIzaSyX" ')).toBe('AIzaSyX');
    expect(normalizeAPIKey('a.b-c_d')).toBe('a.b-c_d');
  });

  it('converts Greenhouse entity-escaped HTML to text without leaving tags', () => {
    const text = htmlToText('&lt;p&gt;Financial &amp;amp; modelling&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Debt&lt;/li&gt;&lt;/ul&gt;');
    expect(text).toContain('Financial & modelling');
    expect(text).toContain('• Debt');
    expect(text).not.toMatch(/<|&lt;/);
  });
});

describe('Gemini error explanations', () => {
  const body = (status: string, message: string, details: Record<string, unknown>[] = []) => ({ error: { code: 0, status, message, details } });

  it('identifies an invalid key from Google’s real error shape', () => {
    const e = explainGoogleError(400, body('INVALID_ARGUMENT', 'API key not valid. Please pass a valid API key.', [{ '@type': 'type.googleapis.com/google.rpc.ErrorInfo', reason: 'API_KEY_INVALID' }]));
    expect(e.kind).toBe('invalid-key');
    expect(e.detail).toContain('HTTP 400');
    expect(e.detail).toContain('API_KEY_INVALID');
  });

  it('separates a zero free quota from a temporary rate limit', () => {
    const zero = explainGoogleError(429, body('RESOURCE_EXHAUSTED', 'Quota exceeded for metric generate_content_free_tier_requests, limit: 0', [{ '@type': 'QuotaFailure', violations: [{ quotaValue: '0' }] }]), 'gemini-x-pro');
    expect(zero.kind).toBe('no-free-quota');
    const temp = explainGoogleError(429, body('RESOURCE_EXHAUSTED', 'Quota exceeded', [{ '@type': 'RetryInfo', retryDelay: '31s' }]), 'gemini-x-flash');
    expect(temp.kind).toBe('quota');
    expect(temp.message).toContain('31s');
  });

  it('names disabled APIs, website restrictions, unsupported locations and missing models', () => {
    expect(explainGoogleError(403, body('PERMISSION_DENIED', 'x', [{ reason: 'SERVICE_DISABLED' }])).kind).toBe('api-disabled');
    expect(explainGoogleError(403, body('PERMISSION_DENIED', 'Requests from referer https://x are blocked.', [{ reason: 'API_KEY_HTTP_REFERRER_BLOCKED' }])).kind).toBe('referrer-blocked');
    expect(explainGoogleError(400, body('FAILED_PRECONDITION', 'User location is not supported for the API use.')).kind).toBe('location');
    expect(explainGoogleError(404, body('NOT_FOUND', 'models/x is not found'), 'x').kind).toBe('model');
    expect(explainGoogleError(503, null).kind).toBe('server');
  });
});

describe('Gemini client', () => {
  it('sends the key only in the x-goog-api-key header, to Google, and parses JSON past thought parts', async () => {
    const fetch = vi.fn(async () => geminiReply({ ok: true }));
    vi.stubGlobal('fetch', fetch);
    const out = await testConnection('secret-key', 'gemini-9-flash');
    expect(out.data).toEqual({ ok: true });
    expect(out.tokens).toBe(321);
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('https://generativelanguage.googleapis.com/v1beta/models/gemini-9-flash:generateContent');
    expect((init.headers as Record<string, string>)['x-goog-api-key']).toBe('secret-key');
    expect(url).not.toContain('secret-key');
    expect(String(init.body)).not.toContain('secret-key');
  });

  it('scores a vacancy and keeps authorization separate', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => geminiReply('```json\n' + JSON.stringify(assessment) + '\n```')));
    const job = { id: '1', company: 'Bank', title: 'Analyst', location: 'London', url: '', description: 'Project finance analyst', source: 'Manual', found: '', status: 'DISCOVERED' as const, history: [], notes: '' };
    const { data } = await assessFit({ key: 'k', settings: { ...defaultSettings, model: 'm' } }, { ...emptyProfile, cv: 'CV text' }, job);
    expect(data.authorization).toBe('NEEDS USER INPUT');
    expect(weightedScore(data, defaultSettings.weights)).toBe(80);
  });

  it('reports truncated output, missing keys, network failures and incomplete answers distinctly', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => geminiReply('{"ok":', 'MAX_TOKENS')));
    await expect(testConnection('k', 'm')).rejects.toMatchObject({ kind: 'truncated' });
    await expect(testConnection('', 'm')).rejects.toMatchObject({ kind: 'no-key' });
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))));
    await expect(testConnection('k', 'm')).rejects.toMatchObject({ kind: 'network' });
    vi.stubGlobal('fetch', vi.fn(async () => geminiReply({ components: {} })));
    const err = await generateJSON('k', 'm', { system: '', prompt: '' }, assessmentSchema).catch((e) => e);
    expect(err).toBeInstanceOf(GeminiError);
    expect(err.kind).toBe('malformed');
    expect(err.reason).toContain('components');
  });

  it('lists models and ranks free-tier Flash models first', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Response.json({
          models: [
            { name: 'models/gemini-2.5-flash', supportedGenerationMethods: ['generateContent'], outputTokenLimit: 65536 },
            { name: 'models/gemini-3.8-flash', supportedGenerationMethods: ['generateContent'] },
            { name: 'models/gemini-3.8-pro', supportedGenerationMethods: ['generateContent'] },
            { name: 'models/gemini-3.5-flash-lite', supportedGenerationMethods: ['generateContent'] },
            { name: 'models/gemini-3.9-flash-preview', supportedGenerationMethods: ['generateContent'] },
            { name: 'models/gemini-2.5-flash-image', supportedGenerationMethods: ['generateContent'] },
            { name: 'models/text-embedding-004', supportedGenerationMethods: ['embedContent'] },
          ],
        }),
      ),
    );
    const models = await listModels('k');
    expect(models.map((m) => m.id)).not.toContain('text-embedding-004');
    expect(rankModels(models).map((m) => m.id)).toEqual(['gemini-3.8-flash', 'gemini-3.5-flash-lite', 'gemini-2.5-flash', 'gemini-3.9-flash-preview']);
    expect(isFreeTierTextModel('gemini-3.8-pro')).toBe(false);
  });

  it('extracts JSON from fenced or chatty text', () => {
    expect(parseJSONText('Here you go: {"a":1} done')).toEqual({ a: 1 });
    expect(z.object({ a: z.number() }).parse(parseJSONText('```json\n{"a":2}\n```'))).toEqual({ a: 2 });
  });
});

describe('storage and backups', () => {
  it('round-trips a workspace and never includes an API key', () => {
    const ws = { ...initialWorkspace, profile: { ...emptyProfile, name: 'Test', cv: 'x'.repeat(40) } };
    const text = JSON.stringify(ws);
    expect(parseWorkspace(text).profile.name).toBe('Test');
    expect(text).not.toMatch(/apiKey|AIza/);
  });

  it('imports version 1 backups from the earlier site and clears guessed model names', () => {
    const v1 = { version: 1, profile: { ...emptyProfile, cv: 'x'.repeat(40) }, settings: { ...defaultSettings, model: 'gemini-3.8-flash' }, jobs: [], activity: [], calls: 2, usage: 10 };
    const ws = parseWorkspace(JSON.stringify(v1));
    expect(ws.version).toBe(2);
    expect(ws.settings.model).toBe('');
    expect(ws.calls).toBe(2);
  });

  it('rejects files that are not backups with a specific reason', () => {
    expect(() => parseWorkspace('not json')).toThrow(/not valid JSON/);
    expect(() => parseWorkspace('{"version":3}')).toThrow(/not a valid Ascent backup/);
  });
});

describe('employer feeds', () => {
  it('accepts careers links as well as board names', () => {
    expect(boardFromInput('https://boards.greenhouse.io/examplebank/jobs/123')).toBe('examplebank');
    expect(boardFromInput('https://jobs.lever.co/acme')).toBe('acme');
    expect(boardFromInput('plain')).toBe('plain');
  });

  it('parses a Greenhouse board into plain-text vacancies with the employer’s name', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        url.endsWith('/jobs?content=true')
          ? Response.json({ jobs: [{ id: 1, title: 'Project Finance Analyst', location: { name: 'London' }, absolute_url: 'https://boards.greenhouse.io/t/jobs/1', content: '&lt;p&gt;Infrastructure debt.&lt;/p&gt;', updated_at: '2026-09-01' }] })
          : Response.json({ name: 'Test Capital' }),
      ),
    );
    const out = await readFeed('greenhouse', 'test');
    expect(out.company).toBe('Test Capital');
    expect(out.jobs[0]).toMatchObject({ title: 'Project Finance Analyst', location: 'London', description: 'Infrastructure debt.' });
  });

  it('rejects unsafe board names before any request', async () => {
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    await expect(readFeed('greenhouse', '../../secret')).rejects.toThrow();
    expect(fetch).not.toHaveBeenCalled();
  });
});
