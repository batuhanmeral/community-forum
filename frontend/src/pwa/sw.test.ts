import { readFileSync } from 'node:fs';
import path from 'node:path';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const SOURCE = readFileSync(path.resolve(import.meta.dirname, '../../public/sw.js'), 'utf8');
const ORIGIN = 'https://nexus.test';

type Handler = (event: Record<string, unknown>) => void;

function load(language = 'en-US') {
  const handlers: Record<string, Handler> = {};
  const store = new Map<string, Response>();
  const cache = {
    match: vi.fn(async (req: Request) => store.get(req.url)),
    put: vi.fn(async (req: Request, res: Response) => void store.set(req.url, res)),
  };
  const shown: Array<{ title: string; options: Record<string, unknown> }> = [];
  const windows: Array<{ url: string; focus: () => Promise<unknown>; navigate: (u: string) => Promise<unknown> }> = [];
  const self = {
    location: { origin: ORIGIN },
    navigator: { language },
    addEventListener: (type: string, fn: Handler) => void (handlers[type] = fn),
    skipWaiting: vi.fn(),
    caches: {
      open: vi.fn(async () => cache),
      keys: vi.fn(async () => ['nexus-static-v1', 'nexus-static-v0', 'someone-elses']),
      delete: vi.fn(async () => true),
    },
    clients: {
      claim: vi.fn(async () => undefined),
      matchAll: vi.fn(async () => windows),
      openWindow: vi.fn(async () => null),
    },
    registration: {
      showNotification: vi.fn(async (title: string, options: Record<string, unknown>) => {
        shown.push({ title, options });
      }),
    },
  };
  new Function('self', SOURCE)(self);
  return { handlers, self, cache, shown, windows };
}

function pushEvent(data: unknown, raw = false) {
  const waits: Promise<unknown>[] = [];
  return {
    event: {
      data: { json: () => (raw ? JSON.parse(data as string) : data), text: () => String(data) },
      waitUntil: (p: Promise<unknown>) => void waits.push(p),
    },
    done: () => Promise.all(waits),
  };
}

describe('service worker: push', () => {
  let sw: ReturnType<typeof load>;
  beforeEach(() => {
    sw = load();
  });

  it('shows a generic notification built from the type only', async () => {
    const { event, done } = pushEvent({ type: 'dm', url: '/messages', tag: 'dm' });
    sw.handlers.push(event);
    await done();
    expect(sw.shown).toHaveLength(1);
    expect(sw.shown[0].title).toBe('Nexus');
    expect(sw.shown[0].options).toMatchObject({ body: 'New message', tag: 'dm', data: { url: '/messages' } });
  });

  it('speaks Turkish for Turkish browsers', async () => {
    const tr = load('tr-TR');
    const { event, done } = pushEvent({ type: 'reply', url: '/inbox', tag: 'reply' });
    tr.handlers.push(event);
    await done();
    expect(tr.shown[0].options.body).toBe('Yeni yanıt');
  });

  it('never displays server-supplied text, so a forged payload cannot show its own message', async () => {
    const { event, done } = pushEvent({ type: 'dm', title: 'Your bank', body: 'Call 555', url: '/messages' });
    sw.handlers.push(event);
    await done();
    expect(JSON.stringify(sw.shown)).not.toContain('bank');
    expect(JSON.stringify(sw.shown)).not.toContain('555');
  });

  it('still shows something for unknown or unreadable payloads (a push must be visible)', async () => {
    for (const bad of [{ type: 'weird' }, '{not json', null]) {
      const local = load();
      const { event, done } = pushEvent(bad, typeof bad === 'string');
      local.handlers.push(event);
      await done();
      expect(local.shown).toHaveLength(1);
      expect(local.shown[0].options.data).toEqual({ url: '/' });
    }
  });

  it.each(['//evil.com', 'https://evil.com/x', 'javascript:alert(1)', '/\\evil.com', 'http:evil'])(
    'falls back to the root for the unsafe url %s',
    async (url) => {
      const { event, done } = pushEvent({ type: 'follow', url });
      sw.handlers.push(event);
      await done();
      expect(sw.shown[0].options.data).toEqual({ url: '/' });
    },
  );
});

describe('service worker: notification click', () => {
  it('focuses an open window and navigates it', async () => {
    const sw = load();
    const focus = vi.fn(async () => undefined);
    const navigate = vi.fn(async () => undefined);
    sw.windows.push({ url: `${ORIGIN}/c/py`, focus, navigate: navigate as never });
    const close = vi.fn();
    const waits: Promise<unknown>[] = [];
    sw.handlers.notificationclick({
      notification: { close, data: { url: '/messages' } },
      waitUntil: (p: Promise<unknown>) => waits.push(p),
    });
    await Promise.all(waits);
    expect(close).toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith(`${ORIGIN}/messages`);
    expect(focus).toHaveBeenCalled();
  });

  it('opens a new window on the own origin when none is open, even for a forged url', async () => {
    const sw = load();
    const waits: Promise<unknown>[] = [];
    sw.handlers.notificationclick({
      notification: { close: vi.fn(), data: { url: 'https://evil.com/steal' } },
      waitUntil: (p: Promise<unknown>) => waits.push(p),
    });
    await Promise.all(waits);
    expect(sw.self.clients.openWindow).toHaveBeenCalledWith(`${ORIGIN}/`);
  });
});

