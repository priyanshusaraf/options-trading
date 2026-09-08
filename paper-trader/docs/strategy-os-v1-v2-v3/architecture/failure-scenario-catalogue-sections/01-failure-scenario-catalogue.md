Reference: [section index](../FAILURE-SCENARIO-CATALOGUE.md). Read with its scope; this is not a new assignment.

# Failure scenario catalogue

> Timing amendment: bounded point-in-time reference/events, Dynamic Watchlists and chart semantics are now V1. General Workflows and deeper data domains remain later.

Classification describes the current source-backed position. It does not replace runtime evidence.

| ID | Scenario | Severity | Classification | Current containment | Required permanent proof |
| --- | --- | --- | --- | --- | --- |
| F-001 | Two simultaneous entries spend the same account capital | Critical | LIKELY RISK | one account execution holder and in-process allocator | durable batch, account lock, reservation mutation test |
| F-002 | Stale actor admits after lease takeover | Critical | ALREADY SAFELY HANDLED | fence epoch and lease checks | keep two-session stale-token regression |
| F-003 | Worker dies after reservation before broker send | Critical | HYPOTHESIS REQUIRING TEST | reservation absent | reservation recovery test |
| F-004 | Worker dies after broker send before acknowledgement | Critical | LIKELY RISK | command and order reconciliation | end-to-end ambiguous-command recovery |
| F-005 | Broker accepts duplicate retry | Critical | LIKELY RISK | client intent, broker tag, idempotency seams | duplicate network outcome test per broker |
| F-006 | Partial fill consumes only some capital | Critical | LIKELY RISK | execution events track cumulative fill | reservation partial-consumption test |
| F-007 | Cancel and fill cross | Critical | LIKELY RISK | immutable events and reducer | both event orders and late fill |
| F-008 | Manual broker order changes margin after admission | Critical | LIKELY RISK | live margin read and reserve buffer | refresh, broker reject, new-batch rule |
| F-009 | Atomic basket executes only one leg | Critical | CONFIRMED ABSENCE | no parent group semantics | basket-or-none admission and broker capability test |
| F-010 | Silent resize changes user intent | Critical | ALREADY SAFELY HANDLED in current allocator | no current resizing | mutation that enables resize must fail |
| F-011 | Risk-reducing exit blocked by ARM or reservation | Critical | ALREADY SAFELY HANDLED by policy | ARM gates entries | permanent exit-during-block regression |
| F-012 | Open position loses instrument identity after Universe removal | Critical | PARTIAL | removal refuses current open positions; canonical held identity exists in new authority | exact held contract survives alias and Universe changes |
| F-013 | Dynamic selector rewrites held option | Critical | ALREADY SAFELY HANDLED in authority contract | preserve_held_identity and position facts | provider and runtime integration test |
| F-014 | Strategy signal is treated as execution authority | Critical | ALREADY SAFELY HANDLED | admission and execution binding are distinct | keep authority-withdrawal mutation |
| F-015 | Research approval acts like a renewable lease | Critical | ALREADY SAFELY HANDLED | consumed admission model | exact grant, withdrawal, and regrant tests |
| F-016 | Mutable watchlist changes a running deployment | High | CONFIRMED DEFECT | none for exact member set | immutable static Universe snapshot |
| F-017 | Duplicate Dynamic Universe discovery creates two deployments | High | CONFIRMED ABSENCE | deployment name uniqueness only | candidate identity and idempotent command |
| F-018 | Current instrument list is used as historical Universe | High | LIKELY RISK | no dynamic historical claim exists | point-in-time Universe replay |
| F-019 | Delisted instrument disappears from cross-sectional backtest | High | LIKELY RISK | market truth can represent listing facts | historical population fixture |
| F-020 | Ranking tie resolves by unordered iteration | High | HYPOTHESIS REQUIRING TEST | no ranking product exists | stable tie-break and randomized order mutation |
| F-021 | Threshold churn creates subscription and deployment thrash | High | HYPOTHESIS REQUIRING TEST | no dynamic product exists | enter/leave hysteresis and cooldown tests |
| F-022 | Universe removal stops data needed for an open position | Critical | HYPOTHESIS REQUIRING TEST | current runner keeps enabled positions in current paths | held-position priority subscription test |
| F-023 | Workflow retry writes deployment tables twice | Critical | HYPOTHESIS REQUIRING TEST | no Workflow engine | idempotent deployment command test |
| F-024 | Workflow bypasses preflight or ARM | Critical | HYPOTHESIS REQUIRING TEST | current services enforce admission and ARM separately | direct-table-write prohibition and command integration |
| F-025 | Human approval survives material candidate change | Critical | CONFIRMED ABSENCE | current bounded decisions bind exact evidence in some paths | approval stale-on-change matrix |
| F-026 | Cancellation races Workflow completion | High | HYPOTHESIS REQUIRING TEST | current operations expose cancel request | caller-visible won or too-late outcome |
| F-027 | Research worker resumes under a different build or provider mode | High | ALREADY SAFELY HANDLED | operation stores and checks both | keep takeover regression |
| F-028 | Completed research item runs twice after reclaim | High | ALREADY SAFELY HANDLED | unique item-to-run receipt and claim fence | keep duplicate reclaim mutation |
| F-029 | Trial completion order changes claimed deterministic search | High | LIKELY RISK | seed and trial records exist | parallel-order identity test |
| F-030 | Failed or pruned trials vanish from multiple-testing population | High | LIKELY RISK | OptimizationTrial records exist | population completeness assertion |
| F-031 | OOS is observed before candidate freeze | Critical | LIKELY RISK | research contracts exist | hidden OOS access mutation |
| F-032 | Current pairlist creates look-ahead in backtest | High | CONFIRMED external pattern | no current Dynamic Universe product | V2 current-condition refusal |
| F-033 | Future bar changes an earlier node output | Critical | ALREADY SAFELY HANDLED on accepted causal paths | prefix checks and independent evaluator | every new component causality proof |
| F-034 | Recursive indicator warmup is too short | High | LIKELY RISK for new components | causal recursive state and derived v1 warmup | nested recursive warmup fixtures |
| F-035 | Cache reuses result across different input data | Critical | ALREADY SAFELY HANDLED for backtest result identity; local IR cache scope is per evaluation | full dataset and Phase 4 binding | prohibit cross-frame IR cache without data digest |
| F-036 | Dataset correction leaves prior cache current | Critical | ALREADY SAFELY HANDLED in Phase 4 identity | correction and manifest addresses | end-to-end invalidation |
| F-037 | Current market rule substitutes for historical gap | Critical | ALREADY SAFELY HANDLED in rulebook contract | point-in-time refusal | integration through backtest consumer |
| F-038 | Provider restatement rewrites old fundamental value | High | V1 RISK for bounded reference/events | no current append-only point-in-time fact | V1 publication/revision/knowledge-time test |
| F-039 | Public candle blob is reinterpreted as generic data | High | CONTAINED BY OWNER DECISION | V1 format remains fixed | new versioned V2 schema only |
| F-040 | Provider token reuse maps to wrong instrument | Critical | ALREADY SAFELY HANDLED in new alias contract | effective intervals and overlap refusal | operational adapter integration |
| F-041 | Operational Instrument keeps Kite symbol on another provider | Critical | CONFIRMED DEFECT | resolver seam and Phase 4 canonical authority | two-provider mapping parity |
| F-042 | Provider capability declaration lies | High | PARTIAL | capability and conformance tests | mutation per supported field and order feature |
| F-043 | Upstox data is mistaken for Upstox execution | Critical | ALREADY SAFELY HANDLED | registry refuses missing venue | keep selection refusal |
| F-044 | Dhan protection is silently weakened | Critical | ALREADY SAFELY HANDLED in broker spec and venue | explicit refusal | conformance with options preflight |
| F-045 | Market socket connects but delivers no first event | High | LIKELY RISK | no full subscription state machine | acknowledgement and first-event test |
| F-046 | Browser socket reports connected during stale provider feed | High | CONFIRMED DEFECT | backend health exists separately | client state contract |
| F-047 | Slow browser stalls engine | Critical | ALREADY SAFELY HANDLED | per-client sender, bounded queues, timeout | keep slow-client test |
| F-048 | UI tick queue grows without bound | High | ALREADY SAFELY HANDLED | latest-wins coalescing | load test and dropped count |
| F-049 | Trading-critical order event is coalesced | Critical | ALREADY SAFELY HANDLED by durable domain path | outbox and immutable events | type allowlist regression |
| F-050 | Outbox effect commits before cursor and repeats | High | ALREADY SAFELY HANDLED by idempotency contract | leases and receipts | duplicate delivery test |
| F-051 | Poisoned outbox event is skipped | High | ALREADY SAFELY HANDLED by runbook | cursor does not advance | unsupported-event integration |
| F-052 | Database pool exhaustion delays position protection | Critical | LIKELY RISK | short transactions, pool settings, readiness | production-shaped load and priority isolation |
| F-053 | Research load starves execution | Critical | LIKELY RISK | separate research DB and job controls | CPU, memory, process, and pool capacity test |
| F-054 | Execution and research database copies disagree | Critical | PARTIAL | exact addresses and two-plane verification | process-death integration and drift refusal |
| F-055 | Migration starts from an unsupported historical schema | Critical | CONFIRMED ACTIVE BLOCKER | current foundation gate refuses claim | complete accepted-start matrix |
| F-056 | Partial migration reports current head | Critical | ACTIVE FOUNDATION RISK | migration guards under correction | interruption and restart evidence |
| F-057 | Backup restores rows but not authority or sequence state | Critical | PARTIAL | signed manifest and digest checks in runbook | release-shaped clean restore |
| F-058 | Old primary returns after restore | Critical | PARTIAL | isolation and higher epoch in runbook | production rehearsal |
| F-059 | Credential key rotates without rewrapping rows | Critical | PARTIAL | key ID and decrypt refusal | rotation rehearsal |
| F-060 | Credential appears in logs or backup manifest | Critical | PARTIAL | redaction and secret exclusions | automated secret scan |
| F-061 | Support reads private Strategy content | Critical | LIKELY RISK | no ordinary support graph UI | support policy and negative tests |
| F-062 | Telemetry reconstructs private Strategy logic | High | FUTURE RISK | telemetry scope not complete | consented aggregate event schema |
| F-063 | Uploaded archive escapes target directory | Critical | FUTURE RISK | upload product absent | path traversal and quarantine tests |
| F-064 | Uploaded CSV executes formula on export | High | FUTURE RISK | upload product absent | formula neutralization |
| F-065 | Custom Python reads file, network, or credential | Critical | CONTAINED for generated tier | AST allowlist | future arbitrary-tier sandbox tests |
| F-066 | Dependency update changes semantics under same component version | Critical | LIKELY RISK | implementation closure and build identity | dependency lock and component version gate |
| F-067 | Chart edit mutates a live Strategy | Critical | FUTURE RISK | feature absent | immutable annotation snapshot |
| F-068 | TradingView webhook places order directly | Critical | FUTURE RISK | ingress absent | typed external signal and normal admission |
| F-069 | Replay omits Universe or provider correction event | High | CONFIRMED ABSENCE | candle replay only | versioned general event replay |
| F-070 | Final P&L matches while earlier events diverge | High | LIKELY RISK | prefix evaluator exists for graph | full first-divergence tool |
