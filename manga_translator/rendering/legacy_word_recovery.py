"""Repair high-confidence Vietnamese syllables broken by old auto layout.

Old renderer versions persisted *visual* line breaks in semantic translations.
Some users removed [BR] by replacing it with a space, leaving broken syllables
such as "xon g", "ch ị", "hu ấn". Because original word boundaries are lost,
we only repair high-confidence splits. All other boundaries remain untouched.

Display-only cleanup is separate from guarded Editor data repair. Neither
changes a file merely because the page was opened.
"""
from __future__ import annotations

import re
from typing import Any

from .rich_text import is_redundant_plain_document

_BR = r"(?:\[BR\]|【BR】|<br\s*/?>)"
_TOKEN = r"[^\W\d_]+"
# The right-hand token is a lookahead, not consumed: neighboring breaks
# must both be examined (e.g. "hu[BR]ấn luyện ch[BR]o").
_GAP = re.compile(
    rf"(?P<left>{_TOKEN})(?P<gap>\s*{_BR}\s*|\s+)(?=(?P<right>{_TOKEN}))",
    re.I | re.U,
)
_BR_ONLY = re.compile(_BR, re.I)
_WORD = re.compile(_TOKEN, re.U)

# One-letter words/interjections can be legitimate Vietnamese words. Never
# merge these automatically on the basis of length alone.
_STANDALONE = frozenset(
    "a à á ạ ả ã e è é ẹ ẻ ẽ ê ề ế ệ ể ễ i ì í ị ỉ ĩ "
    "o ò ó ọ ỏ õ ô ồ ố ộ ổ ỗ ơ ờ ớ ợ ở ỡ "
    "u ù ú ụ ủ ũ ư ừ ứ ự ử ữ y ỳ ý ỵ ỷ ỹ".split()
)
# Common Vietnamese initial-consonant clusters requiring a vowel; splitting
# before their vowel leaves a nonsensical fragment (e.g. "ch ị" / "ch o").
_ONSETS = frozenset(("ch", "nh", "kh", "tr", "ph", "th", "ng", "gh", "gi", "qu"))
_VOWELS = frozenset("aăâeêioôơuưyàáạảãằắặẳẵầấậẩẫèéẹẻẽềếệểễìíịỉĩòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ")
# Only highly recognizable longer splits: the source language cannot reliably
# tell us Vietnamese syllable boundaries; don't guess arbitrary new words.
_STRONG_JOINED = frozenset(("huấn", "luyện", "xong", "chị", "cho"))


def _confident_join(left: str, right: str, *, hard_break: bool, source_tokens: set[str]) -> bool:
    lower_left, lower_right = left.casefold(), right.casefold()
    whole = lower_left + lower_right
    if whole in source_tokens or whole in _STRONG_JOINED:
        return True
    if lower_left.endswith("n") and lower_right == "g" and len(lower_left) >= 3:
        return True
    if lower_left in _ONSETS and len(right) == 1 and lower_right in _VOWELS:
        return True
    if hard_break and len(left) == 1 and lower_left not in _STANDALONE and len(right) >= 2:
        return True
    return False


def recover_split_words(text: str | None, ocr_text: str | None = None, *, prose: bool = False) -> str:
    """Join only strong evidence of a split syllable.

    When prose=True, replace all remaining [BR] with spaces for the translation
    panel only. With prose=False keep valid manual line breaks in storage.
    """
    original = str(text or "")
    source_tokens = {word.casefold() for word in _WORD.findall(str(ocr_text or ""))}
    # A substitution can create a new adjacent boundary; repeat at most a few
    # times until stable, without merging ordinary adjacent words.
    result = original
    for _ in range(5):
        def fix(match):
            left = match.group("left")
            boundary = match.group("gap")
            right = match.group("right")
            hard_break = bool(_BR_ONLY.search(boundary))
            if _confident_join(left, right, hard_break=hard_break, source_tokens=source_tokens):
                return left  # next word belongs to the lookahead, not this match
            return match.group(0)
        next_result = _GAP.sub(fix, result)
        if next_result == result:
            break
        result = next_result
    if prose:
        result = _BR_ONLY.sub(" ", result)
        result = " ".join(result.split())
    return result


def repair_editor_region_split_words(region: dict) -> bool:
    """Repair high-confidence artifacts in the Editor's in-memory data.

    A user-styled rich paragraph is protected (it could contain deliberately
    styled runs). For plain rich text documents representing the same old text,
    remove the obsolete paragraphs after repairing a split; the Editor will
    rebuild the unstyled document from the corrected translation. User hard
    breaks between complete words remain untouched.
    """
    if not isinstance(region, dict):
        return False
    if str(region.get("target_lang") or "").upper() != "VIN":
        return False
    old = region.get("translation")
    if not isinstance(old, str) or not old:
        return False
    fixed = recover_split_words(old, region.get("text"))
    if old == fixed:
        return False
    rich = region.get("translation_rich")
    if rich:
        try:
            if not is_redundant_plain_document(rich, old):
                return False
        except (TypeError, ValueError):
            return False
    region["translation"] = fixed
    if region.get("translation_raw") == old:
        region["translation_raw"] = fixed
    if rich:
        region.pop("translation_rich", None)
    return True


def repair_editor_region_list(regions: Any) -> int:
    if not isinstance(regions, list):
        return 0
    return sum(repair_editor_region_split_words(region) for region in regions)
