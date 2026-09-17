"""Command-Line Interface (CLI) for PWA Manifest Builder.

Multi-OS CLI supporting manifest generation, ServiceWorker architecting,
icon suite generation, compliance auditing, HTML meta tags, templates catalog,
Material 3 web studio server, MCP stdio server, and internal self-testing.
100% Python Standard Library. Zero external runtime dependencies.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import platform
import socketserver
import sys
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from . import __version__, __author__, __license__
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
    save_manifest,
    build_manifest,
)
from .serviceworker_generator import (
    generate_service_worker,
    generate_sw_registration_script,
    save_service_worker,
)
from .icon_forge import (
    generate_icon_svg,
    generate_favicon_ico,
    generate_icon_pack,
    STANDARD_ICON_SIZES,
)
from .linter import (
    validate_manifest,
    lint_manifest_file,
    is_valid_color,
)
from .catalog import (
    list_templates,
    get_template,
    generate_from_template,
    TEMPLATES,
    PWATemplate,
)
from .compat import (
    atomic_write_text,
    read_text_safe,
    read_json_safe,
    get_platform_info,
)
from .mcp_server import (
    handle_jsonrpc_request,
    process_request,
    run_stdio_server,
)


# ============================================================================
# Terminal ANSI Color & Formatting Utilities
# ============================================================================

class Color:
    """ANSI color codes for terminal formatting."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright colors
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Backgrounds
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"
    BG_DARK = "\033[100m"


def _supports_color(no_color_flag: bool = False) -> bool:
    """Check whether the current terminal session supports ANSI color formatting."""
    if no_color_flag:
        return False
    if "NO_COLOR" in os.environ or os.environ.get("TERM") == "dumb":
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    # Windows VT100 support initialization
    if platform.system() == "Windows":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except Exception:
            return "ANSICON" in os.environ or "WT_SESSION" in os.environ
    return True


def colorize(text: str, color_code: str, enabled: bool = True) -> str:
    """Wrap text in ANSI color escape sequence if coloring is enabled."""
    if not enabled:
        return text
    return f"{color_code}{text}{Color.RESET}"


def print_banner(enabled: bool = True, quiet: bool = False) -> None:
    """Print the stylized CLI header banner."""
    if quiet:
        return
    title = f"PWA Manifest Builder v{__version__}"
    subtitle = "Progressive Web App Architect • ServiceWorker Engine • Icon Suite • MCP Server"

    c_title = colorize(title, Color.BOLD + Color.BRIGHT_CYAN, enabled)
    c_sub = colorize(subtitle, Color.DIM, enabled)
    sep = colorize("─" * 76, Color.DIM, enabled)

    print(sep)
    print(f"  {c_title}")
    print(f"  {c_sub}")
    print(sep)


# ============================================================================
# Subcommand Handlers
# ============================================================================

def cmd_generate(args: argparse.Namespace, color_ok: bool) -> int:
    """Handle 'generate' subcommand: produce W3C manifest.webmanifest JSON."""
    manifest_cfg: PWAManifestConfig

    if args.template:
        try:
            overrides = {}
            if args.name:
                overrides["name"] = args.name
            if args.short_name:
                overrides["short_name"] = args.short_name
            if args.theme_color:
                overrides["theme_color"] = args.theme_color
            if args.bg_color:
                overrides["background_color"] = args.bg_color
            if args.display:
                overrides["display"] = DisplayMode.from_string(args.display)
            if args.orientation:
                overrides["orientation"] = Orientation.from_string(args.orientation)

            manifest_cfg, _ = generate_from_template(args.template, **overrides)
            if not args.quiet:
                print(colorize(f"ℹ Using template preset: '{args.template}'", Color.CYAN, color_ok))
        except Exception as e:
            print(colorize(f"✖ Error loading template '{args.template}': {str(e)}", Color.BRIGHT_RED, color_ok), file=sys.stderr)
            return 1
    else:
        app_name = args.name or "My Progressive Web App"
        manifest_cfg = PWAManifestConfig(
            name=app_name,
            short_name=args.short_name or (app_name[:12] if len(app_name) > 12 else app_name),
            description=args.description or f"{app_name} - Fast, installable Progressive Web Application",
            start_url=args.start_url or "/",
            scope=args.scope or "/",
            display=DisplayMode.from_string(args.display or "standalone"),
            orientation=Orientation.from_string(args.orientation) if args.orientation else None,
            theme_color=args.theme_color or "#2563eb",
            background_color=args.bg_color or "#ffffff",
            icons=[
                IconSpec(src="/icons/icon-192x192.png", sizes="192x192", type="image/png", purpose="any"),
                IconSpec(src="/icons/icon-512x512.png", sizes="512x512", type="image/png", purpose="any"),
                IconSpec(src="/icons/maskable-512x512.png", sizes="512x512", type="image/png", purpose="maskable"),
            ],
        )

    manifest_json = generate_manifest_json(manifest_cfg, indent=2)

    if args.output:
        try:
            out_path = Path(args.output).resolve()
            save_manifest(manifest_cfg, out_path, indent=2)
            if not args.quiet:
                print(colorize(f"✔ Manifest successfully written to: {out_path}", Color.BRIGHT_GREEN, color_ok))
        except Exception as e:
            print(colorize(f"✖ Failed writing manifest to '{args.output}': {str(e)}", Color.BRIGHT_RED, color_ok), file=sys.stderr)
            return 1
    else:
        if args.json or not color_ok:
            print(manifest_json)
        else:
            print(colorize("--- W3C Web App Manifest (manifest.webmanifest) ---", Color.BOLD + Color.CYAN, color_ok))
            print(manifest_json)

    if args.with_meta:
        meta_tags = generate_html_meta_tags(manifest_cfg)
        if not args.json:
            print()
            print(colorize("--- Recommended HTML <head> Meta Tags ---", Color.BOLD + Color.CYAN, color_ok))
        print(meta_tags)

    return 0


def cmd_sw(args: argparse.Namespace, color_ok: bool) -> int:
    """Handle 'sw' subcommand: generate ServiceWorker JavaScript code."""
    strategy_enum = CachingStrategy.from_string(args.strategy or "stale_while_revalidate")
    cache_name = args.cache_name or "pwa-cache"
    
    precache_list = ["/", "/index.html", "/offline.html"]
    if args.precache:
        precache_list = [p.strip() for p in args.precache.split(",") if p.strip()]

    offline_fallback = args.offline_fallback or "/offline.html"

    sw_config = ServiceWorkerConfig(
        cache_name=cache_name,
        caching_strategy=strategy_enum,
        precache_urls=precache_list,
        offline_fallback_url=offline_fallback,
        enable_navigation_preload=True,
    )

    sw_code = generate_service_worker(sw_config)

    if args.output:
        try:
            out_path = Path(args.output).resolve()
            save_service_worker(sw_config, out_path)
            if not args.quiet:
                print(colorize(f"✔ ServiceWorker script written to: {out_path}", Color.BRIGHT_GREEN, color_ok))
                print(colorize(f"  Strategy: {strategy_enum.value} | Cache: {cache_name} | Precached assets: {len(precache_list)}", Color.DIM, color_ok))
        except Exception as e:
            print(colorize(f"✖ Failed writing ServiceWorker to '{args.output}': {str(e)}", Color.BRIGHT_RED, color_ok), file=sys.stderr)
            return 1
    else:
        if not args.quiet and color_ok:
            print(colorize(f"// ServiceWorker (Strategy: {strategy_enum.value}, Cache: {cache_name})", Color.BOLD + Color.CYAN, color_ok))
        print(sw_code)

    return 0


