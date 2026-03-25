// SPDX-FileCopyrightText: 2025 PeARS Project, <community@pearsproject.org>,
//
// SPDX-License-Identifier: AGPL-3.0-only

const CACHE_VERSION = 'pears-v1';
const STATIC_ASSETS = [
  '/static/vendor/oat/oat.min.css',
  '/static/vendor/oat/oat.min.js',
  '/static/css/pears-theme.css',
  '/static/js/theme-toggle.js',
  '/static/js/loading.js',
  '/static/fonts/source-sans-3-latin-regular.woff2',
  '/static/fonts/source-sans-3-latin-italic.woff2',
  '/static/fonts/source-sans-3-latin-ext-regular.woff2',
  '/static/fonts/source-sans-3-latin-ext-italic.woff2',
  '/static/fonts/source-serif-4-latin-regular.woff2',
  '/static/fonts/source-serif-4-latin-ext-regular.woff2',
  '/static/fonts/source-code-pro-latin-regular.woff2',
  '/static/fonts/source-code-pro-latin-ext-regular.woff2',
  '/static/images/pears-icon.svg',
  '/static/images/logo.svg',
  '/static/images/happy.svg',
  '/static/images/sad.svg',
  '/static/favicon.png',
  '/static/search-outline.svg',
  '/static/sunny-outline.svg',
  '/static/moon-outline.svg'
];

// Install: pre-cache static assets
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_VERSION).then(function(cache) {
      return cache.addAll(STATIC_ASSETS);
    })
  );
});

// Activate: clean up old caches
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(key) {
          return key !== CACHE_VERSION;
        }).map(function(key) {
          return caches.delete(key);
        })
      );
    })
  );
});

// Fetch: cache-first for static assets, network-first for everything else
self.addEventListener('fetch', function(event) {
  var url = new URL(event.request.url);

  // Static assets: serve from cache, fall back to network
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then(function(cached) {
        return cached || fetch(event.request).then(function(response) {
          return caches.open(CACHE_VERSION).then(function(cache) {
            cache.put(event.request, response.clone());
            return response;
          });
        });
      })
    );
    return;
  }

  // HTML pages: network-first, fall back to cache
  if (event.request.headers.get('Accept') &&
      event.request.headers.get('Accept').includes('text/html')) {
    event.respondWith(
      fetch(event.request).then(function(response) {
        return caches.open(CACHE_VERSION).then(function(cache) {
          cache.put(event.request, response.clone());
          return response;
        });
      }).catch(function() {
        return caches.match(event.request);
      })
    );
    return;
  }
});
