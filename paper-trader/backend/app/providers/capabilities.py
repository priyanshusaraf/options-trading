"""What a provider connection can actually do, declared rather than inferred from its name.

Ten sites in shared engine, backtest and analytics code currently branch on the provider's
literal name string — `provider.name == "kite"` or `== "mock"`. That works while there is
exactly one real broker and stops working the moment there is a second one, silently and in the
worst direction:

  * `broker_factory.py` would never construct a live broker for a non-Kite provider, so live
    execution would quietly not happen;
  * `runner.py`'s `is_live` gate would read no funds, and sizing fails closed to zero;
  * `analytics.py` would report no account equity;
  * `universe.py` would refuse to build a real instrument universe.

None of those would raise. Each would take the safe-looking branch and be wrong.

A capability is the question those sites are really asking. `name == "kite"` at
`analytics.py:100` means "can this connection tell me the account's equity" — which is a
property of the connection, not of its brand.

## Roles, not one interface

Strategy OS keeps these distinct on purpose, because one user may hold several connections and
use them for different jobs — market data from one broker, execution at another:

  * **market data** — quotes, candles, option chains, depth, streaming
  * **account / portfolio** — funds, positions, equity, margin quotes
  * **execution** — order placement and lifecycle (`Broker` / `ExecutionVenue`, a separate seam)
  * **instrument resolution** — provider symbol/token ↔ canonical Strategy OS instrument

The capability set is how a connection says which of those roles it can serve. Declaring a
capability is a promise the conformance suite will hold the adapter to; the default is to
declare nothing.

## Declared-but-unbuilt capabilities

Some names below have no consumer yet (`STREAMING`, `DEPTH`, `POSTBACKS`, `GTT`, `SLICING`).
They are listed so the vocabulary is fixed before adapters start inventing their own words, and
so a deployment can eventually validate its required capabilities before activation. **Declaring
one you do not implement is a defect** — `test_provider_capabilities.py` checks the declaration
against the methods that actually exist.
"""
from __future__ import annotations

from typing import Final

# ── market data ──────────────────────────────────────────────────────────────
HISTORICAL_DATA: Final = "historical_data"      # get_candles over a real history window
LIVE_QUOTES: Final = "live_quotes"              # get_ltp / get_live_price
OPTION_CHAIN: Final = "option_chain"            # get_option_chain / option_ltp
FUTURES_QUOTES: Final = "futures_quotes"        # get_futures_ltp for a dated contract
STREAMING: Final = "streaming"                  # push feed rather than poll — not built
DEPTH: Final = "depth"                          # L2 order book — not built

# ── account / portfolio ──────────────────────────────────────────────────────
ACCOUNT_FUNDS: Final = "account_funds"          # account_funds()
ACCOUNT_POSITIONS: Final = "account_positions"  # account_positions()
ACCOUNT_EQUITY: Final = "account_equity"        # account_equity()
ORDER_MARGIN: Final = "order_margin"            # order_margin() — a real broker margin quote

# ── execution ────────────────────────────────────────────────────────────────
# Held here so the vocabulary is one vocabulary. The execution seam itself is
# `app/engine/broker_protocol.py`; a provider declaring LIVE_EXECUTION is stating that a live
# order client can be built from this connection, not that it places orders itself.
LIVE_EXECUTION: Final = "live_execution"
MARKET_ORDERS: Final = "market_orders"
LIMIT_ORDERS: Final = "limit_orders"
STOP_ORDERS: Final = "stop_orders"
GTT: Final = "gtt"                              # standing trigger orders — not built
SLICING: Final = "slicing"                      # broker-side order slicing — not built
POSTBACKS: Final = "postbacks"                  # push order updates — not built

# ── instrument identity ──────────────────────────────────────────────────────
INSTRUMENT_UNIVERSE: Final = "instrument_universe"   # can enumerate tradable instruments

# ── determinism ──────────────────────────────────────────────────────────────
# Not a broker feature: a property of simulated providers whose clock is advanceable and whose
# series is reproducible. The `name == "mock"` branches are really asking this.
SIMULATED_CLOCK: Final = "simulated_clock"

ALL: Final[frozenset[str]] = frozenset({
    HISTORICAL_DATA, LIVE_QUOTES, OPTION_CHAIN, FUTURES_QUOTES, STREAMING, DEPTH,
    ACCOUNT_FUNDS, ACCOUNT_POSITIONS, ACCOUNT_EQUITY, ORDER_MARGIN,
    LIVE_EXECUTION, MARKET_ORDERS, LIMIT_ORDERS, STOP_ORDERS, GTT, SLICING, POSTBACKS,
    INSTRUMENT_UNIVERSE, SIMULATED_CLOCK,
})

# Which concrete method backs each capability. Used by the conformance test to refuse a
# declaration whose method is missing or is still the base class's no-op default. Capabilities
# with no method yet map to None and are declaration-only until a consumer exists.
BACKING_METHOD: Final[dict[str, str | None]] = {
    HISTORICAL_DATA: "get_candles",
    LIVE_QUOTES: "get_ltp",
    OPTION_CHAIN: "get_option_chain",
    FUTURES_QUOTES: "get_futures_ltp",
    STREAMING: None,
    DEPTH: None,
    ACCOUNT_FUNDS: "account_funds",
    ACCOUNT_POSITIONS: "account_positions",
    ACCOUNT_EQUITY: "account_equity",
    ORDER_MARGIN: "order_margin",
    LIVE_EXECUTION: None,
    MARKET_ORDERS: None,
    LIMIT_ORDERS: None,
    STOP_ORDERS: None,
    GTT: None,
    SLICING: None,
    POSTBACKS: None,
    INSTRUMENT_UNIVERSE: None,
    SIMULATED_CLOCK: "advance",
}


class UnknownCapability(ValueError):
    """A provider declared a capability outside the vocabulary.

    Fail loudly rather than silently ignoring it: a typo'd capability that is quietly dropped
    reads at every call site as "this connection cannot do that", which is the same wrong-and-
    quiet failure the name-string branching produced.
    """


def validate(declared: frozenset[str]) -> frozenset[str]:
    unknown = set(declared) - ALL
    if unknown:
        raise UnknownCapability(
            f"unknown provider capabilities {sorted(unknown)}; "
            f"add them to app/providers/capabilities.py rather than inventing a name"
        )
    return frozenset(declared)


def provider_supports(provider: object, capability: str) -> bool:
    """Does this connection declare `capability`?

    Defensive by design. Several call sites reach this through `getattr(provider, "name", "")`
    because they may be handed a duck-typed stub rather than a `MarketDataProvider` — a test
    double, or a partially constructed provider during startup. Preserving that tolerance keeps
    the migration from the name comparisons behaviour-identical: an object that cannot answer
    is treated as not capable, which is the same fail-closed answer `name == "kite"` gave it.

    The declaration is checked FIRST, deliberately. Reading `CAPABILITIES` works for an
    instance and for a class; calling `supports()` works only for an instance, because it is an
    unbound function on a class and the capability argument would silently bind to `self`. An
    earlier version called first and swallowed the resulting failure into `False`, which is the
    exact silent-wrong-branch behaviour this module exists to remove.
    """
    declared = getattr(provider, "CAPABILITIES", None)
    if declared is not None:
        return capability in declared
    supports = getattr(provider, "supports", None)
    if callable(supports):
        try:
            return bool(supports(capability))
        except Exception:            # noqa: BLE001 — an unanswerable provider is not capable
            return False
    return False
