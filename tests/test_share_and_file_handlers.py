"""
Comprehensive test suite for Web Share Target API & File Handling API.
Verifies compliance validation, payload simulation, script synthesis,
MCP integration, CLI subcommands, and UI server endpoints.
100% Python Standard Library.
"""

import json
from io import StringIO
import pytest

from pwa_manifest_builder.models import (
    FileHandlerItem,
    FileHandlerSpec,
    FileHandlerValidationReport,
    FileLaunchSimulationResult,
    PWAManifestConfig,
    ShareSimulationResult,
    ShareTargetSpec,
    ShareTargetValidationReport,
)
from pwa_manifest_builder.share_and_file_handlers import (
    simulate_file_launch,
    simulate_web_share,
    validate_file_handlers,
    validate_share_target,
)
from pwa_manifest_builder.linter import validate_manifest
from pwa_manifest_builder.mcp_server import handle_jsonrpc_request
from pwa_manifest_builder.cli import main as cli_main


# ============================================================================
# 1. Web Share Target API Validation Tests
# ============================================================================

def test_validate_share_target_valid_get():
    """Test standard GET share target validation."""
    target = {
        "action": "/share-target",
        "method": "GET",
        "params": {
            "title": "share_title",
            "text": "share_text",
            "url": "share_url",
        },
    }
    report = validate_share_target(target, scope="/")
    assert report.is_valid is True
    assert report.action == "/share-target"
    assert report.method == "GET"
    assert report.supports_files is False
    assert len(report.errors) == 0
    assert "URLSearchParams" in report.receiver_script
    assert "navigator.share" in report.share_invoker_script


def test_validate_share_target_valid_post_with_files():
    """Test POST share target validation accepting multipart file payloads."""
    target = {
        "action": "/api/receive-share",
        "method": "POST",
        "enctype": "multipart/form-data",
        "params": {
            "title": "name",
            "text": "description",
            "files": {
                "name": "media",
                "accept": ["image/png", "image/jpeg", ".webp"],
            },
        },
    }
    report = validate_share_target(target, scope="/")
    assert report.is_valid is True
    assert report.method == "POST"
    assert report.enctype == "multipart/form-data"
    assert report.supports_files is True
    assert "image/png" in report.accepted_file_types
    assert ".webp" in report.accepted_file_types
    assert "event.request.formData()" in report.receiver_script
    assert "Response.redirect" in report.receiver_script


def test_validate_share_target_missing_action():
    """Test error when share_target lacks required action URL."""
    target = {
        "method": "GET",
        "params": {"title": "title"},
    }
    report = validate_share_target(target)
    assert report.is_valid is False
    assert any("action" in err.lower() for err in report.errors)


def test_validate_share_target_invalid_method_and_enctype():
    """Test error when method is invalid and files used without multipart/form-data."""
    target = {
        "action": "/share",
        "method": "PATCH",
        "params": {"title": "title"},
    }
    report = validate_share_target(target)
    assert report.is_valid is False
    assert any("method" in err.lower() for err in report.errors)

    # File sharing with GET should fail
    target_files_get = {
        "action": "/share",
        "method": "GET",
        "params": {"files": {"name": "f", "accept": ["image/png"]}},
    }
    rep2 = validate_share_target(target_files_get)
    assert rep2.is_valid is False
    assert any("post" in err.lower() for err in rep2.errors)


def test_validate_share_target_empty_params():
    """Test rejection when params defines neither title, text, url, nor files."""
    target = {
        "action": "/share",
        "method": "GET",
        "params": {},
    }
    report = validate_share_target(target)
    assert report.is_valid is False
    assert any("params" in err.lower() for err in report.errors)


# ============================================================================
# 2. File Handling API Validation Tests
# ============================================================================

