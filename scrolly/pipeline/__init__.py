"""Build orchestration — glues deck + slide conversion + rendering + writing."""

from scrolly.pipeline.orchestrator import build_deck, validate_deck_sources
from scrolly.pipeline.writer import write_output

__all__ = ["build_deck", "validate_deck_sources", "write_output"]
