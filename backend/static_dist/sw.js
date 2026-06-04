const CACHE_NAME = 'sku-vision-mvp-v2'
const APP_SHELL = ['/', '/index.html', '/manifest.webmanifest', '/icon.svg']

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
    ),
  )
  self.clients.claim()
})

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return
  const url = new URL(event.request.url)
  const isSameOrigin = url.origin === self.location.origin

  if (!isSameOrigin) return

  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const copy = response.clone()
          caches.open(CACHE_NAME).then((cache) => cache.put('/index.html', copy)).catch(() => null)
          return response
        })
        .catch(async () => {
          const cached = await caches.match('/index.html')
          if (cached) return cached
          return caches.match('/')
        }),
    )
    return
  }

  const shouldCache =
    url.pathname.startsWith('/assets/') ||
    url.pathname === '/manifest.webmanifest' ||
    url.pathname === '/icon.svg' ||
    url.pathname === '/sw.js'

  if (!shouldCache) return

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached

      return fetch(event.request).then((response) => {
        const copy = response.clone()
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy)).catch(() => null)
        return response
      })
    }),
  )
})
