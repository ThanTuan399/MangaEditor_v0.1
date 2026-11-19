"""Local-only Ollama configuration and connection checks.

Keep these helpers dependency-free so the GUI can probe Ollama without
importing or initializing model/translation engines.
"""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_OLLAMA_MODEL = "qwen3:4b"
_LOOPBACK_HOSTS = frozenset(("127.0.0.1", "localhost", "::1"))


def normalize_ollama_base_url(value: str | None) -> str:
    """Return an OpenAI-compatible /v1 endpoint confined to this machine."""
    raw = str(value or DEFAULT_OLLAMA_BASE_URL).strip()
    try:
        parts = urlsplit(raw)
        port = parts.port
        host = parts.hostname
    except ValueError as exc:
        raise ValueError("Địa chỉ Ollama không hợp lệ.") from exc
    if (parts.scheme != "http" or host not in _LOOPBACK_HOSTS
            or not parts.netloc or parts.username or parts.password
            or parts.query or parts.fragment):
        raise ValueError(
            "Ollama chỉ được kết nối cục bộ: ví dụ http://127.0.0.1:11434/v1"
        )
    if parts.path.rstrip("/") not in ("", "/v1"):
        raise ValueError("API URL của Ollama phải kết thúc bằng /v1.")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Cổng Ollama không hợp lệ.")
    return urlunsplit(("http", parts.netloc, "/v1", "", ""))


def validate_ollama_model_name(model: str | None) -> str:
    name = str(model or "").strip()
    if not name:
        raise ValueError("Bạn chưa nhập tên mô hình Ollama (ví dụ qwen3:4b).")
    return name


def check_ollama_connection(
    base_url: str | None = DEFAULT_OLLAMA_BASE_URL,
    model: str | None = DEFAULT_OLLAMA_MODEL,
    timeout: float = 4.0,
) -> str:
    """Probe /v1/models without generating text; safe for a background thread."""
    endpoint = normalize_ollama_base_url(base_url)
    name = validate_ollama_model_name(model)
    request = Request(
        f"{endpoint}/models",
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read(2_000_000).decode("utf-8"))
    except (URLError, TimeoutError, OSError, HTTPError) as exc:
        raise ConnectionError(
            f"Không kết nối được Ollama tại {endpoint}. "
            "Hãy mở Ollama hoặc chạy 'ollama serve'."
        ) from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise ConnectionError("Ollama trả về danh sách mô hình không hợp lệ.") from exc
    entries = result.get("data", []) if isinstance(result, dict) else []
    available = {
        item.get("id")
        for item in entries
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if name not in available:
        raise ValueError(
            f"Ollama đang chạy nhưng chưa có mô hình '{name}'. "
            f"Hãy chạy: ollama pull {name}"
        )
    return f"Ollama kết nối thành công · {name}"
