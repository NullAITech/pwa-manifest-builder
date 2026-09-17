"""
Unit tests for pwa_manifest_builder.models module.
Tests enums, dataclasses, serialization, deserialization, and model helper methods.
"""

import json
import pytest
from pwa_manifest_builder.models import (
    DisplayMode,
    Orientation,
    CachingStrategy,
    IconSpec,
    ShortcutSpec,
    ShareTargetSpec,
    PWAManifestConfig,
    ServiceWorkerConfig,
    PWAValidationIssue,
    PWAValidationReport,
)


def test_display_mode_enum():
    assert DisplayMode.STANDALONE.value == "standalone"
    assert DisplayMode.FULLSCREEN.value == "fullscreen"
    assert DisplayMode.MINIMAL_UI.value == "minimal-ui"
    assert DisplayMode.BROWSER.value == "browser"
    
    assert DisplayMode.from_string("standalone") == DisplayMode.STANDALONE
    assert DisplayMode.from_string("FULLSCREEN") == DisplayMode.FULLSCREEN
    assert DisplayMode.from_string("minimal-ui") == DisplayMode.MINIMAL_UI
    assert DisplayMode.from_string("minimal_ui") == DisplayMode.MINIMAL_UI
    assert DisplayMode.from_string("unknown_value") == DisplayMode.STANDALONE
    assert DisplayMode.from_string(DisplayMode.BROWSER) == DisplayMode.BROWSER


def test_orientation_enum():
    assert Orientation.PORTRAIT.value == "portrait"
    assert Orientation.LANDSCAPE.value == "landscape"
    assert Orientation.ANY.value == "any"
    
    assert Orientation.from_string("portrait") == Orientation.PORTRAIT
    assert Orientation.from_string("PORTRAIT_PRIMARY") == Orientation.PORTRAIT_PRIMARY
    assert Orientation.from_string(Orientation.LANDSCAPE) == Orientation.LANDSCAPE
    assert Orientation.from_string(None) is None
    assert Orientation.from_string("invalid_xyz") is None


def test_caching_strategy_enum():
    assert CachingStrategy.CACHE_FIRST.value == "CacheFirst"
    assert CachingStrategy.NETWORK_FIRST.value == "NetworkFirst"
    assert CachingStrategy.STALE_WHILE_REVALIDATE.value == "StaleWhileRevalidate"
    
    assert CachingStrategy.from_string("cache-first") == CachingStrategy.CACHE_FIRST
    assert CachingStrategy.from_string("networkfirst") == CachingStrategy.NETWORK_FIRST
    assert CachingStrategy.from_string("stale_while_revalidate") == CachingStrategy.STALE_WHILE_REVALIDATE
    assert CachingStrategy.from_string("unknown") == CachingStrategy.NETWORK_FIRST
    assert CachingStrategy.from_string(CachingStrategy.CACHE_ONLY) == CachingStrategy.CACHE_ONLY


def test_icon_spec():
    icon = IconSpec(src="/icons/app-512.png", sizes="512x512", type="image/png", purpose="maskable")
    assert icon.width == 512
    assert icon.height == 512
    
    d = icon.to_dict()
    assert d["src"] == "/icons/app-512.png"
    assert d["sizes"] == "512x512"
    assert d["purpose"] == "maskable"
    
    restored = IconSpec.from_dict(d)
    assert restored.src == icon.src
    assert restored.sizes == icon.sizes
    assert restored.purpose == icon.purpose
    assert restored.width == 512


def test_shortcut_spec():
    shortcut = ShortcutSpec(
        name="Inbox",
        url="/inbox",
        short_name="Mail",
        description="View your inbox",
        icons=[IconSpec(src="/icons/inbox.png", sizes="96x96")]
    )
    d = shortcut.to_dict()
    assert d["name"] == "Inbox"
    assert d["url"] == "/inbox"
    assert len(d["icons"]) == 1
    assert d["icons"][0]["sizes"] == "96x96"
    
    restored = ShortcutSpec.from_dict(d)
    assert restored.name == "Inbox"
    assert len(restored.icons) == 1
    assert isinstance(restored.icons[0], IconSpec)


def test_share_target_spec():
    st = ShareTargetSpec(
        action="/share-target",
        method="POST",
        enctype="multipart/form-data",
        params={"title": "title", "text": "text", "url": "url"}
    )
    d = st.to_dict()
    assert d["action"] == "/share-target"
    assert d["method"] == "POST"
    assert d["params"]["title"] == "title"
    
    restored = ShareTargetSpec.from_dict(d)
    assert restored.action == "/share-target"
    assert restored.method == "POST"
    assert restored.params["text"] == "text"


def test_pwa_manifest_config_methods():
    cfg = PWAManifestConfig(
        name="Super Amazing PWA Application Long Title",
        description="PWA App Description",
        theme_color="#1a73e8",
        background_color="#ffffff"
    )
    # Check auto-generated short_name (capped at 12)
    assert len(cfg.short_name) <= 12
    assert cfg.id == "/"
    
    # Test add_icon helper
    icon = cfg.add_icon("/icons/icon-192.png", sizes="192x192", purpose="any")
    assert len(cfg.icons) == 1
    assert icon.sizes == "192x192"
    
    # Test add_shortcut helper
    sc = cfg.add_shortcut("Search", "/search", short_name="Find")
    assert len(cfg.shortcuts) == 1
    assert sc.name == "Search"
    
    # Test to_dict and to_json
    d = cfg.to_dict()
    assert d["name"] == "Super Amazing PWA Application Long Title"
    assert d["display"] == "standalone"
    assert len(d["icons"]) == 1
    assert len(d["shortcuts"]) == 1
    
    json_str = cfg.to_json()
    parsed = json.loads(json_str)
    assert parsed["name"] == cfg.name
    
    # Test from_dict roundtrip
    rebuilt = PWAManifestConfig.from_dict(parsed)
    assert rebuilt.name == cfg.name
    assert len(rebuilt.icons) == 1
    assert len(rebuilt.shortcuts) == 1


def test_service_worker_config():
    sw = ServiceWorkerConfig(
        cache_name="app-cache",
        cache_version="v3",
        caching_strategy="cache-first",
        offline_fallback_url="/offline.html",
        enable_navigation_preload=True,
        enable_background_sync=True
    )
    assert sw.caching_strategy == CachingStrategy.CACHE_FIRST
    
    d = sw.to_dict()
    assert d["cache_name"] == "app-cache"
    assert d["cache_version"] == "v3"
    assert d["caching_strategy"] == "CacheFirst"
    assert d["offline_fallback_url"] == "/offline.html"
    
    rebuilt = ServiceWorkerConfig.from_dict(d)
    assert rebuilt.cache_name == "app-cache"
    assert rebuilt.caching_strategy == CachingStrategy.CACHE_FIRST


def test_validation_report():
    issue1 = PWAValidationIssue(severity="error", code="MISSING_ICON", message="Icon missing", field="icons")
    issue2 = PWAValidationIssue(severity="warning", code="LONG_NAME", message="Name is long", field="name")
    
    report = PWAValidationReport(
        is_valid=False,
        installable_score=45,
        issues=[issue1],
        warnings=[issue2],
        passed_checks=["has_theme_color", "has_start_url"]
    )
    
    assert report.has_errors() is True
    assert len(report.errors()) == 1
    assert "FAILED (Not Installable)" in report.summary()
    assert report.installable_score == 45
    
    d = report.to_dict()
    assert d["is_valid"] is False
    assert len(d["issues"]) == 1
    assert len(d["warnings"]) == 1
    assert len(d["passed_checks"]) == 2
