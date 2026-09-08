# New repository backlog

Status: recommendations only. No repository was cloned.

Existing local clones were inspected first. A new clone earns a slot only when it answers one exact Strategy OS question.

## Priority 0

### Angel One SmartAPI Python

- Candidate: [angel-one/smartapi-python](https://github.com/angel-one/smartapi-python)
- Exact question: What authentication, instrument, order, WebSocket, and lifecycle facts must the V1 Angel One adapter contain?
- Why current clones are insufficient: official Zerodha, Upstox, and Dhan SDKs cannot establish Angel One semantics.
- Expected output: broker conformance packet, request and response map, failure taxonomy, exact tested commit, licence decision.
- Time: 1 to 2 focused days.
- Clone depth: shallow.
- Licence concern: the inspected GitHub page did not expose a clear licence. Stop for owner and legal direction before code adoption.
- Verdict: clone only inside v1-angelone-provider-and-execution-conformance.

### Groww Python SDK source

- Candidate: official package named growwapi, documented at [Groww Python SDK](https://groww.in/trade-api/docs/python-sdk).
- Exact question: What authentication, reference ID, rate-limit, feed, order, portfolio, and instrument contracts must the V1 Groww adapter contain?
- Why current clones are insufficient: no current local source covers Groww's API and feed.
- Expected output: package provenance, source location, licence, exact version, capability map, lifecycle and conformance plan.
- Time: 1 to 2 focused days.
- Clone depth: none until an official source repository is verified. Inspect the published package and licence first.
- Licence concern: official documentation proves the SDK exists but this search did not verify an official GitHub source or licence.
- Verdict: documentation and package audit first; do not clone an unofficial repository.

### Temporal Python SDK

- Candidate: [temporalio/sdk-python](https://github.com/temporalio/sdk-python)
- Exact question: Does a server-backed durable engine reduce Strategy OS Workflow recovery risk enough to justify a new service?
- Why current clones are insufficient: DBOS has no separate server and a different replay model.
- Expected output: comparison against current research operations and DBOS, versioning, cancellation, deterministic replay, service burden, migration, exit strategy.
- Time: 2 focused days plus one bounded non-money prototype only if approved.
- Licence: MIT.
- Clone depth: shallow with submodule needs recorded.
- Verdict: targeted review before any spike.

### Restate Python SDK

- Candidate: [restatedev/sdk-python](https://github.com/restatedev/sdk-python)
- Exact question: Can durable service objects express candidate and Workflow coordination with lower operational cost than Temporal?
- Expected output: same scenario and evidence as Temporal.
- Time: 1 to 2 focused days.
- Licence: MIT.
- Clone depth: shallow.
- Verdict: review as the materially different alternative in the durable-work decision.

## Priority 1

### Centrifugo

- Candidate: [centrifugal/centrifugo](https://github.com/centrifugal/centrifugo)
- Exact question: At what browser-client scale does the current WSManager need a dedicated fan-out server?
- Expected output: authentication, channel isolation, reconnect recovery, history, outbox integration, slow-client behavior, operational burden.
- Time: 1 day.
- Licence: Apache-2.0.
- Clone depth: shallow.
- Trigger: measured current WebSocket capacity failure or multi-replica frontend fan-out.
- Verdict: reference now, clone only at trigger.

### Hypothesis

- Candidate: [HypothesisWorks/hypothesis](https://github.com/HypothesisWorks/hypothesis)
- Exact question: Which closed Strategy OS invariants gain meaningful fault discovery from generated inputs and shrinking?
- Expected output: bounded adoption plan for IR, time, identity, ranking, reservation, and migration pure contracts.
- Time: 1 day.
- Licence: inspect exact file at clone time.
- Clone depth: shallow.
- Verdict: targeted review and likely test dependency after a focused proof.

### Toxiproxy

- Candidate: [Shopify/toxiproxy](https://github.com/Shopify/toxiproxy)
- Exact question: Can deterministic network faults improve provider, database, and realtime recovery evidence?
- Expected output: fault matrix for timeout, half-open connection, latency, reset, and recovery.
- Time: 1 day.
- Licence: inspect exact file at clone time.
- Clone depth: shallow.
- Verdict: bounded infrastructure-test spike.

### Pandera

- Candidate: [unionai-oss/pandera](https://github.com/unionai-oss/pandera)
- Exact question: Can V2 user-data and external-data admission use a maintained dataframe validator without surrendering canonical authority?
- Expected output: schema, error, performance, migration, pandas and Polars compatibility, dependency weight.
- Time: 1 day.
- Licence: MIT.
- Clone depth: shallow.
- Trigger: v2-external-data-domains.
- Verdict: V2 spike only.

### OpenLineage

- Candidate: [OpenLineage/OpenLineage](https://github.com/OpenLineage/OpenLineage)
- Exact question: Which generic job, run, dataset, and facet names improve interoperability without replacing exact Strategy OS evidence?
- Expected output: mapping and explicit rejection list.
- Time: half day.
- Licence: Apache-2.0.
- Clone depth: shallow or spec-only.
- Verdict: reference, likely no runtime dependency.

### OpenTelemetry Collector

- Candidate: [open-telemetry/opentelemetry-collector](https://github.com/open-telemetry/opentelemetry-collector)
- Exact question: Which production metrics and traces require a collector rather than direct export?
- Expected output: deployment topology, resource cost, security, retention, failure behavior, exit strategy.
- Time: 1 day.
- Licence: Apache-2.0.
- Clone depth: shallow.
- Trigger: v1-observability-and-slo-foundation.
- Verdict: reference until producers and a backend are selected.

## Priority 2

### NATS server

- Candidate: [nats-io/nats-server](https://github.com/nats-io/nats-server)
- Question: Does a second internal market-data consumer require a durable or ephemeral message bus?
- Licence: Apache-2.0.
- Trigger: measured multi-process fan-out need.
- Verdict: defer. Do not add a bus for one process.

### Testcontainers Python

- Candidate: [testcontainers/testcontainers-python](https://github.com/testcontainers/testcontainers-python)
- Question: Does it reduce the current disposable PostgreSQL harness while preserving exact PostgreSQL 16 control?
- Licence: Apache-2.0.
- Trigger: maintenance evidence that the current harness costs more than the dependency.
- Verdict: reference; current harness already works.

### FreqUI

- Candidate: [freqtrade/frequi](https://github.com/freqtrade/frequi)
- Question: Which responsive monitoring and bot-control patterns improve the accepted Strategy OS prototype?
- Expected output: interaction-only review.
- Licence: inspect at clone time.
- Verdict: targeted UI review only after frontend owner gate.

### Hummingbot Dashboard

- Candidate: [hummingbot/dashboard](https://github.com/hummingbot/dashboard)
- Question: How does a companion product group creation, backtest, optimization, deployment, and instance management?
- Licence: Apache-2.0.
- Concern: public documentation shows authentication is optional and documents default sample credentials; security patterns need careful rejection.
- Verdict: interaction and deployment-flow reference only.

## Explicit rejects or deferrals

### TimescaleDB

- Mixed Apache and Timescale licence surfaces.
- No measured current need.
- PostgreSQL tables and object storage remain sufficient.
- Verdict: REJECT now.

### Great Expectations

- Strong data-quality product, Apache-2.0.
- Heavier operating and conceptual surface than current V2 admission needs.
- Verdict: REFERENCE; compare only if Pandera and current validators prove insufficient.

### Kafka and Kubernetes

- No exact repository question can overcome the absence of measured need.
- Verdict: REJECT as speculative infrastructure.

## Newly discovered versus starter list

The concrete additions not already represented by the local library are:

- Angel One SmartAPI Python;
- the official Groww published SDK package and documentation;
- FreqUI;
- Hummingbot Dashboard.

They answer current broker and interaction questions. No other new clone is justified before these and the existing library are exhausted.
