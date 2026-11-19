"""Ollama local translator for the automatic manga pipeline.

Reuse the established OpenAI text translator's batching, prompt building,
cancellation, validation and retry logic, while keeping its credentials,
API rotation and model settings completely separate from OpenAI.
"""
from __future__ import annotations

import asyncio
import copy
import json

from .common import CommonTranslator, VALID_LANGUAGES, _flatten_prompt_data
from .ollama_response import parse_ollama_response
from .openai import OpenAITranslator
from ..utils.ollama_local import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    normalize_ollama_base_url,
    check_ollama_connection,
    validate_ollama_model_name,
)


class OllamaTranslator(OpenAITranslator):
    def __init__(self):
        # Calling OpenAITranslator.__init__ here would read OPENAI_API_KEY and
        # instantiate an OpenAI client. Ollama must never inherit those values.
        CommonTranslator.__init__(self)
        self.client = None
        self.prev_context = ""
        self.api_key = "ollama"  # ignored by local Ollama; SDK requires a value
        self.base_url = DEFAULT_OLLAMA_BASE_URL
        self.model = DEFAULT_OLLAMA_MODEL
        self._runtime_api_settings = None  # disable OpenAI API key rotation
        self.max_tokens = None
        self._MAX_REQUESTS_PER_MINUTE = 0
        self._last_request_ts_key = f"ollama:{self.model}"
        self._ollama_disable_thinking = True
        self._enable_streaming = False
        self.ollama_batch_size = 3

    def parse_args(self, args):
        CommonTranslator.parse_args(self, args)
        cfg = self._resolve_translator_config(args)
        model = validate_ollama_model_name(
            self._get_config_value(cfg, "ollama_model", DEFAULT_OLLAMA_MODEL)
        )
        base = normalize_ollama_base_url(
            self._get_config_value(cfg, "ollama_base_url", DEFAULT_OLLAMA_BASE_URL)
        )
        self._ollama_disable_thinking = bool(
            self._get_config_value(cfg, "ollama_disable_thinking", True)
        )
        self._enable_streaming = bool(
            self._get_config_value(cfg, "ollama_streaming", False)
        )
        # General CLI defaults to unlimited retries; an offline local server
        # must fail promptly rather than retry forever on connection errors.
        if self.attempts == -1:
            self.attempts = 2  # two retries plus the initial request = 3 total
        self._max_total_attempts = self._resolve_max_total_attempts()
        self._runtime_api_settings = None
        try:
            requested_batch = int(self._get_config_value(cfg, "ollama_batch_size", 3))
        except (TypeError, ValueError):
            requested_batch = 3
        self.ollama_batch_size = max(1, min(requested_batch, 8))
        old_identity = (self.base_url, self.model)
        self.base_url = base
        self.model = model
        self.api_key = "ollama"
        self._last_request_ts_key = f"ollama:{model}"
        if self.client is not None and (base, model) != old_identity:
            self._setup_client(force_recreate=True)

    def _resolve_translator_custom_api_params(self, model_name):
        # Ollama's OpenAI-compatible API supports reasoning_effort="none"
        # for Qwen3-style thinking models. The user can turn it off in Settings.
        del model_name
        return {"reasoning_effort": "none"} if self._ollama_disable_thinking else {}

    def _is_streaming_enabled(self, ctx=None) -> bool:
        # This is an Ollama-only toggle; never inherit OpenAI streaming settings.
        return self._enable_streaming

    def _parse_translation_response(self, result_text: str, expected_count: int):
        return parse_ollama_response(result_text, expected_count)

    def _get_system_prompt(
        self, source_lang, target_lang, custom_prompt_json=None,
        line_break_prompt_json=None, retry_attempt=0,
        retry_reason="", extract_glossary=False,
    ):
        # Qwen3:4b struggles with the large cloud-AI prompt with many JSON
        # examples. Ask for just the current IDs; keep custom style/terminology.
        source = VALID_LANGUAGES.get(source_lang, source_lang)
        target = VALID_LANGUAGES.get(target_lang, target_lang)
        prompts = [
            f"You are a professional manga dialogue translator. Translate from {source} to {target}.",
            "Return ONLY one JSON object in exactly this shape:",
            '{"translations":[{"id":1,"translation":"translated text"}]}',
            "Use the input IDs from the latest user message, exactly once each.",
            "The number of translations MUST equal the number of input items.",
            "Do not translate previous messages, repeat input examples, create extra IDs,",
            "add alternatives, add explanations, or wrap JSON in Markdown.",
            "Maintain names, meaning, character voice, and punctuation.",
            "When original_region_count exceeds 1 and line breaks are requested,",
            "preserve required [BR] markers; otherwise do not invent [BR] markers.",
        ]
        if custom_prompt_json:
            prompts.append("Additional translation rules:\n" + _flatten_prompt_data(custom_prompt_json))
        if line_break_prompt_json and isinstance(line_break_prompt_json, dict):
            line_break_instruction = line_break_prompt_json.get("line_break_prompt")
            if line_break_instruction:
                prompts.append("Line breaking rules:\n" + str(line_break_instruction))
        if retry_attempt:
            prompts.append(
                f"Previous answer invalid ({retry_reason}). "
                "Return only the exact required IDs and number of translations."
            )
        return "\n".join(prompts)

    def _build_user_prompt(self, texts, ctx, retry_attempt=0, retry_reason=""):
        # Each chunk starts IDs at 1; the parser checks those IDs strictly.
        enable_ai_break = bool(
            getattr(getattr(getattr(ctx, "config", None), "render", None),
                    "disable_auto_wrap", False)
        )
        regions = getattr(ctx, "text_regions", None) or []
        items = []
        for i, text in enumerate(texts):
            item = {"id": i + 1, "text": str(text or "").replace("\n", " ").replace("\ufffd", "")}
            if enable_ai_break:
                region = regions[i] if i < len(regions) else None
                lines = getattr(region, "lines", None)
                if lines is None and isinstance(region, dict):
                    lines = region.get("lines")
                item["original_region_count"] = (
                    len(lines) if lines is not None else max(1, str(text).count("\n") + 1)
                )
            items.append(item)
        return (
            f"Translate exactly {len(items)} items. Output only JSON with exactly "
            f"{len(items)} translations and IDs 1 through {len(items)}:\n"
            + json.dumps(items, ensure_ascii=False, separators=(",", ":"))
        )

    def _build_openai_context_messages(self, prev_context):
        # A small local model can accidentally retranslate dialogue from old
        # pages, yielding 100 items for 18 inputs. Keep the current batch only.
        return []

    def _context_for_chunk(self, ctx, start, end):
        if ctx is None or getattr(ctx, "text_regions", None) is None:
            return ctx
        try:
            scoped = copy.copy(ctx)
            scoped.text_regions = ctx.text_regions[start:end]
            return scoped
        except (AttributeError, TypeError):
            # Avoid modifying the original context if it cannot be copied.
            return ctx

    async def _translate_chunk(
        self, texts, source_lang, target_lang, ctx,
        custom_prompt_json=None, line_break_prompt_json=None,
    ):
        # The inherited OpenAI translator counts API attempts globally.
        # Budget retries per chunk instead of exhausting them on page 1.
        self._reset_global_attempt_count()
        try:
            result = await self._translate_batch(
                texts, source_lang=source_lang, target_lang=target_lang,
                custom_prompt_json=custom_prompt_json,
                line_break_prompt_json=line_break_prompt_json, ctx=ctx,
            )
            if len(result) != len(texts):
                raise ValueError(
                    f"Translation count mismatch: expected {len(texts)}, got {len(result)}"
                )
            return result
        except Exception as exc:
            if "translation count mismatch" not in str(exc).lower():
                raise
            if len(texts) == 1:
                raise RuntimeError(
                    "Ollama vẫn trả sai số lượng bản dịch cho một vùng chữ. "
                    "Hãy kiểm tra tên model, tắt thinking và xem log phản hồi Ollama."
                ) from exc
            middle = len(texts) // 2
            self.logger.warning(
                "Ollama result count mismatch for %d regions: "
                "automatically splitting into %d + %d regions",
                len(texts), middle, len(texts) - middle,
            )
            left_context = self._context_for_chunk(ctx, 0, middle)
            right_context = self._context_for_chunk(ctx, middle, len(texts))
            left = await self._translate_chunk(
                texts[:middle], source_lang, target_lang, left_context,
                custom_prompt_json, line_break_prompt_json,
            )
            right = await self._translate_chunk(
                texts[middle:], source_lang, target_lang, right_context,
                custom_prompt_json, line_break_prompt_json,
            )
            return left + right

    async def _translate(self, from_lang, to_lang, queries, ctx=None):
        if not queries:
            return []
        await asyncio.to_thread(
            check_ollama_connection, self.base_url, self.model, 3.0
        )
        custom_prompt_json = getattr(ctx, "custom_prompt_json", None)
        line_break_prompt_json = getattr(ctx, "line_break_prompt_json", None)
        results = []
        for start in range(0, len(queries), self.ollama_batch_size):
            self._check_cancelled()
            batch = queries[start:start + self.ollama_batch_size]
            batch_ctx = self._context_for_chunk(ctx, start, start + len(batch))
            self.logger.info(
                "Ollama: translating regions %d-%d/%d",
                start + 1, start + len(batch), len(queries),
            )
            translated = await self._translate_chunk(
                batch, from_lang, to_lang, batch_ctx,
                custom_prompt_json, line_break_prompt_json,
            )
            results.extend(translated)
        if len(results) != len(queries):
            raise ValueError(
                f"Translation count mismatch: expected {len(queries)}, got {len(results)}"
            )
        return [
            self._clean_translation_output(source, translated, to_lang)
            for source, translated in zip(queries, results)
        ]

