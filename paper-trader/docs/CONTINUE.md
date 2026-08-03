# CONTINUE

Session handoff. Four things. Rewritten on every stop.

**For project state read [`PROGRESS.md`](PROGRESS.md). To implement, read
[`engineering/WORKSTREAMS.md`](engineering/WORKSTREAMS.md) and go to your workstream.** This
file is the resume point, not the overview.

---

## 1. Current phase

**Stage A through S1.2 is published; S2.1 is accepted locally.** Fail-closed CI is on the branch. Its first
run exposed two environment-boundary tests that assumed `PT_DISABLE_DOTENV` was absent; the tests
now remove the variable explicitly and the workflow retains its global safety guard. A follow-up
Linux run exposed that cancelling a lane abandoned its active `asyncio.to_thread` worker; `b243b59`
drains those workers before the broker session closes. F13 is published at `22a148f`. The React
viewer now loads the sparse layout, moves authored nodes by pointer or keyboard, saves by revision,
and retains local work on conflict or transport failure. ADR 0001 rejects duplicate product
ledgers and accepts the minimum ownership, identity and lifecycle contract. S2.2 persistence is next.

**Nothing in this session is deployed.** The engine still calls `compute()`; the route is a
viewer and does not adopt the IR runtime in a live path.

## 2. Repository and remote state

- Repository root: `/Users/priyanshusaraf/dev/options-trading`
- Application root: `/Users/priyanshusaraf/dev/options-trading/paper-trader`
- Branch/upstream: `feat/exec-completeness` / `origin/feat/exec-completeness`
- Last completed/pushed slice: S1.2 conflict-safe layout editor through `1a27d39`
- Latest verified remote before the S2.1 commit: `1a27d39`
- Expected ahead/behind after publishing S2.1: `0/0`
- Working tree expected after publishing this handoff: clean

The commit containing this handoff is the current HEAD after publication; resolve its SHA with
`git rev-parse HEAD`. A Git commit cannot embed its own content-derived SHA. Verify the published
state with `git rev-list --left-right --count '@{upstream}...HEAD'` and `git status --short`.

The VPS build was **not measured this session.** `curl localhost:8090/api/health` on the box is
the only answer — never read it off a document.

## 3. Latest acceptance evidence

Latest acceptance run on 2026-08-03:

```
$ .venv/bin/python -m pytest tests research_tests --tb=short
2,719 passed · 6 skipped · 1 deprecation warning · EXIT 0

$ .venv/bin/python scripts/dryrun.py 700
RECONCILE diff -0.0000 · LEDGER OK · EXIT 0

$ .venv/bin/python scripts/backtest_smoke.py
net<gross where charged : OK ✓ · SWEEP OK ✓ · EXIT 0

$ npm test && npm run typecheck && npm run build
169 passed · TYPECHECK OK · BUILD OK · EXIT 0
```

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

**S2.2 — persist projects, editable graph artefacts and immutable graph versions.**

Implement the application-database portion of ADR 0001 test-first: Project, optimistic-concurrency
graph draft and append-only graph version. Seed the fixed catalogue version before attaching layout
ownership, enforce immutable versions against direct SQL, and keep deployment/research extensions
for their later gated slices. No runtime path adopts the new records.

WS-08's typography item is **externally blocked**: it needs the owner's reference site.

Blocked on the owner, several sessions old — `PROGRESS.md` §3 and `ROADMAP.md` §2:

1. **Deploying the eight-phase architecture migration.** Committed, verified, off the box.
   Touches sizing, exits and order routing.
2. **Adopting the IR runtime in a live path.** RFC Appendix C(d); parity evidence now exists.
3. **VPS OS reboot** and **droplet resize 1 GB → 2 GB**.

> Environment notes: `python` is not on `PATH` — use `.venv/bin/python` from `backend/`. Capture
> the pytest exit code and final summary, and inspect both `FAILED` and `ERROR`: a mutation that
> breaks a fixture reports as ERROR, so a sweep grepping only FAILED reads it as vacuous.
