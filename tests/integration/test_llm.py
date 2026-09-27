"""Tests del cliente LLM, portados de Night Council (tests/test_llm.py)."""
import json
import os

import pytest

from core.llm import LLMError, OpenAICompatClient, extract_json, validate


def test_extract_json_handles_think_blocks_and_fences():
    raw = '<think>razono {"no": 1}</think>\n```json\n{"a": {"b": "x}"}, "c": [1, 2]}\n```'
    assert extract_json(raw) == {"a": {"b": "x}"}, "c": [1, 2]}


def test_extract_json_rejects_text_without_object():
    with pytest.raises(LLMError):
        extract_json("no sé")


def test_validate_reports_each_violation():
    schema = {"type": "object", "required": ["a", "b"],
              "properties": {"a": {"type": "integer", "enum": [-1, 1]}, "b": {"type": "string", "maxLength": 3}}}
    assert len(validate({"a": 2, "b": "abcd"}, schema)) == 2
    assert validate({"a": 1, "b": "ab"}, schema) == []
    assert validate({"a": True, "b": "ab"}, schema)          # bool no es integer
    assert validate({"b": "ab"}, schema) == ["$.a: falta"]


def test_request_key_is_stable_and_ignores_the_api_key():
    a = OpenAICompatClient("https://x", "sk-uno", "m")
    b = OpenAICompatClient("https://x", "sk-dos", "m")
    k = a.request_key("s", "u", {"type": "object"}, 100)
    assert k == b.request_key("s", "u", {"type": "object"}, 100)
    assert k != a.request_key("s", "u2", {"type": "object"}, 100)


def test_request_key_includes_extra_body():
    a = OpenAICompatClient("https://x", "sk", "m")
    b = OpenAICompatClient("https://x", "sk", "m", extra_body={"reasoning": {"effort": "high"}})
    schema = {"type": "object"}
    assert a.request_key("s", "u", schema, 100) != b.request_key("s", "u", schema, 100)


def test_replay_without_cassette_fails_clearly(tmp_path):
    c = OpenAICompatClient("", "", "m", mode="replay", cassette_dir=tmp_path)
    with pytest.raises(LLMError, match="NDE1_LLM_MODE=record"):
        c.complete_json(purpose="scout", system="s", user="u", schema={"type": "object"}, prompt_version="t@0")


def test_cache_mode_replays_what_is_recorded_and_calls_only_for_the_rest(tmp_path):
    """Modo `cache`: reanudar una corrida larga sin repetir llamadas ni inventar respuestas."""
    c = OpenAICompatClient("", "", "m", mode="cache", cassette_dir=tmp_path)
    schema = {"type": "object", "required": ["a"], "properties": {"a": {"type": "integer"}}}
    key = c.request_key("s", "u", schema, 100)
    (tmp_path / f"{key}.json").write_text(
        json.dumps({"model": "m", "messages": [], "raw": '{"a": 1}', "input_tokens": 3,
                    "output_tokens": 4, "latency_ms": 12}), encoding="utf-8")
    kw = dict(purpose="scout", schema=schema, prompt_version="t@0", max_tokens=100)
    obj, call = c.complete_json(system="s", user="u", **kw)
    assert obj == {"a": 1} and call.input_tokens == 3 and call.latency_ms == 12
    with pytest.raises(LLMError, match="faltan"):      # lo no grabado sí iría a la API
        c.complete_json(system="s", user="otra", **kw)


def test_for_ollama_needs_no_real_key():
    c = OpenAICompatClient.for_ollama("http://localhost:11434/v1", "qwen3:8b", mode="replay")
    assert c.model == "qwen3:8b" and c.mode == "replay"
