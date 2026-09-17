"""App Shortcuts Action Simulator & URL Protocol Handler Validator.

Provides W3C protocol handler compliance validation (registerProtocolHandler /
protocol_handlers) and client-side deep-link routing / action simulation for App Shortcuts.
100% Python Standard Library.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Union

from .models import (
    IconSpec,
    PWAManifestConfig,
    ProtocolHandlerItem,
    ProtocolHandlerSpec,
    ProtocolHandlerValidationReport,
    ShortcutSimulatorResult,
    ShortcutSpec,
    ShortcutSuiteReport,
)

# Standard safelisted schemes permitted by W3C HTML & Manifest specification
# without requiring the 'web+' prefix
SAFELISTED_SCHEMES: Set[str] = {
    "bitcoin",
    "dat",
    "dweb",
    "geo",
    "gopher",
    "im",
    "ipfs",
    "ipns",
    "irc",
    "ircs",
    "magnet",
    "mailto",
    "matrix",
    "mms",
    "news",
    "nntp",
    "openpgp4fpr",
    "sip",
    "sms",
    "smsto",
    "ssb",
    "ssh",
    "tel",
    "urn",
    "webcal",
    "wtai",
    "xmpp",
}

CUSTOM_SCHEME_RE = re.compile(r"^web\+[a-z0-9\-_]+$", re.IGNORECASE)


def is_valid_protocol_scheme(scheme: str) -> bool:
    """Validate if protocol scheme satisfies W3C registration rules."""
    if not scheme or not isinstance(scheme, str):
        return False
    clean = scheme.strip().lower()
    if clean in SAFELISTED_SCHEMES:
        return True
    return bool(CUSTOM_SCHEME_RE.match(clean))


def validate_protocol_handlers(
    config_or_handlers: Union[PWAManifestConfig, List[Any], Dict[str, Any]],
    scope: str = "/",
) -> ProtocolHandlerValidationReport:
    """Validate protocol_handlers against W3C specification and synthesize registration JS."""
    raw_handlers: List[Any] = []
    resolved_scope = scope

    if isinstance(config_or_handlers, PWAManifestConfig):
        raw_handlers = config_or_handlers.protocol_handlers
        resolved_scope = config_or_handlers.scope or "/"
    elif isinstance(config_or_handlers, dict):
        raw_handlers = config_or_handlers.get("protocol_handlers", [])
        resolved_scope = config_or_handlers.get("scope", scope) or "/"
    elif isinstance(config_or_handlers, list):
        raw_handlers = config_or_handlers

    handlers_data: List[Dict[str, Any]] = []
    errors: List[str] = []
    warnings: List[str] = []

    valid_count = 0
    invalid_count = 0

    js_registrations: List[str] = []

    for idx, item in enumerate(raw_handlers):
        if isinstance(item, ProtocolHandlerSpec):
            proto = item.protocol
            target_url = item.url
            title = item.title
        elif isinstance(item, dict):
            proto = str(item.get("protocol", ""))
            target_url = str(item.get("url", ""))
            title = item.get("title")
        else:
            invalid_count += 1
            errors.append(f"Handler #{idx + 1}: invalid protocol handler data format.")
            continue

        item_errors: List[str] = []
        err_code: Optional[str] = None

        # 1. Scheme Check
        if not proto:
            item_errors.append("Missing required 'protocol' scheme.")
            err_code = "INVALID_PROTOCOL_SCHEME"
        elif not is_valid_protocol_scheme(proto):
            item_errors.append(
                f"Protocol '{proto}' is not permitted. Custom protocols must start with 'web+' "
                f"(e.g., 'web+notes'), or be a safelisted scheme (e.g., 'mailto', 'tel', 'sms', 'geo', 'webcal')."
            )
            err_code = "INVALID_PROTOCOL_SCHEME"

        # 2. URL Check
        if not target_url:
            item_errors.append("Missing required 'url' handler destination.")
            err_code = err_code or "MISSING_DESTINATION_URL"
        else:
            if "%s" not in target_url:
                item_errors.append(
                    f"Handler URL '{target_url}' must contain '%s' parameter placeholder for uri data."
                )
                err_code = err_code or "MISSING_TOKEN_PLACEHOLDER"

            # Check scope matching
            clean_url = target_url.split("?")[0].split("#")[0]
            clean_scope = resolved_scope.split("?")[0].split("#")[0]
            if clean_url.startswith("/") and clean_scope.startswith("/"):
                if not (clean_url.startswith(clean_scope) or (clean_url + "/").startswith(clean_scope)):
                    msg = f"Handler URL '{target_url}' appears to be outside manifest scope '{resolved_scope}'."
                    warnings.append(msg)
                    item_errors.append(msg)
                    err_code = err_code or "OUT_OF_SCOPE"

        if item_errors:
            invalid_count += 1
            for err in item_errors:
                errors.append(f"Handler '{proto or f'#{idx + 1}'}': {err}")
        else:
            valid_count += 1
            safe_proto = json.dumps(proto)
            safe_url = json.dumps(target_url)
            js_registrations.append(
                f"    navigator.registerProtocolHandler({safe_proto}, {safe_url});"
            )

        handlers_data.append(ProtocolHandlerItem(
            protocol=proto,
            url=target_url,
            title=title,
            is_valid=len(item_errors) == 0,
            issues=item_errors,
            error_code=err_code,
        ))

    # Generate browser script
    if js_registrations:
        reg_lines = "\n".join(js_registrations)
        script = f"""// Register PWA Protocol Handlers in browser
