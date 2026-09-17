"""
Domain data models, Enums, and configurations for PWA Manifest Builder.

Defines typed dataclasses and enums representing W3C Web App Manifest specifications,
Service Worker synthesis options, and validation/linting audit results.
100% Python Standard Library.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class DisplayMode(str, Enum):
    """W3C Web App Manifest display mode options."""
    STANDALONE = "standalone"
    FULLSCREEN = "fullscreen"
    MINIMAL_UI = "minimal-ui"
    BROWSER = "browser"

    @classmethod
    def from_string(cls, val: Union[str, DisplayMode]) -> DisplayMode:
        if isinstance(val, cls):
            return val
        clean = str(val).strip().lower().replace("_", "-")
        for member in cls:
            if member.value == clean or member.name.lower() == clean:
                return member
        return cls.STANDALONE


class Orientation(str, Enum):
    """W3C Web App Manifest orientation values."""
    ANY = "any"
    NATURAL = "natural"
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"
    PORTRAIT_PRIMARY = "portrait-primary"
    PORTRAIT_SECONDARY = "portrait-secondary"
    LANDSCAPE_PRIMARY = "landscape-primary"
    LANDSCAPE_SECONDARY = "landscape-secondary"

    @classmethod
    def from_string(cls, val: Optional[Union[str, Orientation]]) -> Optional[Orientation]:
        if val is None:
            return None
        if isinstance(val, cls):
            return val
        clean = str(val).strip().lower().replace("_", "-")
        for member in cls:
            if member.value == clean or member.name.lower() == clean:
                return member
        return None


class CachingStrategy(str, Enum):
    """Service worker caching strategies for network and cache routing."""
    CACHE_FIRST = "CacheFirst"
    NETWORK_FIRST = "NetworkFirst"
    STALE_WHILE_REVALIDATE = "StaleWhileRevalidate"
    NETWORK_ONLY = "NetworkOnly"
    CACHE_ONLY = "CacheOnly"

    @classmethod
    def from_string(cls, val: Union[str, CachingStrategy]) -> CachingStrategy:
        if isinstance(val, cls):
            return val
        clean = str(val).strip().lower().replace("-", "").replace("_", "")
        for member in cls:
            if member.name.lower().replace("_", "") == clean or member.value.lower() == clean:
                return member
        return cls.NETWORK_FIRST


@dataclass
class IconSpec:
    """Specification for an icon asset in a Web App Manifest."""
    src: str
    sizes: str = "192x192"
    type: str = "image/png"
    purpose: str = "any"  # "any", "maskable", "monochrome", or space-separated "any maskable"
    density: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None

    def __post_init__(self):
        # Auto-extract width & height if sizes is 'WxH'
        if self.sizes and "x" in self.sizes and (self.width is None or self.height is None):
            parts = self.sizes.split("x")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                self.width = int(parts[0])
                self.height = int(parts[1])

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "src": self.src,
            "sizes": self.sizes,
            "type": self.type,
        }
        if self.purpose and self.purpose != "any":
            d["purpose"] = self.purpose
        elif self.purpose:
            d["purpose"] = self.purpose
        if self.density is not None:
            d["density"] = self.density
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> IconSpec:
        return cls(
            src=data.get("src", ""),
            sizes=data.get("sizes", "192x192"),
            type=data.get("type", "image/png"),
            purpose=data.get("purpose", "any"),
            density=data.get("density"),
            width=data.get("width"),
            height=data.get("height")
        )


@dataclass
class ShortcutSpec:
    """Specification for app shortcuts in the manifest."""
    name: str
    url: str
    short_name: Optional[str] = None
    description: Optional[str] = None
    icons: List[IconSpec] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "name": self.name,
            "url": self.url,
        }
        if self.short_name:
            d["short_name"] = self.short_name
        if self.description:
            d["description"] = self.description
        if self.icons:
            d["icons"] = [icon.to_dict() if isinstance(icon, IconSpec) else icon for icon in self.icons]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ShortcutSpec:
        raw_icons = data.get("icons", [])
        icons = [IconSpec.from_dict(i) if isinstance(i, dict) else i for i in raw_icons]
        return cls(
            name=data.get("name", ""),
            url=data.get("url", ""),
            short_name=data.get("short_name"),
            description=data.get("description"),
            icons=icons
        )


@dataclass
class ShareTargetSpec:
    """Specification for Web Share Target API in the manifest."""
    action: str
    method: str = "GET"
    enctype: str = "application/x-www-form-urlencoded"
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "method": self.method.upper(),
            "enctype": self.enctype,
            "params": self.params,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ShareTargetSpec:
        return cls(
            action=data.get("action", ""),
            method=data.get("method", "GET"),
            enctype=data.get("enctype", "application/x-www-form-urlencoded"),
            params=data.get("params", {}),
        )


@dataclass
class ProtocolHandlerSpec:
    """Specification for URL Protocol Handlers API in the manifest."""
    protocol: str
    url: str
    title: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "protocol": self.protocol,
            "url": self.url,
        }
        if self.title:
            d["title"] = self.title
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProtocolHandlerSpec:
        return cls(
            protocol=str(data.get("protocol", "")),
            url=str(data.get("url", "")),
            title=data.get("title"),
        )


@dataclass
class PWAManifestConfig:
    """Complete configuration model for W3C Web App Manifest."""
    name: str
    short_name: Optional[str] = None
    description: Optional[str] = None
    start_url: str = "/"
    scope: str = "/"
    display: Union[DisplayMode, str] = DisplayMode.STANDALONE
    orientation: Optional[Union[Orientation, str]] = None
    theme_color: str = "#000000"
    background_color: str = "#ffffff"
    lang: str = "en"
    dir: str = "auto"
    categories: List[str] = field(default_factory=list)
    icons: List[IconSpec] = field(default_factory=list)
    shortcuts: List[ShortcutSpec] = field(default_factory=list)
    screenshots: List[Dict[str, Any]] = field(default_factory=list)
    related_applications: List[Dict[str, Any]] = field(default_factory=list)
    prefer_related_applications: bool = False
    id: Optional[str] = None
    share_target: Optional[ShareTargetSpec] = None
    protocol_handlers: List[Dict[str, Any]] = field(default_factory=list)
    file_handlers: List[Dict[str, Any]] = field(default_factory=list)
    display_override: List[str] = field(default_factory=list)
    i18n: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.display, str):
            self.display = DisplayMode.from_string(self.display)
        if self.orientation is not None and isinstance(self.orientation, str):
            self.orientation = Orientation.from_string(self.orientation)
        if not self.short_name:
            self.short_name = self.name[:12] if len(self.name) > 12 else self.name
        if not self.id:
            self.id = self.start_url

    def add_icon(
        self,
        src: str,
        sizes: str = "192x192",
        type: str = "image/png",
        purpose: str = "any"
    ) -> IconSpec:
        """Helper to append an icon to the manifest configuration."""
        icon = IconSpec(src=src, sizes=sizes, type=type, purpose=purpose)
        self.icons.append(icon)
        return icon

    def add_shortcut(
        self,
        name: str,
        url: str,
        short_name: Optional[str] = None,
        description: Optional[str] = None,
        icons: Optional[List[IconSpec]] = None
    ) -> ShortcutSpec:
        """Helper to append a shortcut to the manifest configuration."""
        shortcut = ShortcutSpec(
            name=name,
            url=url,
            short_name=short_name,
            description=description,
            icons=icons or []
        )
        self.shortcuts.append(shortcut)
        return shortcut

    def to_dict(self) -> Dict[str, Any]:
        """Converts configuration to W3C-compliant manifest dictionary."""
        d: Dict[str, Any] = {
            "name": self.name,
            "short_name": self.short_name or self.name,
            "start_url": self.start_url,
            "scope": self.scope,
            "display": self.display.value if isinstance(self.display, DisplayMode) else str(self.display),
            "theme_color": self.theme_color,
            "background_color": self.background_color,
        }

        if self.id:
            d["id"] = self.id
        if self.description:
            d["description"] = self.description
        if self.orientation:
            d["orientation"] = self.orientation.value if isinstance(self.orientation, Orientation) else str(self.orientation)
        if self.lang:
            d["lang"] = self.lang
        if self.dir and self.dir != "auto":
            d["dir"] = self.dir
        if self.categories:
            d["categories"] = self.categories
        if self.display_override:
            d["display_override"] = self.display_override
        if self.icons:
            d["icons"] = [icon.to_dict() if isinstance(icon, IconSpec) else icon for icon in self.icons]
        if self.shortcuts:
            d["shortcuts"] = [s.to_dict() if isinstance(s, ShortcutSpec) else s for s in self.shortcuts]
        if self.screenshots:
            d["screenshots"] = self.screenshots
        if self.related_applications:
            d["related_applications"] = self.related_applications
            d["prefer_related_applications"] = self.prefer_related_applications
        if self.share_target:
            d["share_target"] = self.share_target.to_dict() if isinstance(self.share_target, ShareTargetSpec) else self.share_target
        if self.protocol_handlers:
            d["protocol_handlers"] = [
                h.to_dict() if hasattr(h, "to_dict") else h for h in self.protocol_handlers
            ]
        if self.file_handlers:
            d["file_handlers"] = self.file_handlers
        if self.i18n:
            d["i18n"] = self.i18n

        return d

    def to_json(self, indent: int = 2) -> str:
        """Serializes manifest to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False) + "\n"

    def add_protocol_handler(
        self,
        protocol: str,
        url: str,
        title: Optional[str] = None,
    ) -> ProtocolHandlerSpec:
        """Helper to append a URL protocol handler to the manifest configuration."""
        handler = ProtocolHandlerSpec(protocol=protocol, url=url, title=title)
        self.protocol_handlers.append(handler)
        return handler

    def simulate_shortcuts(self) -> ShortcutSuiteReport:
        """Simulate App Shortcuts action events and validate icon assets."""
        from .shortcuts_simulator import simulate_app_shortcuts
        return simulate_app_shortcuts(self)

    def validate_protocols(self) -> ProtocolHandlerValidationReport:
        """Validate URL protocol handlers against W3C specification."""
        from .shortcuts_simulator import validate_protocol_handlers
        return validate_protocol_handlers(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PWAManifestConfig:
        """Constructs a PWAManifestConfig instance from a dictionary."""
        icons = [IconSpec.from_dict(i) if isinstance(i, dict) else i for i in data.get("icons", [])]
        shortcuts = [ShortcutSpec.from_dict(s) if isinstance(s, dict) else s for s in data.get("shortcuts", [])]
        raw_protocols = data.get("protocol_handlers", [])
        protocol_handlers = [
            ProtocolHandlerSpec.from_dict(h) if isinstance(h, dict) else h
            for h in raw_protocols
        ]
        share_target = None
        if data.get("share_target"):
            st = data["share_target"]
            share_target = ShareTargetSpec.from_dict(st) if isinstance(st, dict) else st

        return cls(
            name=data.get("name", "PWA App"),
            short_name=data.get("short_name"),
            description=data.get("description"),
            start_url=data.get("start_url", "/"),
            scope=data.get("scope", "/"),
            display=DisplayMode.from_string(data.get("display", "standalone")),
            orientation=Orientation.from_string(data.get("orientation")),
            theme_color=data.get("theme_color", "#000000"),
            background_color=data.get("background_color", "#ffffff"),
            lang=data.get("lang", "en"),
            dir=data.get("dir", "auto"),
            categories=data.get("categories", []),
            icons=icons,
            shortcuts=shortcuts,
            screenshots=data.get("screenshots", []),
            related_applications=data.get("related_applications", []),
            prefer_related_applications=data.get("prefer_related_applications", False),
            id=data.get("id"),
            share_target=share_target,
            protocol_handlers=protocol_handlers,
            file_handlers=data.get("file_handlers", []),
            display_override=data.get("display_override", []),
            i18n=data.get("i18n", {})
        )


@dataclass
class ServiceWorkerConfig:
    """Configuration for synthesizing production-ready Service Workers."""
    cache_name: str = "pwa-cache"
    cache_version: str = "v1"
    caching_strategy: Union[CachingStrategy, str] = CachingStrategy.NETWORK_FIRST
    precache_urls: List[str] = field(default_factory=lambda: ["/", "/index.html", "/manifest.webmanifest"])
    runtime_cache_patterns: List[Dict[str, Any]] = field(default_factory=list)
    offline_fallback_url: Optional[str] = None
    enable_navigation_preload: bool = False
    enable_background_sync: bool = False
    background_sync_tag: str = "sync-data"
    enable_push_notifications: bool = False

    def __post_init__(self):
        if isinstance(self.caching_strategy, str):
            self.caching_strategy = CachingStrategy.from_string(self.caching_strategy)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cache_name": self.cache_name,
            "cache_version": self.cache_version,
            "caching_strategy": self.caching_strategy.value if isinstance(self.caching_strategy, CachingStrategy) else str(self.caching_strategy),
            "precache_urls": self.precache_urls,
            "runtime_cache_patterns": self.runtime_cache_patterns,
            "offline_fallback_url": self.offline_fallback_url,
            "enable_navigation_preload": self.enable_navigation_preload,
            "enable_background_sync": self.enable_background_sync,
            "background_sync_tag": self.background_sync_tag,
            "enable_push_notifications": self.enable_push_notifications,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ServiceWorkerConfig:
        return cls(
            cache_name=data.get("cache_name", "pwa-cache"),
            cache_version=data.get("cache_version", "v1"),
            caching_strategy=CachingStrategy.from_string(data.get("caching_strategy", "NetworkFirst")),
            precache_urls=data.get("precache_urls", ["/", "/index.html", "/manifest.webmanifest"]),
            runtime_cache_patterns=data.get("runtime_cache_patterns", []),
            offline_fallback_url=data.get("offline_fallback_url"),
            enable_navigation_preload=data.get("enable_navigation_preload", False),
            enable_background_sync=data.get("enable_background_sync", False),
            background_sync_tag=data.get("background_sync_tag", "sync-data"),
            enable_push_notifications=data.get("enable_push_notifications", False)
        )


@dataclass
class PWAValidationIssue:
    """Represents a linting or validation issue in a PWA manifest."""
    severity: str  # "error", "warning", "info"
    code: str
    message: str
    field: Optional[str] = None
    fix_suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "field": self.field,
            "fix_suggestion": self.fix_suggestion
        }


