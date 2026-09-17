"""
Pytest fixtures and configuration for pwa-manifest-builder test suite.
Ensures src directory is in sys.path and provides shared mock data and temp fixtures.
"""

import os
import sys
from pathlib import Path
import pytest

# Ensure src directory is placed at the front of sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pwa_manifest_builder.models import (
    PWAManifestConfig,
    IconSpec,
    ShortcutSpec,
    ShareTargetSpec,
    DisplayMode,
    Orientation,
    CachingStrategy,
    ServiceWorkerConfig,
)


@pytest.fixture
def sample_manifest_dict():
    """Standard valid PWA manifest dictionary fixture."""
    return {
        "name": "Google PWA Studio Test",
        "short_name": "PWAStudio",
        "description": "A progressive web app studio test manifest.",
        "start_url": "/?source=pwa",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "theme_color": "#1a73e8",
        "background_color": "#ffffff",
        "lang": "en-US",
        "dir": "ltr",
        "categories": ["utilities", "productivity", "developer"],
        "icons": [
            {
                "src": "/icons/icon-192x192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any"
            },
            {
                "src": "/icons/icon-512x512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any"
            },
            {
                "src": "/icons/maskable-512x512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable"
            }
        ],
        "shortcuts": [
            {
                "name": "New Project",
                "url": "/new",
                "short_name": "New",
                "description": "Create a new project",
                "icons": [
                    {
                        "src": "/icons/shortcut-new.png",
                        "sizes": "96x96",
                        "type": "image/png"
                    }
                ]
            }
        ],
        "screenshots": [
            {
                "src": "/screenshots/desktop-1.png",
                "sizes": "1280x720",
                "type": "image/png",
                "form_factor": "wide",
                "label": "Homescreen"
            }
        ],
        "prefer_related_applications": False,
        "id": "/?source=pwa"
    }


@pytest.fixture
def sample_manifest_config(sample_manifest_dict):
    """Constructed PWAManifestConfig instance."""
    return PWAManifestConfig.from_dict(sample_manifest_dict)


@pytest.fixture
def sample_sw_config():
    """Constructed ServiceWorkerConfig instance."""
    return ServiceWorkerConfig(
        cache_name="test-pwa-cache",
        cache_version="v2",
        caching_strategy=CachingStrategy.STALE_WHILE_REVALIDATE,
        precache_urls=["/", "/index.html", "/app.js", "/styles.css", "/offline.html"],
        offline_fallback_url="/offline.html",
        enable_navigation_preload=True,
        enable_background_sync=True,
        background_sync_tag="sync-notes",
        enable_push_notifications=True
    )


@pytest.fixture
def temp_project_dir(tmp_path):
    """Temporary directory for file output testing."""
    out_dir = tmp_path / "pwa_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
