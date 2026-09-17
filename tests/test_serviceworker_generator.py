"""
Unit tests for pwa_manifest_builder.serviceworker_generator module.
Tests ServiceWorker code synthesis, caching strategy routines, background sync, push notification hooks, and registration scripts.
"""

from pathlib import Path
import pytest

from pwa_manifest_builder.serviceworker_generator import (
    generate_service_worker,
    generate_sw_registration_script,
    save_service_worker,
)
from pwa_manifest_builder.models import ServiceWorkerConfig, CachingStrategy


def test_generate_service_worker_default(sample_sw_config):
    sw_js = generate_service_worker(sample_sw_config)
    
    assert "const CACHE_NAME = 'test-pwa-cache-v2';" in sw_js
    assert "self.addEventListener('install'" in sw_js
    assert "self.addEventListener('activate'" in sw_js
    assert "self.addEventListener('fetch'" in sw_js
    assert "handleStaleWhileRevalidate" in sw_js
    assert "handleNetworkFirst" in sw_js
    assert "handleCacheFirst" in sw_js
    assert "self.skipWaiting()" in sw_js
    assert "self.clients.claim()" in sw_js
    assert "/offline.html" in sw_js


def test_generate_service_worker_with_sync_and_push():
    cfg = ServiceWorkerConfig(
        cache_name="sync-push-cache",
        cache_version="v1",
        enable_background_sync=True,
        background_sync_tag="my-sync-tag",
        enable_push_notifications=True
    )
    sw_js = generate_service_worker(cfg)
    
    assert "self.addEventListener('sync'" in sw_js
    assert "my-sync-tag" in sw_js
    assert "self.addEventListener('push'" in sw_js
    assert "self.addEventListener('notificationclick'" in sw_js


def test_generate_sw_registration_script():
    script = generate_sw_registration_script(sw_path="/custom-sw.js", scope="/app/", auto_reload_on_update=True)
    
    assert "<script>" in script
    assert "navigator.serviceWorker.register('/custom-sw.js', { scope: '/app/' })" in script
    assert "controllerchange" in script
    assert "window.location.reload()" in script


def test_save_service_worker_atomic(sample_sw_config, tmp_path):
    sw_file = tmp_path / "sw.js"
    saved = save_service_worker(sample_sw_config, sw_file)
    
    assert saved.exists()
    content = saved.read_text(encoding="utf-8")
    assert "test-pwa-cache-v2" in content
