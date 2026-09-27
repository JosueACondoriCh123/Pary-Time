"""Cliente LLM OpenAI-compatible. Copiado de Night Council (night_council/llm.py, mismo autor).

En N-de-1 apunta a Ollama local (`http://localhost:11434/v1`, api_key cualquiera). Cambios: LLMCall y
LLMError viven acá, `from_env` se reemplazó por `for_ollama`, y la cassette usa NDE1_LLM_MODE.

Cuatro modos: live llama al modelo; record llama y graba la respuesta real en una cassette; replay
solo reproduce cassettes; cache reproduce si existe y si no graba. Los tests reproducen exactamente lo
que dijo el modelo, sin inventar respuestas.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from openai import (APIConnectionError, APIError, APITimeoutError, BadRequestError, OpenAI,
                    RateLimitError)

from dataclasses import dataclass

from core.journal.canon import canonical, sha256


@dataclass(frozen=True)
class LLMCall:
    """Rastro auditable de una llamada al modelo."""
    purpose: str            # "scout" | "red_team"
    model: str
    prompt_version: str     # "<nombre>@<sha256[:8] del prompt>"
    request_sha256: str
    response_sha256: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float


class LLMError(Exception):
    pass

MODES = ("live", "record", "replay", "cache")
_TYPES = {"object": dict, "array": list, "string": str, "integer": int,
          "number": (int, float), "boolean": bool}


def extract_json(raw: str) -> dict:
    """Primer objeto JSON balanceado de la respuesta. Ignora <think>…</think> y ```fences```."""
    text = re.sub(r"(?is)<think>.*?</think>", "", raw).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    if start < 0:
        raise LLMError("la respuesta no contiene un objeto JSON")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError as e:
                    raise LLMError(f"JSON inválido: {e}") from e
    raise LLMError("objeto JSON sin cerrar")


def validate(obj, schema: dict, path: str = "$") -> list[str]:
    """Subset de JSON Schema: type (str o lista), enum, minimum, maximum, maxLength,
    required, properties, items."""
    t = schema.get("type")
    if t:
        allowed = t if isinstance(t, list) else [t]
        if not any(isinstance(obj, _TYPES[x]) and not (x in ("integer", "number") and isinstance(obj, bool))
                   for x in allowed):
            return [f"{path}: se esperaba {t}"]
    errs = []
    if "enum" in schema and obj not in schema["enum"]:
        errs.append(f"{path}: {obj!r} fuera de {schema['enum']}")
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        if "minimum" in schema and obj < schema["minimum"]:
            errs.append(f"{path}: {obj} < {schema['minimum']}")
        if "maximum" in schema and obj > schema["maximum"]:
            errs.append(f"{path}: {obj} > {schema['maximum']}")
    if isinstance(obj, str) and "maxLength" in schema and len(obj) > schema["maxLength"]:
        errs.append(f"{path}: {len(obj)} caracteres > {schema['maxLength']}")
    if isinstance(obj, dict):
        errs += [f"{path}.{k}: falta" for k in schema.get("required", []) if k not in obj]
        for k, sub in schema.get("properties", {}).items():
            if k in obj:
                errs += validate(obj[k], sub, f"{path}.{k}")
    if isinstance(obj, list) and "items" in schema:
        for i, v in enumerate(obj):
            errs += validate(v, schema["items"], f"{path}[{i}]")
    return errs


class OpenAICompatClient:
    def __init__(self, base_url: str, api_key: str, model: str, *, price_in: float = 0.0,
                 price_out: float = 0.0, mode: str = "live", cassette_dir: Path | None = None,
                 retries: int = 3, timeout: float = 90, extra_body: dict | None = None):
        if mode not in MODES:
            raise ValueError(f"modo LLM inválido: {mode}")
        self.model, self.mode = model, mode
        self.price_in, self.price_out, self.retries = price_in, price_out, retries
        self.extra_body = extra_body
        self.cassette_dir = Path(cassette_dir) if cassette_dir else None
        self._client = None
        if mode != "replay" and base_url and api_key:
            self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0)

    @classmethod
    def for_ollama(cls, base_url: str, model: str, *, mode: str | None = None,
                   cassette_dir: Path | None = None, timeout: float = 300) -> "OpenAICompatClient":
        """Ollama no pide clave, pero el SDK exige una no vacía."""
        return cls(base_url, "ollama", model, mode=mode or os.getenv("NDE1_LLM_MODE", "live"),
                   cassette_dir=cassette_dir, timeout=timeout)

    def request_key(self, system: str, user: str, schema: dict, max_tokens: int) -> str:
        return sha256(canonical({"model": self.model, "system": system, "user": user, "schema": schema,
                                 "max_tokens": max_tokens, "temperature": 0, "extra_body": self.extra_body}))

    def complete_json(self, *, purpose: str, system: str, user: str, schema: dict,
                      prompt_version: str, max_tokens: int = 1200,
                      normalize=None) -> tuple[dict, LLMCall]:
        key = self.request_key(system, user, schema, max_tokens)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        problem = ""
        for attempt in range(2):  # un intento de reparación de formato
            raw, tin, tout, ms = self._raw(key if attempt == 0 else f"{key}-r1", messages, max_tokens)
            try:
                obj = extract_json(raw)
                if normalize is not None:
                    obj = normalize(obj)
                errs = validate(obj, schema)
            except LLMError as e:
                obj, errs = None, [str(e)]
            if not errs:
                cost = round(tin * self.price_in / 1e6 + tout * self.price_out / 1e6, 6)
                return obj, LLMCall(purpose, self.model, prompt_version, key, sha256(raw), tin, tout, ms, cost)
            problem = "; ".join(errs[:5])
            messages = messages + [{"role": "assistant", "content": raw},
                                   {"role": "user", "content": f"Tu respuesta no cumple el formato: {problem}. "
                                                               "Devolvé SOLO el objeto JSON corregido."}]
        raise LLMError(f"{purpose}: respuesta inválida tras reparar: {problem}")

    def _raw(self, cassette_key: str, messages: list[dict], max_tokens: int) -> tuple[str, int, int, int]:
        path = self.cassette_dir / f"{cassette_key}.json" if self.cassette_dir else None
        cached = self.mode == "cache" and path is not None and path.exists()
        if self.mode == "replay" or cached:
            if not path or not path.exists():
                raise LLMError(f"sin cassette {cassette_key[:12]}: grabala con NDE1_LLM_MODE=record")
            c = json.loads(path.read_text(encoding="utf-8"))
            return c["raw"], c["input_tokens"], c["output_tokens"], c["latency_ms"]
        raw, tin, tout, ms = self._call_api(messages, max_tokens)
        if self.mode in ("record", "cache") and path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"model": self.model, "messages": messages, "raw": raw,
                                        "input_tokens": tin, "output_tokens": tout, "latency_ms": ms},
                                       ensure_ascii=False, indent=1), encoding="utf-8")
        return raw, tin, tout, ms

    def _call_api(self, messages: list[dict], max_tokens: int) -> tuple[str, int, int, int]:
        if self._client is None:
            raise LLMError("faltan base_url / model del LLM (¿Ollama configurado en Settings?)")
        json_mode = True
        for attempt in range(self.retries + 1):
            t0 = time.monotonic()
            try:
                extra = {"response_format": {"type": "json_object"}} if json_mode else {}
                if self.extra_body:
                    extra["extra_body"] = self.extra_body
                r = self._client.chat.completions.create(model=self.model, messages=messages, temperature=0,
                                                         max_tokens=max_tokens, **extra)
                u = r.usage
                return (r.choices[0].message.content or "", getattr(u, "prompt_tokens", 0) or 0,
                        getattr(u, "completion_tokens", 0) or 0, int((time.monotonic() - t0) * 1000))
            except BadRequestError as e:
                if json_mode and "response_format" in str(e).lower():
                    json_mode = False  # el proveedor no soporta JSON mode para este modelo
                    continue
                raise LLMError(f"request rechazado por el proveedor: {e.status_code}") from e
            except (RateLimitError, APITimeoutError, APIConnectionError, APIError) as e:
                code = getattr(e, "status_code", None)
                if attempt == self.retries:
                    raise LLMError(
                        f"API del LLM no disponible: {type(e).__name__}"
                        + (f" {code}" if code else "")
                    ) from e
                wait = 30 * (attempt + 1) if code == 429 else min(2 ** attempt * 2, 60)
                time.sleep(wait)
        raise LLMError("sin respuesta del LLM")
