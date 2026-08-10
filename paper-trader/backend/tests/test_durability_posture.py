"""The durability posture, pinned — so a document and the pragmas cannot drift apart again.

**Why this file exists.** ADR 0015 §3 was accepted on 2026-08-10 asserting, under *Enforced
now*, that "the money plane commits with `synchronous=FULL`". It did not, and never had:
`session.py` sets `NORMAL`. The claim survived review, a full test suite and a mutation sweep,
because nothing anywhere connected the sentence to the pragma. It was caught by the owner asking
whether we were actually complying — which is not a control.

That is this codebase's defining defect arriving in a new place: a document claiming wiring that
does not exist. The guards built for it look at code (`test_no_unconsumed_mechanisms`) and at
tests (the mutation sweeps). Neither can see a *durability posture* stated in prose, because
there is no callable to have no callers.

So these tests are the connection. They do **not** assert that the current posture is correct —
it is not; F-2 is open and a committed money transaction can still be lost to a host failure.
They assert that the posture is **what the ADR currently says it is**, in both directions. If
someone raises `synchronous`, this fails and sends them to update the ADR. If someone edits the
ADR to claim a posture the code does not have, the docstring here is what they have to argue
with.
"""
from __future__ import annotations

import pathlib

import pytest

from app.db.session import engine

ADR = (pathlib.Path(__file__).resolve().parents[2]
       / "docs/engineering/decisions/0015-three-planes-and-the-home-of-a-credential.md")


def _pragma(name: str):
    with engine.connect() as conn:
        return conn.exec_driver_sql(f"PRAGMA {name}").scalar()


# ── the posture as it actually is ─────────────────────────────────────────

def test_the_write_durability_is_normal_and_that_is_a_known_open_risk():
    """`synchronous=NORMAL` under WAL survives a PROCESS crash and not a HOST failure. That is
    F-2 in `reference/2026-08-10-multi-user-failure-modes.md`, and it is open.

    Raising this to `FULL` is not a free win and must not be done as a drive-by: all three
    planes share one file and one engine, so `FULL` would put an fsync on every bulk backtest
    write too — the exact coupling the plane split exists to remove. It is fixed by the physical
    split, or by a deliberate global change WITH the write benchmark re-taken.
    """
    assert _pragma("synchronous") == 1, (          # 0=OFF 1=NORMAL 2=FULL 3=EXTRA
        "synchronous changed. If this was deliberate, update ADR 0015 §3 in the same commit — "
        "the whole reason this test exists is that the ADR once claimed FULL while the code "
        "said NORMAL, and nothing noticed.")


def test_wal_is_on_because_the_risk_loop_must_never_block_on_a_reader():
    """Hard invariant 2: nothing may block an exit. WAL is what keeps a dashboard read from
    blocking the engine's write."""
    assert str(_pragma("journal_mode")).lower() == "wal"


def test_foreign_keys_are_enforced():
    """SQLite defaults them OFF. The plane ratchet counts foreign keys as a real constraint; if
    they are not enforced at runtime, that count is bookkeeping."""
    assert _pragma("foreign_keys") == 1


def test_a_contended_write_waits_rather_than_failing():
    """`database is locked` in the risk loop is an exit that did not happen."""
    assert int(_pragma("busy_timeout")) >= 10_000


# ── the document must not claim more than the code does ───────────────────

def test_the_adr_does_not_claim_a_durability_it_has_not_got():
    """The specific false claim, pinned by its own words.

    Narrow on purpose: this cannot verify prose in general, and pretending otherwise would be a
    second false guarantee. It verifies the one sentence that was actually wrong, so that
    re-introducing it requires deleting a test that explains why.
    """
    text = ADR.read_text()
    enforced, _, deferred = text.partition("Deliberately NOT done now:")
    assert deferred, "ADR 0015 lost its 'Deliberately NOT done now' section"
    assert "synchronous=FULL" not in enforced, (
        "ADR 0015 claims `synchronous=FULL` under 'Enforced now'. The code sets NORMAL "
        "(session.py). Either implement it — global, benchmarked, and read the test above "
        "first — or keep the claim in the deferred section.")
    assert "synchronous=FULL" in deferred, (
        "the deferred section no longer records that FULL is outstanding; F-2 would become "
        "invisible rather than fixed")


@pytest.mark.parametrize("claim", [
    "Every table is assigned to exactly one plane",
    "No *new* foreign key crosses a plane boundary",
])
def test_the_adrs_enforced_claims_are_the_ones_with_tests_behind_them(claim):
    """The two rules ADR 0015 lists as enforced are exactly the two `test_db_planes.py` checks.
    A third claim appearing in that section without a test is how the last one got in."""
    enforced = ADR.read_text().partition("Deliberately NOT done now:")[0]
    assert claim in enforced, f"ADR 0015 no longer states {claim!r} as enforced"
