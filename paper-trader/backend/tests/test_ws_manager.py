"""WS broadcast hub — the 2026-07-23 outage fix.

The old manager sent to every client inline (one slow client stalled the engine
callbacks) and spawned a fire-and-forget coroutine per log line
(run_coroutine_threadsafe), so a stalled/slow dashboard client made snapshots
pile up unboundedly: RSS +100MB/min with the dashboard open, OOM on the 1GB VPS.

New contract, encoded here:
  - broadcast()/push() never block on client I/O — they enqueue and return
  - "state"/"position_ticks" coalesce latest-wins (stale snapshots dropped)
  - log lines sit in a bounded per-client buffer (oldest dropped)
  - a client that can't take a send within SEND_TIMEOUT is evicted
  - push() from a foreign thread must not create one task per message
  - a message is JSON-encoded ONCE per broadcast, not once per client, and the
    bytes on the wire stay identical to what starlette's send_json produced
  - encoding stays inside the sender's try/except: a message that cannot be
    serialised evicts clients, it never raises into the producer (engine loop)
"""
import asyncio
import json
import threading
import time

from starlette.websockets import WebSocket

from app.ws.manager import WSManager


CHANNEL = ("test-org", "test-account")


class FakeWS:
    """Stand-in for a starlette WebSocket. block=True simulates a dead-slow
    client whose TCP window is full: the send never completes.

    The manager now sends pre-encoded text, so this double takes `send_text`
    and decodes it back — `sent` therefore still holds dicts for the tests that
    assert on message content, but nothing here can invent a payload the real
    starlette consumer would not have seen. The byte-level contract is pinned
    separately by test_wire_bytes_match_starlette_send_json, which uses a REAL
    starlette WebSocket rather than this double."""

    def __init__(self, block: bool = False):
        self.sent_text: list[str] = []
        self.block = block
        self.closed = False

    @property
    def sent(self) -> list[dict]:
        return [json.loads(t) for t in self.sent_text]

    async def accept(self):
        pass

    async def send_text(self, text):
        assert isinstance(text, str), f"send_text got {type(text).__name__}, not str"
        if self.block:
            await asyncio.Event().wait()  # never set — hangs forever
        self.sent_text.append(text)

    async def close(self, code: int = 1000):
        self.closed = True


def _real_ws(captured: list[dict]) -> WebSocket:
    """A genuine starlette WebSocket whose ASGI output is captured verbatim."""

    async def receive():
        return {"type": "websocket.connect"}

    async def send(message):
        captured.append(message)

    return WebSocket({"type": "websocket", "path": "/ws", "headers": []}, receive, send)


def _mgr() -> WSManager:
    m = WSManager()
    m.bind(asyncio.get_event_loop())
    return m


# ── serialise-once fan-out (backend-hardening 2026-08-08 §11) ───────────────
def test_wire_bytes_match_starlette_send_json():
    """The ASGI frame the manager produces must be identical to the one
    starlette's own send_json would have produced for the same message."""
    msg = {
        "type": "state",
        "data": {
            "NIFTY 50": {"ltp": 24_512.35, "chg": -0.42, "_ratchet_atr": None},
            "unicode": "₹ Ø 日本",
            "nested": [1, 2.5, True, None],
        },
    }

    async def run():
        via_manager: list[dict] = []
        m = _mgr()
        ws = _real_ws(via_manager)
        await m.connect(ws, channel=CHANNEL)
        await m.broadcast(CHANNEL, msg)
        await asyncio.sleep(0.05)

        via_starlette: list[dict] = []
        ref = _real_ws(via_starlette)
        await ref.accept()
        await ref.send_json(msg)
        return via_manager, via_starlette

    via_manager, via_starlette = asyncio.run(run())
    sends_m = [x for x in via_manager if x["type"] == "websocket.send"]
    sends_s = [x for x in via_starlette if x["type"] == "websocket.send"]
    assert len(sends_m) == 1, f"expected one send frame, got {sends_m}"
    assert sends_m == sends_s, (
        f"wire frame diverged from starlette send_json\n"
        f"  manager:   {sends_m}\n  send_json: {sends_s}"
    )


def test_message_is_encoded_once_regardless_of_client_count():
    """One broadcast to N clients must cost exactly one json.dumps.

    json.dumps is patched on the json module itself, so this counts encoding
    wherever it happens — in the manager or inside starlette's send_json.
    """
    n_clients = 5
    calls = []
    real_dumps = json.dumps

    def counting_dumps(obj, *a, **kw):
        calls.append(obj)
        return real_dumps(obj, *a, **kw)

    async def run():
        m = _mgr()
        for _ in range(n_clients):
            await m.connect(_real_ws([]), channel=CHANNEL)
        assert m.client_count() == n_clients
        json.dumps = counting_dumps
        try:
            await m.broadcast(CHANNEL, {"type": "state", "data": {"i": 1}})
            await asyncio.sleep(0.1)
        finally:
            json.dumps = real_dumps
        return len(calls)

    n_encodes = asyncio.run(run())
    assert n_encodes == 1, (
        f"{n_encodes} json.dumps calls for one message to {n_clients} clients "
        f"— the payload is being re-encoded per client"
    )


