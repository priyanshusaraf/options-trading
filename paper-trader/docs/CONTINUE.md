# CONTINUE

Session handoff. Four things. Rewritten on every stop.

**For project state read [`PROGRESS.md`](PROGRESS.md). To implement, read
[`engineering/WORKSTREAMS.md`](engineering/WORKSTREAMS.md) and go to your workstream.** This
file is the resume point, not the overview.

---

## 1. Current phase

**Execution-first foundation update (2026-08-09):** the isolated
`codex/execution-foundation` branch now contains migration `0014`, immutable live-entry intent
and event records, lifecycle-first restart recovery, cumulative fill-delta accounting, a durable
protection-before-booking boundary, normalized broker reads and persisted execution telemetry.
It is not deployed and did not contact Kite. Broker expansion, authentication and tenancy remain
deferred. The next backend slices are the causal strategy contract, content-addressed backtest
cache and the 100-user deployment/soak boundary described in the execution-first roadmap.

**Stage A through S4.6d is implemented. The M-band (M1–M6) is closed; the next boundary is the
owner-gated L1 execution-integration adoption design.** Fail-closed CI is on the branch. Its first
run exposed two environment-boundary tests that assumed `PT_DISABLE_DOTENV` was absent; the tests
now remove the variable explicitly and the workflow retains its global safety guard. A follow-up
Linux run exposed that cancelling a lane abandoned its active `asyncio.to_thread` worker; `b243b59`
drains those workers before the broker session closes. F13 is published at `22a148f`. The React
viewer now loads the sparse layout, moves authored nodes by pointer or keyboard, saves by revision,
and retains local work on conflict or transport failure. ADR 0001 rejects duplicate product
ledgers and accepts the minimum ownership, identity and lifecycle contract. S2.2 adds durable
projects, optimistic graph drafts, append-only graph versions and reversible layout ownership.
S3.1 applies bounded edit batches through the existing IR primitives. S3.2a adds one coherent
editor document plus revision-safe graph rename and parameter override interaction. S3.2b adds
final-state semantic node/edge batches, separately revisioned visual groups, atomic presentation
reconciliation, server-derived component/socket descriptors and accessible structural/group
controls. Backend receipts restore both semantic and presentation state during undo/redo.
S3.3 proves an equivalent closed structural history and hand-authored reference have identical
canonical executable identity, and that graph plus presentation state reloads without loss.
S4.1 binds an exact project-owned immutable graph version to the existing research orchestrator.
S4.2 persists content-addressed success and controlled-failure evidence, exposes project-owned
history/detail/comparison, records pending-only canonical candidate decisions with reasons, and
renders the evidence and decisions accessibly. The superseded combined approval/deployment write
is closed; preview remains read-only.
S4.3 keeps the existing Finding ledger, derives exact graph/evidence binding through its verified
run foreign key, creates interpretations from completed evidence only, and revises by atomic
immutable successor. The UI shows automated/authored active and superseded history and retains
revision intent on conflict.
S4.4 gives nightly and manual research one shared OS lock and a canonical atomic current/last
receipt. The read-only status API and cockpit show bounded plan identity, progress and safe failure
without exposing remote run controls or invoking research during reads.
S4.5 compares server-owned immutable graph documents by structure, components, parameters,
interface, metadata and exact identity, then optionally composes verified persisted run evidence.
The UI selects versions and paired evidence without supplying graph or evidence claims.
S4.6a derives one project-owned timeline from verified immutable graph, run, finding and candidate
facts and keeps the global operation receipt outside project identity and pagination. Closed filters,
content-addressed cursors, current queues and source-error containment are exposed through one
read-only route and accessible daily-review surface without invoking research or write seams.
S4.6b persists non-authoritative project review notes and saved filter views under optimistic
revisions. Notes anchor only to server-derived project events and survive missing source events
without stale summary copies. Saved views contain no cursor or queue visibility state. Migration
`0008`, closed principal-aware APIs and accessible workflows leave source facts and identities
unchanged.
S4.6c searches only verified project-event summaries and active owner-note bodies. Its pure
Unicode-stable literal matcher uses bounded sources, deterministic rank and query-bound keyset
cursors. The closed read route and accessible transient UI contain source failures and never load
raw graph, evidence, scorecard, candidate-reason or global-operation text.

L1 Stage 1 is **engineering-closed** with the warmup/history admission contract, and
execution-state ownership is defined, gated and now **wired**: `EngineRunner` resolves every
strategy through `execution_binding.bind`, proven equivalent to the resolution it replaced,
with AST guards against both a second resolver appearing in the runner and the contract call
being removed. `ir_graph` remains `shadow` in `AUTHORITY_BY_SOURCE`; a refusal skips the
instrument and substitutes nothing; every writer of an engine assignment passes
`assert_may_execute` and the API answers 409 with the reason.

