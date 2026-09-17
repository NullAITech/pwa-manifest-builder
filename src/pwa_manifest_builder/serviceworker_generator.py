"""
Production-Ready Service Worker Synthesizer.

Generates high-performance, robust JavaScript Service Workers supporting:
  - CacheFirst, NetworkFirst, and StaleWhileRevalidate routing strategies
  - Pre-caching core assets with atomic versioning
  - Navigation preload and offline fallback routing
  - Background sync and push notification listeners
  - Instant cache updates and client claiming
100% Python Standard Library.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .models import ServiceWorkerConfig, CachingStrategy
from .compat import atomic_write_text, normalize_path


def _coerce_sw_config(config: Union[ServiceWorkerConfig, Dict[str, Any]]) -> ServiceWorkerConfig:
    if isinstance(config, ServiceWorkerConfig):
        return config
    if isinstance(config, dict):
        return ServiceWorkerConfig.from_dict(config)
    raise TypeError(f"Expected ServiceWorkerConfig or dict, got {type(config).__name__}")


def generate_service_worker(config: Union[ServiceWorkerConfig, Dict[str, Any]]) -> str:
    """
    Synthesizes a production-grade JavaScript Service Worker script from ServiceWorkerConfig or dict.
    """
    cfg = _coerce_sw_config(config)
    cache_id = f"{cfg.cache_name}-{cfg.cache_version}"
    precache_list = list(dict.fromkeys(cfg.precache_urls))  # deduplicate preserving order
    if cfg.offline_fallback_url and cfg.offline_fallback_url not in precache_list:
        precache_list.append(cfg.offline_fallback_url)

    precache_json = json.dumps(precache_list, indent=2)
    default_strategy = (
        config.caching_strategy.value
        if isinstance(config.caching_strategy, CachingStrategy)
        else str(config.caching_strategy)
    )

    offline_url_str = json.dumps(config.offline_fallback_url)
    enable_nav_preload_js = "true" if config.enable_navigation_preload else "false"

    # Runtime patterns serialized
    runtime_rules = config.runtime_cache_patterns or [
        {"pattern": r"\.(?:png|jpg|jpeg|svg|webp|gif|ico|woff|woff2|ttf|eot)$", "strategy": "CacheFirst"},
        {"pattern": r"\.(?:css|js)$", "strategy": "StaleWhileRevalidate"},
        {"pattern": r"\/api\/", "strategy": "NetworkFirst"},
    ]
    runtime_rules_json = json.dumps(runtime_rules, indent=2)

    sync_block = ""
    if config.enable_background_sync:
        sync_block = f"""
// ==========================================
// Background Sync
// ==========================================
self.addEventListener('sync', (event) => {{
  if (event.tag === '{config.background_sync_tag}') {{
    event.waitUntil(
      (async () => {{
        console.log('[SW] Processing background sync:', event.tag);
        // Custom background sync replay logic
        const clients = await self.clients.matchAll();
        clients.forEach((client) => {{
          client.postMessage({{ type: 'BACKGROUND_SYNC_TRIGGERED', tag: event.tag }});
        }});
      }})()
    );
  }}
}});
"""

    push_block = ""
    if config.enable_push_notifications:
        push_block = """
// ==========================================
// Web Push Notifications
// ==========================================
self.addEventListener('push', (event) => {
  let data = { title: 'New Notification', body: 'You have a new update!', icon: '/icons/icon-192x192.png' };
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: data.icon || '/icons/icon-192x192.png',
    badge: data.badge || '/icons/icon-96x96.png',
    data: data.data || { url: '/' },
    vibrate: [100, 50, 100],
    actions: data.actions || []
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'App Update', options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || '/';
  
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if (client.url === targetUrl && 'focus' in client) {
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl);
      }
    })
  );
});
"""

    sw_script = f"""/**
 * Service Worker Synthesized by pwa-manifest-builder
 * Cache Name: {cache_id}
 * Default Strategy: {default_strategy}
 */

'use strict';

