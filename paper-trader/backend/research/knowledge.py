"""The reinforcement loop — what makes the nightly LEARN rather than re-roll.

Before this, every night sampled from the same distribution regardless of what
the previous nights found. Findings are free text, so nothing could ask "which
block keeps dying on bullion?" — the knowledge existed as prose and was unusable
as an input. `research_block_edge` is that knowledge in structured form, and this
module is how generation reads it.

Three ideas, in order of how much they matter:

**Count blocks, not compositions.** A composition is a one-off; a block is a
reusable family, and the family is the level at which a lesson generalises to
tomorrow's draw. `rsi_gt(14, ...)` and `rsi_gt(21, ...)` are the same idea at
different settings.

**Suppression needs a power floor.** Suppressing on one bad night would let a
single noisy evaluation permanently delete an idea from the search space. It
takes a well-powered negative record, and it is always escapable by later
evidence — the same "never permanently banned" principle that makes
`retest_priority` decay upward.

**Suppression is per instrument.** The whole claim is "which idea works WHERE".
A family that dies on gold stays available on crude; otherwise this is a global
blocklist wearing a map's clothes.
"""
from __future__ import annotations

import datetime as dt
import random
import re

from research.domain.models import BlockEdge

# A family must have been tried this many times on an instrument before its
# record counts as evidence. Below it, silence.
MIN_TRIALS_TO_SUPPRESS = 8
# ...and must have failed at least this fraction of those tries.
SUPPRESS_LOSS_RATE = 0.85
# ...and no matter how bad the record, never suppress more than this fraction of
# the families that have evidence. THIS IS AN EXPLORATION FLOOR, and it exists
# because the obvious implementation destroys the search: on a universe where
# nothing works yet, every family accumulates a losing record, all of them get
# suppressed, and the nightly quietly stops exploring. Observed for real —
# suppression took all four trend families at once, and since every composition
# structurally requires a trend block, the sampler could draw NOTHING.
MAX_SUPPRESSED_FRACTION = 0.4

