"""
Comprehensive test suite for PWA App Shortcuts Simulator & Protocol Handler Auditor.
Tests 100% pure Python standard library capabilities across platforms.
"""

import json
import pytest
from pwa_manifest_builder.models import (
    PWAManifestConfig,
    ShortcutSpec,
    ProtocolHandlerSpec,
    IconSpec,
)
from pwa_manifest_builder.shortcuts_simulator import (
    validate_protocol_handlers,
    simulate_app_shortcuts,
)
from pwa_manifest_builder.linter import validate_manifest
from pwa_manifest_builder.mcp_server import handle_jsonrpc_request
from pwa_manifest_builder.cli import main as cli_main


def test_validate_protocol_handlers_valid_safelist():
    """Test validating safelisted protocols like mailto and webcal."""
    handlers = [
        {"protocol": "mailto", "url": "/compose?to=%s"},
        {"protocol": "webcal", "url": "/subscribe?calendar=%s"},
    ]
    report = validate_protocol_handlers(handlers, scope="/")
    assert report.is_valid is True
    assert len(report.valid_handlers) == 2
    assert len(report.invalid_handlers) == 0
    assert "registerProtocolHandler" in report.registration_snippet_js
    assert "mailto" in report.registration_snippet_js


def test_validate_protocol_handlers_valid_custom_web_plus():
    """Test validating custom web+ protocol handlers."""
    handlers = [
        {"protocol": "web+notes", "url": "/open-note?id=%s"},
    ]
    report = validate_protocol_handlers(handlers, scope="/")
    assert report.is_valid is True
    assert len(report.valid_handlers) == 1
    assert "web+notes" in report.registration_snippet_js


def test_validate_protocol_handlers_invalid_scheme():
    """Test rejecting protocols that are neither safelisted nor prefixed with web+."""
    handlers = [
        {"protocol": "mycustomproto", "url": "/view?item=%s"},
    ]
    report = validate_protocol_handlers(handlers, scope="/")
    assert report.is_valid is False
    assert len(report.invalid_handlers) == 1
    assert report.invalid_handlers[0].error_code == "INVALID_PROTOCOL_SCHEME"


def test_validate_protocol_handlers_missing_percent_s():
    """Test rejecting protocol handler URLs lacking %s token."""
    handlers = [
        {"protocol": "web+todo", "url": "/view/all"},
    ]
    report = validate_protocol_handlers(handlers, scope="/")
    assert report.is_valid is False
    assert len(report.invalid_handlers) == 1
    assert report.invalid_handlers[0].error_code == "MISSING_TOKEN_PLACEHOLDER"


def test_validate_protocol_handlers_out_of_scope():
    """Test warning when protocol handler URL is outside app scope."""
    handlers = [
        {"protocol": "web+app", "url": "/other/handler?uri=%s"},
    ]
    report = validate_protocol_handlers(handlers, scope="/app/")
    assert len(report.invalid_handlers) == 1
    assert report.invalid_handlers[0].error_code == "OUT_OF_SCOPE"


def test_simulate_app_shortcuts_complete():
    """Test app shortcuts simulation with icon recommendations and deep-link router JS."""
    shortcuts = [
        {
            "name": "New Task",
            "url": "/tasks/new",
            "short_name": "New",
            "description": "Quickly create a new task",
            "icons": [
                {"src": "/icons/shortcut-96.png", "sizes": "96x96", "type": "image/png"},
                {"src": "/icons/shortcut-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/icons/shortcut-mono.png", "sizes": "96x96", "type": "image/png", "purpose": "monochrome"},
            ],
        },
        {
            "name": "View Calendar",
            "url": "/calendar",
        },
    ]
    report = simulate_app_shortcuts(shortcuts, scope="/")
    assert report.total_shortcuts == 2
    assert report.has_exceeded_platform_limit is False
    assert len(report.shortcuts) == 2

    first = report.shortcuts[0]
    assert first.name == "New Task"
    assert first.has_recommended_sizes is True
    assert first.has_monochrome_icon is True

    second = report.shortcuts[1]
    assert second.has_recommended_sizes is False
    assert "No icons defined" in second.warnings[0]

    assert "launchQueue" in report.client_deep_link_router_js
    assert "/tasks/new" in report.client_deep_link_router_js
    assert "/calendar" in report.client_deep_link_router_js