const CACHE_NAME = '{cache_id}';
const OFFLINE_FALLBACK_URL = {offline_url_str};
const PRECACHE_ASSETS = {precache_json};
const RUNTIME_RULES = {runtime_rules_json};
const ENABLE_NAVIGATION_PRELOAD = {enable_nav_preload_js};

// ==========================================
// Lifecycle: Install (Precache)
// ==========================================
self.addEventListener('install', (event) => {{
  console.log('[SW] Installing Service Worker:', CACHE_NAME);
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {{
      console.log('[SW] Precaching static assets');
      return cache.addAll(PRECACHE_ASSETS);
    }}).then(() => {{
      return self.skipWaiting();
    }}).catch((error) => {{
      console.error('[SW] Precache failed:', error);
    }})
  );
}});

// ==========================================
// Lifecycle: Activate (Cleanup Stale Caches)
// ==========================================
self.addEventListener('activate', (event) => {{
  console.log('[SW] Activating Service Worker:', CACHE_NAME);
  event.waitUntil(
    (async () => {{
      if (ENABLE_NAVIGATION_PRELOAD && self.registration.navigationPreload) {{
        await self.registration.navigationPreload.enable();
      }}
      
      const cacheKeys = await caches.keys();
      await Promise.all(
        cacheKeys.map((key) => {{
          if (key !== CACHE_NAME) {{
            console.log('[SW] Deleting stale cache:', key);
            return caches.delete(key);
          }}
        }})
      );
      
      await self.clients.claim();
      console.log('[SW] Clients claimed');
    }})()
  );
}});

// ==========================================
// Strategy Handlers
// ==========================================

async function handleCacheFirst(request) {{
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {{
    return cachedResponse;
  }}
  try {{
    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {{
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }}
    return networkResponse;
  }} catch (error) {{
    console.warn('[SW] CacheFirst fetch failed:', request.url);
    if (request.mode === 'navigate' && OFFLINE_FALLBACK_URL) {{
      return caches.match(OFFLINE_FALLBACK_URL);
    }}
    throw error;
  }}
}}

async function handleNetworkFirst(request) {{
  try {{
    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.status === 200) {{
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }}
    return networkResponse;
  }} catch (error) {{
    console.warn('[SW] Network failed, falling back to cache:', request.url);
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {{
      return cachedResponse;
    }}
    if (request.mode === 'navigate' && OFFLINE_FALLBACK_URL) {{
      const fallback = await caches.match(OFFLINE_FALLBACK_URL);
      if (fallback) return fallback;
    }}
    throw error;
  }}
}}

async function handleStaleWhileRevalidate(request) {{
  const cachedResponse = await caches.match(request);
  const fetchPromise = fetch(request).then((networkResponse) => {{
    if (networkResponse && networkResponse.status === 200) {{
      caches.open(CACHE_NAME).then((cache) => {{
        cache.put(request, networkResponse.clone());
      }});
    }}
    return networkResponse;
  }}).catch((err) => {{
    console.warn('[SW] Background revalidation failed:', request.url);
  }});

  return cachedResponse || fetchPromise;
}}

async function handleNetworkOnly(request) {{
  return fetch(request);
}}

async function handleCacheOnly(request) {{
  const cached = await caches.match(request);
  if (cached) return cached;
  throw new Error('Asset not found in cache: ' + request.url);
}}

