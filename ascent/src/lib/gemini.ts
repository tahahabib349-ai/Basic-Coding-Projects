import { z } from 'zod';

/**
 * Direct browser client for the Gemini Developer API.
 * Google allows cross-origin calls, so no server sits between the user and Google.
 * The key travels only in the x-goog-api-key header to generativelanguage.googleapis.com.
 */
export const API_ROOT = 'https://generativelanguage.googleapis.com/v1beta';

export type GeminiErrorKind =
  | 'no-key'
  | 'network'
  | 'invalid-key'
  | 'permission'
  | 'api-disabled'
  | 'referrer-blocked'
  | 'location'
  | 'quota'
  | 'no-free-quota'
  | 'model'
  | 'bad-request'
  | 'server'
  | 'truncated'
  | 'blocked'
  | 'malformed'
  | 'timeout';

export class GeminiError extends Error {
  readonly kind: GeminiErrorKind;
  readonly status?: number;
  readonly reason?: string;
  readonly googleMessage?: string;
  readonly retryAfter?: string;
  constructor(kind: GeminiErrorKind, message: string, extra: { status?: number; reason?: string; googleMessage?: string; retryAfter?: string } = {}) {
    super(message);
    this.name = 'GeminiError';
    this.kind = kind;
    Object.assign(this, extra);
  }
  /** One line for the technical-details disclosure. Never contains the key. */
  get detail() {
    return [this.status && `HTTP ${this.status}`, this.reason, this.googleMessage && `Google: “${this.googleMessage}”`].filter(Boolean).join(' · ');
  }
}

type GoogleErrorBody = {
  error?: {
    code?: number;
    message?: string;
    status?: string;
    details?: { '@type'?: string; reason?: string; retryDelay?: string; violations?: { quotaId?: string; quotaValue?: string; quotaMetric?: string }[] }[];
  };
};

/** Turns Google's error response into a specific, plain-English explanation. */
export function explainGoogleError(status: number, body: GoogleErrorBody | null, model?: string): GeminiError {
  const err = body?.error;
  const googleMessage = err?.message?.slice(0, 400);
  const details = err?.details ?? [];
  const reason = details.find((d) => d.reason)?.reason ?? err?.status;
  const retryDelay = details.find((d) => d.retryDelay)?.retryDelay;
  const quotaZero = details.some((d) => d.violations?.some((v) => v.quotaValue === '0')) || /limit:\s*0\b/.test(googleMessage ?? '');
  const extra = { status, reason, googleMessage, retryAfter: retryDelay };
  const msg = googleMessage ?? '';

  if (reason === 'API_KEY_INVALID' || /API key not valid/i.test(msg))
    return new GeminiError('invalid-key', 'Google does not recognise this API key. Copy it again from Google AI Studio → API keys (the whole key, nothing else).', extra);
  if (reason === 'API_KEY_HTTP_REFERRER_BLOCKED' || /referer|referrer/i.test(msg))
    return new GeminiError('referrer-blocked', 'This key is restricted to other websites. In Google Cloud → Credentials, allow this site’s address for the key, or remove the website restriction.', extra);
  if (reason === 'SERVICE_DISABLED' || reason === 'API_KEY_SERVICE_BLOCKED' || /has not been used in project|is disabled/i.test(msg))
    return new GeminiError('api-disabled', 'The Gemini API is not enabled for this key’s Google project. Create the key from Google AI Studio, which enables it automatically.', extra);
  if (/location is not supported/i.test(msg))
    return new GeminiError('location', 'Google does not offer the Gemini API in the country your connection appears to come from. A VPN or office proxy can cause this.', extra);
  if (status === 429) {
    if (quotaZero)
      return new GeminiError('no-free-quota', `${model ?? 'This model'} has no free quota on your project. Pick a Flash or Flash-Lite model in Settings; Ascent never switches to a paid option.`, extra);
    return new GeminiError(
      'quota',
      `You have reached the free request limit for ${model ?? 'this model'}${retryDelay ? `. Google says retry in ${retryDelay}` : '. Wait a minute and retry'}. No paid fallback was used.`,
      extra,
    );
  }
  if (status === 404) return new GeminiError('model', `The model “${model}” is not available to your project. Choose another model in Settings.`, extra);
  if (status === 401 || status === 403)
    return new GeminiError('permission', 'Google refused this key for the Gemini API. Check the key’s project in Google AI Studio.', extra);
  if (status >= 500) return new GeminiError('server', 'Google’s Gemini service is busy or failing right now. Retry in a few minutes.', extra);
  return new GeminiError('bad-request', 'Google rejected the request. The technical details below say why.', extra);
}

