"""Tests for scrolly.pipeline.assets — asset delivery step."""

from __future__ import annotations

from pathlib import Path

import pytest

from scrolly.errors import SlideSourceError
from scrolly.pipeline.assets import _MIME_TYPES, copy_assets, rewrite_asset_refs
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


class TestRewriteAssetRefsNoInline:
    def test_no_assets_returns_chunk_unchanged(self) -> None:
        chunk = _chunk()
        result, _ = rewrite_asset_refs({"s": chunk}, inline=False)
        assert result["s"] is chunk

    def test_rewrites_html_references(self, tmp_path: Path) -> None:
        src = _write_file(tmp_path / "src" / "bg.png")
        chunk = _chunk(
            html='<img src="__asset__/bg.png">',
            assets=(src,),
        )
        result, _ = rewrite_asset_refs({"s1": chunk}, inline=False)
        assert "__asset__/" not in result["s1"].html
        assert "_assets/s1/bg.png" in result["s1"].html

    def test_rewrites_scoped_css_references(self, tmp_path: Path) -> None:
        src = _write_file(tmp_path / "src" / "bg.png")
        chunk = _chunk(
            scoped_css="background: url(__asset__/bg.png);",
            assets=(src,),
        )
        result, _ = rewrite_asset_refs({"s1": chunk}, inline=False)
        assert "__asset__/" not in result["s1"].scoped_css
        assert "_assets/s1/bg.png" in result["s1"].scoped_css

    def test_same_filename_different_slides_rewritten_separately(self, tmp_path: Path) -> None:
        f1 = _write_file(tmp_path / "slide1" / "bg.png", "slide1-data")
        f2 = _write_file(tmp_path / "slide2" / "bg.png", "slide2-data")
        chunks = {
            "s1": _chunk(html='<img src="__asset__/bg.png">', assets=(f1,)),
            "s2": _chunk(html='<img src="__asset__/bg.png">', assets=(f2,)),
        }
        result, _ = rewrite_asset_refs(chunks, inline=False)
        assert "_assets/s1/bg.png" in result["s1"].html
        assert "_assets/s2/bg.png" in result["s2"].html


class TestRewriteAssetRefsInline:
    def test_no_assets_returns_chunk_unchanged(self) -> None:
        chunk = _chunk()
        result, _ = rewrite_asset_refs({"s": chunk})
        assert result["s"] is chunk

    def test_inlines_html_references_as_data_uri(self, tmp_path: Path) -> None:
        src = tmp_path / "bg.png"
        src.write_bytes(b"\x89PNG fake")
        chunk = _chunk(html='<img src="__asset__/bg.png">', assets=(src,))
        result, _ = rewrite_asset_refs({"s1": chunk}, compress=False)
        assert "__asset__/" not in result["s1"].html
        assert "data:image/png;base64," in result["s1"].html

    def test_inlines_scoped_css_references(self, tmp_path: Path) -> None:
        src = tmp_path / "bg.jpg"
        src.write_bytes(b"\xff\xd8\xff fake jpeg")
        chunk = _chunk(scoped_css="background: url(__asset__/bg.jpg);", assets=(src,))
        result, _ = rewrite_asset_refs({"s1": chunk})
        assert "data:image/jpeg;base64," in result["s1"].scoped_css

    def test_inlines_svg(self, tmp_path: Path) -> None:
        src = tmp_path / "icon.svg"
        src.write_text("<svg></svg>")
        chunk = _chunk(html='<img src="__asset__/icon.svg">', assets=(src,))
        result, _ = rewrite_asset_refs({"s1": chunk}, compress=False)
        assert "data:image/svg+xml;base64," in result["s1"].html

    def test_data_uri_decodes_to_original_content(self, tmp_path: Path) -> None:
        content = b"\x89PNG\r\n\x1a\nreal png data here"
        src = tmp_path / "img.png"
        src.write_bytes(content)
        chunk = _chunk(html='<img src="__asset__/img.png">', assets=(src,))
        result, _ = rewrite_asset_refs({"s1": chunk}, compress=False)
        import base64

        uri = result["s1"].html.split('"')[1]
        encoded = uri.split(",", 1)[1]
        assert base64.b64decode(encoded) == content

    def test_unsupported_extension_raises(self, tmp_path: Path) -> None:
        src = tmp_path / "data.bin"
        src.write_bytes(b"binary")
        chunk = _chunk(html='<img src="__asset__/data.bin">', assets=(src,))
        with pytest.raises(SlideSourceError, match="unsupported image format"):
            rewrite_asset_refs({"s1": chunk})


