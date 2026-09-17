"""
PWA Manifest Linter and Installability Auditor.

Validates Web App Manifest configurations against W3C standards, Lighthouse PWA audits,
Chromium/Android installability criteria, and Apple iOS PWA requirements.
100% Python Standard Library.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .models import (
    PWAManifestConfig,
    PWAValidationIssue,
    PWAValidationReport,
    DisplayMode,
    Orientation,
    IconSpec
)
from .manifest_generator import generate_html_meta_tags
from .compat import read_json_safe, normalize_path


# Standard W3C Web App Manifest valid categories
VALID_CATEGORIES: Set[str] = {
    "books", "business", "education", "entertainment", "finance", "fitness",
    "food", "games", "government", "health", "kids", "lifestyle", "magazines",
    "medical", "music", "navigation", "news", "personalization", "photo",
    "productivity", "security", "shopping", "social", "sports", "travel", "utilities", "weather"
}

# Standard W3C Valid Orientations
VALID_ORIENTATIONS: Set[str] = {
    "any", "natural", "landscape", "portrait",
    "portrait-primary", "portrait-secondary",
    "landscape-primary", "landscape-secondary"
}

# Hex and basic CSS color patterns
HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
RGB_COLOR_RE = re.compile(r"^rgba?\s*\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[\d.]+\s*)?\)$", re.IGNORECASE)
HSL_COLOR_RE = re.compile(r"^hsla?\s*\(\s*\d+\s*,\s*[\d.]+%?\s*,\s*[\d.]+%?\s*(?:,\s*[\d.]+\s*)?\)$", re.IGNORECASE)
NAMED_COLORS: Set[str] = {
    "transparent", "black", "white", "red", "green", "blue", "yellow", "orange",
    "purple", "gray", "grey", "silver", "maroon", "navy", "teal", "aqua", "lime", "fuchsia"
}


def is_valid_color(color_str: Optional[str]) -> bool:
    """Checks if a string is a valid CSS color format."""
    if not color_str or not isinstance(color_str, str):
        return False
    clean = color_str.strip()
    if HEX_COLOR_RE.match(clean) or RGB_COLOR_RE.match(clean) or HSL_COLOR_RE.match(clean):
        return True
    return clean.lower() in NAMED_COLORS


def _is_url_within_scope(url: str, scope: str) -> bool:
    """Checks if a start_url falls within the designated scope."""
    # Strip query params / hash fragments for check
    clean_url = url.split("?")[0].split("#")[0]
    clean_scope = scope.split("?")[0].split("#")[0]
    
    # Handle absolute vs relative paths
    if clean_scope.endswith("/") and not clean_url.endswith("/"):
        clean_url_dir = clean_url + "/"
    else:
        clean_url_dir = clean_url
        
    return clean_url.startswith(clean_scope) or clean_url_dir.startswith(clean_scope)


def validate_manifest(
    config_or_dict: Union[PWAManifestConfig, Dict[str, Any]]
) -> PWAValidationReport:
    """
    Performs comprehensive linting and validation on a Web App Manifest.
    Audits installability criteria, security, icons, routing scope, colors, and rich PWA features.
    Computes an Installability Score (0 - 100).
    """
    if isinstance(config_or_dict, PWAManifestConfig):
        cfg = config_or_dict
        raw = config_or_dict.to_dict()
    else:
        raw = config_or_dict
        cfg = PWAManifestConfig.from_dict(raw)

    issues: List[PWAValidationIssue] = []
    warnings: List[PWAValidationIssue] = []
    passed_checks: List[str] = []

    score = 100

    # 1. Identity Check
    name = raw.get("name")
    short_name = raw.get("short_name")

    if not name and not short_name:
        issues.append(PWAValidationIssue(
            severity="error",
            code="ERR_NAME_MISSING",
            message="Manifest must have at least 'name' or 'short_name'.",
            field="name",
            fix_suggestion="Provide a clear, human-readable name for your application."
        ))
        score -= 25
    else:
        if name:
            passed_checks.append("App 'name' is defined.")
            if len(name) > 45:
                warnings.append(PWAValidationIssue(
                    severity="warning",
                    code="WARN_NAME_LENGTH",
                    message=f"App name is {len(name)} chars long; recommended max is 45 characters.",
                    field="name",
                    fix_suggestion="Keep app name concise to avoid truncation on mobile home screens."
                ))
                score -= 3
        if short_name:
            passed_checks.append("App 'short_name' is defined.")
            if len(short_name) > 12:
                warnings.append(PWAValidationIssue(
                    severity="warning",
                    code="WARN_SHORT_NAME_LENGTH",
                    message=f"short_name '{short_name}' is {len(short_name)} chars long; recommended max is 12 characters.",
                    field="short_name",
                    fix_suggestion="Shorten 'short_name' to 12 characters or fewer for clean icon labels."
                ))
                score -= 2
        else:
            warnings.append(PWAValidationIssue(
                severity="warning",
                code="WARN_SHORT_NAME_MISSING",
                message="Manifest is missing 'short_name'; mobile home screens may truncate the full name.",
                field="short_name",
                fix_suggestion="Add a 'short_name' with 12 or fewer characters."
            ))
            score -= 5

    # 2. Navigation & Scope
    start_url = raw.get("start_url")
    scope = raw.get("scope", "/")

    if not start_url:
        issues.append(PWAValidationIssue(
            severity="error",
            code="ERR_START_URL_MISSING",
            message="Manifest must contain a valid 'start_url'.",
            field="start_url",
            fix_suggestion="Set 'start_url' to '/' or your app's main landing route."
        ))
        score -= 20
    else:
        passed_checks.append("Valid 'start_url' configured.")
        # Check start_url inside scope
        if scope and not _is_url_within_scope(start_url, scope):
            issues.append(PWAValidationIssue(
                severity="error",
                code="ERR_START_URL_OUTSIDE_SCOPE",
                message=f"start_url '{start_url}' is outside designated scope '{scope}'.",
                field="start_url",
                fix_suggestion="Adjust 'scope' or 'start_url' so start_url is inside scope."
            ))
            score -= 15
        else:
            passed_checks.append("start_url is within scope.")

        # Check HTTPS requirement (warning if http:// on non-localhost)
        if start_url.startswith("http://") and not any(h in start_url for h in ["localhost", "127.0.0.1", "0.0.0.0"]):
            warnings.append(PWAValidationIssue(
                severity="warning",
                code="WARN_INSECURE_HTTP",
                message="PWAs require HTTPS in production environments for installation.",
                field="start_url",
                fix_suggestion="Serve your PWA over HTTPS."
            ))
            score -= 5

    # 3. Display Mode Check
    display = str(raw.get("display", "standalone")).lower()
    valid_displays = {"standalone", "fullscreen", "minimal-ui", "browser"}
    if display not in valid_displays:
        issues.append(PWAValidationIssue(
            severity="error",
            code="ERR_INVALID_DISPLAY",
            message=f"Display mode '{display}' is not a recognized W3C display mode.",
            field="display",
            fix_suggestion="Use 'standalone', 'fullscreen', or 'minimal-ui'."
        ))
        score -= 15
    elif display == "browser":
        warnings.append(PWAValidationIssue(
            severity="warning",
            code="WARN_DISPLAY_BROWSER",
            message="Display mode 'browser' disables standalone PWA app-window experience.",
            field="display",
            fix_suggestion="Change 'display' to 'standalone' for full app experience."
        ))
        score -= 10
    else:
        passed_checks.append(f"Installable display mode '{display}' configured.")

    # 4. Orientation Check
    orientation = raw.get("orientation")
    if orientation:
        if str(orientation).lower() not in VALID_ORIENTATIONS:
            warnings.append(PWAValidationIssue(
                severity="warning",
                code="WARN_INVALID_ORIENTATION",
                message=f"Orientation '{orientation}' is not a standard W3C orientation value.",
                field="orientation",
                fix_suggestion=f"Choose from: {', '.join(sorted(VALID_ORIENTATIONS))}."
            ))
            score -= 3
        else:
            passed_checks.append(f"Valid orientation '{orientation}' set.")

    # 5. Color Validation
    theme_color = raw.get("theme_color")
    background_color = raw.get("background_color")

    if not theme_color:
        warnings.append(PWAValidationIssue(
            severity="warning",
            code="WARN_THEME_COLOR_MISSING",
            message="'theme_color' is missing; browser toolbar colors won't match app branding.",
            field="theme_color",
            fix_suggestion="Add 'theme_color' with a valid hex code (e.g., '#1a73e8')."
        ))
        score -= 5
    elif not is_valid_color(theme_color):
        issues.append(PWAValidationIssue(
            severity="error",
            code="ERR_INVALID_THEME_COLOR",
            message=f"theme_color '{theme_color}' is not a valid CSS color.",
            field="theme_color",
            fix_suggestion="Provide a valid hex color code (e.g., '#1a73e8')."
        ))
        score -= 5
    else:
        passed_checks.append("Valid 'theme_color' configured.")

    if not background_color:
        warnings.append(PWAValidationIssue(
            severity="warning",
            code="WARN_BACKGROUND_COLOR_MISSING",
            message="'background_color' is missing; splash screen will default to white.",
            field="background_color",
            fix_suggestion="Add 'background_color' to customize the app launch splash screen."
        ))
        score -= 3
    elif not is_valid_color(background_color):
        issues.append(PWAValidationIssue(
            severity="error",
            code="ERR_INVALID_BACKGROUND_COLOR",
            message=f"background_color '{background_color}' is not a valid CSS color.",
            field="background_color",
            fix_suggestion="Provide a valid hex color code (e.g., '#ffffff')."
        ))
        score -= 3
    else:
        passed_checks.append("Valid 'background_color' configured.")

    # 6. Icons Audit (Lighthouse & Chromium PWA Installability criteria)
    icons = raw.get("icons", [])
    if not icons or not isinstance(icons, list):
        issues.append(PWAValidationIssue(
            severity="error",
            code="ERR_NO_ICONS",
            message="Manifest must contain at least one icon for PWA installability.",
            field="icons",
            fix_suggestion="Add icons array including 192x192 and 512x512 icons."
        ))
        score -= 30
    else:
        has_192 = False
        has_512 = False
        has_maskable = False

        for icon in icons:
            if not isinstance(icon, dict):
                continue
            sizes = str(icon.get("sizes", ""))
            purpose = str(icon.get("purpose", "any")).lower()
            src = str(icon.get("src", ""))

            if not src:
                issues.append(PWAValidationIssue(
                    severity="error",
                    code="ERR_ICON_SRC_EMPTY",
                    message="Icon entry has an empty 'src'.",
                    field="icons",
                    fix_suggestion="Specify a valid path or URL for each icon."
                ))

            if "192x192" in sizes or sizes == "any":
                has_192 = True
            if "512x512" in sizes or sizes == "any":
                has_512 = True
            if "maskable" in purpose:
                has_maskable = True

        if has_192:
            passed_checks.append("Contains 192x192 (or vector) app icon.")
        else:
            issues.append(PWAValidationIssue(
                severity="error",
                code="ERR_MISSING_192_ICON",
                message="PWA installability requires at least one 192x192 icon.",
                field="icons",
                fix_suggestion="Add a 192x192 icon with 'sizes': '192x192'."
            ))
            score -= 15

        if has_512:
            passed_checks.append("Contains 512x512 (or vector) app icon.")
        else:
            issues.append(PWAValidationIssue(
                severity="error",
                code="ERR_MISSING_512_ICON",
                message="PWA installability requires at least one 512x512 icon for splash screens.",
                field="icons",
                fix_suggestion="Add a 512x512 icon with 'sizes': '512x512'."
            ))
            score -= 15

        if has_maskable:
            passed_checks.append("Contains maskable icon for Android adaptive shapes.")
        else:
            warnings.append(PWAValidationIssue(
                severity="warning",
                code="WARN_NO_MASKABLE_ICON",
                message="No maskable icon specified; app icon may display inside a white border on Android.",
                field="icons",
                fix_suggestion="Add an icon with 'purpose': 'maskable' and safe zone geometry."
            ))
            score -= 8

    # 7. Rich Discovery & UX Enhancements
    if raw.get("description"):
        passed_checks.append("App description is provided.")
    else:
        warnings.append(PWAValidationIssue(
            severity="info",
            code="INFO_DESCRIPTION_MISSING",
            message="Adding an app description enhances install dialogs and app store discovery.",
            field="description",
            fix_suggestion="Add a 1-2 sentence description of your app."
        ))
        score -= 2

    if raw.get("shortcuts"):
        from .shortcuts_simulator import simulate_app_shortcuts
        suite = simulate_app_shortcuts(raw)
        passed_checks.append(f"App defines {len(raw['shortcuts'])} shortcut actions (Android ready: {suite.android_ready}, Windows ready: {suite.windows_ready}).")
        if len(raw["shortcuts"]) > 4:
            warnings.append(PWAValidationIssue(
                severity="warning",
                code="SHORTCUTS_EXCEEDED",
                message=f"Configured {len(raw['shortcuts'])} shortcuts; Android and Windows taskbars generally display a maximum of 4.",
                field="shortcuts",
                fix_suggestion="Limit shortcuts to the 4 most frequent actions."
            ))
        for sc in suite.shortcuts:
            for issue in sc.issues:
                warnings.append(PWAValidationIssue(
                    severity="warning",
                    code="WARN_SHORTCUT_ISSUE",
                    message=f"Shortcut '{sc.name}': {issue}",
                    field="shortcuts",
                    fix_suggestion="Ensure shortcuts have valid URLs and appropriate 96x96/192x192 icons."
                ))
    else:
        warnings.append(PWAValidationIssue(
            severity="info",
            code="INFO_SHORTCUTS_RECOMMENDED",
            message="App shortcuts allow users to jump straight into key features from app icon menu.",
            field="shortcuts",
            fix_suggestion="Add 'shortcuts' for quick actions."
        ))
        score -= 2

    # Protocol Handlers Audit
    if raw.get("protocol_handlers"):
        from .shortcuts_simulator import validate_protocol_handlers
        p_report = validate_protocol_handlers(raw)
        if p_report.errors:
            for p_err in p_report.errors:
                issues.append(PWAValidationIssue(
                    severity="error",
                    code="PROTOCOL_HANDLER_INVALID",
                    message=p_err,
                    field="protocol_handlers",
                    fix_suggestion="Use 'web+custom' or safelisted scheme (e.g. 'mailto', 'tel') and include '%s' in URL."
                ))
                score -= 5
        for p_warn in p_report.warnings:
            warnings.append(PWAValidationIssue(
                severity="warning",
                code="WARN_PROTOCOL_HANDLER",
                message=p_warn,
                field="protocol_handlers",
                fix_suggestion="Ensure protocol handler URL is within scope."
            ))
        if p_report.valid_count > 0:
            passed_checks.append(f"App defines {p_report.valid_count} valid URL protocol handler(s).")

    if raw.get("screenshots"):
        passed_checks.append(f"App provides {len(raw['screenshots'])} preview screenshots.")
    else:
        warnings.append(PWAValidationIssue(
            severity="info",
            code="INFO_SCREENSHOTS_RECOMMENDED",
            message="Screenshots enable rich desktop & mobile install sheets in modern browsers.",
            field="screenshots",
            fix_suggestion="Add desktop and mobile screenshots."
        ))
        score -= 2

    # Final scoring clamp & status
    final_score = max(0, min(100, score))
    has_critical_errors = any(i.severity == "error" for i in issues)
    is_valid = not has_critical_errors

    # Generate companion HTML meta tags
    meta_tags_html = generate_html_meta_tags(cfg)

    # Combine warnings and infos
    report_warnings = warnings + [i for i in issues if i.severity == "warning"]
    report_errors = [i for i in issues if i.severity == "error"]

    return PWAValidationReport(
        is_valid=is_valid,
        installable_score=final_score,
        issues=report_errors,
        warnings=report_warnings,
        passed_checks=passed_checks,
        meta_tags_html=meta_tags_html
    )


def lint_manifest_file(file_path: Union[str, Path]) -> PWAValidationReport:
    """
    Reads a manifest JSON / webmanifest file from disk and returns a full validation report.
    """
    p = normalize_path(file_path)
    if not p.is_file():
        err = PWAValidationIssue(
            severity="error",
            code="ERR_FILE_NOT_FOUND",
            message=f"Manifest file not found: '{p}'",
            field="file",
            fix_suggestion="Ensure path points to an existing webmanifest or json file."
        )
        return PWAValidationReport(
            is_valid=False,
            installable_score=0,
            issues=[err],
            warnings=[],
            passed_checks=[],
            meta_tags_html=""
        )

    data = read_json_safe(p)
    if data is None or not isinstance(data, dict):
        err = PWAValidationIssue(
            severity="error",
            code="ERR_INVALID_JSON",
            message=f"Failed to parse valid JSON from '{p}'",
            field="file",
            fix_suggestion="Check file for syntax errors or invalid JSON structure."
        )
        return PWAValidationReport(
            is_valid=False,
            installable_score=0,
            issues=[err],
            warnings=[],
            passed_checks=[],
            meta_tags_html=""
        )

    return validate_manifest(data)
