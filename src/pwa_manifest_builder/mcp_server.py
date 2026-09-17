"""Model Context Protocol (MCP) Server for PWA Manifest Builder.

Implements JSON-RPC 2.0 protocol over stdio for tool calling, resource inspection,
and prompting per the MCP specification (2024-11-05).
100% Python Standard Library. Zero external dependencies.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from .models import (
    PWAManifestConfig,
    ServiceWorkerConfig,
    DisplayMode,
    Orientation,
    CachingStrategy,
    IconSpec,
    ShortcutSpec,
    PWAValidationReport,
)
from .manifest_generator import (
    generate_manifest_dict,
    generate_manifest_json,
    generate_html_meta_tags,
    build_manifest,
)
from .serviceworker_generator import (
    generate_service_worker,
    generate_sw_registration_script,
)
from .icon_forge import (
    generate_icon_svg,
    STANDARD_ICON_SIZES,
)
from .linter import (
    validate_manifest,
    is_valid_color,
)
from .catalog import (
    list_templates,
    get_template,
    generate_from_template,
    TEMPLATES,
)
from .compat import get_platform_info


# ============================================================================
# Protocol Constants & Registry
# ============================================================================

MCP_PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "pwa-manifest-builder"
SERVER_VERSION = "0.1.0"

# Standard JSON-RPC 2.0 Error Codes
ERR_PARSE_ERROR = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602
ERR_INTERNAL = -32603


# ============================================================================
# Registered Tools Specifications
# ============================================================================

REGISTERED_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "pwa_generate_manifest",
        "description": "Generate W3C-compliant manifest.webmanifest JSON and HTML meta tags from parameters or preset templates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Full name of the web application (e.g. 'Starlight Commerce')",
                },
                "short_name": {
                    "type": "string",
                    "description": "Short name displayed on mobile home screen (max 12 characters recommended)",
                },
                "description": {
                    "type": "string",
                    "description": "General description of the application purpose",
                },
                "start_url": {
                    "type": "string",
                    "default": "/",
                    "description": "URL to launch when app starts",
                },
                "scope": {
                    "type": "string",
                    "default": "/",
                    "description": "Navigation scope of the PWA context",
                },
                "display": {
                    "type": "string",
                    "enum": ["standalone", "fullscreen", "minimal-ui", "browser"],
                    "default": "standalone",
                    "description": "Preferred display mode for the application window",
                },
                "orientation": {
                    "type": "string",
                    "enum": ["any", "natural", "landscape", "portrait", "portrait-primary", "landscape-primary"],
                    "default": "any",
                    "description": "Default screen orientation lock",
                },
                "theme_color": {
                    "type": "string",
                    "default": "#2563eb",
                    "description": "Hex theme color for browser toolbar and status bar",
                },
                "background_color": {
                    "type": "string",
                    "default": "#ffffff",
                    "description": "Hex background color for splash screen on startup",
                },
                "id": {
                    "type": "string",
                    "description": "Unique app identity string (e.g. '/?source=pwa')",
                },
                "lang": {
                    "type": "string",
                    "default": "en",
                    "description": "Primary BCP 47 language code",
                },
                "dir": {
                    "type": "string",
                    "enum": ["auto", "ltr", "rtl"],
                    "default": "auto",
                    "description": "Text directionality",
                },
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of standard app categories (e.g. ['utilities', 'shopping'])",
                },
                "shortcuts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "url": {"type": "string"},
                            "description": {"type": "string"},
                            "short_name": {"type": "string"},
                        },
                        "required": ["name", "url"],
                    },
                    "description": "Quick action shortcuts on mobile app launcher",
                },
                "icons": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "src": {"type": "string"},
                            "sizes": {"type": "string"},
                            "type": {"type": "string"},
                            "purpose": {"type": "string"},
                        },
                        "required": ["src", "sizes"],
                    },
                    "description": "List of app icon specifications",
                },
                "template": {
                    "type": "string",
                    "description": "Optional preset template name (e.g. 'ecommerce', 'game', 'dashboard', 'productivity', 'offline-doc', 'social', 'media', 'crypto-tracker', 'ai-assistant')",
                },
                "include_meta_tags": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to also output corresponding HTML <head> meta tags",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "pwa_generate_serviceworker",
        "description": "Generate production-ready offline ServiceWorker JavaScript code with caching strategies (cache_first, network_first, stale_while_revalidate), precaching assets, and offline fallback.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "strategy": {
                    "type": "string",
                    "enum": ["cache_first", "network_first", "stale_while_revalidate", "network_only", "cache_only", "CacheFirst", "NetworkFirst", "StaleWhileRevalidate"],
                    "default": "stale_while_revalidate",
                    "description": "Primary caching strategy for runtime requests",
                },
                "cache_name": {
                    "type": "string",
                    "default": "pwa-cache",
                    "description": "Cache storage namespace identifier",
                },
                "cache_version": {
                    "type": "string",
                    "default": "v1",
                    "description": "Cache version tag for cache busting",
                },
                "precache_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["/", "/index.html", "/offline.html"],
                    "description": "Static assets to precache during ServiceWorker installation",
                },
                "offline_fallback_url": {
                    "type": "string",
                    "default": "/offline.html",
                    "description": "HTML file to serve when network fails and asset is not in cache",
                },
                "enable_navigation_preload": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable Navigation Preload API to eliminate SW boot delay",
                },
                "enable_background_sync": {
                    "type": "boolean",
                    "default": False,
                    "description": "Enable Background Sync listener for offline queue replay",
                },
                "enable_push_notifications": {
                    "type": "boolean",
                    "default": False,
                    "description": "Enable Web Push notification event listeners",
                },
                "include_registration_snippet": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include client-side registration snippet (navigator.serviceWorker.register)",
                },
            },
        },
    },
    {
        "name": "pwa_generate_icons",
        "description": "Generate scalable SVG app icons, Apple touch icons, and Android adaptive maskable icons with custom colors, monogram glyphs, and safe-zone dimensions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "default": "App",
                    "description": "Application name used to derive 1-2 letter monogram",
                },
                "letter": {
                    "type": "string",
                    "description": "Explicit 1-2 character monogram glyph to render in icon center",
                },
                "bg_color": {
                    "type": "string",
                    "default": "#2563eb",
                    "description": "Hex background color or primary brand color",
                },
                "fg_color": {
                    "type": "string",
                    "default": "#ffffff",
                    "description": "Hex foreground/text glyph color",
                },
                "shape": {
                    "type": "string",
                    "enum": ["rounded", "circle", "square", "squircle", "hex"],
                    "default": "rounded",
                    "description": "Corner shape of the icon container",
                },
                "icon_name": {
                    "type": "string",
                    "description": "Optional vector icon glyph preset (sparkles, bolt, code, rocket, cube, store, chart, music, terminal, chat, check, heart, book, game, shield, globe, star)",
                },
                "sizes": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "default": [192, 512],
                    "description": "List of pixel dimensions to generate",
                },
                "maskable": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to apply Android maskable safe-zone padding (80% diameter safe area)",
                },
            },
        },
    },
    {
        "name": "pwa_audit_manifest",
        "description": "Audit manifest JSON or config against W3C standards and Google Lighthouse PWA installability criteria, returning readiness score and actionable fixes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "manifest": {
                    "type": "object",
                    "description": "Manifest dictionary or JSON object to evaluate",
                },
                "check_installability": {
                    "type": "boolean",
                    "default": True,
                    "description": "Verify Chrome/Edge/Safari desktop & mobile installation criteria",
                },
                "check_lighthouse_pwa": {
                    "type": "boolean",
                    "default": True,
                    "description": "Calculate Google Lighthouse PWA score (0-100)",
                },
            },
            "required": ["manifest"],
        },
    },
    {
        "name": "pwa_html_meta_tags",
        "description": "Generate complete HTML <head> meta tags for PWA manifest linking, Apple iOS mobile web app support, and Windows live tiles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "manifest_path": {
                    "type": "string",
                    "default": "/manifest.webmanifest",
                    "description": "Path or href URL to web app manifest",
                },
                "theme_color": {
                    "type": "string",
                    "default": "#2563eb",
                    "description": "Theme color hex code",
                },
                "name": {
                    "type": "string",
                    "default": "Progressive Web App",
                    "description": "Application title",
                },
                "short_name": {
                    "type": "string",
                    "description": "Apple mobile web app title",
                },
                "description": {
                    "type": "string",
                    "description": "Application description",
                },
            },
        },
    },
    {
        "name": "pwa_list_templates",
        "description": "List built-in PWA app templates with tailored configurations for e-commerce, games, dashboards, productivity, docs, social, media, and crypto.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category filter (e.g. 'commerce', 'gaming', 'productivity', 'finance', 'education', 'social', 'entertainment')",
                },
            },
        },
    },
    {
        "name": "pwa_diagnostics",
        "description": "Run multi-OS environment diagnostics check, inspecting platform capabilities, Python environment, terminal color support, and PWA builder engine state.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "verbose": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include extended system and path details",
                },
            },
        },
    },
    {
        "name": "pwa_simulate_shortcuts",
        "description": "Simulate and validate PWA App Shortcuts, verifying icon assets and generating client-side action routing / deep-link dispatcher code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "shortcuts": {
                    "type": "array",
                    "description": "Array of shortcut specifications ({name, url, short_name, icons})",
                },
                "template": {
                    "type": "string",
                    "description": "Optional preset template ID to load shortcuts from",
                },
            },
        },
    },
    {
        "name": "pwa_validate_protocol_handlers",
        "description": "Validate URL Protocol Handlers against W3C specification and synthesize client-side navigator.registerProtocolHandler code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "protocol_handlers": {
                    "type": "array",
                    "description": "Array of protocol handlers ({protocol, url, title})",
                },
                "scope": {
                    "type": "string",
                    "default": "/",
                    "description": "Manifest scope for URL containment checks",
                },
            },
        },
    },
    {
        "name": "pwa_validate_share_target",
        "description": "Validate W3C Web Share Target API configuration (action, method, enctype, params) and synthesize client or ServiceWorker receiver code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "share_target": {
                    "type": "object",
                    "description": "Share target specification ({action, method, enctype, params})",
                },
                "manifest": {
                    "type": "object",
                    "description": "Full manifest dictionary containing 'share_target'",
                },
                "scope": {
                    "type": "string",
                    "default": "/",
                    "description": "Manifest scope boundary",
                },
            },
        },
    },
    {
        "name": "pwa_validate_file_handlers",
        "description": "Validate W3C File Handling API entries (action, accept MIME/exts, launch_type) and generate launchQueue.setConsumer() script.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_handlers": {
                    "type": "array",
                    "description": "Array of file handler objects ({action, accept, name, launch_type})",
                },
                "manifest": {
                    "type": "object",
                    "description": "Full manifest dictionary containing 'file_handlers'",
                },
                "scope": {
                    "type": "string",
                    "default": "/",
                    "description": "Manifest scope boundary",
                },
            },
        },
    },
    {
        "name": "pwa_simulate_share",
        "description": "Simulate an incoming Web Share action against a share_target definition with title, text, url, and files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "share_target": {
                    "type": "object",
                    "description": "Share target specification ({action, method, enctype, params})",
                },
                "title": {
                    "type": "string",
                    "description": "Title payload to share",
                },
                "text": {
                    "type": "string",
                    "description": "Text body payload to share",
                },
                "url": {
                    "type": "string",
                    "description": "URL payload to share",
                },
                "files": {
                    "type": "array",
                    "description": "Array of mock files ({name, type, size}) to share",
                },
            },
        },
    },
    {
        "name": "pwa_simulate_file_open",
        "description": "Simulate an OS file open event dispatched to the PWA via the File Handling API.",
        "inputSchema": {
            "type": "object",
            "required": ["file_name"],
            "properties": {
                "file_handlers": {
                    "type": "array",
                    "description": "Array of file handlers or manifest",
                },
                "file_name": {
                    "type": "string",
                    "description": "File name to open (e.g. document.txt, image.png)",
                },
                "mime_type": {
                    "type": "string",
                    "description": "Optional MIME type override",
                },
            },
        },
    },
]


# ============================================================================
# Registered Resources Specifications & Content
# ============================================================================

REGISTERED_RESOURCES: List[Dict[str, Any]] = [
    {
        "uri": "pwa://templates",
        "name": "PWA App Templates Catalog",
        "description": "Catalog of built-in PWA templates (e-commerce, game, productivity, dashboard, offline-doc, blog, media, social, crypto-tracker, ai-assistant).",
        "mimeType": "application/json",
    },
    {
        "uri": "pwa://specs/w3c-manifest",
        "name": "W3C Web App Manifest Specification Guide",
        "description": "Reference guide for W3C web app manifest specification parameters, standard keys, and installability criteria.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "pwa://specs/serviceworker-strategies",
        "name": "ServiceWorker Offline Caching Strategies Guide",
        "description": "Reference guide for offline caching strategies (cache-first, network-first, stale-while-revalidate), precaching, and eviction policies.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "pwa://specs/share-and-file-handling",
        "name": "Web Share Target & File Handling APIs Specification Guide",
        "description": "Reference guide for W3C Web Share Target API (GET/POST, multipart payloads) and File Handling API (launchQueue consumers, MIME mappings).",
        "mimeType": "text/markdown",
    },
]

RESOURCE_CONTENT_MAP: Dict[str, Tuple[str, str]] = {
    "pwa://templates": (
        "application/json",
        json.dumps(list_templates(), indent=2),
    ),
    "pwa://specs/w3c-manifest": (
        "text/markdown",
        """# W3C Web App Manifest Specification Reference

