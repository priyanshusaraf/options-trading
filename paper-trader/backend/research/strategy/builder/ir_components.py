"""
The block library, as Component IR components.

This is the first step of Research Plane Generation 2, and the reason it comes
first: Generation 1 searches *parameters* over a fixed block grammar, and RFC
0001 C14 names why that ceiling exists — "vectorbt builds parameter grids into
the indicator contract itself, which silently defines *search = parameter
sweeping* for everything downstream, and the research plane inherited that
shape. **Structure search is not reachable from a design where components sweep
themselves.**" A generator cannot search over structure until the vocabulary is
composable, versioned and typed. That is what a component is.

**The derivation is mechanical, and Appendix A.3 predicted it would be.** "Each
block's `BlockSpec` already declares `(param_name, kind)` pairs drawn from the
same bounded vocabulary as F5 — `length`, `pct`, `mult`. The block registry is
therefore already most of a component interface; what it lacks is F2's version
and F4's declared panels." So nothing here invents anything: identifier from the
block's name, parameters from `BlockSpec.params` with defaults from
`sample_args`, warmup from `BlockSpec.warmup`, and a single boolean output —
which is itself a recorded defect of the current library (Appendix A.2: "every
public block returns `Series[bool]`… so a value like ATR cannot be named,
shared, or forked today").

**Direction of dependency.** `research/` imports `app.ir`, never the reverse.
The research plane's isolation rule is about *capital* — `research/guards.py`
forbids the execution modules — and the IR is a language, not an executor.

**What the interface check cannot verify here, said out loud.** One adapter
serves all twenty-three blocks, so it reaches `inputs` and `params` dynamically
and `authoring._check_satisfies_interface` cannot conclude anything about them.
It reports that as `unchecked` rather than passing silently, and
`test_ir_block_components.py` asserts it — the alternative, a check that quietly
approves whatever it cannot read, is the failure this codebase already hit once
with F7.
"""
from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from app.ir.authoring import AuthoredComponent, component, parameter, socket, wire
from research.strategy.builder.blocks import BLOCKS, BlockSpec

# Blocks consume bars, not a graph-shaped input, so every derived component
# declares the OHLCV frame the adapter rebuilds. Narrowing this per block —
# `zscore_gt` reads only `close` — is a real refinement and deliberately not
# done here: it would mean inferring each block's inputs from its body, which is
# what F4 forbids. It belongs in the blocks' own declarations.
BAR_INPUTS = ("open", "high", "low", "close", "volume")

DOMAIN = {"instrument": "*", "timeframe": "*"}


def _bar_domain(instrument: str, timeframe: str) -> dict[str, str]:
    return {"instrument": instrument, "timeframe": timeframe}


def _adapter(spec: BlockSpec, order: tuple[str, ...]):
    """One kernel for every block: rebuild the frame, call the block, name the output.

    `order` is captured rather than read from `params` so the positional call
    into `BlockSpec.fn` is a function of the declared interface, not of dict
    ordering — the same reason resolution sorts what it records (C5).
    """

    def kernel(params, inputs):
        frame = pd.DataFrame({name: inputs[name] for name in BAR_INPUTS})
        return {"out": spec.fn(frame, *(params[name] for name in order))}

    return kernel


def derive(name: str, spec: BlockSpec, *, instrument: str = "*",
           timeframe: str = "*") -> AuthoredComponent:
    """One block → one component. Nothing here is a judgement call."""
    order = tuple(param_name for param_name, _ in spec.params)
    defaults = dict(zip(order, spec.sample_args))
    bar = wire(instrument=instrument, timeframe=timeframe)

    return component(
        f"block.{name}",
        display_name=name.replace("_", " "),
        interface=[
            *(socket(field, "input", bar) for field in BAR_INPUTS),
            *(parameter(param_name, kind, defaults[param_name])
              for param_name, kind in spec.params),
            socket("out", "output",
                   wire("bool", instrument=instrument, timeframe=timeframe)),
        ],
        # C10 — the block's own warmup function, over the node's bound
        # parameters. `BlockSpec.warmup` already takes the argument tuple, so
        # this is a re-ordering and not a reimplementation.
        warmup=lambda p, order=order, spec=spec: int(
            spec.warmup(tuple(p[param_name] for param_name in order))),
        # One adapter serves all twenty-three blocks, so its *source* is
        # identical for every one of them. Without naming what it closes over,
        # all twenty-three would share a single body address — and a registry
        # keyed by address would silently keep whichever came last. The block's
        # own source is what actually distinguishes them.
        closes_over={"block": name, "fn": _block_source(spec)},
    )(_adapter(spec, order))


def _block_source(spec: BlockSpec) -> str:
    import inspect
    import textwrap

    return textwrap.dedent(inspect.getsource(spec.fn))


def derive_all(*, instrument: str = "*", timeframe: str = "*"
               ) -> dict[str, AuthoredComponent]:
    """The whole vocabulary, keyed by block name."""
    return {name: derive(name, spec, instrument=instrument, timeframe=timeframe)
            for name, spec in BLOCKS.items()}


def groups() -> Mapping[str, tuple[str, ...]]:
    """Block name → its family, carried through so a generator can still reason
    about `trend`/`momentum`/`volatility`/`confirmation` without the IR having
    to know what those mean. This is metadata *about* components, not a field
    on them — C13: nothing an executor sees may say where a component came from
    or what family it belongs to."""
    out: dict[str, list[str]] = {}
    for name, spec in BLOCKS.items():
        out.setdefault(spec.group, []).append(name)
    return {group: tuple(sorted(names)) for group, names in sorted(out.items())}
