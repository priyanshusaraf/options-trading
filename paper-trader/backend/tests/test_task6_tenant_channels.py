"""Task 6 regression proofs for tenant WebSocket delivery."""
import asyncio
import json
from types import SimpleNamespace

from app.api import principal as principal_api
from app.api import routes
from app.api.principal import Principal
from app.events.delivery import ResumeCursorCodec
from app.events.outbox import PrincipalScope
from fastapi import HTTPException
from app.ws.manager import PUBLIC_MARKET, WSManager


class FakeWS:
    def __init__(self):
        self.sent_text: list[str] = []
        self.closed = False

    async def accept(self):
        pass

    async def send_text(self, text):
        self.sent_text.append(text)

    async def close(self, code=1000):
        self.closed = True

    @property
    def sent(self):
        return [json.loads(frame) for frame in self.sent_text]


def test_private_delivery_must_not_cross_organization_or_account_dimensions():
    async def run():
        manager = WSManager()
        manager.bind(asyncio.get_running_loop())
        a1, a2, b1 = FakeWS(), FakeWS(), FakeWS()
        await manager.connect(a1, channel=("org-a", "account-1"))
        await manager.connect(a2, channel=("org-a", "account-2"))
        await manager.connect(b1, channel=("org-b", "account-1"))
        await manager.broadcast(("org-a", "account-1"), {"type": "state", "data": {"marker": "a1"}})
        await asyncio.sleep(0.02)
        return a1.sent, a2.sent, b1.sent

    a1, a2, b1 = asyncio.run(run())
    assert [frame["data"]["marker"] for frame in a1] == ["a1"]
    assert a2 == [], "same organization / different account received private state"
    assert b1 == [], "different organization / matching account received private state"


def test_public_market_requires_an_explicit_subscription():
    async def run():
        manager = WSManager()
        manager.bind(asyncio.get_running_loop())
        private, public = FakeWS(), FakeWS()
        await manager.connect(private, channel=("org-a", "account-1"))
        await manager.connect(public, channel=PUBLIC_MARKET)
        await manager.broadcast(PUBLIC_MARKET, {"type": "quote", "data": {"symbol": "NIFTY"}})
        await asyncio.sleep(0.02)
        return private.sent, public.sent

    private, public = asyncio.run(run())
    assert private == []
    assert [frame["type"] for frame in public] == ["quote"]


def test_two_tenant_fanout_serializes_once_and_leaves_other_pending_empty(monkeypatch):
    async def run():
        manager = WSManager()
        manager.bind(asyncio.get_running_loop())
        a_clients = [FakeWS() for _ in range(250)]
        b_clients = [FakeWS() for _ in range(250)]
        for ws in a_clients:
            await manager.connect(ws, channel=("org-a", "account-1"))
        for ws in b_clients:
            await manager.connect(ws, channel=("org-b", "account-1"))
        calls = []
        real_dumps = json.dumps

        def counted_dumps(*args, **kwargs):
            calls.append(args[0])
            return real_dumps(*args, **kwargs)

        monkeypatch.setattr(json, "dumps", counted_dumps)
        await manager.broadcast(("org-a", "account-1"),
                                {"type": "state", "data": {"marker": "a"}})
        await asyncio.sleep(0.05)
        return calls, a_clients, b_clients, [manager.pending_count(ws) for ws in b_clients]

    calls, a_clients, b_clients, b_pending = asyncio.run(run())
    assert len(calls) == 1
    assert all(ws.sent[-1]["data"]["marker"] == "a" for ws in a_clients)
    assert all(ws.sent == [] for ws in b_clients)
    assert b_pending == [0] * 250


def test_main_socket_missing_execution_scope_closes_before_local_cell(monkeypatch):
    ws = SimpleNamespace(state=SimpleNamespace(), close_codes=[])

    async def close(code=1000):
        ws.close_codes.append(code)

    ws.close = close
    denied = Principal(id="user-a", kind="user", scopes=frozenset(), user_id="user-a",
                       organization_id="org-a", role="viewer")

    async def authenticate(_):
        return denied

    monkeypatch.setattr(principal_api, "authenticate_websocket", authenticate)
    monkeypatch.setattr(routes, "local_execution_cell",
                        lambda *_: (_ for _ in ()).throw(AssertionError("local cell read")))
    asyncio.run(routes.ws_main(ws))
    assert ws.close_codes == [1008]


