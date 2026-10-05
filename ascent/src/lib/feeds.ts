import { htmlToText } from './core';

export type Provider = 'greenhouse' | 'lever' | 'lever-eu';
export type FeedJob = { company: string; title: string; location: string; url: string; description: string; source: string; updated?: string };

export const providers: { id: Provider; label: string; hint: string }[] = [
  { id: 'greenhouse', label: 'Greenhouse', hint: 'boards.greenhouse.io/' },
  { id: 'lever', label: 'Lever', hint: 'jobs.lever.co/' },
  { id: 'lever-eu', label: 'Lever (Europe)', hint: 'jobs.eu.lever.co/' },
];

/** Accepts a bare board name or a pasted careers URL and returns the board name. */
export function boardFromInput(input: string) {
  const s = input.trim();
  const m = s.match(/(?:greenhouse\.io|lever\.co)\/(?:embed\/job_board\?for=)?([A-Za-z0-9_-]+)/);
  return m ? m[1] : s;
}

const titleCase = (slug: string) => slug.replace(/[-_]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

export async function readFeed(provider: Provider, rawBoard: string): Promise<{ jobs: FeedJob[]; company: string; truncated: boolean }> {
  const board = boardFromInput(rawBoard);
  if (!/^[A-Za-z0-9_-]{1,100}$/.test(board)) throw new Error('Enter the employer’s board name, for example the word after boards.greenhouse.io/ in their careers link.');

  const url =
    provider === 'greenhouse'
      ? `https://boards-api.greenhouse.io/v1/boards/${board}/jobs?content=true`
      : `https://${provider === 'lever-eu' ? 'api.eu.lever.co' : 'api.lever.co'}/v0/postings/${board}?mode=json`;

  let r: Response;
  try {
    r = await fetch(url, { signal: AbortSignal.timeout(20_000) });
  } catch {
    throw new Error('The employer feed could not be reached from your browser. Check your connection, or paste the vacancy manually with Add vacancy.');
  }
  if (r.status === 404) throw new Error(`No public ${provider === 'greenhouse' ? 'Greenhouse' : 'Lever'} board called “${board}”. Check the name in the employer’s careers link.`);
  if (!r.ok) throw new Error(`The employer feed answered with an error (HTTP ${r.status}). Paste the vacancy manually instead.`);
  const data = (await r.json()) as unknown;

  let company = titleCase(board);
  if (provider === 'greenhouse') {
    try {
      const meta = await fetch(`https://boards-api.greenhouse.io/v1/boards/${board}`, { signal: AbortSignal.timeout(10_000) });
      if (meta.ok) company = ((await meta.json()) as { name?: string }).name || company;
    } catch {
      /* the board name is a fine fallback */
    }
  }

  const list = (provider === 'greenhouse' ? (data as { jobs?: unknown[] }).jobs : data) as Record<string, any>[] | undefined;
  if (!Array.isArray(list)) throw new Error('The employer feed returned something unexpected. Paste the vacancy manually instead.');

  const jobs = list.slice(0, 500).map((j): FeedJob => {
    if (provider === 'greenhouse')
      return { company, title: String(j.title ?? ''), location: String(j.location?.name ?? ''), url: String(j.absolute_url ?? ''), description: htmlToText(String(j.content ?? '')), source: 'Greenhouse', updated: j.updated_at ?? undefined };
    const lists = Array.isArray(j.lists) ? j.lists.map((l: Record<string, string>) => `${l.text ?? ''}\n${htmlToText(l.content ?? '')}`).join('\n\n') : '';
    return {
      company,
      title: String(j.text ?? ''),
      location: String(j.categories?.location ?? ''),
      url: String(j.hostedUrl ?? ''),
      description: [j.descriptionPlain ?? htmlToText(String(j.description ?? '')), lists, j.additionalPlain ?? htmlToText(String(j.additional ?? ''))].filter(Boolean).join('\n\n').trim(),
      source: 'Lever',
    };
  });
  return { jobs, company, truncated: list.length > 500 };
}
