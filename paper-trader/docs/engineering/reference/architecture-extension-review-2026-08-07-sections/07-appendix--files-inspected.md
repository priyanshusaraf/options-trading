Reference: [section index](../architecture-extension-review-2026-08-07.md). Read with its scope; this is not a new assignment.

## Appendix — files inspected

**IR / language.** `app/ir/schema.py`, `validate.py`, `resolve.py`, `runtime.py`, `kernels.py`,
`hashing.py`, `authoring.py`, `catalogue.py`, `edit.py`, `strategies/expanding_z.py`.

**Strategy.** `app/strategy/ir_adapter.py`, `spec.py`, `identity.py`, `registry/__init__.py`,
`registry/base.py`.

**Execution / core.** `app/core/execution_binding.py`, `paper_authority.py`, `execution_book.py`,
`scoped_config.py`, `app/engine/runner.py`, `broker.py`, `broker_protocol.py`, `execution_policy.py`,
`allocator.py`, `ir_shadow.py`.

**Data / persistence.** `app/providers/base.py`, `app/market_data/candles.py`, `app/db/models.py`,
`app/db/session.py`, `app/backtest/engine.py`, `app/backtest/sweep.py`,
`migrations/versions/` (0001–0013).

**API / editor / frontend.** `app/api/ir_edit_routes.py`, `principal.py`, `auth.py`,
`app/editor/descriptors.py`, `frontend/src/views/GraphView.tsx`.

**Documents.** `docs/ARCHITECTURE.md`, `docs/CONTINUE.md`, `docs/engineering/EXECUTION_PLAN.md`,
`docs/rfcs/0001-component-ir.md`, `docs/engineering/workstreams/WS-01-component-ir.md`,
`docs/engineering/decisions/0011`, `0012`, `docs/engineering/reference/multiverse-index.md`.

**Reference library.** `~/dev/multiverse-of-ideas/_meta/LICENCES.md`,
`reviews/nautilus-trader.md`, and the licence files of `nautilus_trader`, `xyflow`, `backtrader`,
`freqtrade`; `~/dev/openalgo/README.md`.

**Probes run** (scratchpad only, never added to the tree): a resolution/measurement probe, a
three-drill language probe (Drills 1, 2, 5) and a publish round-trip probe (Drill 4). All output is
quoted inline above.
