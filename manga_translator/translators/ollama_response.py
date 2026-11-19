"""Strict Ollama text-response parser.

The generic HQ parser intentionally prefers the *longest* JSON translation list,
which can select a model-generated example (e.g. 100 items for 18 OCR regions).
For the local backend, only accept a complete mapping to the current input IDs.
Never truncate or silently pair an overlong response with OCR regions.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .common import parse_hq_response


def _exact_translations(payload: Any, expected: int) -> tuple[list[str], int] | None:
    if isinstance(payload, dict):
        if "translations" in payload:
            payload = payload["translations"]
        elif "t" in payload:
            payload = payload["t"]
        elif expected == 1 and "translation" in payload:
            payload = [payload]
        else:
            return None
    if not isinstance(payload, list) or len(payload) != expected:
        return None
    if all(isinstance(entry, str) and entry.strip() for entry in payload):
        return list(payload), 1
    if not all(isinstance(entry, dict) for entry in payload):
        return None

    translated = []
    has_ids = [("id" in entry) for entry in payload]
    if any(has_ids) and not all(has_ids):
        return None
    if all(has_ids):
        by_id: dict[int, str] = {}
        for entry in payload:
            ident = entry["id"]
            # Do not accept booleans or malformed IDs.
            if isinstance(ident, bool) or not str(ident).isdigit():
                return None
            index = int(ident)
            value = entry.get("translation")
            if not isinstance(value, str) or not value.strip():
                return None
            if not 1 <= index <= expected or index in by_id:
                return None
            by_id[index] = value
        if len(by_id) != expected:
            return None
        return [by_id[index] for index in range(1, expected + 1)], 2

    for entry in payload:
        value = entry.get("translation")
        if not isinstance(value, str) or not value.strip():
            return None
        translated.append(value)
    return translated, 1


def parse_ollama_response(text: str, expected: int) -> tuple[list[str], list]:
    """Choose the last complete JSON candidate with exact, unique input IDs.

    Unlike the generic parser, nested JSON examples and 100-item lists cannot
    masquerade as the required N items. The generic count is returned only when
    wrong so the caller's existing mismatch/split error path remains descriptive.
    """
    raw = str(text or "")
    decoder = json.JSONDecoder()
    candidates: list[tuple[int, list[str]]] = []
    index = 0
    while index < len(raw):
        if raw[index] not in "[{":
            index += 1
            continue
        try:
            payload, consumed = decoder.raw_decode(raw, index)
        except ValueError:
            index += 1
            continue
        accepted = _exact_translations(payload, expected)
        if accepted is not None:
            values, priority = accepted
            candidates.append((priority, values))
        # Skip a fully parsed JSON container even if it contains 100 entries;
        # otherwise a single nested object could masquerade as a 1-item reply.
        index = consumed

    if candidates:
        # Highest score requires explicit, unique IDs; last is the final answer
        # when a model also emits JSON examples before its final output.
        top_score = max(score for score, _ in candidates)
        return next(values for score, values in reversed(candidates) if score == top_score), []

    # Plain numbered lines are accepted only with all IDs exactly 1..N.
    numbered: dict[int, str] = {}
    for line in raw.strip().splitlines():
        match = re.fullmatch(r"\s*(\d+)[.)]\s+(.+?)\s*", line)
        if not match:
            numbered = {}
            break
        item_id, value = int(match.group(1)), match.group(2)
        if item_id in numbered or not 1 <= item_id <= expected:
            numbered = {}
            break
        numbered[item_id] = value
    if len(numbered) == expected:
        return [numbered[index] for index in range(1, expected + 1)], []

    # Preserve count diagnostics (e.g. got 100), but never accept non-strict
    # results just because the generic parser returned N unverified lines.
    generic, _terms = parse_hq_response(raw)
    if len(generic) == expected:
        return [], []
    return generic, []
