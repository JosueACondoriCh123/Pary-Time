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
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from core.contracts import (Arm, CouncilRun, OUTCOME_RULES, Preregistration, ProposalRecord, Settings,
                            seed_commitment)
from core.council import llm_roles
from core.council.allocator import Candidate, choose, fallback_hypotheses
from core.council.journal_view import JournalView
from core.council.red_team import MAX_WEEKS, MIN_BASELINE_BLOCKS, fallback_ratio, report, run_tools
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
    new_id: Callable[[], str] = _hex12       # inyectable: la exploración se siembra con el run_id
    new_seed: Callable[[], str] = lambda: secrets.token_hex(32)   # inyectable solo para simular reproducible

    def run(self) -> CouncilRun:
        s = self.settings()
        view = JournalView.load(self.journal)
        snap = build_snapshot(view)
        run_id, ran = f"run_{self.new_id()}", self.now_ms()
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

        # Efecto mínimo detectable en el tope de semanas: restricción para el Scout y ratio del respaldo.
        mde = fallback_ratio(snap, view, next_alpha(view.alpha_history(), s.family_alpha))

        # 1. Scout (familia A).
        hyps, reason, llm_used = [], None, False
        try:
            constraints = {"ratio_max_detectable_sin_moderador": mde, "semanas_max": MAX_WEEKS}
            hyps, _call, dropped = llm_roles.scout(self.client_factory("scout", s.scout_model), snap, constraints)
            llm_used = True
            if not hyps:
                reason = "el Scout se abstuvo" + (f" (descartadas por formato: {len(dropped)})" if dropped else "")
        except LLMError as e:
            reason = f"Scout no disponible: {e}"[:300]

        # 2. Red Team determinista (con veto) sobre lo del Scout.
        def evaluate(hs, source):
            out = []
            for h in hs:
                tools, plan = run_tools(h, snap, view, s, check_citations=source == "scout")
                out.append(Candidate(h, source, report(tools, ""), plan))
            return out

        candidates = evaluate(hyps, "scout")
        # Si nada del Scout sobrevive (o no hubo Scout), entra el respaldo con el efecto mínimo detectable:
        # así una semana de hipótesis inviables no deja a la persona sin experimento.
        if not any(c.red_team.verdict == "pass" for c in candidates):
            why = reason or ("todas las hipótesis del Scout fueron vetadas" if candidates else "sin hipótesis")
            if mde is None:
                reason = why + "; ni el respaldo entra en el tope de semanas"
            else:
                candidates += evaluate(fallback_hypotheses(mde), "allocator_fallback")
                reason = why + "; respaldo con el efecto mínimo detectable"

        # 3. Allocator + constitución (ya aplicada como herramienta con veto).
        ledger = build_ledger(self._ledger_results(view))
        pick, prereg_source = choose(candidates, ledger, s.exploration_fraction, random.Random(run_id))
        if pick is not None:
            # Pre-mortem del Red Team LLM (familia B, sin veto) solo para lo elegido: una llamada, no ocho.
            try:
                pm = llm_roles.premortem(self.client_factory("red_team", s.red_team_model), pick.hypothesis,
                                         pick.red_team.tools)
            except LLMError:
                pm = ""
            chosen = replace(pick, red_team=report(pick.red_team.tools, pm))
            candidates = [chosen if c is pick else c for c in candidates]
            pick = chosen
        proposals = [ProposalRecord(hypothesis=c.hypothesis, source=c.source, red_team=c.red_team)
                     for c in candidates]
        if pick is None:
            return record(proposals, llm_used=llm_used, reason=reason or "todas las hipótesis fueron vetadas")

        # 4. Preregistro sellado ANTES del primer sorteo.
        exp_id, seed = f"exp_{self.new_id()}", self.new_seed()
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
