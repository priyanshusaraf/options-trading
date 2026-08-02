"""Strategy registry — the single place the platform resolves a strategy by key.

Every module dropped in this package that exposes a module-level `STRATEGY`
(a `Strategy` instance) is auto-discovered and registered under its `.key`. To add
a strategy you commit one file here (the owner's "put the python code in from our
end"); no UI builder, no runtime exec of pasted code.

There are TWO resolution functions, and picking the wrong one is a real-money bug.

* `resolve_strategy(key)` — **FAIL-CLOSED**. An unknown key raises `StrategyNotFound`.
  This is the correct call for anything bound to a deployment, a customer, or an
  attribution record.
* `get_strategy(key)` — **fail-safe**: unknown/None falls back to the default strategy.
  This exists for the legacy per-instrument path only (see the allow-list below).

Why the split (audit finding C4): falling back is the right posture for one owner
running one strategy he wrote — a stale per-instrument assignment must not crash a tick.
It inverts under a marketplace. A strategy that fails to load, or was renamed, or was
withdrawn by its author, does not stop under a fallback: it trades the platform's
DEFAULT strategy with the customer's real capital, while the trade rows claim it was
the customer's strategy. Silent substitution of the executing logic is the class of
defect that ends in a regulatory conversation, so anything that is not the legacy path
must fail closed.

**Callers allowed to use `get_strategy` (fail-safe):**
  - `engine/runner.py` — per-instrument `strategy_keys` map; a stale key must not stall
    the risk loop (invariant 2: never block an exit).
  - `backtest/{engine,premium,sweep}.py` and `api/routes.py` chart payloads, when called
    with `None`/`DEFAULT_STRATEGY_KEY` — that is the explicit "give me the default" idiom
    and is not a substitution at all.
  - `research/evaluation/kernels.py` re-export, used by research against known keys.

**Everything else must use `resolve_strategy`:** deployment binding, promotions,
generated/marketplace strategies, anything that writes a `strategy_key` onto a money
record. When in doubt, fail closed — a halted deployment is recoverable, a
misattributed fill is not.

Identity: every strategy carries a content-addressed `version` (`app/strategy/identity.py`),
so `(key, version)` — not `key` — is the execution artifact.
"""
from __future__ import annotations

import importlib
import pkgutil

from app.core.logging import log

from .base import CANONICAL_COLUMNS, Strategy

DEFAULT_STRATEGY_KEY = "trend_impulse_v3"

_REGISTRY: dict[str, Strategy] = {}
_SKIP = {"base"}


class StrategyNotFound(LookupError):
    """Raised by `resolve_strategy` for a key the registry cannot resolve.

    A `LookupError` subclass so an existing `except KeyError/LookupError` around a
    lookup still catches it, but it is deliberately its own type: a caller that means
    "halt this deployment" must be able to distinguish an unresolvable strategy from
    any other missing-key error in the same block.
    """

    def __init__(self, key: str | None, available: list[str] | None = None) -> None:
        self.key = key
        self.available = available or []
        super().__init__(
            f"strategy {key!r} is not registered; refusing to substitute a different "
            f"strategy. Registered: {', '.join(self.available) or '(none)'}")


def _discover() -> None:
    if _REGISTRY:
        return
    import app.strategy.registry as pkg
    for mod in pkgutil.iter_modules(pkg.__path__):
        if mod.name in _SKIP:
            continue
        m = importlib.import_module(f"{pkg.__name__}.{mod.name}")
        strat = getattr(m, "STRATEGY", None)
        if isinstance(strat, Strategy) and strat.key:
            _REGISTRY[strat.key] = strat


def register(strat: Strategy) -> None:
    """Register (or replace) a strategy at runtime — the seam for deployed generated
    strategies, which are reconstructed from the DB at engine startup rather than
    dropped in as a module. Committing a module with a `STRATEGY` remains the path for
    hand-written strategies; this never runs pasted code (the generated strategy was
    already emitted, AST-validated, and sandbox-loaded by the builder)."""
    _discover()
    if isinstance(strat, Strategy) and strat.key:
        _REGISTRY[strat.key] = strat