def test_validate_file_handlers_valid():
    """Test valid file handler registrations."""
    handlers = [
        {
            "action": "/editor",
            "name": "Markdown Document",
            "accept": {
                "text/markdown": [".md", ".markdown"],
                "text/plain": [".txt"],
            },
            "launch_type": "single-client",
        },
        {
            "action": "/viewer",
            "name": "Image Asset",
            "accept": {
                "image/png": [".png"],
                "image/jpeg": [".jpg", ".jpeg"],
            },
            "launch_type": "multiple-clients",
        },
    ]
    report = validate_file_handlers(handlers, scope="/")
    assert report.is_valid is True
    assert report.valid_count == 2
    assert report.invalid_count == 0
    assert len(report.errors) == 0
    assert "launchQueue" in report.launch_queue_script
    assert "LaunchParams.prototype" in report.launch_queue_script


def test_validate_file_handlers_invalid_accept_format():
    """Test rejection when file extension lacks leading dot or MIME format is invalid."""
    handlers = [
        {
            "action": "/open",
            "accept": {
                "not-a-real-mime": ["md"],  # missing leading dot and invalid MIME
            },
        }
    ]
    report = validate_file_handlers(handlers)
    assert report.is_valid is False
    assert report.invalid_count == 1
    assert any("leading '.'" in err.lower() for err in report.errors)
    assert any("mime" in err.lower() for err in report.errors)


def test_validate_file_handlers_invalid_launch_type():
    """Test rejection of invalid launch_type."""
    handlers = [
        {
            "action": "/open",
            "accept": {"text/plain": [".txt"]},
            "launch_type": "invalid-mode",
        }
    ]
    report = validate_file_handlers(handlers)
    assert report.is_valid is False
    assert any("launch_type" in err.lower() for err in report.errors)


# ============================================================================
# 3. Web Share & File Launch Simulators
# ============================================================================

def test_simulate_web_share_get():
    """Test GET share simulation query generation."""
    target = {
        "action": "/share",
        "method": "GET",
        "params": {"title": "t", "text": "body", "url": "link"},
    }
    res = simulate_web_share(target, title="My Title", text="Hello world", url="https://example.com")
    assert res.matched is True
    assert res.method == "GET"
    assert "/share?t=My+Title&body=Hello+world&link=https%3A%2F%2Fexample.com" in res.simulated_url
    assert res.query_params["t"] == "My Title"
    assert res.query_params["body"] == "Hello world"
    assert "URLSearchParams" in res.client_receiver_code


def test_simulate_web_share_post_files():
    """Test POST share simulation with mock files."""
    target = {
        "action": "/upload-share",
        "method": "POST",
        "enctype": "multipart/form-data",
        "params": {
            "title": "title",
            "files": {"name": "doc", "accept": [".pdf", "application/pdf"]},
        },
    }
    files = [{"name": "report.pdf", "type": "application/pdf", "size": 4096}]
    res = simulate_web_share(target, title="Quarterly Report", files=files)
    assert res.matched is True
    assert res.method == "POST"
    assert res.form_fields["title"] == "Quarterly Report"
    assert len(res.files_payload) == 1
    assert res.files_payload[0]["name"] == "report.pdf"


def test_simulate_file_launch_matching():
    """Test matching file extensions against registered handlers."""
    handlers = [
        {
            "action": "/text-editor",
            "name": "Text Editor",
            "accept": {"text/markdown": [".md"], "text/plain": [".txt"]},
            "launch_type": "single-client",
        },
        {
            "action": "/image-viewer",
            "name": "Image Viewer",
            "accept": {"image/png": [".png"]},
            "launch_type": "multiple-clients",
        },
    ]

    # 1. Match Markdown file
    res1 = simulate_file_launch(handlers, file_name="notes.md")
    assert res1.handled is True
    assert res1.matched_action == "/text-editor"
    assert res1.matched_handler_name == "Text Editor"
    assert res1.launch_type == "single-client"
    assert "notes.md" in res1.consumer_dispatch_code

    # 2. Match PNG image
    res2 = simulate_file_launch(handlers, file_name="screenshot.png")
    assert res2.handled is True
    assert res2.matched_action == "/image-viewer"
    assert res2.launch_type == "multiple-clients"

    # 3. Unhandled file extension
    res3 = simulate_file_launch(handlers, file_name="archive.tar.gz")
    assert res3.handled is False
    assert res3.matched_action is None
    assert len(res3.issues) > 0


