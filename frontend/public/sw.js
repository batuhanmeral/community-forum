/* Nexus service worker: Web Push and a minimal static cache. No workbox.
 *
 * Deliberately small:
 *  - It only ever shows text it owns (a fixed phrase per notification type). The server payload
 *    is just {type, url, tag}; nothing it sends is displayed as-is.
 *  - It caches nothing but hashed build assets and icons. API, auth, pages, media and sockets are
 *    never intercepted, so no private response can end up in a cache.
 */
const CACHE_PREFIX = 'nexus-static-';
const CACHE = CACHE_PREFIX + 'v1';
const CACHEABLE_PREFIXES = ['/assets/', '/icons/'];

const TEXT = {
  en: {
    dm: 'New message',
    reply: 'New reply',
    comment: 'New reply',
    mention: 'You were mentioned',
    follow: 'New follower',
    modmail: 'New modmail message',
    removal: 'A moderator removed your content',
    mod_action: 'A moderator acted on your content',
    other: 'New notification',
  },
  tr: {
    dm: 'Yeni mesaj',
    reply: 'Yeni yanıt',
    comment: 'Yeni yanıt',
    mention: 'Senden bahsedildi',
    follow: 'Yeni takipçi',
    modmail: 'Yeni modmail mesajı',
    removal: 'Bir moderatör içeriğini kaldırdı',
    mod_action: 'Bir moderatör içeriğin hakkında işlem yaptı',
    other: 'Yeni bildirim',
  },
};

function textFor(type) {
  const language = String((self.navigator && self.navigator.language) || 'en').toLowerCase();
  const table = language.startsWith('tr') ? TEXT.tr : TEXT.en;
  return Object.prototype.hasOwnProperty.call(table, type) ? table[type] : table.other;
}

// The SPA fallback answers unknown paths with index.html (status 200): never store that as an
// asset or icon. Icons must really be images.
function cacheable(url, response) {
  if (!response.ok || response.type === 'opaque') return false;
  const type = (response.headers && response.headers.get('content-type')) || '';
  if (type.includes('text/html')) return false;
  return !url.pathname.startsWith('/icons/') || type.startsWith('image/');
}

// Only a same-origin absolute path may be opened; anything else becomes the home page.
function safePath(url) {
  if (typeof url !== 'string' || !url.startsWith('/') || url.startsWith('//') || url.includes('\\')) {
    return '/';
  }
  return url;
}

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    self.caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE).map((key) => self.caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('push', (event) => {
  let payload = {};
  try {
    payload = (event.data && event.data.json()) || {};
  } catch (_error) {
    payload = {};
  }
  const type = typeof payload.type === 'string' ? payload.type : 'other';
  const tag = typeof payload.tag === 'string' ? payload.tag.slice(0, 32) : type;
  event.waitUntil(
    self.registration.showNotification('Nexus', {
      body: textFor(type),
      tag,
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
      data: { url: safePath(payload.url) },
    }),
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = new URL(safePath(event.notification.data && event.notification.data.url), self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
      const existing = windows.find((client) => client.url.startsWith(self.location.origin));
      // navigate() exists only on controlled clients and rejects otherwise: fall back to a new window.
      if (existing && typeof existing.navigate === 'function') {
        return existing
          .navigate(target)
          .then(() => existing.focus())
          .catch(() => self.clients.openWindow(target));
      }
      return self.clients.openWindow(target);
    }),
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET' || request.headers.has('authorization')) return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (!CACHEABLE_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) return;
  event.respondWith(
    self.caches.open(CACHE).then((cache) =>
      cache.match(request).then(
        (hit) =>
          hit ||
          fetch(request).then((response) => {
            if (cacheable(url, response)) cache.put(request, response.clone());
            return response;
          }),
      ),
    ),
  );
});