**Nothing in this session is deployed.** The engine still calls `compute()`; the route is a
viewer and does not adopt the IR runtime in a live path. The wiring changed which code
answers "what runs here", not what the answer is.

**L1.2b closed execution attribution.** L1.2 canonicalised execution selection authority; L1.2b
canonicalises execution attribution. The binding that produced a signal is carried from the
scan to the fill, so a stale assignment no longer trades the default while the money record
names the key that failed to resolve. `publish_signal` writes a signal and its binding through
one door; a state entry with no binding is a signal whose author is unknown and the entry
paths refuse to open on one. No schema change and no migration — all 72 production live trades
already carry a valid key or the documented `NULL` (ADR 0012 §4.1b).

**L1.3A shipped managed shadow deployment binding.** The IR shadow pairing is now a
server-owned record (`ir_shadow_deployments`, migration `0011`,
`app/core/shadow_deployments.py`) rather than runtime machinery, with staged /
shadow-active / paused / retired lifecycle, revision-guarded transitions, verified graph
content address and research lineage, warmup admission checked before activation, and
deterministic reload after restart. `execution_binding.shadow_source_for` is the one
boundary the observer asks; managed deployments outrank the legacy key pairing, which is
kept and named as the fallback. Authority is refused three times independently — the
authority map, database CHECK constraints, and a service with no mode parameter.

**L1.3B separated the execution books.** `app/core/execution_book.py` answers "whose money
is this", and the answer is the execution mode — no new abstraction, because
`positions.mode` and `trades.mode` already named it. What was missing was reach: the
discriminator was read by *no* position query and did not exist on `capital_state` (one
row, mutated in place) or `equity_snapshots`. Migration `0012` adds it to both and
back-stamps nothing. `broker.open_positions`/`position_for` scope ~35 call sites from one
chokepoint; the daily-loss breaker, round-trip cap, re-anchor, drift, restart and the
startup lot-size repair each count only their own book. Resolution fails closed to `live`.
Scoping the exit lane makes an orphan possible — chosen deliberately, because a paper
broker can only fake a live close — so `foreign_book_positions` reports the other book's
open rows at startup and on `/api/health`. Authority is now a reviewed
`(source, execution_mode)` pair; `(ir_graph, paper)` is **absent**.

**L1.3C shipped IR paper authority.** `(ir_graph, paper, authoritative)` is granted;
`(ir_graph, live, authoritative)` is not. `ir_paper_deployments` (migration `0013`) +
`app/core/paper_authority.py` bind an approved graph version to one instrument and interval
in the paper book, with verified evidence, a staged/paper-active/paused/retired lifecycle,
and an explicit named rollback target. The grant alone does not confer authority — a
graph-backed binding must also come from a paper-authority record and match the approved
content address, recomputed at the gate. Attribution now carries `strategy_key` **and**
`strategy_version` on all three entry paths and onto the `Trade` row.

**Owner gate, now the live one:** `(ir_graph, live, authoritative)` — designed nowhere and
**not built**. Nothing may let IR output influence simulated or live
orders, positions, accounting, sizing, routing, exits, reconciliation or risk without
explicit approval. The design is presented separately.

## 2. Repository and remote state

- Active isolated worktree for this increment:
  `/Users/priyanshusaraf/dev/options-trading/.claude/worktrees/codex-execution-foundation`
- Active isolated branch: `codex/execution-foundation`
- This branch is local and not pushed or deployed.

- Repository root: `/Users/priyanshusaraf/dev/options-trading`
- Application root: `/Users/priyanshusaraf/dev/options-trading/paper-trader`
- Branch/upstream: `feat/exec-completeness` / `origin/feat/exec-completeness`
- Last completed/pushed bounded increment before this handoff: failed-run evidence through `6f474f0`
- S4.2 comparison increment: `f809e2d`
- S4.2 product-surface slice: current HEAD after this handoff is published
- S4.3 backend lineage boundary: `c645b64`
- S4.3 product-surface slice: current HEAD after this handoff is published
- S4.4 operations observability: current HEAD after this handoff is published
- S4.5 version/evidence comparison: current HEAD after this handoff is published
- S4.6a daily review: current HEAD after this handoff is published
- S4.6b review notes/saved views: current HEAD after this handoff is published
- S4.6c bounded review search: `b8831c7`
- S4.6d immutable review snapshots: current HEAD after this handoff is published
- S3.2b structural frontend boundary: `0b3b784`
- Expected ahead/behind after publishing this handoff: `0/0`
- Working tree expected after publishing this handoff: clean

