"""The A↔B boundary value — what Layer B produces and Layer A consumes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from scrolly.pipeline._compress import CompressionStats


@dataclass(frozen=True)
class SlideHTML:
    """The uniform per-slide render output — what Layer B produces and Layer A consumes.

    Parallels ``SlideIR``: IR is the intermediate representation, HTML is
    the final representation.  The pipeline reads: IR → HTML.
    """

    title: str
    html: str
    scoped_css: str = ""
    scroll_range: int | None = None
    initial_scroll_position: int = 0
    scroll_speed: float = 1.0
    font_scale: float = 1.0
    assets: tuple[Path, ...] = ()
    snap_positions: tuple[int, ...] = ()
    reverse: bool = False
    has_mermaid: bool = False
    compression_stats: CompressionStats = field(default_factory=CompressionStats)

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValueError("title must be a non-empty string")
        if self.scroll_range is not None and self.scroll_range <= 0:
            raise ValueError(
                f"scroll_range must be a positive int when set, got {self.scroll_range}; "
                f"use None for content-driven mode"
            )
        if self.initial_scroll_position < 0:
            raise ValueError(f"initial_scroll_position must be >= 0, got {self.initial_scroll_position}")
        if self.scroll_speed <= 0:
            raise ValueError(f"scroll_speed must be > 0, got {self.scroll_speed}")
        if self.font_scale <= 0:
            raise ValueError(f"font_scale must be > 0, got {self.font_scale}")
        if self.snap_positions:
            for pos in self.snap_positions:
                if pos < 0:
                    raise ValueError(f"snap_positions values must be >= 0, got {pos}")
                if self.scroll_range is not None and pos > self.scroll_range:
                    raise ValueError(f"snap_positions value {pos} exceeds scroll_range {self.scroll_range}")
