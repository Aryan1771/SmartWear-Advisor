// sw.js — SmartWear Advisor Service Worker
// Strategy: Network-first for API/dynamic routes, Cache-first for static assets.

const CACHE_NAME    = "smartwear-v1";
const STATIC_ASSETS = [
  "/",
  "/static/css/style.css",
  "/static/manifest.json",
];

// API routes that must never be served from cache
const NETWORK_ONLY = [
  "/process_remote_frame",
  "/register_remote",
  "/detail/",
  "/admin/",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((c) => c.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // Always go to network for API/dynamic routes
  if (NETWORK_ONLY.some((p) => url.pathname.startsWith(p))) {
    e.respondWith(fetch(e.request).catch(() =>
      new Response(JSON.stringify({ error: "offline" }), {
        headers: { "Content-Type": "application/json" },
      })
    ));
    return;
  }

  // Cache-first for static assets
  e.respondWith(
    caches.match(e.request).then((cached) => {
      if (cached) return cached;
      return fetch(e.request).then((resp) => {
        if (resp && resp.status === 200 && e.request.method === "GET") {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then((c) => c.put(e.request, clone));
        }
        return resp;
      });
    })
  );
});