The Web App Manifest is a JSON document that provides metadata about an application to the browser, enabling Progressive Web App (PWA) installation to mobile home screens and desktop application menus.

## Mandatory Installability Keys (Chrome, Edge, Safari, Firefox)
1. **`name`** (string): Full human-readable name of the application.
2. **`short_name`** (string): Short identifier displayed where space is constrained (e.g. mobile home screen launcher). Max 12 characters recommended.
3. **`start_url`** (string): The start URL that loads when the application is launched. Must be within `scope`.
4. **`display`** (string): Window rendering mode:
   - `standalone`: Looks and feels like a native app (no browser navigation UI).
   - `fullscreen`: Uses entire display with no browser chrome or OS status bars (ideal for games).
   - `minimal-ui`: Provides minimal navigation controls (back, forward, reload).
   - `browser`: Standard browser tab.
5. **`icons`** (array of IconSpec):
   - At least one `192x192` PNG/SVG icon.
   - At least one `512x512` PNG/SVG icon.
   - An adaptive `maskable` icon (`purpose: "maskable"`) with 10% safe zone padding for Android adaptive icon rendering.

## Important Visual & Localization Keys
- **`theme_color`** (hex string): Sets the color of the OS titlebar and browser toolbar.
- **`background_color`** (hex string): Color for the instant splash screen displayed while application assets load.
- **`scope`** (string): Defines URL navigation boundaries for the PWA context.
- **`id`** (string): Stable application identity across URL renames.
- **`orientation`** (string): Screen orientation lock (`any`, `natural`, `landscape`, `portrait`).
- **`lang`** (string): Primary BCP 47 language code (e.g. `en-US`, `es`).
- **`dir`** (string): Text direction (`ltr`, `rtl`, or `auto`).
- **`categories`** (array of string): Standard web app store classification tags.
- **`shortcuts`** (array of ShortcutSpec): App launcher quick actions on long-press or right-click.
- **`screenshots`** (array of ScreenshotSpec): Media previews for rich install dialogs (`form_factor: "wide"` or `"narrow"`).
""",
    ),
    "pwa://specs/serviceworker-strategies": (
        "text/markdown",
        """# ServiceWorker Offline Caching Strategies Guide

