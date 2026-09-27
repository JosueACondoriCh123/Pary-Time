"""Roles con LLM: Scout (propone) y pre-mortem del Red Team (sin veto). Modelos de familias distintas.

Un LLM que falla no frena al consejo: el Scout cae al respaldo del Allocator y el pre-mortem queda vacío.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.contracts import INTERVENTIONS, Hypothesis, ToolVerdict
from core.council.snapshot import Snapshot
from core.journal.canon import sha256
from core.llm import LLMCall, LLMError, OpenAICompatClient

PROMPTS = Path(__file__).parent / "prompts"
MAX_HYPOTHESES = 3

SCOUT_SCHEMA = {
    "type": "object", "required": ["abstain", "hypotheses"],
    "properties": {
        "abstain": {"type": "boolean"},
        "hypotheses": {"type": "array", "items": {
            "type": "object", "required": ["intervention", "expected_ratio", "rationale", "cited_block_ids"],
            "properties": {
                "intervention": {"type": "string", "enum": [a.value for a in INTERVENTIONS]},
                "moderator": {"type": ["object", "null"]},
                "expected_ratio": {"type": "number", "minimum": 0.05, "maximum": 1.0},
                "rationale": {"type": "string", "maxLength": 600},
                "cited_block_ids": {"type": "array", "items": {"type": "string"}},
            }}},
    }}
PREMORTEM_SCHEMA = {"type": "object", "required": ["premortem"],
                    "properties": {"premortem": {"type": "string", "maxLength": 1200}}}


def _prompt(name: str) -> tuple[str, str]:
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    return text, f"{name}@{sha256(text)[:8]}"


def scout(client: OpenAICompatClient, snapshot: Snapshot) -> tuple[list[Hypothesis], LLMCall, list[str]]:
    """Hipótesis válidas según el contrato, la llamada auditable y lo descartado por formato."""
    system, version = _prompt("scout")
    obj, call = client.complete_json(purpose="scout", system=system, user=snapshot.to_prompt(),
                                     schema=SCOUT_SCHEMA, prompt_version=version, max_tokens=2000)
    if obj.get("abstain"):
        return [], call, []
    hyps, dropped = [], []
    for raw in obj.get("hypotheses", [])[:MAX_HYPOTHESES]:
        try:
            hyps.append(Hypothesis.model_validate(raw))
        except ValueError as e:
            dropped.append(str(e).splitlines()[0][:120])
    return hyps, call, dropped


def premortem(client: OpenAICompatClient, h: Hypothesis, tools: list[ToolVerdict]) -> str:
    system, version = _prompt("premortem")
    user = json.dumps({"hipotesis": h.model_dump(mode="json"),
                       "herramientas": [t.model_dump(mode="json") for t in tools]}, ensure_ascii=False)
    try:
        obj, _ = client.complete_json(purpose="red_team", system=system, user=user, schema=PREMORTEM_SCHEMA,
                                      prompt_version=version, max_tokens=700)
        return obj["premortem"]
    except LLMError:
        return ""
