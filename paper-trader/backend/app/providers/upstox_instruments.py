"""Upstox's names for our canonical instruments — provider-owned data, not provider logic.

An Upstox instrument key is `SEGMENT|ISIN` (`NSE_EQ|INE848E01016`) or, for indices,
`SEGMENT|NAME` (`NSE_INDEX|Nifty 50`). **There is no transformation from a Kite tradingsymbol to
one.** `RELIANCE` does not become `INE002A01018` by any rule; it is a lookup.

That is exactly why this is a data file and not a function. A `_derive_key(inst)` inside the
provider would be a second symbol table — the thing `.claude/rules/providers-brokers.md` forbids
and the thing that makes the second adapter the one nobody can verify. It is also why the
canonical `Instrument` cannot carry the mapping: it already carries Kite's, and a second one
would fork it.

**Seeded fixture, deliberately, and deliberately visible.** The authoritative source is Upstox's
official daily instrument JSON. Loading that is the right long-term shape and needs a live
connection to fetch; until the acceptance run in the design doc §4, this module holds a small
audited mapping for the instruments the universe actually uses, in one place, where it can be
diffed against the official master rather than hidden inside request-building.

Every ISIN below is a real, checkable identifier. If one is wrong the adapter resolves to the
wrong company — silently, because a valid-looking key returns valid-looking prices. That failure
mode is the reason `check_instrument_identity` requires provenance on every mapping, and the
reason the acceptance run must verify these against the official master before anyone trusts a
number produced through this connection.
"""
from __future__ import annotations

import dataclasses

# Upstox segment codes used here. Kept as constants so a typo is a NameError rather than a key
# that resolves to nothing at request time.
NSE_INDEX = "NSE_INDEX"
NSE_EQ = "NSE_EQ"


@dataclasses.dataclass(frozen=True)
class UpstoxInstrument:
    """One row of the provider's master: what Upstox calls one canonical instrument."""

    canonical_key: str      # the Strategy OS key — the only identifier that crosses providers
    instrument_key: str     # Upstox's addressing form, `SEGMENT|ISIN` or `SEGMENT|NAME`
    segment: str
    tradingsymbol: str      # Upstox's display symbol, NOT Kite's
    isin: str | None = None


def _index(canonical: str, name: str, symbol: str) -> UpstoxInstrument:
    return UpstoxInstrument(canonical_key=canonical, instrument_key=f"{NSE_INDEX}|{name}",
                            segment=NSE_INDEX, tradingsymbol=symbol)


def _equity(canonical: str, isin: str, symbol: str) -> UpstoxInstrument:
    return UpstoxInstrument(canonical_key=canonical, instrument_key=f"{NSE_EQ}|{isin}",
                            segment=NSE_EQ, tradingsymbol=symbol, isin=isin)


# Indices first: they are addressed by NAME rather than ISIN, which is a genuine shape
# difference in the key format and not a special case in the code.
_SEED: tuple[UpstoxInstrument, ...] = (
    _index("NIFTY", "Nifty 50", "NIFTY 50"),
    _index("BANKNIFTY", "Nifty Bank", "NIFTY BANK"),
    _equity("RELIANCE", "INE002A01018", "RELIANCE"),
    _equity("TCS", "INE467B01029", "TCS"),
    _equity("HDFCBANK", "INE040A01034", "HDFCBANK"),
    _equity("INFY", "INE009A01021", "INFY"),
    _equity("ICICIBANK", "INE090A01021", "ICICIBANK"),
    _equity("SBIN", "INE062A01020", "SBIN"),
    _equity("ITC", "INE154A01025", "ITC"),
    _equity("LT", "INE018A01030", "LT"),
    _equity("AXISBANK", "INE238A01034", "AXISBANK"),
    _equity("MARUTI", "INE585B01010", "MARUTI"),
)

BY_CANONICAL_KEY: dict[str, UpstoxInstrument] = {row.canonical_key: row for row in _SEED}


def lookup(canonical_key: str) -> UpstoxInstrument | None:
    """Upstox's row for a canonical key, or `None`.

    `None` means "this connection does not carry that instrument" and the caller must refuse.
    It must never fall back to another provider's symbology, which is how a wrong contract gets
    priced while every layer above looks healthy.
    """
    return BY_CANONICAL_KEY.get(canonical_key)


def coverage() -> frozenset[str]:
    """Which canonical instruments this connection can serve. Used by the conformance case, and
    by anyone asking honestly what a seeded master does and does not cover."""
    return frozenset(BY_CANONICAL_KEY)