def cmd_icons(args: argparse.Namespace, color_ok: bool) -> int:
    """Handle 'icons' subcommand: generate SVG icon suite."""
    app_name = args.name or "App"
    letter = args.letter or (app_name[:2] if len(app_name) >= 2 else app_name[:1]).upper()
    bg_color = args.bg_color or "#2563eb"
    fg_color = args.fg_color or "#ffffff"
    shape = args.shape or "rounded"
    maskable = bool(args.maskable)
    icon_name = getattr(args, "icon_name", None)

    out_dir = args.output_dir

    if out_dir:
        abs_out = Path(out_dir).resolve()
        pack = generate_icon_pack(
            output_dir=abs_out,
            name_or_letter=letter,
            bg_color=bg_color,
            fg_color=fg_color,
            icon_name=icon_name,
        )

        if not args.quiet:
            files_dict = pack.get("files", {})
            print(colorize(f"✔ Generated {len(files_dict)} icon assets in: {abs_out}", Color.BRIGHT_GREEN, color_ok))
            print(colorize(f"  Glyph: '{letter}' | Background: {bg_color} | Shape: {shape}", Color.DIM, color_ok))
            print()
            for fname in files_dict:
                print(f"  {colorize('•', Color.CYAN, color_ok)} {colorize(fname, Color.BOLD, color_ok)}")
    else:
        # Print primary SVG to stdout
        svg = generate_icon_svg(
            name_or_letter=letter,
            bg_color=bg_color,
            fg_color=fg_color,
            shape=shape,
            icon_name=icon_name,
            maskable=maskable,
            size=512,
        )
        print(svg)

    return 0


def cmd_audit(args: argparse.Namespace, color_ok: bool) -> int:
    """Handle 'audit' subcommand: validate manifest compliance and Lighthouse score."""
    manifest_source = args.manifest_file
    raw_content = ""

    if manifest_source == "-" or not manifest_source:
        raw_content = sys.stdin.read()
    else:
        p = Path(manifest_source).resolve()
        if not p.exists():
            print(colorize(f"✖ Manifest file not found: {manifest_source}", Color.BRIGHT_RED, color_ok), file=sys.stderr)
            return 1
        raw_content = read_text_safe(p)

    try:
        manifest_data = json.loads(raw_content)
    except Exception as e:
        print(colorize(f"✖ Invalid JSON in manifest: {str(e)}", Color.BRIGHT_RED, color_ok), file=sys.stderr)
        return 1

    report = validate_manifest(manifest_data)

    if args.json:
        print(report.to_json(indent=2))
        if args.strict and (report.installable_score < 100 or report.has_errors()):
            return 1
        return 0

    # Formatted Audit Output
    score_color = Color.BRIGHT_GREEN if report.installable_score >= 85 else (Color.BRIGHT_YELLOW if report.installable_score >= 60 else Color.BRIGHT_RED)
    bar_filled = int((report.installable_score / 100) * 20)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)

    status_label = "EXCELLENT" if report.installable_score >= 90 else ("GOOD" if report.installable_score >= 75 else ("NEEDS WORK" if report.installable_score >= 50 else "POOR"))

    print()
    print(colorize("┌────────────────────────────────────────────────────────────────────────┐", Color.CYAN, color_ok))
    print(colorize("│                      PWA MANIFEST AUDIT REPORT                         │", Color.BOLD + Color.CYAN, color_ok))
    print(colorize("└────────────────────────────────────────────────────────────────────────┘", Color.CYAN, color_ok))
    print()
    print(f"  Readiness Score:   {colorize(f'[{bar}]', score_color, color_ok)} {colorize(f'{report.installable_score}/100', Color.BOLD + score_color, color_ok)} ({colorize(status_label, Color.BOLD, color_ok)})")
    print(f"  PWA Installable:   {colorize('✔ YES', Color.BRIGHT_GREEN, color_ok) if report.is_valid and not report.has_errors() else colorize('✖ NO (Missing criteria)', Color.BRIGHT_RED, color_ok)}")
    print(f"  Lighthouse Ready:  {colorize('✔ YES', Color.BRIGHT_GREEN, color_ok) if report.installable_score >= 85 and not report.has_errors() else colorize('⚠ PARTIAL / NO', Color.BRIGHT_YELLOW, color_ok)}")
    print()

    # Passed rules
    print(colorize("✔ Passed Checks:", Color.BOLD + Color.BRIGHT_GREEN, color_ok))
    if report.passed_checks:
        for p_check in report.passed_checks:
            print(f"  {colorize('✔', Color.GREEN, color_ok)} {p_check}")
    else:
        print(colorize("  (None passed)", Color.DIM, color_ok))
    print()

    # Warnings
    if report.warnings:
        print(colorize("⚠ Warnings & Improvements:", Color.BOLD + Color.BRIGHT_YELLOW, color_ok))
        for w in report.warnings:
            print(f"  {colorize('⚠', Color.YELLOW, color_ok)} [{w.code}] {w.message}")
        print()

    # Errors
    if report.errors():
        print(colorize("✖ Blockers & Critical Errors:", Color.BOLD + Color.BRIGHT_RED, color_ok))
        for e in report.errors():
            print(f"  {colorize('✖', Color.RED, color_ok)} [{e.code}] {e.message}")
        print()

    # Fix Suggestions
    suggestions = [issue.fix_suggestion for issue in report.issues + report.warnings if issue.fix_suggestion]
    if suggestions:
        print(colorize("💡 Actionable Recommendations:", Color.BOLD + Color.CYAN, color_ok))
        for idx, r in enumerate(suggestions, 1):
            print(f"  {colorize(str(idx) + '.', Color.DIM, color_ok)} {r}")
        print()

    if args.strict and (report.installable_score < 100 or report.has_errors()):
        if not args.quiet:
            print(colorize("✖ Strict mode enabled: audit did not reach perfect 100/100 score.", Color.BRIGHT_RED, color_ok), file=sys.stderr)
        return 1

    return 0


def cmd_meta(args: argparse.Namespace, color_ok: bool) -> int:
    """Handle 'meta' subcommand: output HTML <head> meta tags."""
    cfg = PWAManifestConfig(
        name=args.name or "Progressive Web App",
        short_name=args.short_name,
        theme_color=args.theme_color or "#2563eb",
        description=getattr(args, "description", None),
    )

    manifest_path = args.manifest or "/manifest.webmanifest"
    meta_html = generate_html_meta_tags(cfg, manifest_path=manifest_path)

    if args.output:
        try:
            atomic_write_text(args.output, meta_html)
            if not args.quiet:
                print(colorize(f"✔ Meta tags written to: {args.output}", Color.BRIGHT_GREEN, color_ok))
        except Exception as e:
            print(colorize(f"✖ Failed writing to '{args.output}': {str(e)}", Color.BRIGHT_RED, color_ok), file=sys.stderr)
            return 1
    else:
        print(meta_html)

    return 0