The commit containing this handoff is the current HEAD after publication; resolve its SHA with
`git rev-parse HEAD`. A Git commit cannot embed its own content-derived SHA. Verify the published
state with `git rev-list --left-right --count '@{upstream}...HEAD'` and `git status --short`.

The VPS build was **not measured this session.** `curl localhost:8090/api/health` on the box is
the only answer — never read it off a document.

## 3. Latest acceptance evidence

Execution-first foundation checkpoint on 2026-08-09:

```text
$ .venv/bin/pytest -q tests research_tests
3,698 collected · 3,692 passed · 6 expected skips · EXIT 0

$ PT_PROVIDER=mock PT_EXECUTION=paper .venv/bin/python scripts/dryrun.py 700
cash ₹187,733.06 · expected ₹187,733.06 · diff -0.0000 · LEDGER OK · EXIT 0

$ PT_PROVIDER=mock PT_EXECUTION=paper .venv/bin/python scripts/backtest_smoke.py
16/16 cells · net<gross where charged OK · SWEEP OK · EXIT 0

$ .venv/bin/python -m app.db.migrate head
0014 · EXIT 0

Live broker calls: none
Deployment: none
```

Latest acceptance run on 2026-08-07, for the L1.3A managed shadow deployment slice:

```
$ .venv/bin/python -m pytest tests research_tests
3,184 passed · 6 skipped · EXIT 0            (209s)

$ .venv/bin/python scripts/dryrun.py 700
RECONCILE cash vs expected: 187,733.06 vs 187,733.06 (diff -0.0000) · LEDGER OK · EXIT 0

$ .venv/bin/python scripts/backtest_smoke.py
net<gross where charged : OK ✓ · SWEEP OK ✓ · EXIT 0

$ .venv/bin/python -m app.db.migrate head
0011 · EXIT 0                                 (ir_shadow_deployments, model/migration parity green)

$ .venv/bin/python scripts/ir_shadow_mutations.py
all 35 guards reddened on their own defect and were restored · EXIT 0

$ npm test -- --run && npm run typecheck && npm run build
222 passed · TYPECHECK OK · BUILD OK · EXIT 0      (no frontend files modified)
```

The C13 conformance test went red on the first draft of the wiring — a runner docstring used
the word "provenance", which executor paths may not name. The guard was right and the prose
was wrong; the fix was the wording, not the allowlist. The authority gate does inspect a
source, and it lives in `app/core/`, outside the executor perimeter, with the engine
consuming only the verdict.

Two guards had to be repaired before they counted as evidence in L1.2b. A mutation
("re-resolve the identity at the fill") stayed green against a test that flipped the
assignment from inside `open_equity_position` — the attribution argument is evaluated before
the call, so the window was never open; the test now drives the scan and the entry as
separate halves of a tick. And ten attribution tests failed in the suite while passing alone,
because five wiring files pin `provider.now` on the process-wide singleton at sixteen sites
and never restore it, freezing the market clock past the 09:30 entry gate. Fixed once in the
rootdir `conftest.py` (ADR 0012 §4.1a).

Earlier, in L1.2: one of the six mutations exposed a **vacuous test**: "assign a graph key and
watch the engine refuse" never reaches the authority re-check, because `bind` already refuses at
resolution. The re-check is now proven against a *forged* binding from a drifted resolver,
which is the only thing it defends against.

Note this project's pytest config sets `addopts = -q` and suppresses the trailing count line;
`-rs` or `--collect-only` is how you get exact numbers. An `EXIT 0` with no visible summary is
normal here and is not evidence that nothing ran.

S4.6d's checkpoint was required because migration `0009` adds durable historical state. Eight
deliberate mutations were proven red and restored: forbidden seam, content-address verification on
read, listing bound, corrupt containment, archived fail-fast, the append-only DELETE trigger,
source-change rejection and source-error refusal. Two defects surfaced and were fixed rather than
noted: the content-address guard was **vacuous** (its fixture failed schema validation before
reaching the address comparison, so an isolating valid-manifest/false-address case now pins it),
and the seam guards patched unresolved bindings (`graph_artifacts` holds its own `resolve`
reference, and one leg patched a function that does not exist) — they now patch resolved bindings
with `raising=True`. A frontend request gate stops a superseded capture or project switch from
adopting a stale response, and `ExperimentRun.decision` is narrowed to the orchestrator vocabulary
before it can enter an immutable content-addressed summary.

