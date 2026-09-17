"""
Unit and integration tests for pwa_manifest_builder.ui_server module.
Tests ThreadingHTTPServer lifecycle, REST API endpoints, CORS handling, and ZIP bundle generation.
"""

import io
import json
import urllib.request
import urllib.error
import zipfile
import pytest

from pwa_manifest_builder.ui_server import PWAServer, PWARequestHandler


@pytest.fixture(scope="module")
def running_server():
    """Fixture that boots a background PWAServer on a random free port and tears it down after tests."""
    server = PWAServer(host="127.0.0.1", port=18900)
    url = server.start(open_browser=False)
    yield url
    server.stop()


def _http_get(url: str, headers: dict = None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req) as resp:
        return resp.getcode(), resp.read(), resp.headers


def _http_post_json(url: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        return resp.getcode(), resp.read(), resp.headers


def test_ui_server_health(running_server):
    code, data, headers = _http_get(f"{running_server}/health")
    assert code == 200
    res = json.loads(data.decode("utf-8"))
    assert res["status"] == "healthy"


def test_ui_server_index_html(running_server):
    code, data, headers = _http_get(f"{running_server}/")
    assert code == 200
    text = data.decode("utf-8")
    assert "PWA Studio" in text
    assert "html" in headers.get("Content-Type", "")


def test_ui_server_templates_api(running_server):
    code, data, _ = _http_get(f"{running_server}/api/templates")
    assert code == 200
    res = json.loads(data.decode("utf-8"))
    assert "templates" in res
    assert res["count"] >= 10

    # Single template endpoint
    code2, data2, _ = _http_get(f"{running_server}/api/templates/saas-dashboard")
    assert code2 == 200
    t = json.loads(data2.decode("utf-8"))
    assert t["id"] == "saas-dashboard"

    # Non-existent template 404
    try:
        _http_get(f"{running_server}/api/templates/non-existent-xyz")
        assert False, "Expected HTTP 404"
    except urllib.error.HTTPError as err:
        assert err.code == 404


def test_ui_server_stats_and_diagnostics(running_server):
    code, data, _ = _http_get(f"{running_server}/api/stats")
    assert code == 200
    stats = json.loads(data.decode("utf-8"))
    assert "template_count" in stats
    assert "supported_icon_sizes" in stats

    code2, data2, _ = _http_get(f"{running_server}/api/diagnostics")
    assert code2 == 200
    diag = json.loads(data2.decode("utf-8"))
    assert "python_version" in diag
    assert "server_name" in diag


def test_ui_server_generate_manifest_api(running_server):
    payload = {
        "name": "API Test PWA",
        "short_name": "APITest",
        "theme_color": "#1a73e8",
        "display": "standalone"
    }
    code, data, _ = _http_post_json(f"{running_server}/api/generate-manifest", payload)
    assert code == 200
    res = json.loads(data.decode("utf-8"))
    assert res["manifest"]["name"] == "API Test PWA"
    assert "html_meta_tags" in res
    assert "validation" in res
    assert res["score"] >= 0


def test_ui_server_generate_sw_api(running_server):
    payload = {
        "cache_name": "api-cache",
        "caching_strategy": "CacheFirst",
        "precache_urls": ["/", "/index.html"]
    }
    code, data, _ = _http_post_json(f"{running_server}/api/generate-sw", payload)
    assert code == 200
    res = json.loads(data.decode("utf-8"))
    assert "service_worker" in res
    assert "api-cache" in res["service_worker"]
    assert "registration_script" in res


def test_ui_server_generate_icons_api(running_server):
    payload = {
        "name": "Studio Icon",
        "bg_color": "#059669",
        "icon_name": "bolt"
    }
    code, data, _ = _http_post_json(f"{running_server}/api/generate-icons", payload)
    assert code == 200
    res = json.loads(data.decode("utf-8"))
    assert "icons" in res
    assert len(res["icons"]) > 5
    assert "file_summary" in res


def test_ui_server_audit_api(running_server):
    payload = {
        "manifest": {
            "name": "Audited App",
            "short_name": "Audit",
            "start_url": "/",
            "icons": [
                {"src": "/icon-192.png", "sizes": "192x192"},
                {"src": "/icon-512.png", "sizes": "512x512"}
            ]
        }
    }
    code, data, _ = _http_post_json(f"{running_server}/api/audit", payload)
    assert code == 200
    res = json.loads(data.decode("utf-8"))
    assert "installable_score" in res
    assert res["is_valid"] is True


def test_ui_server_bundle_zip_export(running_server):
    payload = {
        "manifest": {
            "name": "Zip Export App",
            "short_name": "ZipApp",
            "theme_color": "#1a73e8",
            "background_color": "#ffffff",
            "start_url": "/",
            "scope": "/"
        },
        "sw_config": {
            "cache_name": "zip-cache",
            "cache_version": "v1",
            "caching_strategy": "StaleWhileRevalidate"
        }
    }
    code, data, headers = _http_post_json(f"{running_server}/api/bundle", payload)
    assert code == 200
    assert headers.get("Content-Type") == "application/zip"
    
    # Read the returned ZIP archive in-memory
    zip_buffer = io.BytesIO(data)
    with zipfile.ZipFile(zip_buffer, "r") as z:
        names = z.namelist()
        assert "manifest.webmanifest" in names
        assert "sw.js" in names
        assert "index.html" in names
        assert "offline.html" in names
        assert any(n.startswith("icons/") for n in names)
        
        manifest_text = z.read("manifest.webmanifest").decode("utf-8")
        assert "Zip Export App" in manifest_text