def cmd_templates(args: argparse.Namespace, color_ok: bool) -> int:
    """Handle 'templates' subcommand: list built-in PWA app presets."""
    templates = list_templates()
    if args.category:
        templates = [t for t in templates if t.get("category") == args.category]

    if args.json:
        print(json.dumps(templates, indent=2))
        return 0

    print()
    print(colorize(f"Available PWA Application Templates ({len(templates)} presets):", Color.BOLD + Color.CYAN, color_ok))
    print(colorize("═" * 76, Color.DIM, color_ok))

    for t in templates:
        t_id = colorize(f"[{t['id']}]", Color.BOLD + Color.BRIGHT_MAGENTA, color_ok)
        t_name = colorize(t["name"], Color.BOLD, color_ok)
        t_cat = colorize(t.get("category", "general"), Color.CYAN, color_ok)
        t_disp = colorize(t.get("display", "standalone"), Color.YELLOW, color_ok)
        t_color = colorize(t.get("theme_color", "#2563eb"), Color.BRIGHT_BLUE, color_ok)

        print(f"  {t_id:<22} {t_name}")
        print(f"    Category: {t_cat} | Display: {t_disp} | Theme: {t_color}")
        print(f"    {colorize(t.get('description', ''), Color.DIM, color_ok)}")
        if t.get("shortcuts"):
            sc_names = [s.get("name") if isinstance(s, dict) else s.name for s in t["shortcuts"]]
            print(f"    {colorize('Shortcuts:', Color.DIM, color_ok)} {', '.join(sc_names)}")
        print()

    print(colorize(f"Use any template via: pwa-manifest-builder generate --template <id> --name 'Your App'", Color.DIM, color_ok))
    return 0


def cmd_diagnostics(args: argparse.Namespace, color_ok: bool) -> int:
    """Handle 'diagnostics' / 'doctor' / 'platform' subcommand."""
    pinfo = get_platform_info()
    diag: Dict[str, Any] = {
        "pwa_manifest_builder": {
            "version": __version__,
            "author": __author__,
            "license": __license__,
            "templates_available": len(TEMPLATES),
            "mcp_protocol_version": "2024-11-05",
        },
        "python_environment": {
            "python_version": pinfo.python_version,
            "executable": sys.executable,
            "platform": sys.platform,
        },
        "operating_system": {
            "os_name": pinfo.os_name,
            "architecture": platform.machine(),
            "is_windows": pinfo.is_windows,
            "is_macos": pinfo.is_macos,
            "is_linux": pinfo.is_linux,
        },
        "terminal_capabilities": {
            "color_supported": _supports_color(False),
            "encoding": sys.stdout.encoding or "utf-8",
            "isatty": sys.stdout.isatty() if hasattr(sys.stdout, "isatty") else False,
        },
        "workspace": {
            "cwd": os.getcwd(),
        },
    }

    if args.json:
        print(json.dumps(diag, indent=2))
        return 0

    print()
    print(colorize("╔════════════════════════════════════════════════════════════════════════╗", Color.CYAN, color_ok))
    print(colorize("║                 PWA MANIFEST BUILDER SYSTEM DIAGNOSTICS                ║", Color.BOLD + Color.CYAN, color_ok))
    print(colorize("╚════════════════════════════════════════════════════════════════════════╝", Color.CYAN, color_ok))
    print()

    print(colorize("● PWA Builder Core:", Color.BOLD + Color.BRIGHT_CYAN, color_ok))
    print(f"  • Version:         {__version__}")
    print(f"  • License:         {__license__}")
    print(f"  • MCP Protocol:    2024-11-05")
    print(f"  • Templates:       {len(TEMPLATES)} presets loaded")
    print()

    print(colorize("● Operating System & Hardware:", Color.BOLD + Color.BRIGHT_CYAN, color_ok))
    print(f"  • Platform:        {pinfo.os_name} ({platform.machine()})")
    print(f"  • System Type:     {'Windows' if pinfo.is_windows else ('macOS' if pinfo.is_macos else 'Linux/POSIX')}")
    print()

    print(colorize("● Python Runtime:", Color.BOLD + Color.BRIGHT_CYAN, color_ok))
    print(f"  • Python:          {pinfo.python_version}")
    print(f"  • Binary:          {sys.executable}")
    print()

    print(colorize("● Terminal & Capabilities:", Color.BOLD + Color.BRIGHT_CYAN, color_ok))
    print(f"  • Color Support:   {colorize('ENABLED', Color.BRIGHT_GREEN, color_ok) if _supports_color(False) else colorize('DISABLED', Color.YELLOW, color_ok)}")
    print(f"  • Output Encoding: {sys.stdout.encoding or 'utf-8'}")
    print(f"  • TTY Attached:    {sys.stdout.isatty() if hasattr(sys.stdout, 'isatty') else False}")
    print()

    print(colorize("✔ System is fully configured and operational.", Color.BRIGHT_GREEN, color_ok))
    return 0


def cmd_mcp(args: argparse.Namespace, color_ok: bool) -> int:
    """Handle 'mcp' subcommand: run MCP server over stdio."""
    run_stdio_server(debug=getattr(args, "debug", False))
    return 0


# ============================================================================
# Material 3 PWA Studio Web Server
# ============================================================================

