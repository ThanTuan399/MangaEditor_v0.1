"""Validate OCR polygon coordinates before passing them to cv2.fillPoly.

TextBlock loads polygon points from project JSON as float64, while OpenCV
requires a contiguous array of 2D int32 points. The mask generator must not
fail an entire render job because one OCR region has invalid or empty geometry.
"""
from __future__ import annotations

import logging
from typing import Iterable

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def mask_from_text_regions(regions: Iterable, shape: tuple[int, int]) -> np.ndarray:
    """Build a uint8 region mask, skipping invalid/degenerate polygons safely."""
    height, width = int(shape[0]), int(shape[1])
    result = np.zeros((max(height, 0), max(width, 0)), dtype=np.uint8)
    if height <= 0 or width <= 0:
        return result

    polygons = []
    invalid = 0
    for region in regions:
        raw_lines = region.get("lines", []) if isinstance(region, dict) else getattr(region, "lines", [])
        try:
            lines = np.asarray(raw_lines, dtype=np.float64)
        except (TypeError, ValueError, OverflowError):
            invalid += 1
            continue

        # Typical JSON has shape (line_count, 4, 2).
        # A single polygon may also have shape (4, 2).
        if lines.ndim == 2 and lines.shape[-1] == 2:
            lines = lines[np.newaxis, :, :]
        if lines.ndim != 3 or lines.shape[-1] != 2:
            invalid += 1
            continue

        for points in lines:
            if len(points) < 3 or not np.isfinite(points).all():
                invalid += 1
                continue
            coords = np.rint(points)
            # Clamp before converting: floats can be outside int32 range.
            coords[:, 0] = np.clip(coords[:, 0], 0, width - 1)
            coords[:, 1] = np.clip(coords[:, 1], 0, height - 1)
            polygon = np.ascontiguousarray(coords, dtype=np.int32)
            if len(np.unique(polygon, axis=0)) < 3:
                invalid += 1
                continue
            polygons.append(polygon.reshape(-1, 1, 2))

    if invalid:
        logger.warning(
            "Skipped %d malformed/degenerate OCR polygons while creating render mask",
            invalid,
        )
    if polygons:
        cv2.fillPoly(result, polygons, 255)
    return result



def repair_missing_translation_masks(
    regions: Iterable,
    shape: tuple[int, int],
    mask: np.ndarray | None,
    *,
    min_coverage: float = 0.02,
    expand_px: int = 1,
) -> tuple[np.ndarray, bool]:
    """Fill OCR line polygons only where a translated region has no erase mask.

    OCR-only projects can store valid text regions but no mask, or a detector
    mask that entirely misses one dialogue. Inpainting without the missing
    polygon leaves the old Japanese characters visible behind the Vietnamese
    translation. Never cover untranslated regions or replace an existing
    reasonably covered mask; keep image details outside those specific lines.

    Returns (binary_mask, changed). 'changed' invalidates historical inpaint
    sidecars so callers must render a fresh background before saving/exporting.
    """
    height, width = int(shape[0]), int(shape[1])
    if height <= 0 or width <= 0:
        return np.zeros((max(height, 0), max(width, 0)), dtype=np.uint8), False

    if mask is None:
        output = np.zeros((height, width), dtype=np.uint8)
    else:
        arr = np.asarray(mask)
        if arr.ndim == 3:
            arr = arr[:, :, 0]
        if arr.shape != (height, width):
            raise ValueError(
                f"Mask shape {arr.shape} does not match image {(height, width)}"
            )
        output = np.where(arr > 0, 255, 0).astype(np.uint8)

    changed = False
    added_regions = 0
    for region in regions:
        translation = (
            region.get("translation") if isinstance(region, dict)
            else getattr(region, "translation", "")
        )
        if not isinstance(translation, str) or not translation.strip():
            continue
        region_mask = mask_from_text_regions([region], (height, width))
        count = int(np.count_nonzero(region_mask))
        if count < 4:
            continue
        covered = int(np.count_nonzero((region_mask > 0) & (output > 0)))
        if covered / count >= min_coverage:
            continue
        if expand_px > 0:
            radius = max(0, min(int(expand_px), 3))
            if radius:
                kernel = cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1)
                )
                region_mask = cv2.dilate(region_mask, kernel, iterations=1)
        missing = (region_mask > 0) & (output == 0)
        if np.any(missing):
            output[missing] = 255
            changed = True
            added_regions += 1
    if added_regions:
        logger.info(
            "Restored erase masks for %d translated OCR regions missing "
            "inpainting coverage",
            added_regions,
        )
    return output, changed
