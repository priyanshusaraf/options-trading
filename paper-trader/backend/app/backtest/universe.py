"""
Build the backtest universe.

"liquid" (default): the tradable, actually-liquid set — index futures, NSE F&O
stock underlyings, and liquid MCX/NCDEX commodities (~200+ names). Resolved from
Kite's instrument dumps when authenticated.

"full": everything resolvable (all NSE/BSE equities + commodities) — a much
larger, slower opt-in sweep.

Offline / unauthenticated (tests, mock): falls back to the curated seed list so
the whole sweep pipeline is exercisable without Kite.
"""
from __future__ import annotations

from app.core.instruments import Instrument, all_instruments
from app.core.logging import log

# Index option `name` -> NSE/BSE spot tradingsymbol (indices don't trade as the
# bare name; their spot series lives under these symbols).
INDEX_SPOT = {
    "NIFTY": ("NSE", "NIFTY 50"),
    "BANKNIFTY": ("NSE", "NIFTY BANK"),
    "FINNIFTY": ("NSE", "NIFTY FIN SERVICE"),
    "MIDCPNIFTY": ("NSE", "NIFTY MIDCAP SELECT"),
    "SENSEX": ("BSE", "SENSEX"),
    "BANKEX": ("BSE", "BANKEX"),
}


def _modal_step(strikes: list[float]) -> float:
    gaps = [round(b - a, 4) for a, b in zip(strikes, strikes[1:]) if b > a]
    if not gaps:
        return 1.0
    # most common positive gap = strike step
    return max(set(gaps), key=gaps.count)


def _fno_underlyings(provider, exchange: str, segment: str) -> list[Instrument]:
    """Derive option underlyings (indices + stocks) from an options dump."""
    try:
        rows = provider._instruments(exchange)  # throttled, cached per-day
    except Exception as e:
        log.warn(f"could not load {exchange} dump for universe: {e}")
        return []
    by_name: dict[str, list] = {}
    for r in rows:
        if r.get("instrument_type") in ("CE", "PE") and r.get("name"):
            by_name.setdefault(r["name"], []).append(r)

    out: list[Instrument] = []
    for name, rs in by_name.items():
        lot = max((int(r.get("lot_size") or 0) for r in rs), default=0) or 1
        strikes = sorted({float(r["strike"]) for r in rs if r.get("strike")})
        step = _modal_step(strikes)
        spot_exch, spot_sym = INDEX_SPOT.get(name, (("BSE", name) if segment == "BFO" else ("NSE", name)))
        out.append(Instrument(
            key=name, name=name, segment=segment, spot_exchange=spot_exch,
            spot_symbol=spot_sym, option_name=name, lot_size=lot,
            strike_step=step, priority=100, mock_spot=1000.0, mock_vol=0.2))
    return out


def _mcx_commodities(provider) -> list[Instrument]:
    """MCX commodity underlyings (those that have options), via the FUT/OPT dump."""
    try:
        rows = provider._instruments("MCX")
    except Exception as e:
        log.warn(f"could not load MCX dump: {e}")
        return []
    names = {r["name"] for r in rows
             if r.get("instrument_type") in ("CE", "PE") and r.get("name")}
    out: list[Instrument] = []
    for name in names:
        opt_rows = [r for r in rows if r.get("name") == name and r.get("instrument_type") in ("CE", "PE")]
        lot = max((int(r.get("lot_size") or 0) for r in opt_rows), default=0) or 1
        strikes = sorted({float(r["strike"]) for r in opt_rows if r.get("strike")})
        out.append(Instrument(
            key=name, name=name, segment="MCX", spot_exchange="MCX",
            spot_symbol=name, option_name=name, lot_size=lot,
            strike_step=_modal_step(strikes), priority=100,
            mock_spot=1000.0, mock_vol=0.25))
    return out


def liquid_universe(provider) -> list[Instrument]:
    """The liquid, tradable universe. Real set from Kite when authenticated;
    curated seed list otherwise."""
    authed = False
    try:
        authed = provider.name == "kite" and provider.is_authenticated()
    except Exception:
        authed = False

    if not authed:
        log.info("backtest universe: using curated seed list (Kite not authenticated)")
        return list(all_instruments())

    specs: dict[str, Instrument] = {}
    for inst in (_fno_underlyings(provider, "NFO", "NFO")
                 + _fno_underlyings(provider, "BFO", "BFO")
                 + _mcx_commodities(provider)):
        specs.setdefault(inst.key, inst)
    # always include the curated seed names (correct index spot symbols etc.)
    for inst in all_instruments():
        specs.setdefault(inst.key, inst)
    result = list(specs.values())
    log.info(f"backtest universe (liquid): {len(result)} instruments resolved from Kite")
    return result


def full_universe(provider) -> list[Instrument]:
    """Opt-in: liquid set + all NSE/BSE cash equities (no options → tracking/
    backtest only). Large and slow."""
    base = {i.key: i for i in liquid_universe(provider)}
    authed = getattr(provider, "name", "") == "kite"
    if not authed:
        return list(base.values())
    for exch in ("NSE", "BSE"):
        try:
            rows = provider._instruments(exch)
        except Exception:
            continue
        for r in rows:
            if r.get("instrument_type") == "EQ" and r.get("tradingsymbol"):
                key = f"{exch}:{r['tradingsymbol']}"
                base.setdefault(key, Instrument(
                    key=key, name=r.get("name") or r["tradingsymbol"],
                    segment=exch, spot_exchange=exch, spot_symbol=r["tradingsymbol"],
                    option_name="", lot_size=1, strike_step=0.05, priority=200,
                    mock_spot=1000.0, mock_vol=0.2, has_options=False))
    return list(base.values())