class TestCopyAssets:
    def test_copies_file_to_correct_path(self, tmp_path: Path) -> None:
        src = _write_file(tmp_path / "src" / "hero.jpg")
        chunk = _chunk(
            html='<img src="_assets/intro/hero.jpg">',
            assets=(src,),
        )
        out = tmp_path / "out"
        out.mkdir()
        copy_assets({"intro": chunk}, out)
        assert (out / "_assets" / "intro" / "hero.jpg").exists()

    def test_multiple_assets_all_copied(self, tmp_path: Path) -> None:
        a = _write_file(tmp_path / "src" / "a.jpg")
        b = _write_file(tmp_path / "src" / "b.svg")
        chunk = _chunk(assets=(a, b))
        out = tmp_path / "out"
        out.mkdir()
        copy_assets({"s": chunk}, out)
        assert (out / "_assets" / "s" / "a.jpg").exists()
        assert (out / "_assets" / "s" / "b.svg").exists()

    def test_same_filename_different_slides_separate_dirs(self, tmp_path: Path) -> None:
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

    def test_preserves_file_content(self, tmp_path: Path) -> None:
        content = b"\x89PNG\r\n\x1a\n fake png data"
        src = tmp_path / "src" / "image.png"
        src.parent.mkdir(parents=True)
        src.write_bytes(content)
        chunk = _chunk(assets=(src,))
        out = tmp_path / "out"
        out.mkdir()
        copy_assets({"s": chunk}, out)
        assert (out / "_assets" / "s" / "image.png").read_bytes() == content

    def test_skips_chunks_without_assets(self, tmp_path: Path) -> None:
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


class TestMimeTypeCoverage:
    """Parametrized coverage of every entry in ``_MIME_TYPES``.

    Guards against silent regressions when a format is added to or removed
    from the supported set: every entry must round-trip cleanly through both
    the inline (``data:`` URI) and external-asset (file copy) paths.
    """

    @pytest.mark.parametrize(("ext", "expected_mime"), sorted(_MIME_TYPES.items()))
    def test_inline_data_uri_uses_correct_mime(
        self,
        tmp_path: Path,
        ext: str,
        expected_mime: str,
    ) -> None:
        # --- arrange ----------------------
        src = tmp_path / f"asset{ext}"
        src.write_bytes(b"sentinel-payload")
        chunk = _chunk(html=f'<img src="__asset__/asset{ext}">', assets=(src,))

        # --- act --------------------------
        result, _ = rewrite_asset_refs({"s1": chunk}, compress=False)

        # --- assert -----------------------
        assert f"data:{expected_mime};base64," in result["s1"].html

    @pytest.mark.parametrize("ext", sorted(_MIME_TYPES))
    def test_external_mode_rewrites_ref(self, tmp_path: Path, ext: str) -> None:
        # --- arrange ----------------------
        src = _write_file(tmp_path / "src" / f"asset{ext}")
        chunk = _chunk(html=f'<img src="__asset__/asset{ext}">', assets=(src,))

        # --- act --------------------------
        result, _ = rewrite_asset_refs({"s1": chunk}, inline=False)

        # --- assert -----------------------
        assert "__asset__/" not in result["s1"].html
        assert f"_assets/s1/asset{ext}" in result["s1"].html

    @pytest.mark.parametrize("ext", sorted(_MIME_TYPES))
    def test_copy_assets_copies_file(self, tmp_path: Path, ext: str) -> None:
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


