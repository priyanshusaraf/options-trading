"""StrategySpec — the single execution contract every strategy compiles into.

The problem this solves
-----------------------
`Strategy` (registry/base.py) says a strategy is a function from candles to four
boolean columns, and its own docstring is explicit that risk is not its job. That
was right for one hand-written strategy. It is wrong for four *sources* of strategy
— built-in, generated, visual, Python, marketplace — because it leaves a strategy
unable to say anything about:

  * **its parameters** — and the engine proves the point. `scan_signals` passes
    ema_length/z_length/entry_z/slope_lookback from global Settings *only* when the
    strategy is the default one, and calls `strat.signals(frame)` with NO parameters
    at all for every other strategy (runner.py). A marketplace strategy therefore
    cannot be tuned, and two deployments of the same strategy cannot differ.
  * **its exits** — all trade management lives in the runner, keyed by segment.
  * **its sizing** — `_intraday_margin_sizer` / `_futures_margin_sizer` are runner
    methods.

Four strategy sources that all reduce to four booleans and then run one hard-coded
risk model are four skins on one strategy.

What this module is, and is not
-------------------------------
It is the *contract*: metadata, a typed parameter schema, signal generation, and
declared entry/exit/sizing policies, plus `compile_spec()` which turns any existing
`Strategy` into one. Every registered strategy compiles today — that is asserted by
test — and nothing about how they execute has changed.

It is NOT yet the thing the engine reads. Swapping the runner onto specs is a
behaviour-affecting change to real-money entry and exit paths and belongs in its own
phase with its own parity evidence. Compiling first, adopting second, is the same
order Phase G used for the decision kernel and for the same reason.

Reuse over reinvention
----------------------
`ExitPolicy` is the decision kernel's, not a second one. A spec that described exits
in its own vocabulary would need translating into the kernel's, and the translation
would be the thing that drifts. The parameter *bounds* likewise defer to
`runtime_config.BOUNDS` where a key is already a platform knob.
"""
from __future__ import annotations

import dataclasses
from typing import Any

from app.engine.decision_kernel import ExitPolicy

# Parameter kinds. Deliberately the same small, bounded vocabulary the research
# plane's block grammar already uses (`research/strategy/builder/grammar.py`):
# lengths, thresholds, percentages, multipliers, bounded choices, minute-of-day.
# A visual builder and a Python editor both need to render an editor for a
# parameter, and they can only do that from a KIND — "it's a float" is not enough
# to know whether 0.8 means 80% or 0.8 ATR.
LENGTH = "length"
THRESHOLD = "thr"
PERCENT = "pct"
MULTIPLIER = "mult"
CHOICE = "choice"
MINUTE = "minute"
BOOLEAN = "bool"
KINDS = (LENGTH, THRESHOLD, PERCENT, MULTIPLIER, CHOICE, MINUTE, BOOLEAN)


@dataclasses.dataclass(frozen=True)
class ParamSpec:
    """One tunable parameter: what it is called, what kind of thing it is, and what
    values are lawful. The bounds are part of the contract, not advice — a
    marketplace strategy's parameters are edited by someone who did not write it."""
    name: str
    kind: str
    default: Any
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple = ()
    label: str = ""

    def validate(self, value):
        """Coerce and bounds-check. Raises ValueError; callers decide whether that
        is fatal (a write path) or a fallback-to-default (a read path)."""
        if self.kind == BOOLEAN:
            return bool(value)
        if self.kind in (LENGTH, CHOICE, MINUTE):
            coerced = int(value)
        else:
            coerced = float(value)
        if self.minimum is not None and coerced < self.minimum:
            raise ValueError(f"{self.name}={coerced} below minimum {self.minimum}")
        if self.maximum is not None and coerced > self.maximum:
            raise ValueError(f"{self.name}={coerced} above maximum {self.maximum}")
        if self.choices and coerced not in self.choices:
            raise ValueError(f"{self.name}={coerced} not in {self.choices}")
        return coerced

    def to_dict(self) -> dict:
        return {"name": self.name, "kind": self.kind, "default": self.default,
                "minimum": self.minimum, "maximum": self.maximum,
                "choices": list(self.choices), "label": self.label or self.name}


# Sizing models the platform knows how to execute. A strategy DECLARES one; the
# engine still owns the arithmetic (real margin probes, dust floors, leftover-cash
# flow), because that is broker and account knowledge a strategy has no business
# holding. Declaring is what lets two strategies size differently at all.
ONE_LOT = "one_lot"                  # exactly one F&O lot — the backtest's model
MARGIN_TARGET = "margin_target"      # size to a target margin (equity_intraday live)
PLATFORM_DEFAULT = "platform_default"  # whatever the engine does today for this segment
SIZING_MODELS = (ONE_LOT, MARGIN_TARGET, PLATFORM_DEFAULT)


@dataclasses.dataclass(frozen=True)
class SizingPolicy:
    model: str = PLATFORM_DEFAULT
    target_margin: float | None = None

    def to_dict(self) -> dict:
        return {"model": self.model, "target_margin": self.target_margin}


