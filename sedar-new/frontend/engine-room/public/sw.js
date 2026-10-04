"use strict";

const CACHE = "engine-room-v4";
const SCOPE_PATH = new URL("./", self.location).pathname;

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(["./index.html", "./logo.png"])).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

// The page asks the network first so a new release shows at once; offline it falls back to the cached copy.
// Hashed assets never change, so they are served from the cache.
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || !url.pathname.startsWith(SCOPE_PATH)) return;
  const isPage = event.request.mode === "navigate" || url.pathname.endsWith("/index.html");
  const fromNetwork = () => fetch(event.request, { cache: "no-cache" }).then((response) => {
    if (response.ok) {
      const copy = response.clone();
      caches.open(CACHE).then((cache) => cache.put(event.request, copy));
    }
    return response;
  });
  event.respondWith(
    isPage
      ? fromNetwork().catch(() => caches.match("./index.html"))
      : caches.match(event.request).then((cached) => cached || fromNetwork()),
  );
});