describe('service worker: click fallbacks', () => {
  it('opens a new window when navigate() rejects for an uncontrolled client', async () => {
    const sw = load();
    sw.windows.push({
      url: `${ORIGIN}/c/py`,
      focus: vi.fn(async () => undefined),
      navigate: vi.fn(async () => Promise.reject(new TypeError('uncontrolled'))) as never,
    });
    const waits: Promise<unknown>[] = [];
    sw.handlers.notificationclick({
      notification: { close: vi.fn(), data: { url: '/inbox' } },
      waitUntil: (p: Promise<unknown>) => waits.push(p),
    });
    await Promise.all(waits);
    expect(sw.self.clients.openWindow).toHaveBeenCalledWith(`${ORIGIN}/inbox`);
  });

  it('opens a new window when the client cannot navigate at all', async () => {
    const sw = load();
    sw.windows.push({ url: `${ORIGIN}/`, focus: vi.fn(async () => undefined) } as never);
    const waits: Promise<unknown>[] = [];
    sw.handlers.notificationclick({
      notification: { close: vi.fn(), data: { url: '/messages' } },
      waitUntil: (p: Promise<unknown>) => waits.push(p),
    });
    await Promise.all(waits);
    expect(sw.self.clients.openWindow).toHaveBeenCalledWith(`${ORIGIN}/messages`);
  });
});

describe('service worker: caching', () => {
  function fetchEvent(url: string, init: { method?: string; headers?: Record<string, string> } = {}) {
    let responded: Promise<Response> | undefined;
    const request = new Request(url, init);
    return {
      event: { request, respondWith: (p: Promise<Response>) => void (responded = p) },
      responded: () => responded,
    };
  }

  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('body', { status: 200 })));
  });

  it.each([
    `${ORIGIN}/api/v1/users/me/`,
    `${ORIGIN}/api/v1/auth/refresh/`,
    `${ORIGIN}/`,
    `${ORIGIN}/posts/1`,
    `${ORIGIN}/ws/`,
    `${ORIGIN}/media/avatars/x.png`,
    'https://cdn.example.com/assets/x.js',
  ])('never touches %s', (url) => {
    const sw = load();
    const { event, responded } = fetchEvent(url);
    sw.handlers.fetch(event);
    expect(responded()).toBeUndefined();
    expect(sw.cache.put).not.toHaveBeenCalled();
  });

  it('ignores non-GET requests and ones carrying credentials', () => {
    const sw = load();
    const post = fetchEvent(`${ORIGIN}/assets/a.js`, { method: 'POST' });
    sw.handlers.fetch(post.event);
    expect(post.responded()).toBeUndefined();
    const authed = fetchEvent(`${ORIGIN}/assets/a.js`, { headers: { Authorization: 'Bearer x' } });
    sw.handlers.fetch(authed.event);
    expect(authed.responded()).toBeUndefined();
  });

  it('serves hashed build assets cache-first', async () => {
    const sw = load();
    const first = fetchEvent(`${ORIGIN}/assets/index-abc.js`);
    sw.handlers.fetch(first.event);
    expect(await (await first.responded())!.text()).toBe('body');
    expect(sw.cache.put).toHaveBeenCalledTimes(1);
    const second = fetchEvent(`${ORIGIN}/assets/index-abc.js`);
    sw.handlers.fetch(second.event);
    await second.responded();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('does not cache failed responses', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('nope', { status: 500 })));
    const sw = load();
    const { event, responded } = fetchEvent(`${ORIGIN}/assets/missing.js`);
    sw.handlers.fetch(event);
    await responded();
    expect(sw.cache.put).not.toHaveBeenCalled();
  });

  it('drops old caches when it activates', async () => {
    const sw = load();
    const waits: Promise<unknown>[] = [];
    sw.handlers.activate({ waitUntil: (p: Promise<unknown>) => waits.push(p) });
    await Promise.all(waits);
    expect(sw.self.caches.delete).toHaveBeenCalledWith('nexus-static-v0');
    expect(sw.self.caches.delete).not.toHaveBeenCalledWith('nexus-static-v1');
    expect(sw.self.caches.delete).not.toHaveBeenCalledWith('someone-elses');
  });

  it('never caches the SPA index served for a missing asset or icon', async () => {
    const html = () =>
      new Response('<!doctype html>', { status: 200, headers: { 'Content-Type': 'text/html' } });
    for (const url of [`${ORIGIN}/assets/gone.js`, `${ORIGIN}/icons/gone.png`]) {
      vi.stubGlobal('fetch', vi.fn(async () => html()));
      const sw = load();
      const { event, responded } = fetchEvent(url);
      sw.handlers.fetch(event);
      await responded();
      expect(sw.cache.put).not.toHaveBeenCalled();
    }
  });

  it('caches icons only when they really are images', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('png', { status: 200, headers: { 'Content-Type': 'image/png' } })),
    );
    const sw = load();
    const { event, responded } = fetchEvent(`${ORIGIN}/icons/icon-192.png`);
    sw.handlers.fetch(event);
    await responded();
    expect(sw.cache.put).toHaveBeenCalledTimes(1);
  });
});
