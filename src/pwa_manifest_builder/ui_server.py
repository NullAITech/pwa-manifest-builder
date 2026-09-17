"""
Pure-Python Threading HTTP Studio UI Server & REST API.

Serves the Google Material 3 PWA Studio interface and provides complete REST endpoints
for real-time manifest generation, ServiceWorker synthesis, SVG icon forging,
installability audits, and complete 1-click ZIP bundle downloads.
100% Python Standard Library - zero external dependencies.
"""

from __future__ import annotations

import io
import json
import os
import platform
import socket
import sys
import threading
import time
import urllib.parse
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Internal module imports
from .compat import normalize_path, read_text_safe
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
)
from .serviceworker_generator import (
    generate_service_worker,
    generate_sw_registration_script,
)
from .icon_forge import (
    generate_icon_svg,
    generate_favicon_ico,
    generate_icon_pack,
    STANDARD_ICON_SIZES,
)
from .linter import validate_manifest, is_valid_color
from .catalog import list_templates, get_template, generate_from_template
from .shortcuts_simulator import simulate_app_shortcuts, validate_protocol_handlers

SERVER_VERSION = "1.0.0"
SERVER_START_TIME = time.time()

# Locate public/index.html with fallback paths
def _find_static_index_html() -> Optional[str]:
    """Finds and reads public/index.html relative to package or repo root."""
    possible_paths = [
        Path(__file__).resolve().parent.parent.parent / "public" / "index.html",
        Path(__file__).resolve().parent / "public" / "index.html",
        Path.cwd() / "public" / "index.html",
        Path.cwd() / "index.html",
    ]
    for p in possible_paths:
        if p.is_file():
            content = read_text_safe(p)
            if content:
                return content
    return None


