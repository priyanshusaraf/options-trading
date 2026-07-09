"""How much the bot may deploy — your own trades always take priority.

The bot is bounded by (a) its own capital cap and (b) in live mode, the REAL
available margin minus a reserve kept free for you. Position/margin glitches during
your intraday exits can't let it overspend because the hard cap still binds."""
from app.engine.capital import deployable_capital


def test_paper_bounded_by_cap_minus_deployed():
    # paper / mock: real margin not consumed -> bounded by cap headroom only
    d = deployable_capital(ledger_base=100000, bot_deployed=30000,
                           account_available=None, reserve=0, cap=0, is_live=False)
    assert d == 70000


def test_cap_overrides_ledger_base():
    d = deployable_capital(ledger_base=100000, bot_deployed=10000,
                           account_available=None, reserve=0, cap=40000, is_live=False)
    assert d == 30000           # 40k cap - 10k deployed, not 100k base


def test_live_bounded_by_real_available_minus_reserve():
    # plenty of bot-cap headroom, but the account only has 20k free and we keep 5k
    d = deployable_capital(ledger_base=100000, bot_deployed=0,
                           account_available=20000, reserve=5000, cap=0, is_live=True)
    assert d == 15000           # min(100k, 20k-5k)


def test_live_takes_the_tighter_of_cap_and_margin():
    d = deployable_capital(ledger_base=100000, bot_deployed=0,
                           account_available=80000, reserve=0, cap=25000, is_live=True)
    assert d == 25000           # cap is tighter than available


def test_never_negative_when_owner_locked_the_capital():
    # you used the margin for your own trades -> available below the reserve
    d = deployable_capital(ledger_base=100000, bot_deployed=0,
                           account_available=3000, reserve=5000, cap=0, is_live=True)
    assert d == 0.0


def test_live_fails_closed_when_account_read_unavailable():
    # live but the real account margin is unreadable (margins()/token failure -> None):
    # deploy NOTHING rather than sizing off the bot's ledger cap while blind to the
    # actual account headroom (audit H12 — fail closed, not open).
    d = deployable_capital(ledger_base=100000, bot_deployed=0,
                           account_available=None, reserve=0, cap=0, is_live=True)
    assert d == 0.0
