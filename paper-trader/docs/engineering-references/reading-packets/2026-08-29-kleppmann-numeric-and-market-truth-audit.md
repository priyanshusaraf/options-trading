# Kleppmann numeric and market-truth reading packet

This bounded packet is recorded in:

- [`../../research/kleppmann/source-notes/2026-08-29-numeric-and-market-truth-audit.md`](../../research/kleppmann/source-notes/2026-08-29-numeric-and-market-truth-audit.md)
- [`../source-notes/2026-08-29-numeric-and-market-truth-audit.md`](../source-notes/2026-08-29-numeric-and-market-truth-audit.md)
- [`../refresh-reports/2026-08-29-kleppmann-numeric-and-market-truth-audit.json`](../refresh-reports/2026-08-29-kleppmann-numeric-and-market-truth-audit.json)
- [`../source-registry.yaml`](../source-registry.yaml)
- [`../claim-registry.jsonl`](../claim-registry.jsonl)

It preserves the 373-record first-party inventory and the 2,016-record one-hop
triage. It reviews nine public external artifacts, reuses the accepted Kleppmann
packet and runs six isolated repository probes. It records seven claim decisions:
two confirmed current bugs, two missing numeric/causal invariants, one deferred
units contract, one group of controls that already hold, and one locale/currency
future seam.

The packet changes no product behavior. It adds no dependency, schema, frontend,
provider connection, deployment, live, order or money authority. Each applicable
finding needs a separate product capsule and direct verification under its exact
V0 or V1 owner.
