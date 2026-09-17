"""
Unit tests for pwa_manifest_builder.cli module.
Tests CLI argument parsing, subcommands (generate, sw, icons, audit, meta, templates, diagnostics, test), and stdout/file output.
"""

import json
import sys
from io import StringIO
import pytest

from pwa_manifest_builder.cli import main, build_parser


def test_cli_parser_creation():
    parser = build_parser()
    assert parser.prog == "pwa-manifest-builder"


def test_cli_help():
    assert main(["--help"]) == 0


def test_cli_empty_args():
    assert main([]) == 0


def test_cli_generate_stdout(capsys):
    ret = main([
        "generate",
        "--name", "CLI Test App",
        "--short-name", "CLITest",
        "--theme-color", "#1a73e8",
        "--bg-color", "#ffffff",
        "--display", "standalone",
        "--stdout",
        "--no-color"
    ])
    assert ret == 0
    captured = capsys.readouterr()
    assert "CLI Test App" in captured.out or "CLITest" in captured.out


def test_cli_generate_to_file(tmp_path):
    out_file = tmp_path / "manifest.json"
    ret = main([
        "generate",
        "--name", "File App",
        "--short-name", "FileApp",
        "-o", str(out_file),
        "--no-color"
    ])
    assert ret == 0
    assert out_file.exists()
    content = json.loads(out_file.read_text(encoding="utf-8"))
    assert content["name"] == "File App"


def test_cli_sw_stdout(capsys):
    ret = main([
        "sw",
        "--cache-name", "cli-cache",
        "--strategy", "stale_while_revalidate",
        "--stdout",
        "--no-color"
    ])
    assert ret == 0
    captured = capsys.readouterr()
    assert "cli-cache" in captured.out
    assert "addEventListener('fetch'" in captured.out


def test_cli_icons_generation(tmp_path):
    out_dir = tmp_path / "icons"
    ret = main([
        "icons",
        "--name", "Acme",
        "--bg-color", "#34a853",
        "-o", str(out_dir),
        "--no-color"
    ])
    assert ret == 0


def test_cli_meta_tags(capsys):
    ret = main([
        "meta",
        "--name", "Meta PWA",
        "--theme-color", "#ea4335",
        "--no-color"
    ])
    assert ret == 0
    captured = capsys.readouterr()
    assert '<link rel="manifest"' in captured.out
    assert '<meta name="theme-color" content="#ea4335">' in captured.out


def test_cli_templates_json(capsys):
    ret = main([
        "templates",
        "--json",
        "--no-color"
    ])
    assert ret == 0
    captured = capsys.readouterr()
    assert "ecommerce" in captured.out or "store" in captured.out


def test_cli_diagnostics(capsys):
    ret = main([
        "diagnostics",
        "--json",
        "--no-color"
    ])
    assert ret == 0
    captured = capsys.readouterr()
    assert "python_version" in captured.out


def test_cli_internal_test():
    ret = main([
        "test",
        "--no-color"
    ])
    assert ret == 0