@dataclass
class PWAValidationReport:
    """Comprehensive validation report for PWA installability and compliance."""
    is_valid: bool
    installable_score: int  # 0 to 100
    issues: List[PWAValidationIssue] = field(default_factory=list)
    warnings: List[PWAValidationIssue] = field(default_factory=list)
    passed_checks: List[str] = field(default_factory=list)
    meta_tags_html: str = ""

    def errors(self) -> List[PWAValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    def has_errors(self) -> bool:
        return len(self.errors()) > 0

    def summary(self) -> str:
        err_count = len(self.errors())
        warn_count = len(self.warnings)
        status = "PASSED (Installable)" if self.is_valid and err_count == 0 else "FAILED (Not Installable)"
        return (
            f"PWA Validation Audit: {status}\n"
            f"Installability Score: {self.installable_score}/100\n"
            f"Errors: {err_count}, Warnings: {warn_count}, Passed Checks: {len(self.passed_checks)}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "installable_score": self.installable_score,
            "issues": [i.to_dict() for i in self.issues],
            "warnings": [w.to_dict() for w in self.warnings],
            "passed_checks": self.passed_checks,
            "meta_tags_html": self.meta_tags_html,
            "summary": self.summary()
        }


@dataclass
class ShortcutSimulatorResult:
    """Individual shortcut simulation assessment."""
    name: str
    url: str
    short_name: Optional[str] = None
    has_icons: bool = False
    icon_sizes: List[str] = field(default_factory=list)
    has_monochrome_icon: bool = False
    is_valid: bool = True
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    sample_event_handler: str = ""

    @property
    def has_recommended_sizes(self) -> bool:
        return any(sz in ("96x96", "192x192") for sz in self.icon_sizes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "short_name": self.short_name,
            "has_icons": self.has_icons,
            "icon_sizes": self.icon_sizes,
            "has_monochrome_icon": self.has_monochrome_icon,
            "has_recommended_sizes": self.has_recommended_sizes,
            "is_valid": self.is_valid,
            "issues": self.issues,
            "warnings": self.warnings,
            "sample_event_handler": self.sample_event_handler,
        }


@dataclass
class ShortcutSuiteReport:
    """Overall report and client-side router simulation for App Shortcuts."""
    shortcuts: List[ShortcutSimulatorResult]
    total_count: int
    android_ready: bool
    windows_ready: bool
    warnings: List[str]
    client_router_js: str

    @property
    def total_shortcuts(self) -> int:
        return self.total_count

    @property
    def global_warnings(self) -> List[str]:
        return self.warnings

    @property
    def has_exceeded_platform_limit(self) -> bool:
        return self.total_count > 4

    @property
    def client_deep_link_router_js(self) -> str:
        return self.client_router_js

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_count": self.total_count,
            "total_shortcuts": self.total_count,
            "android_ready": self.android_ready,
            "windows_ready": self.windows_ready,
            "warnings": self.warnings,
            "global_warnings": self.warnings,
            "has_exceeded_platform_limit": self.has_exceeded_platform_limit,
            "shortcuts": [s.to_dict() for s in self.shortcuts],
            "client_router_js": self.client_router_js,
            "client_deep_link_router_js": self.client_router_js,
        }


