"""
The paper broker. Simulates fills at the contract LTP, books realistic charges,
and keeps the persistent capital ledger.

Every open position has removed (premium×qty + entry charges) from cash; closing
adds back (exit_premium×qty − exit charges) and folds the net into realized P&L.
This keeps the reconciliation invariant in models.py true at all times.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from decimal import Decimal

from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.market_hours import now_ist
from app.core.instruments import Instrument
from app.core.logging import log
from app.db.models import (
    BrokerAccount,
    LEGACY_BROKER_ACCOUNT_ID,
    LEGACY_DEPLOYMENT_ID,
    CapitalState,
    EquitySnapshot,
    Position,
    Trade,
)
from app.db.session import SessionLocal
from app.core.runtime_config import effective
from app.core.execution_book import book_of, capital_for_book
from app.engine.charges import (
    CORRECTED_RESEARCH_CHARGE_SCHEDULE,
    DEFAULT_RUNTIME_CHARGE_SCHEDULE,
    ZERODHA_CHARGES_V1,
    ZERODHA_CHARGES_V2,
    ChargeScheduleRefusal,
    allocate_minor_units,
    charge_schedule_document,
    compute_charges,
    legs_for,
    monetary_minor,
)
from app.engine.equity_entry import equity_stop_target
from app.providers.base import MarketDataProvider, OptionQuote


_PAPER_V2_SEGMENTS = frozenset({"NFO", "BFO"})
_PAPER_CHARGE_RECEIPT_SCHEME_V1 = "paper-charge-result/1"
_PAPER_CHARGE_RECEIPT_SCHEME_V2 = "paper-charge-result/2"
_PAPER_INTENT_CONTEXT_JSON = '{"schema":"paper-entry-lifecycle/1"}'


class PaperBroker:
    MODE = "paper"   # stamped on every Position/Trade this broker creates (LiveBroker overrides to "live")
    _OPERATIONAL_LOG_LEVELS = frozenset({"trade", "info", "warn", "error"})
    _OPERATIONAL_LOG_MODES = frozenset({"paper", "live"})
    _OPERATIONAL_LOG_EVENTS = frozenset({
        "PAPER_EXIT_LIFECYCLE_UNKNOWN", "OPEN", "OPEN_EQUITY", "CLOSE_EQUITY",
        "MANUAL_OPEN", "REINFORCE", "OPEN_FUTURES", "CLOSE_FUTURES", "CLOSE",
        "PARTIAL_CLOSE", "PARTIAL_CLOSE_EQUITY", "PARTIAL_CLOSE_FUTURES",
    })
    _OPERATIONAL_LOG_OUTCOMES = frozenset({"APPLIED", "DEGRADED"})

    def __init__(self, provider: MarketDataProvider, deployment_id: int = LEGACY_DEPLOYMENT_ID,
                 *, owner_id: str, broker_account_id: str, execution_lease_token=None) -> None:
        self.provider = provider
        self.settings = get_settings()
        self.s = SessionLocal()
        self.execution_lease_token = execution_lease_token
        if execution_lease_token is not None:
            from app.execution.leases import LeaseRepository
            LeaseRepository.bind_money_session(self.s, execution_lease_token)
        # Which book this broker writes into. Every Position/Trade/EquitySnapshot it
        # creates is stamped with it, so attribution is a property of the write path
        # rather than something reconstructed later from timestamps and guesswork.
        # Defaults to the legacy deployment, which is what the single existing book
        # is — so this changes nothing until a second deployment exists.
        self.deployment_id = deployment_id
        self.owner_id = owner_id
        # Which *book* this broker reads and writes. Distinct from `deployment_id`:
        # a deployment says which strategy configuration is trading, a book says whose
        # money it is. Resolved from the object actually built, and fail-closed to live
        # (`core/execution_book.py`) — a broker that cannot say which book it writes to
        # must not be assumed harmless.
        self.book = book_of(self)
        self.broker_account_id = broker_account_id
        account = self.s.scalar(select(BrokerAccount).where(
            BrokerAccount.broker_account_id == self.broker_account_id,
            BrokerAccount.owner_id == self.owner_id,
            BrokerAccount.status == "active",
        ))
        if account is None:
            self.s.close()
            raise ValueError("broker account is not available to this owner")
        self.account = account
        # Attribute this book's ledger once, here, at construction. Doing it lazily on
        # the first `capital()` call would put a bootstrap write in the middle of a fill.
        capital_for_book(self.s, self.book, broker_account_id=self.broker_account_id)

    def _operational_log(self, level: str, event: str, outcome: str) -> None:
        """Emit one bounded operational fact; the paper ledger owns all detail."""
        if level not in self._OPERATIONAL_LOG_LEVELS:
            raise ValueError("unsupported paper operational log level")
        if event not in self._OPERATIONAL_LOG_EVENTS:
            raise ValueError("unsupported paper operational log event")
        if outcome not in self._OPERATIONAL_LOG_OUTCOMES:
            raise ValueError("unsupported paper operational log outcome")
        if self.MODE not in self._OPERATIONAL_LOG_MODES:
            raise ValueError("unsupported paper operational log mode")
        emitted_level = "warning" if level == "warn" else level
        log.emit(emitted_level, "Paper broker event", event=event, mode=self.MODE, outcome=outcome)

    def _is_legacy_recovery_intent(self, intent, entry_intent_id: str | None) -> bool:
        """Only a persisted legacy intent can justify a receiptless recovered fill.

        Do not trust a caller-supplied ORM object: it may be transient or forged. The
        row is read again by primary key at booking time.
        """
        from app.db.models import ExecutionIntent
        if not isinstance(intent, ExecutionIntent) or not entry_intent_id:
            return False
        with self.s.no_autoflush:
            persisted = self.s.scalar(select(ExecutionIntent).where(
                ExecutionIntent.client_intent_id == entry_intent_id,
                ExecutionIntent.owner_id == self.owner_id,
                ExecutionIntent.broker_account_id == self.broker_account_id,
                ExecutionIntent.deployment_id == self.deployment_id,
                ExecutionIntent.admission_address.is_(None),
            ))
        return persisted is not None and persisted is intent

    def _is_persisted_entry_intent(self, intent, *, entry_intent_id: str | None,
                                   admission_address: str | None,
                                   strategy_key: str | None,
                                   strategy_version: str | None,
                                   graph_address: str | None,
                                   attribution_state: str) -> bool:
        """Accept booking only from the exact durable intent that caused a fill.

        This is not a public ``legacy_recovery`` switch.  It requires the caller's
        ORM object to be the session's persisted row, scoped to this owner/account/
        deployment, with the same immutable attribution.  It is used after a real
        broker submit, when a second current-registry check could strand an already
        filled order if helpers changed in the short interval before booking.
        """
        from app.db.models import ExecutionIntent
        if not isinstance(intent, ExecutionIntent) or not entry_intent_id:
            return False
        with self.s.no_autoflush:
            persisted = self.s.scalar(select(ExecutionIntent).where(
                ExecutionIntent.client_intent_id == entry_intent_id,
                ExecutionIntent.owner_id == self.owner_id,
                ExecutionIntent.broker_account_id == self.broker_account_id,
                ExecutionIntent.deployment_id == self.deployment_id,
                ExecutionIntent.admission_address == admission_address,
                ExecutionIntent.strategy_key == strategy_key,
                ExecutionIntent.strategy_version == strategy_version,
                ExecutionIntent.graph_address == graph_address,
                ExecutionIntent.attribution_state == attribution_state,
            ))
        return persisted is not None and persisted is intent

    @staticmethod
    def _paper_product(segment: str | None) -> str | None:
        if segment == "equity_intraday":
            return "MIS"
        if segment == "index_futures":
            return "NRML"
        return None

    @staticmethod
    def _paper_identity_collision(exc: IntegrityError) -> bool:
        detail = str(getattr(exc, "orig", exc)).lower()
        identity = (
            "execution_intents.client_intent_id" in detail
            or "execution_intents.broker_tag" in detail
        )
        return identity and ("unique" in detail or "duplicate" in detail)

    @staticmethod
    def _intent_matches_entry(intent, expected: dict) -> bool:
        return all(getattr(intent, key) == value for key, value in expected.items())

    def _lock_unused_paper_intent(self, entry_intent_id: str, expected: dict):
        """Serialize one Paper lifecycle claim and refuse durable reuse.

        PostgreSQL locks the intent row. SQLite takes its database write reservation
        before the reference scan. The caller then books Position and capital in the
        same transaction, so a waiter can only proceed after seeing the first effect.
        """
        from app.db.models import ExecutionIntent

        self.s.commit()
        dialect = self.s.get_bind().dialect.name
        if dialect == "sqlite":
            self.s.connection().exec_driver_sql("BEGIN IMMEDIATE")
            statement = select(ExecutionIntent).where(
                ExecutionIntent.client_intent_id == entry_intent_id)
        elif dialect == "postgresql":
            account = self.s.scalar(select(BrokerAccount).where(
                BrokerAccount.broker_account_id == self.broker_account_id,
                BrokerAccount.owner_id == self.owner_id,
            ).with_for_update())
            if account is None:
                self.s.rollback()
                raise ValueError("ENTRY_INTENT_SCOPE_MISMATCH")
            statement = select(ExecutionIntent).where(
                ExecutionIntent.client_intent_id == entry_intent_id).with_for_update()
        else:
            raise RuntimeError("Paper entry intent requires SQLite or PostgreSQL")
        intent = self.s.scalar(statement)
        if intent is None or not self._intent_matches_entry(intent, expected):
            self.s.rollback()
            raise ValueError("ENTRY_INTENT_SCOPE_MISMATCH")
        already_used = (
            self.s.scalar(select(Position.id).where(
                Position.entry_intent_id == entry_intent_id).limit(1)) is not None
            or self.s.scalar(select(Trade.id).where(
                Trade.entry_intent_id == entry_intent_id).limit(1)) is not None
        )
        if already_used:
            self.s.rollback()
            raise ValueError("ENTRY_INTENT_ALREADY_USED")
        return intent

    def _prepare_paper_entry_intent(
        self,
        *,
        entry_intent_id: str | None,
        recovery_intent,
        instrument_key: str,
        tradingsymbol: str,
        exchange: str,
        side: str,
        segment: str | None,
        qty: int,
        decision_price: float,
        now: dt.datetime,
        strategy_key: str | None,
        strategy_version: str | None,
        admission_address: str | None,
        graph_address: str | None,
        attribution_state: str,
        runtime_context_json: str | None = None,
    ) -> str | None:
        """Persist or require one canonical identity before any Paper money effect."""
        if self.MODE != "paper":
            return entry_intent_id

        from app.db.models import ExecutionIntent

        from app.db.migrate import validate_paper_entry_lifecycle_manifest
        try:
            validate_paper_entry_lifecycle_manifest(self.s.connection())
        except RuntimeError as exc:
            raise RuntimeError(
                "PAPER_ENTRY_LIFECYCLE_SCHEMA_STALE: exact accepted 0045/0046 required"
            ) from exc

        if runtime_context_json is not None:
            from app.paper_runtime.contracts import validate_runtime_context_json

            if entry_intent_id is None:
                raise ValueError("RUNTIME_CONTEXT_REQUIRES_DURABLE_INTENT")
            try:
                runtime_context = validate_runtime_context_json(
                    runtime_context_json, client_intent_id=entry_intent_id,
                    broker_owner_id=self.owner_id,
                    broker_account_id=self.broker_account_id,
                    broker_deployment_id=self.deployment_id,
                    broker_fence_epoch=getattr(
                        self.execution_lease_token, "fence_epoch", None))
            except ValueError as exc:
                raise ValueError("PAPER_RUNTIME_CONTEXT_INVALID") from exc
            runtime_authority = runtime_context["instrument_authority"]
            expected_runtime_action = "BUY" if side == "BUY" else "SELL"
            if (runtime_context["action"] != expected_runtime_action
                    or runtime_context["instrument_key"] != instrument_key
                    or runtime_context["approved_quantity"] != qty
                    or Decimal(runtime_context["entry_reference"]) != Decimal(str(decision_price))
                    or runtime_authority["strategy_key"] != strategy_key
                    or runtime_authority["strategy_version"] != strategy_version
                    or runtime_context["admission_address"] != admission_address
                    or runtime_authority["graph_address"] != graph_address
                    or runtime_authority["attribution_state"] != attribution_state
                    or runtime_authority["charge_segment"] != exchange):
                raise ValueError("PAPER_RUNTIME_CONTEXT_RELATION_MISMATCH")

        expected = {
            "deployment_id": self.deployment_id,
            "owner_id": self.owner_id,
            "broker_account_id": self.broker_account_id,
            "intent": "ENTRY",
            "instrument_key": instrument_key,
            "tradingsymbol": tradingsymbol,
            "exchange": exchange,
            "side": side,
            "product": self._paper_product(segment),
            "order_type": "MARKET",
            "requested_qty": qty,
            "limit_price": None,
            "decision_price": decision_price,
            "signal_at": now,
            "strategy_key": strategy_key,
            "strategy_version": strategy_version,
            "admission_address": admission_address,
            "graph_address": graph_address,
            "attribution_state": attribution_state,
        }
        if runtime_context_json is not None:
            expected["context_json"] = runtime_context_json
        if entry_intent_id is not None:
            with self.s.no_autoflush:
                intent = self.s.scalar(select(ExecutionIntent).where(
                    ExecutionIntent.client_intent_id == entry_intent_id))
            if (intent is None
                    or (recovery_intent is not None and intent is not recovery_intent)
                    or not self._intent_matches_entry(intent, expected)):
                raise ValueError("ENTRY_INTENT_SCOPE_MISMATCH")
        else:
            fence = self.s.info.get("execution_lease_token")
            for attempt in range(3):
                candidate = uuid.uuid4().hex
                intent = ExecutionIntent(
                    client_intent_id=candidate,
                    broker=self.account.broker,
                    account_scope=self.account.external_account_id,
                    connection_scope="paper",
                    broker_tag=f"pti-{candidate[:16]}",
                    fence_epoch=getattr(fence, "fence_epoch", None),
                    context_json=_PAPER_INTENT_CONTEXT_JSON,
                    created_at=now,
                    **expected,
                )
                self.s.add(intent)
                try:
                    self.s.commit()
                    entry_intent_id = candidate
                    break
                except IntegrityError as exc:
                    self.s.rollback()
                    if not self._paper_identity_collision(exc) or attempt == 2:
                        raise
            else:  # pragma: no cover - the loop either breaks or raises
                raise AssertionError("unreachable")
        self._lock_unused_paper_intent(entry_intent_id, expected)
        return entry_intent_id

    # ── ledger ────────────────────────────────────────────────────────────
    def capital(self) -> CapitalState:
        """This book's ledger row, claimed or created on first use.

        Was `self.s.get(CapitalState, 1)`. One row for both books made hard invariant 1
        (`cash == initial + realized − Σ open`) unprovable the moment a second book
        existed, because a paper fill debited the live book's cash."""
        return capital_for_book(self.s, self.book, broker_account_id=self.broker_account_id)

    def cash(self) -> float:
        return self.capital().cash

    def open_positions(self, deployment_id: int | None = None) -> list[Position]:
        """This book's open positions. **Book-scoped always; deployment-scoped on ask.**

        The two scopes are not the same kind of thing, and only one of them is optional.

        *Deployment* stays opt-in for the reason it always did: a read that misses a
        position is a position nobody marks, ratchets or exits, and hard invariant 2 says
        not getting out is worse than any other failure.

        *Book* is mandatory, and it is the one place this slice knowingly makes such a
        miss possible. It is still right, because the alternative is worse: this broker
        can only act on positions it can actually close. A `PaperBroker` holds no order
        client, so "exiting" a live position writes a close into the ledger while the
        contract stays open at Zerodha — a visible orphan becomes an invisible one. The
        residual is made loud instead of silent by
        `execution_book.foreign_book_positions`, reported at startup and on `/api/health`.
        """
        stmt = select(Position).where(
            Position.mode == self.book,
            Position.owner_id == self.owner_id,
            Position.broker_account_id == self.broker_account_id,
        )
        if deployment_id is not None:
            stmt = stmt.where(Position.deployment_id == deployment_id)
        return list(self.s.scalars(stmt))

    def position_for(self, key: str, deployment_id: int | None = None) -> Position | None:
        """This book's open position for `key` — see `open_positions` for the scoping.

        The unscoped form assumed at most ONE open position per instrument across the
        whole system. That was structurally true before deployments (audit finding C1) and
        it stops being true the moment paper and live coexist: the same instrument may be
        open in both books at once, holding different contracts at different prices.
        """
        stmt = select(Position).where(Position.instrument_key == key,
                                      Position.mode == self.book,
                                      Position.owner_id == self.owner_id,
                                      Position.broker_account_id == self.broker_account_id)
        if deployment_id is not None:
            stmt = stmt.where(Position.deployment_id == deployment_id)
        return self.s.scalar(stmt)

    def commit(self) -> None:
        self.s.commit()

    def _append_money_projection(self, *, state: str, aggregate_id: str,
                                 revision: str = "") -> None:
        """Append the position/trade/capital refresh fact before this owner commits."""
        from app.events.producers import append_execution_change
        digest = hashlib.sha256(
            f"{self.owner_id}\x1f{self.broker_account_id}\x1f{aggregate_id}\x1f{state}\x1f{revision}"
            .encode("utf-8")
        ).hexdigest()
        append_execution_change(
            self.s, owner_id=self.owner_id,
            broker_account_id=self.broker_account_id,
            aggregate_type="money_book", aggregate_id=str(aggregate_id),
            event_type="execution.money.changed", projection="money_book",
            producer_key=f"money:{digest}", facts={"state": state},
        )

    def _charge_schedule_id(self, segment: str) -> str:
        """Select v2 only for verified Paper options; live and gaps remain v1."""
        if self.MODE == "paper" and segment in _PAPER_V2_SEGMENTS:
            return CORRECTED_RESEARCH_CHARGE_SCHEDULE
        return DEFAULT_RUNTIME_CHARGE_SCHEDULE

    def _compute_charge(self, segment: str, side: str, price: float, qty: int) -> dict:
        answer = compute_charges(
            segment, side, price, qty,
            schedule_id=self._charge_schedule_id(segment),
        )
        if self.MODE == "paper":
            self._validated_schedule_pair(
                answer["schedule_id"], answer["schedule_address"], allow_unknown=False)
        return answer

    @staticmethod
    def _validated_schedule_pair(schedule_id: str | None,
                                 schedule_address: str | None, *,
                                 allow_unknown: bool) -> dict | None:
        """Return the exact frozen schedule document or reject the persisted pair.

        NULL/NULL is a historical fact, never a schedule selection. A half pair,
        unknown id or stale address cannot authorize a Paper money effect.
        """
        if schedule_id is None and schedule_address is None:
            if allow_unknown:
                return None
            raise ChargeScheduleRefusal(
                "CHARGE_AUTHORITY_MISSING", "Paper charge authority is required")
        if schedule_id is None or schedule_address is None:
            raise ChargeScheduleRefusal(
                "CHARGE_AUTHORITY_INCOMPLETE", "Paper charge authority pair is incomplete")
        schedule = charge_schedule_document(schedule_id)
        if schedule["address"] != schedule_address:
            raise ChargeScheduleRefusal(
                "CHARGE_SCHEDULE_STALE", "Paper charge schedule address does not match")
        return schedule

    def _paper_entry_authority(self, answer: dict) -> dict[str, str | None]:
        if self.MODE != "paper":
            return {
                "paper_entry_charge_schedule_id": None,
                "paper_entry_charge_schedule_address": None,
            }
        self._validated_schedule_pair(
            answer.get("schedule_id"), answer.get("schedule_address"), allow_unknown=False)
        return {
            "paper_entry_charge_schedule_id": answer["schedule_id"],
            "paper_entry_charge_schedule_address": answer["schedule_address"],
        }

    def _paper_trade_authority(self, position: Position,
                               exit_answer: dict) -> dict[str, str | None]:
        if self.MODE != "paper":
            return {
                "paper_entry_charge_schedule_id": None,
                "paper_entry_charge_schedule_address": None,
                "paper_exit_charge_schedule_id": None,
                "paper_exit_charge_schedule_address": None,
            }
        self._validated_schedule_pair(
            position.paper_entry_charge_schedule_id,
            position.paper_entry_charge_schedule_address,
            allow_unknown=True,
        )
        self._validated_schedule_pair(
            exit_answer.get("schedule_id"), exit_answer.get("schedule_address"),
            allow_unknown=False,
        )
        return {
            "paper_entry_charge_schedule_id": position.paper_entry_charge_schedule_id,
            "paper_entry_charge_schedule_address": position.paper_entry_charge_schedule_address,
            "paper_exit_charge_schedule_id": exit_answer["schedule_id"],
            "paper_exit_charge_schedule_address": exit_answer["schedule_address"],
        }

    def _exit_charge_answer(self, position: Position, side: str,
                            price: float, qty: int) -> dict:
        """Choose exit authority without inferring a missing historical entry."""
        if self.MODE != "paper":
            return compute_charges(
                position.exchange, side, price, qty,
                schedule_id=DEFAULT_RUNTIME_CHARGE_SCHEDULE,
            )
        entry_schedule = self._validated_schedule_pair(
            position.paper_entry_charge_schedule_id,
            position.paper_entry_charge_schedule_address,
            allow_unknown=True,
        )
        schedule_id = (
            entry_schedule["id"] if entry_schedule is not None
            else self._charge_schedule_id(position.exchange)
        )
        answer = compute_charges(
            position.exchange, side, price, qty, schedule_id=schedule_id)
        self._validated_schedule_pair(
            answer["schedule_id"], answer["schedule_address"], allow_unknown=False)
        return answer

    @staticmethod
    def _option_charge_sides(row) -> tuple[str, str]:
        if getattr(row, "segment", "options") == "options":
            return "BUY", "SELL"
        return legs_for(row.direction)

    def _paper_lifecycle_allocation(self, row, entry_schedule: dict,
                                    entry_side: str) -> bool:
        """Validate and reconstruct one lifecycle selected only by intent ID."""
        from app.db.models import ExecutionIntent

        if not row.entry_intent_id:
            raise ChargeScheduleRefusal(
                "CHARGE_ENTRY_LIFECYCLE_REQUIRED",
                "known Paper entry authority requires an entry intent",
            )
        intent = self.s.get(ExecutionIntent, row.entry_intent_id)
        expected_intent = {
            "deployment_id": row.deployment_id,
            "owner_id": row.owner_id,
            "broker_account_id": row.broker_account_id,
            "intent": "ENTRY",
            "instrument_key": row.instrument_key,
            "tradingsymbol": row.tradingsymbol,
            "exchange": row.exchange,
            "side": entry_side,
            "product": self._paper_product(row.segment or "options"),
            "order_type": "MARKET",
            "limit_price": None,
            "decision_price": row.entry_premium,
            "signal_at": row.entry_time,
            "strategy_key": row.strategy_key,
            "strategy_version": row.strategy_version,
            "admission_address": row.admission_address,
            "graph_address": row.graph_address,
            "attribution_state": row.attribution_state,
        }
        if intent is None or not self._intent_matches_entry(intent, expected_intent):
            raise ChargeScheduleRefusal(
                "CHARGE_ENTRY_LIFECYCLE_SCOPE",
                "Paper entry intent does not match the receipt row",
            )

        lifecycle_trades = list(self.s.scalars(select(Trade).where(
            Trade.entry_intent_id == row.entry_intent_id)))
        remaining_positions = list(self.s.scalars(select(Position).where(
            Position.entry_intent_id == row.entry_intent_id)))
        siblings = [*lifecycle_trades, *remaining_positions]
        scope_fields = (
            "owner_id", "broker_account_id", "deployment_id", "instrument_key",
            "tradingsymbol", "exchange", "direction", "entry_premium", "entry_time",
            "strategy_key", "strategy_version", "admission_address", "graph_address",
            "attribution_state",
        )
        if any(sibling.mode != "paper" for sibling in siblings):
            raise ChargeScheduleRefusal(
                "CHARGE_ENTRY_LIFECYCLE_SCOPE", "entry intent crosses execution books")
        if any((sibling.segment or "options") != (row.segment or "options")
               or any(getattr(sibling, field) != getattr(row, field)
                      for field in scope_fields)
               for sibling in siblings):
            raise ChargeScheduleRefusal(
                "CHARGE_ENTRY_LIFECYCLE_SCOPE", "entry intent crosses receipt scope")
        expected_pair = (entry_schedule["id"], entry_schedule["address"])
        if any((sibling.paper_entry_charge_schedule_id,
                sibling.paper_entry_charge_schedule_address) != expected_pair
               for sibling in siblings):
            raise ChargeScheduleRefusal(
                "CHARGE_ENTRY_LIFECYCLE_AUTHORITY",
                "Paper lifecycle entry authority is inconsistent",
            )
        lifecycle_qty = (
            sum(trade.qty for trade in lifecycle_trades)
            + sum(position.qty for position in remaining_positions)
        )
        lifecycle_entry_minor = (
            sum(monetary_minor(trade.charges_total)
                - monetary_minor(trade.exit_charges)
                for trade in lifecycle_trades)
            + sum(monetary_minor(position.entry_charges)
                  for position in remaining_positions)
        )
        if lifecycle_qty <= 0 or lifecycle_qty != intent.requested_qty:
            raise ChargeScheduleRefusal(
                "CHARGE_ENTRY_LIFECYCLE_QUANTITY",
                "Paper lifecycle quantity is inconsistent")
        lifecycle_answer = compute_charges(
            row.exchange, entry_side, row.entry_premium, lifecycle_qty,
            schedule_id=entry_schedule["id"],
        )
        if monetary_minor(lifecycle_answer["total"]) != lifecycle_entry_minor:
            raise ChargeScheduleRefusal(
                "CHARGE_ENTRY_LIFECYCLE_ALLOCATION",
                "Paper lifecycle entry allocation is inconsistent",
            )
        return lifecycle_qty != row.qty

    def charge_result_receipt(self, row) -> dict:
        """Project one receipt from durable per-leg authority and stored money.

        Paper authority is never inferred from rounded amounts or a caller label.
        Historical NULL stays explicitly unknown while a new exit can still carry
        complete current authority.
        """
        if not isinstance(row, (Position, Trade)):
            raise ChargeScheduleRefusal(
                "CHARGE_RECEIPT_INVALID", "charge receipt requires a Position or Trade"
            )
        if (row.owner_id != self.owner_id
                or row.broker_account_id != self.broker_account_id):
            raise ChargeScheduleRefusal(
                "CHARGE_RECEIPT_OWNERSHIP", "charge receipt row is not owned by this account"
            )
        entry_side, exit_side = self._option_charge_sides(row)
        observed_entry_minor = (
            monetary_minor(row.entry_charges)
            if isinstance(row, Position)
            else monetary_minor(row.charges_total) - monetary_minor(row.exit_charges)
        )
        observed_exit_minor = (
            None if isinstance(row, Position) else monetary_minor(row.exit_charges)
        )
        partial_entry = isinstance(row, Position) and row.qty < row.lot_size
        if row.mode == "live":
            if any(getattr(row, name, None) is not None for name in (
                    "paper_entry_charge_schedule_id",
                    "paper_entry_charge_schedule_address",
                    "paper_exit_charge_schedule_id",
                    "paper_exit_charge_schedule_address")):
                raise ChargeScheduleRefusal(
                    "CHARGE_AUTHORITY_MODE", "live row carries Paper charge authority")
            entry_schedule = charge_schedule_document(ZERODHA_CHARGES_V1)
            exit_schedule = None if isinstance(row, Position) else entry_schedule
            entry_state = exit_state = "LIVE_V1"
        else:
            entry_schedule = self._validated_schedule_pair(
                row.paper_entry_charge_schedule_id,
                row.paper_entry_charge_schedule_address,
                allow_unknown=True,
            )
            exit_schedule = None
            if isinstance(row, Trade):
                exit_schedule = self._validated_schedule_pair(
                    row.paper_exit_charge_schedule_id,
                    row.paper_exit_charge_schedule_address,
                    allow_unknown=True,
                )
            entry_state = (
                "KNOWN" if entry_schedule is not None
                else "LEGACY_ENTRY_AUTHORITY_UNKNOWN")
            exit_state = (
                None if isinstance(row, Position) else
                ("KNOWN" if exit_schedule is not None
                 else "LEGACY_EXIT_AUTHORITY_UNKNOWN"))

        lifecycle_state = None
        if row.mode == "paper":
            lifecycle_state = (
                "KNOWN_INTENT" if row.entry_intent_id is not None
                else "LEGACY_NULL"
            )
            if entry_schedule is not None:
                partial_entry = self._paper_lifecycle_allocation(
                    row, entry_schedule, entry_side)
        if (entry_schedule is not None and isinstance(row, Position)
                and not partial_entry and row.mode != "paper"):
            entry_answer = compute_charges(
                row.exchange, entry_side, row.entry_premium, row.lot_size,
                schedule_id=entry_schedule["id"],
            )
            if monetary_minor(entry_answer["total"]) != observed_entry_minor:
                raise ChargeScheduleRefusal(
                    "CHARGE_RECEIPT_MISMATCH", "stored entry charge does not match authority")
        if isinstance(row, Trade):
            # Fully funded options persist premium notional plus entry charges,
            # so their cost independently proves the entry-charge allocation.
            # Margined equity/futures persist margin plus charges: subtracting
            # notional there fabricates a large negative amount (V0-PCA-CR-001).
            if (row.segment or "options") == "options":
                stored_entry_slice = monetary_minor(
                    row.entry_cost - row.entry_premium * row.qty)
                if stored_entry_slice != observed_entry_minor:
                    raise ChargeScheduleRefusal(
                        "CHARGE_ENTRY_LIFECYCLE_ALLOCATION",
                        "stored option Trade entry slice is inconsistent")
            if entry_schedule is not None:
                entry_answer = compute_charges(
                    row.exchange, entry_side, row.entry_premium, row.qty,
                    schedule_id=entry_schedule["id"],
                )
                if row.mode != "paper":
                    partial_entry = (
                        monetary_minor(entry_answer["total"]) != observed_entry_minor)
        if exit_schedule is not None:
            exit_answer = compute_charges(
                row.exchange, exit_side, row.exit_premium, row.qty,
                schedule_id=exit_schedule["id"],
            )
            if monetary_minor(exit_answer["total"]) != observed_exit_minor:
                raise ChargeScheduleRefusal(
                    "CHARGE_RECEIPT_MISMATCH", "stored exit charge does not match authority")
        payload = {
            "scheme": (
                _PAPER_CHARGE_RECEIPT_SCHEME_V2
                if row.mode == "paper" else _PAPER_CHARGE_RECEIPT_SCHEME_V1
            ),
            "row_kind": "position" if isinstance(row, Position) else "trade",
            "row_id": row.id,
            "owner_id": row.owner_id,
            "broker_account_id": row.broker_account_id,
            "deployment_id": row.deployment_id,
            "instrument_key": row.instrument_key,
            "exchange": row.exchange,
            "segment": row.segment or "options",
            "direction": row.direction,
            "entry_side": entry_side,
            "exit_side": None if isinstance(row, Position) else exit_side,
            "qty": row.qty,
            "entry_price_minor": monetary_minor(row.entry_premium),
            "exit_price_minor": (
                None if isinstance(row, Position) else monetary_minor(row.exit_premium)
            ),
            "entry_charge_minor": observed_entry_minor,
            "exit_charge_minor": observed_exit_minor,
            "total_charge_minor": (
                observed_entry_minor if observed_exit_minor is None
                else observed_entry_minor + observed_exit_minor
            ),
            "partial_entry_allocation": partial_entry,
            "entry_time": row.entry_time.isoformat(),
            "exit_time": (
                None if isinstance(row, Position) else row.exit_time.isoformat()
            ),
            "entry_authority_state": entry_state,
            "entry_schedule_id": (
                None if entry_schedule is None else entry_schedule["id"]),
            "entry_schedule_address": (
                None if entry_schedule is None else entry_schedule["address"]),
            "exit_authority_state": exit_state,
            "exit_schedule_id": (
                None if exit_schedule is None else exit_schedule["id"]),
            "exit_schedule_address": (
                None if exit_schedule is None else exit_schedule["address"]),
            "entry_rounding_policy": (
                None if entry_schedule is None else entry_schedule["rounding_policy"]),
            "exit_rounding_policy": (
                None if exit_schedule is None else exit_schedule["rounding_policy"]),
        }
        if row.mode == "paper":
            payload.update({
                "entry_intent_id": row.entry_intent_id,
                "entry_lifecycle_state": lifecycle_state,
            })
        return {
            "address": "sha256:" + hashlib.sha256(
                json.dumps(
                    payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode("utf-8")
            ).hexdigest(),
            **payload,
        }

    def _risk_reducing_receipt_or_none(self, row) -> dict | None:
        """Keep an exact owned exit available when old identity is inconsistent."""
        try:
            return self.charge_result_receipt(row)
        except ChargeScheduleRefusal as exc:
            if exc.code not in {
                "CHARGE_ENTRY_LIFECYCLE_REQUIRED",
                "CHARGE_ENTRY_LIFECYCLE_SCOPE",
                "CHARGE_ENTRY_LIFECYCLE_AUTHORITY",
                "CHARGE_ENTRY_LIFECYCLE_QUANTITY",
                "CHARGE_ENTRY_LIFECYCLE_ALLOCATION",
            }:
                raise
            self._operational_log("error", "PAPER_EXIT_LIFECYCLE_UNKNOWN", "DEGRADED")
            return None

    def _require_owned_position(self, pos: Position) -> None:
        if (pos.owner_id != self.owner_id
                or pos.broker_account_id != self.broker_account_id):
            raise ValueError("position is not available to this broker account")
        if pos.id is None:
            raise ValueError("position is not durably open")
        with self.s.no_autoflush:
            persisted = self.s.scalar(select(Position).where(
                Position.id == pos.id,
                Position.owner_id == self.owner_id,
                Position.broker_account_id == self.broker_account_id,
                Position.deployment_id == pos.deployment_id,
                Position.mode == self.book,
            ))
        if persisted is not pos:
            raise ValueError("position is no longer open in this broker book")

    def _require_current_entry_receipt(self, *, admission_address: str | None,
                                       strategy_key: str | None,
                                       strategy_version: str | None,
                                       graph_address: str | None,
                                       attribution_state: str) -> None:
        """Verify a caller-supplied receipt at the owning paper-book write seam.

        ``sha256:...`` is an identifier, never a capability.  Runner verification is
        deliberately independent from this check because direct broker callers (manual
        tools, recovery bugs, and future routes) otherwise turn a plausible-looking
        string into new exposure.  The receipt's *source* identity is checked here: an
        admitted handwritten adapter may execute its IR equivalent, while the money row
        still records the adapter identity that produced the authorised binding.
        """
        from app.backtest.repository import AdmissionRequired, load_verified_admission

        try:
            admitted = load_verified_admission(
                self.s, owner_id=self.owner_id, admission_address=admission_address)
        except AdmissionRequired as exc:
            raise ValueError(exc.code) from exc
        from app.strategy.admission import matches_execution_identity
        if not matches_execution_identity(
                admitted.artifact, strategy_key=strategy_key,
                strategy_version=strategy_version,
                graph_address=graph_address,
                attribution_state=attribution_state):
            raise ValueError("GRAPH_ATTRIBUTION_MISMATCH")

    # ── fills ─────────────────────────────────────────────────────────────
    def open_position(self, inst: Instrument, direction: str, q: OptionQuote,
                      reason: str, now: dt.datetime, spot: float,
                      params: dict | None = None, plan=None,
                      strategy_key: str | None = None,
                      strategy_version: str | None = None,
                      entry_intent_id: str | None = None,
                      admission_address: str | None = None,
                      graph_address: str | None = None,
                      attribution_state: str = "NON_GRAPH",
                      recovery_intent=None,
                      runtime_context_json: str | None = None) -> Position:
        recovery_proof = self._is_persisted_entry_intent(
            recovery_intent, entry_intent_id=entry_intent_id,
            admission_address=admission_address, strategy_key=strategy_key,
            strategy_version=strategy_version, graph_address=graph_address,
            attribution_state=attribution_state)
        legacy_proof = self._is_legacy_recovery_intent(recovery_intent, entry_intent_id)
        if not admission_address and not (legacy_proof or recovery_proof):
            raise ValueError("ADMISSION_REQUIRED")
        if admission_address and (not recovery_proof or runtime_context_json is not None):
            self._require_current_entry_receipt(
                admission_address=admission_address, strategy_key=strategy_key,
                strategy_version=strategy_version, graph_address=graph_address,
                attribution_state=attribution_state)
        # `plan` (routing decision) is used by LiveBroker to choose market/limit;
        # the paper broker ignores it and fills at the quote.
        qty, premium = q.lot_size, q.ltp
        charge_answer = self._compute_charge(inst.segment, "BUY", premium, qty)
        entry_authority = self._paper_entry_authority(charge_answer)
        charges = charge_answer["total"]
        cost = premium * qty + charges
        # Initial SL/TP honor live Settings overrides (runtime_config). The runner
        # passes its already-resolved snapshot; other callers (manual_open, tests)
        # fall back to the effective merge so an override is never silently ignored.
        p = params if params is not None else effective(self.settings, owner_id=self.owner_id)
        stop_loss_pct = p.get("stop_loss_pct", self.settings.stop_loss_pct)
        target_pct = p.get("target_pct", self.settings.target_pct)

        entry_intent_id = self._prepare_paper_entry_intent(
            entry_intent_id=entry_intent_id, recovery_intent=recovery_intent,
            instrument_key=inst.key, tradingsymbol=q.tradingsymbol,
            exchange=inst.segment, side="BUY", segment="options", qty=qty,
            decision_price=premium, now=now, strategy_key=strategy_key,
            strategy_version=strategy_version, admission_address=admission_address,
            graph_address=graph_address, attribution_state=attribution_state,
            runtime_context_json=runtime_context_json)
        cap = self.capital()
        cap.cash -= cost
        cap.updated_at = now

        pos = Position(
            owner_id=self.owner_id, broker_account_id=self.broker_account_id,
            deployment_id=self.deployment_id,
            entry_intent_id=entry_intent_id,
            instrument_key=inst.key, direction=direction, option_type=q.option_type,
            tradingsymbol=q.tradingsymbol, exchange=inst.segment, strike=q.strike,
            expiry=q.expiry, lot_size=qty, qty=qty, entry_premium=premium,
            entry_charges=charges, entry_cost=cost, entry_spot=spot, entry_time=now,
            **entry_authority,
            entry_reason=reason,
            stop_price=premium * (1 - stop_loss_pct),
            target_price=premium * (1 + target_pct),
            last_premium=premium, last_spot=spot,
            last_mark_time=now, high_water_premium=premium,
            mfe=0.0, mae=0.0,   # seeded at the 0 excursion at entry (E0.3)
            # The identity of the logic that actually produced this fill, passed in from
            # the runner's canonical binding. The options path resolved that binding and
            # refused to open without it, but did not carry it onto the row — so every
            # option position was written unattributed. Latent until L1.3C, because
            # production runs `max_open_positions=0`; reachable the moment a graph became
            # authoritative, which is the slice that found it.
            strategy_key=strategy_key, strategy_version=strategy_version,
            admission_address=admission_address,
            graph_address=graph_address, attribution_state=attribution_state,
            mode=self.MODE,
        )
        self.s.add(pos)
        self.s.flush()
        charge_receipt = None
        if self.MODE == "paper":
            charge_receipt = self.charge_result_receipt(pos)
            pos.charge_result_receipt = charge_receipt
        self._append_money_projection(state="position_opened", aggregate_id=str(pos.id))
        self.s.commit()
        self._operational_log("trade", "OPEN", "APPLIED")
        return pos

    # ── intraday equity (MIS): margin-sized shares, direction-aware ──────────
    def open_equity_position(self, inst: Instrument, direction: str, price: float,
                             qty: int, charge_segment: str, reason: str,
                             now: dt.datetime, params: dict | None = None,
                             strategy_key: str | None = None,
                             strategy_version: str | None = None,
                             margin: float | None = None,
                             sl_pct: float | None = None,
                             tp_pct: float | None = None,
                             entry_intent_id: str | None = None,
                             plan=None,
                             admission_address: str | None = None,
                             graph_address: str | None = None,
                             attribution_state: str = "NON_GRAPH",
                             recovery_intent=None,
                             runtime_context_json: str | None = None) -> Position:
        """Open an intraday equity (MIS) position of `qty` shares at `price`.

        MIS is leveraged: only the MARGIN leaves cash, not the full notional — but P&L
        is on the full share move. We store entry_cost = margin + entry charges (the
        actual cash out), so the ledger reconciliation invariant holds exactly. When the
        caller supplies `margin` (fix A: the REAL Zerodha `order_margins` figure the
        position was sized to) we book that; otherwise we fall back to notional/leverage.
        SL/TP are direction-aware (a SHORT's stop is above entry). `sl_pct`/`tp_pct`, when
        given (purple-tiered entries), are frozen onto the row (entry_sl_pct/entry_tp_pct)
        so a later flag toggle can never reshape this position; omitted (the legacy shape)
        falls back to the global intraday_stop_loss_pct/intraday_target_pct and leaves the
        columns NULL. Charges use the intraday charge segment (NSE_INTRADAY/BSE_INTRADAY)."""
        recovery_proof = self._is_persisted_entry_intent(
            recovery_intent, entry_intent_id=entry_intent_id,
            admission_address=admission_address, strategy_key=strategy_key,
            strategy_version=strategy_version, graph_address=graph_address,
            attribution_state=attribution_state)
        legacy_proof = self._is_legacy_recovery_intent(recovery_intent, entry_intent_id)
        if not admission_address and not (legacy_proof or recovery_proof):
            raise ValueError("ADMISSION_REQUIRED")
        if admission_address and (not recovery_proof or runtime_context_json is not None):
            self._require_current_entry_receipt(
                admission_address=admission_address, strategy_key=strategy_key,
                strategy_version=strategy_version, graph_address=graph_address,
                attribution_state=attribution_state)
        p = params if params is not None else effective(self.settings, owner_id=self.owner_id)
        leverage = p.get("intraday_leverage", 2.5) or 2.5
        eff_sl_pct = sl_pct if sl_pct is not None else p.get("intraday_stop_loss_pct", 0.01)
        eff_tp_pct = tp_pct if tp_pct is not None else p.get("intraday_target_pct", 0.02)
        notional = price * qty
        margin = margin if (margin is not None and margin > 0) else notional / leverage
        # E7: a SHORT opens by SELLING — direction-aware legs, or STT/stamp land on the
        # wrong leg and Trade.net_pnl can't reconcile against the contract note.
        entry_side, _ = legs_for(direction)
        stop, target = equity_stop_target(direction, price, eff_sl_pct, eff_tp_pct)

        entry_intent_id = self._prepare_paper_entry_intent(
            entry_intent_id=entry_intent_id, recovery_intent=recovery_intent,
            instrument_key=inst.key,
            tradingsymbol=getattr(inst, "spot_symbol", "") or inst.key,
            exchange=charge_segment, side=entry_side, segment="equity_intraday",
            qty=qty, decision_price=price, now=now, strategy_key=strategy_key,
            strategy_version=strategy_version, admission_address=admission_address,
            graph_address=graph_address, attribution_state=attribution_state,
            runtime_context_json=runtime_context_json)
        if runtime_context_json is not None:
            from app.paper_runtime.contracts import runtime_sources_from_context_json
            from app.paper_runtime.service import validate_durable_runtime_authority

            (runtime_context, runtime_assignment, runtime_authority,
             runtime_event, runtime_command) = runtime_sources_from_context_json(
                runtime_context_json, client_intent_id=entry_intent_id,
                broker_owner_id=self.owner_id,
                broker_account_id=self.broker_account_id,
                broker_deployment_id=self.deployment_id,
                broker_fence_epoch=getattr(
                    self.execution_lease_token, "fence_epoch", None))
            validate_durable_runtime_authority(
                self, runtime_assignment, runtime_authority, runtime_event,
                runtime_command, allow_converged_effect=False)
            # This explicit runtime seam preserves exact source prices. Legacy
            # callers still use the percentage-derived values above unchanged.
            stop = float(runtime_context["stop_loss"])
            target = float(runtime_context["take_profit"])

        charge_answer = self._compute_charge(charge_segment, entry_side, price, qty)
        entry_authority = self._paper_entry_authority(charge_answer)
        charges = charge_answer["total"]
        cost = margin + charges
        cap = self.capital()
        cap.cash -= cost
        cap.updated_at = now

        pos = Position(
            owner_id=self.owner_id, broker_account_id=self.broker_account_id,
            deployment_id=self.deployment_id,
            entry_intent_id=entry_intent_id,
            instrument_key=inst.key, direction=direction, option_type="EQ",
            tradingsymbol=getattr(inst, "spot_symbol", "") or inst.key,
            exchange=charge_segment, segment="equity_intraday", strategy_key=strategy_key,
            strategy_version=strategy_version, admission_address=admission_address,
            graph_address=graph_address, attribution_state=attribution_state,
            strike=0.0, expiry=now.date(), lot_size=qty, qty=qty, entry_premium=price,
            entry_charges=charges, entry_cost=cost, entry_spot=price, entry_time=now,
            **entry_authority,
            entry_reason=reason, stop_price=stop, target_price=target,
            entry_sl_pct=sl_pct, entry_tp_pct=tp_pct,
            last_premium=price, last_spot=price, last_mark_time=now,
            high_water_premium=price,
            mfe=0.0, mae=0.0,   # seeded at the 0 excursion at entry (E0.3)
            mode=self.MODE)
        self.s.add(pos)
        self.s.flush()
        self._append_money_projection(state="position_opened", aggregate_id=str(pos.id))
        self.s.commit()
        self._operational_log("trade", "OPEN_EQUITY", "APPLIED")
        return pos

    def close_equity_position(self, pos: Position, exit_price: float, reason: str,
                              now: dt.datetime,
                              exit_price_estimated: bool = False) -> Trade:
        """Close an intraday equity position. Releases the blocked margin and books
        direction-aware P&L (a SHORT profits when price falls), net of both legs'
        charges. proceeds = entry_cost + net, so the ledger invariant stays exact."""
        self._require_owned_position(pos)
        qty = pos.qty
        _, exit_side = legs_for(pos.direction)      # E7: a SHORT closes by BUYING to cover
        charge_answer = self._exit_charge_answer(pos, exit_side, exit_price, qty)
        trade_authority = self._paper_trade_authority(pos, charge_answer)
        charges = charge_answer["total"]
        gross = ((exit_price - pos.entry_premium) * qty if pos.direction == "LONG"
                 else (pos.entry_premium - exit_price) * qty)
        total_charges = pos.entry_charges + charges
        net = gross - total_charges
        proceeds = pos.entry_cost + net    # == released margin + gross − exit charges
        margin = pos.entry_cost - pos.entry_charges

        cap = self.capital()
        cap.cash += proceeds
        cap.realized_pnl += net
        cap.updated_at = now

        tr = Trade(
            owner_id=self.owner_id, broker_account_id=self.broker_account_id,
            deployment_id=self.deployment_id,
            entry_intent_id=pos.entry_intent_id,
            instrument_key=pos.instrument_key, direction=pos.direction,
            option_type="EQ", tradingsymbol=pos.tradingsymbol, exchange=pos.exchange,
            segment="equity_intraday", strategy_key=pos.strategy_key,
            strategy_version=pos.strategy_version, admission_address=pos.admission_address,
            graph_address=pos.graph_address, attribution_state=pos.attribution_state,
            strike=0.0, expiry=pos.expiry, qty=qty,
            entry_premium=pos.entry_premium, entry_cost=pos.entry_cost,
            **trade_authority,
            entry_spot=pos.entry_spot, entry_time=pos.entry_time,
            exit_premium=exit_price, exit_charges=charges, exit_spot=exit_price,
            exit_time=now, exit_reason=reason, gross_pnl=gross,
            charges_total=total_charges, net_pnl=net,
            return_pct=(net / margin * 100) if margin else 0.0,
            holding_minutes=(now - pos.entry_time).total_seconds() / 60,
            win=net > 0, held_overnight=False, overnight_pnl=0.0,
            intraday_pnl=round(net, 2), reinforcements=0, mode=self.MODE,
            exit_price_estimated=exit_price_estimated,
            mfe=pos.mfe, mae=pos.mae)
        self.s.delete(pos)
        self.s.add(tr)
        self.s.flush()
        charge_receipt = None
        if self.MODE == "paper":
            charge_receipt = self._risk_reducing_receipt_or_none(tr)
            tr.charge_result_receipt = charge_receipt
        self._append_money_projection(state="trade_closed", aggregate_id=str(tr.id))
        self.s.commit()
        self._operational_log("trade", "CLOSE_EQUITY", "APPLIED")
        return tr

    def manual_open(self, inst: Instrument, direction: str, chain, settings,
                    now: dt.datetime, *, strategy_key: str | None = None,
                    strategy_version: str | None = None,
                    admission_address: str | None = None,
                    graph_address: str | None = None,
                    attribution_state: str = "NON_GRAPH") -> tuple[Position | None, str]:
        """Owner-initiated entry with the same immutable receipt as engine entries."""
        from app.options.picker import pick_option
        if not admission_address:
            return None, "ADMISSION_REQUIRED"
        if self.position_for(inst.key) is not None:
            return None, "already holding a position for this instrument"
        if chain is None:
            return None, "no option chain available to price a contract"
        pick = pick_option(chain, direction, settings, now)
        if not pick.chosen:
            return None, f"no priceable contract: {pick.reason}"
        qty = pick.chosen.lot_size
        charges = self._compute_charge(
            inst.segment, "BUY", pick.chosen.ltp, qty
        )["total"]
        cost = pick.chosen.ltp * qty + charges
        if cost > self.cash():
            return None, f"insufficient cash: need ₹{cost:,.0f}, have ₹{self.cash():,.0f}"
        pos = self.open_position(inst, direction, pick.chosen,
                                 f"MANUAL {direction}", now, chain.spot,
                                 strategy_key=strategy_key,
                                 strategy_version=strategy_version,
                                 admission_address=admission_address,
                                 graph_address=graph_address,
                                 attribution_state=attribution_state)
        self._operational_log("info", "MANUAL_OPEN", "APPLIED")
        return pos, "ok"

    def reinforce_position(self, pos: Position, params: dict, now: dt.datetime) -> dict:
        """Apply a same-direction reinforcement to a held position: ratchet the
        stop, optionally extend the target, bump the count. No quantity change."""
        self._require_owned_position(pos)
        from app.engine.exit_monitor import apply_reinforcement
        prem = pos.last_premium or pos.entry_premium
        r = apply_reinforcement(pos.entry_premium, pos.stop_price, pos.target_price,
                                prem, pos.reinforcement_count, pos.last_reinforce_time,
                                now, params)
        if r["applied"]:
            pos.stop_price = r["stop_price"]
            if not pos.manual_target:
                pos.target_price = r["target_price"]   # owner-set target is not auto-extended
            pos.reinforcement_count = r["count"]
            pos.last_reinforce_time = now
            self._append_money_projection(
                state="position_reinforced", aggregate_id=str(pos.id), revision=str(r["count"]))
            self.s.commit()
            # the stop just ratcheted — push it to the exchange GTT backstop too
            # (no-op on paper; LiveBroker modifies the live GTT).
            self.update_stop_protection(pos, pos.last_premium)
            self._operational_log("info", "REINFORCE", "APPLIED")
        return r

    def mark(self, pos: Position, premium: float | None, spot: float | None,
             now: dt.datetime | None = None) -> None:
        self._require_owned_position(pos)
        # Use explicit None checks: a real 0.0 premium (option decayed to zero —
        # the buyer's maximum loss) is a VALID mark and must advance freshness, or
        # the staleness guard would suppress the stop at the worst possible time.
        if premium is not None:
            pos.last_premium = premium
            # Fall back to IST wall-clock, NOT naive host-local. Everything in
            # this app speaks IST — including the value this is compared against
            # by the mark-staleness guard. The production box happens to be set
            # to IST today, but DO droplets default to UTC, so a rebuild would
            # make a just-taken mark look 19,800s old and `is_stale` would
            # suppress SL/TP on live money. Correctness must not rest on a
            # machine setting. See tests/test_timezone_independence.py.
            pos.last_mark_time = now or now_ist().replace(tzinfo=None)
            if premium > (pos.high_water_premium or 0.0):
                pos.high_water_premium = premium
            # peak-excursion telemetry (E0.3) — pure read of unrealized_pnl(), which
            # is already segment/direction-aware; never feeds cash/P&L/exit logic.
            # float() casts away any numpy scalar (mock premiums are np.float64):
            # a numpy value written into the ORM column corrupts the unit-of-work's
            # change bookkeeping and surfaces as a StaleDataError on the next commit.
            u = float(pos.unrealized_pnl())
            pos.mfe = float(max(pos.mfe or 0.0, u))
            pos.mae = float(min(pos.mae or 0.0, u))
        if spot is not None:
            pos.last_spot = spot

    # ── index futures (E2) ────────────────────────────────────────────────
    def open_futures_position(self, inst: Instrument, direction: str, price: float,
                              qty: int, charge_segment: str, reason: str,
                              now: dt.datetime, expiry: dt.date,
                              margin: float, params: dict | None = None,
                              strategy_key: str | None = None,
                              strategy_version: str | None = None,
                              admission_address: str | None = None,
                              graph_address: str | None = None,
                              attribution_state: str = "NON_GRAPH",
                              entry_intent_id: str | None = None,
                              recovery_intent=None,
                              runtime_context_json: str | None = None) -> Position:
        """Open an index-futures position of `qty` units at the FUTURES price.

        Deliberately a near-copy of `open_equity_position` rather than a shared
        generic: both are margined, but they differ in charge segment, expiry
        handling and SL/TP knobs, and collapsing them into one parameterised
        method would put the equity path — which trades real money today — one
        refactor away from every futures change.

        `margin` is REQUIRED and has no fallback. Equity can fall back to
        notional/leverage because MIS leverage is roughly knowable; SPAN is
        portfolio-scanned and instrument-specific, so a guessed futures margin
        would be a fabricated number sitting directly in the ledger. The caller
        obtains it from a broker quote (live) or the flagged paper estimate.

        entry_cost = margin + entry charges — the actual cash out — so the
        reconciliation invariant `cash == initial + realized − Σ(open entry_cost)`
        holds exactly, the same as every other segment.
        """
        recovery_proof = self._is_persisted_entry_intent(
            recovery_intent, entry_intent_id=entry_intent_id,
            admission_address=admission_address,
            strategy_key=strategy_key, strategy_version=strategy_version,
            graph_address=graph_address, attribution_state=attribution_state)
        if not admission_address and not recovery_proof:
            raise ValueError("ADMISSION_REQUIRED")
        if admission_address and (not recovery_proof or runtime_context_json is not None):
            self._require_current_entry_receipt(
                admission_address=admission_address, strategy_key=strategy_key,
                strategy_version=strategy_version, graph_address=graph_address,
                attribution_state=attribution_state)
        if margin is None or margin <= 0:
            raise ValueError("open_futures_position requires a positive margin: "
                             "SPAN is instrument-specific and must never be guessed")
        p = params if params is not None else effective(self.settings, owner_id=self.owner_id)
        sl_pct = p.get("index_futures_stop_loss_pct",
                       self.settings.index_futures_stop_loss_pct)
        tp_pct = p.get("index_futures_target_pct",
                       self.settings.index_futures_target_pct)
        entry_side, _ = legs_for(direction)
        charge_answer = self._compute_charge(charge_segment, entry_side, price, qty)
        entry_authority = self._paper_entry_authority(charge_answer)
        charges = charge_answer["total"]
        cost = margin + charges
        stop, target = equity_stop_target(direction, price, sl_pct, tp_pct)

        entry_intent_id = self._prepare_paper_entry_intent(
            entry_intent_id=entry_intent_id, recovery_intent=recovery_intent,
            instrument_key=inst.key,
            tradingsymbol=getattr(inst, "option_name", "") or inst.key,
            exchange=charge_segment, side=entry_side, segment="index_futures",
            qty=qty, decision_price=price, now=now, strategy_key=strategy_key,
            strategy_version=strategy_version, admission_address=admission_address,
            graph_address=graph_address, attribution_state=attribution_state,
            runtime_context_json=runtime_context_json)

        cap = self.capital()
        cap.cash -= cost
        cap.updated_at = now

        pos = Position(
            owner_id=self.owner_id, broker_account_id=self.broker_account_id,
            deployment_id=self.deployment_id,
            entry_intent_id=entry_intent_id,
            instrument_key=inst.key, direction=direction, option_type="FUT",
            tradingsymbol=getattr(inst, "option_name", "") or inst.key,
            exchange=charge_segment, segment="index_futures", strategy_key=strategy_key,
            strategy_version=strategy_version, admission_address=admission_address,
            graph_address=graph_address, attribution_state=attribution_state,
            strike=0.0, expiry=expiry, lot_size=qty, qty=qty, entry_premium=price,
            entry_charges=charges, entry_cost=cost, entry_spot=price, entry_time=now,
            **entry_authority,
            entry_reason=reason, stop_price=stop, target_price=target,
            last_premium=price, last_spot=price, last_mark_time=now,
            high_water_premium=price, mfe=0.0, mae=0.0, mode=self.MODE)
        self.s.add(pos)
        self.s.flush()
        self._append_money_projection(state="position_opened", aggregate_id=str(pos.id))
        self.s.commit()
        self._operational_log("trade", "OPEN_FUTURES", "APPLIED")
        return pos

    def close_futures_position(self, pos: Position, exit_price: float, reason: str,
                               now: dt.datetime,
                               exit_price_estimated: bool = False) -> Trade:
        """Close an index-futures position. Releases the blocked margin and books
        direction-aware P&L net of both legs' charges, so
        `proceeds = entry_cost + net` and the ledger invariant stays exact."""
        self._require_owned_position(pos)
        qty = pos.qty
        _, exit_side = legs_for(pos.direction)
        charge_answer = self._exit_charge_answer(pos, exit_side, exit_price, qty)
        trade_authority = self._paper_trade_authority(pos, charge_answer)
        charges = charge_answer["total"]
        gross = ((exit_price - pos.entry_premium) * qty if pos.direction == "LONG"
                 else (pos.entry_premium - exit_price) * qty)
        total_charges = pos.entry_charges + charges
        net = gross - total_charges
        proceeds = pos.entry_cost + net
        margin = pos.entry_cost - pos.entry_charges

        cap = self.capital()
        cap.cash += proceeds
        cap.realized_pnl += net
        cap.updated_at = now

        tr = Trade(
            owner_id=self.owner_id, broker_account_id=self.broker_account_id,
            deployment_id=self.deployment_id,
            entry_intent_id=pos.entry_intent_id,
            instrument_key=pos.instrument_key, direction=pos.direction,
            option_type="FUT", tradingsymbol=pos.tradingsymbol, exchange=pos.exchange,
            segment="index_futures", strategy_key=pos.strategy_key,
            strategy_version=pos.strategy_version, admission_address=pos.admission_address,
            graph_address=pos.graph_address, attribution_state=pos.attribution_state,
            strike=0.0, expiry=pos.expiry, qty=qty,
            entry_premium=pos.entry_premium, entry_cost=pos.entry_cost,
            **trade_authority,
            entry_spot=pos.entry_spot, entry_time=pos.entry_time,
            exit_premium=exit_price, exit_charges=charges, exit_spot=exit_price,
            exit_time=now, exit_reason=reason, gross_pnl=gross,
            charges_total=total_charges, net_pnl=net,
            return_pct=(net / margin * 100) if margin else 0.0,
            holding_minutes=(now - pos.entry_time).total_seconds() / 60,
            win=net > 0, held_overnight=False, overnight_pnl=0.0,
            intraday_pnl=round(net, 2), reinforcements=0, mode=self.MODE,
            exit_price_estimated=exit_price_estimated,
            mfe=pos.mfe, mae=pos.mae)
        self.s.delete(pos)
        self.s.add(tr)
        self.s.flush()
        charge_receipt = None
        if self.MODE == "paper":
            charge_receipt = self._risk_reducing_receipt_or_none(tr)
            tr.charge_result_receipt = charge_receipt
        self._append_money_projection(state="trade_closed", aggregate_id=str(tr.id))
        self.s.commit()
        self._operational_log("trade", "CLOSE_FUTURES", "APPLIED")
        return tr

    def close_position(self, pos: Position, exit_premium: float, reason: str,
                       now: dt.datetime, spot: float,
                       exit_price_estimated: bool = False) -> Trade:
        self._require_owned_position(pos)
        qty = pos.qty
        charge_answer = self._exit_charge_answer(pos, "SELL", exit_premium, qty)
        trade_authority = self._paper_trade_authority(pos, charge_answer)
        schedule_id = charge_answer["schedule_id"]
        charges = charge_answer["total"]
        proceeds = exit_premium * qty - charges
        gross = (exit_premium - pos.entry_premium) * qty
        if schedule_id == ZERODHA_CHARGES_V2:
            total_charges = (
                monetary_minor(pos.entry_charges) + monetary_minor(charges)
            ) / 100
        else:
            total_charges = pos.entry_charges + charges
        net = proceeds - pos.entry_cost  # == gross - total_charges

        cap = self.capital()
        cap.cash += proceeds
        cap.realized_pnl += net
        cap.updated_at = now

        tr = Trade(
            owner_id=self.owner_id, broker_account_id=self.broker_account_id,
            deployment_id=self.deployment_id,
            entry_intent_id=pos.entry_intent_id,
            instrument_key=pos.instrument_key, direction=pos.direction,
            option_type=pos.option_type, tradingsymbol=pos.tradingsymbol,
            exchange=pos.exchange, strategy_key=pos.strategy_key,
            strategy_version=pos.strategy_version, admission_address=pos.admission_address,
            graph_address=pos.graph_address, attribution_state=pos.attribution_state,
            strike=pos.strike, expiry=pos.expiry, qty=qty,
            entry_premium=pos.entry_premium, entry_cost=pos.entry_cost,
            **trade_authority,
            entry_spot=pos.entry_spot, entry_time=pos.entry_time,
            exit_premium=exit_premium, exit_charges=charges, exit_spot=spot,
            exit_time=now, exit_reason=reason, gross_pnl=gross,
            charges_total=total_charges, net_pnl=net,
            return_pct=(net / pos.entry_cost * 100) if pos.entry_cost else 0.0,
            holding_minutes=(now - pos.entry_time).total_seconds() / 60,
            win=net > 0,
            held_overnight=pos.held_overnight,
            overnight_pnl=round(pos.overnight_pnl, 2),
            intraday_pnl=round(net - pos.overnight_pnl, 2),
            reinforcements=pos.reinforcement_count,
            mode=self.MODE,
            exit_price_estimated=exit_price_estimated,
            mfe=pos.mfe, mae=pos.mae,
        )
        self.s.delete(pos)
        self.s.add(tr)
        self.s.flush()
        charge_receipt = None
        if self.MODE == "paper":
            charge_receipt = self._risk_reducing_receipt_or_none(tr)
            tr.charge_result_receipt = charge_receipt
        self._append_money_projection(state="trade_closed", aggregate_id=str(tr.id))
        self.s.commit()
        self._operational_log("trade", "CLOSE", "APPLIED")
        return tr

    def book_partial_close(self, pos: Position, qty: int, exit_premium: float,
                           reason: str, now: dt.datetime, spot: float) -> Trade:
        """Realize PART of an open position (a SELL that only partially filled): book
        a Trade for `qty`, shrink the open position by `qty`, and split its entry cost
        proportionally. The position stays open at the reduced qty so the remainder
        can still be managed/exited. Keeps the cash reconciliation invariant exact:
        the realized entry-cost slice and the remaining entry_cost sum to the original.
        """
        self._require_owned_position(pos)
        qty = min(int(qty), pos.qty)
        charge_answer = self._exit_charge_answer(pos, "SELL", exit_premium, qty)
        trade_authority = self._paper_trade_authority(pos, charge_answer)
        charges = charge_answer["total"]
        proceeds = exit_premium * qty - charges
        gross = (exit_premium - pos.entry_premium) * qty
        # split the entry cost/charges by the fraction sold; the remainder and the
        # realized slice add back to the originals exactly (no rounding drift).
        schedule_id = charge_answer["schedule_id"]
        if schedule_id == ZERODHA_CHARGES_V2 and qty < pos.qty:
            charges_slice_minor, remaining_minor = allocate_minor_units(
                monetary_minor(pos.entry_charges), (qty, pos.qty - qty)
            )
            charges_slice = charges_slice_minor / 100
            remaining_entry_charges = remaining_minor / 100
            cost_slice = pos.entry_premium * qty + charges_slice
            remaining_cost = pos.entry_cost - cost_slice
        else:
            remaining_cost = pos.entry_cost * (pos.qty - qty) / pos.qty
            cost_slice = pos.entry_cost - remaining_cost
            remaining_entry_charges = pos.entry_charges * (pos.qty - qty) / pos.qty
            charges_slice = pos.entry_charges - remaining_entry_charges
        net = proceeds - cost_slice
        if schedule_id == ZERODHA_CHARGES_V2:
            charges_total = (
                monetary_minor(charges_slice) + monetary_minor(charges)
            ) / 100
        else:
            charges_total = charges_slice + charges

        cap = self.capital()
        cap.cash += proceeds
        cap.realized_pnl += net
        cap.updated_at = now

        tr = Trade(
            owner_id=self.owner_id, broker_account_id=self.broker_account_id,
            deployment_id=self.deployment_id,
            entry_intent_id=pos.entry_intent_id,
            instrument_key=pos.instrument_key, direction=pos.direction,
            option_type=pos.option_type, tradingsymbol=pos.tradingsymbol,
            exchange=pos.exchange, strategy_key=pos.strategy_key,
            strategy_version=pos.strategy_version, admission_address=pos.admission_address,
            graph_address=pos.graph_address, attribution_state=pos.attribution_state,
            strike=pos.strike, expiry=pos.expiry, qty=qty,
            entry_premium=pos.entry_premium, entry_cost=cost_slice,
            **trade_authority,
            entry_spot=pos.entry_spot, entry_time=pos.entry_time,
            exit_premium=exit_premium, exit_charges=charges, exit_spot=spot,
            exit_time=now, exit_reason=reason, gross_pnl=gross,
            charges_total=charges_total, net_pnl=net,
            return_pct=(net / cost_slice * 100) if cost_slice else 0.0,
            holding_minutes=(now - pos.entry_time).total_seconds() / 60,
            win=net > 0,
            held_overnight=pos.held_overnight,
            overnight_pnl=0.0, intraday_pnl=round(net, 2),
            reinforcements=pos.reinforcement_count,
            mode=self.MODE,
            mfe=pos.mfe, mae=pos.mae,
        )
        pos.qty -= qty
        pos.entry_cost = remaining_cost
        pos.entry_charges = remaining_entry_charges
        self.s.add(tr)
        self.s.flush()
        charge_receipt = None
        if self.MODE == "paper":
            charge_receipt = self._risk_reducing_receipt_or_none(tr)
            tr.charge_result_receipt = charge_receipt
        self._append_money_projection(state="trade_partially_closed", aggregate_id=str(tr.id))
        self.s.commit()
        self._operational_log("trade", "PARTIAL_CLOSE", "APPLIED")
        return tr

    def book_partial_close_equity(self, pos: Position, qty: int, exit_price: float,
                                  reason: str, now: dt.datetime) -> Trade:
        """Realize PART of an intraday-equity (MIS) position — the equity analogue of
        book_partial_close (H16). Direction-aware P&L (a SHORT profits when price
        falls), releases the sold slice's margin, and splits entry cost/charges
        proportionally so the cash invariant stays exact (the realized slice + the
        remaining entry_cost sum to the original). The position stays open at the
        reduced qty so the remainder can be re-stopped and exited later."""
        self._require_owned_position(pos)
        qty = min(int(qty), pos.qty)
        _, exit_side = legs_for(pos.direction)      # E7: a SHORT covers with a BUY
        charge_answer = self._exit_charge_answer(pos, exit_side, exit_price, qty)
        trade_authority = self._paper_trade_authority(pos, charge_answer)
        exit_charges = charge_answer["total"]
        gross = ((exit_price - pos.entry_premium) * qty if pos.direction == "LONG"
                 else (pos.entry_premium - exit_price) * qty)
        if self.MODE == "paper":
            charges_slice_minor, remaining_charges_minor = allocate_minor_units(
                monetary_minor(pos.entry_charges), (qty, pos.qty - qty))
            charges_slice = charges_slice_minor / 100
            remaining_entry_charges = remaining_charges_minor / 100
            margin = pos.entry_cost - pos.entry_charges
            remaining_margin = margin * (pos.qty - qty) / pos.qty
            margin_slice = margin - remaining_margin
            cost_slice = margin_slice + charges_slice
            remaining_cost = remaining_margin + remaining_entry_charges
        else:
            remaining_cost = pos.entry_cost * (pos.qty - qty) / pos.qty
            cost_slice = pos.entry_cost - remaining_cost
            remaining_entry_charges = pos.entry_charges * (pos.qty - qty) / pos.qty
            charges_slice = pos.entry_charges - remaining_entry_charges
            margin_slice = cost_slice - charges_slice
        net = gross - charges_slice - exit_charges
        proceeds = cost_slice + net    # released margin slice + net

        cap = self.capital()
        cap.cash += proceeds
        cap.realized_pnl += net
        cap.updated_at = now

        tr = Trade(
            owner_id=self.owner_id, broker_account_id=self.broker_account_id,
            deployment_id=self.deployment_id,
            entry_intent_id=pos.entry_intent_id,
            instrument_key=pos.instrument_key, direction=pos.direction,
            option_type=pos.option_type, tradingsymbol=pos.tradingsymbol, exchange=pos.exchange,
            segment=pos.segment, strategy_key=pos.strategy_key,
            strategy_version=pos.strategy_version, admission_address=pos.admission_address,
            graph_address=pos.graph_address, attribution_state=pos.attribution_state,
            strike=pos.strike, expiry=pos.expiry, qty=qty,
            entry_premium=pos.entry_premium, entry_cost=cost_slice,
            **trade_authority,
            entry_spot=pos.entry_spot, entry_time=pos.entry_time,
            exit_premium=exit_price, exit_charges=exit_charges, exit_spot=exit_price,
            exit_time=now, exit_reason=reason, gross_pnl=gross,
            charges_total=charges_slice + exit_charges, net_pnl=net,
            return_pct=(net / margin_slice * 100) if margin_slice else 0.0,
            holding_minutes=(now - pos.entry_time).total_seconds() / 60,
            win=net > 0, held_overnight=False, overnight_pnl=0.0,
            intraday_pnl=round(net, 2), reinforcements=0, mode=self.MODE,
            mfe=pos.mfe, mae=pos.mae)
        pos.qty -= qty
        pos.entry_cost = remaining_cost
        pos.entry_charges = remaining_entry_charges
        self.s.add(tr)
        self.s.flush()
        charge_receipt = None
        if self.MODE == "paper":
            charge_receipt = self._risk_reducing_receipt_or_none(tr)
            tr.charge_result_receipt = charge_receipt
        self._append_money_projection(state="trade_partially_closed", aggregate_id=str(tr.id))
        self.s.commit()
        if pos.segment == "index_futures":
            self._operational_log("trade", "PARTIAL_CLOSE_FUTURES", "APPLIED")
        else:
            self._operational_log("trade", "PARTIAL_CLOSE_EQUITY", "APPLIED")
        return tr

    def book_partial_close_futures(self, pos: Position, qty: int, exit_price: float,
                                   reason: str, now: dt.datetime) -> Trade:
        """Book a partial margined futures exit through the exact shared allocation.

        This is the futures spelling of the existing margined partial-close
        contract. It adds no routing or order authority; callers still own the
        fill and pass its exact held Position and price.
        """
        if pos.segment != "index_futures" or pos.option_type != "FUT":
            raise ValueError("partial futures close requires an index futures Position")
        return self.book_partial_close_equity(pos, qty, exit_price, reason, now)

    # ── exchange-side stop protection (no-op for paper; LiveBroker overrides) ──
    def update_stop_protection(self, pos, last_price) -> None:
        """Sync an exchange-side GTT stop to the (possibly ratcheted) stop price."""

    def ensure_stop_protection(self, pos, last_price) -> None:
        """Per-tick check that a backstop is resting; no-op for paper."""

    def reconcile_orphans(self, now: dt.datetime) -> list:
        """Book any bot position the live account no longer backs (e.g. a GTT fired
        while the bot was down). No-op on paper."""
        return []

    def adopt_pending_entries(self, now: dt.datetime) -> list:
        """Adopt any bot entry order that filled AFTER its poll window into the book.
        No-op on paper (paper fills are synchronous, never late)."""
        return []

    def cancel_working_entries(self) -> list:
        """Cancel working/timed-out entry orders on KILL. No-op on paper (paper fills
        are synchronous — there is never a resting entry order)."""
        return []

    def recover_journal(self, now) -> list:
        """Replay the persisted order journal on startup (H13). No-op on paper (paper
        fills are synchronous — nothing is ever left in flight across a restart)."""
        return []

    # ── analytics support ─────────────────────────────────────────────────
    def snapshot(self, now: dt.datetime) -> EquitySnapshot:
        opens = self.open_positions()
        invested = sum(p.entry_cost for p in opens)
        # mtm_value() is segment-aware: options = premium × qty (full cost left cash),
        # leveraged MIS = margin + unrealized P&L (only margin left cash). Summing raw
        # last × qty double-counts MIS leverage and inflates the persisted equity curve.
        mtm = sum(p.mtm_value() for p in opens)
        cap = self.capital()
        snap = EquitySnapshot(owner_id=self.owner_id,
                              broker_account_id=self.broker_account_id,
                              deployment_id=self.deployment_id, book=self.book,
                              time=now, equity=cap.cash + mtm, cash=cap.cash,
                              invested=invested, realized_pnl=cap.realized_pnl,
                              open_count=len(opens))
        self.s.add(snap)
        self.s.commit()
        return snap

    def reconcile(self) -> dict:
        """Self-check: cash should equal initial + realized − Σ(open entry_cost)."""
        cap = self.capital()
        opens = self.open_positions()
        expected = cap.initial_capital + cap.realized_pnl - sum(p.entry_cost for p in opens)
        return {"cash": round(cap.cash, 2), "expected_cash": round(expected, 2),
                "diff": round(cap.cash - expected, 4),
                "realized_pnl": round(cap.realized_pnl, 2), "open": len(opens)}

    def close(self) -> None:
        """Release the long-lived session and its pooled connection.

        `self.s` is held for the broker's lifetime BY DESIGN — the identity map
        is load-bearing (E0.2's ledger re-anchor only works because the write
        goes through this session), which is why context-managing it is a
        separate, deliberate refactor rather than something to do casually.

        But "long-lived" is not "never closed", and this existed while nothing
        called it. Without it the connection outlives the engine: at shutdown
        that is untidy, and in a test process it is a real failure — the next
        `init_db(reset=True)` drops and recreates tables while a connection is
        still open and fails with "database is locked", passing in isolation and
        failing in the suite. It bit twice while building the futures segment.

        Best-effort: safe to call twice, and never raises. A shutdown path is the
        worst place to introduce a new way to fail.
        """
        try:
            self.s.close()
        except Exception:
            pass
