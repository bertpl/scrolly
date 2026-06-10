import pytest

from scrolly.slide.html import SlideHTML


def test_chunk_defaults():
    c = SlideHTML(title="T", html="<p>hi</p>")
    assert c.title == "T"
    assert c.html == "<p>hi</p>"
    assert c.scoped_css == ""
    # Content-driven mode is the default — runtime computes the range.
    assert c.scroll_range is None
    assert c.initial_scroll_position == 0
    assert c.scroll_speed == 1.0
    assert c.font_scale == 1.0
    assert c.reverse is False


def test_chunk_reverse_true():
    c = SlideHTML(title="T", html="", reverse=True)
    assert c.reverse is True


def test_chunk_all_fields():
    c = SlideHTML(
        title="Slide One",
        html="<p>hi</p>",
        scoped_css=".x { color: red }",
        scroll_range=1000,
        initial_scroll_position=10,
        scroll_speed=2.5,
    )
    assert c.title == "Slide One"
    assert c.scoped_css == ".x { color: red }"
    assert c.scroll_range == 1000
    assert c.initial_scroll_position == 10
    assert c.scroll_speed == 2.5


def test_chunk_is_frozen():
    c = SlideHTML(title="T", html="")
    with pytest.raises((AttributeError, TypeError)):
        c.html = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("title", ["", "   "])
def test_blank_title_rejected(title):
    with pytest.raises(ValueError, match="title must be a non-empty string"):
        SlideHTML(title=title, html="")


def test_scroll_range_none_is_content_driven_default():
    c = SlideHTML(title="T", html="")
    assert c.scroll_range is None


def test_negative_scroll_range_rejected():
    with pytest.raises(ValueError, match="scroll_range must be >= 0"):
        SlideHTML(title="T", html="", scroll_range=-5)


@pytest.mark.parametrize("scroll_range", [0, 500])
def test_non_negative_scroll_range_accepted(scroll_range):
    # Zero is an explicit author choice — a static slide — distinct
    # from None (content-driven: compute at runtime; might be zero).
    c = SlideHTML(title="T", html="", scroll_range=scroll_range)
    assert c.scroll_range == scroll_range


def test_negative_initial_scroll_position_rejected():
    with pytest.raises(ValueError, match="initial_scroll_position must be >= 0"):
        SlideHTML(title="T", html="", initial_scroll_position=-1)


@pytest.mark.parametrize("scroll_speed", [0, -1.0])
def test_non_positive_scroll_speed_rejected(scroll_speed):
    with pytest.raises(ValueError, match="scroll_speed must be > 0"):
        SlideHTML(title="T", html="", scroll_speed=scroll_speed)


def test_scroll_speed_default_is_one():
    c = SlideHTML(title="T", html="")
    assert c.scroll_speed == 1.0


def test_font_scale_default_is_one():
    c = SlideHTML(title="T", html="")
    assert c.font_scale == 1.0


def test_font_scale_positive_accepted():
    c = SlideHTML(title="T", html="", font_scale=1.5)
    assert c.font_scale == 1.5
    c2 = SlideHTML(title="T", html="", font_scale=0.5)
    assert c2.font_scale == 0.5


@pytest.mark.parametrize("font_scale", [0, -1.0])
def test_non_positive_font_scale_rejected(font_scale):
    with pytest.raises(ValueError, match="font_scale must be > 0"):
        SlideHTML(title="T", html="", font_scale=font_scale)


def test_snap_positions_default_empty():
    c = SlideHTML(title="T", html="")
    assert c.snap_positions == ()


def test_snap_positions_accepted():
    c = SlideHTML(title="T", html="", scroll_range=200, snap_positions=(0, 100, 200))
    assert c.snap_positions == (0, 100, 200)


def test_snap_positions_negative_rejected():
    with pytest.raises(ValueError, match="snap_positions values must be >= 0"):
        SlideHTML(title="T", html="", scroll_range=100, snap_positions=(-1, 50))


def test_snap_positions_exceeds_scroll_range_rejected():
    with pytest.raises(ValueError, match="exceeds scroll_range"):
        SlideHTML(title="T", html="", scroll_range=100, snap_positions=(0, 150))


def test_snap_positions_valid_without_scroll_range():
    c = SlideHTML(title="T", html="", snap_positions=(0, 50))
    assert c.snap_positions == (0, 50)
