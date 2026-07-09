"""Position-ownership boundary — the most important safety rule once the bot runs
on the owner's REAL account (which also holds the owner's own discretionary
trades). The bot may only act on contracts IT opened, and must verify the live
account actually backs its long position before it ever sends a close order. It
NEVER touches, enumerates, or squares off the owner's positions."""
from app.engine.reconcile import account_net_qty, can_bot_close, find_orphans


class FakePos:
    def __init__(self, ts, qty):
        self.tradingsymbol = ts
        self.qty = qty
        self.instrument_key = ts


def test_account_net_qty_sums_matching_symbol():
    acct = [{"tradingsymbol": "NIFTY24CE", "quantity": 75},
            {"tradingsymbol": "NIFTY24CE", "quantity": 75},
            {"tradingsymbol": "OTHER", "quantity": 50}]
    assert account_net_qty(acct, "NIFTY24CE") == 150
    assert account_net_qty(acct, "MISSING") == 0


def test_can_close_when_account_backs_the_long():
    chk = can_bot_close(FakePos("X", 75), [{"tradingsymbol": "X", "quantity": 75}])
    assert chk.ok is True


def test_cannot_close_when_account_short_of_qty():
    # owner partially exited the same symbol, or a margin/position glitch
    chk = can_bot_close(FakePos("X", 75), [{"tradingsymbol": "X", "quantity": 50}])
    assert chk.ok is False and "not sending" in chk.reason.lower()


def test_cannot_close_when_symbol_absent_from_account():
    chk = can_bot_close(FakePos("X", 75), [{"tradingsymbol": "Y", "quantity": 75}])
    assert chk.ok is False


def test_cannot_close_when_account_is_net_short_that_symbol():
    # the owner is SHORT X — selling the bot's qty would deepen the owner's short
    chk = can_bot_close(FakePos("X", 75), [{"tradingsymbol": "X", "quantity": -75}])
    assert chk.ok is False


def test_find_orphans_flags_bot_positions_not_in_account():
    bot = [FakePos("A", 75), FakePos("B", 50)]
    acct = [{"tradingsymbol": "A", "quantity": 75}]      # B missing from the account
    orphans = find_orphans(bot, acct)
    assert [o.tradingsymbol for o in orphans] == ["B"]


# ── C4: a failed/unauthenticated account read must never look like a flat account ──
def test_account_net_qty_none_read_is_zero():
    # a failed read (None) is not a flat account — net is 0 but callers must fail closed
    assert account_net_qty(None, "X") == 0


def test_cannot_close_when_account_read_unavailable():
    # provider.account_positions() returned None (API/auth failure) — never send an order
    chk = can_bot_close(FakePos("X", 75), None)
    assert chk.ok is False and "unavailable" in chk.reason.lower()


def test_find_orphans_returns_none_when_account_read_unavailable():
    # a None read must NOT mark every bot position as orphaned (that is the phantom-close bug)
    bot = [FakePos("A", 75), FakePos("B", 50)]
    assert find_orphans(bot, None) == []