if (typeof navigator !== 'undefined' && 'registerProtocolHandler' in navigator) {{
  try {{
{reg_lines}
    console.info('[PWA] Registered {len(js_registrations)} protocol handler(s).');
  }} catch (err) {{
    console.warn('[PWA] Protocol handler registration failed:', err);
  }}
}}"""
    else:
        script = "// No valid protocol handlers to register."

    return ProtocolHandlerValidationReport(
        is_valid=(invalid_count == 0 and len(raw_handlers) > 0),
        valid_count=valid_count,
        invalid_count=invalid_count,
        handlers=handlers_data,
        errors=errors,
        warnings=warnings,
        registration_script=script,
    )


def simulate_app_shortcuts(
    config_or_shortcuts: Union[PWAManifestConfig, List[Any], Dict[str, Any]],
    scope: str = "/",
    manifest_url: str = "/",
) -> ShortcutSuiteReport:
    """Audit and simulate App Shortcuts, verifying icon specs and generating deep-link dispatcher."""
    raw_shortcuts: List[Any] = []
    resolved_scope = scope

    if isinstance(config_or_shortcuts, PWAManifestConfig):
        raw_shortcuts = config_or_shortcuts.shortcuts
        resolved_scope = config_or_shortcuts.scope or scope or "/"
    elif isinstance(config_or_shortcuts, dict):
        raw_shortcuts = config_or_shortcuts.get("shortcuts", [])
        resolved_scope = config_or_shortcuts.get("scope", scope) or "/"
    elif isinstance(config_or_shortcuts, list):
        raw_shortcuts = config_or_shortcuts

    results: List[ShortcutSimulatorResult] = []
    warnings: List[str] = []

    if len(raw_shortcuts) > 4:
        warnings.append(
            f"Configured {len(raw_shortcuts)} shortcuts exceeds the 4-item threshold; Android and Windows taskbars generally display a maximum of 4."
        )

    all_android_ready = True
    all_windows_ready = True

    route_cases: List[str] = []

    for idx, item in enumerate(raw_shortcuts):
        if isinstance(item, ShortcutSpec):
            name = item.name
            url = item.url
            short_name = item.short_name
            icons = item.icons
        elif isinstance(item, dict):
            name = str(item.get("name", ""))
            url = str(item.get("url", ""))
            short_name = item.get("short_name")
            raw_icons = item.get("icons", [])
            icons = [IconSpec.from_dict(i) if isinstance(i, dict) else i for i in raw_icons]
        else:
            continue

        issues: List[str] = []
        sc_warnings: List[str] = []

        # Validate name & URL
        if not name:
            issues.append("Shortcut is missing required 'name'.")
        elif len(name) > 20:
            w_msg = f"Shortcut '{name}' exceeds recommended 20 chars; may truncate on mobile."
            warnings.append(w_msg)
            sc_warnings.append(w_msg)

        if not url:
            issues.append("Shortcut is missing required 'url'.")
        else:
            clean_url = url.split("?")[0].split("#")[0]
            clean_scope = resolved_scope.split("?")[0].split("#")[0]
            if clean_url.startswith("/") and not (clean_url.startswith(clean_scope) or (clean_url + "/").startswith(clean_scope)):
                w_msg = f"Shortcut '{name}' url '{url}' is outside manifest scope '{resolved_scope}'."
                warnings.append(w_msg)
                sc_warnings.append(w_msg)

        # Icon audits
        has_icons = len(icons) > 0
        icon_sizes: List[str] = []
        has_monochrome = False
        has_recommended_size = False

        for ic in icons:
            sz = ic.sizes if isinstance(ic, IconSpec) else ic.get("sizes", "")
            purp = ic.purpose if isinstance(ic, IconSpec) else ic.get("purpose", "")
            icon_sizes.append(sz)
            if "monochrome" in purp:
                has_monochrome = True
            if sz in ("96x96", "192x192"):
                has_recommended_size = True

        if not has_icons:
            issues.append(f"Shortcut '{name}' has no icons. At least one icon (96x96 or 192x192) is recommended.")
            sc_warnings.append(f"No icons defined for shortcut '{name}'.")
            all_android_ready = False
            all_windows_ready = False
        else:
            if not has_recommended_size:
                w_msg = f"Shortcut '{name}' lacks recommended 96x96 or 192x192 icon."
                warnings.append(w_msg)
                sc_warnings.append(w_msg)
            if not has_monochrome:
                all_windows_ready = False

        # Generate sample action event listener handler
        action_key = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower())
        sample_handler = f"""// Action handler for shortcut: {name}