ServiceWorkers intercept network requests via the `fetch` event listener and orchestrate CacheStorage.

## Standard Caching Strategies

### 1. Stale-While-Revalidate (Recommended for App Shell & Dynamic Feeds)
- **Mechanism**: Immediately returns cached response if available for instant rendering, while asynchronously sending a network request to update the cache in the background.
- **Best for**: Homepages, social feeds, avatars, documentation pages, dashboard shells.

### 2. Cache-First (Falling back to Network)
- **Mechanism**: Checks CacheStorage first. If found, returns immediately. If missing, fetches from network, saves to cache, and returns.
- **Best for**: Immutable static assets (versioned JS bundles, CSS files, SVG icons, fonts, static images).

### 3. Network-First (Falling back to Cache)
- **Mechanism**: Attempts network request first. If network succeeds, updates cache and returns. If network fails (offline), returns cached version or offline fallback page.
- **Best for**: Real-time APIs, user profile data, shopping carts, live inventory.

### 4. Network-Only
- **Mechanism**: Never reads from or writes to cache; directly proxies to network.
- **Best for**: Payment processing, auth logins, telemetry, non-idempotent POST/PUT requests.

### 5. Cache-Only
- **Mechanism**: Only serves from cache. Never hits network.
- **Best for**: Pre-bundled offline packages or strictly sandboxed offline execution.