@dataclasses.dataclass(frozen=True)
class EntryPolicy:
    """When this strategy is allowed to open, beyond its own signal.

    These are the platform's day-shape guards (entry window, stale-signal age cap,
    event blackouts, gap guard). They are listed here rather than assumed because a
    marketplace strategy must be able to say "I am an opening-range strategy, do not
    apply the 09:30 entry window to me" — and, more importantly, because the
    platform must be able to see that it said so.

    Defaults reproduce today's behaviour exactly: every guard on.
    """
    respect_entry_window: bool = True
    respect_event_blackouts: bool = True
    respect_gap_guard: bool = True
    max_signal_age_minutes: float | None = None   # None = platform default
    allow_reinforcement: bool = True

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class StrategyMetadata:
    key: str
    version: str
    display_name: str = ""
    source: str = "builtin"       # builtin | generated | visual | python | marketplace
    description: str = ""

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class StrategySpec:
    """Everything the platform needs to know to run a strategy.

    `signal_fn` is kept as a callable rather than serialised: signal generation is
    the one part that genuinely differs per source (compiled Python, a composition
    interpreted by the block library, a visual graph). The other four parts are
    data, which is what makes a spec transportable — a marketplace listing is its
    metadata + params + policies, and the signal artifact is fetched separately.
    """
    metadata: StrategyMetadata
    params: tuple
    signal_fn: Any
    entry: EntryPolicy = dataclasses.field(default_factory=EntryPolicy)
    exit: ExitPolicy = dataclasses.field(default_factory=ExitPolicy)
    sizing: SizingPolicy = dataclasses.field(default_factory=SizingPolicy)

    def param(self, name: str) -> ParamSpec | None:
        return next((p for p in self.params if p.name == name), None)

    def defaults(self) -> dict:
        return {p.name: p.default for p in self.params}

    def resolve_params(self, overrides: dict | None = None) -> dict:
        """Defaults merged with `overrides`, each validated against its ParamSpec.

        An invalid override falls back to the default rather than raising: this is
        the read path (the engine, mid-loop), and one bad parameter on one strategy
        must not stop the process managing open positions. The write path should
        call `ParamSpec.validate` directly and surface the error to whoever typed it.
        """
        out = self.defaults()
        for name, value in (overrides or {}).items():
            spec = self.param(name)
            if spec is None:
                continue
            try:
                out[name] = spec.validate(value)
            except (TypeError, ValueError):
                pass
        return out

    def to_dict(self) -> dict:
        return {"metadata": self.metadata.to_dict(),
                "params": [p.to_dict() for p in self.params],
                "entry": self.entry.to_dict(),
                "exit": dataclasses.asdict(self.exit),
                "sizing": self.sizing.to_dict(),
                "divergences": self.exit.divergences()}


# ── compilation: every existing strategy becomes a spec ──────────────────────

# Inferring a kind from a parameter NAME is a heuristic, and it is confined to this
# one table so that it is reviewable and so that a strategy can override it later by
# declaring `param_specs` directly. It exists because the built-in strategies predate
# the concept and describe their parameters only as `default_params` — a bare dict
# with no types, no bounds and no units.
_NAME_KINDS = {
    "ema_length": (LENGTH, 2, 400),
    "z_length": (LENGTH, 2, 400),
    "slope_lookback": (LENGTH, 1, 100),
    "atr_length": (LENGTH, 2, 400),
    "entry_z": (THRESHOLD, -10.0, 10.0),
    "exit_z": (THRESHOLD, -10.0, 10.0),
}


def _infer_param(name: str, default) -> ParamSpec:
    known = _NAME_KINDS.get(name)
    if known:
        kind, lo, hi = known
        return ParamSpec(name=name, kind=kind, default=default,
                         minimum=lo, maximum=hi)
    if isinstance(default, bool):
        return ParamSpec(name=name, kind=BOOLEAN, default=default)
    if isinstance(default, int):
        return ParamSpec(name=name, kind=LENGTH, default=default, minimum=1)
    # An unrecognised float is declared a MULTIPLIER with no bounds rather than a
    # PERCENT: guessing "this 0.5 means 50%" would put a wrong unit in front of
    # someone editing a risk parameter, and an unbounded multiplier is honest about
    # not knowing.
    return ParamSpec(name=name, kind=MULTIPLIER, default=default)


def compile_spec(strategy) -> StrategySpec:
    """Compile any `Strategy` into a StrategySpec. Backwards compatible by
    construction: policies default to exactly what the platform does today, so a
    compiled spec describes current behaviour rather than proposing new behaviour.

    A strategy MAY declare `param_specs`, `entry_policy`, `exit_policy` or
    `sizing_policy` to say something more precise; nothing does yet, and the
    absence of any of them is not an error — it means "the platform default", which
    is the true answer for every strategy written before this contract existed.
    """
    declared = getattr(strategy, "param_specs", None)
    if declared:
        params = tuple(declared)
    else:
        params = tuple(_infer_param(name, default)
                       for name, default in
                       sorted(getattr(strategy, "default_params", {}).items()))

    source = "generated" if str(getattr(strategy, "key", "")).startswith("gen_") \
        else "builtin"

    metadata = StrategyMetadata(
        key=strategy.key,
        version=strategy.version,
        display_name=getattr(strategy, "display_name", "") or strategy.key,
        source=source,
        description=(strategy.__doc__ or "").strip().split("\n")[0],
    )

    # A declared `risk_model` means the strategy manages its own exit via the ATR
    # ratchet; without one it exits on its canonical flags plus the platform's
    # protective band. Both are expressed in the kernel's vocabulary so a spec and a
    # live exit decision can never disagree about what a policy means.
    exit_policy = getattr(strategy, "exit_policy", None) or ExitPolicy(
        ratchet=getattr(strategy, "risk_model", None) is not None)

    return StrategySpec(
        metadata=metadata,
        params=params,
        signal_fn=strategy.signals,
        entry=getattr(strategy, "entry_policy", None) or EntryPolicy(),
        exit=exit_policy,
        sizing=getattr(strategy, "sizing_policy", None) or SizingPolicy(),
    )
