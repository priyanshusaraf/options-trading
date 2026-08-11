"""
LiveBroker — places REAL Kite orders, books the ACTUAL fill into the same ledger
as the paper broker, and enforces the position-ownership boundary so it can never
touch the owner's own positions.

Subclasses PaperBroker: every bit of ledger / accounting / mark / snapshot /
reconcile logic is reused unchanged — only the FILL mechanism changes. open/close
return None on any non-fill (rejected / partial / timeout) OR an ownership block,
so the engine keeps managing the position and alerts instead of assuming a fill.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import replace

from sqlalchemy import select

from app.core.instruments import get_instrument
from app.core.logging import log
from app.core.runtime_config import effective
from app.db.models import (
    Deployment,
    ExecutionIntent,
    ExecutionOrderEvent,
    LEGACY_DEPLOYMENT_ID,
    LEGACY_OWNER_ID,
    OrderJournal,
    Position,
)
from app.core.config import get_settings
from app.engine.broker import PaperBroker
from app.engine.charges import compute_charges, legs_for
from app.engine.equity_entry import equity_stop_target
from app.engine.execution_policy import plan_order, plan_reference_entry
from app.engine.gtt import round_to_tick
from app.engine.broker_protocol import (
    ProtectiveStopKind,
    clear_protective_order_id,
    protective_order_id,
    set_protective_order_id,
)
from app.providers.base import OptionQuote
from app.engine.execution_lifecycle import (
    ExecutionLifecycleStore,
    NewExecutionEvent,
    NewExecutionIntent,
    broker_observation_id,
    make_broker_tag,
)
from app.engine.kite_order_client import PreWireProtectionRejected, is_strategy_os_tag
from app.engine.order_executor import OrderRequest, OrderResult, execute_order
from app.engine.reconcile import can_bot_close
from app.engine.venue import (
    protective_kind_for_book_segment,
    tenor_for_charge_segment,
)
from app.providers.connection import (
    KITE_LEGACY_CONNECTION_SCOPE as _KITE_LEGACY_CONNECTION_SCOPE,
    Connection,
    connection_for,
)

TAG = "pt-bot"  # protective stops and legacy orders retain their historical tag
# Re-exported, not redefined: `app/providers/connection.py` owns the constant now that a
# connection is a real object. Kept under this name because three modules and several tests
# import it from here, and because every pre-seam `ExecutionIntent` row carries this value.
KITE_LEGACY_CONNECTION_SCOPE = _KITE_LEGACY_CONNECTION_SCOPE

# Kite order statuses that mean the order is dead (no working order left at the
# exchange). Anything else that is not a terminal fill is treated as possibly-working.
_DEAD_STATUSES = frozenset({"REJECTED", "CANCELLED"})


class LiveBroker(PaperBroker):
    MODE = "live"   # every fill this broker books is a REAL trade — tagged so the log never mixes it with paper

    def __init__(self, provider, order_client, *, poll_seconds: float = 0.5,
                 timeout_seconds: float = 30.0, notifier=None,
                 deployment_id: int = LEGACY_DEPLOYMENT_ID,
                 owner_id: str, broker_account_id: str,
                 lifecycle_clock=None, connection: Connection | None = None,
                 venue=None) -> None:
        super().__init__(provider, deployment_id=deployment_id,
                         owner_id=owner_id,
                         broker_account_id=broker_account_id)
        self.client = order_client
        # The wire seam. Every protective-stop call goes through here, so this broker
        # asks for a RESTING_STOP or a SERVER_TRIGGER and never for an SL-M or a GTT —
        # the venue owns that spelling. Defaulting to `KiteVenue` keeps every existing
        # caller (and every test holding a fake Kite client) working unchanged: the
        # adapter is a pure delegator, so wrapping a fake changes nothing it observes.
        # `broker_factory` passes one explicitly; a second broker supplies its own.
        if venue is None:
            from app.engine.kite_venue import KiteVenue
            venue = KiteVenue(order_client)
        self.venue = venue
        # Which credential these orders go through. Written into every ExecutionIntent and
        # matched by the restart-recovery query, so it decides which unresolved entries this
        # broker may adopt. Defaults to the legacy derivation — the data provider serving as
        # its own execution connection — which is what production runs today.
        self.connection = connection or connection_for(provider)
        # Whose money this broker moves. Stamped onto every ExecutionIntent and matched by the
        # restart-recovery query, so it decides which unresolved live entries this broker may
        # adopt. One owner today; the dimension exists so a second is a configuration rather
        # than a migration of the money record.
        self.owner_id = owner_id
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds
        self.notifier = notifier
        self.lifecycle_clock = lifecycle_clock or dt.datetime.now
        # tradingsymbol -> order id of an order that TIMED OUT while possibly still
        # working at the exchange. Before placing a NEW order for that contract we
        # cancel/await it, so a contract never has two working bot orders at once
        # (the timed-out-but-still-working double-send / oversell residual).
        self._inflight: dict[str, str] = {}
        # instrument_key -> count of CONSECUTIVE reconcile reads showing it orphaned.
        # A position is booked closed only once this reaches orphan_confirm_count, so a
        # single transient account-feed glitch can't phantom-close a live position (L8).
        self._orphan_seen: dict[str, int] = {}
        # tradingsymbol -> context for a bot ENTRY order that timed out with no confirmed
        # fill. It may still fill later (a pre-open uncross, a slow open); the reconcile
        # sweep re-queries it and ADOPTS a confirmed fill into the book (+stop) rather than
        # leaving an untracked, stopless orphan — the BSE 2026-07-03 incident (#17).
        self._pending_entries: dict[str, dict] = {}
        # #14: CONSECUTIVE zero-fill order outcomes. Systemic failures (expired token,
        # IP not whitelisted, margin exhausted) kill every order the same way; the
        # runner disarms once this reaches order_failure_disarm_count. Any real fill
        # resets it, as does a deliberate re-arm.
        self.order_fail_streak: int = 0

    def _notify(self, text: str) -> None:
        if self.notifier:
            try:
                self.notifier._emit(text)
            except Exception as e:
                # L11 — a money-critical alert that fails to send must never vanish
                # silently; at least record it (with the dropped text) so it's visible
                # in the Engine/Logs console even when Telegram is down.
                log.error(f"ALERT NOT DELIVERED ({e}): {text}", event="NOTIFY_FAIL")

    def _execute(self, req: OrderRequest, *, intent: str = "", kind: str = "", context=None):
        """Place a real order, JOURNAL it (H13), and return (res, filled, avg). The
        journal row is WORKING before placement, stamped with the order id the instant
        placement acks, and marked TERMINAL on resolution — so a crash in the poll
        window is recoverable on restart. ALL journal I/O is non-fatal: a journal
        write must never block or fail a real order/exit."""
        row_id = self._journal_open(req, intent, kind, context)
        on_placed = (lambda oid: self._journal_set_order_id(row_id, oid)) if row_id else None
        res = execute_order(self.client, req, poll_seconds=self.poll_seconds,
                            timeout_seconds=self.timeout_seconds, on_placed=on_placed)
        filled, avg = self._actual_fill(res)
        self._journal_resolve(row_id, res, filled, avg)
        return res, filled, avg

    def _execute_entry(
        self,
        req: OrderRequest,
        *,
        kind: str,
        context: dict,
        now: dt.datetime,
        decision_price: float | None,
        strategy_key: str | None,
        strategy_version: str | None,
    ):
        """Persist an entry identity before submitting exactly one real order.

        Any failure before ``execute_order`` propagates and therefore refuses the
        submit. A persistence failure after placement returns the known broker order
        id with reconciliation required and assumes no fill.
        """
        deployment = self.s.scalar(select(Deployment).where(
            Deployment.id == self.deployment_id,
            Deployment.owner_id == self.owner_id,
            Deployment.broker_account_id == self.broker_account_id,
        ))
        if deployment is None:
            raise LookupError(f"unknown deployment {self.deployment_id}")

        store = ExecutionLifecycleStore(
            self.s, owner_id=self.owner_id,
            broker_account_id=self.broker_account_id)
        durable_context = dict(context or {})
        intent_row = store.create_intent(
            NewExecutionIntent(
                deployment_id=self.deployment_id,
                owner_id=self.owner_id,
                broker_account_id=self.broker_account_id,
                broker=self.connection.broker,
                account_scope=self.account.external_account_id,
                connection_scope=self.connection.scope,
                intent="ENTRY",
                instrument_key=durable_context.get("inst_key", ""),
                tradingsymbol=req.tradingsymbol,
                exchange=req.exchange,
                side=req.side,
                product=req.product,
                order_type=req.order_type,
                requested_qty=req.qty,
                limit_price=req.limit_price,
                decision_price=decision_price,
                signal_at=now,
                strategy_key=strategy_key,
                strategy_version=strategy_version,
                context=durable_context,
            ),
            durable_context,
            self.lifecycle_clock(),
        )
        client_intent_id = intent_row.client_intent_id
        tagged_req = replace(req, tag=intent_row.broker_tag)
        store.append_event(
            client_intent_id,
            NewExecutionEvent(
                source="engine",
                source_event_id="submit-started",
                kind="SUBMIT_STARTED",
                broker_order_id=None,
                broker_status="",
                cumulative_filled_qty=0,
                avg_price=0.0,
                payload={"broker_tag": intent_row.broker_tag},
            ),
            self.lifecycle_clock(),
        )

        journal_context = dict(durable_context, client_intent_id=client_intent_id)
        row_id = self._journal_open(tagged_req, "ENTRY", kind, journal_context)

        def persist_ack(order_id: str) -> None:
            if row_id:
                self._journal_set_order_id(row_id, order_id)
            store.append_event(
                client_intent_id,
                NewExecutionEvent(
                    source="broker",
                    source_event_id=f"ack:{order_id}",
                    kind="ACKNOWLEDGED",
                    broker_order_id=str(order_id),
                    broker_status="",
                    cumulative_filled_qty=0,
                    avg_price=0.0,
                    payload={"order_id": str(order_id)},
                ),
                self.lifecycle_clock(),
            )

        res = execute_order(
            self.client,
            tagged_req,
            poll_seconds=self.poll_seconds,
            timeout_seconds=self.timeout_seconds,
            on_placed=persist_ack,
        )
        filled, avg = self._actual_fill(res)
        status_payload = {
            "status": res.status,
            "filled_qty": filled,
            "avg_price": avg,
            "reason": res.reason,
            "reconciliation_required": res.reconciliation_required,
        }
        broker_status = "COMPLETE" if res.status == "FILLED" else res.status
        if res.status == "PARTIAL" and "cancelled" in (res.reason or "").lower():
            broker_status = "CANCELLED"
        try:
            store.append_event(
                client_intent_id,
                NewExecutionEvent(
                    source="broker",
                    source_event_id=broker_observation_id(
                        str(res.order_id or client_intent_id), status_payload),
                    kind="STATUS_OBSERVED",
                    broker_order_id=str(res.order_id) if res.order_id is not None else None,
                    broker_status=broker_status,
                    cumulative_filled_qty=filled,
                    avg_price=avg,
                    payload=status_payload,
                ),
                self.lifecycle_clock(),
            )
        except Exception as e:
            res = OrderResult(
                "ERROR", res.order_id, 0, 0.0,
                f"status observation persistence failed: {e}",
                reconciliation_required=True,
            )
            filled, avg = 0, 0.0
        if filled <= 0 and not res.reconciliation_required:
            self._journal_resolve(row_id, res, filled, avg)
        return res, filled, avg, client_intent_id, row_id

    def _prepare_entry_request(self, req: OrderRequest) -> OrderRequest:
        """Freeze the exact venue-valid limit before durable intent creation.

        The venue adapter also rounds defensively at send time. Doing the same here is
        required because the immutable intent must describe the order actually sent,
        including instruments whose exchange tick is coarser than the planner's grid.
        """
        if req.order_type != "LIMIT":
            return req
        if req.limit_price is None:
            raise ValueError("LIMIT entry requires limit_price")
        tick_fn = getattr(self.client, "tick_size", None)
        try:
            tick = float(tick_fn(req.tradingsymbol, req.exchange)) if tick_fn else 0.05
        except Exception:
            tick = 0.05
        return replace(req, limit_price=round_to_tick(req.limit_price, tick))

    def _mark_position_booked(self, client_intent_id: str, row_id: int | None,
                              pos: Position, res, filled: int, avg: float) -> bool:
        """Close the durable broker-to-ledger gap after the Position commit."""
        if ExecutionLifecycleStore(self.s, owner_id=self.owner_id,
                                   broker_account_id=self.broker_account_id).state_for(
                client_intent_id).protected_qty < pos.qty:
            log.error(
                f"position booking refused for {pos.tradingsymbol}: protection is not "
                f"durable for qty {pos.qty}", event="LIFECYCLE_FAIL")
            return False
        source_event_id = f"position:{pos.id}:{pos.qty}"
        existing = self.s.scalar(select(ExecutionOrderEvent).where(
            ExecutionOrderEvent.client_intent_id == client_intent_id,
            ExecutionOrderEvent.owner_id == self.owner_id,
            ExecutionOrderEvent.broker_account_id == self.broker_account_id,
            ExecutionOrderEvent.source == "engine",
            ExecutionOrderEvent.source_event_id == source_event_id,
        ))
        if existing is None:
            try:
                ExecutionLifecycleStore(self.s, owner_id=self.owner_id,
                                        broker_account_id=self.broker_account_id).append_event(
                    client_intent_id,
                    NewExecutionEvent(
                        source="engine", source_event_id=source_event_id,
                        kind="POSITION_BOOKED", broker_order_id=res.order_id,
                        broker_status=res.status, cumulative_filled_qty=pos.qty,
                        avg_price=pos.entry_premium,
                        payload={"position_id": pos.id, "booked_qty": pos.qty},
                    ),
                    self.lifecycle_clock(),
                )
            except Exception as e:
                log.error(f"position booking event failed: {e}", event="LIFECYCLE_FAIL")
                return False
        self._journal_resolve(row_id, res, filled, avg)
        return True

    def _append_position_protected(self, client_intent_id: str, pos: Position) -> bool:
        """Persist that exchange protection covers the current ledger quantity."""
        protection_id = protective_order_id(pos)
        if not protection_id:
            return False
        source_event_id = f"position-protected:{pos.id}:{pos.qty}:{protection_id}"
        existing = self.s.scalar(select(ExecutionOrderEvent).where(
            ExecutionOrderEvent.client_intent_id == client_intent_id,
            ExecutionOrderEvent.owner_id == self.owner_id,
            ExecutionOrderEvent.broker_account_id == self.broker_account_id,
            ExecutionOrderEvent.source == "engine",
            ExecutionOrderEvent.source_event_id == source_event_id,
        ))
        if existing is not None:
            return True
        try:
            ExecutionLifecycleStore(self.s, owner_id=self.owner_id,
                                    broker_account_id=self.broker_account_id).append_event(
                client_intent_id,
                NewExecutionEvent(
                    source="engine", source_event_id=source_event_id,
                    kind="POSITION_PROTECTED", broker_order_id=None,
                    broker_status="", cumulative_filled_qty=pos.qty,
                    avg_price=pos.entry_premium,
                    payload={"position_id": pos.id, "protected_qty": pos.qty,
                             "protection_id": str(protection_id)},
                ),
                self.lifecycle_clock(),
            )
            return True
        except Exception as e:
            log.error(f"protection event failed: {e}", event="LIFECYCLE_FAIL")
            return False

    def _protection_inventory(
        self, pos: Position,
    ) -> tuple[str, set[str], set[str]]:
        """Read all protection IDs and the exact subset for this Position."""
        side = "BUY" if (pos.segment == "equity_intraday"
                         and pos.direction == "SHORT") else "SELL"
        exchange = self.venue.exchange_for(pos.exchange)
        try:
            tick = float(self.venue.tick_size(pos.tradingsymbol, exchange))
        except Exception:
            tick = 0.05

        def trigger_key(value) -> int:
            return round(float(value or 0.0) / tick)

        kind = protective_kind_for_book_segment(pos.segment)
        # A RESTING_STOP shares the order book with every other order this account
        # placed, so it must additionally match our tag; a SERVER_TRIGGER lives in its
        # own GTT book and Kite carries no tag there, which is why the tag test is
        # conditional rather than absent.
        try:
            rows = list(self.venue.protective_inventory(kind))
            candidates = [row for row in rows if (
                row.get("tradingsymbol") == pos.tradingsymbol
                and row.get("exchange") == exchange
                and str(row.get("side") or "").upper() == side
                and int(row.get("qty") or 0) == pos.qty
                and trigger_key(row.get("trigger_price")) == trigger_key(pos.stop_price)
                and row.get("status") != "dead"
                and (kind is not ProtectiveStopKind.RESTING_STOP or row.get("tag") == TAG)
            )]
            all_ids = {str(row["id"]) for row in rows if row.get("id")}
            exact_ids = {str(row["id"]) for row in candidates if row.get("id")}
        except Exception as e:
            log.error(f"PROTECTION {pos.tradingsymbol}: inventory failed: {e}",
                      event="PROTECTION_RECONCILE_FAIL")
            return "ambiguous", set(), set()
        return "ok", all_ids, exact_ids

    def _ensure_entry_protected(self, pos: Position, last_price: float,
                                client_intent_id: str) -> bool:
        """Protect a filled entry, resolving uncertain prior stop submissions first."""
        store = ExecutionLifecycleStore(self.s, owner_id=self.owner_id,
                                        broker_account_id=self.broker_account_id)
        state = store.state_for(client_intent_id)
        if state.protected_qty >= pos.qty and protective_order_id(pos):
            return True
        if protective_order_id(pos):
            if 0 < state.protected_qty < pos.qty:
                if not self.update_stop_protection(pos, last_price):
                    return False
            return self._append_position_protected(client_intent_id, pos)

        events = list(self.s.scalars(select(ExecutionOrderEvent).where(
            ExecutionOrderEvent.client_intent_id == client_intent_id,
            ExecutionOrderEvent.owner_id == self.owner_id,
            ExecutionOrderEvent.broker_account_id == self.broker_account_id,
            ExecutionOrderEvent.kind.in_({
                "PROTECTION_SUBMIT_STARTED", "PROTECTION_ACKNOWLEDGED",
                "PROTECTION_RETRY_ALLOWED"}),
        ).order_by(ExecutionOrderEvent.id)))
        last_submit = next(
            (event for event in reversed(events)
             if event.kind == "PROTECTION_SUBMIT_STARTED"), None)
        retry_id = (f"retry-allowed:{last_submit.source_event_id}"
                    if last_submit is not None else None)
        retry_allowed = any(event.source_event_id == retry_id for event in events)
        if last_submit is not None and not retry_allowed:
            try:
                submit_payload = json.loads(last_submit.payload_json or "")
                baseline_ids = submit_payload["baseline_ids"]
                if (not isinstance(submit_payload, dict)
                        or not isinstance(baseline_ids, list)
                        or not all(isinstance(value, str) for value in baseline_ids)):
                    raise ValueError("invalid protection baseline")
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as e:
                log.error(
                    f"PROTECTION {pos.tradingsymbol}: corrupt submit metadata: {e}",
                    event="PROTECTION_RECONCILE_FAIL",
                )
                self._notify(
                    f"⚠️ {pos.tradingsymbol}: protection metadata is invalid; "
                    f"entry remains blocked for manual reconciliation."
                )
                return False

            acknowledged = None
            for event in reversed(events):
                if event.kind != "PROTECTION_ACKNOWLEDGED":
                    continue
                try:
                    payload = json.loads(event.payload_json or "")
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
                if payload.get("submit_event") == last_submit.source_event_id:
                    acknowledged = event
                    break

            if acknowledged is not None and acknowledged.broker_order_id:
                outcome, all_ids, exact_ids = self._protection_inventory(pos)
                protection_id = str(acknowledged.broker_order_id)
                if outcome != "ok" or protection_id not in all_ids:
                    self._notify(
                        f"⚠️ {pos.tradingsymbol}: acknowledged protection "
                        f"{protection_id} is not yet visible; entry remains blocked."
                    )
                    return False
                if protection_id not in exact_ids:
                    self._notify(
                        f"⚠️ {pos.tradingsymbol}: acknowledged protection "
                        f"{protection_id} does not match the required stop; entry remains blocked."
                    )
                    return False
                set_protective_order_id(pos, protection_id)
                try:
                    self.s.commit()
                except Exception as e:
                    self.s.rollback()
                    log.error(f"PROTECTION {pos.tradingsymbol}: matched-id persistence "
                              f"failed: {e}", event="PROTECTION_RECONCILE_FAIL")
                    return False
                return self._append_position_protected(client_intent_id, pos)

            self._notify(
                f"⚠️ {pos.tradingsymbol}: protective-order placement has no durable "
                f"broker acknowledgement; entry remains blocked for manual reconciliation."
            )
            return False

        attempt = 1 + sum(
            event.kind == "PROTECTION_SUBMIT_STARTED" for event in events)
        source_event_id = f"protection-submit:{pos.id}:{pos.qty}:{attempt}"
        if last_submit is None:
            intent = self.s.get(ExecutionIntent, client_intent_id)
            try:
                intent_context = json.loads(intent.context_json or "") if intent else {}
                preflight = intent_context["protection_preflight"]
                baseline_ids = preflight["baseline_ids"]
                if (not isinstance(preflight, dict)
                        or not isinstance(baseline_ids, list)
                        or not all(isinstance(value, str) for value in baseline_ids)):
                    raise ValueError("invalid protection preflight")
                baseline_ids = set(baseline_ids)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                # Older unresolved intents did not persist a pre-entry inventory.
                # They may still be repaired, but only after a successful read now.
                inventory_status, baseline_ids, _ = self._protection_inventory(pos)
                if inventory_status != "ok":
                    self._notify(
                        f"⚠️ {pos.tradingsymbol}: protection inventory could not be "
                        f"read; no protective order was submitted."
                    )
                    return False
        else:
            inventory_status, baseline_ids, _ = self._protection_inventory(pos)
            if inventory_status != "ok":
                self._notify(
                    f"⚠️ {pos.tradingsymbol}: protection inventory could not be read; "
                    f"no protective order was submitted."
                )
                return False
        try:
            store.append_event(
                client_intent_id,
                NewExecutionEvent(
                    source="engine", source_event_id=source_event_id,
                    kind="PROTECTION_SUBMIT_STARTED", broker_order_id=None,
                    broker_status="", cumulative_filled_qty=0, avg_price=0.0,
                    payload={
                        "position_id": pos.id, "qty": pos.qty,
                        "tradingsymbol": pos.tradingsymbol,
                        "exchange": self.venue.exchange_for(pos.exchange),
                        "side": "BUY" if (pos.segment == "equity_intraday"
                                           and pos.direction == "SHORT") else "SELL",
                        "trigger_price": pos.stop_price,
                        "baseline_ids": sorted(baseline_ids),
                    },
                ),
                self.lifecycle_clock(),
            )
        except Exception as e:
            log.error(f"PROTECTION {pos.tradingsymbol}: submit fact failed: {e}",
                      event="LIFECYCLE_FAIL")
            return False
        def protection_acknowledged(protection_id: str) -> None:
            store.append_event(
                client_intent_id,
                NewExecutionEvent(
                    source="broker",
                    source_event_id=f"protection-ack:{protection_id}",
                    kind="PROTECTION_ACKNOWLEDGED",
                    broker_order_id=str(protection_id),
                    broker_status="ACKNOWLEDGED",
                    cumulative_filled_qty=0,
                    avg_price=0.0,
                    payload={"submit_event": source_event_id,
                             "protection_id": str(protection_id)},
                ),
                self.lifecycle_clock(),
            )

        if protective_kind_for_book_segment(
                pos.segment) is ProtectiveStopKind.RESTING_STOP:
            outcome = self._place_equity_stop(
                pos, last_price, on_placed=protection_acknowledged)
        else:
            outcome = self._place_gtt(
                pos, last_price, on_placed=protection_acknowledged)
        if outcome == "prewire_rejected":
            try:
                store.append_event(
                    client_intent_id,
                    NewExecutionEvent(
                        source="engine", source_event_id=f"retry-allowed:{source_event_id}",
                        kind="PROTECTION_RETRY_ALLOWED", broker_order_id=None,
                        broker_status="", cumulative_filled_qty=0, avg_price=0.0,
                        payload={"submit_event": source_event_id},
                    ),
                    self.lifecycle_clock(),
                )
            except Exception as e:
                log.error(f"PROTECTION {pos.tradingsymbol}: retry fact failed: {e}",
                          event="LIFECYCLE_FAIL")
            return False
        if outcome != "protected":
            return False
        return self._append_position_protected(client_intent_id, pos)

    # ── order journal (H13) — durable mirror of _inflight ∪ _pending_entries ──
    def _journal_open(self, req, intent: str, kind: str, context) -> int | None:
        if not intent:
            return None
        try:
            row = OrderJournal(
                owner_id=self.owner_id,
                broker_account_id=self.broker_account_id,
                deployment_id=self.deployment_id,
                order_id=None, tradingsymbol=req.tradingsymbol,
                instrument_key=(context or {}).get("inst_key", ""), side=req.side,
                kind=kind, intent=intent, qty=req.qty,
                context_json=json.dumps(context or {}), status="WORKING",
                placed_at=self.provider.now())
            self.s.add(row)
            self.s.commit()
            return row.id
        except Exception as e:
            self.s.rollback()
            log.error(f"journal open failed: {e}", event="JOURNAL_FAIL")
            return None

    def _journal_set_order_id(self, row_id: int, order_id: str) -> None:
        try:
            row = self.s.scalar(select(OrderJournal).where(
                OrderJournal.id == row_id,
                OrderJournal.owner_id == self.owner_id,
                OrderJournal.broker_account_id == self.broker_account_id,
            ))
            if row:
                row.order_id = order_id
                self.s.commit()
        except Exception as e:
            self.s.rollback()
            log.error(f"journal order_id set failed: {e}", event="JOURNAL_FAIL")

    @staticmethod
    def _journal_resolution(res, filled: int, qty: int) -> str | None:
        """None => the row stays WORKING (order may still be live); else terminal."""
        if res.reconciliation_required:
            return None
        if qty > 0 and filled >= qty:
            return "FILLED"
        if filled > 0:                              # partial
            if "timeout" in (res.reason or "").lower():
                return None                         # may still work — H16 resolves it
            return "CANCELLED"                      # cancelled-after-partial (dead)
        if res.status == "REJECTED":
            return "REJECTED"
        if res.status == "ERROR" and not res.order_id:
            return "NEVER_PLACED"
        if res.order_id and res.status in ("TIMEOUT", "ERROR"):
            return None                             # working — recover on restart
        return "UNKNOWN"

    def _journal_resolve(self, row_id: int | None, res, filled: int, avg: float) -> None:
        if row_id is None:
            return
        try:
            row = self.s.scalar(select(OrderJournal).where(
                OrderJournal.id == row_id,
                OrderJournal.owner_id == self.owner_id,
                OrderJournal.broker_account_id == self.broker_account_id,
            ))
            if not row:
                return
            resolution = self._journal_resolution(res, filled, row.qty)
            if resolution is not None:
                row.status = "TERMINAL"
                row.resolution = resolution
                row.filled_qty = filled
                row.avg_price = avg
                row.resolved_at = self.provider.now()
                self.s.commit()
        except Exception as e:
            self.s.rollback()
            log.error(f"journal resolve failed: {e}", event="JOURNAL_FAIL")

    def journal_mark_terminal(self, order_id: str, resolution: str,
                              filled: int = 0, avg: float = 0.0) -> None:
        """Mark the WORKING journal row for an order terminal — called from every site
        that pops _inflight/_pending_entries, keeping the journal in lockstep."""
        if not order_id:
            return
        try:
            row = self.s.scalars(
                select(OrderJournal).where(OrderJournal.order_id == order_id,
                                           OrderJournal.deployment_id == self.deployment_id,
                                           OrderJournal.owner_id == self.owner_id,
                                           OrderJournal.broker_account_id == self.broker_account_id,
                                           OrderJournal.status == "WORKING")).first()
            if row:
                row.status = "TERMINAL"
                row.resolution = resolution
                if filled:
                    row.filled_qty = filled
                if avg:
                    row.avg_price = avg
                row.resolved_at = self.provider.now()
                self.s.commit()
        except Exception as e:
            self.s.rollback()
            log.error(f"journal mark terminal failed: {e}", event="JOURNAL_FAIL")

    def _pending_from_context(self, *, kind: str, order_id, row_id,
                              client_intent_id: str, broker_tag: str, ctx: dict) -> dict:
        """Reconstruct a pending entry from its durable lifecycle context."""
        inst = get_instrument(ctx["inst_key"])
        common = {
            "kind": kind,
            "order_id": order_id,
            "inst": inst,
            "direction": ctx["direction"],
            "reason": ctx.get("reason", "recovered"),
            "params": ctx.get("params"),
            "strategy_key": ctx.get("strategy_key"),
            "strategy_version": ctx.get("strategy_version"),
            "client_intent_id": client_intent_id,
            "broker_tag": broker_tag,
            "row_id": row_id,
        }
        if kind == "options":
            qd = dict(ctx.get("q", {}))
            exp = qd.get("expiry")
            if isinstance(exp, str):
                try:
                    qd["expiry"] = dt.date.fromisoformat(exp)
                except Exception:
                    pass
            q = OptionQuote(instrument_key=ctx["inst_key"], **qd)
            return dict(common, q=q, spot=ctx.get("spot", 0.0))
        return dict(
            common,
            charge_segment=ctx.get("charge_segment", ""),
            sl_pct=ctx.get("sl_pct"),
            tp_pct=ctx.get("tp_pct"),
            margin=ctx.get("margin"),
            requested_qty=ctx.get("requested_qty"),
        )

    def _rebuild_pending(self, row, ctx) -> dict:
        """Reconstruct a _pending_entries context from a journaled ENTRY row (H13)."""
        client_intent_id = ctx.get("client_intent_id")
        return self._pending_from_context(
            kind=row.kind,
            order_id=row.order_id,
            row_id=row.id,
            client_intent_id=client_intent_id,
            broker_tag=make_broker_tag(client_intent_id) if client_intent_id else "",
            ctx=ctx,
        )

    def _reconcile_uncertain_entries(self, now) -> None:
        """Attach no-ack intents only when one exact broker tag match exists."""
        uncertain = [
            (symbol, ctx) for symbol, ctx in self._pending_entries.items()
            if not ctx.get("order_id") and ctx.get("broker_tag")
        ]
        if not uncertain:
            return
        try:
            orders = list(self.client.orders() or [])
        except Exception as e:
            log.error(f"UNCERTAIN: exact-tag reconciliation failed: {e}",
                      event="ENTRY_RECONCILE_FAIL")
            return

        store = ExecutionLifecycleStore(self.s, owner_id=self.owner_id,
                                        broker_account_id=self.broker_account_id)
        for symbol, ctx in uncertain:
            matches = [order for order in orders
                       if order.get("tag") == ctx["broker_tag"]]
            if not matches:
                # Broker order books can be eventually consistent. Absence is not
                # proof that placement failed, so the entry remains blocked.
                continue
            if len(matches) != 1:
                order_ids = sorted(str(order.get("order_id") or "") for order in matches)
                source_event_id = "tag-multiple:" + ctx["broker_tag"]
                existing = self.s.scalar(select(ExecutionOrderEvent).where(
                    ExecutionOrderEvent.client_intent_id == ctx["client_intent_id"],
                    ExecutionOrderEvent.owner_id == self.owner_id,
                    ExecutionOrderEvent.broker_account_id == self.broker_account_id,
                    ExecutionOrderEvent.source == "recovery",
                    ExecutionOrderEvent.source_event_id == source_event_id,
                ))
                if existing is None:
                    anomaly = (f"multiple exact broker-tag matches for {ctx['broker_tag']}: "
                               f"{', '.join(order_ids)}")
                    try:
                        store.append_event(
                            ctx["client_intent_id"],
                            NewExecutionEvent(
                                source="recovery", source_event_id=source_event_id,
                                kind="RECONCILIATION_ANOMALY", broker_order_id=None,
                                broker_status="", cumulative_filled_qty=0,
                                avg_price=0.0,
                                payload={"tag": ctx["broker_tag"],
                                         "order_ids": order_ids},
                                anomaly=anomaly,
                            ),
                            self.lifecycle_clock(),
                        )
                    except Exception as e:
                        log.error(f"UNCERTAIN {symbol}: anomaly persistence failed: {e}",
                                  event="LIFECYCLE_FAIL")
                self._notify(f"⚠️ {symbol}: multiple orders match durable entry tag "
                             f"{ctx['broker_tag']}; entry remains blocked. Verify on Zerodha.")
                continue

            order_id = str(matches[0].get("order_id") or "")
            if not order_id:
                continue
            try:
                store.append_event(
                    ctx["client_intent_id"],
                    NewExecutionEvent(
                        source="broker", source_event_id=f"ack:{order_id}",
                        kind="ACKNOWLEDGED", broker_order_id=order_id,
                        broker_status="", cumulative_filled_qty=0, avg_price=0.0,
                        payload={"order_id": order_id, "recovered_by_tag": True},
                    ),
                    self.lifecycle_clock(),
                )
            except Exception as e:
                log.error(f"UNCERTAIN {symbol}: acknowledgement persistence failed: {e}",
                          event="LIFECYCLE_FAIL")
                continue
            ctx["order_id"] = order_id
            self._inflight[symbol] = order_id
            if ctx.get("row_id"):
                self._journal_set_order_id(ctx["row_id"], order_id)

    def recover_journal(self, now) -> list:
        """H13: on startup, replay WORKING journal rows — the in-memory in-flight
        trackers were wiped by the restart. A late-filled ENTRY is adopted (book +
        stop); a filled EXIT is booked ledger-only at the REAL price (beats the orphan
        reconciler's stale mark); still-working orders are re-tracked; dead ones closed.
        A status read failure leaves the row WORKING (fail open — retry next start)."""
        recovered: list[str] = []
        rows = self.s.scalars(
            select(OrderJournal).where(OrderJournal.status == "WORKING",
                                       OrderJournal.deployment_id == self.deployment_id,
                                       OrderJournal.owner_id == self.owner_id,
                                       OrderJournal.broker_account_id == self.broker_account_id)).all()
        for row in rows:
            if not row.order_id:
                if row.intent == "ENTRY":
                    try:
                        ctx = json.loads(row.context_json or "{}")
                        pending = self._rebuild_pending(row, ctx)
                        client_intent_id = ctx.get("client_intent_id")
                        if client_intent_id:
                            state = ExecutionLifecycleStore(
                                self.s, owner_id=self.owner_id,
                                broker_account_id=self.broker_account_id).state_for(
                                client_intent_id)
                            pending["order_id"] = state.broker_order_id
                            if state.broker_order_id:
                                self._inflight[row.tradingsymbol] = state.broker_order_id
                                self._journal_set_order_id(row.id, state.broker_order_id)
                        self._pending_entries[row.tradingsymbol] = pending
                    except Exception as e:
                        log.error(f"RECOVER {row.tradingsymbol}: uncertain submit rebuild "
                                  f"failed: {e}", event="RECOVER_FAIL")
                continue
            try:
                st = self.client.status(row.order_id)
            except Exception as e:
                log.error(f"RECOVER {row.tradingsymbol}: status({row.order_id}) failed: {e} "
                          f"— left WORKING", event="RECOVER_FAIL")
                continue
            status = str(st.get("status", "")).upper()
            filled = int(st.get("filled_qty", 0) or 0)
            avg = float(st.get("avg_price", 0.0) or 0.0)
            try:
                ctx = json.loads(row.context_json or "{}")
            except Exception:
                ctx = {}
            if row.intent == "ENTRY":
                if filled > 0 and avg > 0:
                    self._pending_entries[row.tradingsymbol] = self._rebuild_pending(row, ctx)
                elif status in _DEAD_STATUSES:
                    self.journal_mark_terminal(row.order_id, "DEAD")
                else:
                    self._inflight[row.tradingsymbol] = row.order_id
                    self._pending_entries[row.tradingsymbol] = self._rebuild_pending(row, ctx)
            else:   # EXIT
                pos = self.s.scalar(select(Position).where(
                    Position.id == ctx["position_id"],
                    Position.deployment_id == self.deployment_id,
                    Position.owner_id == self.owner_id,
                    Position.broker_account_id == self.broker_account_id,
                )) if ctx.get("position_id") else None
                if filled >= row.qty and pos is not None:
                    if pos.segment == "equity_intraday":
                        PaperBroker.close_equity_position(self, pos, avg, "RECOVERED_EXIT_FILL", now)
                    else:
                        PaperBroker.close_position(self, pos, avg, "RECOVERED_EXIT_FILL", now, pos.last_spot)
                    self.journal_mark_terminal(row.order_id, "FILLED", filled, avg)
                    recovered.append(row.tradingsymbol)
                elif status in _DEAD_STATUSES:
                    self.journal_mark_terminal(row.order_id, "DEAD")
                else:
                    self._inflight[row.tradingsymbol] = row.order_id
        # The lifecycle log is the authoritative entry record. A crash can happen
        # after SUBMIT_STARTED even when the best-effort journal never committed, so
        # rebuild those blockers independently and under the exact broker scope.
        deployment = self.s.scalar(select(Deployment).where(
            Deployment.id == self.deployment_id,
            Deployment.owner_id == self.owner_id,
            Deployment.broker_account_id == self.broker_account_id,
        ))
        if deployment is not None:
            store = ExecutionLifecycleStore(self.s, owner_id=self.owner_id,
                                            broker_account_id=self.broker_account_id)
            intents = store.unresolved_entries(
                self.deployment_id,
                self.account.external_account_id,
                self.connection.scope,
                broker=self.connection.broker,
            )
            pending_ids = {ctx.get("client_intent_id")
                           for ctx in self._pending_entries.values()}
            for intent in intents:
                if intent.client_intent_id in pending_ids:
                    continue
                try:
                    ctx = json.loads(intent.context_json or "{}")
                    state = store.state_for(intent.client_intent_id)
                    kind = "options" if "q" in ctx else "equity"
                    pending = self._pending_from_context(
                        kind=kind,
                        order_id=state.broker_order_id,
                        row_id=None,
                        client_intent_id=intent.client_intent_id,
                        broker_tag=intent.broker_tag,
                        ctx=ctx,
                    )
                    self._pending_entries[intent.tradingsymbol] = pending
                    pending_ids.add(intent.client_intent_id)
                    if state.broker_order_id:
                        self._inflight[intent.tradingsymbol] = state.broker_order_id
                except Exception as e:
                    log.error(f"RECOVER {intent.tradingsymbol}: lifecycle rebuild failed: {e}",
                              event="RECOVER_FAIL")
        self._reconcile_uncertain_entries(now)
        try:
            recovered.extend(self.adopt_pending_entries(now))   # books + marks ADOPTED
        except Exception as e:
            log.error(f"RECOVER adopt failed: {e}", event="RECOVER_FAIL")
        self._recover_tag_sweep()
        return recovered

    def _recover_tag_sweep(self) -> None:
        """Surface any tag=pt-bot exchange order the bot cannot account for (a crash
        between the journal write and the placement ack). Never auto-books — alerts to
        verify.

        "Cannot account for" means: not in `order_journal` AND not a resting protective
        stop recorded on a position. The protective SL-M is placed with the same tag but
        is tracked in `positions.gtt_trigger_id`, so a journal-only check reported every
        one of the bot's own stops as an orphan — nine false alarms and nine Telegram
        messages on EVERY restart through July. That is worse than useless: this is the
        alert that guards against a real position the bot has lost track of, and an alert
        that cries wolf nine times a day is one nobody reads.

        Order ids are compared as strings: Kite has returned them as both ints and
        strings, and a type mismatch would make every bot order look untracked."""
        try:
            orders = self.client.orders()
        except Exception as e:
            # "Failed to look" must never read as "found nothing".
            log.error(f"RECOVER: could not read the order book ({e}) — orphaned-order "
                      f"check DID NOT RUN this start", event="RECOVER_SWEEP_FAIL")
            self._notify(f"⚠️ could not read the Zerodha order book ({e}) — the bot could "
                         f"not check for orphaned orders this start; verify manually.")
            return

        def sid(v) -> str:
            return "" if v is None else str(v)

        deployment_id = getattr(self, "deployment_id", LEGACY_DEPLOYMENT_ID)
        known = {sid(r.order_id) for r in self.s.scalars(
            select(OrderJournal).where(
                OrderJournal.deployment_id == deployment_id,
                OrderJournal.owner_id == self.owner_id,
                OrderJournal.broker_account_id == self.broker_account_id)).all()
                 if r.order_id}
        lifecycle_intents = self.s.scalars(select(ExecutionIntent).where(
            ExecutionIntent.deployment_id == deployment_id,
            ExecutionIntent.owner_id == self.owner_id,
            ExecutionIntent.broker_account_id == self.broker_account_id)).all()
        lifecycle_store = ExecutionLifecycleStore(
            self.s, owner_id=self.owner_id,
            broker_account_id=self.broker_account_id)
        known |= {sid(lifecycle_store.state_for(intent.client_intent_id).broker_order_id)
                  for intent in lifecycle_intents}
        # Resting protective stops of positions still open …
        known |= {sid(protective_order_id(p)) for p in self.s.scalars(
            select(Position).where(
                Position.deployment_id == deployment_id,
                Position.owner_id == self.owner_id,
                Position.broker_account_id == self.broker_account_id)).all()
                  if protective_order_id(p)}
        known.discard("")

        for o in orders or []:
            oid = sid(o.get("order_id"))
            if is_strategy_os_tag(o.get("tag")) and oid not in known:
                log.error(f"RECOVER: tagged order {oid} ({o.get('tradingsymbol')}) "
                          f"has no journal row — verify on Zerodha", event="RECOVER_UNTRACKED")
                self._notify(f"⚠️ a bot-tagged order ({oid}) has no journal record "
                             f"— verify on Zerodha; the bot won't touch it.")

    @staticmethod
    def _quote_to_ctx(q) -> dict:
        """JSON-safe snapshot of an OptionQuote for the journal, rebuilt on recovery."""
        exp = q.expiry.isoformat() if hasattr(q.expiry, "isoformat") else q.expiry
        return {"tradingsymbol": q.tradingsymbol, "exchange": q.exchange, "strike": q.strike,
                "expiry": exp, "option_type": q.option_type, "lot_size": q.lot_size,
                "ltp": q.ltp, "bid": q.bid, "ask": q.ask,
                "bid_qty": q.bid_qty, "ask_qty": q.ask_qty,
                "volume": q.volume, "oi": q.oi}

    def _note_order_outcome(self, filled: int) -> None:
        """#14: feed the order circuit breaker — a zero-fill outcome extends the
        consecutive-failure streak, any real fill resets it. Called right after
        every _actual_fill read so the streak tracks ORDERS, not signals."""
        self.order_fail_streak = 0 if filled > 0 else self.order_fail_streak + 1

    def _entry_protection_preflight(self, *, kind: str, direction: str,
                                    price: float, params, tradingsymbol: str,
                                    exchange: str, sl_pct=None) -> dict | None:
        """Return durable protection context or refuse before the entry submit."""
        if not self._gtt_enabled() or price <= 0:
            return None
        from app.core.runtime_config import effective
        resolved = params if params is not None else effective(self.settings)
        if kind == "options":
            stop_pct = float(resolved.get("stop_loss_pct", self.settings.stop_loss_pct))
            stop = price * (1 - stop_pct)
        else:
            stop_pct = float(
                sl_pct if sl_pct is not None else resolved.get(
                    "intraday_stop_loss_pct", self.settings.intraday_stop_loss_pct))
            stop, _ = equity_stop_target(direction, price, stop_pct, 0.01)
        if stop <= 0:
            return None
        # ONE rule for which protective kind a position takes. This used to be `kind ==
        # "options"` here while `_protection_inventory` used
        # `protective_kind_for_book_segment(pos.segment)` — two independently-derived answers
        # that agree for every segment that exists today, so the baseline written here and the
        # `all_ids` it is later compared against came from different families by luck. A new
        # segment (futures, CNC carry) that mapped differently under the two would silently
        # compare a GTT id against the SL-M order book. F7, 2026-08-10.
        protective_kind = protective_kind_for_book_segment(
            "options" if kind == "options" else "equity_intraday")
        try:
            rows = list(self.venue.protective_inventory(protective_kind))
        except Exception as e:
            log.error(
                f"LIVE OPEN refused {tradingsymbol}: {protective_kind.value} inventory "
                f"failed: {e}",
                event="LIVE_OPEN_PROTECTION_REFUSED",
            )
            return None
        baseline_ids = sorted(str(row["id"]) for row in rows if row.get("id"))
        return {
            "kind": kind,
            "tradingsymbol": tradingsymbol,
            "exchange": exchange,
            "side": "BUY" if (kind == "equity" and direction == "SHORT") else "SELL",
            "qty": None,
            "trigger_price": stop,
            "baseline_ids": baseline_ids,
        }

    def _record_inflight(self, symbol: str, res) -> None:
        """An order that was placed but whose outcome is UNKNOWN — a TIMEOUT (no fill
        reported) or an ERROR after submission (e.g. the status poll failed) — may
        still be live at the exchange. Record it so the next open/close for this
        contract cancels/awaits it first, never sending a second working order. (An
        ERROR with no order id means nothing reached the exchange — not recorded.)"""
        if res.order_id and res.status in ("TIMEOUT", "ERROR"):
            self._inflight[symbol] = res.order_id

    def _ensure_no_inflight(self, symbol: str) -> bool:
        """Guarantee at most ONE working bot order per contract. If a prior order for
        this symbol may still be working, resolve it before placing a new one. Returns
        True if it is now safe to place, False if it is NOT (the prior order already
        filled — a second order would double up — or a stuck order could not be
        cancelled)."""
        if self._pending_entries:
            if any(not pending.get("order_id") and pending.get("broker_tag")
                   for pending in self._pending_entries.values()):
                self._reconcile_uncertain_entries(self.provider.now())
            try:
                self.adopt_pending_entries(self.provider.now())
            except Exception as e:
                log.error(f"PENDING ENTRY: adoption failed: {e}",
                          event="ENTRY_RECONCILE_FAIL")
            # This call began with a durable entry blocker. Even if it was repaired,
            # never place another entry in the same decision cycle.
            return False

        oid = self._inflight.pop(symbol, None)
        if not oid:
            return True
        try:
            st = self.client.status(oid)
        except Exception as e:
            st = {}
            log.error(f"INFLIGHT {symbol}: status({oid}) read failed: {e}",
                      event="INFLIGHT_FAIL")
        status = str(st.get("status", "")).upper()
        filled = int(st.get("filled_qty", 0) or 0)
        if filled > 0:
            # the prior order actually filled since we recorded it — placing another
            # would be a duplicate BUY / an oversell. Surface it; do NOT place.
            log.error(f"INFLIGHT {symbol}: prior order {oid} already filled {filled} — "
                      f"NOT placing another", event="INFLIGHT_FILLED")
            self._notify(f"⚠️ {symbol}: a prior bot order ({oid}) already filled {filled} "
                         f"— verify on Zerodha; not sending another")
            return False
        if status in _DEAD_STATUSES or status == "COMPLETE":
            return True   # nothing working at the exchange — safe to place fresh
        # OPEN / PENDING / unknown / unreadable -> cancel and confirm before placing
        try:
            self.client.cancel(oid)
            log.warn(f"INFLIGHT {symbol}: cancelled stuck order {oid} before re-placing",
                     event="INFLIGHT_CANCEL")
        except Exception as e:
            log.error(f"INFLIGHT {symbol}: cancel({oid}) failed: {e} — NOT placing "
                      f"another to avoid a double fill", event="INFLIGHT_FAIL")
            self._notify(f"⚠️ {symbol}: couldn't cancel a stuck order ({oid}); not "
                         f"sending a new one to avoid a double fill — check Zerodha")
            return False
        return True

    def cancel_working_entries(self) -> list[str]:
        """H8: cancel every working/timed-out bot ENTRY order so KILL is a true hard
        stop — a still-resting entry can't fill after the kill and leave an untracked,
        stopless position. Best-effort per order; an order whose cancel FAILS (it may
        have just raced to a fill) is kept in the trackers so adopt_pending_entries can
        still catch and manage that fill. Successfully-cancelled orders are cleared."""
        order_ids = set(self._inflight.values())
        order_ids |= {ctx["order_id"] for ctx in self._pending_entries.values()
                      if ctx.get("order_id")}
        cancelled, failed = [], set()
        for oid in order_ids:
            try:
                self.client.cancel(oid)
                cancelled.append(oid)
                self.journal_mark_terminal(oid, "CANCELLED")   # H13
                log.warn(f"KILL: cancelled working entry order {oid}", event="KILL_CANCEL")
            except Exception as e:
                failed.add(oid)
                log.error(f"KILL: cancel({oid}) failed: {e} — verify on Zerodha",
                          event="KILL_CANCEL_FAIL")
                self._notify(f"⚠️ KILL: couldn't cancel working order {oid} — it may have "
                             f"filled; verify on Zerodha")
        # keep only orders whose cancel failed (a fill may have beaten the cancel — let
        # adoption manage it); drop everything successfully cancelled.
        self._inflight = {s: o for s, o in self._inflight.items() if o in failed}
        self._pending_entries = {s: c for s, c in self._pending_entries.items()
                                 if c.get("order_id") in failed}
        return cancelled

    def _actual_fill(self, res) -> tuple[int, float]:
        """How much actually filled, and at what average price. The poll's own count
        is authoritative for FILLED/PARTIAL; on a TIMEOUT (poll gave up reporting
        nothing) we re-query the order once to catch a fill that landed at the buzzer
        — so a real position is never missed."""
        if res.filled_qty and res.filled_qty > 0:
            return int(res.filled_qty), float(res.avg_price)
        if res.status == "TIMEOUT" and res.order_id:
            try:
                st = self.client.status(res.order_id)
            except Exception:
                return 0, 0.0
            fq = int(st.get("filled_qty", 0) or 0)
            if fq > 0:
                return fq, float(st.get("avg_price", 0.0) or 0.0)
        return 0, 0.0

    def open_position(self, inst, direction, q, reason, now, spot,
                      params=None, plan=None, strategy_key=None,
                      strategy_version=None, entry_intent_id=None):
        if entry_intent_id is not None:
            raise ValueError("LiveBroker creates and commits its own entry intent")
        protection_preflight = self._entry_protection_preflight(
                kind="options", direction=direction, price=q.ltp,
                params=params, tradingsymbol=q.tradingsymbol,
                exchange=self.venue.exchange_for(inst.segment))
        if protection_preflight is None:
            log.error(f"LIVE OPEN refused {q.tradingsymbol}: exchange protection is "
                      f"disabled or invalid", instrument=inst.key,
                      event="LIVE_OPEN_PROTECTION_REFUSED")
            return None
        # never two working bot orders on one contract — resolve any prior in-flight
        # order for this symbol first (cancel a stuck one; abort if one already filled).
        if not self._ensure_no_inflight(q.tradingsymbol):
            return None
        # Callers historically pass partial dictionaries (including ``{}``) and expect
        # omitted controls to inherit the effective settings. Treat params as an overlay,
        # not as a complete routing configuration.
        p = {**effective(self.settings), **(params or {})}
        if plan is None:
            plan = plan_order("ENTRY", "BUY", q.bid, q.ask, q.ltp, q.ask_qty,
                              q.lot_size, p)
        if plan.action == "SKIP":
            log.warn(f"LIVE OPEN routing refused {q.tradingsymbol}: {plan.reason}",
                     instrument=inst.key, event="ROUTE_SKIP")
            return None
        order_type = plan.action if plan.action in ("MARKET", "LIMIT") else "MARKET"
        limit = plan.limit_price if (plan and plan.action == "LIMIT") else None
        context = {"inst_key": inst.key, "direction": direction, "reason": reason,
                   "spot": spot, "params": params, "q": self._quote_to_ctx(q),
                   "strategy_key": strategy_key, "strategy_version": strategy_version,
                   "protection_preflight": dict(
                       protection_preflight, qty=q.lot_size)}
        decision_price = ((q.bid + q.ask) / 2.0
                          if q.bid > 0 and q.ask > 0 and q.ask >= q.bid else q.ltp)
        request = self._prepare_entry_request(
            OrderRequest(q.tradingsymbol, inst.segment, "BUY", q.lot_size,
                         order_type, limit))
        res, filled, avg, client_intent_id, row_id = self._execute_entry(
            request,
            kind="options", context=context, now=now, decision_price=decision_price,
            strategy_key=strategy_key, strategy_version=strategy_version)
        # L1 — ADOPT whatever actually filled (partial fills and buzzer fills too),
        # never silently drop a real position. Only a genuine zero-fill records nothing.
        self._note_order_outcome(filled)
        if filled <= 0:
            self._record_inflight(q.tradingsymbol, res)   # may still be working — guard next tick
            # C3: the option order may still fill after the poll window (a slow ack).
            # Remember enough to ADOPT that late fill on the reconcile sweep — otherwise
            # it becomes an invisible, stopless position (the equity #17 fix, now for
            # options, the default segment).
            if ((res.order_id and res.status in ("TIMEOUT", "ERROR"))
                    or res.reconciliation_required):
                self._pending_entries[q.tradingsymbol] = {
                    "kind": "options", "order_id": res.order_id, "inst": inst,
                    "direction": direction, "q": q, "reason": reason, "spot": spot,
                    "params": params, "strategy_key": strategy_key,
                    "strategy_version": strategy_version,
                    "client_intent_id": client_intent_id,
                    "broker_tag": make_broker_tag(client_intent_id), "row_id": row_id,
                    "booked_qty": 0}
            log.error(f"LIVE OPEN not filled [{res.status}] {q.tradingsymbol} — {res.reason}",
                      instrument=inst.key, event="LIVE_OPEN_FAIL")
            self._notify(f"⚠️ LIVE OPEN {q.tradingsymbol} {res.status}: {res.reason}")
            return None
        # book the ACTUAL filled qty at the ACTUAL fill price (not the snapshot ltp).
        pos = super().open_position(inst, direction,
                                    replace(q, ltp=avg, lot_size=filled),
                                    reason, now, spot, params,
                                    strategy_key=strategy_key,
                                    strategy_version=strategy_version,
                                    entry_intent_id=client_intent_id)
        pos.lot_size = q.lot_size   # qty reflects the real fill; lot_size stays the true lot
        self.s.commit()
        protected = self._ensure_entry_protected(pos, avg, client_intent_id)
        booked = (protected and self._mark_position_booked(
            client_intent_id, row_id, pos, res, filled, avg))
        partial_working = (res.status == "PARTIAL" and res.order_id
                           and "timeout" in (res.reason or "").lower())
        if not booked or partial_working:
            if partial_working:
                self._inflight[q.tradingsymbol] = res.order_id
            self._pending_entries[q.tradingsymbol] = {
                "kind": "options", "order_id": res.order_id, "inst": inst,
                "direction": direction, "q": q, "reason": reason, "spot": spot,
                "params": params, "strategy_key": strategy_key,
                "strategy_version": strategy_version,
                "client_intent_id": client_intent_id,
                "broker_tag": make_broker_tag(client_intent_id), "row_id": row_id,
                "booked_qty": filled}
        if filled < q.lot_size:
            log.error(f"LIVE OPEN PARTIAL {q.tradingsymbol} {filled}/{q.lot_size} "
                      f"@ {avg:.2f} (order {res.order_id})", instrument=inst.key,
                      event="LIVE_OPEN_PARTIAL")
            self._notify(f"⚠️ LIVE OPEN {q.tradingsymbol} only PARTIAL: {filled}/"
                         f"{q.lot_size} @ {avg:.2f} — managing the partial; verify on Zerodha")
        else:
            log.info(f"LIVE FILLED BUY {q.tradingsymbol} @ {avg:.2f} "
                     f"(order {res.order_id})", instrument=inst.key, event="LIVE_OPEN")
        return pos

    def open_equity_position(self, inst, direction, price, qty, charge_segment, reason,
                             now, params=None, strategy_key=None,
                             strategy_version=None, margin=None,
                             sl_pct=None, tp_pct=None, entry_intent_id=None, plan=None):
        """Place a REAL intraday-equity (MIS) order and book the ACTUAL fill. Mirrors
        the options open path but direction-aware: LONG buys to open, SHORT sells to
        open (Kite MIS allows real intraday shorts). A direction-aware GTT backstops it.

        `sl_pct`/`tp_pct` (purple tiering) are forwarded to PaperBroker so the live row
        freezes the same band a paper row would, and are carried on `_pending_entries`
        so a late fill adopted on the reconcile sweep keeps its purple band too."""
        if entry_intent_id is not None:
            raise ValueError("LiveBroker creates and commits its own entry intent")
        tsym = getattr(inst, "spot_symbol", None) or inst.key
        protection_preflight = self._entry_protection_preflight(
                kind="equity", direction=direction, price=price,
                params=params, tradingsymbol=tsym,
                exchange=self.venue.exchange_for(charge_segment), sl_pct=sl_pct)
        if protection_preflight is None:
            log.error(f"LIVE EQUITY OPEN refused {inst.key}: exchange protection is "
                      f"disabled or invalid", instrument=inst.key,
                      event="LIVE_OPEN_PROTECTION_REFUSED")
            return None
        if not self._ensure_no_inflight(tsym):
            return None
        side = "BUY" if direction == "LONG" else "SELL"
        p = {**effective(self.settings), **(params or {})}
        if plan is None:
            plan = plan_reference_entry(side, price, p)
        if plan.action == "SKIP":
            log.warn(f"LIVE EQUITY OPEN routing refused {tsym}: {plan.reason}",
                     instrument=inst.key, event="ROUTE_SKIP")
            return None
        context = {"inst_key": inst.key, "direction": direction,
                   "charge_segment": charge_segment, "reason": reason,
                   "params": params, "strategy_key": strategy_key,
                   "strategy_version": strategy_version, "sl_pct": sl_pct,
                   "tp_pct": tp_pct, "margin": margin,
                   "requested_qty": qty,
                   "protection_preflight": dict(
                       protection_preflight, qty=qty)}
        request = self._prepare_entry_request(OrderRequest(
            tsym, self.venue.exchange_for(charge_segment), side, qty, plan.action,
            plan.limit_price if plan.action == "LIMIT" else None,
            product=self.venue.product_for(tenor_for_charge_segment(charge_segment))))
        res, filled, avg, client_intent_id, row_id = self._execute_entry(
            request,
            kind="equity", context=context, now=now, decision_price=price,
            strategy_key=strategy_key, strategy_version=strategy_version)
        self._note_order_outcome(filled)
        if filled <= 0:
            self._record_inflight(tsym, res)
            # #17: the order may still fill later (pre-open uncross / slow open). Remember
            # enough to ADOPT that fill on the reconcile sweep instead of orphaning it.
            if ((res.order_id and res.status in ("TIMEOUT", "ERROR"))
                    or res.reconciliation_required):
                self._pending_entries[tsym] = {
                    "kind": "equity",
                    "order_id": res.order_id, "inst": inst, "direction": direction,
                    "charge_segment": charge_segment, "reason": reason, "params": params,
                    "strategy_key": strategy_key, "strategy_version": strategy_version,
                    "sl_pct": sl_pct, "tp_pct": tp_pct,
                    "margin": margin, "requested_qty": qty,
                    "client_intent_id": client_intent_id,
                    "broker_tag": make_broker_tag(client_intent_id), "row_id": row_id,
                    "booked_qty": 0}
            log.error(f"LIVE EQUITY OPEN not filled [{res.status}] {tsym} — {res.reason}",
                      instrument=inst.key, event="LIVE_EQUITY_OPEN_FAIL")
            self._notify(f"⚠️ LIVE EQUITY OPEN {tsym} {res.status}: {res.reason}")
            return None
        # book the REAL margin sized to the ACTUAL fill (scale for a partial fill)
        fill_margin = (margin * filled / qty) if (margin and margin > 0 and qty) else None
        pos = super().open_equity_position(inst, direction, avg, filled, charge_segment,
                                           reason, now, params, strategy_key,
                                           strategy_version,
                                           margin=fill_margin, sl_pct=sl_pct, tp_pct=tp_pct,
                                           entry_intent_id=client_intent_id)
        protected = self._ensure_entry_protected(pos, avg, client_intent_id)
        booked = (protected and self._mark_position_booked(
            client_intent_id, row_id, pos, res, filled, avg))
        partial_working = (res.status == "PARTIAL" and res.order_id
                           and "timeout" in (res.reason or "").lower())
        if not booked or partial_working:
            if partial_working:
                self._inflight[tsym] = res.order_id
            self._pending_entries[tsym] = {
                "kind": "equity", "order_id": res.order_id, "inst": inst,
                "direction": direction, "charge_segment": charge_segment,
                "reason": reason, "params": params, "strategy_key": strategy_key,
                "strategy_version": strategy_version, "sl_pct": sl_pct,
                "tp_pct": tp_pct, "margin": margin, "requested_qty": qty,
                "client_intent_id": client_intent_id,
                "broker_tag": make_broker_tag(client_intent_id),
                "row_id": row_id, "booked_qty": filled}
        if filled < qty:
            log.error(f"LIVE EQUITY OPEN PARTIAL {tsym} {filled}/{qty} @ {avg:.2f} "
                      f"(order {res.order_id})", instrument=inst.key,
                      event="LIVE_EQUITY_OPEN_PARTIAL")
            self._notify(f"⚠️ LIVE EQUITY OPEN {tsym} only PARTIAL: {filled}/{qty} @ "
                         f"{avg:.2f} — managing the partial; verify on Zerodha")
        else:
            log.info(f"LIVE FILLED {side} {tsym} {filled}@{avg:.2f} (order {res.order_id})",
                     instrument=inst.key, event="LIVE_EQUITY_OPEN")
        return pos

    def close_equity_position(self, pos, exit_price, reason, now,
                              exit_price_estimated: bool = False):
        """Flat an intraday-equity position with a REAL MIS order: a LONG sells, a
        SHORT buys to cover. Same ownership boundary + cancel-stop-then-send as options,
        but the backstop is a resting SL-M order (not a GTT — GTT isn't allowed for MIS).

        `exit_price_estimated` is accepted only for call-site signature compatibility
        with PaperBroker (e.g. a manual-close route that doesn't know which broker it's
        calling) and is otherwise IGNORED here: every booking below comes from a real
        order fill (`avg`), so it is never an estimate regardless of what the caller
        passed."""
        sym = pos.tradingsymbol
        if not self._ensure_no_inflight(sym):
            return None
        chk = can_bot_close(pos, self.provider.account_positions())
        if not chk.ok:
            log.error(f"LIVE EQUITY CLOSE BLOCKED {sym} — {chk.reason}",
                      instrument=pos.instrument_key, event="LIVE_CLOSE_BLOCKED")
            self._notify(f"🚫 CLOSE blocked {sym}: {chk.reason}")
            return None
        if protective_order_id(pos) and not self._cancel_equity_stop(protective_order_id(pos), sym):
            # #7/#18: couldn't cancel the resting SL-M — do NOT send a close (the SL-M
            # could fire into it → oversell/reverse) and don't orphan it. Leave the
            # position protected by its still-resting stop and flag for the owner.
            log.error(f"LIVE EQUITY CLOSE ABORTED {sym} — SL-M cancel failed; position left "
                      f"protected by its stop", instrument=pos.instrument_key, event="LIVE_CLOSE_ABORT")
            self._notify(f"🚫 CLOSE aborted {sym}: SL-M cancel failed — still protected by its "
                         f"stop; verify on Zerodha")
            return None
        # H4 — the SL-M stop is now cancelled; persist that before the close order so a
        # crash mid-close can't leave a dead trigger id that self-heal trusts.
        if protective_order_id(pos):
            clear_protective_order_id(pos)
            self.s.commit()
        chk2 = can_bot_close(pos, self.provider.account_positions())
        if not chk2.ok:
            log.error(f"LIVE EQUITY CLOSE ABORTED {sym} — {chk2.reason}",
                      instrument=pos.instrument_key, event="LIVE_CLOSE_ABORT")
            self._notify(f"🚫 CLOSE aborted {sym}: {chk2.reason}")
            self._place_equity_stop(pos, pos.last_premium or pos.entry_premium)
            return None
        side = "SELL" if pos.direction == "LONG" else "BUY"   # buy to cover a short
        res, filled, avg = self._execute(
            OrderRequest(sym, self.venue.exchange_for(pos.exchange), side, pos.qty,
                         "MARKET", None, tag=TAG,
                         product=self.venue.product_for(
                             tenor_for_charge_segment(pos.exchange))),
            intent="EXIT", kind="equity",
            context={"inst_key": pos.instrument_key, "position_id": pos.id, "segment": pos.segment})
        self._note_order_outcome(filled)
        if filled <= 0:
            self._record_inflight(sym, res)
            log.error(f"LIVE EQUITY CLOSE not filled [{res.status}] {sym} — {res.reason}",
                      instrument=pos.instrument_key, event="LIVE_CLOSE_FAIL")
            self._notify(f"⚠️ LIVE EQUITY CLOSE {sym} {res.status}: {res.reason}")
            self._place_equity_stop(pos, pos.last_premium or pos.entry_premium)
            return None
        if filled < pos.qty:
            # H16: book the sold slice and re-protect the REMAINDER, instead of leaving a
            # stopless position + a full-qty phantom for the reconciler to mis-book.
            # If the close order may still be working (timeout-partial), it must be
            # cancel-confirmed first — a fresh SL-M alongside a live close order could
            # both execute → oversell into the owner's account.
            if "timeout" in (res.reason or ""):
                try:
                    self.client.cancel(res.order_id)
                except Exception as e:
                    # couldn't cancel a possibly-live order — re-query: a raced full fill
                    # means the whole position closed; otherwise the working order still
                    # owns the exit (don't book, don't re-stop).
                    st = {}
                    try:
                        st = self.client.status(res.order_id)
                    except Exception:
                        pass
                    if int(st.get("filled_qty", 0) or 0) >= pos.qty:
                        return super().close_equity_position(
                            pos, float(st.get("avg_price", avg) or avg), reason, now)
                    log.error(f"LIVE EQUITY CLOSE PARTIAL {sym} {filled}/{pos.qty} — cancel "
                              f"failed ({e}); working order still owns the exit",
                              instrument=pos.instrument_key, event="LIVE_CLOSE_PARTIAL")
                    self._notify(f"⚠️ LIVE EQUITY CLOSE {sym} PARTIAL {filled}/{pos.qty} — "
                                 f"a working order still owns the rest; verify on Zerodha")
                    self._inflight[sym] = res.order_id
                    return None
                # cancel succeeded — re-query for the final fill (a lot can land between
                # the poll giving up and the cancel landing).
                try:
                    st = self.client.status(res.order_id)
                    filled = int(st.get("filled_qty", filled) or filled)
                    avg = float(st.get("avg_price", avg) or avg)
                except Exception:
                    pass
                if filled >= pos.qty:
                    return super().close_equity_position(pos, avg, reason, now)
            log.error(f"LIVE EQUITY CLOSE PARTIAL {sym} {filled}/{pos.qty} @ {avg:.2f} "
                      f"(order {res.order_id}) — booking the slice, re-protecting the rest",
                      instrument=pos.instrument_key, event="LIVE_CLOSE_PARTIAL")
            self._notify(f"⚠️ LIVE EQUITY CLOSE {sym} PARTIAL {filled}/{pos.qty} @ {avg:.2f} "
                         f"— booked the sold lots; {pos.qty - filled} still open & re-stopped")
            self.book_partial_close_equity(pos, filled, avg, reason, now)   # shrinks pos.qty
            self._place_equity_stop(pos, avg)   # SL-M for the (now smaller) remainder
            return None
        log.info(f"LIVE FILLED {side} {sym} {filled}@{avg:.2f} (order {res.order_id})",
                 instrument=pos.instrument_key, event="LIVE_CLOSE")
        return super().close_equity_position(pos, avg, reason, now)

    def close_position(self, pos, exit_premium, reason, now, spot,
                       exit_price_estimated: bool = False):
        # `exit_price_estimated` is accepted for call-site compatibility with
        # PaperBroker (e.g. the manual-close route) and IGNORED here — every path
        # below books a real order fill, never a mark.
        sym = pos.tradingsymbol
        # never two working bot orders on one contract — resolve any prior in-flight
        # SELL for this symbol first (cancel a stuck one; abort if one already filled,
        # which means it likely already closed and a second SELL would oversell).
        if not self._ensure_no_inflight(sym):
            return None
        # OWNERSHIP GUARD — never act on a position the live account doesn't back.
        chk = can_bot_close(pos, self.provider.account_positions())
        if not chk.ok:
            log.error(f"LIVE CLOSE BLOCKED {sym} — {chk.reason}",
                      instrument=pos.instrument_key, event="LIVE_CLOSE_BLOCKED")
            self._notify(f"🚫 CLOSE blocked {sym}: {chk.reason}")
            return None
        # L6 — cancel the exchange GTT BEFORE the closing SELL (cancel-then-sell), so
        # a premium gap-down can't fire the server-side stop into the same window as
        # our market SELL (both execute → oversell into the owner's account).
        gid = protective_order_id(pos)
        if gid and not self._cancel_gtt(gid, sym):
            # #7: couldn't cancel the exchange GTT — do NOT send the SELL (the live GTT
            # could fire into it → oversell) and don't orphan it. Leave the position
            # protected by its still-resting GTT and flag for the owner.
            log.error(f"LIVE CLOSE ABORTED {sym} — GTT {gid} cancel failed; position left "
                      f"protected by its GTT", instrument=pos.instrument_key, event="LIVE_CLOSE_ABORT")
            self._notify(f"🚫 CLOSE aborted {sym}: GTT cancel failed — still protected by its "
                         f"GTT; verify on Zerodha")
            return None
        # H4 — the GTT is now cancelled at the exchange. Persist that immediately: if the
        # process dies during the SELL poll below, the DB must not keep a dead trigger id
        # (ensure_stop_protection would trust it and never re-place a stop, and the next
        # close would re-cancel a dead GTT and abort forever). Every path from here either
        # re-places a fresh GTT (abort/partial/fail) or deletes the row (full fill).
        if gid:
            clear_protective_order_id(pos)
            self.s.commit()
        # Re-check the account immediately before sending. If the GTT already fired
        # (or the owner exited) the account no longer backs us — send NO order and
        # leave the now-orphaned position for reconcile_orphans to book.
        chk2 = can_bot_close(pos, self.provider.account_positions())
        if not chk2.ok:
            log.error(f"LIVE CLOSE ABORTED {sym} — {chk2.reason}",
                      instrument=pos.instrument_key, event="LIVE_CLOSE_ABORT")
            self._notify(f"🚫 CLOSE aborted {sym} (backstop may have fired): {chk2.reason}")
            # we already cancelled the GTT — if this was a transient glitch the
            # position is still real, so restore its backstop rather than leave it
            # unprotected (a stray GTT on a truly-closed position is cancelled by the
            # orphan reconciler, and Kite rejects a SELL of a holding you don't have).
            self._place_gtt(pos, pos.last_premium or pos.entry_premium)
            return None
        want = pos.qty
        res, sold, avg = self._execute(
            OrderRequest(sym, pos.exchange, "SELL", want, "MARKET", None, tag=TAG),
            intent="EXIT", kind="options",
            context={"inst_key": pos.instrument_key, "position_id": pos.id, "segment": pos.segment})
        # L2 — book what ACTUALLY sold (re-querying a TIMEOUT to catch a buzzer fill),
        # never assume the full size sold.
        if sold <= 0:
            self._record_inflight(sym, res)   # may still be working — guard next tick
            log.error(f"LIVE CLOSE not filled [{res.status}] {sym} — {res.reason}",
                      instrument=pos.instrument_key, event="LIVE_CLOSE_FAIL")
            self._notify(f"⚠️ LIVE CLOSE {sym} {res.status}: {res.reason}")
            # the SELL didn't go through but the position is still open and REAL —
            # restore the exchange backstop we cancelled so it's never unprotected.
            self._place_gtt(pos, pos.last_premium or pos.entry_premium)
            return None
        if sold < want:
            # only part sold — book that slice, keep (and re-protect) the remainder so
            # the ledger never overstates the position and the next exit can't oversell.
            log.error(f"LIVE CLOSE PARTIAL {sym} {sold}/{want} @ {avg:.2f} "
                      f"(order {res.order_id})", instrument=pos.instrument_key,
                      event="LIVE_CLOSE_PARTIAL")
            self._notify(f"⚠️ LIVE CLOSE {sym} only PARTIAL: {sold}/{want} @ {avg:.2f} "
                         f"— booked the sold lots; {want - sold} still open & protected")
            self.book_partial_close(pos, sold, avg, reason, now, spot)
            self._place_gtt(pos, pos.last_premium or pos.entry_premium)
            return None
        log.info(f"LIVE FILLED SELL {sym} @ {avg:.2f} "
                 f"(order {res.order_id})", instrument=pos.instrument_key, event="LIVE_CLOSE")
        return super().close_position(pos, avg, reason, now, spot)

    # ── GTT safety-net stop ───────────────────────────────────────────────
    def _gtt_enabled(self) -> bool:
        from app.core.runtime_config import effective
        return bool(effective(self.settings).get("gtt_stop_enabled", True))

    def _place_gtt(self, pos, last_price, on_placed=None) -> str:
        if pos is None or not self._gtt_enabled() or pos.stop_price <= 0:
            return "disabled"
        # a long position's protective stop SELLs below; an intraday-equity SHORT's
        # BUYs to cover above. Equity charge-segments map to the bare NSE/BSE exchange.
        side = "BUY" if (pos.segment == "equity_intraday" and pos.direction == "SHORT") else "SELL"
        exchange = self.venue.exchange_for(pos.exchange)
        try:
            tid = self.venue.place_protective_stop(
                ProtectiveStopKind.SERVER_TRIGGER, tradingsymbol=pos.tradingsymbol,
                exchange=exchange, qty=pos.qty, trigger_price=pos.stop_price,
                side=side, last_price=last_price)
        except PreWireProtectionRejected as e:
            log.error(f"GTT rejected locally {pos.tradingsymbol}: {e}",
                      instrument=pos.instrument_key, event="GTT_PREWIRE_REJECT")
            return "prewire_rejected"
        except Exception as e:
            log.error(f"GTT place failed {pos.tradingsymbol}: {e}",
                      instrument=pos.instrument_key, event="GTT_FAIL")
            self._notify(f"⚠️ GTT backstop placement uncertain for {pos.tradingsymbol} — "
                         f"will reconcile before any retry ({e})")
            return "uncertain"
        if on_placed is not None:
            try:
                on_placed(str(tid))
            except Exception as e:
                log.error(f"GTT acknowledgement persistence failed {pos.tradingsymbol}: {e}",
                          instrument=pos.instrument_key, event="GTT_PERSIST_FAIL")
                self._notify(f"⚠️ GTT {tid} may be live for {pos.tradingsymbol}, but "
                             f"its acknowledgement was not durable; manual reconciliation "
                             f"is required.")
                return "uncertain"
        try:
            set_protective_order_id(pos, tid)
            self.s.commit()
            log.info(f"GTT stop placed {pos.tradingsymbol} @ {pos.stop_price:.2f} (gtt {tid})",
                     instrument=pos.instrument_key, event="GTT_PLACE")
            return "protected"
        except Exception as e:
            self.s.rollback()
            log.error(f"GTT id persistence failed {pos.tradingsymbol}: {e}",
                      instrument=pos.instrument_key, event="GTT_PERSIST_FAIL")
            self._notify(f"⚠️ GTT may be live for {pos.tradingsymbol}, but its id could "
                         f"not be persisted; entry remains blocked and no duplicate will "
                         f"be sent until reconciliation ({e})")
            return "uncertain"

    # ── SL-M protective stop (the MIS backstop; GTT isn't allowed for MIS) ──
    def _place_equity_stop(self, pos, last_price=None, on_placed=None) -> str:
        """Exchange-side protective stop for an intraday (MIS) position. Zerodha allows
        GTT only on CNC/NRML, never MIS — so a real SL-M order rests at the exchange
        instead: a LONG is protected by a SELL SL-M below the stop, a SHORT by a BUY SL-M
        above. The resting order id is kept in `pos.gtt_trigger_id` (the protective-stop
        id column). Governed by the same `gtt_stop_enabled` toggle as the option GTT; on
        failure the position is still managed by the bot's own risk-loop stop."""
        if pos is None or not self._gtt_enabled() or pos.stop_price <= 0:
            return "disabled"
        side = "BUY" if pos.direction == "SHORT" else "SELL"   # cover a short above / sell a long below
        exchange = self.venue.exchange_for(pos.exchange)
        try:
            oid = self.venue.place_protective_stop(
                ProtectiveStopKind.RESTING_STOP, tradingsymbol=pos.tradingsymbol,
                exchange=exchange, qty=pos.qty, trigger_price=pos.stop_price,
                side=side, tag=TAG)
        except PreWireProtectionRejected as e:
            log.error(f"SL-M rejected locally {pos.tradingsymbol}: {e}",
                      instrument=pos.instrument_key, event="STOP_PREWIRE_REJECT")
            return "prewire_rejected"
        except Exception as e:
            log.error_ratelimited(f"SL-M stop placement uncertain {pos.tradingsymbol}: {e}",
                                  key=f"{pos.tradingsymbol}:SLM_FAIL", event="STOP_FAIL",
                                  instrument=pos.instrument_key)
            self._notify(f"⚠️ SL-M stop placement uncertain for {pos.tradingsymbol} — "
                         f"will reconcile before any retry ({e})")
            return "uncertain"
        if on_placed is not None:
            try:
                on_placed(str(oid))
            except Exception as e:
                log.error(f"SL-M acknowledgement persistence failed {pos.tradingsymbol}: {e}",
                          instrument=pos.instrument_key, event="STOP_PERSIST_FAIL")
                self._notify(f"⚠️ SL-M {oid} may be live for {pos.tradingsymbol}, but "
                             f"its acknowledgement was not durable; manual reconciliation "
                             f"is required.")
                return "uncertain"
        try:
            set_protective_order_id(pos, oid)
            self.s.commit()
            self._journal_stop(pos, oid, side)
            log.info(f"SL-M stop placed {pos.tradingsymbol} @ {pos.stop_price:.2f} (order {oid})",
                     instrument=pos.instrument_key, event="STOP_PLACE")
            return "protected"
        except Exception as e:
            self.s.rollback()
            log.error(f"SL-M id persistence failed {pos.tradingsymbol}: {e}",
                      instrument=pos.instrument_key, event="STOP_PERSIST_FAIL")
            self._notify(f"⚠️ SL-M may be live for {pos.tradingsymbol}, but its id could "
                         f"not be persisted; entry remains blocked and no duplicate will "
                         f"be sent until reconciliation ({e})")
            return "uncertain"

    def _journal_stop(self, pos, order_id, side: str) -> None:
        """Record a resting protective stop in the order journal.

        The journal's contract is "every real order the bot places", and the SL-M was the
        one exception — tracked only on the position, which meant that once the position
        closed, its (cancelled or filled) stop still sitting in the day's order book
        became unattributable and was reported as an orphan on every restart until
        midnight. Rows are written TERMINAL/RESTING deliberately: `recover_journal()`
        replays WORKING rows through the ENTRY/EXIT state machine, and a protective stop
        belongs to neither — its lifecycle is owned by `ensure_stop_protection` and the
        external-fill reconciliation. This row exists to make the order ACCOUNTABLE, not
        to hand it a second owner."""
        try:
            self.s.add(OrderJournal(
                owner_id=self.owner_id,
                broker_account_id=self.broker_account_id,
                deployment_id=self.deployment_id,
                order_id=str(order_id), tradingsymbol=pos.tradingsymbol,
                instrument_key=pos.instrument_key, side=side, kind="equity",
                intent="STOP", qty=pos.qty,
                context_json=json.dumps({"position_id": pos.id,
                                         "stop_price": pos.stop_price}),
                status="TERMINAL", resolution="RESTING",
                placed_at=self.provider.now()))
            self.s.commit()
        except Exception as e:
            self.s.rollback()
            log.error(f"journal stop record failed: {e}", event="JOURNAL_FAIL")

    def _cancel_equity_stop(self, oid, sym: str = "") -> bool:
        """Cancel a resting SL-M protective stop. Returns True on success (or nothing to
        cancel), False if the broker rejected it — the caller MUST NOT then send a closing
        order (the SL-M could still fire into it → oversell / a reversed position) and must
        not mark the position closed (that would orphan the resting SL-M)."""
        if not oid:
            return True
        try:
            self.venue.cancel_protective_stop(ProtectiveStopKind.RESTING_STOP, oid)
            log.info(f"SL-M {oid} cancelled ({sym})", event="STOP_CANCEL")
            return True
        except Exception as e:
            log.error(f"SL-M {oid} cancel failed: {e}", event="STOP_FAIL")
            self._notify(f"⚠️ could not cancel SL-M {oid} for {sym} — check/cancel it on Zerodha")
            return False

    def _cancel_gtt(self, gid, sym: str = "") -> bool:
        """Cancel a resting GTT. Returns True on success (or nothing to cancel), False if
        the broker rejected the cancel — the caller MUST NOT then send a closing order (a
        still-live GTT could fire into it → oversell / a reversed position) and must not
        mark the position closed (that would orphan the GTT)."""
        if not gid:
            return True
        try:
            self.venue.cancel_protective_stop(ProtectiveStopKind.SERVER_TRIGGER, gid)
            log.info(f"GTT {gid} cancelled ({sym})", event="GTT_DELETE")
            return True
        except Exception as e:
            log.error(f"GTT {gid} cancel failed: {e}", event="GTT_FAIL")
            self._notify(f"⚠️ could not cancel GTT {gid} for {sym} — check/cancel it on Zerodha")
            return False

    def ensure_stop_protection(self, pos, last_price) -> None:
        """Cheap per-tick check: if this open position has no resting exchange-side
        backstop (never placed, or an earlier placement attempt failed — e.g. the
        2026-07-08 LODHA tick-size rejection), place one now. A single attribute
        check once a backstop exists, so it's safe to call every risk-loop tick
        regardless of whether the stop ratcheted — a position that never ratchets
        (flat or underwater all session) still gets its missing stop retried."""
        if protective_order_id(pos) or not self._gtt_enabled():
            return
        lp = last_price or pos.last_premium or pos.entry_premium
        if protective_kind_for_book_segment(pos.segment) is ProtectiveStopKind.RESTING_STOP:
            self._place_equity_stop(pos, lp)
        else:
            self._place_gtt(pos, lp)

    def update_stop_protection(self, pos, last_price) -> bool:
        if not self._gtt_enabled():
            return False
        gid = protective_order_id(pos)
        if not gid:
            # never placed, or an earlier attempt failed — place fresh at the
            # ratcheted level instead of silently no-op'ing forever.
            self.ensure_stop_protection(pos, last_price)
            return bool(protective_order_id(pos))
        lp = last_price or pos.last_premium or pos.entry_premium
        if protective_kind_for_book_segment(pos.segment) is ProtectiveStopKind.RESTING_STOP:
            # If the ratcheted stop is already crossed by LTP it fires THIS risk-loop
            # tick (the close cancels the SL-M) — a modify now only draws the same
            # permissible-range rejection. Leave the resting stop; the internal stop exits.
            if self._equity_stop_crossed(pos, lp):
                return False
            try:
                # tradingsymbol/exchange let the client resolve the SAME real tick the
                # initial SL-M placement used, instead of falling back to 0.05.
                self.venue.modify_protective_stop(
                    ProtectiveStopKind.RESTING_STOP, gid,
                    tradingsymbol=pos.tradingsymbol,
                    exchange=self.venue.exchange_for(pos.exchange),
                    qty=pos.qty, trigger_price=pos.stop_price)
                log.info(f"SL-M {gid} trailed → {pos.stop_price:.2f} ({pos.tradingsymbol})",
                         instrument=pos.instrument_key, event="STOP_MODIFY")
                return True
            except Exception as e:
                # 2026-07-13 SUZLON: a rejected trigger modify left the exchange SL-M stale
                # at the old level while the internal stop moved (silent divergence). Don't
                # diverge — cancel the stale resting stop and place a fresh one at the new
                # trigger so the exchange backstop tracks the ratcheted internal stop.
                log.warn(f"SL-M trigger modify rejected {pos.tradingsymbol}: {e} — cancel+replacing",
                         instrument=pos.instrument_key, event="STOP_MODIFY_REJECT")
                return self._resync_equity_stop(pos, gid)
        try:
            # options backstop is a GTT (long premium → protective SELL).
            self.venue.modify_protective_stop(
                ProtectiveStopKind.SERVER_TRIGGER, gid,
                tradingsymbol=pos.tradingsymbol,
                exchange=self.venue.exchange_for(pos.exchange),
                qty=pos.qty, trigger_price=pos.stop_price, last_price=lp, side="SELL")
            log.info(f"GTT {gid} trailed → {pos.stop_price:.2f} ({pos.tradingsymbol})",
                     instrument=pos.instrument_key, event="GTT_MODIFY")
            return True
        except Exception as e:
            # E3 (the SUZLON class, options edition): only logging here left the exchange
            # GTT resting at the OLD, looser trigger while the internal stop ratcheted up
            # — and because gtt_trigger_id stayed set, ensure_stop_protection's self-heal
            # never retried. Cancel + replace so the backstop tracks the internal stop.
            log.warn(f"GTT trigger modify rejected {pos.tradingsymbol}: {e} — cancel+replacing",
                     instrument=pos.instrument_key, event="GTT_MODIFY_REJECT")
            return self._resync_option_gtt(pos, gid, lp)

    def _equity_stop_crossed(self, pos, lp) -> bool:
        """Is the intraday stop already triggering at the current mark? (SHORT stops
        ABOVE, LONG stops BELOW.) When true, the internal risk-loop stop fires this tick,
        so we skip the exchange modify to avoid a guaranteed permissible-range reject."""
        if not lp or pos.stop_price <= 0:
            return False
        return lp >= pos.stop_price if pos.direction == "SHORT" else lp <= pos.stop_price

    def _gtt_fired(self, gid, sym: str) -> bool:
        """Did this resting GTT already trigger? Conservative: no id, a client that
        doesn't implement `gtt_status`, or any read failure all answer False — the caller
        then treats the close as external, which keeps the (safe) re-entry block rather
        than silently skipping it on a guess."""
        if not gid:
            return False
        try:
            # The venue normalises both shapes — its own flag and a raw kite.get_gtt()
            # status string — and answers a not-triggered False for a client that cannot
            # report at all, which is the same conservative fallback this method has
            # always applied.
            state = self.venue.protective_stop_state(
                ProtectiveStopKind.SERVER_TRIGGER, gid)
            return bool((state or {}).get("triggered"))
        except Exception as e:
            log.warn(f"GTT STATUS {sym}: gtt_status({gid}) read failed: {e} — treating as "
                     f"external exit (conservative fallback)", event="GTT_STATUS_FAIL")
            return False

    def _resync_option_gtt(self, pos, gid, last_price) -> bool:
        """Cancel a stale options GTT and place a fresh one at `pos.stop_price` so the
        exchange backstop tracks the ratcheted internal stop. Mirrors
        `_resync_equity_stop`: if the cancel is refused, DO NOT place a second GTT (it
        could fire into the first → oversell) — leave the still-protective stale one and
        alert. If the replace fails, `gtt_trigger_id` is left None so
        `ensure_stop_protection` retries it on the next risk tick."""
        if not self._cancel_gtt(gid, pos.tradingsymbol):
            log.error(f"GTT resync ABORTED {pos.tradingsymbol} — cancel refused; stale GTT "
                      f"still resting at the old trigger, internal stop is authoritative",
                      instrument=pos.instrument_key, event="GTT_RESYNC_ABORT")
            self._notify(f"⚠️ {pos.tradingsymbol}: couldn't re-sync the exchange GTT (cancel "
                         f"refused) — verify on Zerodha; bot-managed stop still active")
            return False
        clear_protective_order_id(pos)
        self.s.commit()
        outcome = self._place_gtt(pos, last_price)  # places at pos.stop_price
        if not protective_order_id(pos):
            log.error(f"GTT resync REPLACE failed {pos.tradingsymbol} — no exchange stop "
                      f"resting; bot-managed stop only until retry",
                      instrument=pos.instrument_key, event="GTT_RESYNC_FAIL")
            self._notify(f"🚫 {pos.tradingsymbol}: exchange GTT NOT re-placed — bot-managed "
                         f"stop only until it retries; verify on Zerodha")
            return False
        else:
            log.info(f"GTT resync recovered {pos.tradingsymbol} @ {pos.stop_price:.2f} "
                     f"(gtt {protective_order_id(pos)})", instrument=pos.instrument_key,
                     event="GTT_RESYNC_RECOVERED")
            return outcome == "protected"

    def _resync_equity_stop(self, pos, gid) -> bool:
        """Cancel a stale resting SL-M and place a fresh one at `pos.stop_price` so the
        exchange backstop tracks the ratcheted internal stop. If the cancel is refused,
        DO NOT place a second stop (oversell risk) — leave the still-protective stale one
        and alert. If the replace fails, the position is exchange-unprotected (bot-managed
        stop only) — alert; `ensure_stop_protection` retries it next tick."""
        if not self._cancel_equity_stop(gid, pos.tradingsymbol):
            log.error(f"SL-M resync ABORTED {pos.tradingsymbol} — cancel refused; stale stop "
                      f"still resting at the old trigger, internal stop is authoritative",
                      instrument=pos.instrument_key, event="STOP_RESYNC_ABORT")
            self._notify(f"⚠️ {pos.tradingsymbol}: couldn't re-sync the exchange stop (cancel "
                         f"refused) — verify on Zerodha; bot-managed stop still active")
            return False
        clear_protective_order_id(pos)
        self.s.commit()
        outcome = self._place_equity_stop(
            pos, pos.last_spot or pos.last_premium)   # places at pos.stop_price
        if not protective_order_id(pos):
            log.error(f"SL-M resync REPLACE failed {pos.tradingsymbol} — no exchange stop resting; "
                      f"bot-managed stop only until retry", instrument=pos.instrument_key,
                      event="STOP_RESYNC_FAIL")
            self._notify(f"🚫 {pos.tradingsymbol}: exchange stop NOT re-placed — bot-managed stop "
                         f"only until it retries; verify on Zerodha")
            return False
        else:
            # today this recovery was silent — the 2026-07-15 autopsy could not confirm
            # any recovery ever happened. Log it explicitly so it's visible in the
            # Engine/Logs console and searchable in the journal.
            log.info(f"SL-M resync recovered {pos.tradingsymbol} @ {pos.stop_price:.2f} "
                     f"(order {protective_order_id(pos)})", instrument=pos.instrument_key,
                     event="STOP_RESYNC_RECOVERED")
            return outcome == "protected"

    def reconcile_orphans(self, now) -> list:
        """If the live account no longer backs a bot position (a GTT/SL-M fired, you
        exited it, or it expired — typically while the bot was down), book it closed
        in the ledger WITHOUT sending any order, and cancel its resting GTT/SL-M.

        R3 — an equity position's OWN exchange-side SL-M filling looks identical to a
        genuinely external exit from the account-flat read alone (both leave the
        account flat). Before booking one as external, the resting stop order's own
        status is checked: COMPLETE-with-a-fill means the bot's own stop closed it, so
        it's booked STOP_LOSS at the real fill price and NOT returned for the runner's
        same-day re-entry auto-block (only genuinely external closes are returned).

        L8 — booking requires the position to read orphaned on `orphan_confirm_count`
        CONSECUTIVE passes; a single >60s feed glitch that looks like an exit no longer
        phantom-closes a still-open real position. Any read where the account backs the
        position (or it is no longer open) resets the streak."""
        from app.core.config import get_settings
        from app.engine.reconcile import find_orphans
        need = int(getattr(self.settings, "orphan_confirm_count", 2) or 1)
        acct = self.provider.account_positions()
        orphans = find_orphans(self.open_positions(), acct)
        orphan_keys = {p.instrument_key for p in orphans}
        # reset the streak for anything no longer seen as orphaned (backed again, or gone)
        for k in list(self._orphan_seen):
            if k not in orphan_keys:
                del self._orphan_seen[k]
        booked = []
        for pos in orphans:
            if (now - pos.entry_time).total_seconds() < 60:
                continue  # just opened — the account feed may simply be lagging
            k = pos.instrument_key
            self._orphan_seen[k] = self._orphan_seen.get(k, 0) + 1
            if self._orphan_seen[k] < need:
                continue  # not enough consecutive confirmations yet — wait
            gid, sym = protective_order_id(pos), pos.tradingsymbol
            prem = pos.last_premium or pos.entry_premium
            # book through the segment's correct close (ledger-only, no order): equity
            # is margin-based and direction-aware; routing it through the options close
            # mistakes the released notional for profit (+₹40k on ₹10k margin) and
            # mislabels the trade 'options'.
            # NB this branch is about LEDGER BOOKING (equity margin maths vs options
            # premium maths), not about protection shape — `equity_intraday` is a
            # domain segment, not venue vocabulary, so it stays a segment test.
            if pos.segment == "equity_intraday":
                # R3 (2026-07-15 DLF incident): an account-flat read alone can't tell the
                # bot's OWN exchange-side SL-M firing apart from a genuinely external exit
                # — both leave the account flat. Ask the resting stop order itself first.
                # A COMPLETE fill means the bot's OWN protective stop is what closed this,
                # so it's booked STOP_LOSS at the real fill price (not last_premium), the
                # (already-dead) cancel is skipped, and it must NOT count as an external
                # exit — the runner blocks re-entry only on what this method returns.
                exit_price, reason, is_external = prem, "RECONCILED_EXTERNAL_EXIT", True
                estimated = True   # both fallback paths below book a MARK, not a fill
                if gid:
                    try:
                        st = self.client.status(gid)
                    except Exception as e:
                        log.warn(f"STOP STATUS {sym}: status({gid}) read failed: {e} — "
                                 f"treating as external exit (conservative fallback)",
                                 instrument=pos.instrument_key, event="STOP_STATUS_FAIL")
                    else:
                        st_status = str(st.get("status", "")).upper()
                        filled = int(st.get("filled_qty", 0) or 0)
                        avg = float(st.get("avg_price", 0.0) or 0.0)
                        if st_status == "COMPLETE" and filled > 0 and avg > 0:
                            exit_price, reason, is_external = avg, "STOP_LOSS", False
                            estimated = False   # a real fill from the stop order itself
                            log.info(f"SL-M FILLED at exchange — booked STOP_LOSS "
                                     f"{sym} @ {avg:.2f} (order {gid})",
                                     instrument=pos.instrument_key,
                                     event="STOP_FILL_RECONCILED")
                PaperBroker.close_equity_position(self, pos, exit_price, reason, now,
                                                  exit_price_estimated=estimated)
                if is_external:
                    self._cancel_equity_stop(gid, sym)   # pull the resting SL-M backstop
                prem = exit_price
            else:
                # E0.1: an external/reconciled options close was booked at last_premium
                # (a MARK) even though the account has the real fill on record — the
                # 2026-07-24 SENSEX put mispricing (bot recorded ~₹1,000, actual exit
                # +₹792 pre-charges). Ask the broker for the real SELL fill first, same
                # idea as R3 above; fall back to the mark only if none is found (or the
                # lookup itself fails), and tag that fallback as an estimate.
                exit_price, estimated = prem, True
                fill = None
                try:
                    fill = self.client.find_fill(sym, side="SELL")
                except Exception as e:
                    log.warn(f"FILL LOOKUP {sym}: find_fill failed: {e} — "
                             f"booking at last mark (conservative fallback)",
                             instrument=pos.instrument_key, event="FILL_LOOKUP_FAIL")
                    fill = None
                if fill and float(fill.get("avg_price", 0.0) or 0.0) > 0 \
                        and int(fill.get("filled_qty", 0) or 0) > 0:
                    exit_price, estimated = float(fill["avg_price"]), False
                    log.info(f"EXTERNAL CLOSE {sym} — real fill found @ {exit_price:.2f}, "
                             f"booked at the true fill (not the last mark)",
                             instrument=pos.instrument_key, event="EXTERNAL_FILL_RECONCILED")
                # E6: the equity branch asks its resting stop whether IT fired (R3); this
                # branch booked external unconditionally, so the bot's own GTT stop firing
                # was mislabelled RECONCILED_EXTERNAL_EXIT (corrupting the exit-reason
                # analytics the backtest-vs-live comparison rests on) and earned the
                # instrument a false same-day re-entry block. A trigger_id isn't an
                # order_id, so this needs the GTT's own state.
                fired = self._gtt_fired(gid, sym)
                reason = "STOP_LOSS" if fired else "RECONCILED_EXTERNAL_EXIT"
                PaperBroker.close_position(self, pos, exit_price, reason,
                                           now, pos.last_spot, exit_price_estimated=estimated)
                is_external = not fired
                if is_external:
                    self._cancel_gtt(gid, sym)      # a fired GTT is already dead
                else:
                    log.info(f"GTT FIRED at exchange — booked STOP_LOSS {sym} @ "
                             f"{exit_price:.2f} (gtt {gid})", instrument=pos.instrument_key,
                             event="GTT_FILL_RECONCILED")
                prem = exit_price
            self._orphan_seen.pop(k, None)
            if is_external:
                self._notify(f"ℹ️ {sym} is no longer in your account (GTT fired, manual "
                             f"exit, or expiry) — booked closed at ~{prem:.2f}; verify the "
                             f"fill on Zerodha")
                booked.append(pos.instrument_key)
            else:
                self._notify(f"✅ {sym}: your own SL-M stop filled at the exchange @ "
                             f"{prem:.2f} — booked STOP_LOSS")
        return booked

    def adopt_pending_entries(self, now) -> list:
        """Re-query each bot ENTRY order that timed out with no confirmed fill. If it has
        since FILLED and the book doesn't already track that instrument, ADOPT it: book the
        real fill and rest its SL-M stop — so a fill that landed after the poll window (a
        pre-open uncross, a slow open) becomes a managed, stopped position instead of an
        invisible, stopless orphan the engine keeps re-entering (the BSE 2026-07-03
        incident, #17). Dead orders (rejected/cancelled, no fill) are dropped; still-working
        ones are kept for the next pass."""
        adopted = []
        for sym, ctx in list(self._pending_entries.items()):
            if not ctx.get("order_id"):
                continue
            try:
                st = self.client.status(ctx["order_id"])
            except Exception as e:
                log.error(f"ADOPT {sym}: status({ctx['order_id']}) read failed: {e}",
                          event="ADOPT_FAIL")
                continue   # transient — retry next pass
            status = str(st.get("status", "")).upper()
            filled = int(st.get("filled_qty", 0) or 0)
            avg = float(st.get("avg_price", 0.0) or 0.0)
            payload = {"status": status, "filled_qty": filled, "avg_price": avg,
                       "reason": str(st.get("reason", "") or "")}
            source_event_id = broker_observation_id(str(ctx["order_id"]), payload)
            existing_event = self.s.scalar(select(ExecutionOrderEvent).where(
                ExecutionOrderEvent.client_intent_id == ctx.get("client_intent_id"),
                ExecutionOrderEvent.owner_id == self.owner_id,
                ExecutionOrderEvent.broker_account_id == self.broker_account_id,
                ExecutionOrderEvent.source == "broker",
                ExecutionOrderEvent.source_event_id == source_event_id,
            ))
            if existing_event is None and ctx.get("client_intent_id"):
                try:
                    ExecutionLifecycleStore(
                        self.s, owner_id=self.owner_id,
                        broker_account_id=self.broker_account_id).append_event(
                        ctx["client_intent_id"],
                        NewExecutionEvent(
                            source="broker", source_event_id=source_event_id,
                            kind="STATUS_OBSERVED", broker_order_id=str(ctx["order_id"]),
                            broker_status=status, cumulative_filled_qty=filled,
                            avg_price=avg, payload=payload),
                        self.lifecycle_clock())
                except Exception as e:
                    log.error(f"ADOPT {sym}: status persistence failed: {e}",
                              event="LIFECYCLE_FAIL")
                    continue
            if filled > 0 and avg > 0:
                inst = ctx["inst"]
                client_intent_id = ctx.get("client_intent_id")
                if not client_intent_id:
                    existing = self.position_for(
                        inst.key, deployment_id=self.deployment_id)
                    pos = existing
                    if existing is None:
                        if ctx.get("kind") == "options":
                            q = ctx["q"]
                            pos = super().open_position(
                                inst, ctx["direction"],
                                replace(q, ltp=avg, lot_size=filled),
                                ctx["reason"], now, ctx["spot"], ctx["params"])
                            pos.lot_size = q.lot_size
                            self.s.commit()
                            self._place_gtt(pos, avg)
                        else:
                            pos = super().open_equity_position(
                                inst, ctx["direction"], avg, filled,
                                ctx["charge_segment"], ctx["reason"], now,
                                ctx["params"], ctx.get("strategy_key"),
                                ctx.get("strategy_version"),
                                margin=ctx.get("margin"),
                                sl_pct=ctx.get("sl_pct"), tp_pct=ctx.get("tp_pct"))
                            self._place_equity_stop(pos, avg)
                    if ((status == "COMPLETE" or status in _DEAD_STATUSES)
                            and protective_order_id(pos)):
                        self.journal_mark_terminal(
                            ctx["order_id"], "ADOPTED", filled, avg)
                        self._pending_entries.pop(sym, None)
                        self._inflight.pop(sym, None)
                    continue
                lifecycle_state = ExecutionLifecycleStore(
                    self.s, owner_id=self.owner_id,
                    broker_account_id=self.broker_account_id).state_for(
                    client_intent_id)
                pos = self.s.scalar(select(Position).where(
                    Position.entry_intent_id == ctx.get("client_intent_id"),
                    Position.deployment_id == self.deployment_id,
                    Position.owner_id == self.owner_id,
                    Position.broker_account_id == self.broker_account_id,
                ))
                existing = self.position_for(inst.key, deployment_id=self.deployment_id)
                if pos is None and existing is not None:
                    log.error(
                        f"ADOPT {sym}: existing position {existing.id} is not linked to "
                        f"entry intent {ctx['client_intent_id']} — left blocked",
                        event="ADOPT_CONFLICT",
                    )
                    self._notify(
                        f"⚠️ {sym}: recovered fill conflicts with an unrelated open "
                        f"position; entry remains blocked for manual review."
                    )
                    continue
                if pos is None:
                    if ctx.get("kind") == "options":
                        # C3: adopt an options late fill and rest its GTT backstop, mirroring
                        # the live open_position booking (real filled qty at the real price).
                        q = ctx["q"]
                        pos = super().open_position(
                            inst, ctx["direction"], replace(q, ltp=avg, lot_size=filled),
                            ctx["reason"], now, ctx["spot"], ctx["params"],
                            strategy_key=ctx.get("strategy_key"),
                            strategy_version=ctx.get("strategy_version"),
                            entry_intent_id=ctx.get("client_intent_id"))
                        pos.lot_size = q.lot_size
                        self.s.commit()
                    else:
                        requested_qty = int(ctx.get("requested_qty") or filled)
                        margin = ctx.get("margin")
                        fill_margin = (
                            float(margin) * filled / requested_qty
                            if margin is not None and float(margin) > 0 and requested_qty > 0
                            else None
                        )
                        pos = super().open_equity_position(
                            inst, ctx["direction"], avg, filled, ctx["charge_segment"],
                            ctx["reason"], now, ctx["params"], ctx["strategy_key"],
                            ctx.get("strategy_version"),
                            margin=fill_margin,
                            sl_pct=ctx.get("sl_pct"), tp_pct=ctx.get("tp_pct"),
                            entry_intent_id=ctx.get("client_intent_id"))
                    log.warn(f"ADOPTED late fill {sym} {filled}@{avg:.2f} — was untracked; "
                             f"now managed + stopped", instrument=inst.key, event="ADOPT_FILL")
                    self._notify(f"ℹ️ {sym}: a bot order filled late ({filled}@{avg:.2f}) — "
                                 f"adopted into the book with a stop; verify on Zerodha")
                    adopted.append(inst.key)
                    first_result = OrderResult(
                        "FILLED" if status == "COMPLETE" else "PARTIAL",
                        ctx["order_id"], filled, avg,
                        "complete" if status == "COMPLETE" else "partial fill",
                    )
                    if not self._ensure_entry_protected(
                            pos, avg, ctx["client_intent_id"]):
                        continue
                    if not self._mark_position_booked(
                            ctx["client_intent_id"], ctx.get("row_id"), pos,
                            first_result, filled, avg):
                        continue
                    lifecycle_state = ExecutionLifecycleStore(
                        self.s, owner_id=self.owner_id,
                        broker_account_id=self.broker_account_id).state_for(
                        ctx["client_intent_id"])
                elif pos.qty > lifecycle_state.booked_qty:
                    # The ledger commit won a crash race against POSITION_BOOKED.
                    # Close that durable gap before considering any newer broker fill.
                    if not self._ensure_entry_protected(
                            pos, pos.last_premium or pos.entry_premium,
                            ctx["client_intent_id"]):
                        continue
                    gap_result = OrderResult(
                        "FILLED" if status == "COMPLETE" else "PARTIAL",
                        ctx["order_id"], pos.qty, pos.entry_premium,
                        "ledger position recovered",
                    )
                    if not self._mark_position_booked(
                            ctx["client_intent_id"], ctx.get("row_id"), pos,
                            gap_result, pos.qty, pos.entry_premium):
                        continue
                    lifecycle_state = ExecutionLifecycleStore(
                        self.s, owner_id=self.owner_id,
                        broker_account_id=self.broker_account_id).state_for(
                        ctx["client_intent_id"])
                if pos is not None and filled > lifecycle_state.booked_qty:
                    # POSITION_BOOKED is the durable debit watermark. The Position
                    # must agree with it before applying the next cumulative delta.
                    if pos.qty != lifecycle_state.booked_qty:
                        log.error(
                            f"ADOPT {sym}: ledger qty {pos.qty} disagrees with durable "
                            f"booked qty {lifecycle_state.booked_qty} — left blocked",
                            event="ADOPT_CONFLICT",
                        )
                        continue
                    old_qty = pos.qty
                    old_cost = pos.entry_cost
                    stop_ratio = pos.stop_price / pos.entry_premium
                    target_ratio = pos.target_price / pos.entry_premium
                    if ctx.get("kind") == "options":
                        charges = compute_charges(pos.exchange, "BUY", avg, filled)["total"]
                        new_cost = avg * filled + charges
                    else:
                        entry_side, _ = legs_for(pos.direction)
                        charges = compute_charges(pos.exchange, entry_side, avg, filled)["total"]
                        margin_per_unit = (old_cost - pos.entry_charges) / old_qty
                        new_cost = margin_per_unit * filled + charges
                    cap = self.capital()
                    cap.cash -= new_cost - old_cost
                    cap.updated_at = now
                    pos.qty = filled
                    pos.entry_premium = avg
                    pos.entry_charges = charges
                    pos.entry_cost = new_cost
                    pos.stop_price = avg * stop_ratio
                    pos.target_price = avg * target_ratio
                    pos.last_premium = avg
                    pos.last_mark_time = now
                    try:
                        self.s.commit()
                    except Exception as e:
                        self.s.rollback()
                        log.error(f"ADOPT {sym}: cumulative ledger commit failed: {e}",
                                  event="ADOPT_FAIL")
                        continue
                    result = OrderResult(
                        "FILLED" if status == "COMPLETE" else "PARTIAL",
                        ctx["order_id"], filled, avg,
                        "complete" if status == "COMPLETE" else "partial fill at timeout")
                    if not self._ensure_entry_protected(
                            pos, avg, ctx["client_intent_id"]):
                        continue
                    if not self._mark_position_booked(
                            ctx["client_intent_id"], ctx.get("row_id"), pos,
                            result, filled, avg):
                        continue
                if status == "COMPLETE" or status in _DEAD_STATUSES:
                    result = OrderResult(
                        "FILLED" if status == "COMPLETE" else "PARTIAL",
                        ctx["order_id"], filled, avg,
                        "complete" if status == "COMPLETE" else "cancelled after partial")
                    if not self._ensure_entry_protected(
                            pos, avg, ctx["client_intent_id"]):
                        continue
                    if not self._mark_position_booked(
                            ctx["client_intent_id"], ctx.get("row_id"), pos,
                            result, filled, avg):
                        continue
                    self._pending_entries.pop(sym, None)
                    self._inflight.pop(sym, None)
            elif status in _DEAD_STATUSES:
                self.journal_mark_terminal(ctx["order_id"], "DEAD")   # H13
                self._pending_entries.pop(sym, None)   # died with no fill — nothing to adopt
        return adopted
