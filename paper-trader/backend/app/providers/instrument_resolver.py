"""Who owns an instrument's identity, and who owns its symbology.

**Strategy OS owns economic instrument identity. A provider owns its own names for it.**

That distinction does not exist in the type system today, and the cost is concrete. The canonical
`Instrument` (`app/core/instruments.py`) carries fields that are, in fact, one broker's
symbology:

  * `spot_symbol` is a Kite tradingsymbol — `kite.py` matches the instruments dump on
    `row["tradingsymbol"] == inst.spot_symbol`;
  * `option_name` is documented as "the `name` used to find option contracts in the instruments
    dump", which is a Kite concept;
  * `lot_size` / `strike_step` are "re-resolved from the instruments dump each day";
  * `f"{inst.spot_exchange}:{inst.spot_symbol}"` is literally a Kite quote key.

So a second provider with different symbology has nowhere to put its mapping. It would either
reuse Kite's strings — resolving to the wrong contract, silently — or fork `Instrument`, which
breaks "one of anything". Both are worse than the seam below.

## What this module changes, and what it deliberately does not

It introduces the **seam**: a provider answers "what do *you* call this canonical instrument",
and shared code stops assuming the answer is spelled on the `Instrument`. `KiteProvider`
implements it over its existing lookup logic, so this ships with a real consumer rather than as
a mechanism wired to nothing — the defect this codebase is named for.

It does **not** yet move `spot_symbol` / `option_name` off `Instrument`. Those fields are Kite's
mapping data sitting in the canonical object, and relocating them is a schema and seed change on
the live symbol-resolution path. The seam has to exist first so there is somewhere for the
second provider's mapping to go; the relocation lands with adapter #2, when there is a second
mapping to hold and a way to prove the move preserved Kite's resolution exactly.

Until then the honest statement is: **`Instrument` still carries Kite's symbology, and
`KiteInstrumentResolver` is the only thing allowed to read those fields as symbology.** A second
resolver must supply its own mapping and must not read `spot_symbol` or `option_name`, which
`test_instrument_resolution.py` enforces.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.core.instruments import Instrument


@dataclass(frozen=True)
class ResolvedInstrument:
    """One provider's names for one canonical instrument.

    `provider` is provenance and is not decoration: a mapping that travels without saying which
    connection produced it can be applied against a different broker, which resolves to the
    wrong contract while looking entirely valid. Every field below is provider-scoped; only
    `canonical_key` crosses connections.
    """

    canonical_key: str          # the Strategy OS instrument key — the only cross-provider id
    provider: str               # which connection produced this mapping
    symbol: str                 # the provider's tradingsymbol for the underlying
    exchange: str               # the provider's exchange code
    token: int | None = None    # the provider's numeric instrument id, when it has one
    lot_size: int | None = None
    tick_size: float | None = None

    def quote_key(self) -> str:
        """The provider's own addressing form, e.g. Kite's `NSE:NIFTY 50`.

        Built here rather than at call sites so a second provider whose feed is addressed
        differently (a token, a URL path) overrides one method instead of every caller.
        """
        return f"{self.exchange}:{self.symbol}"


@runtime_checkable
class InstrumentResolver(Protocol):
    """Maps a canonical Strategy OS instrument onto one provider's symbology.

    Deliberately narrow. This is the *identity* role from the connection model — distinct from
    market data, account/portfolio and execution — so a connection can serve it alone.
    """

    def resolve_underlying(self, inst: Instrument) -> ResolvedInstrument | None:
        """This provider's mapping for the instrument's underlying, or None if it cannot
        resolve it. `None` means "I do not know this instrument" and the caller must refuse —
        never fall back to another provider's mapping, which is how a wrong contract gets
        traded."""
        ...
