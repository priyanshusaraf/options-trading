"""Phase 2: notifier formatting + the approaching-SL/TP throttle, and the
Telegram sender being a safe no-op when unconfigured."""
from app.notify.notifier import Notifier


class FakeSender:
    def __init__(self):
        self.sent = []

    def __call__(self, text):
        self.sent.append(text)
        return True


def test_proximity_fires_once_then_rearms_on_leaving():
    f = FakeSender()
    n = Notifier(sender=f)
    # comfortably inside the band -> nothing
    n.check_proximity("NIFTY", "SYM", premium=200, stop=100, target=300, proximity_pct=0.10)
    assert f.sent == []
    # within 10% above the stop -> exactly one alert
    n.check_proximity("NIFTY", "SYM", premium=105, stop=100, target=300, proximity_pct=0.10)
    assert len(f.sent) == 1 and "STOP" in f.sent[0]
    # still near the stop -> no repeat (throttled)
    n.check_proximity("NIFTY", "SYM", premium=104, stop=100, target=300, proximity_pct=0.10)
    assert len(f.sent) == 1
    # premium recovers out of the zone -> re-arm
    n.check_proximity("NIFTY", "SYM", premium=200, stop=100, target=300, proximity_pct=0.10)
    # drops back near the stop -> fires again
    n.check_proximity("NIFTY", "SYM", premium=105, stop=100, target=300, proximity_pct=0.10)
    assert len(f.sent) == 2


def test_proximity_target_side():
    f = FakeSender()
    n = Notifier(sender=f)
    # within 10% below the target (>= 270) -> a TARGET alert
    n.check_proximity("X", "SYM", premium=285, stop=100, target=300, proximity_pct=0.10)
    assert len(f.sent) == 1 and "TARGET" in f.sent[0]


def test_clear_resets_proximity_state():
    f = FakeSender()
    n = Notifier(sender=f)
    n.check_proximity("X", "SYM", premium=105, stop=100, target=300, proximity_pct=0.10)
    assert len(f.sent) == 1
    n.clear("X")                       # position closed -> forget its near-state
    n.check_proximity("X", "SYM", premium=105, stop=100, target=300, proximity_pct=0.10)
    assert len(f.sent) == 2            # fires again after clear


def test_sender_failure_never_propagates():
    def boom(_text):
        raise RuntimeError("network down")
    n = Notifier(sender=boom)
    # must not raise — a dead notifier can never take down the engine
    n.check_proximity("X", "SYM", premium=105, stop=100, target=300, proximity_pct=0.10)


def test_telegram_send_noop_without_creds(monkeypatch):
    from app.notify import telegram
    monkeypatch.setattr(telegram, "_creds", lambda: ("", ""))
    assert telegram.send("hi") is False   # no creds -> no-op, returns False, no raise
