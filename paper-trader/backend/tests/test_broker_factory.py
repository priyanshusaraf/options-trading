"""You cannot reach the order-placing broker by accident: it needs BOTH live flags
AND the live Kite provider. Default and mock always give the paper broker."""
from app.db.session import init_db
from app.engine.broker import PaperBroker
from app.engine.broker_factory import live_execution_enabled, make_broker
from app.providers.mock import MockProvider


def test_paper_broker_by_default(monkeypatch):
    monkeypatch.delenv("PT_EXECUTION", raising=False)
    monkeypatch.delenv("PT_LIVE_ACK", raising=False)
    init_db(reset=True)
    assert live_execution_enabled() is False
    assert isinstance(make_broker(MockProvider()), PaperBroker)


def test_both_flags_required(monkeypatch):
    monkeypatch.setenv("PT_EXECUTION", "live")
    monkeypatch.delenv("PT_LIVE_ACK", raising=False)
    assert live_execution_enabled() is False          # ack flag missing
    monkeypatch.setenv("PT_LIVE_ACK", "I_UNDERSTAND_REAL_MONEY")
    assert live_execution_enabled() is True


def test_live_flags_but_mock_provider_stays_paper(monkeypatch):
    monkeypatch.setenv("PT_EXECUTION", "live")
    monkeypatch.setenv("PT_LIVE_ACK", "I_UNDERSTAND_REAL_MONEY")
    init_db(reset=True)
    # even with both flags, the mock provider can never place a real order
    assert isinstance(make_broker(MockProvider()), PaperBroker)


def test_make_broker_uses_a_bounded_configurable_order_timeout(monkeypatch):
    """L5: the live order poll timeout must be configurable AND bounded well under
    the old 30s, so a stuck poll can't hold the engine lock for half a minute."""
    import types
    monkeypatch.setenv("PT_EXECUTION", "live")
    monkeypatch.setenv("PT_LIVE_ACK", "I_UNDERSTAND_REAL_MONEY")
    init_db(reset=True)
    prov = MockProvider()
    prov.name = "kite"            # look like the live provider
    prov.access_token = "tok"
    monkeypatch.setattr("app.providers.live_kite.LiveExecutionKite",
                        lambda **k: types.SimpleNamespace(set_access_token=lambda t: None))
    monkeypatch.setattr("app.engine.kite_order_client.KiteOrderClient",
                        lambda *a, **k: object())
    captured = {}

    def fake_lb(provider, client, *, poll_seconds=0.5, timeout_seconds=30.0, notifier=None):
        captured["poll"], captured["timeout"] = poll_seconds, timeout_seconds
        return "LB"

    monkeypatch.setattr("app.engine.live_broker.LiveBroker", fake_lb)
    assert make_broker(prov) == "LB"
    from app.core.config import get_settings
    s = get_settings()
    assert captured["timeout"] == s.order_timeout_seconds
    assert captured["poll"] == s.order_poll_seconds
    assert captured["timeout"] <= 15.0


def test_make_broker_passes_configured_market_protection_to_order_client(monkeypatch):
    """The order client must be built with the configured market_protection_pct so
    every live MARKET order is compliant (unprotected market orders are rejected by
    the exchange since 1-Apr-2026)."""
    import types
    monkeypatch.setenv("PT_EXECUTION", "live")
    monkeypatch.setenv("PT_LIVE_ACK", "I_UNDERSTAND_REAL_MONEY")
    init_db(reset=True)
    prov = MockProvider()
    prov.name = "kite"
    prov.access_token = "tok"
    monkeypatch.setattr("app.providers.live_kite.LiveExecutionKite",
                        lambda **k: types.SimpleNamespace(set_access_token=lambda t: None))
    captured = {}

    def fake_client(kite, **kw):
        captured.update(kw)
        return object()

    monkeypatch.setattr("app.engine.kite_order_client.KiteOrderClient", fake_client)
    monkeypatch.setattr("app.engine.live_broker.LiveBroker",
                        lambda *a, **k: "LB")
    assert make_broker(prov) == "LB"
    from app.core.config import get_settings
    assert captured["market_protection"] == get_settings().market_protection_pct


def test_make_broker_wires_the_provider_tick_size_as_the_tick_source(monkeypatch):
    """The order client must resolve REAL per-instrument tick sizes (LT trades in
    0.10 steps, MARUTI in whole rupees — the 2026-07-15 incident was every trigger
    rounded to a hardcoded 0.05 grid). This one line of wiring connects the whole
    fix to production: make_broker must pass the provider's tick_size method
    through as KiteOrderClient's tick_source."""
    import types
    monkeypatch.setenv("PT_EXECUTION", "live")
    monkeypatch.setenv("PT_LIVE_ACK", "I_UNDERSTAND_REAL_MONEY")
    init_db(reset=True)
    prov = MockProvider()
    prov.name = "kite"
    prov.access_token = "tok"
    prov.tick_size = lambda tradingsymbol, exchange: 0.10   # stands in for KiteProvider.tick_size
    monkeypatch.setattr("app.providers.live_kite.LiveExecutionKite",
                        lambda **k: types.SimpleNamespace(set_access_token=lambda t: None))
    captured = {}

    def fake_client(kite, **kw):
        captured.update(kw)
        return object()

    monkeypatch.setattr("app.engine.kite_order_client.KiteOrderClient", fake_client)
    monkeypatch.setattr("app.engine.live_broker.LiveBroker", lambda *a, **k: "LB")
    assert make_broker(prov) == "LB"
    assert captured["tick_source"] is prov.tick_size
    assert captured["tick_source"]("LT", "NSE") == 0.10


def test_make_broker_tick_source_is_none_when_the_provider_has_no_tick_size(monkeypatch):
    """A provider without a tick_size method (shouldn't happen for the real
    KiteProvider, but keep the wiring defensive) must not blow up make_broker —
    KiteOrderClient's own fallback then covers every trigger with 0.05."""
    import types
    monkeypatch.setenv("PT_EXECUTION", "live")
    monkeypatch.setenv("PT_LIVE_ACK", "I_UNDERSTAND_REAL_MONEY")
    init_db(reset=True)
    prov = MockProvider()
    prov.name = "kite"
    prov.access_token = "tok"
    assert not hasattr(prov, "tick_size")
    monkeypatch.setattr("app.providers.live_kite.LiveExecutionKite",
                        lambda **k: types.SimpleNamespace(set_access_token=lambda t: None))
    captured = {}

    def fake_client(kite, **kw):
        captured.update(kw)
        return object()

    monkeypatch.setattr("app.engine.kite_order_client.KiteOrderClient", fake_client)
    monkeypatch.setattr("app.engine.live_broker.LiveBroker", lambda *a, **k: "LB")
    assert make_broker(prov) == "LB"
    assert captured["tick_source"] is None


def test_live_gate_reads_dotenv_via_settings(monkeypatch):
    """The flags must work from .env (Settings), not only a shell export — so the
    owner controls live mode from one file with no per-session exports. Simulate the
    .env-backed Settings with NO matching OS env var present."""
    from app.core.config import get_settings
    monkeypatch.delenv("PT_EXECUTION", raising=False)
    monkeypatch.delenv("PT_LIVE_ACK", raising=False)
    s = get_settings()
    monkeypatch.setattr(s, "execution", "live")
    monkeypatch.setattr(s, "live_ack", "I_UNDERSTAND_REAL_MONEY")
    assert live_execution_enabled() is True
    monkeypatch.setattr(s, "live_ack", "wrong")     # ack must match exactly
    assert live_execution_enabled() is False
