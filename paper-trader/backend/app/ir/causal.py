"""Closed causal declarations for Component IR kernel implementations.

These values describe implementation facts and therefore live beside the
kernel registry, not in serialized Component IR v1 artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass
import inspect
import math
from typing import Any, Callable, Literal, Mapping, TypeAlias

JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]

ALLOWED_CONTEXT_INPUTS = frozenset({"bar_timestamp"})
HISTORY_MODES = frozenset({"bounded", "causal_recursive"})
MAX_HISTORY_BARS = 1_000_000


class CausalDeclarationError(ValueError):
    """A causal declaration is incomplete, open, or internally inconsistent."""


@dataclass(frozen=True)
class BoundTerm:
    parameter: str
    multiplier: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.parameter, str) or not self.parameter:
            raise CausalDeclarationError("history parameter must be a non-empty string")
        if isinstance(self.multiplier, bool) or not isinstance(self.multiplier, int):
            raise CausalDeclarationError("history multipliers must be integers")


@dataclass(frozen=True)
class HistoryBound:
    mode: Literal["bounded", "causal_recursive"]
    constant: int = 0
    terms: tuple[BoundTerm, ...] = ()

    def __post_init__(self) -> None:
        if self.mode not in HISTORY_MODES:
            raise CausalDeclarationError("history declaration is invalid")
        if isinstance(self.constant, bool) or not isinstance(self.constant, int) \
                or self.constant < 0:
            raise CausalDeclarationError("history declaration is invalid")
        if not isinstance(self.terms, tuple) or not all(
                isinstance(term, BoundTerm) for term in self.terms):
            raise CausalDeclarationError("history terms must be BoundTerm values")
        parameters = tuple(term.parameter for term in self.terms)
        if len(set(parameters)) != len(parameters):
            raise CausalDeclarationError("history parameters must be unique")

    def bars(self, params: Mapping[str, Any]) -> int:
        total = self.constant
        for term in self.terms:
            if term.parameter not in params:
                raise CausalDeclarationError(
                    f"history parameter {term.parameter!r} is undeclared")
            value = params[term.parameter]
            if isinstance(value, bool):
                raise CausalDeclarationError("history parameters must be integers")
            try:
                integral = int(value)
            except (TypeError, ValueError, OverflowError) as exc:
                raise CausalDeclarationError(
                    "history parameters must be integers") from exc
            if integral != value:
                raise CausalDeclarationError("history parameters must be integers")
            total += integral * term.multiplier
        if total < 0 or total > MAX_HISTORY_BARS:
            raise CausalDeclarationError("evaluated history is outside the closed range")
        return total


Initializer = Callable[[Mapping[str, JSONValue]], object]
StateEncoder = Callable[[object], JSONValue]
StateUpdate = Callable[
    [object, Mapping[str, JSONValue], Mapping[str, JSONScalar],
     Mapping[str, JSONScalar]], object
]
StateStep = Callable[
    [object, Mapping[str, JSONValue], Mapping[str, JSONScalar],
     Mapping[str, JSONScalar]], Mapping[str, JSONScalar]
]


@dataclass(frozen=True)
class RecursiveStateContract:
    initializer: Initializer
    state_type: type
    state_encoder: StateEncoder
    update: StateUpdate
    step: StateStep

    def __post_init__(self) -> None:
        values = (self.initializer, self.state_encoder, self.update, self.step)
        if not isinstance(self.state_type, type) or not all(callable(value) for value in values):
            raise CausalDeclarationError(
                "recursive_state requires initializer, state type/encoder, update, and step")
        expected = ((self.initializer, 1), (self.state_encoder, 1),
                    (self.update, 4), (self.step, 4))
        if any(len(inspect.signature(function).parameters) != arity
               for function, arity in expected):
            raise CausalDeclarationError(
                "recursive_state functions have invalid signatures")

    def initialize(self, params: Mapping[str, JSONValue]) -> object:
        return self._state(self.initializer(params))

    def advance(self, state: object, params: Mapping[str, JSONValue],
                node_inputs: Mapping[str, JSONScalar],
                context_inputs: Mapping[str, JSONScalar]) -> object:
        self._state(state)
        return self._state(self.update(state, params, node_inputs, context_inputs))

    def encode(self, state: object) -> JSONValue:
        self._state(state)
        encoded = self.state_encoder(state)
        if not _is_closed_json(encoded):
            raise CausalDeclarationError("state_encoder must produce closed JSON data")
        return encoded

    def output(self, state: object, params: Mapping[str, JSONValue],
               node_inputs: Mapping[str, JSONScalar],
               context_inputs: Mapping[str, JSONScalar]) -> Mapping[str, JSONScalar]:
        self._state(state)
        outputs = self.step(state, params, node_inputs, context_inputs)
        if not isinstance(outputs, Mapping) or not _is_closed_json(dict(outputs)):
            raise CausalDeclarationError("recursive step must produce closed JSON outputs")
        return outputs

    def _state(self, state: object) -> object:
        if type(state) is not self.state_type:
            raise CausalDeclarationError("recursive function must return exact state_type")
        return state


def _is_closed_json(value: object) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if value is None or isinstance(value, (str, int, bool)):
        return True
    if isinstance(value, list):
        return all(_is_closed_json(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_closed_json(item)
                   for key, item in value.items())
    return False


@dataclass(frozen=True)
class CausalContract:
    node_input_sockets: tuple[str, ...]
    context_inputs: tuple[Literal["bar_timestamp"], ...] = ()
    history: HistoryBound = HistoryBound("bounded")
    output_delay_bars: int = 0
    input_bar: Literal["completed"] = "completed"
    purity: Literal["pure"] = "pure"
    recursive_state: RecursiveStateContract | None = None

    def __post_init__(self) -> None:
        _validate_contract_values(
            self.node_input_sockets,
            self.context_inputs,
            self.history,
            self.output_delay_bars,
            self.recursive_state,
            self.input_bar,
            self.purity,
        )


def _validate_contract_values(node_input_sockets: tuple[str, ...],
                              context_inputs: tuple[str, ...],
                              history: HistoryBound,
                              output_delay_bars: int,
                              recursive_state: RecursiveStateContract | None,
                              input_bar: str,
                              purity: str) -> None:
    if not isinstance(node_input_sockets, tuple) or any(
            not isinstance(socket, str) or not socket for socket in node_input_sockets):
        raise CausalDeclarationError("node_input_sockets must be non-empty strings")
    if len(set(node_input_sockets)) != len(node_input_sockets):
        raise CausalDeclarationError("node_input_sockets must be unique")
    if not isinstance(context_inputs, tuple) or set(context_inputs) - ALLOWED_CONTEXT_INPUTS:
        raise CausalDeclarationError(
            f"context_inputs must be drawn from {sorted(ALLOWED_CONTEXT_INPUTS)}")
    if len(set(context_inputs)) != len(context_inputs):
        raise CausalDeclarationError("context_inputs must be unique")
    if not isinstance(history, HistoryBound):
        raise CausalDeclarationError("history must be a closed HistoryBound")
    if isinstance(output_delay_bars, bool) or not isinstance(output_delay_bars, int) \
            or output_delay_bars < 0:
        raise CausalDeclarationError("output_delay_bars must be a non-negative integer")
    if history.mode == "bounded" and recursive_state is not None:
        raise CausalDeclarationError("bounded history cannot declare recursive_state")
    if history.mode == "causal_recursive" and recursive_state is None:
        raise CausalDeclarationError(
            "causal_recursive history requires a complete recursive_state contract")
    if input_bar != "completed":
        raise CausalDeclarationError("input_bar must be 'completed'")
    if purity != "pure":
        raise CausalDeclarationError("purity must be 'pure'")


def causal_contract(*, node_input_sockets: tuple[str, ...],
                    history: HistoryBound,
                    context_inputs: tuple[str, ...] = (),
                    output_delay_bars: int = 0,
                    recursive_state: RecursiveStateContract | None = None
                    ) -> CausalContract:
    """Construct a closed contract; no dependency kind has an open fallback."""
    return CausalContract(
        node_input_sockets=node_input_sockets,
        context_inputs=context_inputs,
        history=history,
        output_delay_bars=output_delay_bars,
        recursive_state=recursive_state,
    )


@dataclass(frozen=True)
class BlockCausalDisposition:
    status: Literal["admitted", "quarantined"]
    contract: CausalContract | None
    quarantine_reason: str | None
    dependencies: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        admitted = self.status == "admitted"
        quarantined = self.status == "quarantined"
        if admitted and isinstance(self.contract, CausalContract) \
                and self.quarantine_reason is None \
                and isinstance(self.dependencies, tuple):
            return
        if quarantined and self.contract is None \
                and isinstance(self.quarantine_reason, str) \
                and bool(self.quarantine_reason.strip()) and not self.dependencies:
            return
        raise CausalDeclarationError("block causal disposition is invalid")

    @classmethod
    def admitted(cls, contract: CausalContract,
                 dependencies: tuple[object, ...] = ()) -> "BlockCausalDisposition":
        return cls("admitted", contract, None, dependencies)

    @classmethod
    def quarantined(cls, reason: str) -> "BlockCausalDisposition":
        return cls("quarantined", None, reason, ())
