# Tool and asset scorecard

## Decision scale

- ADOPT: use directly after normal dependency and deployability checks.
- ADAPT: wrap behind a Strategy OS contract.
- REFERENCE: use patterns and tests only.
- SPIKE: run a bounded comparison before adoption.
- REJECT: do not use for the stated problem.

## Scorecard

| Tool or asset | Problem | Decision | Integration and operating cost | Licence and lock-in | Failure and exit posture |
| --- | --- | --- | --- | --- | --- |
| xyflow | graph canvas interaction | ADOPT in future frontend capsule | medium frontend integration | MIT, low lock-in when IR stays outside view model | replace canvas without changing semantic graph |
| pyKiteConnect | Zerodha transport | ADAPT | current known wrapper cost | MIT | SDK types stay at adapter edge |
| DhanHQ Python SDK | Dhan transport | ADAPT | current known wrapper cost | MIT | Strategy OS owns loop, errors, and lifecycle |
| Upstox Python SDK | Upstox transport | ADAPT | generated API and stream wrapper | permissive notice grant | generated models never cross adapter |
| Groww SDK package | Groww transport | SPIKE | auth, NATS feed, rate limits, and reference IDs require audit | licence unverified in this inspection | package replaceable behind adapter |
| Angel One SmartAPI | Angel One transport | SPIKE | TOTP, HTTP, stream, and lifecycle audit | licence unclear | no adoption before legal gate |
| Optuna | sampler and trial coordination | ADAPT later | low to medium; storage overlap | MIT | Strategy OS keeps search and evidence authority |
| DBOS Python | durable Workflow backend | SPIKE | new dependency and schema | MIT | current domain operations remain portable |
| Temporal Python | durable Workflow server | SPIKE only after measured need | high service and replay burden | MIT SDK; server stack needs full review | Workflow port preserves replacement |
| Restate Python | durable services | SPIKE alternative | medium to high new runtime | MIT SDK | same portable domain port |
| Riskfolio-Lib | portfolio risk math | SPIKE | numerical and solver validation | BSD-3-Clause | immutable allocation request and receipt isolate it |
| Pandera | V2 data validation | SPIKE in V2 | moderate dependency and schema mapping | MIT | canonical Strategy OS authority remains separate |
| Great Expectations | data quality operations | REFERENCE | high conceptual and operating surface | Apache-2.0 | no dependency now |
| DVC data | object-store semantics | REFERENCE | existing Strategy OS store already owns semantics | Apache-2.0 | rederive child-first publication |
| OpenLineage | generic lineage vocabulary | REFERENCE | low if docs only, higher if emitter | Apache-2.0 | exact Strategy OS facts remain authority |
| Hypothesis | property-based tests | ADOPT selectively | low test-only dependency | verify exact licence at dispatch | generated cases and shrunk fixtures remain local |
| Testcontainers Python | disposable integration services | REFERENCE | Docker and helper dependency | Apache-2.0 | current PostgreSQL harness remains fallback |
| Toxiproxy | deterministic network faults | SPIKE | one test service | inspect exact licence | remove without product changes |
| Centrifugo | browser realtime fan-out | REFERENCE then SPIKE | new service and backing store at scale | Apache-2.0 | WS transport port preserves exit |
| NATS | internal messaging | DEFER | new broker and operations | Apache-2.0 | no need before multi-process trigger |
| OpenTelemetry Collector | telemetry pipeline | REFERENCE then ADOPT under ops capsule | new service and exporter config | Apache-2.0 | domain evidence remains independent |
| Prometheus and Grafana | metrics and dashboards | REFERENCE | ordinary operating cost | verify exact distributions | standard export formats ease exit |
| TimescaleDB | time-series storage | REJECT now | extension operations and migration | mixed licence | no measured need |
| vectorbt | vector research engine | REJECT dependency | semantic overlap | Commons Clause conflicts with hosted use | ideas only |
| NautilusTrader | event-driven engine | REJECT replacement | large Rust and Python integration | LGPL-3.0 | current runtime stays |
| LEAN | full trading engine | REJECT replacement | duplicates Strategy OS | Apache-2.0 | use architecture patterns only |
| OpenAlgo code | broker and product code | REJECT code reuse | would merge competitor architecture | AGPL-3.0 | behavior reference only |
| TradingView chart library | chart rendering | SPIKE after commercial access and licence check | significant vendor integration | owner and legal gate | chart adapter and Strategy OS-owned artifacts |
| Lightweight Charts | basic chart rendering | KEEP current use | current frontend dependency | verify current licence at release | chart semantics stay outside vendor |
| Semgrep | static security rules | SPIKE | CI rule ownership | inspect current licence and offering | retain rules in repo |
| Gitleaks | secret detection | ADOPT under supply-chain capsule | low CI cost | inspect current licence | simple exit |
| Trivy | image and dependency scanning | SPIKE | image and database updates | inspect current licence | one owner avoids scanner overlap |
| Syft and Grype | SBOM and vulnerability scan | SPIKE alternative | CI and artifact retention | inspect current licences | choose one coherent stack |

## Immediate recommendations

1. Keep xyflow as the future canvas choice under the frontend owner gate.
2. Finish five-broker V1 work through official SDK wrappers, not copied implementations.
3. Keep current research operations until a bounded Workflow spike proves a better backend.
4. Add Hypothesis only for closed pure contracts where it finds failures the fixed suite misses.
5. Select one supply-chain toolchain in a dedicated capsule.
6. Add no new database, message bus, or orchestration service without measured need.
