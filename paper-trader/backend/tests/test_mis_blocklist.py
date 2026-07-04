"""#5: names the MIS sheet marks ineligible cannot be added to the intraday portfolio."""
import pytest

from app.core import mis_blocklist as mb
from app.db.session import init_db
from app.engine.runner import EngineRunner


def test_is_mis_blocked_normalizes_exchange_prefix(monkeypatch):
    monkeypatch.setattr(mb, "_blocked", lambda: frozenset({"ELITECON"}))
    assert mb.is_mis_blocked("ELITECON") is True
    assert mb.is_mis_blocked("NSE:ELITECON") is True     # exchange-prefixed engine key normalizes
    assert mb.is_mis_blocked("reliance") is False        # case-insensitive, not blocked


def test_set_product_refuses_intraday_for_blocked_name(monkeypatch):
    monkeypatch.setattr(mb, "_blocked", lambda: frozenset({"BLOCKEDNAME"}))
    init_db(reset=True)
    r = EngineRunner()
    with pytest.raises(ValueError):
        r.set_product("BLOCKEDNAME", "equity_intraday")
    assert r.set_product("BLOCKEDNAME", "options") == "options"        # options always fine
    assert r.set_product("RELIANCE", "equity_intraday") == "equity_intraday"  # not blocked -> ok


def test_generated_blocklist_file_loads():
    # the committed app/data/mis_blocklist.json (generated from the sheet) must load and
    # carry ELITECON (the lone 1x name) — a smoke test that the fetch output is valid.
    mb.reload_blocklist()
    assert mb.is_mis_blocked("ELITECON") is True
    mb.reload_blocklist()
