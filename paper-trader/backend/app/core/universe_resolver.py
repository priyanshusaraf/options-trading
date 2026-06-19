"""
Add / remove instruments in the dynamic universe.

When the owner adds an instrument (from the homepage picker or a backtest winner),
we resolve its full spec — preferring the already-built backtest universe (which
came from Kite's dumps), then a raw Kite lookup — persist it as a user
`UniverseInstrument`, enable it for trading, and refresh the in-memory registry.
Seed instruments are never deleted, only un-pinned / disabled.
"""
from __future__ import annotations

from app.core import instruments as reg
from app.core.instruments import Instrument
from app.core.logging import log
from app.db.models import InstrumentState, UniverseInstrument
from app.db.session import SessionLocal

# cache of {key: Instrument} resolved from the Kite-built universe, per day
_catalog: dict[str, Instrument] = {}
_catalog_day: str | None = None


def _build_catalog(provider) -> dict[str, Instrument]:
    global _catalog, _catalog_day
    import datetime as dt
    today = str(dt.date.today())
    if _catalog_day == today and _catalog:
        return _catalog
    from app.backtest.universe import liquid_universe
    try:
        specs = {i.key: i for i in liquid_universe(provider)}
    except Exception as e:
        log.warn(f"universe catalog build failed: {e}")
        specs = {}
    _catalog, _catalog_day = specs, today
    return specs


def resolve_spec(key: str, provider) -> Instrument | None:
    """Find the full Instrument spec for `key`: registry first, then the
    Kite-built catalog, then the full (all-equities) universe."""
    if key in reg._registry:
        return reg._registry[key]
    cat = _build_catalog(provider)
    if key in cat:
        return cat[key]
    try:
        from app.backtest.universe import full_universe
        return {i.key: i for i in full_universe(provider)}.get(key)
    except Exception:
        return None


def add_instrument(key: str, provider, on_home: bool = True,
                   interval: str | None = None) -> dict:
    spec = resolve_spec(key, provider)
    if spec is None:
        return {"error": f"could not resolve instrument '{key}'"}
    # promotion carry-over: keep a supported live interval; else fall back + warn
    from app.core.config import LIVE_INTERVALS, normalize_live_interval
    iv = warning = None
    if interval:
        iv = normalize_live_interval(interval)
        if interval not in LIVE_INTERVALS:
            warning = f"{interval} is not a live timeframe; using {iv}"
    with SessionLocal() as s:
        row = s.get(UniverseInstrument, key)
        if row is None:
            s.add(UniverseInstrument(
                key=spec.key, name=spec.name, segment=spec.segment,
                spot_exchange=spec.spot_exchange, spot_symbol=spec.spot_symbol,
                option_name=spec.option_name, lot_size=spec.lot_size,
                strike_step=spec.strike_step, priority=spec.priority,
                has_options=spec.has_options, source="user", on_home=on_home,
                active=True, mock_spot=spec.mock_spot, mock_vol=spec.mock_vol))
        else:
            row.active = True
            row.on_home = on_home
        st = s.get(InstrumentState, key)
        if st is None:
            st = InstrumentState(instrument_key=key, enabled=True)
            s.add(st)
        else:
            st.enabled = True
        if iv:
            st.live_interval = iv
        s.commit()
    reg.load_universe()
    log.info(f"added {key} to portfolio universe (has_options={spec.has_options}"
             f"{', interval=' + iv if iv else ''})")
    out = {"key": key, "added": True, "has_options": spec.has_options,
           "name": spec.name, "segment": spec.segment}
    if iv:
        out["interval"] = iv
    if warning:
        out["interval_warning"] = warning
    return out


def remove_instrument(key: str) -> dict:
    """Un-pin from the homepage and disable trading. User-added instruments are
    deactivated entirely; seed instruments are kept but disabled/un-pinned."""
    with SessionLocal() as s:
        row = s.get(UniverseInstrument, key)
        if row is None:
            return {"error": f"unknown instrument '{key}'"}
        row.on_home = False
        if row.source == "user":
            row.active = False
        st = s.get(InstrumentState, key)
        if st is not None:
            st.enabled = False
        s.commit()
        was_user = row.source == "user"
    reg.load_universe()
    log.info(f"removed {key} from portfolio universe (user={was_user})")
    return {"key": key, "removed": True}
