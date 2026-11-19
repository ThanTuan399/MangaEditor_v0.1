"""Phase 2: local Ollama backend and automatic translation integration."""
import _bootstrap  # noqa: F401

import asyncio
import json
from types import SimpleNamespace

import pytest

from manga_translator.config import Config, Translator
from manga_translator.translators import TRANSLATORS, get_translator
from manga_translator.translators.ollama import OllamaTranslator
from manga_translator.utils import ollama_local


@pytest.mark.parametrize(
    "url, expected",
    [
        ("http://127.0.0.1:11434", "http://127.0.0.1:11434/v1"),
        ("http://127.0.0.1:11434/v1/", "http://127.0.0.1:11434/v1"),
        ("http://localhost:11434/v1", "http://localhost:11434/v1"),
        ("http://[::1]:11434/v1", "http://[::1]:11434/v1"),
    ],
)
def test_local_endpoint_normalization(url, expected):
    assert ollama_local.normalize_ollama_base_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",
        "http://127.0.0.1.evil.example:11434/v1",
        "http://localhost:11434/v1?token=secret",
        "http://user:pass@localhost:11434/v1",
        "http://localhost:11434/api/chat",
        "ftp://localhost:11434/v1",
    ],
)
def test_ollama_rejects_nonlocal_or_unexpected_endpoints(url):
    with pytest.raises(ValueError):
        ollama_local.normalize_ollama_base_url(url)


def test_ollama_is_first_class_translator_with_own_settings(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-must-not-leak")
    monkeypatch.setenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")

    assert Translator("ollama") == Translator.ollama
    assert TRANSLATORS[Translator.ollama] is OllamaTranslator

    config = Config()
    config.translator.translator = Translator.ollama
    config.translator.ollama_model = "qwen3:4b"
    config.translator.ollama_base_url = "http://localhost:11434"
    backend = get_translator(config.translator.translator)
    assert backend.client is None  # not starting a paid OpenAI client
    backend.parse_args(config)
    assert backend.model == "qwen3:4b"
    assert backend.base_url == "http://localhost:11434/v1"
    assert backend.api_key == "ollama"
    assert backend._runtime_api_settings is None
    assert backend._max_total_attempts == 3  # no infinite retry on stopped server
    assert backend._resolve_translator_custom_api_params("qwen3:4b") == {
        "reasoning_effort": "none"
    }
    assert not backend._is_streaming_enabled()


def test_ollama_custom_settings_and_thinking_control():
    config = Config()
    config.translator.ollama_model = "qwen3:8b"
    config.translator.ollama_disable_thinking = False
    config.translator.ollama_streaming = True
    config.cli.attempts = 2
    backend = OllamaTranslator()
    backend.parse_args(config)
    assert backend.model == "qwen3:8b"
    assert backend._resolve_translator_custom_api_params("qwen3:8b") == {}
    assert backend._is_streaming_enabled() is True
    assert backend._max_total_attempts == 2


def test_gui_config_accepts_ollama_without_api_key():
    from desktop_qt_ui.core.config_models import AppSettings
    from desktop_qt_ui.services.config_service import RUNTIME_API_REQUIREMENTS

    config = AppSettings.model_validate(
        {"translator": {"translator": "ollama", "ollama_model": "qwen3:4b"}}
    )
    assert config.translator.translator == "ollama"
    assert config.translator.ollama_model == "qwen3:4b"
    assert "ollama" not in RUNTIME_API_REQUIREMENTS


class FakeResponse:
    def __init__(self, models):
        self.models = models

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, limit=None):
        del limit
        return json.dumps({"data": [{"id": x} for x in self.models]}).encode()


def test_ollama_probe_detects_local_model(monkeypatch):
    urls = []

    def fake_urlopen(req, timeout):
        urls.append((req.full_url, timeout))
        return FakeResponse(["qwen3:4b", "other:latest"])

    monkeypatch.setattr(ollama_local, "urlopen", fake_urlopen)
    assert "qwen3:4b" in ollama_local.check_ollama_connection(
        "http://127.0.0.1:11434/v1", "qwen3:4b"
    )
    assert urls == [("http://127.0.0.1:11434/v1/models", 4.0)]

    with pytest.raises(ValueError, match="ollama pull"):
        ollama_local.check_ollama_connection(
            "http://127.0.0.1:11434/v1", "missing:latest"
        )


def test_ollama_translation_uses_existing_batch_pipeline(monkeypatch):
    config = Config()
    config.translator.translator = Translator.ollama
    backend = OllamaTranslator()
    backend.parse_args(config)
    check_calls = []
    batches = []

    def check(url, model, timeout):
        check_calls.append((url, model, timeout))

    async def fake_translate_with_split(
        translate_func, texts, **kwargs
    ):
        batches.append((translate_func.__name__, list(texts), kwargs["target_lang"]))
        return ["Xin chào", "Tạm biệt"]

    monkeypatch.setattr(
        "manga_translator.translators.ollama.check_ollama_connection", check
    )
    monkeypatch.setattr(backend, "_translate_with_split", fake_translate_with_split)
    monkeypatch.setattr(backend, "_clean_translation_output", lambda o, t, lang: t)

    output = asyncio.run(backend._translate("JPN", "VIN", ["こんにちは", "さようなら"]))
    assert output == ["Xin chào", "Tạm biệt"]
    assert batches == [("_translate_batch", ["こんにちは", "さようなら"], "VIN")]
    assert check_calls == [
        ("http://127.0.0.1:11434/v1", "qwen3:4b", 3.0)
    ]