def all_strategies() -> list[Strategy]:
    _discover()
    return sorted(_REGISTRY.values(), key=lambda s: s.display_name or s.key)


def strategy_keys() -> list[str]:
    _discover()
    return [s.key for s in all_strategies()]


def resolve_strategy(key: str | None, *, allow_fallback: bool = False) -> Strategy:
    """FAIL-CLOSED resolution. Raises `StrategyNotFound` for an unknown key.

    `allow_fallback=True` reproduces the legacy fail-safe behaviour exactly (unknown or
    None → the default strategy) and is what `get_strategy` calls; it is spelled as an
    explicit keyword so a substitution is always a decision somebody typed, never a
    default that happened to a caller who did not think about it.

    `None` with `allow_fallback=False` also raises: "no strategy specified" is not a
    resolvable identity, and a deployment-bound caller silently getting the platform
    default is precisely the failure this function exists to prevent.
    """
    _discover()
    if key and key in _REGISTRY:
        return _REGISTRY[key]
    if not allow_fallback:
        raise StrategyNotFound(key, sorted(_REGISTRY))
    if key:
        # A key was ASKED FOR and is being ignored. Loud, because the engine will now
        # trade different logic than the caller named, and the trade row will carry the
        # substituted strategy while some upstream config still says otherwise.
        # Rate-limited by key: the runner resolves per instrument on a ~2.5s loop, and
        # the 2026-07-15 autopsy showed unthrottled per-tick errors bury the journal.
        # `error_ratelimited` re-surfaces after the window, so this is never silenced.
        log.error_ratelimited(
            f"strategy {key!r} is NOT registered — falling back to "
            f"{DEFAULT_STRATEGY_KEY!r}. The traded logic is not the configured logic.",
            key=str(key), event="strategy_fallback", window_seconds=300.0)
    # key is None here → the explicit "give me the default" idiom, not a substitution.
    return _REGISTRY[DEFAULT_STRATEGY_KEY]


def get_strategy(key: str | None) -> Strategy:
    """Legacy fail-safe resolution: unknown/None → the default strategy.

    Behaviour is unchanged (an unknown key still returns the default) except that a
    substitution now logs an error. Only the callers listed in the module docstring may
    use this; everything deployment- or attribution-bound must use `resolve_strategy`.
    """
    return resolve_strategy(key, allow_fallback=True)


def strategy_meta() -> list[dict]:
    """Lightweight list for the UI: key, version, label, default params.

    `version` is the content hash — `(key, version)` is the execution artifact, so a
    surface that shows a key without a version cannot tell two builds of the same key
    apart.

    `spec` is the compiled StrategySpec (Phase E) — the typed parameter schema plus
    the declared entry/exit/sizing policies. It is ADDED alongside `default_params`,
    never in place of it: the existing consumers read `default_params` and must keep
    working. It is here because it is what a visual builder or a code editor needs
    to render a parameter without guessing its units, and because a contract with no
    consumer is a contract nobody maintains.
    """
    from app.strategy.spec import compile_spec
    out = []
    for s in all_strategies():
        entry = {"key": s.key, "version": s.version, "display_name": s.display_name,
                 "default_params": dict(s.default_params)}
        try:
            entry["spec"] = compile_spec(s).to_dict()
        except Exception as e:      # a spec is descriptive; never fail a listing over it
            entry["spec"] = None
            entry["spec_error"] = str(e)
        out.append(entry)
    return out


__all__ = ["Strategy", "CANONICAL_COLUMNS", "DEFAULT_STRATEGY_KEY", "StrategyNotFound",
           "register", "all_strategies", "strategy_keys", "get_strategy",
           "resolve_strategy", "strategy_meta"]