@dataclass
class ProtocolHandlerItem:
    """Individual protocol handler validation evaluation."""
    protocol: str
    url: str
    title: Optional[str] = None
    is_valid: bool = True
    issues: List[str] = field(default_factory=list)
    error_code: Optional[str] = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocol": self.protocol,
            "url": self.url,
            "title": self.title,
            "is_valid": self.is_valid,
            "issues": self.issues,
            "error_code": self.error_code,
        }


@dataclass
class ProtocolHandlerValidationReport:
    """Validation report and browser registration script for URL Protocol Handlers."""
    is_valid: bool
    valid_count: int
    invalid_count: int
    handlers: List[Any]
    errors: List[str]
    warnings: List[str]
    registration_script: str

    @property
    def valid_handlers(self) -> List[Any]:
        return [h for h in self.handlers if (isinstance(h, dict) and h.get("is_valid")) or (hasattr(h, "is_valid") and h.is_valid)]

    @property
    def invalid_handlers(self) -> List[Any]:
        return [h for h in self.handlers if (isinstance(h, dict) and not h.get("is_valid")) or (hasattr(h, "is_valid") and not h.is_valid)]

    @property
    def registration_snippet_js(self) -> str:
        return self.registration_script

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "handlers": [h.to_dict() if hasattr(h, "to_dict") else h for h in self.handlers],
            "valid_handlers": [h.to_dict() if hasattr(h, "to_dict") else h for h in self.valid_handlers],
            "invalid_handlers": [h.to_dict() if hasattr(h, "to_dict") else h for h in self.invalid_handlers],
            "errors": self.errors,
            "warnings": self.warnings,
            "registration_script": self.registration_script,
            "registration_snippet_js": self.registration_script,
        }
