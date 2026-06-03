import pytest

from scrolly.errors import OutputError
from scrolly.pipeline.writer import write_output
from scrolly.render.bundled_assets import MermaidAsset


def test_writes_to_new_directory(tmp_path):
    # --- arrange ----------------------
    out = tmp_path / "dist"

    # --- act --------------------------
    write_output(out, "<html></html>")

    # --- assert -----------------------
    assert (out / "index.html").read_text() == "<html></html>"


def test_writes_to_empty_existing_directory(tmp_path):
    # --- arrange ----------------------
    out = tmp_path / "dist"
    out.mkdir()

    # --- act --------------------------
    write_output(out, "<html></html>")

    # --- assert -----------------------
    assert (out / "index.html").read_text() == "<html></html>"


def test_creates_parent_directories(tmp_path):
    # --- arrange ----------------------
    out = tmp_path / "a" / "b" / "c"

    # --- act --------------------------
    write_output(out, "<html></html>")

    # --- assert -----------------------
    assert (out / "index.html").exists()


def test_refuses_non_empty_directory_without_force(tmp_path):
    # --- arrange ----------------------
    out = tmp_path / "dist"
    out.mkdir()
    (out / "stale.txt").write_text("leftover")

    # --- act / assert -----------------
    with pytest.raises(OutputError, match="not empty"):
        write_output(out, "<html></html>")


def test_force_overwrites_non_empty_directory(tmp_path):
    # --- arrange ----------------------
    out = tmp_path / "dist"
    out.mkdir()
    (out / "stale.txt").write_text("leftover")

    # --- act --------------------------
    write_output(out, "<html></html>", force=True)

    # --- assert -----------------------
    assert (out / "index.html").read_text() == "<html></html>"


def test_path_is_a_file_rejected(tmp_path):
    # --- arrange ----------------------
    p = tmp_path / "dist"
    p.write_text("not a directory")

    # --- act / assert -----------------
    with pytest.raises(OutputError, match="not a directory"):
        write_output(p, "<html></html>")


def test_inline_mode_writes_only_index_html(tmp_path):
    # --- arrange ----------------------
    out = tmp_path / "dist"

    # --- act --------------------------
    write_output(out, "<html></html>")

    # --- assert -----------------------
    assert (out / "index.html").exists()
    assert not (out / "canvas.css").exists()
    assert not (out / "canvas.js").exists()


def test_no_inline_copies_bundled_assets(tmp_path):
    # --- arrange ----------------------
    out = tmp_path / "dist"

    # --- act --------------------------
    write_output(out, "<html></html>", inline=False)

    # --- assert -----------------------
    assert (out / "canvas.css").exists()
    assert (out / "canvas.js").exists()
    assert ".canvas" in (out / "canvas.css").read_text()


def test_no_inline_writes_mermaid_when_present(tmp_path):
    # --- arrange ----------------------
    out = tmp_path / "dist"
    mermaid = MermaidAsset(name="mermaid.min.js", content=b"// mermaid bytes", version="11.0.0", source="bundled")

    # --- act --------------------------
    write_output(out, "<html></html>", inline=False, mermaid=mermaid)

    # --- assert -----------------------
    assert (out / "mermaid.min.js").read_bytes() == b"// mermaid bytes"


def test_no_inline_skips_mermaid_when_absent(tmp_path):
    # --- arrange / act ----------------
    out = tmp_path / "dist"
    write_output(out, "<html></html>", inline=False)  # mermaid=None default

    # --- assert -----------------------
    assert not (out / "mermaid.min.js").exists()


def test_inline_does_not_write_mermaid_even_when_present(tmp_path):
    # --- arrange ----------------------
    out = tmp_path / "dist"
    mermaid = MermaidAsset(name="mermaid.min.js", content=b"// inlined", version="11.0.0", source="bundled")

    # --- act --------------------------
    # inline=True (default) means mermaid is in the HTML, not a separate file.
    write_output(out, "<html></html>", mermaid=mermaid)

    # --- assert -----------------------
    assert not (out / "mermaid.min.js").exists()
