"""
Cross-platform compatibility utilities for pwa-manifest-builder.

Provides atomic file I/O, robust path normalization across POSIX, Windows, macOS,
and Android/Termux environments, safe encodings, and platform introspection.
100% Python Standard Library.
"""

from __future__ import annotations

import os
import sys
import json
import shutil
import tempfile
import platform
from dataclasses import dataclass, asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass(frozen=True)
class PlatformInfo:
    """System platform and runtime environment metadata."""
    os_name: str
    is_windows: bool
    is_macos: bool
    is_linux: bool
    is_termux: bool
    is_android: bool
    python_version: str
    path_separator: str
    home_dir: str


def get_platform_info() -> PlatformInfo:
    """
    Detects and returns metadata about the current OS and Python environment.
    Handles Linux, macOS, Windows, and Android/Termux.
    """
    sys_name = platform.system()
    is_win = sys_name == "Windows"
    is_mac = sys_name == "Darwin"
    is_lin = sys_name == "Linux"
    
    # Check for Termux or Android environment
    is_termux = bool(
        os.environ.get("TERMUX_VERSION") or 
        os.path.exists("/data/data/com.termux") or
        "com.termux" in os.environ.get("PREFIX", "")
    )
    is_android = is_termux or "ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ

    return PlatformInfo(
        os_name=sys_name,
        is_windows=is_win,
        is_macos=is_mac,
        is_linux=is_lin,
        is_termux=is_termux,
        is_android=is_android,
        python_version=platform.python_version(),
        path_separator=os.sep,
        home_dir=str(Path.home())
    )


def normalize_path(path: Union[str, Path]) -> Path:
    """
    Expands user home directory and returns a resolved, normalized Path object.
    Safe against non-existent paths (calls resolve() without strict=True).
    """
    if isinstance(path, str):
        path_obj = Path(os.path.expanduser(os.path.expandvars(path)))
    else:
        path_obj = path.expanduser()
    try:
        return path_obj.resolve()
    except (RuntimeError, OSError):
        return path_obj.absolute()


def resolve_safe_path(base_dir: Union[str, Path], sub_path: Union[str, Path]) -> Path:
    """
    Resolves a sub-path relative to a base directory, preventing path traversal attacks.
    Raises ValueError if sub_path escapes base_dir.
    """
    base = normalize_path(base_dir)
    target = normalize_path(base / sub_path)
    
    try:
        target.relative_to(base)
    except ValueError:
        raise ValueError(f"Path traversal detected: '{sub_path}' is outside base directory '{base}'")
    
    return target


def ensure_dir(dir_path: Union[str, Path]) -> Path:
    """
    Recursively creates the directory path if it does not exist.
    Returns the resolved Path object.
    """
    p = normalize_path(dir_path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def atomic_write_bytes(
    file_path: Union[str, Path],
    content: bytes,
    fsync: bool = True
) -> Path:
    """
    Writes binary content to a file atomically via a temporary file in the same directory.
    Flushes and fsyncs to disk before atomic replace to prevent data corruption.
    """
    dest_path = normalize_path(file_path)
    parent_dir = dest_path.parent
    ensure_dir(parent_dir)

    temp_file = tempfile.NamedTemporaryFile(
        dir=parent_dir,
        prefix=f".tmp_{dest_path.name}_",
        delete=False
    )
    temp_path = Path(temp_file.name)

    try:
        temp_file.write(content)
        temp_file.flush()
        if fsync:
            os.fsync(temp_file.fileno())
        temp_file.close()

        # Atomic rename/replace
        os.replace(temp_path, dest_path)
        return dest_path
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def atomic_write_text(
    file_path: Union[str, Path],
    content: str,
    encoding: str = "utf-8",
    fsync: bool = True
) -> Path:
    """
    Writes string content to a text file atomically using the specified encoding.
    """
    return atomic_write_bytes(
        file_path=file_path,
        content=content.encode(encoding),
        fsync=fsync
    )


def read_text_safe(
    file_path: Union[str, Path],
    default: str = "",
    encodings: Tuple[str, ...] = ("utf-8", "utf-8-sig", "latin-1", "cp1252")
) -> str:
    """
    Safely reads text from a file, attempting multiple encodings if needed.
    Returns `default` if file does not exist or cannot be read.
    """
    p = normalize_path(file_path)
    if not p.is_file():
        return default

    for enc in encodings:
        try:
            return p.read_text(encoding=enc)
        except (UnicodeDecodeError, OSError):
            continue
    
    # Fallback to reading bytes and ignoring errors
    try:
        return p.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return default


def _json_default_encoder(obj: Any) -> Any:
    """Encoder helper for dataclasses, enums, paths and sets in JSON serialization."""
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def read_json_safe(
    file_path: Union[str, Path],
    default: Any = None,
    encodings: Tuple[str, ...] = ("utf-8", "utf-8-sig")
) -> Any:
    """
    Reads and parses a JSON file safely.
    Returns `default` if the file does not exist or JSON parsing fails.
    """
    text = read_text_safe(file_path, default="", encodings=encodings)
    if not text.strip():
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def write_json_safe(
    file_path: Union[str, Path],
    data: Any,
    indent: int = 2,
    ensure_ascii: bool = False
) -> Path:
    """
    Serializes data to formatted JSON and writes atomically to disk.
    Supports dataclasses, Enums, Paths, and standard collections.
    """
    json_str = json.dumps(
        data,
        indent=indent,
        ensure_ascii=ensure_ascii,
        default=_json_default_encoder
    )
    # Ensure trailing newline for clean POSIX files
    if not json_str.endswith("\n"):
        json_str += "\n"
    return atomic_write_text(file_path, json_str, encoding="utf-8")


def safe_delete(file_or_dir_path: Union[str, Path], missing_ok: bool = True) -> bool:
    """
    Safely deletes a file or directory tree.
    Returns True if deletion succeeded or target did not exist (when missing_ok=True).
    """
    p = normalize_path(file_or_dir_path)
    if not p.exists():
        return missing_ok

    try:
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)
        else:
            p.unlink()
        return True
    except OSError:
        return False
