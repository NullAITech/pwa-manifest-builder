"""
Unit tests for pwa_manifest_builder.manifest_generator module.
Tests manifest dictionary generation, JSON formatting, HTML meta tags generation, and file saving.
"""

import json
from pathlib import Path
import pytest

from pwa_manifest_builder.manifest_generator import (
    generate_manifest_dict,
    generate_manifest_json,
    generate_html_meta_tags,
    save_manifest,
    build_manifest,
)
from pwa_manifest_builder.models import PWAManifestConfig, DisplayMode, Orientation, IconSpec


def test_generate_manifest_dict_and_json(sample_manifest_config):
    d = generate_manifest_dict(sample_manifest_config)
    assert d["name"] == "Google PWA Studio Test"
    assert d["short_name"] == "PWAStudio"
    assert d["start_url"] == "/?source=pwa"
    assert d["display"] == "standalone"
    assert len(d["icons"]) == 3
    
    json_str = generate_manifest_json(sample_manifest_config)
    parsed = json.loads(json_str)
    assert parsed["name"] == "Google PWA Studio Test"
    assert parsed["theme_color"] == "#1a73e8"


def test_generate_html_meta_tags(sample_manifest_config):
    html = generate_html_meta_tags(sample_manifest_config, manifest_path="/custom-manifest.json")
    
    assert '<link rel="manifest" href="/custom-manifest.json">' in html
    assert '<meta name="theme-color" content="#1a73e8">' in html
    assert '<meta name="application-name" content="PWAStudio">' in html
    assert '<meta name="apple-mobile-web-app-capable" content="yes">' in html
    assert '<meta name="msapplication-TileColor" content="#1a73e8">' in html
    assert 'viewport-fit=cover' in html


def test_build_manifest_factory_helper():
    cfg = build_manifest(
        name="Factory App",
        short_name="Factory",
        description="Created via factory",
        theme_color="#34a853",
        display="fullscreen",
        icons=[
            {"src": "/icons/icon.png", "sizes": "192x192", "type": "image/png"}
        ]
    )
    assert isinstance(cfg, PWAManifestConfig)
    assert cfg.name == "Factory App"
    assert cfg.display == DisplayMode.FULLSCREEN
    assert len(cfg.icons) == 1
    assert isinstance(cfg.icons[0], IconSpec)


def test_save_manifest_atomic(sample_manifest_config, tmp_path):
    out_file = tmp_path / "manifest.webmanifest"
    saved = save_manifest(sample_manifest_config, out_file)
    
    assert saved.exists()
    content = saved.read_text(encoding="utf-8")
    data = json.loads(content)
    assert data["name"] == "Google PWA Studio Test"