S2.2's final editor/IR/persistence regression passed 337 tests. The focused persistence set passed
41 tests, including `0006 → 0005 → 0006`, orphan quarantine/restore, direct-SQL immutability,
stale draft conflicts and rollback after a flushed version insert.

S3.2a's focused backend editor/layout/graph/view set passed 104 tests, its WS-04 regression passed
310 and its database/migration regression passed 86. Focused frontend editor tests passed 39.
Transaction guard mutations proved stale-CAS, closed-schema, layout-identity, response rollback and
canonical-inverse assertions fail for their intended reasons before restoration.

S3.2b's backend WS-04 regression passed 131 tests before the shared checkpoint. The frontend
workstream regression passed 51 tests. Negative controls proved visual groups cannot contaminate
content addresses, invalid final semantic state cannot publish, reconciliation cannot leave the
transaction, removed nodes cannot retain positions/memberships, semantic-only undo is incomplete,
different canonical JSON cannot claim one executable identity and routes cannot bypass
`app.ir.edit.apply_batch()`. The full checkpoint first exposed the superseded public
`carry_layout_forward()` wrapper; removing that dead surface made the no-unconsumed-mechanisms
guard and complete acceptance green.

S3.3's focused equivalence/reload proof and 187-test WS-04 regression pass. The proof uses a closed
add/connect/disconnect/remove history and an independently built reference at the same immutable
version. It disposes database connections before reload, compares the full coherent document, then
replays the persisted inverse receipt. Presentation-contamination, semantic-content, node-order,
edge-order and executable-identity diagnostics are pinned. S3.3 changes no schema, research gate or
execution path, so the complete checkpoint was not repeated after S3.2b's immediately preceding
green run.

S4.5's focused backend/API set passed 37 tests and the combined WS-03/04/API regression passed 141.
All 209 frontend tests, typecheck and production build pass. S4.5 changes no schema, runtime or
safety boundary, so S4.4's 2,883-pass full checkpoint and exact-head green Actions run
`30819757907` remain the shared baseline.

S4.6a's final focused set passed 13 backend and 17 frontend tests. Its combined immutable-version,
editor-equivalence, experiment, finding, project/API, operation and review regression passed 104
tests. All 212 frontend tests, typecheck and production build pass. Guards cover stable/tamper-proof
pagination, one-session research derivation, wrong-project exclusion, corrupt candidate/global
receipt containment, global-operation non-attribution and no resolver/provider/orchestrator/write
calls. It changes no schema, execution or shared-runtime boundary, so the S4.4 full checkpoint is
not repeated.

S4.6b's focused migration/repository/API/review set passed 44 backend tests and its frontend
transport/surface set passed 19. The shared-persistence checkpoint collected 2,928 backend/research
tests and completed with 2,922 passed plus 6 expected skips. All 214 frontend tests, typecheck and
production build pass; deterministic smoke reports `LEDGER OK` and 16/16 `SWEEP OK`; migration head
is `0008`. Negative proofs cover destructive downgrade refusal, stale CAS rollback, immutable note
anchors, missing-source retention without copied summaries, global/wrong-project anchor refusal,
owner normalization, graph/presentation identity invariance and no IR/research/execution writes.
Exact-head S4.6a Actions run `30822688238` is fully green.

S4.6c's 13 focused backend search guards and 183-test WS-03/04/08 regression pass. All 216
frontend tests, typecheck and production build pass. Guards cover Unicode/case/whitespace
normalization, literal matching, stable query-bound pagination, source bounds, cross-project and
deleted-note exclusion, missing-anchor notes, corrupt-source containment and no IR, research,
execution or review-write calls. S4.6c changes no schema or shared runtime, so S4.6b's 2,922-pass
plus 6-skip shared-persistence checkpoint remains current. Exact-head S4.6b Actions run
`30824375970` is fully green across backend, frontend and deterministic smoke.

S4.3's focused and WS-03/API regression collected 570 tests and completed with 6 skips. All 204
frontend tests, typecheck and production build pass. Negative proofs cover cross-project and raw
identity input, non-completed/legacy/corrupt evidence, internally consistent but contradictory
terminal envelopes, stale revision with no orphan successor, post-insert rollback, no recomputation
on reads and lossless active/superseded reload. No schema/runtime/safety boundary changed after the
immediately preceding S4.2 full checkpoint.

CI was implemented test-first. The six contract tests first failed because the workflow was
absent. Guard proof then removed `research_tests` from the backend command; the specific contract
test failed on that missing root. A second mutation replaced official checkout with a SHA-pinned
unapproved action; the action-origin guard failed. Both returned green after restoration.