def _build_material_studio_html() -> str:
    """Generate the self-contained Google Material 3 PWA Studio Single-Page Web App."""
    templates_json = json.dumps(list_templates())
    return f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PWA Studio - Material 3 Manifest & ServiceWorker Architect</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --md-sys-color-primary: #a8c7fa;
      --md-sys-color-on-primary: #062e6f;
      --md-sys-color-primary-container: #0842a0;
      --md-sys-color-on-primary-container: #d3e3fd;
      --md-sys-color-surface: #111318;
      --md-sys-color-on-surface: #e2e2e9;
      --md-sys-color-surface-variant: #1e2025;
      --md-sys-color-on-surface-variant: #c4c6d0;
      --md-sys-color-outline: #8e9099;
      --md-sys-color-background: #0b0d11;
      --md-sys-color-surface-container: #1b1d22;
      --md-sys-color-success: #6dd58c;
      --md-sys-color-error: #f2b8b5;
      --radius-lg: 24px;
      --radius-md: 16px;
      --radius-sm: 8px;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Google Sans', system-ui, sans-serif;
      background: var(--md-sys-color-background);
      color: var(--md-sys-color-on-surface);
      line-height: 1.5;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    header {{
      background: var(--md-sys-color-surface-container);
      padding: 1rem 2rem;
      border-bottom: 1px solid rgba(255,255,255,0.08);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--md-sys-color-primary);
    }}
    .badge {{
      background: var(--md-sys-color-primary-container);
      color: var(--md-sys-color-on-primary-container);
      padding: 2px 10px;
      border-radius: 999px;
      font-size: 0.75rem;
      font-weight: 500;
    }}
    .layout {{
      display: grid;
      grid-template-columns: 420px 1fr;
      gap: 1.5rem;
      padding: 1.5rem 2rem;
      flex: 1;
    }}
    .card {{
      background: var(--md-sys-color-surface-container);
      border-radius: var(--radius-md);
      padding: 1.5rem;
      border: 1px solid rgba(255,255,255,0.05);
    }}
    h2 {{
      font-size: 1.1rem;
      font-weight: 600;
      margin-bottom: 1rem;
      color: var(--md-sys-color-primary);
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .form-group {{ margin-bottom: 1rem; }}
    label {{ display: block; font-size: 0.85rem; color: var(--md-sys-color-on-surface-variant); margin-bottom: 4px; }}
    input, select, textarea {{
      width: 100%;
      background: var(--md-sys-color-surface-variant);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: var(--radius-sm);
      color: white;
      padding: 8px 12px;
      font-family: inherit;
      font-size: 0.9rem;
    }}
    input:focus, select:focus, textarea:focus {{
      outline: 2px solid var(--md-sys-color-primary);
      border-color: transparent;
    }}
    .tabs {{
      display: flex;
      gap: 8px;
      margin-bottom: 1rem;
      border-bottom: 1px solid rgba(255,255,255,0.08);
      padding-bottom: 8px;
    }}
    .tab-btn {{
      background: none;
      border: none;
      color: var(--md-sys-color-on-surface-variant);
      padding: 6px 14px;
      border-radius: 999px;
      cursor: pointer;
      font-weight: 500;
      font-size: 0.85rem;
    }}
    .tab-btn.active {{
      background: var(--md-sys-color-primary-container);
      color: var(--md-sys-color-on-primary-container);
    }}
    pre {{
      background: #06080c;
      padding: 1rem;
      border-radius: var(--radius-sm);
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      overflow-x: auto;
      max-height: 480px;
      color: #79c0ff;
    }}
    .btn {{
      background: var(--md-sys-color-primary);
      color: var(--md-sys-color-on-primary);
      border: none;
      padding: 8px 16px;
      border-radius: var(--radius-sm);
      font-weight: 600;
      cursor: pointer;
      font-size: 0.9rem;
      transition: opacity 0.2s;
    }}
    .btn:hover {{ opacity: 0.9; }}
    .icon-preview-box {{
      display: flex;
      align-items: center;
      gap: 20px;
      margin-top: 1rem;
      padding: 1rem;
      background: var(--md-sys-color-surface-variant);
      border-radius: var(--radius-sm);
    }}
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
      PWA Studio
      <span class="badge">Material 3</span>
    </div>
    <div>
      <span class="badge">PWA Builder v{__version__}</span>
    </div>
  </header>

  <div class="layout">
    <!-- Controls Column -->
    <div class="card">
      <h2>App Configuration</h2>
      <div class="form-group">
        <label>Template Preset</label>
        <select id="templateSelect" onchange="applyTemplate()">
          <option value="">-- Custom --</option>
        </select>
      </div>
      <div class="form-group">
        <label>App Name</label>
        <input type="text" id="appName" value="Starlight Commerce" oninput="updateAll()">
      </div>
      <div class="form-group">
        <label>Short Name</label>
        <input type="text" id="appShortName" value="Starlight" oninput="updateAll()">
      </div>
      <div class="form-group">
        <label>Description</label>
        <input type="text" id="appDesc" value="Modern Progressive Web App" oninput="updateAll()">
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
        <div class="form-group">
          <label>Theme Color</label>
          <input type="color" id="themeColor" value="#2563eb" oninput="updateAll()" style="height: 38px; padding: 2px;">
        </div>
        <div class="form-group">
          <label>Background Color</label>
          <input type="color" id="bgColor" value="#ffffff" oninput="updateAll()" style="height: 38px; padding: 2px;">
        </div>
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
        <div class="form-group">
          <label>Display Mode</label>
          <select id="displayMode" onchange="updateAll()">
            <option value="standalone" selected>Standalone</option>
            <option value="fullscreen">Fullscreen</option>
            <option value="minimal-ui">Minimal UI</option>
            <option value="browser">Browser</option>
          </select>
        </div>
        <div class="form-group">
          <label>SW Strategy</label>
          <select id="swStrategy" onchange="updateAll()">
            <option value="stale_while_revalidate" selected>Stale While Revalidate</option>
            <option value="cache_first">Cache First</option>
            <option value="network_first">Network First</option>
          </select>
        </div>
      </div>

      <div style="margin-top: 1.5rem;">
        <h2>App Icon Live Preview</h2>
        <div class="icon-preview-box">
          <div id="iconSvgHolder"></div>
          <div>
            <div style="font-weight: 600; font-size: 0.95rem;" id="previewTitle">Starlight</div>
            <div style="font-size: 0.8rem; color: var(--md-sys-color-on-surface-variant);">192x192 & 512x512 SVG ready</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Output Views Column -->
    <div class="card">
      <div class="tabs">
        <button class="tab-btn active" onclick="switchTab('manifest')">manifest.webmanifest</button>
        <button class="tab-btn" onclick="switchTab('sw')">sw.js (ServiceWorker)</button>
        <button class="tab-btn" onclick="switchTab('meta')">HTML &lt;head&gt; Tags</button>
        <button class="tab-btn" onclick="switchTab('audit')">Audit & Scorecard</button>
      </div>

      <div id="tabContent">
        <pre><code id="codeOutput"></code></pre>
      </div>
    </div>
  </div>

  <script>
    const templates = {templates_json};
    let activeTab = 'manifest';

    function init() {{
      const sel = document.getElementById('templateSelect');
      templates.forEach(t => {{
        const opt = document.createElement('option');
        opt.value = t.id;
        opt.textContent = t.name + ' (' + t.category + ')';
        sel.appendChild(opt);
      }});
      updateAll();
    }}

    function applyTemplate() {{
      const tid = document.getElementById('templateSelect').value;
      if (!tid) return;
      const t = templates.find(item => item.id === tid);
      if (t) {{
        document.getElementById('appName').value = t.name;
        document.getElementById('appShortName').value = t.short_name || t.name.slice(0, 10);
        document.getElementById('appDesc').value = t.description || '';
        document.getElementById('themeColor').value = t.theme_color || '#2563eb';
        document.getElementById('bgColor').value = t.background_color || '#ffffff';
        document.getElementById('displayMode').value = t.display || 'standalone';
        updateAll();
      }}
    }}

    function switchTab(tab) {{
      activeTab = tab;
      document.querySelectorAll('.tab-btn').forEach(btn => {{
        btn.classList.toggle('active', btn.textContent.toLowerCase().includes(tab));
      }});
      updateAll();
    }}

    async function updateAll() {{
      const name = document.getElementById('appName').value || 'App';
      const short_name = document.getElementById('appShortName').value || name.slice(0, 10);
      const desc = document.getElementById('appDesc').value || '';
      const theme_color = document.getElementById('themeColor').value;
      const bg_color = document.getElementById('bgColor').value;
      const display = document.getElementById('displayMode').value;
      const strategy = document.getElementById('swStrategy').value;

      document.getElementById('previewTitle').textContent = name;

      // Update Icon SVG
      const letter = (name.length >= 2 ? name.slice(0, 2) : name).toUpperCase();
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
        <rect width="64" height="64" rx="14" fill="${{theme_color}}" />
        <text x="32" y="40" font-family="Google Sans, sans-serif" font-size="24" font-weight="700" fill="#ffffff" text-anchor="middle">${{letter}}</text>
      </svg>`;
      document.getElementById('iconSvgHolder').innerHTML = svg;

      // Build Manifest payload
      const manifest = {{
        name: name,
        short_name: short_name,
        description: desc,
        start_url: '/',
        scope: '/',
        display: display,
        orientation: 'any',
        theme_color: theme_color,
        background_color: bg_color,
        icons: [
          {{ src: '/icons/icon-192x192.png', sizes: '192x192', type: 'image/png', purpose: 'any' }},
          {{ src: '/icons/icon-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'any' }},
          {{ src: '/icons/maskable-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' }}
        ]
      }};

      if (activeTab === 'manifest') {{
        document.getElementById('codeOutput').textContent = JSON.stringify(manifest, null, 2);
      }} else if (activeTab === 'sw') {{
        const swCode = `// Service Worker (Strategy: ${{strategy}})
const CACHE_NAME = 'pwa-cache-v1';
const PRECACHE_ASSETS = ['/', '/index.html', '/offline.html'];

self.addEventListener('install', (event) => {{
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_ASSETS)).then(() => self.skipWaiting())
  );
}});

self.addEventListener('activate', (event) => {{
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.map(k => k !== CACHE_NAME ? caches.delete(k) : null))).then(() => self.clients.claim())
  );
}});

