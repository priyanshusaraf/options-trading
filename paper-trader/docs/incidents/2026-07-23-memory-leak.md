# Incident — 2026-07-23 memory-leak outage

*Relocated verbatim from `CLAUDE.md` on 2026-07-28. This is the historical post-mortem;
it is not a description of current system state. Open follow-ups from this incident are
tracked in [`../ROADMAP.md`](../strategy-os-v1-v2-v3/V0-V1-V1.5-V2-V3-V4-V5-V6-SCOPE-DECISION-MATRIX.md) (Workstream F) and
[`../operations.md`](../operations.md), not here.*

---

## 2026-07-23 memory-leak outage — FIXED & DEPLOYED (same day)

The live bot went down for ~24h on 2026-07-22/23. **Root cause (verified):** a process memory
leak in the WS broadcast hub, NOT a DB bug — the QueuePool timeouts in the logs were a symptom.
Chain: `WS broadcast leak → RSS 260MB→1.3GB in ~15min (only while a dashboard /ws client was
connected, ~+100MB/min) → 1GB VPS OOM → swap thrash → SQLite disk-bound → 15-conn pool
congestion-collapse → 30s timeouts everywhere`.

**It was TWO leaks, both fixed & deployed 2026-07-23:**
1. **WS broadcast hub** (commit `68c852e`): `backend/app/ws/manager.py` rewritten — producers only
   enqueue; `state`/`position_ticks` coalesce latest-wins; logs in a bounded 200-deep per-client
   deque; per-client sender task with 10s send-timeout eviction; `push()` is one
   `call_soon_threadsafe` callback per log line. TDD `tests/test_ws_manager.py`. This alone did NOT
   stop the dashboard-open leak (a bare `/ws` soak was flat, the real dashboard still leaked) —
   which is how leak 2 was found.
2. **Analytics full-table ORM scans** (commit `6b28645`, found by per-endpoint RSS isolation on the
   VPS): `/api/signals` (5s poll) ran `signal_counts()` materializing the whole 7-day
   `signal_events` window (~73k ORM rows, ~4.2MB retained/req, +55MB/min); `/api/dashboard` (5s
   poll) ran `equity_curve()` loading all ~72k `equity_snapshots` rows then slicing in Python
   (+21MB/min). Churned pages are allocator-retained → RSS ratchets to OOM. Both now aggregate/
   limit in SQL (`app/engine/analytics.py`); `/api/signals` latency 4.6s→0.23s. Tests:
   `test_signal_counts.py`, `test_equity_curve_query.py`.

Plus `MALLOC_ARENA_MAX=2` systemd drop-in (`paper-trader.service.d/malloc.conf`). **Verified:**
15-min soak replaying the FULL dashboard mix (all 8 polled endpoints at real cadences + `/ws`
client) — RSS 290→314MB with growth decelerating to flat (old code: +100MB/min → OOM ~7min).
Dashboard is safe to open. `option_cache_enabled` override cleared. Lesson: validate against the
real traffic mix, not the attributed trigger — the first "fixed" claim was wrong because the soak
only exercised `/ws`.

**Still open:**
1. **Headroom:** the 1GB DO droplet is small — consider resize to 2GB (owner action, DO console).
2. **Minor:** context-manage `_upsert_state` (runner.py) / broker's long-lived session; add
   `pool_pre_ping`, lower `pool_timeout`.
3. **Separate DB-bloat issue (owner wants a rethink):** `paper_trader.db` is ~45MB, +~5MB/day, from
   unbounded append-only `option_data`(~154k)/`signal_events`(~86k)/`equity_snapshots`(~72k). Options:
   retention/pruning, split telemetry to an archive DB, or move time-series off SQLite. NOT DECIDED.

**Ops notes:** SSH = `ssh -i ~/.ssh/paper-trader-vps root@64.227.191.162` (public IP + that key; no
ssh config; tailnet port 22 is Tailscale-SSH and hangs non-interactively). Deploy = rsync whole tree
from Mac + `systemctl restart paper-trader` (VPS has NO git). Engine is DISARMED on every start. A
DB snapshot from the outage is offloaded at `paper-trader/vps-snapshots/`.