def test_simulate_app_shortcuts_exceeding_limit():
    """Test warning when shortcut count exceeds the 4-item platform guideline."""
    shortcuts = [
        {"name": f"Action {i}", "url": f"/action/{i}"} for i in range(6)
    ]
    report = simulate_app_shortcuts(shortcuts, scope="/")
    assert report.total_shortcuts == 6
    assert report.has_exceeded_platform_limit is True
    assert any("exceeds the 4-item threshold" in w for w in report.global_warnings)


def test_manifest_config_shortcuts_and_protocol_methods():
    """Test PWAManifestConfig convenience methods for protocols and shortcuts."""
    config = PWAManifestConfig(
        name="Workspace Pro",
        short_name="Workspace",
        start_url="/app/",
        scope="/app/",
        shortcuts=[
            ShortcutSpec(name="Quick Note", url="/app/note/new"),
        ],
        protocol_handlers=[
            ProtocolHandlerSpec(protocol="web+note", url="/app/open?uri=%s"),
        ],
    )
    s_rep = config.simulate_shortcuts()
    assert s_rep.total_shortcuts == 1

    p_rep = config.validate_protocols()
    assert p_rep.is_valid is True

    # Test add_protocol_handler
    config.add_protocol_handler("web+chat", "/app/chat?room=%s")
    assert len(config.protocol_handlers) == 2


def test_linter_audits_shortcuts_and_protocols():
    """Test that validate_manifest checks shortcuts and protocol handlers."""
    manifest_data = {
        "name": "Audit App",
        "short_name": "Audit",
        "start_url": "/",
        "display": "standalone",
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "shortcuts": [
            {"name": f"Shortcut {i}", "url": f"/item/{i}"} for i in range(5)
        ],
        "protocol_handlers": [
            {"protocol": "badproto", "url": "/view"},
        ],
    }
    report = validate_manifest(manifest_data)
    codes = [issue.code for issue in report.issues + report.warnings]
    assert "SHORTCUTS_EXCEEDED" in codes
    assert "PROTOCOL_HANDLER_INVALID" in codes


def test_mcp_shortcuts_and_protocol_tools():
    """Test MCP server tools for shortcut simulation and protocol validation."""
    # Test pwa_simulate_shortcuts tool
    req_shortcuts = {
        "jsonrpc": "2.0",
        "id": "test-shortcuts-1",
        "method": "tools/call",
        "params": {
            "name": "pwa_simulate_shortcuts",
            "arguments": {
                "shortcuts": [
                    {"name": "Inbox", "url": "/inbox"}
                ]
            }
        }
    }
    res_shortcuts = handle_jsonrpc_request(req_shortcuts)
    assert res_shortcuts.get("error") is None
    data_sc = json.loads(res_shortcuts["result"]["content"][0]["text"])
    assert data_sc["total_shortcuts"] == 1
    assert "launchQueue" in data_sc["client_deep_link_router_js"]

    # Test pwa_validate_protocol_handlers tool
    req_proto = {
        "jsonrpc": "2.0",
        "id": "test-proto-1",
        "method": "tools/call",
        "params": {
            "name": "pwa_validate_protocol_handlers",
            "arguments": {
                "handlers": [
                    {"protocol": "web+search", "url": "/search?q=%s"}
                ]
            }
        }
    }
    res_proto = handle_jsonrpc_request(req_proto)
    assert res_proto.get("error") is None
    data_pr = json.loads(res_proto["result"]["content"][0]["text"])
    assert data_pr["is_valid"] is True
    assert len(data_pr["valid_handlers"]) == 1


def test_cli_shortcuts_and_protocol(capsys):
    """Test CLI commands for shortcuts and protocol subcommands."""
    # Test CLI shortcuts
    cli_main(["shortcuts", "--demo", "--json"])
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert "total_shortcuts" in res
    assert res["total_shortcuts"] >= 2

    # Test CLI protocol
    cli_main(["protocol", "--protocol", "web+music", "--url", "/play?track=%s", "--json"])
    captured = capsys.readouterr()
    res_proto = json.loads(captured.out)
    assert res_proto["is_valid"] is True
    assert len(res_proto["valid_handlers"]) == 1