The first Actions run on `c48dd27` failed two tests because CI's deliberate global
`PT_DISABLE_DOTENV=1` reached test cases simulating a real non-pytest process. The correction at
`4f8fb9a` keeps the global guard and makes both tests delete the variable explicitly. The 36
CI/config safety tests pass with `PT_DISABLE_DOTENV=1` in the caller environment. Run
`30797183456` then exposed the shutdown race: a cancelled wrapper returned while its SQLite
worker kept running, so later app startup could not drop `order_journal`. The focused cancellation
regression and the complete CI-shaped suite pass after `b243b59`.

Known dependency risks: backend requirements use version floors rather than a lockfile; `npm ci`
reports six audit findings (three moderate, two high, one critical). The frontend tests/build are
green, but those findings remain open and must not be described as solved by CI. The built JS is
227.39 kB gzip, above the current 200 kB Vite-SPA profile budget; the build warning remains open.

Live-browser acceptance used a dotenv-disabled mock/paper backend with temporary databases.
Desktop and 390×844 rendered 18 node articles, 35 SVG paths and 35 connection rows with no
console errors. At phone width the 2,216px canvas stayed inside a 356px scroller and the page did
not overflow.

New route guards proven able to fail rather than merely observed passing: unversioned
registration, `/api/v1` mirroring, complete serialization including cache identity, read-only
graph identity, and library-dependent F7 validation. The fixed catalogue also rejects unknown
identifiers before `resolve()` is reached.

S1.1 was test-first: the layout routes first returned 404 and migration head remained `0004`.
The completed checks cover empty read, sparse replace/reload, stale 409 with no partial write,
unknown/derived/duplicate/non-finite/extra-field rejection, orphan filtering and cleanup,
`/api/v1`, schema equivalence and `0005 → 0004 → 0005`. Injecting layout into the graph hash
input made the identity proof fail on the expected mismatch. After restoration, graph content
address, component versions, node cache identities and experiment binding stay unchanged while
the rendered node uses its stored coordinate.

S1.2 was also test-first. The layout transport tests first failed with missing functions; layout
rendering first ignored stored coordinates; move handles, deterministic movement and save-state
tests each failed before their implementation. The completed state machine retains the exact
draft on 409 and transport failure, retries a conflict against the server-reported revision, and
replaces local work only through explicit reload. A guard test requires the persistence function
to receive the full sparse draft, so suppressing the save call turns it red.

Frontend guards were also observed red before implementation: missing graph transport, missing
canvas module, missing tab wiring, non-semantic node cards, collapsed impurity policy, absent
state presenter and absent scroller containment. The reviewed result has no remaining Critical
or Important finding.

Five shapes of **vacuous test** were caught this session by suppression sweeps and fixed —
right-clause-wrong-cause, a fixture already corrupted by an earlier test, checking only the
endpoints, a presence check masking a comparison check, and a case refused for the wrong reason.
All look exactly like passing tests.

Two measurement traps hit this session, both worth not repeating: a sweep grepping only
`^FAILED` misses mutations that break a **fixture** (those report as `ERROR`), and `$?` after a
pipeline is the pipe's exit code, not the command's.

## 4. Next concrete action

**Read this block first; everything below it is older and partly superseded.**

### Resume point, 2026-08-09 (evening)

`codex/execution-foundation` is now the line of record by owner decision, and it is **pushed**
(`origin/codex/execution-foundation`). Exact-head Linux CI run **`31326084453` is green** across
backend, frontend and deterministic smoke — the first time this branch has ever been checked on
Linux, which matters because the two hardest failures this project has had were Linux-only.

Three owner corrections landed and they change the shape of two phases. The full analysis is
[`superpowers/specs/2026-08-09-scale-and-cost-corrections-design.md`](superpowers/specs/2026-08-09-scale-and-cost-corrections-design.md):

1. **500 users from the start**, not 100. The five-accounts-per-worker figure is withdrawn as an
   unmeasured assumption — at 500 users it implies 100 worker processes and a hosting bill the
   owner has named as a blocker. Market data must be fanned in **once per distinct instrument
   set** and broadcast; per-account credentials are for orders, not prices.
2. **10,000 × 5 backtest tier in a few minutes**, not 1,000 × 5.
3. **The frontend is an owner gate.** Do not touch `frontend/`. Write requirements into the
   design notes and stop at the API boundary.

**Phase 5 (scalable sweep) is the active work, and it is now measured** — hardening record §10.
A cell is 84.7 ms on realistic 5,000-bar datasets, down from 185.7 ms after `5ba1233` removed a
`scipy.stats.norm.cdf` wrapper that was 74% of the premium replay. Two floors remain, both named
and neither closed:

