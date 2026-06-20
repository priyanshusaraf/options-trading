"""Turns engine events into short messages and pushes them through a sender
(Telegram by default; injectable for tests).

The 'approaching SL/TP' check is throttled: it fires once when the live premium
enters within `proximity_pct` of the stop or the target, and re-arms only after
the premium leaves that zone — so a 1-second risk loop never spams.
"""
from __future__ import annotations

from app.notify import telegram


class Notifier:
    def __init__(self, sender=None) -> None:
        self._send = sender or telegram.send
        self._near: dict[str, dict] = {}   # instrument_key -> {"stop": bool, "target": bool}

    def _emit(self, text: str) -> None:
        try:
            self._send(text)
        except Exception:
            pass  # a dead notifier must never disrupt trading

    # ── lifecycle events ──────────────────────────────────────────────────
    def opened(self, pos) -> None:
        self._emit(f"🟢 OPEN {pos.direction} {pos.tradingsymbol} @ {pos.entry_premium:.2f} "
                   f"— SL {pos.stop_price:.2f} / TP {pos.target_price:.2f}")

    def closed(self, trade) -> None:
        emoji = "✅" if trade.net_pnl >= 0 else "🔴"
        self._emit(f"{emoji} CLOSE {trade.tradingsymbol} [{trade.exit_reason}] @ "
                   f"{trade.exit_premium:.2f} — net ₹{trade.net_pnl:,.0f} "
                   f"({trade.return_pct:+.1f}%)")
        self.clear(trade.instrument_key)

    def signal(self, key: str, sig: str) -> None:
        self._emit(f"📡 SIGNAL {sig} on {key}")

    # ── approaching SL/TP (throttled) ─────────────────────────────────────
    def check_proximity(self, key: str, tradingsymbol: str, premium: float,
                        stop: float, target: float, proximity_pct: float) -> None:
        st = self._near.setdefault(key, {"stop": False, "target": False})
        near_stop = premium <= stop * (1 + proximity_pct)
        near_target = premium >= target * (1 - proximity_pct)
        if near_stop and not st["stop"]:
            self._emit(f"⚠️ {tradingsymbol} nearing STOP {stop:.2f} (now {premium:.2f})")
        if near_target and not st["target"]:
            self._emit(f"🎯 {tradingsymbol} nearing TARGET {target:.2f} (now {premium:.2f})")
        st["stop"], st["target"] = near_stop, near_target

    def clear(self, key: str) -> None:
        self._near.pop(key, None)