## Precaching & Lifecycle Best Practices
- **`install` event**: Call `cache.addAll(PRECACHE_ASSETS)` and `self.skipWaiting()`.
- **`activate` event**: Delete obsolete cache versions (`caches.keys()`) and call `self.clients.claim()`.
- **Offline Fallback**: Precache `/offline.html` to guarantee a branded offline experience when offline.
""",
    ),
    "pwa://specs/share-and-file-handling": (
        "text/markdown",
        """# Web Share Target & File Handling APIs Reference

## 1. Web Share Target API
Allows your PWA to register as a share target in the operating system's native share dialog (via `navigator.share`).

### Schema Keys:
- **`action`**: Target URL that handles the share (must resolve within manifest `scope`).
- **`method`**: `'GET'` or `'POST'`.
- **`enctype`**: `'application/x-www-form-urlencoded'` (default) or `'multipart/form-data'` (mandatory when receiving files).
- **`params`**: Object mapping `{ title, text, url, files }` to query parameter or form field names.
- **`params.files`**: Object or array of objects with `{ name, accept }` specifying form field name and accepted MIME types or file extensions.

## 2. File Handling API
Allows your PWA to register as an OS file handler in Windows Explorer, macOS Finder, or Linux file managers.

### Schema Keys:
- **`action`**: Target URL that opens when a file is double-clicked or opened with the PWA.
- **`name`**: Human-readable label for file type associations.
- **`accept`**: Map of MIME types to arrays of file extensions, e.g. `{"text/plain": [".txt", ".md"], "image/png": [".png"]}`.
- **`launch_type`**: `'single-client'` (reuses existing window) or `'multiple-clients'` (opens separate window per file).