- **Live-fetch I/O: 5 h 33 m** for 50,000 datasets, which is Kite's documented rate limit and is
  not optimisable in our process. The local content-addressed dataset store is therefore the only
  path to the target and has been **promoted ahead of batch persistence** in the plan.
- **Serial compute: 4,236 s**, still ~20× over target, which is what justifies measured
  multiprocess fan-out. Peak allocation is 2.10 MB/dataset, so the sweep must stream rather than
  accumulate — 50,000 held at once would be ~105 GB.

**Task 3 is DONE (`e985d77`)** — `app/backtest/dataset_store.py`, filesystem blobs, own SQLite
index, no migration. Measured **38 bytes/bar** (≈10 GB at the full tier; the mock's 22 flatters,
do not plan against it). The sweep **writes only** — there is deliberately no read path, which is
what makes "a normal refresh still costs its reads" hold by construction.

**Task 4 is the next task**: the pinned warm path, where the store's zero-fetch payoff is
actually collected. Its whole risk is in one sentence of the design — a pinned run that cannot
find or verify a dataset must **fail closed**, never silently fall back to fetching, because that
turns a pinned run into a refresh wearing a pin's name. Then Task 5 (batch persistence), Task 6
(measured multiprocess fan-out), Task 7 (tiered benchmark).

### Defects and traps found on 2026-08-09, worth not rediscovering

- **`LogBus` has `warn`, not `warning`.** `sweep.py` used the wrong name in *both* degradation
  handlers, so a dataset that could not be addressed aborted the **entire sweep** instead of
  skipping one cell. Guarded by `tests/test_logbus_method_names.py`. Note `app/core/earnings.py`
  uses the *stdlib* logger, where `.warning` is correct — a blanket grep would break it.
- **A vacuous guard, caught by mutation.** The first version of that AST guard looked for
  `x = get_logger(...)`, which almost nothing uses; the real idiom is
  `from app.core.logging import log`. It matched nothing and passed over the very file whose bug
  prompted it. Sixth shape of vacuous test on record here.
- **The 6.61 ms/cell figure was measured on the wrong workload** — 600-bar datasets when a real
  15-minute/200-day window is ~5,000 bars, and **the premium replay books zero trades below
  ~5,000 bars**, so every premium timing at 161 or 1,000 bars was timing an empty loop.
- **Gitignored is not rsync-excluded.** `deploy.sh` would have pushed ~10 GB of candle blobs to
  the droplet. Now in `EXCLUDES` with a test pinning it — the script's header already records two
  outages of this exact class.
- **`scipy.stats.norm.cdf` is a wrapper, not the maths.** It calls `scipy.special.ndtr`; calling
  `ndtr` directly is bit-identical and 232× faster on scalars. Do **not** replace it with a
  `math.erf` expression — that is *nearly* identical, differs in the last mantissa byte, and would
  move every backtested option price without failing anything loudly.
- **WebSocket fan-out was re-encoding per client.** Fixed (`0d6ac14`): 500 `json.dumps` per push
  → 1, 148.94 ms → 0.33 ms. Still open: `_ratchet_atr`/`_ratchet_high` engine internals ship to
  every browser (the delta-protocol slice).

---

**Historical from here.**

**Do not resume at L1, shadow adoption, or the live-authority design.** L1 is closed through
L1.4; `(ir_graph, live, authoritative)` is absent by design and is an **owner gate**, not a task
waiting to be picked up. The material below on L1.4 and the live-authority design is retained as
history, not as an agenda.

### The current phase — provider maturity, tenancy, execution integrity, measured performance

1. **Provider conformance contract — DONE (2026-08-09).** `tests/provider_conformance.py` +
   `tests/test_provider_conformance.py` hold every adapter to one semantic contract and catch
   adapters that lie about, or silently under-declare, a capability. Four defects found and
   fixed; `scripts/provider_conformance_mutations.py` proves 8/8 guards can go red. Full account
   in [`engineering/reference/backend-hardening-2026-08-08.md`](engineering/reference/backend-hardening-2026-08-08.md)
   §9, including five gaps left explicitly open.
2. **Settle `get_candles`'s missing failure channel — do this BEFORE Upstox, and start here.**
   `[]` means both "no history" and "the read failed". Verified consequence: `runner.py:725`
   already handles the failure — health failure, `_mark_token_bad` auth latch, break the scan —
   but `kite.py` swallows every exception, so on a live token expiry the engine records
   `record_ok("candle")` every tick, refreshes `last_scan_ok`, silently skips each instrument on
   the short-frame check, and the token-bad latch never fires. The health surface reports a
   healthy feed while nothing is arriving. Degrades toward no new entries (the safe direction),
   so it is not an emergency — but the signal is not measuring what it claims. Detail in the
   hardening record §9.4.1.
