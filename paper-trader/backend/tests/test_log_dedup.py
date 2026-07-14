"""Fix E (2026-07-14): collapse a repeating failure into ONE warning per outage
episode. The 2026-07-13 run logged `margins() failed: Incorrect api_key` 3,156 times
(a pre-market token-expired blip re-warned every poll), burying real events in the
800-entry live-log ring buffer. WarnGate warns once, notes recovery, and re-arms for
the next distinct episode."""
from app.core.logging import WarnGate, log


def _warns(needle):
    return [e for e in log.recent(5000)
            if e["level"] == "WARNING" and needle in e["msg"]]


def test_repeat_failures_warn_once_until_recovery():
    g = WarnGate()
    tag = "margins() failed [dedup-test-A]"
    for _ in range(5):
        g.fail("margins", tag)
    assert len(_warns(tag)) == 1                 # 5 failures → 1 warning

    g.ok("margins")                              # recovered — re-arm
    for _ in range(5):
        g.fail("margins", tag)
    assert len(_warns(tag)) == 2                 # a fresh episode warns again (once)


def test_recovery_emits_an_info_once():
    g = WarnGate()
    g.fail("funds", "funds down [dedup-test-B]")
    g.ok("funds", "funds recovered [dedup-test-B]")
    g.ok("funds", "funds recovered [dedup-test-B]")   # no-op — already clear
    infos = [e for e in log.recent(5000)
             if e["level"] == "INFO" and "funds recovered [dedup-test-B]" in e["msg"]]
    assert len(infos) == 1


def test_distinct_keys_are_independent():
    g = WarnGate()
    g.fail("k1", "k1 down [dedup-test-C]")
    g.fail("k2", "k2 down [dedup-test-C]")
    assert len(_warns("k1 down [dedup-test-C]")) == 1
    assert len(_warns("k2 down [dedup-test-C]")) == 1


def test_ring_buffer_holds_more_than_the_old_800():
    assert log._buf.maxlen >= 4000