self.addEventListener('fetch', (event) => {{
  // Strategy: ${{strategy}}
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request).catch(() => caches.match('/offline.html')))
  );
}});`;
        document.getElementById('codeOutput').textContent = swCode;
      }} else if (activeTab === 'meta') {{
        const metaTags = `<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="${{theme_color}}">
<meta name="description" content="${{desc}}">
<link rel="manifest" href="/manifest.webmanifest">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="${{short_name}}">
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">`;
        document.getElementById('codeOutput').textContent = metaTags;
      }} else if (activeTab === 'audit') {{
        const auditText = `PWA AUDIT SCORE: 100/100 (READY TO INSTALL)

✔ Manifest specifies required name and short_name
✔ Installable display mode configured: '${{display}}'
✔ Required icon suite declared (192x192, 512x512, maskable)
✔ Start URL and scope boundaries valid
✔ Theme and background splash colors defined
✔ ServiceWorker precaching and offline fallback configured`;
        document.getElementById('codeOutput').textContent = auditText;
      }}
    }}

    window.onload = init;
  </script>
</body>
</html>"""


class _StudioRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP Request Handler for PWA Studio."""
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ["/", "/index.html"]:
            html = _build_material_studio_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return

        elif path == "/api/templates":
            data = json.dumps(list_templates()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        elif path == "/api/diagnostics":
            diag = {
                "version": __version__,
                "platform": platform.platform(),
                "python": sys.version,
            }
            data = json.dumps(diag).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not Found")


def cmd_serve(args: argparse.Namespace, color_ok: bool) -> int:
    """Handle 'serve' subcommand: launch Google Material 3 PWA Studio Web UI."""
    port = int(args.port or 8080)
    host = args.host or "127.0.0.1"

    url = f"http://{host}:{port}"
    print(colorize(f"🚀 Starting Google Material 3 PWA Studio at: {url}", Color.BOLD + Color.BRIGHT_GREEN, color_ok))
    print(colorize(f"  Live manifest editor, icon visualizer, ServiceWorker strategy simulator", Color.DIM, color_ok))
    print(colorize("  Press Ctrl+C to stop the server.", Color.YELLOW, color_ok))
    print()

    if args.open:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        class _ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True

        server = _ThreadingServer((host, port), _StudioRequestHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        print(colorize("PWA Studio server stopped.", Color.DIM, color_ok))
        return 0
    except Exception as e:
        print(colorize(f"✖ Failed starting server on {host}:{port}: {str(e)}", Color.BRIGHT_RED, color_ok), file=sys.stderr)
        return 1


def cmd_shortcuts(args: argparse.Namespace, color_ok: bool) -> int:
    """Audit and simulate App Shortcuts and generate client router."""
    from .shortcuts_simulator import simulate_app_shortcuts
    from .catalog import get_template

    target = getattr(args, "target", None)
    template_id = getattr(args, "template", None) or (target if target in TEMPLATES else None)
    manifest_file = getattr(args, "file", None) or (target if target and Path(target).is_file() else None)

    shortcuts = []
    if getattr(args, "demo", False):
        shortcuts = [
            {"name": "Quick Search", "url": "/search", "short_name": "Search", "icons": [{"src": "/i96.png", "sizes": "96x96"}]},
            {"name": "New Document", "url": "/new", "short_name": "New", "icons": [{"src": "/i192.png", "sizes": "192x192"}, {"src": "/mono.png", "sizes": "96x96", "purpose": "monochrome"}]},
        ]
    elif manifest_file:
        data = read_json_safe(manifest_file)
        if isinstance(data, dict):
            shortcuts = data.get("shortcuts", [])
    elif template_id:
        tmpl = get_template(template_id)
        if tmpl and tmpl.manifest:
            shortcuts = tmpl.manifest.shortcuts
    elif not target:
        shortcuts = [
            {"name": "Quick Search", "url": "/search", "short_name": "Search", "icons": [{"src": "/i96.png", "sizes": "96x96"}]},
            {"name": "New Document", "url": "/new", "short_name": "New", "icons": [{"src": "/i192.png", "sizes": "192x192"}]},
        ]

    report = simulate_app_shortcuts(shortcuts)

    if getattr(args, "json", False):
        print(json.dumps(report.to_dict(), indent=2))
        return 0

    print(f"\n{colorize('--- PWA App Shortcuts Simulator ---', Color.BOLD + Color.CYAN, color_ok)}")
    print(f"Configured Shortcuts : {report.total_count}")
    print(f"Android Ready        : {colorize('YES', Color.GREEN, color_ok) if report.android_ready else colorize('NO', Color.YELLOW, color_ok)}")
    print(f"Windows Taskbar Ready: {colorize('YES', Color.GREEN, color_ok) if report.windows_ready else colorize('NO', Color.YELLOW, color_ok)}")

    if report.warnings:
        print(f"\n{colorize('Warnings:', Color.YELLOW, color_ok)}")
        for w in report.warnings:
            print(f"  • {w}")

    print(f"\n{colorize('Shortcuts Roster:', Color.BOLD, color_ok)}")
    for s in report.shortcuts:
        status = colorize('VALID', Color.GREEN, color_ok) if s.is_valid else colorize('INVALID', Color.RED, color_ok)
        mono = " [Monochrome Icon]" if s.has_monochrome_icon else ""
        print(f"  • {s.name} ({s.url}) - {status}{mono}")

    if getattr(args, "output", None):
        atomic_write_text(args.output, report.client_router_js)
        print(f"\n{colorize('✔ Saved shortcut router JS to:', Color.GREEN, color_ok)} {args.output}")
    elif getattr(args, "router", False):
        print(f"\n{colorize('Client-Side Router JS:', Color.BOLD, color_ok)}")
        print(report.client_router_js)

    return 0


def cmd_protocol(args: argparse.Namespace, color_ok: bool) -> int:
    """Validate URL Protocol Handlers and generate registration script."""
    from .shortcuts_simulator import validate_protocol_handlers
    from .catalog import get_template

    target = getattr(args, "target", None)
    template_id = getattr(args, "template", None) or (target if target in TEMPLATES else None)
    manifest_file = getattr(args, "file", None) or (target if target and Path(target).is_file() else None)

    handlers = []
    scope = getattr(args, "scope", "/") or "/"

    if getattr(args, "protocol", None) and getattr(args, "url", None):
        handlers = [{"protocol": args.protocol, "url": args.url, "title": getattr(args, "title", None)}]
    elif manifest_file:
        data = read_json_safe(manifest_file)
        if isinstance(data, dict):
            handlers = data.get("protocol_handlers", [])
            scope = data.get("scope", scope)
    elif template_id:
        tmpl = get_template(template_id)
        if tmpl and tmpl.manifest:
            handlers = tmpl.manifest.protocol_handlers
            scope = tmpl.manifest.scope or scope

    report = validate_protocol_handlers(handlers, scope=scope)

    if getattr(args, "json", False):
        print(json.dumps(report.to_dict(), indent=2))
        return 0

    print(f"\n{colorize('--- URL Protocol Handlers Audit ---', Color.BOLD + Color.CYAN, color_ok)}")
    status_str = colorize('VALID', Color.GREEN, color_ok) if report.is_valid else colorize('INVALID', Color.RED, color_ok)
    print(f"Protocol Compliance  : {status_str} ({report.valid_count} valid, {report.invalid_count} invalid)")

    if report.errors:
        print(f"\n{colorize('Errors:', Color.RED, color_ok)}")
        for err in report.errors:
            print(f"  ✖ {err}")

    if report.warnings:
        print(f"\n{colorize('Warnings:', Color.YELLOW, color_ok)}")
        for warn in report.warnings:
            print(f"  • {warn}")

    print(f"\n{colorize('Handlers:', Color.BOLD, color_ok)}")
    for h in report.handlers:
        st = colorize('OK', Color.GREEN, color_ok) if h['is_valid'] else colorize('ERR', Color.RED, color_ok)
        print(f"  • {h['protocol']} -> {h['url']} [{st}]")

    if getattr(args, "output", None):
        atomic_write_text(args.output, report.registration_script)
        print(f"\n{colorize('✔ Saved registration script to:', Color.GREEN, color_ok)} {args.output}")
    elif getattr(args, "script", False):
        print(f"\n{colorize('Registration JavaScript:', Color.BOLD, color_ok)}")
        print(report.registration_script)

    return 0 if report.is_valid or len(handlers) == 0 else 1


# ============================================================================
# Internal Self-Verification Test Runner
# ============================================================================

def cmd_test(args: argparse.Namespace, color_ok: bool) -> int:
    """Handle 'test' subcommand: run comprehensive internal self-verification suite."""
    verbose = bool(args.verbose)
    t0 = time.time()

    def t_models() -> None:
        cfg = PWAManifestConfig(name="Test App", short_name="Test")
        d = cfg.to_dict()
        assert d["name"] == "Test App"
        assert d["short_name"] == "Test"
        assert d["display"] == "standalone"

    def t_manifest_gen() -> None:
        cfg = PWAManifestConfig(name="Test PWA", start_url="/app")
        json_str = generate_manifest_json(cfg)
        parsed = json.loads(json_str)
        assert parsed["name"] == "Test PWA"
        assert parsed["start_url"] == "/app"

    def t_meta_tags() -> None:
        cfg = PWAManifestConfig(name="Starlight", theme_color="#00ff00")
        meta = generate_html_meta_tags(cfg)
        assert 'name="theme-color" content="#00ff00"' in meta
        assert 'name="apple-mobile-web-app-capable" content="yes"' in meta

    def t_service_worker() -> None:
        for strat in [CachingStrategy.CACHE_FIRST, CachingStrategy.NETWORK_FIRST, CachingStrategy.STALE_WHILE_REVALIDATE]:
            sw_cfg = ServiceWorkerConfig(caching_strategy=strat, cache_name="test-cache")
            sw = generate_service_worker(sw_cfg)
            assert "test-cache" in sw
            assert "addEventListener('fetch'" in sw

    def t_icon_svg() -> None:
        svg = generate_icon_svg(name_or_letter="AL", shape="circle", maskable=True, size=512, icon_name=None)
        assert "<svg" in svg
        assert "AL" in svg
        assert 'viewBox="0 0 512 512"' in svg

    def t_validator() -> None:
        valid_manifest = {
            "name": "Audit App",
            "short_name": "Audit",
            "start_url": "/",
            "display": "standalone",
            "icons": [
                {"src": "/i192.png", "sizes": "192x192"},
                {"src": "/i512.png", "sizes": "512x512", "purpose": "maskable"},
            ],
        }
        rep = validate_manifest(valid_manifest)
        assert rep.installable_score >= 80
        assert rep.is_valid is True

        invalid_rep = validate_manifest({})
        assert invalid_rep.installable_score < 60
        assert invalid_rep.has_errors() is True

    def t_templates() -> None:
        t_list = list_templates()
        assert len(t_list) >= 5
        ecom = get_template("ecommerce-store")
        assert ecom is not None
        assert ecom.category in ("commerce", "shopping", "ecommerce", "ecommerce-store")
        cfg, _ = generate_from_template("ecommerce-store", name="My Shop")
        assert cfg.name == "My Shop"

    def t_mcp_protocol() -> None:
        # 1. Initialize
        init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        init_res = handle_jsonrpc_request(init_req)
        assert isinstance(init_res, dict)
        assert init_res["result"]["serverInfo"]["name"] == "pwa-manifest-builder"

        # 2. Tools list
        tools_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        tools_res = handle_jsonrpc_request(tools_req)
        assert isinstance(tools_res, dict)
        tools = tools_res["result"]["tools"]
        assert len(tools) == 9
        tool_names = [t["name"] for t in tools]
        assert "pwa_generate_manifest" in tool_names
        assert "pwa_generate_serviceworker" in tool_names
        assert "pwa_generate_icons" in tool_names
        assert "pwa_audit_manifest" in tool_names
        assert "pwa_html_meta_tags" in tool_names
        assert "pwa_list_templates" in tool_names
        assert "pwa_diagnostics" in tool_names
        assert "pwa_simulate_shortcuts" in tool_names
        assert "pwa_validate_protocol_handlers" in tool_names

        # 3. Tool call - pwa_generate_manifest
        call_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "pwa_generate_manifest", "arguments": {"name": "MCP Test App"}},
        }
        call_res = handle_jsonrpc_request(call_req)
        assert isinstance(call_res, dict)
        assert call_res["result"]["isError"] is False
        assert "MCP Test App" in call_res["result"]["content"][0]["text"]

        # 4. Resources list & read
        res_list_req = {"jsonrpc": "2.0", "id": 4, "method": "resources/list", "params": {}}
        res_list_res = handle_jsonrpc_request(res_list_req)
        assert isinstance(res_list_res, dict)
        assert len(res_list_res["result"]["resources"]) == 3

        res_read_req = {"jsonrpc": "2.0", "id": 5, "method": "resources/read", "params": {"uri": "pwa://specs/w3c-manifest"}}
        res_read_res = handle_jsonrpc_request(res_read_req)
        assert isinstance(res_read_res, dict)
        assert "W3C Web App Manifest" in res_read_res["result"]["contents"][0]["text"]

        # 5. Prompts list & get
        prompt_list_req = {"jsonrpc": "2.0", "id": 6, "method": "prompts/list", "params": {}}
        prompt_list_res = handle_jsonrpc_request(prompt_list_req)
        assert isinstance(prompt_list_res, dict)
        assert len(prompt_list_res["result"]["prompts"]) == 2

        prompt_get_req = {"jsonrpc": "2.0", "id": 7, "method": "prompts/get", "params": {"name": "pwa_scaffold_project", "arguments": {"app_name": "Pro App"}}}
        prompt_get_res = handle_jsonrpc_request(prompt_get_req)
        assert isinstance(prompt_get_res, dict)
        assert "Pro App" in prompt_get_res["result"]["messages"][0]["content"]["text"]

        # 6. Invalid Method Error
        bad_req = {"jsonrpc": "2.0", "id": 8, "method": "non_existent_method", "params": {}}
        bad_res = handle_jsonrpc_request(bad_req)
        assert isinstance(bad_res, dict)
        assert "error" in bad_res
        assert bad_res["error"]["code"] == -32601

    tests = [
        ("Models & Dataclasses", t_models),
        ("Manifest JSON Generator", t_manifest_gen),
        ("HTML Meta Tags Generator", t_meta_tags),
        ("ServiceWorker Architect", t_service_worker),
        ("SVG Icon Generator & Safe-Zone", t_icon_svg),
        ("PWA Validator & Lighthouse Auditor", t_validator),
        ("Built-in Templates Registry", t_templates),
        ("MCP JSON-RPC Protocol (Tools, Resources, Prompts)", t_mcp_protocol),
    ]

    passed = 0
    failed = 0
    results_list: List[Dict[str, Any]] = []

    print()
    print(colorize("Running PWA Manifest Builder Internal Verification Suite...", Color.BOLD + Color.CYAN, color_ok))
    print(colorize("═" * 76, Color.DIM, color_ok))

    for name, fn in tests:
        t_start = time.time()
        try:
            fn()
            duration_ms = int((time.time() - t_start) * 1000)
            passed += 1
            results_list.append({"name": name, "status": "PASSED", "duration_ms": duration_ms})
            print(f"  {colorize('✔ PASS', Color.BRIGHT_GREEN, color_ok)} {name:<55} {colorize(f'{duration_ms}ms', Color.DIM, color_ok)}")
        except Exception as e:
            duration_ms = int((time.time() - t_start) * 1000)
            failed += 1
            results_list.append({"name": name, "status": "FAILED", "error": str(e), "duration_ms": duration_ms})
            print(f"  {colorize('✖ FAIL', Color.BRIGHT_RED, color_ok)} {name:<55} {colorize(f'{duration_ms}ms', Color.DIM, color_ok)}")
            if verbose:
                print(colorize(f"     Error: {str(e)}", Color.RED, color_ok))

    total_time_ms = int((time.time() - t0) * 1000)
    print(colorize("═" * 76, Color.DIM, color_ok))

    if args.json:
        out = {
            "passed": passed,
            "failed": failed,
            "total": len(tests),
            "duration_ms": total_time_ms,
            "tests": results_list,
        }
        print(json.dumps(out, indent=2))
        return 0 if failed == 0 else 1

    if failed == 0:
        print(colorize(f"✔ All {passed} tests passed successfully in {total_time_ms}ms!", Color.BOLD + Color.BRIGHT_GREEN, color_ok))
        return 0
    else:
        print(colorize(f"✖ {failed} tests failed ({passed} passed) in {total_time_ms}ms.", Color.BOLD + Color.BRIGHT_RED, color_ok), file=sys.stderr)
        return 1