// ==========================================
// Fetch Event & Strategy Router
// ==========================================
self.addEventListener('fetch', (event) => {{
  const request = event.request;
  
  // Only handle HTTP/HTTPS GET requests
  if (request.method !== 'GET' || !request.url.startsWith('http')) {{
    return;
  }}

  // Handle navigation requests
  if (request.mode === 'navigate') {{
    event.respondWith(
      (async () => {{
        try {{
          // If navigation preload is active, use preloadResponse
          const preloadResponse = await event.preloadResponse;
          if (preloadResponse) {{
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, preloadResponse.clone());
            return preloadResponse;
          }}
          return await handleNetworkFirst(request);
        }} catch (error) {{
          if (OFFLINE_FALLBACK_URL) {{
            const offline = await caches.match(OFFLINE_FALLBACK_URL);
            if (offline) return offline;
          }}
          return caches.match('/') || new Response('Offline', {{ status: 503, statusText: 'Service Unavailable' }});
        }}
      }})()
    );
    return;
  }}

  // Match against runtime caching rules
  for (const rule of RUNTIME_RULES) {{
    const regex = new RegExp(rule.pattern, 'i');
    if (regex.test(request.url)) {{
      const strategy = rule.strategy || '{default_strategy}';
      if (strategy === 'CacheFirst') {{
        event.respondWith(handleCacheFirst(request));
        return;
      }} else if (strategy === 'StaleWhileRevalidate') {{
        event.respondWith(handleStaleWhileRevalidate(request));
        return;
      }} else if (strategy === 'NetworkOnly') {{
        event.respondWith(handleNetworkOnly(request));
        return;
      }} else if (strategy === 'CacheOnly') {{
        event.respondWith(handleCacheOnly(request));
        return;
      }} else {{
        event.respondWith(handleNetworkFirst(request));
        return;
      }}
    }}
  }}

  // Default fallback strategy
  if ('{default_strategy}' === 'CacheFirst') {{
    event.respondWith(handleCacheFirst(request));
  }} else if ('{default_strategy}' === 'StaleWhileRevalidate') {{
    event.respondWith(handleStaleWhileRevalidate(request));
  }} else {{
    event.respondWith(handleNetworkFirst(request));
  }}
}});

// ==========================================
// Client Communication & Maintenance
// ==========================================
self.addEventListener('message', (event) => {{
  if (!event.data) return;
  
  if (event.data.type === 'SKIP_WAITING') {{
    console.log('[SW] Received SKIP_WAITING signal');
    self.skipWaiting();
  }}
  
  if (event.data.type === 'GET_VERSION') {{
    event.ports[0].postMessage({{ version: '{config.cache_version}', cacheName: CACHE_NAME }});
  }}
  
  if (event.data.type === 'CLEAR_CACHE') {{
    caches.delete(CACHE_NAME).then(() => {{
      console.log('[SW] Cache manually cleared:', CACHE_NAME);
      if (event.ports && event.ports[0]) {{
        event.ports[0].postMessage({{ success: true }});
      }}
    }});
  }}
}});
{sync_block}{push_block}"""

    return sw_script.strip() + "\n"


def generate_sw_registration_script(
    sw_path: str = "/sw.js",
    scope: str = "/",
    auto_reload_on_update: bool = False
) -> str:
    """
    Generates client-side JavaScript snippet to register the service worker
    with update checks, controllerchange handling, and lifecycle events.
    """
    reload_code = ""
    if auto_reload_on_update:
        reload_code = """
      let refreshing = false;
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (!refreshing) {
          refreshing = true;
          window.location.reload();
        }
      });
"""
    return f"""<script>
  if ('serviceWorker' in navigator) {{
    window.addEventListener('load', () => {{
      navigator.serviceWorker.register('{sw_path}', {{ scope: '{scope}' }})
        .then((registration) => {{
          console.log('[PWA] Service Worker registered successfully:', registration.scope);
          
          registration.onupdatefound = () => {{
            const installingWorker = registration.installing;
            if (installingWorker == null) return;
            installingWorker.onstatechange = () => {{
              if (installingWorker.state === 'installed') {{
                if (navigator.serviceWorker.controller) {{
                  console.log('[PWA] New content available; please refresh.');
                  window.dispatchEvent(new CustomEvent('pwa-update-available', {{ detail: registration }}));
                }} else {{
                  console.log('[PWA] Content cached for offline use.');
                  window.dispatchEvent(new CustomEvent('pwa-installed'));
                }}
              }}
            }};
          }};
        }})
        .catch((error) => {{
          console.error('[PWA] Service Worker registration failed:', error);
        }});{reload_code}
    }});
  }}
</script>"""


def save_service_worker(
    config: ServiceWorkerConfig,
    output_path: Union[str, Path]
) -> Path:
    """
    Synthesizes and writes the service worker script atomically to disk.
    """
    js_code = generate_service_worker(config)
    return atomic_write_text(output_path, js_code, encoding="utf-8")
