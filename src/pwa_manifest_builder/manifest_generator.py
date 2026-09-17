"""
W3C Web App Manifest and HTML Meta Tag Generator.

Transforms PWAManifestConfig domain models and manifest dictionaries into validated,
W3C-compliant JSON manifests and comprehensive, cross-browser HTML <head> meta tags.
100% Python Standard Library.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .models import PWAManifestConfig, DisplayMode, Orientation, IconSpec, ShortcutSpec
from .compat import atomic_write_text, normalize_path


def _coerce_manifest_config(config: Union[PWAManifestConfig, Dict[str, Any]]) -> PWAManifestConfig:
    """Coerces dict or PWAManifestConfig into a PWAManifestConfig instance."""
    if isinstance(config, PWAManifestConfig):
        return config
    if isinstance(config, dict):
        return PWAManifestConfig.from_dict(config)
    raise TypeError(f"Expected PWAManifestConfig or dict, got {type(config).__name__}")


def generate_manifest_dict(config: Union[PWAManifestConfig, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generates a W3C-compliant Web App Manifest dictionary from a PWAManifestConfig instance or dict.
    Cleans up optional fields and ensures schema compliance.
    """
    cfg = _coerce_manifest_config(config)
    return cfg.to_dict()


def generate_manifest_json(config: Union[PWAManifestConfig, Dict[str, Any]], indent: int = 2) -> str:
    """
    Serializes a PWAManifestConfig or manifest dict into a formatted, W3C-compliant JSON string.
    """
    cfg = _coerce_manifest_config(config)
    return cfg.to_json(indent=indent)


def generate_html_meta_tags(
    config: Union[PWAManifestConfig, Dict[str, Any]],
    manifest_path: str = "/manifest.webmanifest",
    include_viewport: bool = True
) -> str:
    """
    Generates a complete suite of cross-browser HTML <head> meta tags for PWAs.
    Includes:
      - W3C Web App Manifest link
      - Theme & Background colors
      - Apple iOS Web App & Touch Icon meta tags
      - Microsoft Tile & PWA application tags
      - Mobile Viewport optimization (viewport-fit=cover)
      - App description & title
    """
    cfg = _coerce_manifest_config(config)
    app_title = cfg.short_name or cfg.name
    theme_color = cfg.theme_color or "#000000"
    
    # Locate best icon for Apple touch icon (prefer 180x180, 192x192, or first PNG)
    apple_icon_src = None
    ms_icon_src = None

    for icon in cfg.icons:
        src = icon.src if isinstance(icon, IconSpec) else icon.get("src", "")
        sizes = icon.sizes if isinstance(icon, IconSpec) else icon.get("sizes", "")
        
        if "180x180" in sizes:
            apple_icon_src = src
        elif not apple_icon_src and ("192x192" in sizes or "512x512" in sizes):
            apple_icon_src = src
            
        if "144x144" in sizes or "150x150" in sizes:
            ms_icon_src = src
        elif not ms_icon_src and "192x192" in sizes:
            ms_icon_src = src

    if not apple_icon_src and cfg.icons:
        first_icon = cfg.icons[0]
        apple_icon_src = first_icon.src if isinstance(first_icon, IconSpec) else first_icon.get("src", "/icons/icon-180x180.png")
    if not apple_icon_src:
        apple_icon_src = "/icons/icon-180x180.png"

    if not ms_icon_src:
        ms_icon_src = apple_icon_src

    lines: List[str] = [
        "<!-- PWA Core Metadata & Manifest -->",
    ]

    if include_viewport:
        lines.append('<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">')

    lines.extend([
        f'<link rel="manifest" href="{manifest_path}">',
        f'<meta name="theme-color" content="{theme_color}">',
        f'<meta name="application-name" content="{app_title}">',
    ])

    if cfg.description:
        # Escape quotes in description for HTML attribute safety
        safe_desc = cfg.description.replace('"', '&quot;')
        lines.append(f'<meta name="description" content="{safe_desc}">')

    lines.extend([
        "",
        "<!-- Apple iOS PWA Capabilities & Icons -->",
        '<meta name="mobile-web-app-capable" content="yes">',
        '<meta name="apple-mobile-web-app-capable" content="yes">',
        '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">',
        f'<meta name="apple-mobile-web-app-title" content="{app_title}">',
        f'<link rel="apple-touch-icon" href="{apple_icon_src}">',
    ])

    # Add specific size apple touch icons if available
    touch_sizes = ["152x152", "167x167", "180x180"]
    for icon in cfg.icons:
        src = icon.src if isinstance(icon, IconSpec) else icon.get("src", "")
        sizes = icon.sizes if isinstance(icon, IconSpec) else icon.get("sizes", "")
        if sizes in touch_sizes and src != apple_icon_src:
            lines.append(f'<link rel="apple-touch-icon" sizes="{sizes}" href="{src}">')

    lines.extend([
        "",
        "<!-- Microsoft Tile / Windows PWA Metadata -->",
        f'<meta name="msapplication-TileColor" content="{theme_color}">',
        f'<meta name="msapplication-TileImage" content="{ms_icon_src}">',
        '<meta name="msapplication-tap-highlight" content="no">',
    ])

    return "\n".join(lines)


