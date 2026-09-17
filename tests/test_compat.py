"""
Unit tests for pwa_manifest_builder.compat module.
Tests platform detection, path security & normalization, atomic I/O, and JSON serialization.
"""

import os
import sys
import tempfile
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
import pytest

from pwa_manifest_builder.compat import (
    PlatformInfo,
    get_platform_info,
    normalize_path,
    resolve_safe_path,
    ensure_dir,
    atomic_write_bytes,
    atomic_write_text,
    read_text_safe,
    read_json_safe,
    write_json_safe,
    safe_delete,
    _json_default_encoder
)


class DummyEnum(Enum):
    ALPHA = "alpha"
    BETA = "beta"


@dataclass
class DummyData:
    name: str
    count: int


def test_get_platform_info():
    info = get_platform_info()
    assert isinstance(info, PlatformInfo)
    assert info.os_name in ("Linux", "Darwin", "Windows", "Java", "")
    assert isinstance(info.is_windows, bool)
    assert isinstance(info.is_macos, bool)
    assert isinstance(info.is_linux, bool)
    assert isinstance(info.python_version, str)
    assert info.path_separator == os.sep
    assert os.path.exists(info.home_dir)


def test_normalize_path(tmp_path):
    p = normalize_path(str(tmp_path))
    assert isinstance(p, Path)
    assert p.is_absolute()


def test_resolve_safe_path(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    
    # Safe sub path
    safe = resolve_safe_path(base, "sub/file.txt")
    assert str(safe).startswith(str(base))
    
    # Unsafe path traversal
    with pytest.raises(ValueError, match="Path traversal detected"):
        resolve_safe_path(base, "../../etc/passwd")


def test_ensure_dir(tmp_path):
    target = tmp_path / "nested" / "deep" / "dir"
    res = ensure_dir(target)
    assert res.is_dir()
    assert res.exists()


def test_atomic_write_and_read_text(tmp_path):
    target = tmp_path / "test.txt"
    content = "Hello Google PWA Studio 🚀"
    
    atomic_write_text(target, content)
    assert target.exists()
    
    read_back = read_text_safe(target)
    assert read_back == content


def test_atomic_write_and_read_bytes(tmp_path):
    target = tmp_path / "test.bin"
    content = b"\x00\x01\x02\x03\xFF"
    
    atomic_write_bytes(target, content)
    assert target.exists()
    assert target.read_bytes() == content


def test_read_text_safe_nonexistent(tmp_path):
    target = tmp_path / "does_not_exist.txt"
    assert read_text_safe(target, default="fallback") == "fallback"


def test_json_safe_roundtrip(tmp_path):
    target = tmp_path / "data.json"
    data = {
        "title": "PWA Builder",
        "nested": {"key": 123},
        "enum_val": DummyEnum.BETA,
        "dataclass_val": DummyData(name="test", count=42),
        "path_val": Path("/tmp/test"),
        "set_val": {"a", "b"}
    }
    
    write_json_safe(target, data)
    assert target.exists()
    
    loaded = read_json_safe(target)
    assert loaded["title"] == "PWA Builder"
    assert loaded["nested"]["key"] == 123
    assert loaded["enum_val"] == "beta"
    assert loaded["dataclass_val"] == {"name": "test", "count": 42}
    assert isinstance(loaded["set_val"], list)


def test_read_json_safe_invalid_or_missing(tmp_path):
    target = tmp_path / "invalid.json"
    target.write_text("{ broken json: true")
    assert read_json_safe(target, default={}) == {}
    
    missing = tmp_path / "missing.json"
    assert read_json_safe(missing, default=None) is None


def test_json_default_encoder_type_error():
    class Unserializable:
        pass
    with pytest.raises(TypeError):
        _json_default_encoder(Unserializable())


def test_safe_delete_file_and_dir(tmp_path):
    # Test file deletion
    f = tmp_path / "temp.txt"
    f.write_text("delete me")
    assert f.exists()
    assert safe_delete(f) is True
    assert not f.exists()
    
    # Test directory deletion
    d = tmp_path / "temp_dir"
    d.mkdir()
    (d / "sub.txt").write_text("sub")
    assert d.exists()
    assert safe_delete(d) is True
    assert not d.exists()
    
    # Test missing file delete
    missing = tmp_path / "no_file.txt"
    assert safe_delete(missing, missing_ok=True) is True
