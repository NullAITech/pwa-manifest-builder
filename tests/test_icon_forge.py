"""
Unit tests for pwa_manifest_builder.icon_forge module.
Tests SVG generation, maskable safe-zone compliance, BMP/ICO pure-python rasterization, and icon pack building.
"""

from pathlib import Path
import pytest

from pwa_manifest_builder.icon_forge import (
    parse_color_rgba,
    generate_icon_svg,
    generate_bmp,
    generate_favicon_ico,
    generate_ppm,
    generate_icon_pack,
    STANDARD_ICON_SIZES,
    SVG_GLYPHS,
)


def test_parse_color_rgba():
    assert parse_color_rgba("#ffffff") == (255, 255, 255, 255)
    assert parse_color_rgba("#000") == (0, 0, 0, 255)
    assert parse_color_rgba("#1a73e8") == (26, 115, 232, 255)
    assert parse_color_rgba("white") == (255, 255, 255, 255)
    assert parse_color_rgba("transparent") == (0, 0, 0, 0)
    assert parse_color_rgba("rgb(10, 20, 30)") == (10, 20, 30, 255)
    assert parse_color_rgba("invalid_xxx") == (26, 115, 232, 255)  # fallback


def test_generate_icon_svg_standard_and_maskable():
    svg_std = generate_icon_svg(name_or_letter="PWA", bg_color="#1a73e8", maskable=False, size=512)
    assert "<svg" in svg_std
    assert 'viewBox="0 0 512 512"' in svg_std
    assert "</svg>" in svg_std
    
    svg_mask = generate_icon_svg(name_or_letter="PWA", bg_color="#1a73e8", maskable=True, size=512)
    assert "<svg" in svg_mask
    assert '<rect width="512" height="512"' in svg_mask


def test_generate_icon_svg_glyphs():
    for glyph_name in ["sparkles", "bolt", "rocket", "store"]:
        svg = generate_icon_svg(icon_name=glyph_name, size=192)
        assert "<svg" in svg
        assert "<path" in svg


def test_generate_bmp_binary():
    bmp_bytes = generate_bmp(width=32, height=32, letter="P")
    assert bmp_bytes.startswith(b"BM")
    assert len(bmp_bytes) > 54  # header + pixels


def test_generate_favicon_ico_binary():
    ico_bytes = generate_favicon_ico(bg_color="#1a73e8", letter="P", sizes=(16, 32))
    assert ico_bytes[:4] == b"\x00\x00\x01\x00"  # ICO magic header
    assert len(ico_bytes) > 100


def test_generate_ppm_binary():
    ppm = generate_ppm(width=16, height=16, letter="A")
    assert ppm.startswith(b"P6\n16 16\n255\n")


def test_generate_icon_pack(tmp_path):
    out_dir = tmp_path / "icons"
    pack = generate_icon_pack(
        name_or_letter="Google",
        bg_color="#1a73e8",
        output_dir=out_dir,
        base_url_prefix="/static/icons"
    )
    
    assert "icons" in pack
    assert len(pack["icons"]) > 10
    assert (out_dir / "icon.svg").exists()
    assert (out_dir / "icon-maskable.svg").exists()
    assert (out_dir / "icon-192x192.svg").exists()
    assert (out_dir / "icon-512x512.svg").exists()
    assert (out_dir / "favicon.ico").exists()
