/* Cropsy service worker: lets the app open and show saved data with poor or no network.
   - pages: network first, saved copy when offline
   - app files, images, data files: saved copy first
   - safe GET calls to the API (parcels, layers, offices, knowledge): network first, saved copy when offline
   Questions to the advisor (POST) are never saved or replayed. */
const V = "cropsy-v1";
const STATIC = /\/(assets|images|data)\//;
const API_OK = /\/api\/(parcels|layers|offices|knowledge|village-brief|alerts|priority|satellite|history|field-report)/;

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== V).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

async function put(req, res) {
  if (res && res.ok) (await caches.open(V)).put(req, res.clone());
  return res;
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const same = url.origin === self.location.origin;
  if (req.mode === "navigate") {
    e.respondWith(fetch(req).then((r) => put(req, r)).catch(() => caches.match(req).then((m) => m || caches.match("/"))));
    return;
  }
  if (same && STATIC.test(url.pathname)) {
    e.respondWith(caches.match(req).then((m) => m || fetch(req).then((r) => put(req, r))));
    return;
  }
  if (API_OK.test(url.pathname)) {
    e.respondWith(fetch(req).then((r) => put(req, r)).catch(() => caches.match(req)));
  }
});
