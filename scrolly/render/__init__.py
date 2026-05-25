"""Final HTML assembly — canvas template + bundled static assets."""

from scrolly.render.assembler import assemble
from scrolly.render.bundled_assets import MermaidAsset, bundled_css, bundled_js, iter_assets, mermaid_asset

__all__ = ["MermaidAsset", "assemble", "bundled_css", "bundled_js", "iter_assets", "mermaid_asset"]
