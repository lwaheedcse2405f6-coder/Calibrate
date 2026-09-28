import hashlib

import pytest

from app import config
from app.llm import groq_client


def test_missing_key_gives_friendly_error(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    monkeypatch.setattr(groq_client, "_client", None)
    monkeypatch.setattr(groq_client, "CACHE_DIR", tmp_path)
    with pytest.raises(groq_client.LLMError):
        groq_client.ask_json("system text", "user text")


def test_cached_answer_skips_the_api(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    monkeypatch.setattr(groq_client, "CACHE_DIR", tmp_path)
    key = hashlib.sha256(
        f"{config.GROQ_MODEL_FAST}|system text|user text".encode()
    ).hexdigest()
    (tmp_path / f"{key}.json").write_text('{"ok": true}', encoding="utf-8")
    assert groq_client.ask_json("system text", "user text") == {"ok": True}