### Client Consumer (`launchQueue`):
```javascript
if ('launchQueue' in window && 'files' in LaunchParams.prototype) {
  launchQueue.setConsumer(async (launchParams) => {
    for (const fileHandle of launchParams.files) {
      const file = await fileHandle.getFile();
      console.log('Opened file:', file.name, file.type);
    }
  });
}
```
""",
    ),
}


# ============================================================================
# Registered Prompts Specifications
# ============================================================================

REGISTERED_PROMPTS: List[Dict[str, Any]] = [
    {
        "name": "pwa_scaffold_project",
        "description": "Interactive wizard prompt for converting any web app into an offline-first PWA with manifest, icons, and service worker.",
        "arguments": [
            {
                "name": "app_name",
                "description": "Name of the web application",
                "required": True,
            },
            {
                "name": "app_type",
                "description": "Type of application (e.g. ecommerce, game, productivity, dashboard, blog, docs, crypto)",
                "required": False,
            },
            {
                "name": "primary_color",
                "description": "Brand primary theme color in hex (e.g. #3b82f6)",
                "required": False,
            },
        ],
    },
    {
        "name": "pwa_offline_strategy_advisor",
        "description": "Advisory prompt for choosing the optimal caching architecture and ServiceWorker strategy based on app requirements.",
        "arguments": [
            {
                "name": "content_type",
                "description": "Primary content type (static, real-time, dynamic API, media-heavy)",
                "required": True,
            },
            {
                "name": "offline_priority",
                "description": "Offline priority level (critical full offline, partial fallback, read-only offline)",
                "required": False,
            },
        ],
    },
    {
        "name": "pwa_share_and_file_handler_prompt",
        "description": "Interactive guidance prompt for integrating Web Share Target and OS File Handling APIs into a PWA.",
        "arguments": [
            {
                "name": "app_name",
                "description": "Name of the application",
                "required": True,
            },
            {
                "name": "file_extensions",
                "description": "Comma-separated file extensions to handle (e.g. .txt,.md,.json,.png)",
                "required": False,
            },
            {
                "name": "supports_share_files",
                "description": "Whether to accept incoming shared files (true/false)",
                "required": False,
            },
        ],
    },
]


# ============================================================================
# Core MCP Handlers
# ============================================================================

def _execute_tool(name: str, args: Dict[str, Any]) -> Tuple[str, bool]:
    """Execute a registered tool and return (result_text, is_error)."""
    try:
        if name == "pwa_generate_manifest":
            app_name = args.get("name")
            if not app_name:
                return "Error: 'name' parameter is required for manifest generation.", True

            template_name = args.get("template")
            if template_name:
                try:
                    overrides = {k: v for k, v in args.items() if v is not None and k not in ["template", "include_meta_tags"]}
                    manifest_cfg, _ = generate_from_template(template_name, **overrides)
                except Exception as e:
                    return f"Error applying template '{template_name}': {str(e)}", True
            else:
                # Parse icons if provided
                raw_icons = args.get("icons") or [
                    {"src": "/icons/icon-192x192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                    {"src": "/icons/icon-512x512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                    {"src": "/icons/maskable-512x512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
                ]
                icon_specs = [IconSpec.from_dict(i) if isinstance(i, dict) else i for i in raw_icons]

                # Parse shortcuts if provided
                raw_shortcuts = args.get("shortcuts") or []
                shortcut_specs = [ShortcutSpec.from_dict(s) if isinstance(s, dict) else s for s in raw_shortcuts]

                manifest_cfg = PWAManifestConfig(
                    name=app_name,
                    short_name=args.get("short_name") or app_name[:12],
                    description=args.get("description"),
                    start_url=args.get("start_url", "/"),
                    scope=args.get("scope", "/"),
                    display=args.get("display", DisplayMode.STANDALONE),
                    orientation=args.get("orientation"),
                    theme_color=args.get("theme_color", "#2563eb"),
                    background_color=args.get("background_color", "#ffffff"),
                    id=args.get("id"),
                    lang=args.get("lang", "en"),
                    dir=args.get("dir", "auto"),
                    categories=args.get("categories") or ["utilities"],
                    icons=icon_specs,
                    shortcuts=shortcut_specs,
                )

            manifest_json = generate_manifest_json(manifest_cfg, indent=2)
            meta_tags = ""
            if args.get("include_meta_tags", True):
                meta_tags = generate_html_meta_tags(manifest_cfg)

            output_lines = [
                "### PWA Manifest Generated Successfully",
                "",
                "```json",
                manifest_json,
                "```",
            ]
            if meta_tags:
                output_lines.extend([
                    "",
                    "### Recommended HTML <head> Meta Tags",
                    "",
                    "```html",
                    meta_tags,
                    "```",
                ])

            return "\n".join(output_lines), False

        elif name == "pwa_generate_serviceworker":
            strategy_str = args.get("strategy", "stale_while_revalidate")
            strategy_enum = CachingStrategy.from_string(strategy_str)

            sw_config = ServiceWorkerConfig(
                cache_name=args.get("cache_name", "pwa-cache"),
                cache_version=args.get("cache_version", "v1"),
                caching_strategy=strategy_enum,
                precache_urls=args.get("precache_urls", ["/", "/index.html", "/offline.html"]),
                offline_fallback_url=args.get("offline_fallback_url", "/offline.html"),
                enable_navigation_preload=args.get("enable_navigation_preload", True),
                enable_background_sync=args.get("enable_background_sync", False),
                enable_push_notifications=args.get("enable_push_notifications", False),
            )

            sw_code = generate_service_worker(sw_config)
            output_lines = [
                "### ServiceWorker Script (`sw.js`)",
                "",
                "```javascript",
                sw_code,
                "```",
            ]

            if args.get("include_registration_snippet", True):
                snippet = generate_sw_registration_script(sw_path="/sw.js", scope="/")
                output_lines.extend([
                    "",
                    "### Client-Side Registration Snippet",
                    "",
                    "```html",
                    snippet,
                    "```",
                ])

            return "\n".join(output_lines), False

        elif name == "pwa_generate_icons":
            app_name = args.get("name", "App")
            letter = args.get("letter") or (app_name[:2] if len(app_name) >= 2 else app_name[:1]).upper()
            bg_color = args.get("bg_color", "#2563eb")
            fg_color = args.get("fg_color", "#ffffff")
            shape = args.get("shape", "rounded")
            icon_name = args.get("icon_name")
            sizes = args.get("sizes", [192, 512])

            # Generate primary SVG
            svg_content = generate_icon_svg(
                name_or_letter=letter,
                bg_color=bg_color,
                fg_color=fg_color,
                shape=shape,
                icon_name=icon_name,
                maskable=False,
                size=512,
            )

            maskable_svg = generate_icon_svg(
                name_or_letter=letter,
                bg_color=bg_color,
                fg_color=fg_color,
                shape="square",
                icon_name=icon_name,
                maskable=True,
                size=512,
            )

            output_lines = [
                f"### PWA SVG App Icon Generated ({app_name})",
                f"- **Glyph**: {letter}",
                f"- **Background**: `{bg_color}`",
                f"- **Foreground**: `{fg_color}`",
                f"- **Shape**: `{shape}`",
                f"- **Target Dimensions**: {sizes}",
                "",
                "#### Standard Icon SVG (512x512)",
                "```xml",
                svg_content,
                "```",
                "",
                "#### Android Maskable Icon SVG (Adaptive Safe Zone)",
                "```xml",
                maskable_svg,
                "```",
            ]
            return "\n".join(output_lines), False

        elif name == "pwa_audit_manifest":
            raw_manifest = args.get("manifest")
            if not raw_manifest:
                return "Error: 'manifest' parameter is required for audit.", True

            report = validate_manifest(raw_manifest)
            score_bar = "█" * (report.installable_score // 5) + "░" * (20 - (report.installable_score // 5))

            lines = [
                f"### PWA Manifest Audit Report",
                f"**Overall Readiness Score**: `{report.installable_score}/100` `[{score_bar}]`",
                f"**Installable**: `{'YES (Ready for PWA Install)' if report.is_valid and not report.has_errors() else 'NO (Missing requirements)'}`",
                f"**Lighthouse PWA Ready**: `{'YES' if report.installable_score >= 85 and not report.has_errors() else 'NO'}`",
                "",
                "#### Passed Criteria",
            ]
            if report.passed_checks:
                for p in report.passed_checks:
                    lines.append(f"- [x] {p}")
            else:
                lines.append("- _None_")

            if report.warnings:
                lines.extend(["", "#### Warnings"])
                for w in report.warnings:
                    lines.append(f"- ⚠️ **{w.code}**: {w.message}")

            if report.errors():
                lines.extend(["", "#### Errors (Blockers)"])
                for e in report.errors():
                    lines.append(f"- ❌ **{e.code}**: {e.message}")

            recommendations = []
            for issue in report.issues + report.warnings:
                if issue.fix_suggestion:
                    recommendations.append(issue.fix_suggestion)

            if recommendations:
                lines.extend(["", "#### Recommendations"])
                for idx, r in enumerate(recommendations, 1):
                    lines.append(f"{idx}. {r}")

            return "\n".join(lines), False

        elif name == "pwa_html_meta_tags":
            cfg = PWAManifestConfig(
                name=args.get("name", "Progressive Web App"),
                short_name=args.get("short_name"),
                description=args.get("description"),
                theme_color=args.get("theme_color", "#2563eb"),
            )
            tags = generate_html_meta_tags(cfg, manifest_path=args.get("manifest_path", "/manifest.webmanifest"))
            return f"```html\n{tags}\n```", False

        elif name == "pwa_list_templates":
            category = args.get("category")
            templates = list_templates()
            if category:
                templates = [t for t in templates if t.get("category") == category]

            lines = [f"### Built-In PWA Templates ({len(templates)} available)", ""]
            for t in templates:
                lines.append(f"#### `{t['id']}` - {t['name']}")
                lines.append(f"- **Category**: `{t.get('category', 'general')}`")
                lines.append(f"- **Display**: `{t.get('display', 'standalone')}`")
                lines.append(f"- **Theme Color**: `{t.get('theme_color', '#2563eb')}`")
                lines.append(f"- **Description**: {t.get('description', '')}")
                if t.get("shortcuts"):
                    sc_names = [s.get("name") if isinstance(s, dict) else s.name for s in t["shortcuts"]]
                    lines.append(f"- **Shortcuts**: {', '.join(sc_names)}")
                lines.append("")
            return "\n".join(lines), False

        elif name == "pwa_diagnostics":
            verbose = args.get("verbose", False)
            pinfo = get_platform_info()
            diag: Dict[str, Any] = {
                "pwa_manifest_builder_version": SERVER_VERSION,
                "mcp_protocol_version": MCP_PROTOCOL_VERSION,
                "python_version": pinfo.python_version,
                "platform": pinfo.os_type,
                "architecture": pinfo.architecture,
                "is_windows": pinfo.is_windows,
                "is_macos": pinfo.is_macos,
                "is_linux": pinfo.is_linux,
                "cwd": os.getcwd(),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "template_count": len(TEMPLATES),
                "tools_count": len(REGISTERED_TOOLS),
                "resources_count": len(REGISTERED_RESOURCES),
                "prompts_count": len(REGISTERED_PROMPTS),
            }
            if verbose:
                diag["sys_path"] = sys.path
                diag["env_keys"] = sorted(list(os.environ.keys()))

            diag_text = json.dumps(diag, indent=2)
            return f"```json\n{diag_text}\n```", False

        elif name == "pwa_simulate_shortcuts":
            from .shortcuts_simulator import simulate_app_shortcuts
            from .catalog import get_template
            shortcuts = args.get("shortcuts", [])
            template_id = args.get("template")
            if template_id and not shortcuts:
                tmpl = get_template(template_id)
                if tmpl and tmpl.manifest:
                    shortcuts = tmpl.manifest.shortcuts
            report = simulate_app_shortcuts(shortcuts)
            return json.dumps(report.to_dict(), indent=2), False

        elif name == "pwa_validate_protocol_handlers":
            from .shortcuts_simulator import validate_protocol_handlers
            handlers = args.get("protocol_handlers") or args.get("handlers") or []
            scope = args.get("scope", "/")
            report = validate_protocol_handlers(handlers, scope=scope)
            return json.dumps(report.to_dict(), indent=2), False

        elif name == "pwa_validate_share_target":
            from .share_and_file_handlers import validate_share_target
            target = args.get("share_target") or args.get("manifest") or {}
            scope = args.get("scope", "/")
            report = validate_share_target(target, scope=scope)
            return json.dumps(report.to_dict(), indent=2), False

        elif name == "pwa_validate_file_handlers":
            from .share_and_file_handlers import validate_file_handlers
            handlers = args.get("file_handlers") or args.get("manifest") or []
            scope = args.get("scope", "/")
            report = validate_file_handlers(handlers, scope=scope)
            return json.dumps(report.to_dict(), indent=2), False

        elif name == "pwa_simulate_share":
            from .share_and_file_handlers import simulate_web_share
            target = args.get("share_target") or {}
            title = args.get("title")
            text = args.get("text")
            url = args.get("url")
            files = args.get("files")
            sim_res = simulate_web_share(target, title=title, text=text, url=url, files=files)
            return json.dumps(sim_res.to_dict(), indent=2), False

        elif name == "pwa_simulate_file_open":
            from .share_and_file_handlers import simulate_file_launch
            handlers = args.get("file_handlers") or []
            file_name = args.get("file_name", "")
            mime_type = args.get("mime_type")
            sim_res = simulate_file_launch(handlers, file_name=file_name, mime_type=mime_type)
            return json.dumps(sim_res.to_dict(), indent=2), False

        else:
            return f"Unknown tool: {name}", True

    except Exception as ex:
        err_msg = f"Tool execution exception: {str(ex)}\n{traceback.format_exc()}"
        return err_msg, True


def handle_jsonrpc_request(request: Union[Dict[str, Any], str, List[Any]]) -> Union[Dict[str, Any], List[Dict[str, Any]], None]:
    """Parse and dispatch a single or batched JSON-RPC 2.0 request."""
    if isinstance(request, str):
        try:
            req_obj = json.loads(request)
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": ERR_PARSE_ERROR,
                    "message": f"Parse error: {str(e)}",
                },
            }
    else:
        req_obj = request

    # Handle JSON-RPC 2.0 Batch Requests
    if isinstance(req_obj, list):
        if not req_obj:
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": ERR_INVALID_REQUEST,
                    "message": "Invalid request: empty batch",
                },
            }
        responses = []
        for single_req in req_obj:
            resp = _handle_single_request(single_req)
            if resp is not None:
                responses.append(resp)
        return responses if responses else None

    if not isinstance(req_obj, dict):
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": ERR_INVALID_REQUEST,
                "message": "Invalid request: expected JSON object",
            },
        }

    return _handle_single_request(req_obj)


def _handle_single_request(req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process an individual JSON-RPC 2.0 request dictionary."""
    req_id = req.get("id")
    is_notification = "id" not in req

    # Validate JSON-RPC structure
    if req.get("jsonrpc") != "2.0" or "method" not in req:
        if is_notification:
            return None
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": ERR_INVALID_REQUEST,
                "message": "Invalid JSON-RPC 2.0 request structure",
            },
        }

    method = req.get("method", "")
    params = req.get("params") or {}

    # 1. Initialize
    if method == "initialize":
        result = {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {},
                "logging": {},
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
        }
        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    # 2. Initialized Notification / Ping
    elif method in ["notifications/initialized", "initialized"]:
        return None

    elif method == "ping":
        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    # 3. Tools API
    elif method == "tools/list":
        if is_notification:
            return None
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": REGISTERED_TOOLS},
        }

    elif method == "tools/call":
        if not isinstance(params, dict) or "name" not in params:
            if is_notification:
                return None
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": ERR_INVALID_PARAMS,
                    "message": "Missing 'name' in tools/call params",
                },
            }

        tool_name = params.get("name", "")
        tool_args = params.get("arguments") or {}

        result_text, is_err = _execute_tool(tool_name, tool_args)
        if is_notification:
            return None
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": result_text,
                    }
                ],
                "isError": is_err,
            },
        }

    # 4. Resources API
    elif method == "resources/list":
        if is_notification:
            return None
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"resources": REGISTERED_RESOURCES},
        }

    elif method == "resources/read":
        uri = params.get("uri") if isinstance(params, dict) else None
        if not uri:
            if is_notification:
                return None
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": ERR_INVALID_PARAMS,
                    "message": "Missing 'uri' in resources/read params",
                },
            }

        if uri in RESOURCE_CONTENT_MAP:
            mime_type, content_text = RESOURCE_CONTENT_MAP[uri]
            if is_notification:
                return None
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": mime_type,
                            "text": content_text,
                        }
                    ]
                },
            }
        else:
            if is_notification:
                return None
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": ERR_INVALID_PARAMS,
                    "message": f"Resource not found: {uri}",
                },
            }

    # 5. Prompts API
    elif method == "prompts/list":
        if is_notification:
            return None
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"prompts": REGISTERED_PROMPTS},
        }

    elif method == "prompts/get":
        prompt_name = params.get("name") if isinstance(params, dict) else None
        prompt_args = (params.get("arguments") or {}) if isinstance(params, dict) else {}

        if not prompt_name:
            if is_notification:
                return None
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": ERR_INVALID_PARAMS,
                    "message": "Missing 'name' in prompts/get params",
                },
            }

        if prompt_name == "pwa_scaffold_project":
            app_name = prompt_args.get("app_name", "My Web App")
            app_type = prompt_args.get("app_type", "general")
            color = prompt_args.get("primary_color", "#2563eb")

            prompt_body = f"""You are a Principal PWA Architect. Convert '{app_name}' (type: {app_type}, brand color: {color}) into an offline-first Progressive Web App.

Please execute the following steps:
1. Generate the W3C 'manifest.webmanifest' JSON configuration with proper scope, display mode, and icon paths.
2. Generate the HTML <head> meta tags for Apple iOS and Android home screen installation.
3. Architect the ServiceWorker ('sw.js') with optimal precaching and runtime caching strategy.
4. Provide the SVG icon specifications for 192x192, 512x512, and Android adaptive maskable icons.
5. Audit the resulting configuration against Google Lighthouse PWA installability rules."""

            if is_notification:
                return None
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "description": f"Scaffold PWA setup for {app_name}",
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": prompt_body,
                            },
                        }
                    ],
                },
            }

        elif prompt_name == "pwa_offline_strategy_advisor":
            content_type = prompt_args.get("content_type", "static")
            priority = prompt_args.get("offline_priority", "balanced")

            prompt_body = f"""Advise on the optimal ServiceWorker caching strategy for a web app with primary content type '{content_type}' and offline priority '{priority}'.

Compare tradeoffs between Cache-First, Network-First, and Stale-While-Revalidate strategies, precache budgets, and cache eviction quotas."""

            if is_notification:
                return None
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "description": "ServiceWorker Offline Strategy Consultation",
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": prompt_body,
                            },
                        }
                    ],
                },
            }

        elif prompt_name == "pwa_share_and_file_handler_prompt":
            app_name = prompt_args.get("app_name", "My App")
            exts = prompt_args.get("file_extensions", ".txt,.md")
            share_files = prompt_args.get("supports_share_files", "true")

            prompt_body = f"""You are a Web Capabilities & PWA Architect. Configure the W3C Web Share Target and File Handling APIs for '{app_name}'.

Requirements:
1. File Handlers: Register associations for extensions [{exts}], configure single-client vs multiple-clients mode, and draft the launchQueue consumer JavaScript snippet.
2. Web Share Target: Define manifest.webmanifest 'share_target' schema (action, method POST, enctype multipart/form-data) supporting file sharing ({share_files}), and draft the ServiceWorker fetch interceptor to persist incoming shared payloads."""

            if is_notification:
                return None
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "description": f"Share Target & File Handling Setup for {app_name}",
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": prompt_body,
                            },
                        }
                    ],
                },
            }

        else:
            if is_notification:
                return None
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": ERR_INVALID_PARAMS,
                    "message": f"Unknown prompt: {prompt_name}",
                },
            }

    # Unknown Method
    else:
        if is_notification:
            return None
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": ERR_METHOD_NOT_FOUND,
                "message": f"Method not found: {method}",
            },
        }


