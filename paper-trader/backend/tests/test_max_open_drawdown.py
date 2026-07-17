from app.core.config import Settings


def test_max_open_drawdown_default_is_no_longer_zero():
    """H15 (pre-live audit): the guard existed but shipped disabled (0 = off).
    Owner default: half the ₹5k daily-loss halt, since open MTM bleeds faster
    than realized P&L."""
    s = Settings()
    assert s.max_open_drawdown == 2500.0