3. **Upstox, data-only** (historical + live quotes) — **designed, not built**. The API is
   already read and recorded in
   [`engineering/reference/upstox-data-adapter-design.md`](engineering/reference/upstox-data-adapter-design.md):
   instrument keys are `SEGMENT|ISIN` and cannot be derived from a tradingsymbol (which is what
   makes the `spot_symbol` relocation in item 4 provable); candles are arrays, documented
   newest-first, `+05:30`-aware; and the interval vocabulary is not Kite's — our live `15minute`
   is absent from v2 entirely. Four obligations in the conformance contract already cover those.
   Four things are **not** pinned (§5) and must be before it ships. Declaring `STREAMING` is out
   of scope: the live feed is protobuf over WebSocket. **Live verification needs Upstox
   credentials — an owner gate (§6).**
4. **Relocate `spot_symbol` / `option_name` off canonical `Instrument`**, using the second real
   mapping, proving Kite's resolution unchanged.
5. **Tenancy as a V1 blocker** — owner-scoped graphs, identifiers, deployments, research,
   connections and execution state; a migration path, not a bolt-on.
6. **Execution integrity around the real order lifecycle** — acknowledgement ambiguity, partial
   fills, average fill price, requested/decision/fill separation, slippage, duplicate and
   out-of-order events, cancel/fill races, idempotency, restart recovery, reconciliation.
7. **Backtest performance baseline** (~100 securities × 5 timeframes + parameter variation).
   Profile before optimising; no new language or infrastructure without a measured problem.
8. **Finish the research-integrity audit** — DSR/`var_sr`, cache-key dimensionality, cross-series
   temporal leakage.

---

**Historical from here.** L1.4 was closed on 2026-08-07; the live-authority design is owner-gated.

**L1.4 — paper-authority runtime hardening (2026-08-07).** 29 deterministic tests
(`tests/test_paper_authority_runtime.py`) covering restart and exact reload, stale-binding
withdrawal, exit ownership, kill-switch interaction, refused/failed entries, isolation,
shadow/paper separation and evidence. **One real defect found and fixed:**
`refresh_paper_authority` replaced the binding map but left `self.state` and
`self.executed_binding` intact — and those lifecycle routes run *between* a scan and an entry
pass, so retiring or pausing a deployment could still let the previous tick's signal open a
position attributed to a graph that was no longer authorised. The test opened one before the
fix. `_withdraw_superseded_signals` closes it: withdrawing authority withdraws the signal it
produced, scoped per instrument. Two mutations proven red and restored byte-for-byte.
Hard invariant 2 is proven against every form of withdrawal — a graph-opened position is still
marked, exited and squared off after pause, retirement, unverifiability and disarm.
**The "evidence reload gap" it reported was then investigated and is NOT a defect** —
[ADR 0013](engineering/decisions/0013-research-approval-is-admission-not-a-lease.md) settles the
semantics: research approval is an **admission prerequisite**, not an authority lease. Evidence
and approval are immutable and write-once (a decided candidate can never be re-decided;
`decide_project_candidate` refuses), so "withdrawing approval" is not an operation the system
has — only a *newer* decision exists. Measured: with every research door trapped to raise, reload
still loads the binding, rebuilds the adapter and verifies the content address three times, so
restart is already independent of the research plane. `resume` re-verifies evidence, which covers
the one boundary where stale approval was a real risk. **Do not implement an evidence re-read on
reload.** §7's identity-scope review did find real over-withdrawal in
`_withdraw_superseded_signals` — it discarded signals another binding had authored — now scoped to
state the withdrawn binding actually authored, with a mutation guard.

---

**The pre-L1.4 architecture correction is CLOSED.**

An architecture and reuse audit was taken at `75809a3` and is recorded at
[`engineering/reference/architecture-extension-review-2026-08-07.md`](engineering/reference/architecture-extension-review-2026-08-07.md).
It stress-tested twelve candidate product directions against the built code, executed five
extension drills against the real language, and concluded **outcome 2 — one small bounded
correction first, then L1.4 unchanged in scope.** Both corrections are now done:

