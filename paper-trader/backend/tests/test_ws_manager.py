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
"""
import asyncio
import threading
import time

from app.ws.manager import WSManager


class FakeWS:
    """Stand-in for a starlette WebSocket. block=True simulates a dead-slow
    client whose TCP window is full: send_json never completes."""

    def __init__(self, block: bool = False):
        self.sent: list[dict] = []
        self.block = block
        self.closed = False

    async def accept(self):
        pass

    async def send_json(self, msg):
        if self.block:
            await asyncio.Event().wait()  # never set — hangs forever
        self.sent.append(msg)

    async def close(self, code: int = 1000):
        self.closed = True


def _mgr() -> WSManager:
    m = WSManager()
    m.bind(asyncio.get_event_loop())
    return m


def test_broadcast_does_not_block_on_slow_client():
    async def run():
        m = _mgr()
        stuck = FakeWS(block=True)
        await m.connect(stuck)
        t0 = time.monotonic()
        for i in range(50):
            await m.broadcast({"type": "state", "data": {"i": i}})
        return time.monotonic() - t0

    elapsed = asyncio.run(run())
    assert elapsed < 0.5, f"broadcast blocked on a stuck client ({elapsed:.2f}s)"


def test_state_snapshots_coalesce_latest_wins():
    async def run():
        m = _mgr()
        ws = FakeWS()
        await m.connect(ws)
        # 100 snapshots enqueued back-to-back with no yield between them:
        # the sender must deliver the newest, not the whole backlog.
        for i in range(100):
            await m.broadcast({"type": "state", "data": {"i": i}})
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
        await m.connect(stuck)
        for i in range(5000):
            await m.broadcast({"type": "log", "data": {"i": i}})
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
        await m.connect(stuck)
        await m.connect(healthy)
        await m.broadcast({"type": "state", "data": {"i": 0}})
        await asyncio.sleep(0.5)  # > SEND_TIMEOUT — stuck client must be gone
        await m.broadcast({"type": "state", "data": {"i": 1}})
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
        await m.connect(stuck)

        def hammer():
            for i in range(1000):
                m.push({"type": "log", "data": {"i": i}})

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
        await m.connect(ws)
        m.disconnect(ws)
        await m.broadcast({"type": "state", "data": {"i": 0}})
        await asyncio.sleep(0.05)
        return m.client_count(), ws.sent

    n, sent = asyncio.run(run())
    assert n == 0
    assert sent == []