def save_manifest(
    config: Union[PWAManifestConfig, Dict[str, Any]],
    output_path: Union[str, Path],
    indent: int = 2
) -> Path:
    """
    Serializes and writes the Web App Manifest atomically to the specified output path.
    """
    json_text = generate_manifest_json(config, indent=indent)
    return atomic_write_text(output_path, json_text, encoding="utf-8")


def build_manifest(
    name: str,
    short_name: Optional[str] = None,
    description: Optional[str] = None,
    start_url: str = "/",
    scope: str = "/",
    theme_color: str = "#000000",
    background_color: str = "#ffffff",
    display: Union[str, DisplayMode] = DisplayMode.STANDALONE,
    icons: Optional[List[Union[IconSpec, Dict[str, Any]]]] = None,
    **kwargs: Any
) -> PWAManifestConfig:
    """
    Factory helper to instantiate a PWAManifestConfig with standard defaults.
    """
    parsed_icons: List[IconSpec] = []
    if icons:
        for i in icons:
            if isinstance(i, IconSpec):
                parsed_icons.append(i)
            elif isinstance(i, dict):
                parsed_icons.append(IconSpec.from_dict(i))

    return PWAManifestConfig(
        name=name,
        short_name=short_name or name[:12],
        description=description,
        start_url=start_url,
        scope=scope,
        theme_color=theme_color,
        background_color=background_color,
        display=display,
        icons=parsed_icons,
        **kwargs
    )


