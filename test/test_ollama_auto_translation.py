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
    assert backend._max_total_attempts == 3  # 2 retries + initial call


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

    async def fake_translate_batch(texts, source_lang, target_lang, **kwargs):
        batches.append((list(texts), source_lang, target_lang))
        return ["Xin chào", "Tạm biệt"]

    monkeypatch.setattr(
        "manga_translator.translators.ollama.check_ollama_connection", check
    )
    monkeypatch.setattr(backend, "_translate_batch", fake_translate_batch)
    monkeypatch.setattr(backend, "_clean_translation_output", lambda o, t, lang: t)

    output = asyncio.run(backend._translate("JPN", "VIN", ["こんにちは", "さようなら"]))
    assert output == ["Xin chào", "Tạm biệt"]
    assert batches == [(["こんにちは", "さようなら"], "JPN", "VIN")]
    assert check_calls == [
        ("http://127.0.0.1:11434/v1", "qwen3:4b", 3.0)
    ]



def test_ollama_parser_reorders_exact_unique_ids():
    from manga_translator.translators.ollama_response import parse_ollama_response
    message = json.dumps({
        "translations": [
            {"id": 3, "translation": "Ba"},
            {"id": 1, "translation": "Một"},
            {"id": 2, "translation": "Hai"},
        ]
    }, ensure_ascii=False)
    assert parse_ollama_response(message, 3)[0] == ["Một", "Hai", "Ba"]


def test_ollama_parser_skips_overlong_example_even_if_it_has_100_entries():
    from manga_translator.translators.ollama_response import parse_ollama_response
    example = {"translations": [
        {"id": idx, "translation": f"wrong {idx}"} for idx in range(1, 101)
    ]}
    actual = {"translations": [
        {"id": 2, "translation": "Đúng số hai"},
        {"id": 1, "translation": "Đúng số một"},
    ]}
    raw = "An example:\n" + json.dumps(example) + "\nFinal:\n" + json.dumps(actual, ensure_ascii=False)
    assert parse_ollama_response(raw, 2)[0] == ["Đúng số một", "Đúng số hai"]


def test_ollama_parser_never_truncates_100_entries_to_18():
    from manga_translator.translators.ollama_response import parse_ollama_response
    payload = json.dumps({"translations": [
        {"id": idx, "translation": f"Wrong {idx}"}
        for idx in range(1, 101)
    ]})
    texts, _ = parse_ollama_response(payload, 18)
    assert len(texts) != 18
    assert len(texts) == 100


def test_ollama_parser_rejects_duplicate_and_missing_ids():
    from manga_translator.translators.ollama_response import parse_ollama_response
    payload = json.dumps({"translations": [
        {"id": 1, "translation": "wrong"},
        {"id": 1, "translation": "duplicate"},
    ]})
    parsed, _ = parse_ollama_response(payload, 2)
    assert len(parsed) != 2


def test_ollama_parser_numbered_lines_only_with_exact_ids():
    from manga_translator.translators.ollama_response import parse_ollama_response
    assert parse_ollama_response("2. Hai\n1. Một", 2)[0] == ["Một", "Hai"]
    assert parse_ollama_response("1. Một\n1. Hai", 2)[0] != ["Một", "Hai"]


def test_ollama_splits_full_page_into_small_batches(monkeypatch):
    monkeypatch.setattr(
        "manga_translator.translators.ollama.check_ollama_connection",
        lambda *args: "available",
    )
    backend = OllamaTranslator()
    backend.parse_args(Config())
    seen = []

    async def fake_batch(texts, source_lang, target_lang, **kwargs):
        seen.append((list(texts), backend._global_attempt_count))
        backend._global_attempt_count += 1
        return [f"VN:{x}" for x in texts]

    monkeypatch.setattr(backend, "_translate_batch", fake_batch)
    monkeypatch.setattr(backend, "_clean_translation_output", lambda source, trans, lang: trans)
    original = [f"region {i}" for i in range(18)]
    actual = asyncio.run(backend._translate("JPN", "VIN", original))
    assert actual == [f"VN:{x}" for x in original]
    assert [len(batch) for batch, _attempts in seen] == [3] * 6
    assert all(counter == 0 for _batch, counter in seen)


def test_ollama_recursively_splits_count_mismatch_to_single_regions(monkeypatch):
    monkeypatch.setattr(
        "manga_translator.translators.ollama.check_ollama_connection",
        lambda *args: "available",
    )
    backend = OllamaTranslator()
    backend.parse_args(Config())
    groups = []

    async def fake_batch(texts, source_lang, target_lang, **kwargs):
        groups.append(tuple(texts))
        if len(texts) > 1:
            # Simulates the inherited translator rejecting a response with
            # wrong translation count after its own retry budget.
            raise ValueError("Translation count mismatch: expected 3, got 100")
        return [f"Translated {texts[0]}"]

    monkeypatch.setattr(backend, "_translate_batch", fake_batch)
    monkeypatch.setattr(backend, "_clean_translation_output", lambda source, trans, lang: trans)
    original = ["A", "B", "C", "D"]
    actual = asyncio.run(backend._translate("JPN", "VIN", original))
    assert actual == [f"Translated {item}" for item in original]
    assert groups[0] == ("A", "B", "C")
    assert ("A",) in groups and ("B",) in groups and ("C",) in groups


def test_ollama_one_region_failure_is_not_silently_accepted(monkeypatch):
    monkeypatch.setattr(
        "manga_translator.translators.ollama.check_ollama_connection",
        lambda *args: "available",
    )
    backend = OllamaTranslator()
    backend.parse_args(Config())

    async def bad_batch(texts, source_lang, target_lang, **kwargs):
        raise ValueError("Translation count mismatch: expected 1, got 100")

    monkeypatch.setattr(backend, "_translate_batch", bad_batch)
    with pytest.raises(RuntimeError, match="một vùng chữ"):
        asyncio.run(backend._translate("JPN", "VIN", ["one"]))


def test_ollama_non_count_errors_remain_visible(monkeypatch):
    monkeypatch.setattr(
        "manga_translator.translators.ollama.check_ollama_connection",
        lambda *args: "available",
    )
    backend = OllamaTranslator()
    backend.parse_args(Config())

    async def bad_batch(texts, source_lang, target_lang, **kwargs):
        raise ConnectionError("Ollama API unavailable")

    monkeypatch.setattr(backend, "_translate_batch", bad_batch)
    with pytest.raises(ConnectionError, match="unavailable"):
        asyncio.run(backend._translate("JPN", "VIN", ["one", "two"]))


def test_ollama_small_prompt_requests_exact_region_ids():
    backend = OllamaTranslator()
    backend.parse_args(Config())
    system_prompt = backend._get_system_prompt("JPN", "VIN")
    user_prompt = backend._build_user_prompt(["text A", "text B", "text C"], None)
    assert "3 items" in user_prompt
    assert '"id":1' in user_prompt and '"id":3' in user_prompt
    assert "previous messages" in system_prompt
    assert backend.ollama_batch_size == 3
