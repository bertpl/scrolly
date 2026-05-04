import pytest

from scrolly.errors import OutputError
from scrolly.pipeline.writer import write_output


def test_writes_to_new_directory(tmp_path):
    out = tmp_path / "dist"
    write_output(out, "<html></html>")
    assert (out / "index.html").read_text() == "<html></html>"


def test_writes_to_empty_existing_directory(tmp_path):
    out = tmp_path / "dist"
    out.mkdir()
    write_output(out, "<html></html>")
    assert (out / "index.html").read_text() == "<html></html>"


def test_creates_parent_directories(tmp_path):
    out = tmp_path / "a" / "b" / "c"
    write_output(out, "<html></html>")
    assert (out / "index.html").exists()


def test_refuses_non_empty_directory_without_force(tmp_path):
    out = tmp_path / "dist"
    out.mkdir()
    (out / "stale.txt").write_text("leftover")
    with pytest.raises(OutputError, match="not empty"):
        write_output(out, "<html></html>")


def test_force_overwrites_non_empty_directory(tmp_path):
    out = tmp_path / "dist"
    out.mkdir()
    (out / "stale.txt").write_text("leftover")
    write_output(out, "<html></html>", force=True)
    assert (out / "index.html").read_text() == "<html></html>"


def test_path_is_a_file_rejected(tmp_path):
    p = tmp_path / "dist"
    p.write_text("not a directory")
    with pytest.raises(OutputError, match="not a directory"):
        write_output(p, "<html></html>")


def test_inline_mode_writes_only_index_html(tmp_path):
    out = tmp_path / "dist"
    write_output(out, "<html></html>")
    assert (out / "index.html").exists()
    assert not (out / "canvas.css").exists()
    assert not (out / "canvas.js").exists()


def test_no_inline_copies_bundled_assets(tmp_path):
    out = tmp_path / "dist"
    write_output(out, "<html></html>", inline=False)
    assert (out / "canvas.css").exists()
    assert (out / "canvas.js").exists()
    assert ".canvas" in (out / "canvas.css").read_text()