def test_instrument_socket_missing_execution_scope_closes_before_price_work(monkeypatch):
    ws = SimpleNamespace(state=SimpleNamespace(), close_codes=[])

    async def close(code=1000):
        ws.close_codes.append(code)

    ws.close = close
    denied = Principal(id="user-a", kind="user", scopes=frozenset(), user_id="user-a",
                       organization_id="org-a", role="viewer")

    async def authenticate(_):
        return denied

    monkeypatch.setattr(principal_api, "authenticate_websocket", authenticate)
    monkeypatch.setattr(routes, "local_execution_cell",
                        lambda *_: (_ for _ in ()).throw(AssertionError("position/provider read")))
    asyncio.run(routes.ws_instrument(ws, "NIFTY"))
    assert ws.close_codes == [1008]


def test_foreign_main_socket_closes_before_snapshot_or_manager_registration(monkeypatch):
    ws = SimpleNamespace(state=SimpleNamespace(), close_codes=[])

    async def close(code=1000): ws.close_codes.append(code)
    async def authenticate(_): return Principal(id="owner", kind="owner", scopes=frozenset({"*"}))
    ws.close = close
    monkeypatch.setattr(principal_api, "authenticate_websocket", authenticate)
    monkeypatch.setattr(routes, "local_execution_cell",
                        lambda *_: (_ for _ in ()).throw(HTTPException(404, "execution unavailable")))
    monkeypatch.setattr(routes.manager, "connect",
                        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("manager registration")))
    asyncio.run(routes.ws_main(ws))
    assert ws.close_codes == [1008]


def test_foreign_instrument_socket_closes_before_position_or_price_work(monkeypatch):
    ws = SimpleNamespace(state=SimpleNamespace(), close_codes=[])

    async def close(code=1000): ws.close_codes.append(code)
    async def authenticate(_): return Principal(id="owner", kind="owner", scopes=frozenset({"*"}))
    ws.close = close
    monkeypatch.setattr(principal_api, "authenticate_websocket", authenticate)
    monkeypatch.setattr(routes, "local_execution_cell",
                        lambda *_: (_ for _ in ()).throw(HTTPException(404, "execution unavailable")))
    monkeypatch.setattr(routes, "_instrument_payload",
                        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("price/position work")))
    asyncio.run(routes.ws_instrument(ws, "NIFTY"))
    assert ws.close_codes == [1008]


def test_main_socket_rejects_foreign_cursor_before_outbox_read_or_registration(monkeypatch):
    codec = ResumeCursorCodec(b"w" * 32)
    foreign = codec.encode(
        plane="execution", scope=PrincipalScope("other-owner", "account-1"), offset=4)
    ws = SimpleNamespace(
        state=SimpleNamespace(), close_codes=[], query_params={"cursor": foreign},
        app=SimpleNamespace(state=SimpleNamespace(event_cursor_codec=codec)))

    async def close(code=1000): ws.close_codes.append(code)
    async def authenticate(_):
        return Principal(id="owner", kind="owner", scopes=frozenset({"*"}),
                         user_id="owner-user", organization_id="owner", role="owner")
    ws.close = close
    monkeypatch.setattr(principal_api, "authenticate_websocket", authenticate)
    monkeypatch.setattr(routes, "local_execution_cell", lambda *_: SimpleNamespace(
        owner_id="owner", broker_account_id="account-1",
        snapshot_state=lambda: (_ for _ in ()).throw(AssertionError("snapshot read"))))
    monkeypatch.setattr("app.events.planes.execution_outbox", lambda: (
        _ for _ in ()).throw(AssertionError("invalid cursor reached outbox read")))
    monkeypatch.setattr(routes.manager, "connect",
                        lambda *_a, **_k: (_ for _ in ()).throw(
                            AssertionError("invalid socket registered")))
    asyncio.run(routes.ws_main(ws))
    assert ws.close_codes == [1008]