def generate_install_prompt_banner_html(
    config: Union[PWAManifestConfig, Dict[str, Any]],
    banner_id: str = "pwa-install-banner",
    banner_title: Optional[str] = None,
    banner_prompt_text: Optional[str] = None,
    position: str = "bottom",
    accent_color: Optional[str] = None,
    dismiss_days: int = 7,
) -> str:
    """
    Generates a production-ready, accessible, Material 3 influenced floating install prompt banner.
    Captures the `beforeinstallprompt` browser event and provides iOS Safari fallback instructions.
    
    100% self-contained HTML/CSS/JavaScript. Design influenced by Material 3 tokens.
    """
    cfg = _coerce_manifest_config(config)
    app_title = (banner_title or cfg.short_name or cfg.name or "App").replace('"', '&quot;').replace('<', '&lt;')
    prompt_desc = (banner_prompt_text or cfg.description or "Install this app for faster access and offline use.").replace('"', '&quot;').replace('<', '&lt;')
    primary_color = accent_color or cfg.theme_color or "#1a73e8"
    
    # Locate best icon
    icon_src = "/icons/icon-192x192.png"
    for icon in cfg.icons:
        src = icon.src if isinstance(icon, IconSpec) else icon.get("src", "")
        if src:
            icon_src = src
            if "192x192" in (icon.sizes if isinstance(icon, IconSpec) else icon.get("sizes", "")):
                break

    pos_style = "bottom: 20px;" if position != "top" else "top: 20px;"

    return f"""<!-- Material 3 Influenced PWA Install Banner Component -->
<aside id="{banner_id}" class="pwa-install-card pwa-hidden" role="dialog" aria-labelledby="{banner_id}-title" aria-describedby="{banner_id}-desc" style="{pos_style}">
  <div class="pwa-card-content">
    <img class="pwa-app-icon" src="{icon_src}" alt="{app_title} icon" width="48" height="48" loading="lazy" />
    <div class="pwa-text-group">
      <h2 id="{banner_id}-title" class="pwa-title">{app_title}</h2>
      <p id="{banner_id}-desc" class="pwa-desc">{prompt_desc}</p>
    </div>
  </div>
  <div class="pwa-action-group">
    <button type="button" id="{banner_id}-dismiss-btn" class="pwa-btn pwa-btn-text">Not now</button>
    <button type="button" id="{banner_id}-install-btn" class="pwa-btn pwa-btn-primary">Install</button>
  </div>
  <div id="{banner_id}-ios-sheet" class="pwa-ios-sheet pwa-hidden">
    <p>To install on iOS: tap <strong>Share</strong> <span aria-hidden="true">⎋</span> then <strong>Add to Home Screen</strong> <span aria-hidden="true">⊞</span>.</p>
  </div>
</aside>

<style>
/* Material 3 Influenced Floating Sheet Tokens */
#{banner_id} {{
  --pwa-primary: {primary_color};
  --pwa-surface: #ffffff;
  --pwa-on-surface: #1f1f1f;
  --pwa-on-surface-variant: #444746;
  --pwa-outline: #c4c7c5;
  --pwa-elevation-3: 0 4px 16px rgba(0, 0, 0, 0.14), 0 2px 6px rgba(0, 0, 0, 0.08);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  position: fixed;
  left: 50%;
  transform: translateX(-50%);
  width: calc(100% - 32px);
  max-width: 480px;
  background: var(--pwa-surface);
  color: var(--pwa-on-surface);
  box-shadow: var(--pwa-elevation-3);
  border-radius: 20px;
  padding: 16px 20px;
  box-sizing: border-box;
  z-index: 99999;
  display: flex;
  flex-direction: column;
  gap: 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  backdrop-filter: blur(12px);
  transition: opacity 0.25s cubic-bezier(0.2, 0, 0, 1), transform 0.25s cubic-bezier(0.2, 0, 0, 1);
}}
#{banner_id}.pwa-hidden {{
  opacity: 0;
  pointer-events: none;
  transform: translate(-50%, 20px);
}}
#{banner_id} .pwa-card-content {{
  display: flex;
  align-items: center;
  gap: 14px;
}}
#{banner_id} .pwa-app-icon {{
  border-radius: 12px;
  object-fit: cover;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
}}
#{banner_id} .pwa-text-group {{
  display: flex;
  flex-direction: column;
  min-width: 0;
}}
#{banner_id} .pwa-title {{
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.3;
  color: var(--pwa-on-surface);
}}
#{banner_id} .pwa-desc {{
  margin: 2px 0 0;
  font-size: 13px;
  line-height: 1.4;
  color: var(--pwa-on-surface-variant);
}}
#{banner_id} .pwa-action-group {{
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}}
#{banner_id} .pwa-btn {{
  cursor: pointer;
  border-radius: 20px;
  padding: 8px 18px;
  font-size: 14px;
  font-weight: 500;
  border: none;
  outline: none;
  transition: background-color 0.2s ease, box-shadow 0.2s ease;
}}
#{banner_id} .pwa-btn-primary {{
  background: var(--pwa-primary);
  color: #ffffff;
}}
#{banner_id} .pwa-btn-primary:hover {{
  filter: brightness(1.08);
}}
#{banner_id} .pwa-btn-text {{
  background: transparent;
  color: var(--pwa-on-surface-variant);
}}
#{banner_id} .pwa-btn-text:hover {{
  background: rgba(0, 0, 0, 0.05);
}}
#{banner_id} .pwa-ios-sheet {{
  border-top: 1px solid var(--pwa-outline);
  padding-top: 10px;
  font-size: 13px;
  color: var(--pwa-on-surface-variant);
}}
#{banner_id} .pwa-ios-sheet strong {{
  color: var(--pwa-on-surface);
}}
</style>

<script>
(function() {{
  var banner = document.getElementById("{banner_id}");
  var installBtn = document.getElementById("{banner_id}-install-btn");
  var dismissBtn = document.getElementById("{banner_id}-dismiss-btn");
  var iosSheet = document.getElementById("{banner_id}-ios-sheet");
  var deferredPrompt = null;
  var DISMISS_KEY = "pwa-prompt-dismissed";
  var DISMISS_EXPIRY_MS = {dismiss_days} * 24 * 60 * 60 * 1000;

  function isDismissed() {{
    try {{
      var timestamp = localStorage.getItem(DISMISS_KEY);
      if (!timestamp) return false;
      return (Date.now() - parseInt(timestamp, 10)) < DISMISS_EXPIRY_MS;
    }} catch (e) {{
      return false;
    }}
  }}

  function showBanner() {{
    if (isDismissed()) return;
    if (banner) banner.classList.remove("pwa-hidden");
  }}

  function hideBanner() {{
    if (banner) banner.classList.add("pwa-hidden");
  }}

  window.addEventListener("beforeinstallprompt", function(e) {{
    e.preventDefault();
    deferredPrompt = e;
    showBanner();
  }});

  if (installBtn) {{
    installBtn.addEventListener("click", function() {{
      if (deferredPrompt) {{
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(function(choiceResult) {{
          deferredPrompt = null;
          hideBanner();
        }});
      }} else if (/iphone|ipad|ipod/.test(navigator.userAgent.toLowerCase())) {{
        if (iosSheet) iosSheet.classList.toggle("pwa-hidden");
      }}
    }});
  }}

  if (dismissBtn) {{
    dismissBtn.addEventListener("click", function() {{
      hideBanner();
      try {{
        localStorage.setItem(DISMISS_KEY, Date.now().toString());
      }} catch (e) {{}}
    }});
  }}

  // iOS Safari detection fallback
  var isIos = /iphone|ipad|ipod/.test(navigator.userAgent.toLowerCase());
  var isStandalone = ("standalone" in window.navigator) && window.navigator.standalone;
  if (isIos && !isStandalone && !isDismissed()) {{
    showBanner();
  }}
}})();
</script>"""

