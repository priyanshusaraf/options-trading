"""Shadow-paper validation — the stage between "validated" and "ask the owner".

A backtest is a promise. This is the record of whether reality kept it.

Before this, a candidate that cleared the gate battery went straight into the
approval queue carrying only backtest evidence. That evidence is retrospective by
construction: every parameter was chosen with the whole series visible, and the
Phase-0 machinery (deflation, PBO) can only discount that, never remove it. The
one thing it cannot simulate is a session the strategy has never seen.

So a candidate now runs on a RESEARCH-SIDE paper book for N sessions before a
human is asked to look at it, and it arrives with an expected-versus-realised
comparison attached rather than a scorecard alone.

**It never touches the execution plane.** No order, no position, no row in
`paper_trader.db`. The research plane owning its own paper book is the whole
point: a shadow trade must be incapable of becoming a real one by accident.

**The gate fails closed.** A candidate with too few sessions is NOT ready, and a
candidate whose shadow record cannot be read is not ready either. "We could not
check" and "it passed" must never be the same answer — the same discipline as
`research/guards.py` and the PBO gate.
"""
from __future__ import annotations

import dataclasses
import datetime as dt

from research.domain.models import PromotionCandidate, ShadowSession

# Sessions of unseen data a candidate must survive before a human is asked.
# Small enough to be reachable in a fortnight of trading, large enough that a
# single lucky day cannot carry it.
MIN_SHADOW_SESSIONS = 5

# Candidate lifecycle. `shadow` is the new state; `pending` now means "has
# earned a human's attention", which it did not before.
STATUS_SHADOW = "shadow"
STATUS_PENDING = "pending"


@dataclasses.dataclass(frozen=True)
class ShadowRecord:
    sessions: int
    trades: int
    wins: int
    net_pnl: float

    @property
    def hit_rate(self) -> float:
        return (self.wins / self.trades) if self.trades else 0.0

    @property
    def avg_per_trade(self) -> float:
        return (self.net_pnl / self.trades) if self.trades else 0.0


def record_session(session, candidate_id: int, *, session_date: dt.date,
                   instrument_key: str, trades: int, wins: int,
                   net_pnl: float) -> ShadowSession:
    """Append one shadow session. Idempotent per (candidate, date, instrument):
    re-running a day must not inflate the record into looking better-powered than
    it is."""
    candidate = session.get(PromotionCandidate, candidate_id)
    if candidate is None:
        raise ValueError("candidate not found")
    existing = (session.query(ShadowSession)
                .filter(ShadowSession.owner_id == candidate.owner_id,
                        ShadowSession.candidate_id == candidate_id,
                        ShadowSession.session_date == session_date,
                        ShadowSession.instrument_key == instrument_key)
                .one_or_none())
    row = existing or ShadowSession(owner_id=candidate.owner_id, candidate_id=candidate_id,
                                    session_date=session_date,
                                    instrument_key=instrument_key)
    row.trades, row.wins, row.net_pnl = int(trades), int(wins), float(net_pnl)
    if existing is None:
        session.add(row)
    session.flush()
    return row


def shadow_record(session, candidate_id: int) -> ShadowRecord:
    """Aggregate the shadow book for a candidate.

    `sessions` counts DISTINCT DATES, not rows: a candidate run on six
    instruments for one day has seen one session of unseen data, not six. Getting
    that wrong would let a wide universe manufacture the appearance of
    persistence in a single afternoon.
    """
    rows = (session.query(ShadowSession)
            .filter(ShadowSession.candidate_id == candidate_id).all())
    return ShadowRecord(
        sessions=len({r.session_date for r in rows}),
        trades=sum(int(r.trades or 0) for r in rows),
        wins=sum(int(r.wins or 0) for r in rows),
        net_pnl=sum(float(r.net_pnl or 0.0) for r in rows),
    )


def is_ready_for_approval(session, candidate_id: int, *,
                          min_sessions: int = MIN_SHADOW_SESSIONS) -> tuple:
    """(ready, reason). Fails CLOSED — anything unreadable is "not ready"."""
    try:
        rec = shadow_record(session, candidate_id)
    except Exception as e:                    # noqa: BLE001
        return False, f"shadow record unreadable: {e}"
    if rec.sessions < min_sessions:
        return False, (f"only {rec.sessions}/{min_sessions} shadow session(s) — a "
                       f"backtest is a promise, not a result")
    if rec.trades <= 0:
        return False, "shadow ran but produced no trades — nothing was actually tested"
    return True, f"{rec.sessions} shadow sessions, {rec.trades} trades"


def comparison(expected: dict, session, candidate_id: int) -> dict:
    """Expected (backtest) versus realised (shadow) — "did reality match the promise".

    Returned rather than judged: the point is to put the two numbers side by side
    for a human, not to invent a pass mark for how closely a small shadow sample
    must track a backtest. With few sessions the honest reading is usually
    "consistent with, but underpowered".
    """
    rec = shadow_record(session, candidate_id)
    exp_hit = float(expected.get("hit_rate") or 0.0)
    exp_per_trade = float(expected.get("avg_per_trade") or 0.0)
    return {
        "sessions": rec.sessions,
        "trades": rec.trades,
        "expected_hit_rate": round(exp_hit, 4),
        "realised_hit_rate": round(rec.hit_rate, 4),
        "hit_rate_delta": round(rec.hit_rate - exp_hit, 4),
        "expected_avg_per_trade": round(exp_per_trade, 2),
        "realised_avg_per_trade": round(rec.avg_per_trade, 2),
        "avg_per_trade_delta": round(rec.avg_per_trade - exp_per_trade, 2),
        "realised_net_pnl": round(rec.net_pnl, 2),
        # Stated explicitly so nobody reads a 3-session agreement as confirmation.
        "underpowered": rec.sessions < MIN_SHADOW_SESSIONS or rec.trades < 20,
    }


def promote_if_ready(session, candidate_id: int, expected: dict, *,
                     min_sessions: int = MIN_SHADOW_SESSIONS) -> bool:
    """Move a candidate from `shadow` to `pending` only once it has earned it,
    attaching the expected-vs-realised comparison to its scorecard.

    This is the function that enforces the phase's acceptance criterion: no
    candidate reaches the approval queue without shadow evidence.
    """
    import json

    cand = session.get(PromotionCandidate, candidate_id)
    if cand is None or cand.status != STATUS_SHADOW:
        return False
    ready, reason = is_ready_for_approval(session, candidate_id,
                                          min_sessions=min_sessions)
    if not ready:
        return False
    try:
        payload = json.loads(cand.scorecard_json or "{}")
    except ValueError:
        payload = {}
    payload["shadow"] = comparison(expected, session, candidate_id)
    payload["shadow"]["admitted_because"] = reason
    cand.scorecard_json = json.dumps(payload)
    cand.status = STATUS_PENDING
    session.flush()
    return True


def approval_queue(session) -> list:
    """Candidates a human should look at. `shadow` candidates are deliberately
    NOT here — that is the whole gate."""
    return (session.query(PromotionCandidate)
            .filter(PromotionCandidate.status == STATUS_PENDING)
            .order_by(PromotionCandidate.id.desc()).all())
