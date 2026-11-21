"""Safe image+mask keyed inpaint cache for the manual OCR Workspace.

A source-language translation edit must not invalidate the expensive LaMa
background. OCR region geometry, source pixels, the effective erase mask and
inpaint settings *do* invalidate it. Unlike the old bare inpaint sidecar, an
unverified legacy sidecar is never trusted as a fast-path.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

_CACHE_VERSION = 1


def _settings_payload(config: Any, device: str, regions: Any) -> dict:
    inpainter = config.inpainter
    settings = {
        "inpainter": str(inpainter.inpainter),
        "size": int(inpainter.inpainting_size),
        "precision": str(inpainter.inpainting_precision),
        "force_torch": bool(inpainter.force_use_torch_inpainting),
        "solid_fill": bool(inpainter.solid_fill_pure_bubbles),
        "per_block": bool(inpainter.per_block_inpainting),
        "device": str(device),
    }
    if settings["solid_fill"]:
        # Bubble fill uses region geometry and model-detected bubble masks, not
        # the translation itself. Include detector/OCR rules for safe reuse.
        settings["regions"] = [
            (
                getattr(region, "lines", None)
                if not isinstance(region, dict) else region.get("lines")
            )
            for region in (regions or [])
        ]
        settings["detector"] = config.detector.model_dump(mode="json")
        settings["ocr"] = config.ocr.model_dump(mode="json")
    return settings


def workspace_inpaint_signature(
    source_path: str,
    mask: np.ndarray,
    config: Any,
    device: str,
    regions: Any = None,
) -> str:
    stat = os.stat(source_path)
    array = np.asarray(mask)
    if array.ndim == 3:
        array = array[..., 0]
    if array.ndim != 2:
        raise ValueError("Inpaint mask must be 2D")
    binary = np.ascontiguousarray((array > 0).astype(np.uint8))
    info = {
        "version": _CACHE_VERSION,
        "source": os.path.normcase(os.path.abspath(source_path)),
        "source_size": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
        "mask_shape": list(binary.shape),
        "settings": _settings_payload(config, device, regions),
    }
    hasher = hashlib.sha256(
        json.dumps(info, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    )
    hasher.update(binary.tobytes())
    return hasher.hexdigest()


def _record_path(inpainted_path: str) -> Path:
    return Path(inpainted_path + ".manual-cache.json")


def is_valid_workspace_inpaint_cache(
    inpainted_path: str | None, signature: str
) -> bool:
    if not inpainted_path or not signature:
        return False
    try:
        output = Path(inpainted_path)
        stat = output.stat()
        record = json.loads(_record_path(inpainted_path).read_text(encoding="utf-8"))
        return (
            isinstance(record, dict)
            and record.get("version") == _CACHE_VERSION
            and record.get("signature") == signature
            and record.get("output_size") == stat.st_size
            and record.get("output_mtime_ns") == stat.st_mtime_ns
        )
    except (OSError, ValueError, TypeError):
        return False


def write_workspace_inpaint_cache(inpainted_path: str, signature: str) -> None:
    """Atomically mark a completely written sidecar as reusable."""
    if not inpainted_path or not signature:
        return
    output = Path(inpainted_path)
    stat = output.stat()
    record = {
        "version": _CACHE_VERSION,
        "signature": signature,
        "output_size": stat.st_size,
        "output_mtime_ns": stat.st_mtime_ns,
    }
    target = _record_path(inpainted_path)
    temporary = target.with_name(target.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False)
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