async function call(url: string, key: string, init: RequestInit & { timeoutMs?: number } = {}) {
  if (!key) throw new GeminiError('no-key', 'Add your Gemini API key in Settings first.');
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: { 'Content-Type': 'application/json', 'x-goog-api-key': key, ...(init.headers ?? {}) },
      signal: AbortSignal.timeout(init.timeoutMs ?? 90_000),
    });
  } catch (e) {
    if (e instanceof DOMException && (e.name === 'TimeoutError' || e.name === 'AbortError'))
      throw new GeminiError('timeout', 'Gemini took too long to answer. Retry; long job descriptions take longer.');
    throw new GeminiError(
      'network',
      'Your browser could not reach Google (generativelanguage.googleapis.com). You may be offline, or an office network or firewall may block it. Try another network, such as your phone’s data.',
    );
  }
  return response;
}

export type ModelInfo = { id: string; displayName: string; outputTokenLimit?: number; inputTokenLimit?: number };

/** Lists the models this key can actually call, so the model menu never offers one that does not exist. */
export async function listModels(key: string): Promise<ModelInfo[]> {
  const models: ModelInfo[] = [];
  let pageToken = '';
  for (let page = 0; page < 5; page++) {
    const r = await call(`${API_ROOT}/models?pageSize=1000${pageToken ? `&pageToken=${encodeURIComponent(pageToken)}` : ''}`, key, { method: 'GET', timeoutMs: 20_000 });
    const body = (await r.json().catch(() => null)) as
      | (GoogleErrorBody & { models?: { name: string; displayName?: string; supportedGenerationMethods?: string[]; outputTokenLimit?: number; inputTokenLimit?: number }[]; nextPageToken?: string })
      | null;
    if (!r.ok) throw explainGoogleError(r.status, body);
    for (const m of body?.models ?? []) {
      if (!m.supportedGenerationMethods?.includes('generateContent')) continue;
      models.push({ id: m.name.replace(/^models\//, ''), displayName: m.displayName ?? m.name, outputTokenLimit: m.outputTokenLimit, inputTokenLimit: m.inputTokenLimit });
    }
    if (!body?.nextPageToken) break;
    pageToken = body.nextPageToken;
  }
  return models;
}

const version = (id: string) => {
  const m = id.match(/gemini-(\d+(?:\.\d+)?)/);
  return m ? Number(m[1]) : 0;
};

/** Free tier covers Flash and Flash-Lite text models. Excludes image, audio, TTS, live and embedding variants. */
export function isFreeTierTextModel(id: string) {
  return /^gemini-[\d.]+-flash(-lite)?(-latest|-preview(-[\w-]+)?|-\d{3})?$/.test(id) && !/(image|tts|audio|live|thinking-exp|embedding)/.test(id);
}

/** Free-tier text models first, newest first, stable before preview. */
export function rankModels(models: ModelInfo[]) {
  const preview = (id: string) => (/preview|exp|latest/.test(id) ? 1 : 0);
  const lite = (id: string) => (/lite/.test(id) ? 1 : 0);
  return [...models]
    .filter((m) => isFreeTierTextModel(m.id))
    .sort((a, b) => preview(a.id) - preview(b.id) || version(b.id) - version(a.id) || lite(a.id) - lite(b.id) || a.id.localeCompare(b.id));
}

export type WebSource = { uri: string; title: string };

type GenerateResponse = {
  candidates?: {
    finishReason?: string;
    content?: { parts?: { text?: string; thought?: boolean }[] };
    groundingMetadata?: { groundingChunks?: { web?: { uri?: string; title?: string } }[] };
  }[];
  promptFeedback?: { blockReason?: string };
  usageMetadata?: { totalTokenCount?: number };
};

export function parseJSONText(raw: string): unknown {
  const trimmed = raw
    .trim()
    .replace(/^```(?:json)?\s*/i, '')
    .replace(/```\s*$/, '')
    .trim();
  try {
    return JSON.parse(trimmed);
  } catch {
    const start = trimmed.indexOf('{');
    const end = trimmed.lastIndexOf('}');
    if (start >= 0 && end > start) return JSON.parse(trimmed.slice(start, end + 1));
    throw new Error('not json');
  }
}

export async function generateJSON<T>(
  key: string,
  model: string,
  request: { system: string; prompt: string; outputLimit?: number; search?: boolean },
  schema: z.ZodType<T, z.ZodTypeDef, unknown>,
): Promise<{ data: T; tokens: number; sources: WebSource[] }> {
  if (!model) throw new GeminiError('model', 'Choose a Gemini model in Settings first (run the connection check to list yours).');
  const maxOutputTokens = Math.min(16_384, request.outputLimit ?? 16_384);
  const r = await call(`${API_ROOT}/models/${encodeURIComponent(model)}:generateContent`, key, {
    method: 'POST',
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: request.system }] },
      contents: [{ role: 'user', parts: [{ text: request.prompt }] }],
      // Google Search grounding cannot be combined with forced JSON output on every model, so search answers are parsed from text.
      ...(request.search ? { tools: [{ google_search: {} }] } : {}),
      generationConfig: { ...(request.search ? {} : { responseMimeType: 'application/json' }), temperature: 0.2, maxOutputTokens },
    }),
  });
  const body = (await r.json().catch(() => null)) as (GenerateResponse & GoogleErrorBody) | null;
  if (!r.ok) throw explainGoogleError(r.status, body, model);

  if (body?.promptFeedback?.blockReason)
    throw new GeminiError('blocked', 'Gemini declined to process this text. Remove unusual content from the job description and retry.', { reason: body.promptFeedback.blockReason });
  const candidate = body?.candidates?.[0];
  const finish = candidate?.finishReason;
  const textOut = (candidate?.content?.parts ?? [])
    .filter((p) => !p.thought)
    .map((p) => p.text ?? '')
    .join('');
  if (finish === 'MAX_TOKENS')
    throw new GeminiError('truncated', 'Gemini ran out of output space before finishing. Retry, or shorten the job description to its essentials.', { reason: finish });
  if (finish && !['STOP', 'FINISH_REASON_UNSPECIFIED'].includes(finish))
    throw new GeminiError('blocked', 'Gemini stopped before answering. Retry, or try another model.', { reason: finish });
  if (!textOut.trim()) throw new GeminiError('malformed', 'Gemini returned an empty answer. Retry.', { reason: finish });

  let parsed: unknown;
  try {
    parsed = parseJSONText(textOut);
  } catch {
    throw new GeminiError('malformed', 'Gemini’s answer was not in the expected format. Nothing was saved; retry.');
  }
  const result = schema.safeParse(parsed);
  if (!result.success) {
    const issue = result.error.issues[0];
    throw new GeminiError('malformed', 'Gemini’s answer was missing required parts. Nothing was saved; retry.', {
      reason: issue ? `${issue.path.join('.') || 'answer'}: ${issue.message}` : undefined,
    });
  }
  const sources = (candidate?.groundingMetadata?.groundingChunks ?? [])
    .map((c) => ({ uri: c.web?.uri ?? '', title: c.web?.title ?? '' }))
    .filter((c) => c.uri);
  return { data: result.data, tokens: body?.usageMetadata?.totalTokenCount ?? 0, sources };
}

/** Plain-English message plus technical detail, for any thrown value. */
export function describeError(e: unknown): { message: string; detail?: string } {
  if (e instanceof GeminiError) return { message: e.message, detail: e.detail || undefined };
  if (e instanceof Error) return { message: e.message };
  return { message: 'Something went wrong. Retry.' };
}
