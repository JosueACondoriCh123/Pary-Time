"""Una reunión del consejo: snapshot → Scout → verificador → Red Team → Allocator → constitución → preregistro.

Escribe siempre un `council_run` (incluidos los vetos). Si elige algo, escribe el `preregistration` con el
compromiso de la semilla. La semilla queda en `data_dir/council/seeds/<experiment_id>.json` (local, nunca en
el journal) hasta la `resolution`, que la revela.
"""
from __future__ import annotations

import json
import random
import secrets
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from core.contracts import (Arm, CouncilRun, OUTCOME_RULES, Preregistration, ProposalRecord, Settings,
                            seed_commitment)
from core.council import llm_roles
from core.council.allocator import Candidate, choose, fallback_hypotheses
from core.council.journal_view import JournalView
from core.council.red_team import MIN_BASELINE_BLOCKS, fallback_ratio, report, run_tools
from core.council.snapshot import build_snapshot
from core.journal import Journal, append_typed
from core.llm import LLMError, OpenAICompatClient
from core.stats.ledger import build_ledger
from core.stats.multiplicity import next_alpha

COUNCIL_VERSION = "council@1"
LIMITATIONS = [
    "sin ciego: la persona ve la intervención",
    "primer_paso se revela al confirmar el día (hay que escribir el paso antes)",
    "moderador de franja horaria según el reloj local de la compu",
    "una sola persona: el resultado no generaliza",
]

ClientFactory = Callable[[str, str], OpenAICompatClient]      # (rol, modelo) -> cliente


def _hex12() -> str:
    return uuid.uuid4().hex[:12]


class SeedStore:
    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir) / "council" / "seeds"

    def save(self, experiment_id: str, seed_hex: str) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / f"{experiment_id}.tmp"
        tmp.write_text(json.dumps({"seed_hex": seed_hex}), encoding="utf-8")
        tmp.replace(self.dir / f"{experiment_id}.json")

    def load(self, experiment_id: str) -> str | None:
        try:
            return json.loads((self.dir / f"{experiment_id}.json").read_text(encoding="utf-8"))["seed_hex"]
        except FileNotFoundError:
            return None


@dataclass
class Council:
    journal: Journal
    settings: Callable[[], Settings]
    seeds: SeedStore
    client_factory: ClientFactory
    now_ms: Callable[[], int] = lambda: int(time.time() * 1000)

    def run(self) -> CouncilRun:
        s = self.settings()
        view = JournalView.load(self.journal)
        snap = build_snapshot(view)
        run_id, ran = f"run_{_hex12()}", self.now_ms()
        models = {"scout": s.scout_model, "red_team": s.red_team_model}

        def record(proposals, chosen=None, llm_used=False, reason=None) -> CouncilRun:
            run = CouncilRun(run_id=run_id, ran_ms=ran, snapshot_sha256=snap.sha256,
                             n_blocks_in_snapshot=len(snap.rows), proposals=proposals,
                             chosen_experiment_id=chosen, llm_used=llm_used, fallback_reason=reason, models=models)
            append_typed(self.journal, "council_run", run)
            return run

        if view.active_prereg() is not None:
            return record([], reason="ya hay un experimento en curso")
        if len(snap.rows) < MIN_BASELINE_BLOCKS:
            return record([], reason=f"línea base insuficiente: {len(snap.rows)} bloques < {MIN_BASELINE_BLOCKS}")

        # 1. Scout (familia A). Si falla o se abstiene, respaldo determinista.
        hyps, source, reason, llm_used = [], "scout", None, False
        try:
            hyps, _call, dropped = llm_roles.scout(self.client_factory("scout", s.scout_model), snap)
            llm_used = True
            if not hyps:
                reason = "el Scout se abstuvo" + (f" (descartadas por formato: {len(dropped)})" if dropped else "")
        except LLMError as e:
            reason = f"Scout no disponible: {e}"[:300]
        if not hyps:
            ratio = fallback_ratio(snap, view, next_alpha(view.alpha_history(), s.family_alpha))
            if ratio is None:
                return record([], llm_used=llm_used,
                              reason=(reason + "; " if reason else "") + "ni el respaldo entra en el tope de semanas")
            hyps, source = fallback_hypotheses(ratio), "allocator_fallback"

        # 2. Red Team: herramientas con veto (deterministas) + pre-mortem del LLM (familia B, sin veto).
        red_client = None
        try:
            red_client = self.client_factory("red_team", s.red_team_model)
        except LLMError:
            pass
        candidates = []
        for h in hyps:
            tools, plan = run_tools(h, snap, view, s, check_citations=source == "scout")
            pm = llm_roles.premortem(red_client, h, tools) if red_client is not None else ""
            candidates.append(Candidate(h, source, report(tools, pm), plan))
        proposals = [ProposalRecord(hypothesis=c.hypothesis, source=c.source, red_team=c.red_team)
                     for c in candidates]

        # 3. Allocator + constitución (ya aplicada como herramienta con veto).
        ledger = build_ledger(self._ledger_results(view))
        pick, prereg_source = choose(candidates, ledger, s.exploration_fraction, random.Random(run_id))
        if pick is None:
            return record(proposals, llm_used=llm_used, reason=reason or "todas las hipótesis fueron vetadas")

        # 4. Preregistro sellado ANTES del primer sorteo.
        exp_id, seed = f"exp_{_hex12()}", secrets.token_hex(32)
        self.seeds.save(exp_id, seed)
        run = record(proposals, chosen=exp_id, llm_used=llm_used, reason=reason)
        prereg = Preregistration(
            experiment_id=exp_id, created_ms=self.now_ms(), hypothesis=pick.hypothesis,
            arms=(Arm.control, pick.hypothesis.intervention), outcome_rules=OUTCOME_RULES,
            n_per_arm=pick.plan.n_per_arm, alpha=round(pick.plan.alpha, 6), seed_commitment=seed_commitment(seed),
            source=prereg_source, red_team=pick.red_team, limitations=LIMITATIONS, council_version=COUNCIL_VERSION)
        append_typed(self.journal, "preregistration", prereg)
        return run

    @staticmethod
    def _ledger_results(view: JournalView) -> list[tuple[Arm, str]]:
        out = []
        for p in view.preregs:
            r = view.resolutions.get(p.experiment_id)
            if r is not None:
                out.append((p.hypothesis.intervention, r.verdict))
        return out
