"""Portable, non-destructive whole-chapter Editor backup.

A chapter is a directory of source images and manga_translator_work sidecars.
The Editor still saves individual pages while working; this service snapshots
the complete source folders into one independently reopenable directory.

Only the *copied* legacy JSON keys and export-directory hints are relocated.
Original files are never edited or removed.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from manga_translator.image_formats import SUPPORTED_IMAGE_EXTENSIONS

_BACKUP_PREFIX = "MangaEditor_Chapter"
_MANIFEST_NAME = "mangaeditor_backup_manifest.json"
_IGNORED_DIRECTORIES = frozenset({".git", ".venv", "__pycache__"})
_IMAGE_SUFFIXES = frozenset(ext.lower() for ext in SUPPORTED_IMAGE_EXTENSIONS)


@dataclass(frozen=True)
class ChapterBackupResult:
    folder: str
    pages: int
    groups: int
    external_exports: int


def _canonical(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def _within(path: str, folder: str) -> bool:
    try:
        return os.path.commonpath([_canonical(path), _canonical(folder)]) == _canonical(folder)
    except ValueError:
        return False


def _unique_folder(parent: str, name: str) -> str:
    candidate = os.path.join(parent, name)
    index = 2
    while os.path.lexists(candidate):
        candidate = os.path.join(parent, f"{name}_{index}")
        index += 1
    return candidate


def _safe_label(path: str) -> str:
    label = os.path.basename(os.path.normpath(path)) or "Chapter"
    return re.sub(r"[^-_.\w]+", "_", label, flags=re.UNICODE)[:55] or "Chapter"


def _choose_roots(
    image_paths: list[str], source_folders: Iterable[str],
) -> list[tuple[str, list[str]]]:
    """Prefer explicitly registered folders; otherwise group by image parent.

    Never take the common ancestor of unrelated folders: that could be the
    drive root and accidentally archive an entire disk.
    """
    explicit = sorted(
        {_canonical(p) for p in source_folders if os.path.isdir(p)},
        key=lambda p: (len(p), p),
    )
    selected_roots: list[str] = []
    for folder in explicit:
        if not any(_within(folder, chosen) for chosen in selected_roots):
            selected_roots.append(folder)
    group_images: dict[str, list[str]] = {}
    for path in image_paths:
        root = next(
            (folder for folder in selected_roots if _within(path, folder)),
            os.path.dirname(path),
        )
        group_images.setdefault(root, []).append(path)
    # An image might be under a parent folder later added as an explicit root.
    # Compact nested roots to avoid duplicating the same directory tree.
    roots = sorted(group_images, key=lambda p: (len(p), p))
    result: dict[str, list[str]] = {}
    for root in roots:
        parent = next((p for p in result if _within(root, p)), root)
        result.setdefault(parent, []).extend(group_images[root])
    return sorted(result.items(), key=lambda pair: pair[0].casefold())


def _copy_ignore(directory: str, names: list[str]) -> set[str]:
    """Avoid copying ephemeral temp files, source-control and symlink targets."""
    ignored = set()
    for name in names:
        path = os.path.join(directory, name)
        if (
            os.path.islink(path)
            or (os.path.isdir(path) and name in _IGNORED_DIRECTORIES)
            or name.endswith((".tmp", ".part"))
        ):
            ignored.add(name)
    return ignored


def _relocate_key(key: str, source_root: str, final_root: str) -> str:
    if not os.path.isabs(key) or not _within(key, source_root):
        return key
    return os.path.normpath(os.path.join(final_root, os.path.relpath(key, source_root)))


def _external_output(
    previous_directory: str,
    image_path: str,
    destination_root: str,
) -> bool:
    """Copy an explicitly recorded external export, never the source image."""
    if not os.path.isdir(previous_directory):
        return False
    stem = os.path.splitext(os.path.basename(image_path))[0]
    for suffix in sorted(_IMAGE_SUFFIXES):
        candidate = os.path.join(previous_directory, stem + suffix)
        if not os.path.isfile(candidate) or _canonical(candidate) == _canonical(image_path):
            continue
        output = os.path.join(destination_root, "manga_translator_work", "result")
        os.makedirs(output, exist_ok=True)
        shutil.copy2(candidate, os.path.join(output, os.path.basename(candidate)))
        return True
    return False


def _relocate_json(
    staging_root: str, source_root: str, final_root: str,
) -> int:
    """Rewrite paths solely in duplicated translation JSON files.

    Other JSON (configuration, LaMa cache signatures, OCR registry files) is
    retained verbatim: guessing their schemas would risk silent corruption.
    """
    external_exports = 0
    for directory, dirs, files in os.walk(staging_root):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(directory, d))]
        for filename in files:
            if not filename.endswith("_translations.json"):
                continue
            json_path = os.path.join(directory, filename)
            try:
                with open(json_path, "r", encoding="utf-8") as handle:
                    stored = json.load(handle)
            except (OSError, ValueError):
                # A corrupt or legacy file remains untouched in the backup.
                continue
            if not isinstance(stored, dict):
                continue
            relocated = {}
            changed = False
            for old_key, value in stored.items():
                new_key = _relocate_key(old_key, source_root, final_root)
                if new_key != old_key:
                    changed = True
                if isinstance(value, dict) and isinstance(value.get("last_export_dir"), str):
                    value = dict(value)
                    old_dir = value["last_export_dir"]
                    if _within(old_dir, source_root):
                        value["last_export_dir"] = _relocate_key(
                            old_dir, source_root, final_root
                        )
                    else:
                        # External path must not leak into the portable backup.
                        # Include existing exported images when available.
                        old_image = old_key if os.path.isabs(old_key) else os.path.join(
                            source_root, os.path.basename(filename).replace("_translations.json", "")
                        )
                        if _external_output(old_dir, old_image, staging_root):
                            external_exports += 1
                            value["last_export_dir"] = os.path.join(
                                final_root, "manga_translator_work", "result"
                            )
                        else:
                            value.pop("last_export_dir", None)
                    changed = True
                if new_key in relocated:
                    raise ValueError(f"Duplicate image JSON key after relocation: {new_key}")
                relocated[new_key] = value
            if not changed:
                continue
            with open(json_path + ".backup.tmp", "w", encoding="utf-8", newline="\n") as handle:
                json.dump(relocated, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(json_path + ".backup.tmp", json_path)
    return external_exports


def save_chapter_folder(
    image_paths: Iterable[str],
    destination_parent: str,
    *,
    source_folders: Iterable[str] = (),
    created_at: datetime | None = None,
) -> ChapterBackupResult:
    """Create a new complete directory snapshot without overwriting anything.

    The parent must be outside all project folders, preventing recursive copies.
    The final backup only appears after all copies and JSON remaps succeed.
    """
    images = []
    seen = set()
    for image in image_paths:
        path = _canonical(str(image))
        if path not in seen:
            if not os.path.isfile(path) or Path(path).suffix.lower() not in _IMAGE_SUFFIXES:
                raise ValueError(f"Missing or unsupported source image: {path}")
            if os.path.islink(path):
                raise ValueError(f"Linked source images are unsupported: {path}")
            images.append(path)
            seen.add(path)
    if not images:
        raise ValueError("No image pages in the current Editor chapter")

    if not os.path.isdir(destination_parent):
        raise ValueError("Backup destination does not exist")
    parent = _canonical(destination_parent)
    groups = _choose_roots(images, source_folders)
    for source, _ in groups:
        if _within(parent, source):
            raise ValueError(
                "Choose a backup destination outside the source chapter folders"
            )

    date = created_at or datetime.now()
    target = _unique_folder(parent, date.strftime(_BACKUP_PREFIX + "_%Y%m%d_%H%M%S"))
    staging = tempfile.mkdtemp(prefix=".mangaeditor-chapter-", dir=parent)
    exported = 0
    manifest_pages = []
    try:
        for index, (source_root, selected) in enumerate(groups, start=1):
            relative_root = (
                "." if len(groups) == 1 else
                os.path.join("chapters", f"{index:02d}_{_safe_label(source_root)}")
            )
            staging_root = os.path.normpath(os.path.join(staging, relative_root))
            final_root = os.path.normpath(os.path.join(target, relative_root))
            if os.path.islink(source_root):
                raise ValueError(f"Linked source directory is unsupported: {source_root}")
            shutil.copytree(
                source_root, staging_root, dirs_exist_ok=True, ignore=_copy_ignore
            )
            exported += _relocate_json(staging_root, source_root, final_root)
            manifest_pages.extend(
                os.path.relpath(
                    os.path.join(final_root, os.path.relpath(image, source_root)),
                    target,
                ).replace(os.sep, "/")
                for image in selected
            )

        manifest = {
            "format": "mangaeditor.chapter-backup.v1",
            "created_at": date.isoformat(timespec="seconds"),
            "page_count": len(images),
            "group_count": len(groups),
            "pages": manifest_pages,
            "note": "Open this folder (or its chapters subfolders) in MangaEditor to resume editing.",
        }
        with open(os.path.join(staging, _MANIFEST_NAME), "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
        # Atomic publish: a partial backup never masquerades as a completed one.
        os.rename(staging, target)
        staging = ""
        return ChapterBackupResult(
            folder=target, pages=len(images), groups=len(groups),
            external_exports=exported,
        )
    finally:
        if staging and os.path.exists(staging):
            shutil.rmtree(staging)
