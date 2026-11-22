"""Render persisted MangaEditor pages into a chapter backup.

Uses exactly the editor ExportJob / ExportService backend pipeline, not a
second OCR/translation pass. All paths refer to the staging copy, therefore
backend inpaint sidecars and final pictures never overwrite the source project.
"""
from __future__ import annotations

import copy
import os

import numpy as np
from PIL import Image

from manga_translator.utils.path_manager import (
    find_inpainted_path,
    find_paint_overlay_path,
    find_work_image_path,
)
from editor.controller_export_service import ExportJob, EditorControllerExportService
from editor.document_state import ExportBase
from editor.inpaint_state import InpaintKey
from services.export_service import ExportService
from services.file_service import FileService


def _aligned_rgba(value: object, size: tuple[int, int]) -> np.ndarray | None:
    if value is None:
        return None
    array = np.asarray(value)
    if array.ndim != 3 or array.shape[2] != 4:
        raise ValueError("Invalid RGBA editor overlay")
    if array.shape[:2] != (size[1], size[0]):
        # The editor's document loader uses nearest-neighbour here as well.
        import cv2
        array = cv2.resize(array, size, interpolation=cv2.INTER_NEAREST)
    return np.asarray(array, dtype=np.uint8)


def _load_old_paint_overlay(image_path: str, size: tuple[int, int]) -> np.ndarray | None:
    path = find_paint_overlay_path(image_path)
    if not path:
        return None
    with Image.open(path) as layer:
        return _aligned_rgba(np.asarray(layer.convert("RGBA")), size)


def _read_background(
    image_path: str,
    size: tuple[int, int],
    mask: np.ndarray | None,
    repaired: bool,
) -> np.ndarray | None:
    """Read a valid inpaint sidecar only when it matches the stored mask."""
    path = None if repaired else find_inpainted_path(image_path)
    if not path or mask is None or not np.any(mask):
        return None
    with Image.open(path) as image:
        if image.size != size:
            return None
        return np.array(image.convert("RGB"), dtype=np.uint8, copy=True)


def render_saved_chapter_page(
    image_path: str,
    output_path: str,
    config: dict,
    *,
    image_key: str | None = None,
) -> str:
    """Render a saved page using its *copied* JSON and editor image layers.

    image_key is the path encoded in the relocated JSON (the final backup
    location); while rendering, image_path points into the temporary staging
    directory. It avoids FileService accidentally selecting the first entry of
    a multi-page JSON.
    """
    if not isinstance(config, dict):
        raise TypeError("Chapter rendering needs the current Editor config")

    file_service = FileService()
    regions, mask, _, overlays = file_service.load_translation_json(
        image_path, image_key_override=image_key,
    )
    overlays = overlays or {}
    working_image = find_work_image_path(image_path) or image_path
    job = None

    with Image.open(working_image) as image:
        source = image.convert("RGB")
        source.load()
    try:
        size = source.size
        repaired = False
        if regions:
            from manga_translator.mask_refinement.region_polygon_mask import (
                repair_missing_translation_masks,
            )
            mask, repaired = repair_missing_translation_masks(
                regions, (size[1], size[0]), mask
            )
        if mask is not None:
            mask = np.asarray(mask)
            if mask.ndim == 3:
                mask = mask[..., 0]
            if mask.shape != (size[1], size[0]):
                raise ValueError(
                    f"Saved mask size {mask.shape} differs from page size "
                    f"{(size[1], size[0])}: {image_path}"
                )
            mask = mask.astype(np.uint8, copy=False)

        if mask is None or not np.any(mask):
            export_base = ExportBase("source", source, source, None)
        else:
            repaired_bg = _read_background(image_path, size, mask, repaired)
            kind = "paired" if repaired_bg is not None else "backend_inpaint"
            export_base = ExportBase(
                kind, source,
                repaired_bg if repaired_bg is not None else source,
                mask, InpaintKey(1, 1),
            )

        paint = _aligned_rgba(overlays.get("paint"), size)
        if paint is None:
            paint = _load_old_paint_overlay(image_path, size)

        # ExportJob owns deep copies of all regions and image buffers.
        regions_for_export = copy.deepcopy(regions)
        for region in regions_for_export:
            EditorControllerExportService.apply_white_frame_center(region)

        job = ExportJob(
            automatic=False,
            source_path=image_path,
            output_path=output_path,
            export_base=export_base,
            regions=regions_for_export,
            config=config,
            paint_overlay=paint,
            stamp_overlay=_aligned_rgba(overlays.get("stamp"), size),
            paste_overlays=tuple(overlays.get("paste_overlays") or ()),
        )
        exporter = ExportService()
        result = exporter.execute_export_job(job)
        if result.error is not None:
            raise RuntimeError(result.error)
        if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
            raise RuntimeError(f"Editor returned no rendered page: {image_path}")
        return output_path
    finally:
        if job is not None:
            job.release_resources()
        source.close()
