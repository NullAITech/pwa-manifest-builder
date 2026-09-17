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
