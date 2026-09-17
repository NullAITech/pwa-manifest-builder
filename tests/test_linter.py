"""
Unit tests for pwa_manifest_builder.linter module.
Tests manifest auditing, installability criteria, color validation, and error reporting.
"""

from pathlib import Path
import pytest

from pwa_manifest_builder.linter import (
    is_valid_color,
    validate_manifest,
    lint_manifest_file,
)
from pwa_manifest_builder.models import PWAManifestConfig


def test_is_valid_color():
    assert is_valid_color("#fff") is True
    assert is_valid_color("#1a73e8") is True
    assert is_valid_color("rgb(255, 0, 0)") is True
    assert is_valid_color("transparent") is True
    assert is_valid_color("not-a-color") is False
    assert is_valid_color(None) is False


def test_validate_manifest_valid(sample_manifest_config):
    report = validate_manifest(sample_manifest_config)
    assert report.is_valid is True
    assert report.installable_score >= 80
    assert len(report.errors()) == 0
    assert len(report.passed_checks) >= 5


def test_validate_manifest_errors():
    # Empty manifest dictionary
    report = validate_manifest({})
    assert report.is_valid is False
    assert report.has_errors() is True
    assert report.installable_score < 70
    
    error_codes = [e.code for e in report.errors()]
    assert "ERR_NAME_MISSING" in error_codes
    assert "ERR_START_URL_MISSING" in error_codes
    assert "ERR_NO_ICONS" in error_codes


def test_lint_manifest_file(sample_manifest_config, tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(sample_manifest_config.to_json())
    
    report = lint_manifest_file(manifest_path)
    assert report.is_valid is True
    assert report.installable_score >= 80


def test_lint_manifest_file_missing_or_invalid(tmp_path):
    missing_path = tmp_path / "missing.json"
    report = lint_manifest_file(missing_path)
    assert report.is_valid is False
    assert report.installable_score == 0
    
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("not json content!")
    report2 = lint_manifest_file(invalid_path)
    assert report2.is_valid is False
    assert report2.installable_score == 0