# ============================================================================
# 4. PWAManifestConfig Methods & Serialization
# ============================================================================

def test_manifest_config_share_and_file_handler_helpers():
    """Test PWAManifestConfig helper methods and dictionary roundtrip."""
    cfg = PWAManifestConfig(name="Capability App", start_url="/", scope="/")
    
    # Configure share target
    st = cfg.set_share_target(
        action="/share",
        method="POST",
        enctype="multipart/form-data",
        params={"title": "title", "files": {"name": "file", "accept": [".png"]}},
    )
    assert isinstance(st, ShareTargetSpec)
    assert cfg.share_target is not None

    # Configure file handler
    fh = cfg.add_file_handler(
        action="/open",
        name="PNG Viewer",
        accept={"image/png": [".png"]},
        launch_type="single-client",
    )
    assert isinstance(fh, FileHandlerSpec)
    assert len(cfg.file_handlers) == 1

    # Validate methods
    st_rep = cfg.validate_share_target()
    assert st_rep.is_valid is True

    fh_rep = cfg.validate_file_handlers()
    assert fh_rep.is_valid is True

    # Roundtrip serialization
    d = cfg.to_dict()
    assert "share_target" in d
    assert "file_handlers" in d
    assert d["share_target"]["action"] == "/share"
    assert d["file_handlers"][0]["action"] == "/open"

    cfg_restored = PWAManifestConfig.from_dict(d)
    assert isinstance(cfg_restored.share_target, ShareTargetSpec)
    assert isinstance(cfg_restored.file_handlers[0], FileHandlerSpec)
    assert cfg_restored.file_handlers[0].name == "PNG Viewer"


# ============================================================================
# 5. Linter Auditing Integration
# ============================================================================

def test_linter_audits_share_target_and_file_handlers():
    """Test that validate_manifest audits share_target and file_handlers."""
    valid_manifest = {
        "name": "Audit App",
        "short_name": "Audit",
        "start_url": "/",
        "display": "standalone",
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "share_target": {
            "action": "/share",
            "method": "GET",
            "params": {"title": "title", "text": "text", "url": "url"},
        },
        "file_handlers": [
            {
                "action": "/open",
                "name": "Document",
                "accept": {"text/plain": [".txt"]},
                "launch_type": "single-client",
            }
        ],
    }

    report = validate_manifest(valid_manifest)
    assert report.is_valid is True
    assert any("share target" in check.lower() for check in report.passed_checks)
    assert any("file handler" in check.lower() for check in report.passed_checks)

    # Invalid share target test
    invalid_manifest = dict(valid_manifest)
    invalid_manifest["share_target"] = {
        "action": "/share",
        "method": "GET",
        "params": {"files": {"name": "f"}},  # invalid: GET with files
    }
    rep_inv = validate_manifest(invalid_manifest)
    assert any(i.code == "SHARE_TARGET_INVALID" for i in rep_inv.issues)


# ============================================================================
# 6. MCP Protocol Integration
# ============================================================================

