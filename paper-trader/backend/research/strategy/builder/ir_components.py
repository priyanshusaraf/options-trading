"""
The block library, as Component IR components.

Derivation is mechanical: identifier from the block name, parameters from
`BlockSpec.params` with defaults from `sample_args`, warmup from
`BlockSpec.warmup`, one boolean output. `research/` imports `app.ir`, never the
reverse.
"""
from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from app.ir.authoring import AuthoredComponent, component, parameter, socket, wire
from research.strategy.builder.blocks import BLOCKS, BlockSpec

BAR_INPUTS = ("open", "high", "low", "close", "volume")

DOMAIN = {"instrument": "*", "timeframe": "*"}


def _bar_domain(instrument: str, timeframe: str) -> dict[str, str]:
    return {"instrument": instrument, "timeframe": timeframe}


def _adapter(spec: BlockSpec, order: tuple[str, ...]):
    """One kernel for every block: rebuild the frame, call the block, name the output.

    `order` is captured, not read from `params`, so the positional call into
    `BlockSpec.fn` does not depend on dict ordering.
    """

    def kernel(params, inputs):
        frame = pd.DataFrame({name: inputs[name] for name in BAR_INPUTS})
        return {"out": spec.fn(frame, *(params[name] for name in order))}

    return kernel


def derive(name: str, spec: BlockSpec, *, instrument: str = "*",
           timeframe: str = "*") -> AuthoredComponent:
    """One block → one component."""
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
        # C10
        warmup=lambda p, order=order, spec=spec: int(
            spec.warmup(tuple(p[param_name] for param_name in order))),
        # The adapter body is identical for every block; without this, all
        # blocks would share one body address and collide in the registry.
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
    """Block name → its family. Metadata *about* components, never a field on
    them — C13."""
    out: dict[str, list[str]] = {}
    for name, spec in BLOCKS.items():
        out.setdefault(spec.group, []).append(name)
    return {group: tuple(sorted(names)) for group, names in sorted(out.items())}
