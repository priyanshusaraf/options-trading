"""
Generation 2's search loop, scored through Generation 1's gates.

The point of these tests is that there is exactly ONE gate pipeline. A graph is
presented as a `Strategy` and handed to `run_experiment`; if a second scoring
path ever appears, the `candles.py` defect (two hand-written implementations of
one idea) has been repeated in the plane whose whole job is honest numbers.

So they assert the adapter's contract precisely — four canonical columns, an
absent signal all-False rather than NaN or True, warmup never firing — and then
that the loop deflates by the lineage it searched, keeps every report bound to
the `ExperimentRecord` that produced it (F14), and still fails PBO closed.
"""
from __future__ import annotations

import pathlib

import pytest

from app.ir.authoring import library
from app.ir.experiment import validate_experiment
from app.market_data.candles import candles_to_df
from app.strategy.registry.base import CANONICAL_COLUMNS
from research.data.store import StaticDataSource, materialize
from research.domain.models import BlockEdge
from research.strategy.builder.blocks import BLOCKS
from research.strategy.builder.ir_components import BAR_INPUTS, derive_all, groups
from research.strategy.builder.ir_evaluate import (
    Scored,
    UnboundResult,
    block_refs,
    knowledge_payload,
    score_exploration,
)
from research.strategy.builder.ir_search import Explored, Exploration, explore
from research.strategy.builder.ir_strategy import (
    IRGraphStrategy,
    UnmappableGraph,
    column_mapping,
)
from research.strategy.builder.propose import Vocabulary
from research_tests.test_ir_propose import BAR, logic_and, seed_graph


@pytest.fixture(scope="module")
def lib():
    return library([*derive_all(**BAR).values(), logic_and])


@pytest.fixture(scope="module")
def vocabulary():
    return Vocabulary(
        blocks=tuple(sorted(BLOCKS)),
        bar_inputs=BAR_INPUTS,
        block_inputs={name: tuple(spec.inputs) for name, spec in BLOCKS.items()},
        defaults={name: dict(zip([p for p, _ in spec.params], spec.sample_args))
                  for name, spec in BLOCKS.items()},
        families=groups(),
    )


@pytest.fixture(scope="module")
def frame_inputs():
    """The bars as the IR wants them, taken from THE candle converter."""
    from research_tests.conftest import make_uptrend

    df = candles_to_df(make_uptrend(400))
    return {field: df[field].astype(float) for field in BAR_INPUTS}, df


@pytest.fixture(scope="module")
def frame(frame_inputs):
    return frame_inputs[1]


def _walk(vocabulary, lib, frame_inputs, *, seed=5, steps=2):
    return explore(seed_graph(), vocabulary, lib, frame_inputs[0], seed=seed, steps=steps)


def _datasets(inst_factory, candles, keys=("AAA",)):
    source = StaticDataSource({(k, "day"): candles for k in keys})
    return [(inst_factory(k), materialize(source, inst_factory(k), "day")) for k in keys]


# ── the adapter's contract ────────────────────────────────────────────────

def test_the_adapter_emits_the_four_canonical_columns_as_bool(lib, frame):
    strategy = IRGraphStrategy(seed_graph(), lib)
    out = strategy.signals(frame)

    for column in CANONICAL_COLUMNS:
        assert column in out.columns, column
        assert out[column].dtype == bool, column
        assert out[column].isna().sum() == 0, column
    assert len(out) == len(frame)


def test_an_unbound_signal_is_all_false_and_the_bound_one_is_not(lib, frame):
    """An absent signal must be all-False, never NaN and never True — and the
    guard is only worth anything if the BOUND column actually fires, or this
    passes on an adapter that returns four dead columns."""
    out = IRGraphStrategy(seed_graph(), lib).signals(frame)

    assert out["longEntry"].any(), "the bound column never fired; the test is vacuous"
    for column in ("shortEntry", "longExit", "shortExit"):
        assert not out[column].any(), column


def test_warmup_bars_never_fire(lib, frame):
    """C10 — an unsettled bar is not a signal. Firing inside warmup would enter
    on an indicator that has not yet seen enough bars to mean anything."""
    strategy = IRGraphStrategy(seed_graph(), lib)
    warmup = strategy.resolved.warmup
    assert warmup > 0

    out = strategy.signals(frame)
    assert not out[list(CANONICAL_COLUMNS)].iloc[:warmup].to_numpy().any()