def test_mcp_share_and_file_handler_tools():
    """Test MCP tool executions for share target and file handler tools."""
    # 1. pwa_validate_share_target
    req_st = {
        "jsonrpc": "2.0",
        "id": 101,
        "method": "tools/call",
        "params": {
            "name": "pwa_validate_share_target",
            "arguments": {
                "share_target": {
                    "action": "/share",
                    "method": "GET",
                    "params": {"title": "t", "url": "u"},
                }
            },
        },
    }
    res_st = handle_jsonrpc_request(req_st)
    assert isinstance(res_st, dict)
    assert res_st["result"]["isError"] is False
    st_data = json.loads(res_st["result"]["content"][0]["text"])
    assert st_data["is_valid"] is True

    # 2. pwa_validate_file_handlers
    req_fh = {
        "jsonrpc": "2.0",
        "id": 102,
        "method": "tools/call",
        "params": {
            "name": "pwa_validate_file_handlers",
            "arguments": {
                "file_handlers": [
                    {"action": "/open", "accept": {"text/plain": [".txt"]}}
                ]
            },
        },
    }
    res_fh = handle_jsonrpc_request(req_fh)
    assert isinstance(res_fh, dict)
    assert res_fh["result"]["isError"] is False
    fh_data = json.loads(res_fh["result"]["content"][0]["text"])
    assert fh_data["is_valid"] is True

    # 3. pwa_simulate_share
    req_sim_s = {
        "jsonrpc": "2.0",
        "id": 103,
        "method": "tools/call",
        "params": {
            "name": "pwa_simulate_share",
            "arguments": {
                "share_target": {"action": "/share", "params": {"title": "t"}},
                "title": "Cool Article",
            },
        },
    }
    res_sim_s = handle_jsonrpc_request(req_sim_s)
    assert isinstance(res_sim_s, dict)
    sim_s_data = json.loads(res_sim_s["result"]["content"][0]["text"])
    assert sim_s_data["matched"] is True
    assert "Cool+Article" in sim_s_data["simulated_url"]

    # 4. pwa_simulate_file_open
    req_sim_f = {
        "jsonrpc": "2.0",
        "id": 104,
        "method": "tools/call",
        "params": {
            "name": "pwa_simulate_file_open",
            "arguments": {
                "file_handlers": [
                    {"action": "/editor", "accept": {"text/markdown": [".md"]}}
                ],
                "file_name": "readme.md",
            },
        },
    }
    res_sim_f = handle_jsonrpc_request(req_sim_f)
    assert isinstance(res_sim_f, dict)
    sim_f_data = json.loads(res_sim_f["result"]["content"][0]["text"])
    assert sim_f_data["handled"] is True
    assert sim_f_data["matched_action"] == "/editor"

    # 5. Read resource
    req_res = {
        "jsonrpc": "2.0",
        "id": 105,
        "method": "resources/read",
        "params": {"uri": "pwa://specs/share-and-file-handling"},
    }
    res_resource = handle_jsonrpc_request(req_res)
    assert isinstance(res_resource, dict)
    assert "Web Share Target & File Handling APIs Reference" in res_resource["result"]["contents"][0]["text"]

    # 6. Get prompt
    req_prompt = {
        "jsonrpc": "2.0",
        "id": 106,
        "method": "prompts/get",
        "params": {
            "name": "pwa_share_and_file_handler_prompt",
            "arguments": {"app_name": "DocStudio", "file_extensions": ".md,.txt"},
        },
    }
    res_prompt = handle_jsonrpc_request(req_prompt)
    assert isinstance(res_prompt, dict)
    assert "DocStudio" in res_prompt["result"]["messages"][0]["content"]["text"]


# ============================================================================
# 7. CLI Subcommand Tests
# ============================================================================

def test_cli_share_target_command(capsys):
    """Test CLI share-target command execution."""
    code = cli_main(["share-target", "--action", "/share", "--method", "GET", "--json"])
    assert code == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["is_valid"] is True
    assert data["action"] == "/share"

    # Test simulation
    code_sim = cli_main([
        "share-target",
        "--action", "/share",
        "--method", "POST",
        "--enctype", "multipart/form-data",
        "--files-param", "f",
        "--simulate",
        "--share-title", "Doc Title",
        "--json",
    ])
    assert code_sim == 0
    sim_out = capsys.readouterr().out
    sim_data = json.loads(sim_out)
    assert sim_data["matched"] is True


def test_cli_file_handlers_command(capsys):
    """Test CLI file-handlers command execution."""
    code = cli_main([
        "file-handlers",
        "--action", "/open",
        "--accept", "text/plain:.txt,.log",
        "--json",
    ])
    assert code == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["is_valid"] is True
    assert data["valid_count"] == 1

    # Test simulation
    code_sim = cli_main([
        "file-handlers",
        "--action", "/open",
        "--accept", "text/plain:.txt",
        "--simulate", "system.txt",
        "--json",
    ])
    assert code_sim == 0
    sim_out = capsys.readouterr().out
    sim_data = json.loads(sim_out)
    assert sim_data["handled"] is True
    assert sim_data["file_name"] == "system.txt"