EMBEDDED_FALLBACK_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>PWA Manifest Studio</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 40px; background: #f8f9fa; color: #202124; text-align: center; }
    .card { max-width: 600px; margin: 0 auto; background: white; padding: 32px; border-radius: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
    h1 { color: #1a73e8; margin-bottom: 12px; }
    p { color: #5f6368; line-height: 1.6; }
    .btn { display: inline-block; background: #1a73e8; color: white; padding: 10px 24px; border-radius: 20px; text-decoration: none; font-weight: 500; margin-top: 16px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>PWA Manifest Studio</h1>
    <p>PWA Manifest & ServiceWorker Studio Server is running.</p>
    <p>API endpoints are active at <code>/api/generate-manifest</code>, <code>/api/generate-sw</code>, <code>/api/audit</code>, <code>/api/bundle</code>.</p>
  </div>
</body>
</html>"""


class PWARequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for PWA Studio UI and REST Endpoints."""

    server_version = f"PWAManifestStudio/{SERVER_VERSION}"

    def log_message(self, format: str, *args: Any) -> None:
        """Custom clean logging."""
        # Suppress verbose standard logs in tests unless env var set
        if os.environ.get("PWA_SERVER_VERBOSE"):
            sys.stderr.write(f"[PWA Server] {self.address_string()} - {format % args}\n")

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")

    def _send_json_response(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_text_response(self, text: str, content_type: str = "text/plain", status: int = 200) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes_response(self, data: bytes, content_type: str, filename: Optional[str] = None, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def _parse_json_body(self) -> Dict[str, Any]:
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            return {}
        raw = self.rfile.read(content_len).decode("utf-8", errors="replace")
        if not raw.strip():
            return {}
        try:
            return json.loads(raw)
        except Exception as e:
            raise ValueError(f"Invalid JSON payload: {str(e)}")

    def do_OPTIONS(self) -> None:
        """Handle CORS pre-flight requests."""
        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        """Dispatch GET requests."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.rstrip("/")
        if not path:
            path = "/"

        # 1. Health Checks
        if path in ("/health", "/api/health"):
            self._send_json_response({"status": "healthy", "version": SERVER_VERSION, "uptime_seconds": round(time.time() - SERVER_START_TIME, 2)})
            return

        # 2. Studio UI Home Page
        if path in ("/", "/index.html"):
            html_content = _find_static_index_html() or EMBEDDED_FALLBACK_HTML
            self._send_text_response(html_content, content_type="text/html")
            return

        # 3. List Templates
        if path == "/api/templates":
            query = urllib.parse.parse_qs(parsed_url.query)
            category = query.get("category", [None])[0]
            templates = list_templates()
            if category:
                templates = [t for t in templates if t.get("category") == category]
            self._send_json_response({"templates": templates, "count": len(templates)})
            return

        # 4. Get Single Template
        if path.startswith("/api/templates/"):
            tpl_id = path[len("/api/templates/"):]
            tpl = get_template(tpl_id)
            if tpl:
                self._send_json_response(tpl.to_dict())
            else:
                self._send_json_response({"error": f"Template '{tpl_id}' not found"}, status=404)
            return

        # 5. Runtime Statistics
        if path == "/api/stats":
            self._send_json_response({
                "server_version": SERVER_VERSION,
                "uptime_seconds": round(time.time() - SERVER_START_TIME, 2),
                "template_count": len(list_templates()),
                "supported_icon_sizes": STANDARD_ICON_SIZES,
                "supported_display_modes": [m.value for m in DisplayMode],
                "supported_caching_strategies": [s.value for s in CachingStrategy],
            })
            return

        # 6. Diagnostics
        if path == "/api/diagnostics":
            self._send_json_response({
                "server_name": "PWA Manifest Studio UI Server",
                "version": SERVER_VERSION,
                "python_version": sys.version,
                "platform": platform.platform(),
                "system": platform.system(),
                "machine": platform.machine(),
                "cwd": os.getcwd(),
                "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "uptime_seconds": round(time.time() - SERVER_START_TIME, 2),
            })
            return

        # 7. Shortcuts Info (GET)
        if path == "/api/shortcuts":
            sample = [{"name": "Quick Action", "url": "/quick", "short_name": "Quick"}]
            rep = simulate_app_shortcuts(sample)
            self._send_json_response({"status": "ok", "sample_report": rep.to_dict()})
            return

        # 8. Protocol Handlers Info (GET)
        if path == "/api/protocols":
            sample = [{"protocol": "web+pwa", "url": "/open?action=%s"}]
            rep = validate_protocol_handlers(sample)
            self._send_json_response({"status": "ok", "sample_report": rep.to_dict()})
            return

        # Static assets fallback (if public folder has files)
        static_file = Path(__file__).resolve().parent.parent.parent / "public" / path.lstrip("/")
        if static_file.is_file():
            ext = static_file.suffix.lower()
            mime_map = {
                ".html": "text/html",
                ".css": "text/css",
                ".js": "application/javascript",
                ".json": "application/json",
                ".webmanifest": "application/manifest+json",
                ".svg": "image/svg+xml",
                ".png": "image/png",
                ".ico": "image/x-icon",
            }
            mime = mime_map.get(ext, "application/octet-stream")
            content_bytes = static_file.read_bytes()
            self._send_bytes_response(content_bytes, content_type=mime)
            return

        self._send_json_response({"error": f"Route not found: {self.path}"}, status=404)

    def do_POST(self) -> None:
        """Dispatch POST requests."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.rstrip("/")

        try:
            body = self._parse_json_body()
        except ValueError as err:
            self._send_json_response({"error": str(err)}, status=400)
            return

        # 1. Generate Manifest
        if path == "/api/generate-manifest":
            try:
                manifest_cfg = PWAManifestConfig.from_dict(body)
                manifest_dict = generate_manifest_dict(manifest_cfg)
                manifest_json = generate_manifest_json(manifest_cfg, indent=2)
                html_tags = generate_html_meta_tags(manifest_cfg)
                validation_report = validate_manifest(manifest_cfg)

                self._send_json_response({
                    "manifest": manifest_dict,
                    "manifest_json": manifest_json,
                    "html_meta_tags": html_tags,
                    "validation": validation_report.to_dict(),
                    "installable": validation_report.is_valid,
                    "score": validation_report.installable_score,
                })
            except Exception as e:
                self._send_json_response({"error": f"Failed to generate manifest: {str(e)}"}, status=400)
            return

        # 2. Generate Service Worker
        if path == "/api/generate-sw":
            try:
                sw_cfg = ServiceWorkerConfig.from_dict(body)
                sw_script = generate_service_worker(sw_cfg)
                reg_script = generate_sw_registration_script(
                    sw_path=body.get("sw_path", "/sw.js"),
                    scope=body.get("scope", "/"),
                    auto_reload_on_update=body.get("auto_reload_on_update", False)
                )
                self._send_json_response({
                    "service_worker": sw_script,
                    "registration_script": reg_script,
                    "cache_name": sw_cfg.cache_name,
                    "strategy": sw_cfg.caching_strategy.value if hasattr(sw_cfg.caching_strategy, 'value') else str(sw_cfg.caching_strategy),
                })
            except Exception as e:
                self._send_json_response({"error": f"Failed to generate service worker: {str(e)}"}, status=400)
            return

        # 3. Generate Icons
        if path == "/api/generate-icons":
            try:
                name = body.get("name", "PWA")
                bg_color = body.get("bg_color", "#1a73e8")
                fg_color = body.get("fg_color", "#ffffff")
                icon_name = body.get("icon_name", "sparkles")
                
                pack = generate_icon_pack(
                    name_or_letter=name,
                    bg_color=bg_color,
                    fg_color=fg_color,
                    icon_name=icon_name,
                    base_url_prefix=body.get("base_url_prefix", "/icons")
                )
                
                # Convert bytes to hex strings or count for JSON response
                file_summary = {}
                for fname, content in pack["files"].items():
                    if isinstance(content, str):
                        file_summary[fname] = {"type": "svg", "length": len(content)}
                    else:
                        file_summary[fname] = {"type": "binary", "length": len(content)}

                self._send_json_response({
                    "icons": [i.to_dict() for i in pack["icons"]],
                    "file_summary": file_summary,
                    "apple_touch_icon": pack["apple_touch_icon"],
                    "favicon": pack["favicon"]
                })
            except Exception as e:
                self._send_json_response({"error": f"Failed to generate icons: {str(e)}"}, status=400)
            return

        # 4. Audit Manifest
        if path == "/api/audit":
            try:
                manifest_data = body.get("manifest", body)
                report = validate_manifest(manifest_data)
                self._send_json_response(report.to_dict())
            except Exception as e:
                self._send_json_response({"error": f"Failed to audit manifest: {str(e)}"}, status=400)
            return

        # 5. App Shortcuts Simulation & Deep-Link Router Generation
        if path == "/api/shortcuts":
            try:
                shortcuts_data = body.get("shortcuts", body if isinstance(body, list) else [])
                scope = body.get("scope", "/")
                manifest_url = body.get("manifest_url", "/")
                report = simulate_app_shortcuts(shortcuts_data, manifest_url=manifest_url, scope=scope)
                self._send_json_response(report.to_dict())
            except Exception as e:
                self._send_json_response({"error": f"Failed to simulate shortcuts: {str(e)}"}, status=400)
            return

        # 6. Protocol Handlers Validation & Snippet Generation
        if path == "/api/protocols":
            try:
                handlers_data = body.get("protocol_handlers", body.get("protocols", body if isinstance(body, list) else []))
                scope = body.get("scope", "/")
                report = validate_protocol_handlers(handlers_data, scope=scope)
                self._send_json_response(report.to_dict())
            except Exception as e:
                self._send_json_response({"error": f"Failed to validate protocol handlers: {str(e)}"}, status=400)
            return

        # 7. Export Complete PWA ZIP Bundle
        if path in ("/api/bundle", "/api/export-zip"):
            try:
                manifest_data = body.get("manifest", {})
                if not manifest_data:
                    manifest_data = body

                manifest_cfg = PWAManifestConfig.from_dict(manifest_data)
                sw_data = body.get("sw_config", {})
                sw_cfg = ServiceWorkerConfig.from_dict(sw_data)

                # Generate files
                manifest_json = generate_manifest_json(manifest_cfg, indent=2)
                sw_script = generate_service_worker(sw_cfg)
                meta_tags = generate_html_meta_tags(manifest_cfg)
                sw_reg = generate_sw_registration_script("/sw.js", manifest_cfg.scope)

                # Build full index.html
                index_html = f"""<!DOCTYPE html>
<html lang="{manifest_cfg.lang or 'en'}">
<head>
  <meta charset="UTF-8">
  <title>{manifest_cfg.name}</title>
{meta_tags}
  <style>
    body {{
      font-family: system-ui, -apple-system, sans-serif;
      margin: 0;
      padding: 32px;
      background: {manifest_cfg.background_color};
      color: #202124;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 80vh;
      text-align: center;
    }}
    .card {{
      background: white;
      padding: 32px;
      border-radius: 16px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.08);
      max-width: 500px;
    }}
    h1 {{ color: {manifest_cfg.theme_color}; margin-bottom: 8px; }}
    p {{ color: #5f6368; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>{manifest_cfg.name}</h1>
    <p>{manifest_cfg.description or 'A high-performance Progressive Web App.'}</p>
  </div>
{sw_reg}
</body>
</html>"""

                # Build standalone offline.html
                offline_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Offline | {manifest_cfg.name}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, sans-serif; background: {manifest_cfg.background_color}; color: #202124; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; text-align: center; padding: 20px; }}
    h1 {{ color: {manifest_cfg.theme_color}; margin-bottom: 8px; }}
    p {{ color: #5f6368; max-width: 400px; margin-bottom: 24px; }}
    button {{ background: {manifest_cfg.theme_color}; color: white; border: none; padding: 10px 24px; border-radius: 20px; font-weight: 500; cursor: pointer; }}
  </style>
</head>
<body>
  <h1>You're currently offline</h1>
  <p>{manifest_cfg.name} is ready for offline use. Please check your connection.</p>
  <button onclick="window.location.reload()">Retry Connection</button>
</body>
</html>"""

                # Generate Icon Assets
                icon_pack = generate_icon_pack(
                    name_or_letter=manifest_cfg.short_name or manifest_cfg.name,
                    bg_color=manifest_cfg.theme_color,
                    fg_color="#ffffff",
                    base_url_prefix="/icons"
                )

                # Create ZIP in-memory
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    zip_file.writestr("manifest.webmanifest", manifest_json)
                    zip_file.writestr("sw.js", sw_script)
                    zip_file.writestr("index.html", index_html)
                    zip_file.writestr("offline.html", offline_html)

                    # Add icons
                    for fname, content in icon_pack["files"].items():
                        zip_path = f"icons/{fname}"
                        if isinstance(content, str):
                            zip_file.writestr(zip_path, content)
                        else:
                            zip_file.writestr(zip_path, content)

                zip_data = zip_buffer.getvalue()
                filename = f"{manifest_cfg.short_name.lower().replace(' ', '-')}-pwa-bundle.zip"
                self._send_bytes_response(zip_data, content_type="application/zip", filename=filename)
            except Exception as e:
                self._send_json_response({"error": f"Failed to build bundle: {str(e)}"}, status=400)
            return

        self._send_json_response({"error": f"Route not found: {self.path}"}, status=404)


class PWAServer:
    """Manageable Threading HTTP Studio Server for programmatic start/stop."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        self.server: Optional[ThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self, open_browser: bool = False) -> str:
        """Starts the server in a background daemon thread."""
        # Find available port if specified port is in use
        for attempt_port in range(self.port, self.port + 50):
            try:
                self.server = ThreadingHTTPServer((self.host, attempt_port), PWARequestHandler)
                self.port = attempt_port
                break
            except OSError:
                continue

        if not self.server:
            raise RuntimeError(f"Could not bind PWA server to {self.host} on ports {self.port}-{self.port+50}")

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        url = f"http://{self.host}:{self.port}"
        if open_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass

        return url

    def stop(self) -> None:
        """Stops and closes the server cleanly."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
            self.thread = None


def start_ui_server(host: str = "127.0.0.1", port: int = 8080, open_browser: bool = False) -> None:
    """Runs the studio UI server blocking in the main thread (for CLI)."""
    server_manager = PWAServer(host=host, port=port)
    url = server_manager.start(open_browser=open_browser)
    print(f"\n🚀 PWA Manifest Studio UI running at: {url}")
    print("Press Ctrl+C to stop the studio server.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping PWA Manifest Studio UI Server...")
        server_manager.stop()
        print("Server stopped cleanly.")


if __name__ == "__main__":
    start_ui_server()
