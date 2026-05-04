"""Final HTML assembly — canvas template + bundled static assets."""

from scrolly.render.assembler import assemble
from scrolly.render.bundled_assets import bundled_css, bundled_js, iter_assets, mermaid_asset, mermaid_js

__all__ = ["assemble", "bundled_css", "bundled_js", "iter_assets", "mermaid_asset", "mermaid_js"]
