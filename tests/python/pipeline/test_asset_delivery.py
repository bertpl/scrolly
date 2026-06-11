"""Tests for scrolly.pipeline.assets — asset delivery step."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from scrolly._shared.mime import _EXT_TO_MIME
from scrolly.errors import SlideSourceError
from scrolly.pipeline._bundler import PayloadBundler
from scrolly.pipeline.assets import copy_assets, rewrite_asset_refs
from scrolly.slide.html import SlideHTML


def _chunk(
    html: str = "<p>hi</p>",
    scoped_css: str = "",
    assets: tuple[Path, ...] = (),
) -> SlideHTML:
    return SlideHTML(title="T", html=html, scoped_css=scoped_css, assets=assets)


def _write_file(path: Path, content: str = "data") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


# --------------------------------------------------------------------------
#  rewrite_asset_refs — external (inline=False) mode
# --------------------------------------------------------------------------
def test_no_assets_returns_chunk_unchanged_external() -> None:
    chunk = _chunk()
    result = rewrite_asset_refs({"s": chunk}, inline=False)
    assert result["s"] is chunk


def test_rewrites_html_references(tmp_path: Path) -> None:
    src = _write_file(tmp_path / "src" / "bg.png")
    chunk = _chunk(
        html='<img src="__asset__/bg.png">',
        assets=(src,),
    )
    result = rewrite_asset_refs({"s1": chunk}, inline=False)
    assert "__asset__/" not in result["s1"].html
    assert "_assets/s1/bg.png" in result["s1"].html


def test_rewrites_scoped_css_references(tmp_path: Path) -> None:
    src = _write_file(tmp_path / "src" / "bg.png")
    chunk = _chunk(
        scoped_css="background: url(__asset__/bg.png);",
        assets=(src,),
    )
    result = rewrite_asset_refs({"s1": chunk}, inline=False)
    assert "__asset__/" not in result["s1"].scoped_css
    assert "_assets/s1/bg.png" in result["s1"].scoped_css


def test_same_filename_different_slides_rewritten_separately(tmp_path: Path) -> None:
    f1 = _write_file(tmp_path / "slide1" / "bg.png", "slide1-data")
    f2 = _write_file(tmp_path / "slide2" / "bg.png", "slide2-data")
    chunks = {
        "s1": _chunk(html='<img src="__asset__/bg.png">', assets=(f1,)),
        "s2": _chunk(html='<img src="__asset__/bg.png">', assets=(f2,)),
    }
    result = rewrite_asset_refs(chunks, inline=False)
    assert "_assets/s1/bg.png" in result["s1"].html
    assert "_assets/s2/bg.png" in result["s2"].html


# --------------------------------------------------------------------------
#  rewrite_asset_refs — inline (data URI) mode
# --------------------------------------------------------------------------
def test_no_assets_returns_chunk_unchanged_inline() -> None:
    chunk = _chunk()
    result = rewrite_asset_refs({"s": chunk})
    assert result["s"] is chunk


def test_inlines_html_references_as_data_uri(tmp_path: Path) -> None:
    src = tmp_path / "bg.png"
    src.write_bytes(b"\x89PNG fake")
    chunk = _chunk(html='<img src="__asset__/bg.png">', assets=(src,))
    result = rewrite_asset_refs({"s1": chunk})
    assert "__asset__/" not in result["s1"].html
    assert "data:image/png;base64," in result["s1"].html


def test_inlines_scoped_css_references(tmp_path: Path) -> None:
    src = tmp_path / "bg.jpg"
    src.write_bytes(b"\xff\xd8\xff fake jpeg")
    chunk = _chunk(scoped_css="background: url(__asset__/bg.jpg);", assets=(src,))
    result = rewrite_asset_refs({"s1": chunk})
    assert "data:image/jpeg;base64," in result["s1"].scoped_css


def test_inlines_svg(tmp_path: Path) -> None:
    src = tmp_path / "icon.svg"
    src.write_text("<svg></svg>")
    chunk = _chunk(html='<img src="__asset__/icon.svg">', assets=(src,))
    result = rewrite_asset_refs({"s1": chunk})
    assert "data:image/svg+xml;base64," in result["s1"].html


def test_data_uri_decodes_to_original_content(tmp_path: Path) -> None:
    content = b"\x89PNG\r\n\x1a\nreal png data here"
    src = tmp_path / "img.png"
    src.write_bytes(content)
    chunk = _chunk(html='<img src="__asset__/img.png">', assets=(src,))
    result = rewrite_asset_refs({"s1": chunk})
    import base64

    uri = result["s1"].html.split('"')[1]
    encoded = uri.split(",", 1)[1]
    assert base64.b64decode(encoded) == content


def test_unsupported_extension_raises(tmp_path: Path) -> None:
    src = tmp_path / "data.bin"
    src.write_bytes(b"binary")
    chunk = _chunk(html='<img src="__asset__/data.bin">', assets=(src,))
    with pytest.raises(SlideSourceError, match="unsupported image format"):
        rewrite_asset_refs({"s1": chunk})


# --------------------------------------------------------------------------
#  copy_assets
# --------------------------------------------------------------------------
def test_copies_file_to_correct_path(tmp_path: Path) -> None:
    src = _write_file(tmp_path / "src" / "hero.jpg")
    chunk = _chunk(
        html='<img src="_assets/intro/hero.jpg">',
        assets=(src,),
    )
    out = tmp_path / "out"
    out.mkdir()
    copy_assets({"intro": chunk}, out)
    assert (out / "_assets" / "intro" / "hero.jpg").exists()


def test_multiple_assets_all_copied(tmp_path: Path) -> None:
    a = _write_file(tmp_path / "src" / "a.jpg")
    b = _write_file(tmp_path / "src" / "b.svg")
    chunk = _chunk(assets=(a, b))
    out = tmp_path / "out"
    out.mkdir()
    copy_assets({"s": chunk}, out)
    assert (out / "_assets" / "s" / "a.jpg").exists()
    assert (out / "_assets" / "s" / "b.svg").exists()


def test_same_filename_different_slides_separate_dirs(tmp_path: Path) -> None:
    f1 = _write_file(tmp_path / "slide1" / "bg.png", "slide1-data")
    f2 = _write_file(tmp_path / "slide2" / "bg.png", "slide2-data")
    chunks = {
        "s1": _chunk(assets=(f1,)),
        "s2": _chunk(assets=(f2,)),
    }
    out = tmp_path / "out"
    out.mkdir()
    copy_assets(chunks, out)
    assert (out / "_assets" / "s1" / "bg.png").read_text() == "slide1-data"
    assert (out / "_assets" / "s2" / "bg.png").read_text() == "slide2-data"


def test_preserves_file_content(tmp_path: Path) -> None:
    content = b"\x89PNG\r\n\x1a\n fake png data"
    src = tmp_path / "src" / "image.png"
    src.parent.mkdir(parents=True)
    src.write_bytes(content)
    chunk = _chunk(assets=(src,))
    out = tmp_path / "out"
    out.mkdir()
    copy_assets({"s": chunk}, out)
    assert (out / "_assets" / "s" / "image.png").read_bytes() == content


def test_skips_chunks_without_assets(tmp_path: Path) -> None:
    src = _write_file(tmp_path / "src" / "hero.jpg")
    chunks = {
        "plain": _chunk(),
        "rich": _chunk(assets=(src,)),
    }
    out = tmp_path / "out"
    out.mkdir()
    copy_assets(chunks, out)
    assert not (out / "_assets" / "plain").exists()
    assert (out / "_assets" / "rich" / "hero.jpg").exists()


# --------------------------------------------------------------------------
#  MIME-type coverage
#
#  Parametrized coverage of every entry in ``_EXT_TO_MIME``.
#
#  Guards against silent regressions when a format is added to or removed
#  from the supported set: every entry must round-trip cleanly through both
#  the inline (``data:`` URI) and external-asset (file copy) paths.
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("ext", "expected_mime"), sorted(_EXT_TO_MIME.items()))
def test_inline_data_uri_uses_correct_mime(
    tmp_path: Path,
    ext: str,
    expected_mime: str,
) -> None:
    # --- arrange ----------------------
    src = tmp_path / f"asset{ext}"
    src.write_bytes(b"sentinel-payload")
    chunk = _chunk(html=f'<img src="__asset__/asset{ext}">', assets=(src,))

    # --- act --------------------------
    result = rewrite_asset_refs({"s1": chunk})

    # --- assert -----------------------
    assert f"data:{expected_mime};base64," in result["s1"].html


@pytest.mark.parametrize("ext", sorted(_EXT_TO_MIME))
def test_external_mode_rewrites_ref(tmp_path: Path, ext: str) -> None:
    # --- arrange ----------------------
    src = _write_file(tmp_path / "src" / f"asset{ext}")
    chunk = _chunk(html=f'<img src="__asset__/asset{ext}">', assets=(src,))

    # --- act --------------------------
    result = rewrite_asset_refs({"s1": chunk}, inline=False)

    # --- assert -----------------------
    assert "__asset__/" not in result["s1"].html
    assert f"_assets/s1/asset{ext}" in result["s1"].html


@pytest.mark.parametrize("ext", sorted(_EXT_TO_MIME))
def test_copy_assets_copies_file(tmp_path: Path, ext: str) -> None:
    # --- arrange ----------------------
    content = b"\x00\x01\x02 fake bytes"
    src = tmp_path / "src" / f"asset{ext}"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(content)
    chunk = _chunk(assets=(src,))
    out = tmp_path / "out"
    out.mkdir()

    # --- act --------------------------
    copy_assets({"s": chunk}, out)

    # --- assert -----------------------
    assert (out / "_assets" / "s" / f"asset{ext}").read_bytes() == content


# --------------------------------------------------------------------------
#  Bundler wiring
# --------------------------------------------------------------------------
def test_img_ref_with_bundler_emits_data_scrolly_target(tmp_path: Path) -> None:
    # --- arrange ----------------------------
    svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
    src = tmp_path / "icon.svg"
    src.write_bytes(svg_content)
    chunk = _chunk(html='<img src="__asset__/icon.svg" alt="">', assets=(src,))
    bundler = PayloadBundler()

    # --- act --------------------------------
    result = rewrite_asset_refs({"s1": chunk}, bundler=bundler)

    # --- assert ------------------------------
    assert 'data-scrolly-target="0"' in result["s1"].html
    assert 'src="' not in result["s1"].html
    assert "__asset__/" not in result["s1"].html


def test_bundler_registers_blob_payload_with_correct_mime(tmp_path: Path) -> None:
    # --- arrange ----------------------------
    svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
    src = tmp_path / "icon.svg"
    src.write_bytes(svg_content)
    chunk = _chunk(html='<img src="__asset__/icon.svg" alt="">', assets=(src,))
    bundler = PayloadBundler()

    # --- act --------------------------------
    rewrite_asset_refs({"s1": chunk}, bundler=bundler)

    # --- assert ------------------------------
    # The payload is stored on the bundler — visible via inline_fallback,
    # which reproduces the equivalent inline form.
    fallback = bundler.inline_fallback()
    assert fallback == {"0": f'src="data:image/svg+xml;base64,{base64.b64encode(svg_content).decode("ascii")}"'}


def test_raster_asset_also_registered_with_bundler(tmp_path: Path) -> None:
    # No mime-based pre-filter: raster goes through the bundler too,
    # so that duplicate raster assets can dedup.
    # --- arrange ----------------------------
    src = tmp_path / "photo.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 100)
    chunk = _chunk(html='<img src="__asset__/photo.png" alt="">', assets=(src,))
    bundler = PayloadBundler()

    # --- act --------------------------------
    result = rewrite_asset_refs({"s1": chunk}, bundler=bundler)

    # --- assert ------------------------------
    assert 'data-scrolly-target="0"' in result["s1"].html
    assert bundler.inline_fallback()["0"].startswith('src="data:image/png;base64,')


def test_duplicate_img_dedups_to_one_payload(tmp_path: Path) -> None:
    # --- arrange ----------------------------
    svg_content = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        + b'<rect x="0" y="0" width="100" height="100" fill="red"/>' * 30
        + b"</svg>"
    )
    src1 = tmp_path / "a" / "icon.svg"
    src2 = tmp_path / "b" / "icon.svg"
    src1.parent.mkdir(parents=True)
    src2.parent.mkdir(parents=True)
    src1.write_bytes(svg_content)
    src2.write_bytes(svg_content)
    chunks = {
        "s1": _chunk(html='<img src="__asset__/icon.svg">', assets=(src1,)),
        "s2": _chunk(html='<img src="__asset__/icon.svg">', assets=(src2,)),
    }
    bundler = PayloadBundler()

    # --- act --------------------------------
    result = rewrite_asset_refs(chunks, bundler=bundler)
    import json as _json

    manifest = _json.loads(bundler.manifest_and_stream()[0])

    # --- assert ------------------------------
    # Two distinct targets (one per <img>), but a single payload entry
    # — the bundler dedups identical bytes.
    assert len(manifest["targets"]) == 2
    assert len(manifest["payloads"]) == 1
    assert 'data-scrolly-target="0"' in result["s1"].html
    assert 'data-scrolly-target="1"' in result["s2"].html


def test_css_refs_always_use_data_uri_even_with_bundler(tmp_path: Path) -> None:
    # --- arrange ----------------------------
    svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
    src = tmp_path / "bg.svg"
    src.write_bytes(svg_content)
    chunk = _chunk(
        html="<p>no img ref</p>",
        scoped_css="background: url(__asset__/bg.svg);",
        assets=(src,),
    )
    bundler = PayloadBundler()

    # --- act --------------------------------
    result = rewrite_asset_refs({"s1": chunk}, bundler=bundler)

    # --- assert ------------------------------
    assert "data:image/svg+xml;base64," in result["s1"].scoped_css
    assert "data-scrolly-target" not in result["s1"].scoped_css


def test_no_bundler_emits_plain_data_uri(tmp_path: Path) -> None:
    # --- arrange ----------------------------
    src = tmp_path / "icon.svg"
    src.write_bytes(b"<svg></svg>")
    chunk = _chunk(html='<img src="__asset__/icon.svg" alt="">', assets=(src,))

    # --- act --------------------------------
    result = rewrite_asset_refs({"s1": chunk})

    # --- assert ------------------------------
    assert "data:image/svg+xml;base64," in result["s1"].html
    assert "data-scrolly-target" not in result["s1"].html


def test_bundled_img_preserves_other_attributes(tmp_path: Path) -> None:
    # --- arrange ----------------------------
    svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
    src = tmp_path / "frame.svg"
    src.write_bytes(svg_content)
    chunk = _chunk(
        html='<img data-frame-index="0" src="__asset__/frame.svg" alt="">',
        assets=(src,),
    )
    bundler = PayloadBundler()

    # --- act --------------------------------
    result = rewrite_asset_refs({"s1": chunk}, bundler=bundler)

    # --- assert ------------------------------
    assert 'data-frame-index="0"' in result["s1"].html
    assert 'alt=""' in result["s1"].html
    assert 'data-scrolly-target="0"' in result["s1"].html


def test_inline_false_ignores_bundler(tmp_path: Path) -> None:
    # --- arrange ----------------------------
    src = _write_file(tmp_path / "src" / "bg.svg")
    chunk = _chunk(html='<img src="__asset__/bg.svg">', assets=(src,))
    bundler = PayloadBundler()

    # --- act --------------------------------
    result = rewrite_asset_refs({"s1": chunk}, inline=False, bundler=bundler)

    # --- assert ------------------------------
    assert "data-scrolly-target" not in result["s1"].html
    assert "_assets/s1/bg.svg" in result["s1"].html
    # Bundler is unused when inline=False.
    assert bundler.inline_fallback() == {}


# --------------------------------------------------------------------------
#  Validation
# --------------------------------------------------------------------------
def test_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "no_such_file.jpg"
    chunk = _chunk(assets=(missing,))
    with pytest.raises(SlideSourceError, match="does not exist"):
        rewrite_asset_refs({"s": chunk})


def test_duplicate_filename_raises(tmp_path: Path) -> None:
    f1 = _write_file(tmp_path / "dir1" / "img.jpg")
    f2 = _write_file(tmp_path / "dir2" / "img.jpg")
    chunk = _chunk(assets=(f1, f2))
    with pytest.raises(SlideSourceError, match="duplicate"):
        rewrite_asset_refs({"s": chunk})


def test_dotdot_filename_raises(tmp_path: Path) -> None:
    bad = tmp_path / ".."
    bad.mkdir(exist_ok=True)
    chunk = _chunk(assets=(bad,))
    with pytest.raises(SlideSourceError, match="invalid"):
        rewrite_asset_refs({"s": chunk})
