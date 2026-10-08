"""Energy Up-Spike Fade — the shock-reversal engine set to fade UP-spikes only.

Same engine as `shock_reversal` (see that module for the mechanics). Natural gas
differs from crude in the 2019-2026 MCX-proxy research: its UP-spikes faded
reliably (every cell of the in-sample grid z 1.5-2.5 × hold 1-5 sessions was
profitable on the short side) while buying its DOWN-spikes lost money. NG spikes
also often happen overnight (weather-model runs, storage report), so the shock
is measured close-to-close with the overnight gap clipped to ±1.5% (a contract
roll gap can therefore never fire a signal on its own).

Defaults (chosen on NATGASMINI in-sample 2019-2023 only): close-to-close
z >= 1.5 vs the previous 60 sessions, short only, hold 3 sessions, no trend
filter, no pyramiding (a second-shock add helped in-sample but lost
out-of-sample).

Out-of-instrument check: the same settings, never tuned on crude, were
profitable on CRUDEOILM in both periods (IS 2019-23 +₹22k PF 1.5, OOS 2024-26
+₹32k PF 2.3; 7 of 8 calendar years positive, 2019 ≈ −₹0.5k), net of charges and
slippage, and on real NYMEX bars too — the strongest robustness evidence in the
research. Recommended for NATGASMINI and CRUDEOILM; not for gold (no up-spike
overreaction there). Entry timing is the live-compatible `next_session` default
inherited from `shock_reversal`.
"""
from __future__ import annotations

from .shock_reversal import ShockReversal


class SpikeFade(ShockReversal):
    key = "spike_fade"
    display_name = "Energy Up-Spike Fade (multi-session)"
    default_params = {
        **ShockReversal.default_params,
        "shock_mode": "close", "gap_clip": 0.015,
        "z_len": 60, "z_entry": 1.5,
        "side": "short", "hold_sessions": 3,
        "trend_sessions": 0, "trend_rule": "any",
    }


STRATEGY = SpikeFade()