class TestCompression:
    def test_compressible_svg_gets_data_scrolly_gz(self, tmp_path: Path) -> None:
        # --- arrange ----------------------------
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg">' + b"<rect/>" * 100 + b"</svg>"
        src = tmp_path / "big.svg"
        src.write_bytes(svg_content)
        chunk = _chunk(html='<img src="__asset__/big.svg" alt="">', assets=(src,))

        # --- act --------------------------------
        result, stats = rewrite_asset_refs({"s1": chunk}, compress=True)

        # --- assert ------------------------------
        assert "data-scrolly-gz=" in result["s1"].html
        assert 'data-scrolly-sink="img"' in result["s1"].html
        assert 'data-scrolly-mime="image/svg+xml"' in result["s1"].html
        assert 'src="' not in result["s1"].html
        assert stats.compressed == 1
        assert stats.bytes_saved > 0

    def test_incompressible_asset_keeps_data_uri(self, tmp_path: Path) -> None:
        # --- arrange ----------------------------
        src = tmp_path / "tiny.avif"
        src.write_bytes(b"\x00\x00\x00\x1c" + b"x" * 10)
        chunk = _chunk(html='<img src="__asset__/tiny.avif" alt="">', assets=(src,))

        # --- act --------------------------------
        result, stats = rewrite_asset_refs({"s1": chunk}, compress=True)

        # --- assert ------------------------------
        assert "data:image/avif;base64," in result["s1"].html
        assert "data-scrolly-gz" not in result["s1"].html
        assert stats.compressed == 0

    def test_css_refs_always_use_data_uri(self, tmp_path: Path) -> None:
        # --- arrange ----------------------------
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg">' + b"<rect/>" * 100 + b"</svg>"
        src = tmp_path / "bg.svg"
        src.write_bytes(svg_content)
        chunk = _chunk(
            html="<p>no img ref</p>",
            scoped_css="background: url(__asset__/bg.svg);",
            assets=(src,),
        )

        # --- act --------------------------------
        result, _ = rewrite_asset_refs({"s1": chunk}, compress=True)

        # --- assert ------------------------------
        assert "data:image/svg+xml;base64," in result["s1"].scoped_css
        assert "data-scrolly-gz" not in result["s1"].scoped_css

    def test_compress_false_skips_compression(self, tmp_path: Path) -> None:
        # --- arrange ----------------------------
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg">' + b"<rect/>" * 100 + b"</svg>"
        src = tmp_path / "big.svg"
        src.write_bytes(svg_content)
        chunk = _chunk(html='<img src="__asset__/big.svg" alt="">', assets=(src,))

        # --- act --------------------------------
        result, stats = rewrite_asset_refs({"s1": chunk}, compress=False)

        # --- assert ------------------------------
        assert "data:image/svg+xml;base64," in result["s1"].html
        assert "data-scrolly-gz" not in result["s1"].html
        assert stats.compressed == 0

    def test_compressed_img_preserves_other_attributes(self, tmp_path: Path) -> None:
        # --- arrange ----------------------------
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg">' + b"<rect/>" * 100 + b"</svg>"
        src = tmp_path / "big.svg"
        src.write_bytes(svg_content)
        chunk = _chunk(
            html='<img data-frame-index="0" src="__asset__/big.svg" alt="">',
            assets=(src,),
        )

        # --- act --------------------------------
        result, _ = rewrite_asset_refs({"s1": chunk}, compress=True)

        # --- assert ------------------------------
        assert 'data-frame-index="0"' in result["s1"].html
        assert 'alt=""' in result["s1"].html

    def test_no_inline_mode_unaffected_by_compress(self, tmp_path: Path) -> None:
        # --- arrange ----------------------------
        src = _write_file(tmp_path / "src" / "bg.svg")
        chunk = _chunk(html='<img src="__asset__/bg.svg">', assets=(src,))

        # --- act --------------------------------
        result, stats = rewrite_asset_refs({"s1": chunk}, inline=False, compress=True)

        # --- assert ------------------------------
        assert "data-scrolly-gz" not in result["s1"].html
        assert "_assets/s1/bg.svg" in result["s1"].html
        assert stats.compressed == 0


class TestValidation:
    def test_missing_file_raises(self, tmp_path: Path) -> None:
        missing = tmp_path / "no_such_file.jpg"
        chunk = _chunk(assets=(missing,))
        with pytest.raises(SlideSourceError, match="does not exist"):
            rewrite_asset_refs({"s": chunk})

    def test_duplicate_filename_raises(self, tmp_path: Path) -> None:
        f1 = _write_file(tmp_path / "dir1" / "img.jpg")
        f2 = _write_file(tmp_path / "dir2" / "img.jpg")
        chunk = _chunk(assets=(f1, f2))
        with pytest.raises(SlideSourceError, match="duplicate"):
            rewrite_asset_refs({"s": chunk})

    def test_dotdot_filename_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / ".."
        bad.mkdir(exist_ok=True)
        chunk = _chunk(assets=(bad,))
        with pytest.raises(SlideSourceError, match="invalid"):
            rewrite_asset_refs({"s": chunk})