def test_the_column_mapping_is_explicit_and_refuses_to_guess():
    assert column_mapping(("out",)) == {"longEntry": "out"}
    assert column_mapping(("longEntry", "shortExit")) == {
        "longEntry": "longEntry", "shortExit": "shortExit"}

    with pytest.raises(UnmappableGraph):
        column_mapping(("longEntry", "out"))
    with pytest.raises(UnmappableGraph):
        column_mapping(("out", "other"))
    with pytest.raises(UnmappableGraph):
        column_mapping(())


def test_the_adapter_refuses_parameters_after_resolution(lib, frame):
    """A graph resolved with one set of values and run with another would make
    every binding recorded against it describe a different run (F14)."""
    strategy = IRGraphStrategy(seed_graph(), lib)
    with pytest.raises(ValueError):
        strategy.signals(frame, length=10)


def test_the_adapter_is_pure(lib, frame):
    strategy = IRGraphStrategy(seed_graph(), lib)
    first = strategy.signals(frame)
    second = IRGraphStrategy(seed_graph(), lib).signals(frame)
    for column in CANONICAL_COLUMNS:
        assert first[column].equals(second[column]), column
    assert strategy.key == IRGraphStrategy(seed_graph(), lib).key


def test_an_empty_frame_still_carries_the_four_columns(lib):
    import pandas as pd

    empty = pd.DataFrame(columns=["date", *BAR_INPUTS])
    out = IRGraphStrategy(seed_graph(), lib).signals(empty)
    assert list(CANONICAL_COLUMNS) == [c for c in CANONICAL_COLUMNS if c in out.columns]
    assert len(out) == 0


# ── the loop scores through the ONE pipeline ──────────────────────────────

def test_every_scored_candidate_carries_a_binding_that_validates(
        research_session, inst_factory, uptrend_factory, vocabulary, lib, frame_inputs):
    walk = _walk(vocabulary, lib, frame_inputs, steps=2)
    scored = score_exploration(
        research_session, walk, lib, _datasets(inst_factory, uptrend_factory(400)),
        min_trades=1, n_folds=3, min_positive_fold_frac=0.0)

    assert len(scored) == len(walk.steps) >= 3
    for item in scored:
        assert isinstance(item, Scored)
        strategy = IRGraphStrategy(item.explored.graph, lib)
        assert validate_experiment(item.record, strategy.resolved) == []
        assert item.report["binding"] == item.record.binding
        assert item.report["experiment_id"] == item.record.experiment_id
        assert item.report["strategy_key"] == strategy.key
        assert item.report["run_id"]


def test_a_record_bound_to_another_graph_is_refused_not_scored(
        research_session, inst_factory, uptrend_factory, vocabulary, lib, frame_inputs):
    """F14 fails stale, not missing: every field is populated and names the wrong
    run. Scoring that produces a report nobody can attribute."""
    walk = _walk(vocabulary, lib, frame_inputs, steps=2)
    first, second = walk.steps[0], walk.steps[-1]
    swapped = Exploration(seed=walk.seed, steps=(
        Explored(proposal=first.proposal, graph=first.graph,
                 resolved=first.resolved, record=second.record),))

    with pytest.raises(UnboundResult):
        score_exploration(research_session, swapped, lib,
                          _datasets(inst_factory, uptrend_factory(400)),
                          min_trades=1, n_folds=3, min_positive_fold_frac=0.0)


def test_sibling_trials_is_the_size_of_the_lineage(
        research_session, inst_factory, uptrend_factory, vocabulary, lib, frame_inputs):
    """Every candidate in a lineage is a trial for every other one — the same
    argument `run_generated` makes with `len(compositions)`. Scoring a step as
    though it were the only graph tried understates the search."""
    datasets = _datasets(inst_factory, uptrend_factory(400))
    short = _walk(vocabulary, lib, frame_inputs, seed=5, steps=1)
    long = _walk(vocabulary, lib, frame_inputs, seed=5, steps=3)

    a = score_exploration(research_session, short, lib, datasets, min_trades=1,
                          n_folds=3, min_positive_fold_frac=0.0)
    b = score_exploration(research_session, long, lib, datasets, min_trades=1,
                          n_folds=3, min_positive_fold_frac=0.0)

    assert {r.report["sibling_trials"] for r in a} == {len(short.steps)}
    assert {r.report["sibling_trials"] for r in b} == {len(long.steps)}
    assert len(long.steps) > len(short.steps)