case {json.dumps(url)}:
  console.info('[Shortcut] Dispatched {name} ({url})');
  // Trigger custom UI action or navigation
  if (typeof window.onShortcutAction === 'function') {{
    window.onShortcutAction({json.dumps(action_key)}, {json.dumps(url)});
  }}
  break;"""
        route_cases.append(sample_handler)

        results.append(ShortcutSimulatorResult(
            name=name,
            url=url,
            short_name=short_name,
            has_icons=has_icons,
            icon_sizes=icon_sizes,
            has_monochrome_icon=has_monochrome,
            is_valid=len(issues) == 0,
            issues=issues,
            warnings=sc_warnings,
            sample_event_handler=sample_handler,
        ))

    # Build comprehensive client-side deep link router script
    joined_cases = "\n".join(route_cases)
    client_router = f"""// PWA App Shortcuts Client Router & Deep Link Dispatcher
(function() {{
  function routeShortcutUrl(targetUrl) {{
    const url = new URL(targetUrl, window.location.origin);
    const pathAndSearch = url.pathname + url.search;
    
    switch (pathAndSearch) {{
{joined_cases}
      default:
        console.debug('[Shortcut] Unhandled launch URL:', pathAndSearch);
    }}
  }}

  // 1. Launch Queue API (Chrome 98+ Desktop / Android PWA)
  if ('launchQueue' in window && 'setConsumer' in window.launchQueue) {{
    window.launchQueue.setConsumer((launchParams) => {{
      if (launchParams.targetURL) {{
        routeShortcutUrl(launchParams.targetURL);
      }}
    }});
  }}

  // 2. Standard page load deep link detection fallback
  window.addEventListener('DOMContentLoaded', () => {{
    routeShortcutUrl(window.location.href);
  }});
}})();"""

    return ShortcutSuiteReport(
        shortcuts=results,
        total_count=len(results),
        android_ready=all_android_ready and len(results) > 0,
        windows_ready=all_windows_ready and len(results) > 0,
        warnings=warnings,
        client_router_js=client_router,
    )