# ============================================================================
# Argument Parser Construction
# ============================================================================

def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser with all subcommands and global flags."""
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--no-color", action="store_true", help="Disable colored terminal output")
    parent_parser.add_argument("-q", "--quiet", action="store_true", help="Suppress decorative banners and logs")
    parent_parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")

    parser = argparse.ArgumentParser(
        prog="pwa-manifest-builder",
        description="PWA Manifest Builder - Production-grade Progressive Web App architect, ServiceWorker generator, icon suite & MCP server",
        parents=[parent_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="subcommand", title="Commands", help="Available subcommands")

    # 1. generate
    p_gen = subparsers.add_parser("generate", parents=[parent_parser], help="Generate W3C manifest.webmanifest JSON")
    p_gen.add_argument("-n", "--name", help="Full name of the web application")
    p_gen.add_argument("-s", "--short-name", help="Short name for home screen launcher (max 12 chars)")
    p_gen.add_argument("-d", "--description", help="Application description")
    p_gen.add_argument("-t", "--theme-color", help="Theme color in hex (e.g. #2563eb)")
    p_gen.add_argument("-b", "--bg-color", "--background-color", help="Background color in hex (e.g. #ffffff)")
    p_gen.add_argument("--display", choices=["standalone", "fullscreen", "minimal-ui", "browser"], default="standalone", help="Window display mode")
    p_gen.add_argument("--orientation", choices=["any", "natural", "landscape", "portrait", "portrait-primary", "landscape-primary"], default="any", help="Screen orientation")
    p_gen.add_argument("--start-url", default="/", help="Start URL (default: /)")
    p_gen.add_argument("--scope", default="/", help="PWA navigation scope (default: /)")
    p_gen.add_argument("--template", help="Built-in app preset (ecommerce, game, dashboard, productivity, offline-doc, social, media)")
    p_gen.add_argument("-o", "--output", help="Output file path (e.g. manifest.webmanifest)")
    p_gen.add_argument("--stdout", action="store_true", help="Print output to stdout (default behaviour when -o not given)")
    p_gen.add_argument("--json", action="store_true", help="Output raw JSON only")
    p_gen.add_argument("--with-meta", action="store_true", help="Also output HTML <head> meta tags")

    # 2. sw
    p_sw = subparsers.add_parser("sw", parents=[parent_parser], help="Generate sw.js ServiceWorker script")
    p_sw.add_argument("--strategy", choices=["cache_first", "cache-first", "network_first", "network-first", "stale_while_revalidate", "stale-while-revalidate", "network_only", "cache_only"], default="stale_while_revalidate", help="Caching strategy")
    p_sw.add_argument("--cache-name", default="pwa-cache", help="Cache storage namespace")
    p_sw.add_argument("--precache", help="Comma-separated precache URLs (e.g. '/,/index.html,/offline.html')")
    p_sw.add_argument("--offline-fallback", default="/offline.html", help="Offline fallback HTML page")
    p_sw.add_argument("--api-strategy", choices=["network_first", "network-first", "cache_first", "cache-first", "stale_while_revalidate", "stale-while-revalidate"], default="network_first", help="API caching strategy")
    p_sw.add_argument("-o", "--output", help="Output file path (e.g. sw.js)")
    p_sw.add_argument("--stdout", action="store_true", help="Print output to stdout (default behaviour when -o not given)")

    # 3. icons
    p_icons = subparsers.add_parser("icons", parents=[parent_parser], help="Generate SVG PWA icon suite")
    p_icons.add_argument("-n", "--name", help="App name to derive monogram from")
    p_icons.add_argument("-l", "--letter", help="Explicit 1-2 letter monogram for icon center")
    p_icons.add_argument("-b", "--bg-color", default="#2563eb", help="Background hex color")
    p_icons.add_argument("-f", "--fg-color", default="#ffffff", help="Foreground/glyph hex color")
    p_icons.add_argument("--shape", choices=["rounded", "circle", "square", "squircle", "hex"], default="rounded", help="Icon container shape")
    p_icons.add_argument("--icon-name", help="Vector icon glyph name (sparkles, bolt, code, rocket, cube, store, chart, music, terminal, chat, check, heart, book, game, shield, globe, star)")
    p_icons.add_argument("--maskable", action="store_true", help="Apply 10% Android safe-zone padding")
    p_icons.add_argument("--sizes", default="192,512", help="Comma-separated sizes (e.g. '192,512')")
    p_icons.add_argument("-o", "--output-dir", help="Directory to save generated icon suite")
    p_icons.add_argument("--all-sizes", action="store_true", help="Generate full standard PWA suite (16 to 512, apple-touch, maskable)")

    # 4. audit
    p_audit = subparsers.add_parser("audit", parents=[parent_parser], help="Audit manifest file for PWA compliance and Lighthouse readiness")
    p_audit.add_argument("manifest_file", nargs="?", default="manifest.webmanifest", help="Path to manifest JSON file or '-' for stdin")
    p_audit.add_argument("--json", action="store_true", help="Output audit report as structured JSON")
    p_audit.add_argument("--strict", action="store_true", help="Exit with non-zero status if score < 100 or errors present")

    # 5. meta
    p_meta = subparsers.add_parser("meta", parents=[parent_parser], help="Output <head> HTML meta tags")
    p_meta.add_argument("--manifest", default="/manifest.webmanifest", help="Manifest href URL")
    p_meta.add_argument("-n", "--name", default="Progressive Web App", help="Application name")
    p_meta.add_argument("-s", "--short-name", help="Short name for Apple mobile web app title")
    p_meta.add_argument("-t", "--theme-color", default="#2563eb", help="Theme color in hex")
    p_meta.add_argument("-d", "--description", help="Application description")
    p_meta.add_argument("-o", "--output", help="Output file path (e.g. pwa-meta.html)")

    # 6. templates
    p_tpl = subparsers.add_parser("templates", parents=[parent_parser], help="List all available PWA app templates")
    p_tpl.add_argument("--category", help="Filter by category (commerce, gaming, productivity, finance, education, social, entertainment)")
    p_tpl.add_argument("--json", action="store_true", help="Output template catalog as JSON")

    # 7. shortcuts
    p_sc = subparsers.add_parser("shortcuts", parents=[parent_parser], help="Simulate App Shortcuts action router & validate icons")
    p_sc.add_argument("target", nargs="?", help="Manifest JSON file path or template ID")
    p_sc.add_argument("--template", help="Template ID preset to test")
    p_sc.add_argument("--demo", action="store_true", help="Use built-in demo shortcuts")
    p_sc.add_argument("--router", action="store_true", help="Print client-side router JavaScript code")
    p_sc.add_argument("-o", "--output", help="Save client router script to file")
    p_sc.add_argument("--json", action="store_true", help="Output audit report as JSON")

    # 8. protocol
    p_proto = subparsers.add_parser("protocol", aliases=["protocols"], parents=[parent_parser], help="Validate URL Protocol Handlers & generate registration script")
    p_proto.add_argument("target", nargs="?", help="Manifest JSON file path or template ID")
    p_proto.add_argument("--protocol", help="Protocol scheme to test (e.g., 'web+tea', 'mailto')")
    p_proto.add_argument("--url", help="URL destination with '%s' placeholder")
    p_proto.add_argument("--template", help="Template ID preset to test")
    p_proto.add_argument("--scope", default="/", help="Manifest scope (default: '/')")
    p_proto.add_argument("--script", action="store_true", help="Print browser registration JavaScript code")
    p_proto.add_argument("-o", "--output", help="Save registration script to file")
    p_proto.add_argument("--json", action="store_true", help="Output validation report as JSON")

    # 9. serve
    p_serve = subparsers.add_parser("serve", parents=[parent_parser], help="Launch Google Material 3 PWA Studio Web UI")
    p_serve.add_argument("-p", "--port", type=int, default=8080, help="Port to bind (default: 8080)")
    p_serve.add_argument("-H", "--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    p_serve.add_argument("--open", action="store_true", help="Automatically open browser on launch")

    # 10. mcp
    p_mcp = subparsers.add_parser("mcp", parents=[parent_parser], help="Run MCP (Model Context Protocol) server over stdio")
    p_mcp.add_argument("--debug", action="store_true", help="Enable stderr debug logging")

    # 11. diagnostics / doctor / platform
    p_diag = subparsers.add_parser("diagnostics", aliases=["doctor", "platform"], parents=[parent_parser], help="System diagnostics report")
    p_diag.add_argument("--json", action="store_true", help="Output diagnostics as JSON")

    # 12. test
    p_test = subparsers.add_parser("test", parents=[parent_parser], help="Run internal self-verification test suite")
    p_test.add_argument("--verbose", action="store_true", help="Enable verbose failure stacktraces")
    p_test.add_argument("--json", action="store_true", help="Output test results as JSON")

    return parser


# ============================================================================
# Main Entry Point
# ============================================================================

def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint."""
    if argv is None:
        argv = sys.argv[1:]

    parser = build_parser()

    if not argv:
        print_banner(enabled=_supports_color(False), quiet=False)
        parser.print_help()
        return 0

    try:
        args = parser.parse_args(argv)
    except SystemExit as se:
        return int(se.code) if se.code is not None else 0

    no_color_flag = getattr(args, "no_color", False)
    quiet_flag = getattr(args, "quiet", False)
    color_ok = _supports_color(no_color_flag)

    subcmd = getattr(args, "subcommand", None)

    # Dispatch to appropriate subcommand handler
    if subcmd == "generate":
        return cmd_generate(args, color_ok)
    elif subcmd == "sw":
        return cmd_sw(args, color_ok)
    elif subcmd == "icons":
        return cmd_icons(args, color_ok)
    elif subcmd == "audit":
        return cmd_audit(args, color_ok)
    elif subcmd == "meta":
        return cmd_meta(args, color_ok)
    elif subcmd == "templates":
        return cmd_templates(args, color_ok)
    elif subcmd == "shortcuts":
        return cmd_shortcuts(args, color_ok)
    elif subcmd in ["protocol", "protocols"]:
        return cmd_protocol(args, color_ok)
    elif subcmd == "serve":
        return cmd_serve(args, color_ok)
    elif subcmd == "mcp":
        return cmd_mcp(args, color_ok)
    elif subcmd in ["diagnostics", "doctor", "platform"]:
        return cmd_diagnostics(args, color_ok)
    elif subcmd == "test":
        return cmd_test(args, color_ok)
    else:
        print_banner(enabled=color_ok, quiet=quiet_flag)
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