1. **G-1 — the platform component library — SHIPPED.** `app/ir/library.py` composes the platform
   `(Library, IMPLEMENTATIONS)` pair from an explicit `CONTRIBUTORS` tuple and refuses contributor
   disagreement (conflicting component bytes, conflicting kernel declarations, one address with two
   implementations, a declared kernel with none). All six production call sites now take their
   library from it — `api/ir_edit_routes.py`, `editor/graph_artifacts.py`, `engine/ir_shadow.py`
   (×2), `core/paper_authority.py`, `ir/catalogue.py` and
   `research/orchestrator/graph_experiment.py`. **A strategy no longer serves as the platform
   registry.** Identity is byte-identical across the correction, by fingerprint over the graph's
   canonical JSON, its content address, every component body ref and every resolved node id, cache
   id, body ref and warmup: `1077ee8cdb53641e9451956994b6800a5c48a8bce6c2625ba3ea44f07c853590`
   before and after. No schema change; migration head stays `0013`.
2. **G-2 — the signal → intent → order boundary — SHIPPED for live entries.** Migration `0014`
   adds immutable entry intents and observations. Position, protection and booking remain distinct
   facts; restart recovery uses the lifecycle log as authority. Existing exits retain the legacy
   journal until a separate reviewed migration.

The review itself was amended after owner review (its Amendments section): F7 proves that
instrument identity participates in the type system and that *accidental* cross-domain wiring fails
closed — **not** that multi-instrument composition is implemented; the ten-bar drill proves
*data-derived* state is expressible, **not** that all stateful behaviour is (new gap G-8); and the
"no external code" conclusion is scoped to G-1/G-2 and is **not** project reuse policy.

What the audit found **healthy and not to be redesigned**: the one-resolver/one-validator/one-hash/
one-binding-authority structure; authority re-checked at the point of use against `GRANTS`;
provenance-blind execution (C13); paper/live book separation; and `publish()` already reproducing
the shipped ATR body address exactly. Multi-instrument runtime, typed non-OHLCV sources, multi-leg
intent, tenancy and the job/worker boundary (G-3) are all **safe to defer**, each with a named home
(WS-01 §5, L3, L4, L5). `(ir_graph, live, authoritative)` is untouched and remains **NOT APPROVED**.

---

**L1 Stage 1 (shadow lane) — STOP for a second owner approval.**

Stage 0 is complete and published. `app/strategy/ir_adapter.py` presents a resolved graph as
a `Strategy`; `tests/test_ir_adapter.py` proves parity **through the adapter** on real
recorded series across instruments, plus every closed failure path. The `research/` bridge
subclasses the shared adapter, inverting two declared policies (address-embedded identity,
short-window tolerance) rather than duplicating the evaluation.

**The live engine is still the sole execution authority.** No order, paper, shadow or live
path consumes the adapter, and a test asserts `app/engine/*` imports neither it nor `app.ir`.

Stage 1's structural and quantitative entry criteria are ADR 0011 §5. Do not begin it, or any
paper/shadow/live adoption, without explicit owner approval.

One correction carried into the record: ADR 0011 originally said to pass a persistent
`evaluate()` `Cache`. That was **wrong and would have produced silently stale live signals** —
`Cache` is keyed on `node.cache_id`, which is fixed at resolution and carries nothing about
the input data. Measured: reusing one across frames returns the previous frame's series with
all 18 nodes reporting hits. A guard test now pins the hazard.

The M-band is closed and no further review-workflow slice is queued. The next deliverable is a
written design, not code:

1. reconcile the live engine, strategy interface, deployment model, accounting, order lifecycle,
   reconciliation, shadow mode and rollback against the Component IR runtime;
2. enumerate every place the live path bypasses or conflicts with Strategy OS;
3. define the smallest safe adoption sequence, separating paper/shadow from live-money adoption;
4. state which existing execution behavior stays authoritative at each stage;
5. specify compatibility, shadow-validation, rollback, migration and failure containment;
6. produce a test-first plan with explicit non-vacuous safety proofs, and an honest scope/risk
   estimate.

**Do not begin live IR-runtime adoption, live-money activation or any material execution/risk
change before the owner approves that design.** Routine implementation, testing, documentation,
commits, pushes and CI continue autonomously once it is approved; human end-to-end product
validation is deferred by the owner and is not a blocker.

WS-08's typography item is **externally blocked**: it needs the owner's reference site.

Blocked on the owner, several sessions old — `PROGRESS.md` §3 and `ROADMAP.md` §2:

1. **Deploying the eight-phase architecture migration.** Committed, verified, off the box.
   Touches sizing, exits and order routing.
2. **Adopting the IR runtime in a live path.** RFC Appendix C(d); parity evidence now exists.
3. **VPS OS reboot** and **droplet resize 1 GB → 2 GB**.

> Environment notes: `python` is not on `PATH` — use `.venv/bin/python` from `backend/`. Capture
> the pytest exit code and final summary, and inspect both `FAILED` and `ERROR`: a mutation that
> breaks a fixture reports as ERROR, so a sweep grepping only FAILED reads it as vacuous.
