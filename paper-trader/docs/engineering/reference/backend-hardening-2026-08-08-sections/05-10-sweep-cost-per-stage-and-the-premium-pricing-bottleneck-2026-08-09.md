Reference: [section index](../backend-hardening-2026-08-08.md). Read with its scope; this is not a new assignment.

## 10. Sweep cost, per stage, and the premium-pricing bottleneck (2026-08-09)

Taken to size the owner's 10,000 x 5 target ("a few minutes" = 50,000 cells). Machine: this
Mac, mock provider, `trend_impulse_v3`, median of 20 repeats, benchmark in the session
scratchpad.

### The 6.61 ms/cell figure was measured on the wrong workload

The supervisor review's 500-cell benchmark reported 6.61 ms/cell on 600 synthetic bars. Two
things make that number inapplicable to the tier maths:

1. A real 15-minute / 200-day window is **~5,000 bars**, not 600.
2. **The synthetic-premium replay produced zero trades** at 161 and 1,000 bars, so any premium
   timing at those sizes is measuring an empty loop. It only books trades once the series is
   long enough to contain expiry cycles — 300 premium trades at 5,000 bars.

Per-stage cost at 5,000 bars, one strategy (median ms):

| Stage | Before | After | Shared across strategies? |
|---|---:|---:|---|
| acquire (in-process, excludes throttle) | 0.11 | 0.11 | yes |
| address (`ordered_dataset_address`) | 11.01 | 11.75 | yes |
| frame (`prepare_signal_frame`) | 7.94 | 8.58 | yes |
| signals | 1.96 | 2.12 | no |
| simulate (spot) | 24.27 | 25.46 | no |
| **premium (synthetic)** | **140.43** | **36.71** | no |
| **TOTAL** | **185.71** | **84.72** | |

### The dominant cost was a scipy wrapper, not arithmetic

`cProfile` over the premium replay at 5,000 bars: of 0.731 s total, **0.539 s (74%) was
`scipy.stats.norm.cdf`** — 15,264 calls, two per `bs_price`. The time is in
`rv_continuous` generic machinery (`argsreduce`, `broadcast_arrays`, `_open_support_mask`),
not in the normal CDF.

`norm.cdf` computes its answer *by calling* `scipy.special.ndtr`. Calling `ndtr` directly is
the same function without the wrapper:

- **bit-identical** over 600,010 samples — uniform tails, standard-normal body, denormals,
  signed zeros, both infinities. Verified by `struct.pack` comparison, not `approx`.
- **232x faster** on scalars: 24.5 us -> 0.106 us per call.

Result: premium replay **140.4 -> 36.7 ms (3.8x)**, whole cell **185.7 -> 84.7 ms (2.19x)**.
`SWEEP OK` and 561 research/backtest tests unchanged.

`tests/test_options_pricing_identity.py` pins this. The guard was proven non-vacuous by
substituting the `math.erf` formulation — the obvious "equivalent" rewrite — which reddens both
the bit-identity test and a golden price. It differs in the **last mantissa byte**
(`b'@E;%ZoS@'` vs `b'\x80E;%ZoS@'`), which is exactly why an approximation here is more
dangerous than an outright bug: every backtested option price would move and nothing would
fail loudly.

### What the tier maths now says

Serial, one strategy, 5,000-bar datasets:

| Tier | Cells | Compute (serial) | Live-fetch I/O floor @ 0.40 s |
|---|---:|---:|---:|
| 100 x 5 | 500 | 42 s | 200 s |
| 1,000 x 5 | 5,000 | 424 s | 2,000 s (0.56 h) |
| 10,000 x 5 | 50,000 | **4,236 s (1.18 h)** | **20,000 s (5.56 h)** |

Two conclusions, both already in the plan:

- **The provider floor dominates and cannot be optimised in our process** — it is Kite's
  documented rate limit. The local content-addressed dataset store is the only path to the
  target, which is why it was promoted ahead of batching.
- **Compute still misses "a few minutes" by ~20x even after this fix**, so measured
  multiprocess fan-out is required and is now justified by measurement rather than preference.
  The next-largest remaining costs are `simulate` (25.5 ms) and `address` + `frame`
  (20.3 ms, paid once per dataset rather than per strategy).

