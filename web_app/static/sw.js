// ===================== SMARTWEAR SW v2 =====================

const CACHE_NAME = "smartwear-v2";

const STATIC_ASSETS = [
  "/",
  "/static/css/style.css",
  "/static/manifest.json"
];

// API routes (NEVER cache these)
const NETWORK_ONLY = [
  "/process_remote_frame",
  "/register_remote",
  "/admin/",
  "/api/"
];


// ===================== INSTALL =====================
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        return cache.addAll(STATIC_ASSETS).catch((err) => {
          console.warn("Cache addAll failed:", err);
        });
      })
  );

  self.skipWaiting();
});


// ===================== ACTIVATE =====================
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) return caches.delete(key);
        })
      );
    })
  );

  self.clients.claim();
});


// ===================== FETCH STRATEGY =====================
self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Only same-origin handling
  if (url.origin !== location.origin) {
    event.respondWith(fetch(request));
    return;
  }

  // Force network for sensitive routes
  if (isNetworkOnly(url.pathname)) {
    event.respondWith(networkOnly(request));
    return;
  }

  // Navigation fallback (IMPORTANT for PWA)
  if (request.mode === "navigate") {
    event.respondWith(networkFirstWithFallback(request));
    return;
  }

  // Static assets → cache-first
  event.respondWith(cacheFirst(request));
});


// ===================== STRATEGIES =====================

// Cache-first (CSS, images, etc.)
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  const response = await fetch(request);

  if (request.method === "GET" && response && response.status === 200) {
    const cache = await caches.open(CACHE_NAME);
    cache.put(request, response.clone());
  }

  return response;
}

// Network-first with fallback (pages)
async function networkFirstWithFallback(request) {
  try {
    const response = await fetch(request);
    return response;
  } catch (err) {
    const cached = await caches.match("/");
    return cached || new Response("Offline", { status: 503 });
  }
}

// API always network
async function networkOnly(request) {
  try {
    return await fetch(request);
  } catch (err) {
    return new Response(
      JSON.stringify({ error: "offline" }),
      { headers: { "Content-Type": "application/json" }, status: 503 }
    );
  }
}


// ===================== HELPERS =====================
function isNetworkOnly(path) {
  return NETWORK_ONLY.some((route) =>
    path.startsWith(route)
  );
}
