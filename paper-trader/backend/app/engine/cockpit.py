"""The operational read model — one coherent answer to "what is running here, and why".

**This module decides nothing.** It assembles answers the authoritative services already
give and correlates them by instrument. Every field traces to an existing owner:
`execution_binding` says what executes and on whose say-so, `paper_authority` and
`shadow_deployments` own their lifecycles, `execution_book` says whose money it is,
`analytics` owns P&L, `readiness` owns health, and `risk_controls` owns the entry gates.
Nothing here re-derives any of them.

That restraint is the point. A cockpit that computed its own view of "is this allowed to
trade" would be a second operational model, and the two would disagree exactly when it
mattered. So where this module cannot get an answer from the owning service, it says so in
the payload rather than working one out (see `entry_gates` below).

**Read-only, and structurally so.** Nothing here writes, arms, opens, closes or transitions
anything. Lifecycle control stays with the existing routes, which call the existing domain
services — `paper_authority.pause/resume/retire` and the arm/kill routes. This module is not
on the path of any of them.

**Research stays read-only and at arm's length.** The admission facts reported here —
`evidence_run_id`, `evidence_candidate_id`, `evidence_verified_at` — are read from the
*deployment row*, which recorded them at activation. No research database is opened. That is
ADR 0013's model made visible: research grants admission once, and the execution plane holds
the proof of it afterwards.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.core import execution_binding, execution_book, paper_authority
from app.core.execution_book import LIVE, PAPER

#: Why an instrument may not open a new entry right now. Each value is produced by the
#: service that owns the rule; this module only collects them. A gate absent from this
#: tuple is not "passing" — see `EntryEligibility.complete`.
GATE_DISARMED = "disarmed"
GATE_ENTRIES_BLOCKED = "entries_blocked_for_instrument"
GATE_DAILY_LOSS_HALT = "daily_loss_halt"
GATE_GAP_GUARD = "gap_guard"
GATE_NO_SLOTS = "no_position_slots"
GATE_ALREADY_HELD = "position_already_open"
GATE_NOT_ENABLED = "instrument_not_enabled"
GATE_AUTHORITY_REFUSED = "authority_refused"

BOOK_LEVEL_GATES = (GATE_DISARMED, GATE_DAILY_LOSS_HALT, GATE_GAP_GUARD, GATE_NO_SLOTS)


@dataclass(frozen=True)
class EntryEligibility:
    """Whether a new entry could open, and what is stopping it.

    `complete` is `False` on purpose and always. The full entry decision lives in
    `process_entries` and includes per-bar gates this read model has no bar to evaluate —
    signal freshness, the entry window, event blackouts, expiry proximity, re-entry
    cooldown, per-trade cap, round-trip cap, margin. Reporting `allowed=True` as though it
    were the whole answer would make this a second entry authority, so the flag says which
    question was actually answered: *are the standing gates clear?*
    """

    allowed: bool
    blocked_by: tuple[str, ...]
    complete: bool = False

    def to_dict(self) -> dict:
        return {"allowed": self.allowed, "blocked_by": list(self.blocked_by),
                "complete": self.complete,
                "note": ("standing gates only; the per-bar entry chain in process_entries "
                         "applies additional gates at signal time")}


@dataclass(frozen=True)
class InstrumentExecutionView:
    """Everything the cockpit needs about one instrument, correlated."""

    instrument_key: str
    enabled: bool
    interval: str
    product: str
    #: What executes here and on whose say-so — straight from the canonical binding.
    strategy_key: str | None
    strategy_version: str | None
    source: str | None
    authority: str | None
    origin: str | None
    reason: str | None
    binding_error: str | None
    #: The immutable artefact, when a graph is authoritative here.
    graph: dict[str, Any] | None
    #: The non-authoritative observer, if one is attached.
    shadow: dict[str, Any] | None
    execution_mode: str
    position: dict[str, Any] | None
    entry: dict[str, Any]
    lifecycle_actions: tuple[str, ...]

    def to_dict(self) -> dict:
        return {**asdict(self), "lifecycle_actions": list(self.lifecycle_actions)}


@dataclass(frozen=True)
class CockpitView:
    execution_mode: str
    book: str
    armed: bool
    running: bool
    provider: str
    kill_available: bool
    deployable_cash: float | None
    paper_pnl: dict[str, Any]
    health: dict[str, Any]
    problems: dict[str, list[str]]
    foreign_book: dict[str, Any]
    instruments: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── the standing entry gates, collected from their owners ────────────────────────

def entry_eligibility(runner, key: str, *, held: bool, now) -> EntryEligibility:
    """Collect the standing gates for one instrument.

    Each call below is the *engine's own* predicate or state, not a copy of it:
    `runner.armed` is the arm flag the entry pass reads, `_entries_halted` is the
    daily-loss breaker it computes once per tick, `_gap_guard_active` is the gap guard, and
    `slots_available` is `risk_controls`' pure predicate. If one of these changes meaning,
    it changes here too, because there is nothing here to change independently.
    """
    from app.engine.risk_controls import slots_available

    blocked: list[str] = []
    if not runner.armed:
        blocked.append(GATE_DISARMED)
    if key not in runner.enabled:
        blocked.append(GATE_NOT_ENABLED)
    if key in runner.entry_blocks:
        blocked.append(GATE_ENTRIES_BLOCKED)
    if held:
        blocked.append(GATE_ALREADY_HELD)
    try:
        if runner._entries_halted(now):
            blocked.append(GATE_DAILY_LOSS_HALT)
    except Exception:                      # a read model may never break the cockpit
        pass
    try:
        if runner._gap_guard_active(now):
            blocked.append(GATE_GAP_GUARD)
    except Exception:
        pass
    try:
        open_count = len(runner.broker.open_positions())
        free = slots_available(open_count, runner.params.get("max_open_positions", 0))
        if free is not None and free <= 0:
            blocked.append(GATE_NO_SLOTS)
    except Exception:
        pass
    return EntryEligibility(allowed=not blocked, blocked_by=tuple(blocked))


# ── per-instrument assembly ──────────────────────────────────────────────────────

def _binding_view(runner, key: str) -> dict[str, Any]:
    """The canonical binding, or the refusal that replaced it.

    `bind` is the one decision; `strategy_for_execution` is the one gate. Both are called
    here exactly as the engine calls them, so a cockpit that says "authorised" is reporting
    the same verdict the scan would get.
    """
    try:
        binding = runner._binding_for(key)
    except Exception as exc:
        return {"strategy_key": None, "strategy_version": None, "source": None,
                "authority": None, "origin": None, "reason": None,
                "binding_error": f"{type(exc).__name__}: {exc}"}
    error = None
    try:
        execution_binding.strategy_for_execution(binding)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    return {"strategy_key": binding.strategy_key,
            "strategy_version": binding.strategy_version,
            "source": binding.source, "authority": binding.authority,
            "origin": binding.origin, "reason": binding.reason,
            "binding_error": error}


def _graph_view(runner, key: str) -> dict[str, Any] | None:
    """The immutable artefact and its admission facts, from the deployment row only."""
    binding = runner.paper_authority.get(key)
    if binding is None:
        return None
    return {
        "graph_identifier": binding.graph_identifier,
        "graph_version": binding.graph_version,
        "content_address": binding.content_address,
        "project_id": binding.project_id,
        "deployment_row_id": binding.deployment_row_id,
        "execution_mode": binding.execution_mode,
        "authority": binding.authority,
        # ADR 0013: admission facts, recorded at activation and held by the execution
        # plane. Pointers into research, never a research read.
        "admission": {
            "evidence_run_id": binding.evidence_run_id,
            "evidence_candidate_id": binding.evidence_candidate_id,
            "evidence_content_address": binding.evidence_content_address,
            "model": "admission-prerequisite",
        },
    }


def _shadow_view(runner, key: str) -> dict[str, Any] | None:
    found = getattr(runner, "shadow_deployments", {}).get(key)
    if found is None:
        return None
    return {"graph_identifier": found.graph_identifier,
            "graph_version": found.graph_version,
            "content_address": found.content_address,
            "deployment_row_id": found.deployment_row_id,
            "authority": execution_binding.SHADOW,
            "execution_mode": found.execution_mode}


def _lifecycle_actions(runner, key: str) -> tuple[str, ...]:
    """Which lifecycle transitions the *existing* services would accept right now.

    Derived from `paper_authority.STATES`, not invented: the cockpit offers what the domain
    already implements and nothing else. No new control operation exists for the UI's
    convenience.
    """
    binding = runner.paper_authority.get(key)
    if binding is None:
        return ()
    return ("pause", "retire")          # an active binding; resume applies once paused


def instrument_view(runner, key: str, *, positions: dict, now) -> InstrumentExecutionView:
    held = positions.get(key)
    binding = _binding_view(runner, key)
    return InstrumentExecutionView(
        instrument_key=key,
        enabled=key in runner.enabled,
        interval=runner._interval_for(key),
        product=runner.products.get(key, "options"),
        graph=_graph_view(runner, key),
        shadow=_shadow_view(runner, key),
        execution_mode=execution_book.configured_execution_mode(),
        position=held.to_dict() if held is not None else None,
        entry=entry_eligibility(runner, key, held=held is not None, now=now).to_dict(),
        lifecycle_actions=_lifecycle_actions(runner, key),
        **binding)


# ── the whole view ───────────────────────────────────────────────────────────────

def view(runner, session) -> CockpitView:
    """Assemble the operational read model. Never raises for a per-instrument problem."""
    from app.engine import analytics

    now = runner.provider.now()
    book = runner.book
    positions = {p.instrument_key: p for p in runner.broker.open_positions()}

    keys = sorted(set(runner.enabled) | set(runner.paper_authority)
                  | set(getattr(runner, "shadow_deployments", {})) | set(positions))
    instruments = [instrument_view(runner, key, positions=positions, now=now).to_dict()
                   for key in keys]

    try:
        capital = analytics.capital_dict(session, book=book)
    except Exception as exc:
        capital = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        foreign = [p.instrument_key
                   for p in execution_book.foreign_book_positions(session, book)]
    except Exception:
        foreign = []

    return CockpitView(
        execution_mode=execution_book.configured_execution_mode(),
        book=book,
        armed=runner.armed,
        running=runner.running,
        provider=runner.provider.name,
        kill_available=True,
        deployable_cash=_safe_cash(runner),
        paper_pnl=capital,
        health=_health(runner),
        problems={
            "paper_authority": list(getattr(runner, "paper_authority_problems", [])),
            "shadow_deployments": list(getattr(runner, "shadow_deployment_problems", [])),
        },
        foreign_book={
            "other_book": LIVE if book == PAPER else PAPER,
            "open_instruments": foreign,
            "note": ("positions in the other book are managed by nobody in this process "
                     "(L1.3B)") if foreign else "",
        },
        instruments=instruments,
    )


def _safe_cash(runner) -> float | None:
    try:
        return float(runner.deployable_cash())
    except Exception:
        return None


def _health(runner) -> dict[str, Any]:
    """Liveness inputs only, plus a pointer to the authority.

    Deliberately **not** a readiness verdict. `/api/health` owns that: it assembles the
    database probe, uptime, provider auth state and feed anomalies and hands them to
    `readiness.evaluate`, which decides 200 vs 503. Recomputing that here would be a second
    health model whose disagreement with the probe would be the worst possible bug in an
    operational surface. So this reports the same raw lane ages the probe consumes and says
    where the verdict lives.
    """
    out: dict[str, Any] = {"verdict_owned_by": "GET /api/health"}
    for name, read in (("lane_ages", runner.lane_ages),
                       ("markets_open", runner.markets_open)):
        try:
            out[name] = read()
        except Exception as exc:
            out[name] = None
            out[f"{name}_error"] = f"{type(exc).__name__}: {exc}"
    try:
        out["provider"] = runner.health.as_dict()
    except Exception:
        out["provider"] = {}
    return out


def paper_deployments(session) -> list[dict]:
    """Every paper-authority deployment record, including its lifecycle state.

    Straight through to the domain service's own listing — the cockpit does not maintain a
    second view of deployment state.
    """
    return paper_authority.listing(session, include_retired=True)


__all__ = ["BOOK_LEVEL_GATES", "CockpitView", "EntryEligibility",
           "InstrumentExecutionView", "entry_eligibility", "instrument_view",
           "paper_deployments", "view"]