def test_unserialisable_message_evicts_clients_and_never_reaches_producer():
    """Encoding must stay lazy, inside the sender's try/except.

    If it moved into _enqueue (a producer context — the engine tick loop and
    call_soon_threadsafe from the log bus) an unserialisable message would
    raise into the engine instead of costing the offending clients.
    """

    class Unserialisable:
        pass

    bad = {"type": "state", "data": {"x": Unserialisable()}}

    async def run():
        m = _mgr()
        a, b = FakeWS(), FakeWS()
        await m.connect(a, channel=CHANNEL)
        await m.connect(b, channel=CHANNEL)
        await m.broadcast(CHANNEL, bad)  # must not raise here
        await asyncio.sleep(0.1)
        clients_after_broadcast = m.client_count()

        errors: list[BaseException] = []
        m2 = _mgr()
        asyncio.get_running_loop().set_exception_handler(
            lambda loop, ctx: errors.append(ctx.get("exception") or RuntimeError(ctx["message"]))
        )
        await m2.connect(FakeWS(), channel=CHANNEL)
        threading.Thread(target=lambda: m2.push(CHANNEL, bad)).start()
        await asyncio.sleep(0.2)
        return clients_after_broadcast, errors

    clients_after, loop_errors = asyncio.run(run())
    assert clients_after == 0, "unserialisable message did not evict its clients"
    assert loop_errors == [], (
        f"serialisation error escaped into the producer/loop callback: {loop_errors}"
    )


def test_broadcast_does_not_block_on_slow_client():
    async def run():
        m = _mgr()
        stuck = FakeWS(block=True)
        await m.connect(stuck, channel=CHANNEL)
        t0 = time.monotonic()
        for i in range(50):
            await m.broadcast(CHANNEL, {"type": "state", "data": {"i": i}})
        return time.monotonic() - t0

    elapsed = asyncio.run(run())
    assert elapsed < 0.5, f"broadcast blocked on a stuck client ({elapsed:.2f}s)"


def test_state_snapshots_coalesce_latest_wins():
    async def run():
        m = _mgr()
        ws = FakeWS()
        await m.connect(ws, channel=CHANNEL)
        # 100 snapshots enqueued back-to-back with no yield between them:
        # the sender must deliver the newest, not the whole backlog.
        for i in range(100):
            await m.broadcast(CHANNEL, {"type": "state", "data": {"i": i}})
        await asyncio.sleep(0.1)
        return ws.sent

    sent = asyncio.run(run())
    states = [s for s in sent if s["type"] == "state"]
    assert len(states) < 100, "stale snapshots were not coalesced"
    assert states[-1]["data"]["i"] == 99, "latest snapshot must win"


def test_log_buffer_is_bounded_for_stuck_client():
    async def run():
        m = _mgr()
        stuck = FakeWS(block=True)
        await m.connect(stuck, channel=CHANNEL)
        for i in range(5000):
            await m.broadcast(CHANNEL, {"type": "log", "data": {"i": i}})
        # whatever the internal representation, total buffered messages for the
        # client must be bounded well below what was enqueued
        return m.pending_count(stuck)

    pending = asyncio.run(run())
    assert pending <= WSManager.LOG_BUFFER + 2, (
        f"{pending} messages buffered for a stuck client — unbounded growth"
    )


def test_slow_client_is_evicted_and_others_keep_receiving():
    async def run():
        m = _mgr()
        m.SEND_TIMEOUT = 0.1
        stuck, healthy = FakeWS(block=True), FakeWS()
        await m.connect(stuck, channel=CHANNEL)
        await m.connect(healthy, channel=CHANNEL)
        await m.broadcast(CHANNEL, {"type": "state", "data": {"i": 0}})
        await asyncio.sleep(0.5)  # > SEND_TIMEOUT — stuck client must be gone
        await m.broadcast(CHANNEL, {"type": "state", "data": {"i": 1}})
        await asyncio.sleep(0.1)
        return m.client_count(), healthy.sent

    n_clients, healthy_sent = asyncio.run(run())
    assert n_clients == 1, "stuck client was not evicted"
    assert any(s["data"]["i"] == 1 for s in healthy_sent), (
        "healthy client stopped receiving after the stuck one was evicted"
    )


def test_push_from_thread_does_not_flood_the_loop_with_tasks():
    async def run():
        m = _mgr()
        stuck = FakeWS(block=True)
        await m.connect(stuck, channel=CHANNEL)

        def hammer():
            for i in range(1000):
                m.push(CHANNEL, {"type": "log", "data": {"i": i}})

        t = threading.Thread(target=hammer)
        t.start()
        await asyncio.to_thread(t.join)
        await asyncio.sleep(0.2)  # let the callbacks drain
        return len(asyncio.all_tasks()), m.pending_count(stuck)

    n_tasks, pending = asyncio.run(run())
    # old code: one run_coroutine_threadsafe coroutine per log line → ~1000
    assert n_tasks < 20, f"{n_tasks} tasks on the loop — per-message coroutine flood"
    assert pending <= WSManager.LOG_BUFFER + 2


def test_disconnect_stops_sender_and_forgets_client():
    async def run():
        m = _mgr()
        ws = FakeWS()
        await m.connect(ws, channel=CHANNEL)
        m.disconnect(ws)
        await m.broadcast(CHANNEL, {"type": "state", "data": {"i": 0}})
        await asyncio.sleep(0.05)
        return m.client_count(), ws.sent

    n, sent = asyncio.run(run())
    assert n == 0
    assert sent == []
