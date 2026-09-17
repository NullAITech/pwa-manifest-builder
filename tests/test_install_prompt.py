"""Unit tests for PWA install prompt banner generation and display_override support."""

from pwa_manifest_builder.models import PWAManifestConfig, DisplayMode
from pwa_manifest_builder.manifest_generator import (
    generate_install_prompt_banner_html,
    generate_manifest_dict,
)


def test_generate_install_prompt_banner_default():
    cfg = PWAManifestConfig(
        name="Test PWA Application",
        short_name="TestApp",
        description="A blazing fast offline-first PWA",
        theme_color="#1a73e8",
    )
    html = generate_install_prompt_banner_html(cfg)
    assert "pwa-install-banner" in html
    assert 'role="dialog"' in html
    assert "TestApp" in html
    assert "A blazing fast offline-first PWA" in html
    assert "#1a73e8" in html
    assert "beforeinstallprompt" in html
    assert "pwa-ios-sheet" in html
    assert "Not now" in html
    assert "Install" in html


def test_generate_install_prompt_banner_custom_options():
    manifest_dict = {
        "name": "Cloud Studio",
        "short_name": "Studio",
        "theme_color": "#ff5722",
        "display": "standalone",
        "icons": [{"src": "/icons/icon-512.png", "sizes": "512x512"}],
    }
    html = generate_install_prompt_banner_html(
        manifest_dict,
        banner_id="custom-install-widget",
        banner_title="Download Cloud Studio",
        banner_prompt_text="Get the full native experience on desktop and mobile.",
        position="top",
        accent_color="#ff5722",
        dismiss_days=14,
    )
    assert "custom-install-widget" in html
    assert "Download Cloud Studio" in html
    assert "Get the full native experience" in html
    assert "top: 20px;" in html
    assert "#ff5722" in html
    assert "14 * 24 * 60 * 60 * 1000" in html


def test_display_override_manifest_support():
    cfg = PWAManifestConfig(
        name="Desktop Pro App",
        start_url="/",
        display=DisplayMode.STANDALONE,
        display_override=["window-controls-overlay", "standalone", "minimal-ui"],
    )
    manifest_dict = generate_manifest_dict(cfg)
    assert manifest_dict["display"] == "standalone"
    assert "display_override" in manifest_dict
    assert manifest_dict["display_override"] == [
        "window-controls-overlay",
        "standalone",
        "minimal-ui",
    ]
