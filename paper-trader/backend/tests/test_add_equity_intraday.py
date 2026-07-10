"""Adding a non-options cash equity by its bare symbol (e.g. HEG).

Regression: options/F&O underlyings are keyed by bare name ("RELIANCE"), but
`full_universe` keys cash equities as "NSE:HEG". The add UI posts the bare typed
symbol, so `resolve_spec` never matched an equity -> "could not resolve". These
tests pin: (1) a bare equity symbol resolves to its NSE:<sym> spec, (2) the add
persists ONE canonical key across both tables, and (3) a no-options name defaults
to intraday so it can actually trade (not sit tracking-only).
"""
from app.core import instruments as reg
from app.core import universe_resolver as ur
from app.db.models import InstrumentState, UniverseInstrument
from app.db.session import SessionLocal, init_db


class FakeKite:
    """Minimal provider exposing just what liquid/full_universe consume."""
    name = "kite"

    def is_authenticated(self):
        return True

    def _instruments(self, exch):
        # NSE has a cash equity HEG (no options). No NFO/BFO/MCX option rows,
        # so HEG is NOT an option underlying -> only reachable via full_universe.
        if exch == "NSE":
            return [
                {"instrument_type": "EQ", "tradingsymbol": "HEG", "name": "HEG LTD"},
            ]
        return []


def _reset_catalog():
    ur._catalog, ur._catalog_day = {}, None


def test_resolve_bare_equity_symbol():
    _reset_catalog()
    spec = ur.resolve_spec("HEG", FakeKite())
    assert spec is not None, "bare equity symbol 'HEG' should resolve"
    assert spec.key == "NSE:HEG"
    assert spec.has_options is False


def test_add_bare_equity_is_consistent_and_intraday():
    init_db(reset=True)
    _reset_catalog()
    res = ur.add_instrument("HEG", FakeKite())
    assert "error" not in res, res
    assert res["key"] == "NSE:HEG"                 # canonical key returned
    assert res["has_options"] is False
    assert res.get("product") == "equity_intraday"  # no options -> intraday by default
    # both rows persist under the SAME canonical key (no HEG/NSE:HEG split)
    with SessionLocal() as s:
        assert s.get(UniverseInstrument, "NSE:HEG") is not None
        assert s.get(UniverseInstrument, "HEG") is None
        st = s.get(InstrumentState, "NSE:HEG")
        assert st is not None and st.enabled is True
        assert st.product == "equity_intraday"
    assert "NSE:HEG" in reg._registry


def test_explicit_product_on_equity_is_respected():
    """If the caller passes a product, don't override it with the intraday default."""
    init_db(reset=True)
    _reset_catalog()
    res = ur.add_instrument("HEG", FakeKite(), product="options")
    assert "error" not in res, res
    assert res["key"] == "NSE:HEG"
    assert res.get("product") == "options"