def test_the_same_graph_scores_identically_across_runs(
        tmp_path, inst_factory, uptrend_factory, vocabulary, lib, frame_inputs):
    """A binding to an unreplayable run is a fiction."""
    from research.domain.base import init_research_db, make_engine, make_sessionmaker

    datasets = _datasets(inst_factory, uptrend_factory(400))
    walk = _walk(vocabulary, lib, frame_inputs, seed=7, steps=2)

    def once(name):
        engine = make_engine(str(tmp_path / name))
        init_research_db(engine)
        with make_sessionmaker(engine)() as session:
            return [_comparable(r.report) for r in score_exploration(
                session, walk, lib, datasets, min_trades=1, n_folds=3,
                min_positive_fold_frac=0.0)]

    assert once("a.db") == once("b.db")


def _comparable(report):
    return {k: report[k] for k in ("spec_id", "qualified", "rejected", "validated",
                                   "promotion", "decision", "total_bars", "binding",
                                   "strategy_key", "sibling_trials")}


def test_pbo_still_fails_closed(
        research_session, inst_factory, uptrend_factory, vocabulary, lib, frame_inputs):
    """The gate battery is Generation 1's, PBO included. A matrix that cannot be
    evaluated — one candidate, nothing to select between — does not pass."""
    walk = _walk(vocabulary, lib, frame_inputs, seed=5, steps=1)
    scored = score_exploration(
        research_session, walk, lib, _datasets(inst_factory, uptrend_factory(400)),
        min_trades=1, n_folds=3, min_positive_fold_frac=0.0, optimize_search=True)

    reasons = [r["reason"] for item in scored for r in item.report["rejected"]]
    assert any("pbo" in reason for reason in reasons), reasons
    assert all(not v["gates"]["pbo"]["passed"]
               for item in scored for v in item.report["validated"])


def test_the_loop_feeds_what_it_learned_back_through_knowledge(
        research_session, inst_factory, uptrend_factory, vocabulary, lib, frame_inputs):
    walk = _walk(vocabulary, lib, frame_inputs, seed=5, steps=1)
    score_exploration(research_session, walk, lib,
                      _datasets(inst_factory, uptrend_factory(400)),
                      min_trades=1, n_folds=3, min_positive_fold_frac=0.0)

    rows = research_session.query(BlockEdge).all()
    assert rows, "nothing was fed back; the Findings corpus stays write-only"
    assert {r.instrument_key for r in rows} == {"AAA"}
    assert {"price_above_ema", "zscore_gt"} <= {r.block_name for r in rows}
    assert all((r.positive or 0) + (r.negative or 0) >= 1 for r in rows)


def test_the_knowledge_payload_names_the_columns_the_graph_drives():
    payload = knowledge_payload(seed_graph(), {"longEntry": "out"})
    assert list(payload) == ["longEntry"]
    assert payload["longEntry"]["all"] == block_refs(seed_graph())
    assert payload["longEntry"]["all"] == ["price_above_ema(50)", "zscore_gt(50, 0.0)"]


# ── C14: what may not score ───────────────────────────────────────────────

@pytest.mark.parametrize("module", ["propose.py", "ir_strategy.py", "ir_search.py"])
def test_the_modules_that_must_not_score_still_do_not(module):
    """The proposer proposes and the adapter adapts. An objective in either turns
    "propose and present" into "sweep and keep the best", which is Generation 1
    with extra steps — and the gate pipeline stops being the only judge."""
    source = _source(module).lower()
    for scoring in ("sharpe", "fitness", "objective", "rank", "pnl", "dsr", "promot"):
        assert scoring not in source, f"{module}: {scoring}"


@pytest.mark.parametrize("module", ["ir_strategy.py", "ir_evaluate.py"])
def test_the_new_modules_are_deterministic(module):
    import re

    source = _source(module)
    assert re.search(r"random\.Random\(\s*\)", source) is None
    for nondeterminism in ("import random", "import time", "from time",
                           "import datetime", "from datetime", "uuid"):
        assert nondeterminism not in source, f"{module}: {nondeterminism}"


def test_the_loop_imports_the_one_pipeline_rather_than_reimplementing_it():
    source = _source("ir_evaluate.py")
    assert "from research.orchestrator.run import run_experiment" in source
    assert "run_experiment(" in source
    for reimplemented in ("def qualify", "def validate", "def pbo", "deflated_sharpe"):
        assert reimplemented not in source, reimplemented


def _source(module: str) -> str:
    return (pathlib.Path(__file__).resolve().parents[1]
            / "research/strategy/builder" / module).read_text()