def process_request(raw_input: str) -> Optional[str]:
    """Process raw JSON-RPC request line and return formatted JSON response string."""
    trimmed = raw_input.strip()
    if not trimmed:
        return None

    resp = handle_jsonrpc_request(trimmed)
    if resp is None:
        return None
    return json.dumps(resp, ensure_ascii=False)


def run_stdio_server(debug: bool = False) -> None:
    """Run the stdio MCP JSON-RPC server loop."""
    if debug:
        sys.stderr.write(f"[{SERVER_NAME}] Starting MCP stdio server v{SERVER_VERSION} (protocol: {MCP_PROTOCOL_VERSION})...\n")
        sys.stderr.flush()

    try:
        for line in sys.stdin:
            if not line:
                break
            line_str = line.strip()
            if not line_str:
                continue

            if debug:
                sys.stderr.write(f"[{SERVER_NAME} REQ] {line_str}\n")
                sys.stderr.flush()

            response_str = process_request(line_str)
            if response_str is not None:
                if debug:
                    sys.stderr.write(f"[{SERVER_NAME} RESP] {response_str}\n")
                    sys.stderr.flush()
                sys.stdout.write(response_str + "\n")
                sys.stdout.flush()

    except (KeyboardInterrupt, SystemExit):
        if debug:
            sys.stderr.write(f"[{SERVER_NAME}] Shutting down stdio server.\n")
            sys.stderr.flush()
    except Exception as e:
        sys.stderr.write(f"[{SERVER_NAME} FATAL] {str(e)}\n{traceback.format_exc()}\n")
        sys.stderr.flush()


if __name__ == "__main__":
    run_stdio_server(debug="--debug" in sys.argv)
