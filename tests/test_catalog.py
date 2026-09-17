"""
Unit tests for pwa_manifest_builder.catalog module.
Tests template registry, preset retrieval, customization overrides, and template generation.
"""

import pytest
from pwa_manifest_builder.catalog import (
    TEMPLATES,
    PWATemplate,
    list_templates,
    get_template,
    generate_from_template,
)
from pwa_manifest_builder.models import PWAManifestConfig, ServiceWorkerConfig, DisplayMode


def test_list_templates():
    templates = list_templates()
    assert len(templates) >= 12
    ids = [t["id"] for t in templates]
    assert "ecommerce-store" in ids
    assert "saas-dashboard" in ids
    assert "news-reader" in ids
    assert "offline-notes" in ids
    assert "gaming-canvas" in ids


def test_get_template():
    t = get_template("ecommerce-store")
    assert isinstance(t, PWATemplate)
    assert t.id == "ecommerce-store"
    assert t.category == "shopping"
    assert t.display == DisplayMode.STANDALONE
    
    # Non-existent template
    assert get_template("non-existent-template-id") is None


def test_generate_from_template():
    manifest, sw = generate_from_template(
        "saas-dashboard",
        name="Custom Acme Metrics",
        short_name="AcmeMetrics",
        theme_color="#3b82f6"
    )
    assert isinstance(manifest, PWAManifestConfig)
    assert isinstance(sw, ServiceWorkerConfig)
    assert manifest.name == "Custom Acme Metrics"
    assert manifest.short_name == "AcmeMetrics"
    assert manifest.theme_color == "#3b82f6"
    assert len(manifest.icons) > 0
    assert len(manifest.shortcuts) > 0


def test_generate_from_template_invalid():
    with pytest.raises(ValueError, match="Unknown template ID"):
        generate_from_template("invalid-template-slug-xyz")
