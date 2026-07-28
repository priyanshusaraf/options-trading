# Incident — 2026-07-28: the test suite could resolve to live execution

**Severity:** latent, never fired. No orders were placed and no production data was lost.
**Class:** safety-guard placement. The guard existed and was correct; it was one directory
too deep to cover what it was believed to cover.

## What was true

Test-environment safety was set at import time in `backend/tests/conftest.py`. A conftest
applies only to its own directory, so the guard covered `pytest tests` and nothing else.

`backend/research_tests/` has its own conftest, which provides fixtures and sets no env.
A `pytest research_tests` run therefore resolved against the owner's real `backend/.env`:

```
$ .venv/bin/python -m pytest research_tests/probe.py -s -q
PROVIDER='kite' EXECUTION='live' ACK='I_UNDERSTAND_REAL_MONEY'
DB_PATH='paper_trader.db'
LIVE_EXECUTION_ENABLED=True
```

That is: the live Kite data provider, real-money execution enabled at the broker factory,
and the **production ledger** as `PT_DB_PATH`. The shipped `.env` satisfies all three live
gates by design (see CLAUDE.md invariant 3) — the test guard was the only thing standing
between a test run and that configuration.

Two consequences were reachable from ordinary test code:

1. Anything constructing an `EngineRunner` calls `make_broker()`, which under those
   settings builds a real `LiveBroker` wrapping a real `KiteOrderClient`. Order placement
   is still gated by ARM, so this was not a live-order path on its own — but it was one
   guard deep instead of three.
2. `init_db(reset=True)` drops and recreates every table, and is called by many tests in
   `tests/`. Pointed at `paper_trader.db`, that destroys the real trade ledger.

## Why it was invisible

`pytest tests research_tests` — the form `deploy.sh` runs, and the form in CLAUDE.md — was
safe, because collecting `tests/` imported its conftest first and `os.environ` is process
global. Every sanctioned invocation was protected **by collection order**, not by any
guarantee. Nothing would have flagged it until someone ran `pytest research_tests` alone,
added a third test root, or pytest changed its collection order.

## Remediation

Structural, not behavioural — the fix is placement, so no one has to remember it.

1. **`backend/conftest.py`** (rootdir). Forces `PT_PROVIDER=mock`, `PT_EXECUTION=paper`,
   empty `PT_LIVE_ACK`, and a per-run temp `PT_DB_PATH` at module import — which pytest
   performs before any test module, therefore before any `app.*` import. That ordering
   matters: `app.db.session` builds its SQLAlchemy engine from `PT_DB_PATH` at import time,
   so a fixture would be too late to redirect it.
2. **`_forbid_live_execution`**, a session-scoped autouse fixture, re-asserts the env and
   verifies the *resolved* `Settings` — provider, execution, ack, and that `db_path` is
   inside the throwaway dir. A misconfigured run fails at session start instead of running
   and being trusted.
3. **`make_broker()` raises** if it ever resolves a real `LiveBroker` while
   `PYTEST_CURRENT_TEST` is set. The env guards are a soft guarantee — a stray
   `monkeypatch.setenv` or a new test root can undo them. This one fires on the object that
   was actually built and cannot be undone from a test.
4. **`tests/conftest.py` no longer sets env**, and says why. Two writers would resolve by
   import order, which is the bug class that hid this in the first place.

### Two things worth remembering

**`PT_LIVE_ACK` is set empty, not deleted.** "Unset it" is the obvious reading and is wrong:
pydantic-settings falls back to `.env` when an OS var is absent, so deleting it resolves
straight back to the real ack phrase. Verified:

```
after pop()  -> live_ack = 'I_UNDERSTAND_REAL_MONEY'
after ='' -> live_ack = ''
```

Only a present-but-empty OS var shadows `.env`. Empty is also how the app spells "unset" —
`live_execution_enabled()` reads it as falsy.

**The temp DB is now per-run** (`mkdtemp`), not a fixed path in `$TMPDIR`. The old shared
path let two concurrent pytest runs clobber each other's SQLite file, which produced 27
phantom test failures and cost a debugging session chasing a bug that did not exist.

### Fallout in existing tests

Four `tests/test_broker_factory.py` tests broke and were fixed rather than exempted. They
opened the live gate with `monkeypatch.setenv("PT_EXECUTION", "live")`, which worked only
because the old guard set `PT_EXECUTION=""` — falsy, so `live_execution_enabled()` fell
through to its `or os.environ.get(...)` branch. With `"paper"` the Settings value correctly
wins. They now drive `Settings` directly, which is the repo convention and the stronger
test: it exercises the `.env -> Settings` path production actually uses. The env fallback
is still real (a bare `export PT_EXECUTION=live` with no `.env`) and now has its own test.

## Verification

- `pytest research_tests` alone — the previously unprotected run — now resolves
  `PROVIDER='mock' EXECUTION='paper' ACK='' LIVE_EXECUTION_ENABLED=False`, DB under
  `/var/folders/.../paper-trader-pytest-<rand>/paper_trader.db`
- `pytest tests research_tests` → **1132 passed**
- `pytest research_tests` → 167 passed; `pytest tests` → 965 passed
- `scripts/dryrun.py 700` → `LEDGER OK ✓`, reconcile diff `+0.0000`
- Three consecutive interpreter starts produce three distinct temp DB dirs

## Coverage on both roots

The invariant is asserted from **both** suite roots, deliberately:
`tests/test_no_live_under_pytest.py` and `research_tests/test_env_is_never_live.py`.

A check that lives only under `tests/` proves the guard holds when `tests/` is collected —
which was already true before the fix, and is precisely the collection-order accident that
hid the hole. Only an assertion inside `research_tests/` can fail in a `research_tests`-only
invocation. If a future change moves the env forcing back down a directory, that file goes
red immediately instead of in six months.
