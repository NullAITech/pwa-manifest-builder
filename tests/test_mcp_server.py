"""
Unit tests for pwa_manifest_builder.mcp_server module.
Tests JSON-RPC 2.0 protocol compliance, initialization, tools listing, tool execution, and error handling.
"""

import json
import pytest

from pwa_manifest_builder.mcp_server import (
    handle_jsonrpc_request,
    SERVER_NAME,
    SERVER_VERSION,
)


def test_mcp_initialize():
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"}
        }
    }
    resp = handle_jsonrpc_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert "result" in resp
    assert resp["result"]["serverInfo"]["name"] == SERVER_NAME


def test_mcp_tools_list():
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    resp = handle_jsonrpc_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 2
    tools = resp["result"]["tools"]
    assert len(tools) >= 5
    tool_names = [t["name"] for t in tools]
    assert any("manifest" in name for name in tool_names)


def test_mcp_tools_call_generate_manifest():
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "pwa_generate_manifest",
            "arguments": {
                "name": "Test MCP App",
                "short_name": "MCPApp",
                "theme_color": "#1a73e8"
            }
        }
    }
    resp = handle_jsonrpc_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 3
    assert "result" in resp
    content = resp["result"]["content"]
    assert len(content) > 0
    text = content[0]["text"]
    assert "Test MCP App" in text


def test_mcp_invalid_method_and_parse_error():
    req = {
        "jsonrpc": "2.0",
        "id": 99,
        "method": "non_existent_method_xyz",
        "params": {}
    }
    resp = handle_jsonrpc_request(req)
    assert "error" in resp
    assert resp["error"]["code"] == -32601  # Method not found
    
    # Parse error test
    bad_resp = handle_jsonrpc_request("{ invalid json")
    assert "error" in bad_resp
    assert bad_resp["error"]["code"] == -32700  # Parse error


def test_mcp_batch_request():
    batch = [
        {"jsonrpc": "2.0", "id": 10, "method": "ping", "params": {}},
        {"jsonrpc": "2.0", "id": 11, "method": "ping", "params": {}}
    ]
    resp = handle_jsonrpc_request(batch)
    assert isinstance(resp, list)
    assert len(resp) == 2
    assert resp[0]["id"] == 10
    assert resp[1]["id"] == 11
