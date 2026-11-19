"""Ollama local translator for the automatic manga pipeline.

Reuse the established OpenAI text translator's batching, prompt building,
cancellation, validation and retry logic, while keeping its credentials,
API rotation and model settings completely separate from OpenAI.
"""
from __future__ import annotations

from .common import CommonTranslator
from .openai import OpenAITranslator
from ..utils.ollama_local import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    normalize_ollama_base_url,
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
        self._max_total_attempts = self._resolve_max_total_attempts()
        self._runtime_api_settings = None
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