Peak allocation is 2.10 MB per dataset for frame + signals, so 50,000 datasets held at once
would be ~105 GB. The sweep must stream datasets, never accumulate them — this constrains the
fan-out design.

## 11. WebSocket fan-out cost at 500 users (2026-08-09)

The owner named hosting cost at 500 users as a blocker and WebSockets as the part they have
been stuck on before. This is the first measurement rather than an opinion.

**Method and its limit.** Payload sizes are computed from the state entry shape built at
`runner.py:817-831` plus the ratchet keys at 839/841 and a held `Position.to_dict()`,
serialised compactly. This is a **reconstructed** payload, not a capture from a running
server — treat it as the right order of magnitude, and re-measure against a live process
before it becomes a deployment gate.

`main.py` `on_update` broadcasts `{"type": "state", "data": runner.state}` — the **whole**
state dict, every instrument, to every client, on every update.

| Instruments | Bytes/push | MB/user/hour @ 2.5 s tick |
|---:|---:|---:|
| 20 | 11,025 (10.8 KiB) | 15.9 |
| 50 | 26,545 (25.9 KiB) | 38.2 |
| 100 | 49,145 (48.0 KiB) | 70.8 |

At 50 instruments, 6.5 h/day, 22 days: **5.5 GB/user/month**, so **2,733 GB/month at 500
users**. Dashboards left open around the clock take that to ~13.8 TB.

### The bandwidth is not the problem. The serialisation is.

DigitalOcean bundles 1–2 TB per droplet and charges ~$0.01/GB beyond, so 2.7 TB/month is
roughly **$17/month** of overage — real but not the thing to fear. Even the always-on case
is ~$130.

The cliff is CPU. `manager.py:102` sends with `ws.send_json(msg)` **per client**, so the
same dict is JSON-encoded once per connected browser:

```
500 clients x 49 KB every 2.5 s = ~24 MB/s of JSON encoding, to send ~10 MB/s
```

That is the 2026-07-23 outage shape exactly — an application-level fan-out cost that grows
with users while looking like a bandwidth question. The manager is otherwise well built: it
already coalesces per client (`_COALESCE`, `client.latest` keeps only the newest message of
each type), so a slow consumer cannot accumulate a backlog. That part of the July rewrite
holds.

### Two corrections, neither of them "use polling"

1. **Serialise once, send bytes to many. — DONE, `0d6ac14`.** Each enqueued message is now one
   `_Frame` shared by every client, encoded at most once, lazily, inside `_sender`'s existing
   `try/except`. Measured on a 100-instrument payload to 500 clients over 20 pushes:

   | | `json.dumps` calls/push | wall/push |
   |---|---:|---:|
   | before | 500 | 148.94 ms |
   | after | **1** | **0.33 ms** |

   ~450x on the encode step. 149 ms of CPU every 2.5 s tick becomes 0.33 ms.

   Two guards, both proven able to fail. The encoding is byte-identical to starlette's
   `send_json`, pinned by diffing raw ASGI frames from a *genuine* starlette `WebSocket`
   against `send_json`'s own output for the same message, unicode included. And the encode
   stays **lazy** — moving it into `_enqueue` raises `TypeError` straight out of
   `broadcast()`, into the engine tick, instead of evicting the one client that cannot take
   the payload.

   One behaviour change, in our favour: `on_update` broadcasts the *live* `runner.state`, so
   each client's copy used to be serialised at that client's own send moment — clients could
   observe different states and the engine could mutate the dict mid-serialisation, once per
   client per tick. All clients now get one identical snapshot and that window shrinks 500x.
   A late-draining client reads text captured at first send: at most one tick stale, and
   coalescing replaces the frame next tick.
2. **Push deltas, not full state.** A 2.5 s tick changes a handful of fields on a handful of
   instruments, yet every push carries all of them, including `_ratchet_atr` — an
   underscore-prefixed engine internal already flagged in `api/dto.py`'s docstring as
   leaking to browsers. A delta protocol shrinks the payload by roughly the ratio of changed
   to total fields and closes that leak on the way.

Polling is strictly worse on both axes and is not proposed.

**Not yet measured, and still required before this is a gate:** bytes/user/hour captured
from a live process, accounts-per-core under a real session, resident memory per active
account, peak concurrent live accounts versus connected, and DB write throughput at peak
entries.
