Reference: [section index](../codex-supervisor-review-2026-08-09.md). Read with its scope; this is not a new assignment.

## 13. Verification gates for the next milestones

### Provider and connection gate

- One conformance suite passes every adapter and fails a dishonest adapter.
- Concrete adapter auth failures drive runtime health correctly.
- Upstox-like data plus Kite-like execution is selected in one test without provider-name branches.
- Provider mapping provenance reaches decisions, orders, fills, and reconciliation.
- Missing required capability refuses deployment activation.

### Execution gate

- Journal/intent database failure prevents entry submit.
- Ambiguous submit never causes a second order.
- Duplicate and out-of-order fill events book once.
- Partial fills across several events reconcile quantity, average, charges, and position lots.
- Restart recovery is scoped to the exact tenant/account/connection/deployment.
- `dryrun.py 700` reports `LEDGER OK` and mutation tests prove each new guard can fail.
- Live behaviour remains owner-gated.

### Tenancy gate

- Two tenants can create the same display names without global collisions.
- Tenant A cannot read, edit, deploy, backtest, connect, or reconcile Tenant B’s objects by guessed ID.
- Every cache-key audit includes tenant and connection where the answer changes.
- Broker credentials never enter logs, API payloads, research receipts, or database plaintext.

### Research gate

- Every cached result names the full dataset address, executable address, cost model, and trial family.
- The promoted candidate is selected using the correction persisted for human review.
- A statistical test fixture reproduces a known DSR calculation from the source paper.
- Search breadth increases the rejection threshold under a controlled independent-trial fixture.
- Correlated/repeated folds are not labelled independent without a documented effective-trial model.

## 14. Exact next prompt for Claude

```text
You are continuing Strategy OS in /Users/priyanshusaraf/dev/options-trading on branch
feat/exec-completeness. Read these first:

1. paper-trader/CLAUDE.md
2. .claude/rules/providers-brokers.md
3. .claude/rules/execution-safety.md
4. .claude/skills/provider-adapter/SKILL.md
5. .claude/skills/execution-safety-review/SKILL.md
6. paper-trader/docs/engineering/reference/codex-supervisor-review-2026-08-09.md
7. paper-trader/docs/engineering/reference/upstox-data-adapter-design.md

Implement one bounded slice: provider health closure plus explicit runtime connection-role
composition. Do not implement the Upstox adapter yet. Do not change graph, research, trading
logic, sizing, exits, or deployment authority.

First reject or confirm each premise from code:

- get_provider() is process-global and make_broker(provider) currently infers execution from the
  market-data provider;
- KiteProvider.get_ltp() swallows auth errors into None while EngineRunner clears the bad-token
  latch after any non-throwing probe;
- scan_signals advances last_scan_ok before proving the candle frame is usable;
- today’s one-Kite setup must behave exactly as before.

Required work:

1. Add regression tests through concrete KiteProvider semantics showing that an expired-token
   LTP probe returning None does not clear the token latch. Fix the runtime so only a positive
   health result clears it.
2. Split candle transport success from usable-frame freshness. Empty and too-short successful
   reads must not advance last_scan_ok; valid completed frames must. Preserve ProviderReadError
   handling and the auth latch.
3. Introduce one small runtime composition object that explicitly binds these roles:
   market_data, execution, account/portfolio, and instrument resolver. A connection may serve
   several roles, but role selection must remain distinct.
4. Refactor factory/broker construction to consume the explicit execution binding instead of
   deriving execution credentials, access token, and tick source from the market-data provider.
   Preserve mock/replay paper behaviour and the existing Kite live safety gates.
5. Add a proof with two distinct test connections: an Upstox-like data-only provider supplies
   candles/quotes and a Kite-like execution connection supplies the live order client. The test
   must prove the broker can be selected without granting execution capability to the data
   provider. No real credentials and no real SDK order object may be used.
6. Keep capabilities explicit and fail closed when a required role or capability is absent.
   Do not branch on provider names in shared engine code.
7. Update CONTINUE.md and the relevant architecture reference to state what is now actually
   expressible. Do not claim live Upstox verification.

Constraints:

- Use the existing MarketDataProvider, Broker/ExecutionVenue, Account/Portfolio, and
  InstrumentResolver seams. Do not create one giant Connection protocol.
- No product feature, no schema migration unless exact durable connection identity proves
  unavoidable, no multi-user implementation, no queue, no microservice, no Rust rewrite.
- SafePaperKite remains the only SDK object held by the normal Kite data provider.
- Live execution remains gated by PT_EXECUTION=live, the exact live acknowledgement, pytest
  refusal, ARM, and owner acknowledgement before deployment.
- Do not touch the live database or deploy.

Evidence before closure:

- Show each new regression test failing for the intended reason before the fix, then passing.
- Run provider conformance, token-storm, provider-read-failure, broker-factory, no-live-under-
  pytest, SafePaperKite safety, and affected full backend tests.
- Run dryrun.py 700 and backtest_smoke.py if the broker construction path changed.
- Run the full backend suite if shared factory or protocol signatures changed.
- Dispatch execution-safety-reviewer and architecture-critic on the final diff.
- Record exact commands, counts, skips, failures, branch, commit, and migration head.
- Stop for owner acknowledgement before any deployment or live-behaviour change.

Deliver a small, reviewable diff. If role composition cannot be separated without introducing a
durable Connection/Account schema, stop after the health fixes and write the minimal schema plan
with migration/backfill and compatibility details. Do not improvise a second provider singleton.
```
