"""Dhan's names for our canonical instruments — loaded from Dhan's own master, never guessed.

A Dhan instrument is addressed by `(exchangeSegment, securityId)` where `securityId` is an
opaque numeric string. **There is no rule that turns `RELIANCE` into one.** It is a lookup, and
the authoritative source is Dhan's published scrip master:

    https://images.dhan.co/api-data/api-scrip-master.csv          (compact)
    https://images.dhan.co/api-data/api-scrip-master-detailed.csv (detailed)

This module deliberately does **not** ship a hand-typed seed of security ids, and that is a
correction to the pattern `upstox_instruments.py` used. A wrong id there does not raise: it
resolves to a *different real company* and returns valid-looking prices for it, forever, with
every layer above reporting health. Typing a dozen opaque integers from memory is precisely the
way to produce that, and no test can catch it — the numbers are unverifiable by inspection.

So: an unloaded master resolves nothing, and every caller refuses. That is a working connection
with no coverage rather than a connection with wrong coverage, and only one of those two can
lose money quietly.

`load_master(rows)` takes already-parsed rows so the fetch is the caller's decision. The column
names differ between the compact and detailed files, so the resolution below tries the
documented spellings and **raises** when none is present, rather than silently producing an
empty master that would look exactly like a broker with no instruments.
"""
from __future__ import annotations

import dataclasses

from app.providers.base import ProviderReadError

MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"
MASTER_URL_DETAILED = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"

#: Documented `exchangeSegment` enum. Total: a segment absent from here is not a Dhan segment,
#: and sending one is rejected at the API with an error that does not name the field.
EXCHANGE_SEGMENTS = frozenset({
    "IDX_I", "NSE_EQ", "NSE_FNO", "NSE_CURRENCY",
    "BSE_EQ", "BSE_FNO", "BSE_CURRENCY", "MCX_COMM",
})

#: Documented `instrument` enum.
INSTRUMENT_TYPES = frozenset({
    "INDEX", "FUTIDX", "OPTIDX", "EQUITY", "FUTSTK", "OPTSTK",
    "FUTCOM", "OPTFUT", "FUTCUR", "OPTCUR",
})

# Column spellings, compact file first then detailed. Tried in order; a missing set raises.
_SECURITY_ID_COLUMNS = ("SECURITY_ID", "SEM_SMST_SECURITY_ID")
_SEGMENT_COLUMNS = ("SEGMENT", "SEM_SEGMENT")
_SYMBOL_COLUMNS = ("SYMBOL_NAME", "SM_SYMBOL_NAME", "SEM_TRADING_SYMBOL")
_INSTRUMENT_COLUMNS = ("INSTRUMENT", "SEM_INSTRUMENT_NAME", "SEM_EXCH_INSTRUMENT_TYPE")


@dataclasses.dataclass(frozen=True)
class DhanInstrument:
    """One row of Dhan's master: what Dhan calls one canonical instrument."""

    canonical_key: str      # the Strategy OS key — the only identifier that crosses providers
    security_id: str        # Dhan's addressing form, opaque and numeric
    exchange_segment: str
    instrument: str
    tradingsymbol: str      # Dhan's display symbol, NOT Kite's


_MASTER: dict[str, DhanInstrument] = {}


def _pick(row: dict, candidates: tuple[str, ...]) -> str | None:
    for name in candidates:
        value = row.get(name)
        if value not in (None, ""):
            return str(value).strip()
    return None


def load_master(rows, *, canonical_for) -> int:
    """Replace the master from parsed CSV rows. Returns how many were mapped.

    `canonical_for(symbol, segment) -> str | None` is the caller's decision about which Dhan rows
    correspond to canonical instruments. It is injected rather than implemented here because a
    symbol-matching rule living inside a provider module is how a second canonical symbol table
    gets born — the thing `.claude/rules/providers-brokers.md` forbids outright.
    """
    mapped: dict[str, DhanInstrument] = {}
    seen_columns = False
    for row in rows:
        sec = _pick(row, _SECURITY_ID_COLUMNS)
        seg = _pick(row, _SEGMENT_COLUMNS)
        sym = _pick(row, _SYMBOL_COLUMNS)
        if sec and seg and sym:
            seen_columns = True
        else:
            continue
        canonical = canonical_for(sym, seg)
        if not canonical:
            continue
        mapped[canonical] = DhanInstrument(
            canonical_key=canonical, security_id=sec, exchange_segment=seg,
            instrument=_pick(row, _INSTRUMENT_COLUMNS) or "", tradingsymbol=sym)
    if not seen_columns:
        # An empty master and a master whose columns we could not read look identical to every
        # caller — both resolve nothing. Only one of them is a bug, so they are separated here.
        raise ProviderReadError(
            f"dhan scrip master: none of the expected column sets were present. Looked for "
            f"security id in {_SECURITY_ID_COLUMNS}, segment in {_SEGMENT_COLUMNS}, symbol in "
            f"{_SYMBOL_COLUMNS}. Re-read {MASTER_URL} — the file's columns have changed.")
    _MASTER.clear()
    _MASTER.update(mapped)
    return len(_MASTER)


def clear_master() -> None:
    _MASTER.clear()


def lookup(canonical_key: str) -> DhanInstrument | None:
    """Dhan's row for a canonical key, or `None`.

    `None` means "this connection cannot address that instrument" — because the master is not
    loaded, or because Dhan does not carry it. The caller must refuse either way, and must never
    fall back to another provider's symbology.
    """
    return _MASTER.get(canonical_key)


def coverage() -> frozenset[str]:
    """Which canonical instruments this connection can currently serve. Empty until a master is
    loaded, and honestly so."""
    return frozenset(_MASTER)
