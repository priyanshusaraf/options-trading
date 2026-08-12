# Task 6 report — tenant channels and answer-changing cache isolation

## Delivered scope

- Private WebSocket channels now use the server-derived `(organization_id, broker_account_id)` key. `MARKET_PUBLIC` remains explicit, so private subscribers do not receive public frames by implication.
- Both WebSocket routes authenticate, require `read:execution`, and resolve the owned local execution cell before manager registration, state priming, positions, or prices. Rejections close with code `1008`.
- Durable user sockets receive no `LogBus` history or live global process logs.
- Public catalog and option snapshot throttle caches include provider/source identity.
- `UniverseInstrument` remains canonical market data. `UniversePreference` stores `active`, `on_home`, and source by owner/instrument key. API and runner portfolio reads use the owner-composed view.
- Migration `0031` preserves the legacy owner view, initializes idempotently, and refuses a downgrade that would discard a foreign or changed preference.

## Regression proof

- Behavioral RED: the original global manager sent an A/account-1 state marker to A/account-2. The focused regression failed at that exact assertion before the channel implementation.
- Focused tests cover exact two-dimension private delivery, explicit public delivery, 250 clients per tenant with one serialization and zero B pending frames, missing execution scope before local-cell/provider work, provider-separated cache keys, owner A/B preference composition, and unsafe migration downgrade refusal.
- Existing scoped backtest export and ledger artifact coverage remains in `tests/test_backtest_tenant_isolation.py` and `tests/ledger/test_tenant_scope.py`.

## Guardrails respected

- No frontend changes.
- No changes to protected broker/provider files: `app/engine/kite_venue.py`, `app/engine/venue.py`, `app/providers/brokers.py`, or `tests/test_broker_registry.py`.
