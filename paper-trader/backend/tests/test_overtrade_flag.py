"""overtrade_flag: advisory red flag — set live + persisted, reloaded on restart."""
from app.db.session import init_db
from app.engine.runner import EngineRunner


def _fresh_runner():
    init_db(reset=True)
    return EngineRunner()


def test_set_overtrade_flag_live_and_persisted():
    r = _fresh_runner()
    try:
        r.set_overtrade_flag("GOLDM", True)
        assert r.overtrade_flags.get("GOLDM") is True
    finally:
        r.broker.close()
    # a fresh runner reloads the flag from the DB
    r2 = EngineRunner()
    try:
        assert r2.overtrade_flags.get("GOLDM") is True
        r2.set_overtrade_flag("GOLDM", False)
        assert "GOLDM" not in r2.overtrade_flags
    finally:
        r2.broker.close()
