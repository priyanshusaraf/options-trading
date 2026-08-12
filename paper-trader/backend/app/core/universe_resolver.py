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
from sqlalchemy import select

from app.db.models import InstrumentState, Position, UniverseInstrument, UniversePreference
from app.db.session import SessionLocal

# Canonical market catalog cache.  Provider/source identity is part of the key:
# two feeds can legitimately answer differently for the same calendar day.
_catalog: dict[tuple[str, str], dict[str, Instrument]] = {}


def _provider_source(provider) -> str:
    """Stable public-data source identity for answer-changing cache keys."""
    identity = getattr(provider, "source_id", None)
    if callable(identity):
        identity = identity()
    return str(identity or getattr(provider, "name", provider.__class__.__name__))


def _build_catalog(provider) -> dict[str, Instrument]:
    import datetime as dt
    today = str(dt.date.today())
    cache_key = (_provider_source(provider), today)
    cached = _catalog.get(cache_key)
    if cached is not None:
        return cached
    from app.backtest.universe import liquid_universe
    try:
        specs = {i.key: i for i in liquid_universe(provider)}
    except Exception as e:
        log.warn(f"universe catalog build failed: {e}")
        specs = {}
    _catalog[cache_key] = specs
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
                   interval: str | None = None, strategy_key: str | None = None,
                   product: str | None = None, *, owner_id: str) -> dict:
    # Before any write: this function assigns `InstrumentState.strategy_key` directly and
    # validates only against the registry, so it is a second route from "a graph-backed
    # strategy is registered" to "a graph-backed strategy is assigned". Raising here
    # rather than dropping the key keeps the refusal visible — a silently ignored
    # strategy would add the instrument under the default and report success.
    from app.core.execution_binding import assert_may_execute
    assert_may_execute(strategy_key, owner_id=owner_id)
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
                has_options=spec.has_options, source="market", on_home=False,
                active=True, mock_spot=spec.mock_spot, mock_vol=spec.mock_vol))
        pref = s.get(UniversePreference, (owner_id, key))
        if pref is None:
            s.add(UniversePreference(owner_id=owner_id, instrument_key=key,
                                     active=True, on_home=on_home, source="user"))
        else:
            pref.active = True
            pref.on_home = on_home
        st = s.get(InstrumentState, (owner_id, key))
        if st is None:
            st = InstrumentState(owner_id=owner_id, instrument_key=key, enabled=True)
            s.add(st)
        else:
            st.enabled = True
        if iv:
            st.live_interval = iv
        applied_product = applied_strategy = None
        if product in ("options", "equity_intraday"):
            st.product = product
            applied_product = product
        if strategy_key:
            from app.strategy.registry import resolve_strategy
            try:
                resolve_strategy(strategy_key, owner_id=owner_id)
            except LookupError:
                pass
            else:
                st.strategy_key = strategy_key
                applied_strategy = strategy_key
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
    if applied_product:
        out["product"] = applied_product
    if applied_strategy:
        out["strategy_key"] = applied_strategy
    return out


def remove_instrument(key: str, *, owner_id: str, broker_account_id: str) -> dict:
    """Un-pin from the homepage and disable trading. User-added instruments are
    deactivated entirely; seed instruments are kept but disabled/un-pinned."""
    with SessionLocal() as s:
        row = s.get(UniverseInstrument, key)
        if row is None:
            return {"error": f"unknown instrument '{key}'"}
        # E1: deactivating an instrument the bot still holds pops it from the registry,
        # poisoning the position's key. The risk loop now survives that, but refuse it
        # at the source anyway — an open position must stay resolvable.
        # (the Position table holds the OPEN book only — closes become Trade rows)
        if s.scalar(select(Position.id).where(
                Position.owner_id == owner_id,
                Position.broker_account_id == broker_account_id,
                Position.instrument_key == key).limit(1)):
            return {"error": f"'{key}' has an open position — close it before removing"}
        pref = s.get(UniversePreference, (owner_id, key))
        if pref is None:
            return {"error": f"'{key}' is not in this portfolio"}
        pref.on_home = False
        if pref.source == "user":
            pref.active = False
        st = s.get(InstrumentState, (owner_id, key))
        if st is not None:
            st.enabled = False
        s.commit()
        was_user = pref.source == "user"
    reg.load_universe()
    log.info(f"removed {key} from portfolio universe (user={was_user})")
    return {"key": key, "removed": True}


def composed_universe(owner_id: str) -> list[tuple[UniverseInstrument, UniversePreference]]:
    """Return canonical facts composed with only this owner's preference rows."""
    with SessionLocal() as s:
        return list(s.execute(select(UniverseInstrument, UniversePreference).join(
            UniversePreference,
            (UniversePreference.instrument_key == UniverseInstrument.key)
            & (UniversePreference.owner_id == owner_id),
        )).all())
