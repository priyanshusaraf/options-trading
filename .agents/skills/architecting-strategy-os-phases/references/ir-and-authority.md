# IR and authority invariants

- Keep one graph/IR language, validator, resolver, hash, component library, deployment authority, and research ledger. Graph versions are immutable and content-addressed; presentation state stays outside identity.
- Results bind to resolved graph and component versions, node identities, and a data digest derived by resolution. Every edit uses the canonical batch-edit seam. `resolve()` remains pure.
- Prove causality at every node by comparing prefixes. Never reuse an evaluation cache across input frames when its key omits data identity.
- Instrument and timeframe identity remain in the type system. Do not weaken the cross-domain guard for one strategy; add an explicitly typed operator only for a demonstrated need.
- Canonical execution binding is the single decision of what runs where. Requested assignment is not a resolved executable strategy. Preserve attribution from scan through fill and money record.
- Research approval is admission consumed once at activation, not a lease. Authority withdrawal withdraws its signals. Grant/regrant uses an exact content-address match.
- Keep `(ir_graph, live, authoritative)` absent. Any proposal to enable it, or to change live sizing, routing, risk, execution semantics, live VPS, credentials, destructive operations, licence-sensitive adoption, or customer-money decisions requires an owner gate.
- Keep paper and live books structurally separate and fail closed to live. ARM gates entries only; exits must remain available. Execution is provenance-blind; authority and capability checks belong outside the engine.

Read the governing RFC and ADRs before accepting a language or authority change. Require an observable proof and a test that fails under a deliberate guard mutation.

For execution-binding precedence or state ownership, read ADR 0012 before proposing a change. A completed critical slice receives one integrated critical review after its evidence package exists.
