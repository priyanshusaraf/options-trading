"""audit H14: at startup the bot never checked the reverse direction — a REAL Kite
position the ledger has no row for was invisible. It cannot safely adopt one (the account
also holds the owner's own trades, and positions() carries no bot tag), so it surfaces
untracked positions for the operator instead of touching them.

2026-08-01: it surfaced them ALL identically — ERROR + Telegram, on every restart. In
production that meant NETWEB and DIXON, the owner's own discretionary positions, raised the
same alarm several times a day indefinitely. The alert that guards against a phantom book
(invariant #2) was therefore the one alert guaranteed to be ignored. The two cases are now
distinguished by the bot's own order journal, which is the only evidence available about
who placed what.
"""
import datetime as dt

from app.db.models import OrderJournal
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner


def _runner():
    init_db(reset=True)
    return EngineRunner()


def _journal(symbol, when):
    """`placed_at` is stamped on the ENGINE clock (provider.now()), not wall time — the
    mock provider runs at 2025-01-09, so a wall-clock stamp would never match "today"."""
    with SessionLocal() as s:
        s.add(OrderJournal(
            order_id=f"OID-{symbol}", tradingsymbol=symbol, instrument_key=symbol,
            side="BUY", kind="equity", intent="ENTRY", qty=10, status="TERMINAL",
            placed_at=when))
        s.commit()


def test_a_position_the_bot_ordered_but_lost_raises_a_real_alert():
    """The dangerous case: the account holds something the bot ORDERED and is not
    tracking. The book and the account disagree — that is the phantom-book precondition."""
    r = _runner()
    _journal("SUZLON", r.provider.now())
    r.provider.account_positions = lambda: [{"tradingsymbol": "SUZLON", "quantity": 940}]
    sent = []
    r.notifier._emit = lambda m: sent.append(m)

    assert r.startup_account_reconcile() == ["SUZLON"]
    assert sent, "a fill the bot lost must always alert"
    assert "SUZLON" in sent[0]


def test_your_own_discretionary_position_is_reported_but_does_not_cry_wolf():
    """THE production noise: NETWEB and DIXON are the owner's, the bot never ordered them,
    and it re-alerted on every restart forever."""
    r = _runner()
    r.provider.account_positions = lambda: [{"tradingsymbol": "NETWEB", "quantity": 5},
                                            {"tradingsymbol": "DIXON", "quantity": 2}]
    sent = []
    r.notifier._emit = lambda m: sent.append(m)

    assert sorted(r.startup_account_reconcile()) == ["DIXON", "NETWEB"]
    assert sent == [], "a position the bot never ordered must not raise a phantom-book alarm"


def test_a_mixed_account_alerts_only_about_the_bots_own_lost_fill():
    r = _runner()
    _journal("SUZLON", r.provider.now())
    r.provider.account_positions = lambda: [{"tradingsymbol": "NETWEB", "quantity": 5},
                                            {"tradingsymbol": "SUZLON", "quantity": 940}]
    sent = []
    r.notifier._emit = lambda m: sent.append(m)

    assert sorted(r.startup_account_reconcile()) == ["NETWEB", "SUZLON"]
    assert len(sent) == 1
    assert "SUZLON" in sent[0] and "NETWEB" not in sent[0]


def test_yesterdays_journal_entry_does_not_make_todays_position_a_lost_fill():
    """The journal spans the life of the DB; only orders placed today can explain a
    position sitting in today's account."""
    r = _runner()
    _journal("SUZLON", r.provider.now() - dt.timedelta(days=9))
    r.provider.account_positions = lambda: [{"tradingsymbol": "SUZLON", "quantity": 940}]
    sent = []
    r.notifier._emit = lambda m: sent.append(m)

    assert r.startup_account_reconcile() == ["SUZLON"]
    assert sent == []


def test_a_position_already_in_the_book_is_not_untracked():
    r = _runner()
    r.provider.account_positions = lambda: [{"tradingsymbol": "ANYTHING", "quantity": 0}]
    assert r.startup_account_reconcile() == []      # zero qty is not a position


def test_flat_or_failed_read_surfaces_nothing():
    r = _runner()
    r.provider.account_positions = lambda: []      # flat account
    assert r.startup_account_reconcile() == []
    r.provider.account_positions = lambda: None     # read failed
    assert r.startup_account_reconcile() == []


def test_an_unreadable_journal_fails_closed_and_alerts(monkeypatch):
    """If we cannot tell whose position it is, assume it is the dangerous case."""
    r = _runner()
    r.provider.account_positions = lambda: [{"tradingsymbol": "NETWEB", "quantity": 5}]
    monkeypatch.setattr(r, "_journaled_symbols_today",
                        lambda: {"NETWEB"})          # what the failure path returns
    sent = []
    r.notifier._emit = lambda m: sent.append(m)

    assert r.startup_account_reconcile() == ["NETWEB"]
    assert sent, "an unknowable owner must escalate, never go quiet"
