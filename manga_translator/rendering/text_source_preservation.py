"""Protect semantic text from render-only line wrapping.

The layout engine intentionally rewrites TextBlock.translation to work out
fit/line breaks, then generates temporary rich-text paragraphs. Those edits
must NEVER become the persisted OCR/Editor Translation value. The original
TextBlock objects remain the owners of semantic text; renderer-computed
font sizes and geometry are left untouched.

Call around *rendering*, not around OCR/AI translation or explicit Editor text
changes. Manual [BR] markers are part of the source and are restored verbatim.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from typing import Iterable


@contextmanager
def preserve_semantic_translations(regions: Iterable):
    """Restore source, pre-replacement source and user rich text on all exits."""
    snapshots = [
        (
            region,
            region.translation,
            getattr(region, "translation_raw", None),
            deepcopy(getattr(region, "translation_rich", None)),
        )
        for region in regions
    ]
    try:
        yield
    finally:
        for region, source, source_raw, source_rich in snapshots:
            # Set translation first: its setter correctly invalidates the
            # temporary rich document created by auto-layout.
            region.translation = source
            if source_raw is not None:
                region.translation_raw = source_raw
            region.translation_rich = source_rich
            # A failed layout must not leave a text-replacement projection
            # record that contaminates the next render of the same page.
            if hasattr(region, "_replacement_layout_record"):
                delattr(region, "_replacement_layout_record")