_CALL = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(")

_CLAUSE_KEYS = ("longEntry", "shortEntry", "longExit", "shortExit")


def blocks_in(composition: dict) -> set:
    """Every block FAMILY referenced by a composition, parameters discarded."""
    out = set()
    for key in _CLAUSE_KEYS:
        clause = (composition or {}).get(key)
        if not isinstance(clause, dict):
            continue
        for refs in clause.values():
            for ref in refs or []:
                m = _CALL.match(str(ref))
                if m:
                    out.add(m.group(1))
    return out


def record_outcome(session, composition: dict, instrument_key: str, *,
                   validated: bool, run_id: int | None = None) -> None:
    """Credit or debit every block family in `composition` on this instrument.

    Two evaluations are two data points — this accumulates rather than collapsing,
    because the power floor above is meaningless without a real count.
    """
    now = dt.datetime.now()
    for name in blocks_in(composition):
        row = session.get(BlockEdge, (name, instrument_key))
        if row is None:
            row = BlockEdge(block_name=name, instrument_key=instrument_key,
                            positive=0, negative=0)
            session.add(row)
        if validated:
            row.positive = (row.positive or 0) + 1
        else:
            row.negative = (row.negative or 0) + 1
        row.last_run_id = run_id
        row.updated_at = now
    session.flush()


def suppressed_blocks(session, instrument_key: str) -> set:
    """Families with a well-powered negative record on this instrument.

    Returns a set the sampler should avoid — not a ban. A family that later
    validates climbs back out on its own, because the ratio is recomputed from
    the full record every time rather than latched.
    """
    rows = (session.query(BlockEdge)
            .filter(BlockEdge.instrument_key == instrument_key).all())
    scored = []
    for r in rows:
        pos, neg = int(r.positive or 0), int(r.negative or 0)
        n = pos + neg
        if n >= MIN_TRIALS_TO_SUPPRESS and (neg / n) >= SUPPRESS_LOSS_RATE:
            scored.append((neg / n, n, r.block_name))
    if not scored:
        return set()
    # Worst first, then capped. Ranking matters: when the cap bites we keep the
    # families with the strongest negative record and let the marginal ones back
    # into the draw, rather than suppressing an arbitrary subset.
    scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
    cap = max(1, int(len(rows) * MAX_SUPPRESSED_FRACTION))
    return {name for _, _, name in scored[:cap]}


def _nudge(ref: str, rng: random.Random) -> str:
    """Perturb one numeric argument of a block reference, keeping it lawful.

    Integers stay integers and floats stay floats: the grammar type-checks
    `length` as `int` specifically, so turning 14 into 14.7 would be rejected at
    composition time rather than producing an interesting variant.
    """
    m = _CALL.match(ref)
    if not m:
        return ref
    name = m.group(1)
    inner = ref[ref.index("(") + 1:ref.rindex(")")]
    parts = [p.strip() for p in inner.split(",")] if inner.strip() else []
    if not parts:
        return ref
    i = rng.randrange(len(parts))
    try:
        if "." in parts[i]:
            val = float(parts[i]) * rng.choice((0.8, 0.9, 1.1, 1.25))
            parts[i] = f"{round(val, 3)}"
        else:
            val = int(parts[i])
            step = max(1, abs(val) // 4)
            parts[i] = str(max(1, val + rng.choice((-step, step))))
    except ValueError:
        return ref
    return f"{name}({', '.join(parts)})"


def mutate(composition: dict, *, seed: int = 0) -> dict:
    """A nudged variant of a composition that survived.

    Deliberately SMALL: a mutation that rewrites everything is just a fresh
    random draw, and the whole point is to exploit what the survivor knew. One
    clause, one reference, one parameter.
    """
    rng = random.Random(seed)
    out = {k: v for k, v in (composition or {}).items()}
    clauses = [k for k in _CLAUSE_KEYS if isinstance(out.get(k), dict)]
    if not clauses:
        return out
    ck = rng.choice(clauses)
    clause = {k: list(v) for k, v in out[ck].items()}
    op = next(iter(clause))
    refs = clause[op]
    if refs:
        i = rng.randrange(len(refs))
        refs[i] = _nudge(refs[i], rng)
    clause[op] = refs
    out[ck] = clause
    out["key"] = f"{composition.get('key', 'gen')}_m{seed}"
    return out


def edge_weights(session, instrument_key: str) -> dict:
    """Per-family sampling weight on this instrument: >1 favoured, <1 disfavoured.

    Used to bias the draw toward what has worked here. Bounded on both sides so
    knowledge tilts the search without collapsing it onto one idea — an
    exploration floor that stops the loop from converging on its first success.
    """
    rows = (session.query(BlockEdge)
            .filter(BlockEdge.instrument_key == instrument_key).all())
    out = {}
    for r in rows:
        pos, neg = int(r.positive or 0), int(r.negative or 0)
        n = pos + neg
        if n == 0:
            continue
        # Laplace-smoothed win rate, mapped to [0.25, 2.0].
        rate = (pos + 1) / (n + 2)
        out[r.block_name] = round(max(0.25, min(2.0, rate * 2.0)), 3)
    return out


def edge_report(session) -> str:
    """"Which idea works where", rendered for the research report. Empty when
    nothing is known yet — so a caller can use it directly as "is there anything
    to say?"."""
    rows = session.query(BlockEdge).all()
    if not rows:
        return ""
    by_block: dict = {}
    for r in rows:
        by_block.setdefault(r.block_name, []).append(r)
    lines = ["| block | instrument | validated | rejected |", "|---|---|---|---|"]
    for name in sorted(by_block):
        for r in sorted(by_block[name], key=lambda x: x.instrument_key):
            lines.append(f"| {name} | {r.instrument_key} | {r.positive} | {r.negative} |")
    return "\n".join(lines)
