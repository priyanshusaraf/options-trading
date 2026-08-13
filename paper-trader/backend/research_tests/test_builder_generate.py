"""The generate-and-evaluate orchestrator: the bot enumerates its own compositions,
persists each (so a candidate can carry its exact composition to the human), and runs
each through the identical research gauntlet. This is 'the bot generates its own
strategies and they actually run' end to end."""
import datetime as dt
import json
import math

import pytest

from research.data.store import StaticDataSource, materialize
from research.domain.models import (
    ExperimentRun,
    ExperimentSpec,
    GeneratedStrategyRecord,
    PromotionCandidate,
)
from research.orchestrator.generate import run_generated

OWNER_ID = "test-owner"
from research.strategy.builder.grammar import Composition


def _osc_candles(Candle, n=700):
    base = dt.datetime(2024, 1, 1, 9, 15)
    return [Candle(base + dt.timedelta(minutes=15 * i),
                   (100 + 0.15 * i + 6 * math.sin(i / 9.0)) - 0.4,
                   (100 + 0.15 * i + 6 * math.sin(i / 9.0)) + 0.9,
                   (100 + 0.15 * i + 6 * math.sin(i / 9.0)) - 0.9,
                   (100 + 0.15 * i + 6 * math.sin(i / 9.0))) for i in range(n)]


def test_run_generated_evaluates_and_persists_compositions(
        research_session, inst_factory, candles_factory):
    Candle = type(candles_factory(1)[0])
    keys = ["GOLDM", "SILVERM"]                       # the always-allowed research sandbox
    src = StaticDataSource({(k, "day"): _osc_candles(Candle) for k in keys})
    instruments = [inst_factory(k) for k in keys]

    reports = run_generated(research_session, src, instruments, "day", owner_id=OWNER_ID, limit=4,
                            git_commit="gen", min_trades=1, n_folds=3,
                            min_positive_fold_frac=0.0)

    assert len(reports) == 4
    # every evaluated strategy is a generated one and was run to completion
    assert all(r["explanation"]["strategy_key"].startswith("gen_") for r in reports)
    assert research_session.query(ExperimentRun).count() == 4
    recipes = [json.loads(row.recipe_json) for row in research_session.query(ExperimentSpec).all()]
    assert all(recipe["graph_provenance"]["graph"]["content_address"].startswith("sha256:")
               for recipe in recipes)
    assert all(recipe["graph_provenance"]["admission_address"].startswith("sha256:")
               for recipe in recipes)

    # each generated strategy's composition is persisted and round-trips to a Composition
    recs = research_session.query(GeneratedStrategyRecord).all()
    assert len(recs) == 4
    for rec in recs:
        comp = Composition.from_dict(json.loads(rec.composition_json))
        assert comp.key == rec.key
        assert "def compute(df" in rec.source          # the emitted source is stored too

    # any candidate that cleared validation is human-gated, never auto-deployed
    for cand in research_session.query(PromotionCandidate).all():
        # Phase 4 (2026-08-01): candidates are born SHADOW, not "pending". These
        # tests' stated intent — never auto-deployed, always human-gated — is
        # strengthened by that, not weakened: a shadow candidate is not even in
        # the approval queue yet, and cannot enter it without surviving sessions
        # it has never seen. Asserting the intent rather than the old literal.
        from research.shadow import STATUS_SHADOW, approval_queue
        assert cand.status == STATUS_SHADOW
        assert cand.approved_git_sha is None
        assert cand.id not in [c.id for c in approval_queue(research_session)]


def test_run_generated_respects_the_limit(research_session, inst_factory, candles_factory):
    Candle = type(candles_factory(1)[0])
    src = StaticDataSource({("GOLDM", "day"): _osc_candles(Candle)})
    reports = run_generated(research_session, src, [inst_factory("GOLDM")], "day",
                            owner_id=OWNER_ID, limit=2, git_commit="g", min_trades=1, n_folds=3,
                            min_positive_fold_frac=0.0)
    assert len(reports) == 2
    assert research_session.query(GeneratedStrategyRecord).count() == 2


def test_run_generated_checks_claim_before_each_generated_item(
        research_session, inst_factory, candles_factory):
    Candle = type(candles_factory(1)[0])
    src = StaticDataSource({("GOLDM", "day"): _osc_candles(Candle)})
    instruments = [inst_factory("GOLDM")]
    from research.orchestrator.generate import generated_descriptors
    descriptors = generated_descriptors(research_session, instruments, "day", owner_id=OWNER_ID,
                                        limit=1, seed=None, git_commit="unknown",
                                        provider_mode="mock")
    with pytest.raises(RuntimeError, match="claim lost"):
        run_generated(research_session, src, instruments, "day",
                      owner_id=OWNER_ID, limit=1, durable_item_keys=["generated:000:test"],
                      durable_descriptors=descriptors,
                      claim_guard=lambda: (_ for _ in ()).throw(
                          RuntimeError("claim lost")))
    assert research_session.query(GeneratedStrategyRecord).count() == 0


def test_generated_durable_worker_refuses_unadmitted_enumeration_before_provider_io(
        research_session, inst_factory):
    class PoisonSource:
        def candles(self, *_args, **_kwargs):
            raise AssertionError("unadmitted generated work must not fetch data")

    with pytest.raises(RuntimeError, match="admitted durable item descriptors"):
        run_generated(research_session, PoisonSource(), [inst_factory("GOLDM")], "day",
                      owner_id=OWNER_ID, limit=1, claim_guard=lambda: None)


def test_completed_generated_operation_items_need_no_provider_read(
        research_session, inst_factory):
    """A reclaimed generated operation may finish from receipts without data I/O."""
    from research.orchestrator.generate import generated_descriptors

    class PoisonSource:
        def candles(self, *_args, **_kwargs):
            raise AssertionError("completed generated work must not fetch data")

    descriptors = generated_descriptors(
        research_session, [inst_factory("GOLDM")], "day", owner_id=OWNER_ID,
        limit=1, seed=7, git_commit="build-a", provider_mode="mock",
    )
    assert run_generated(
        research_session, PoisonSource(), [inst_factory("GOLDM")], "day",
        owner_id=OWNER_ID, limit=1, git_commit="build-a", claim_guard=lambda: None,
        durable_descriptors=descriptors, durable_item_keys=["generated:0"],
        completed_item_run=lambda key: 101,
    ) == []


def test_cancelled_generated_operation_needs_no_provider_read(
        research_session, inst_factory):
    """A lost claim stops before a generated item can materialize its dataset."""
    from research.orchestrator.generate import generated_descriptors

    class PoisonSource:
        def candles(self, *_args, **_kwargs):
            raise AssertionError("cancelled generated work must not fetch data")

    descriptors = generated_descriptors(
        research_session, [inst_factory("GOLDM")], "day", owner_id=OWNER_ID,
        limit=1, seed=7, git_commit="build-a", provider_mode="mock",
    )
    with pytest.raises(RuntimeError, match="claim lost"):
        run_generated(
            research_session, PoisonSource(), [inst_factory("GOLDM")], "day",
            owner_id=OWNER_ID, limit=1, git_commit="build-a",
            claim_guard=lambda: (_ for _ in ()).throw(RuntimeError("claim lost")),
            durable_descriptors=descriptors, durable_item_keys=["generated:0"],
        )


def test_mixed_generated_descriptor_universes_are_refused_before_provider_read(
        research_session, inst_factory):
    from research.orchestrator.generate import generated_descriptors

    class PoisonSource:
        def get_candles(self, *_args, **_kwargs):
            raise AssertionError("mixed durable descriptor must not fetch data")

    descriptors = generated_descriptors(
        research_session, [inst_factory("GOLDM")], "day", owner_id=OWNER_ID,
        limit=2, seed=7, git_commit="build-a", provider_mode="mock",
    )
    descriptors[1] = {**descriptors[1], "owner_universe": ["SILVERM"]}
    with pytest.raises(RuntimeError, match="provenance drift"):
        run_generated(
            research_session, PoisonSource(), [inst_factory("GOLDM")], "day",
            owner_id=OWNER_ID, limit=2, git_commit="build-a", claim_guard=lambda: None,
            durable_descriptors=descriptors, durable_item_keys=["generated:0", "generated:1"],
        )


def test_generated_manifest_is_secret_free_and_replays_exact_compositions(
        research_session, inst_factory):
    """A durable replay uses its admitted compositions, not today's search weights."""
    from research.orchestrator.generate import (generated_descriptors,
                                                compositions_from_descriptors)

    descriptors = generated_descriptors(
        research_session, [inst_factory("GOLDM")], "day", owner_id=OWNER_ID,
        limit=2, seed=17, git_commit="build-a", provider_mode="mock",
    )
    assert len(descriptors) == 2
    assert all(set(item) == {
        "admission_address", "build", "composition", "composition_identity", "graph",
        "graph_content_address", "interval", "limit",
        "min_positive_fold_frac", "min_trades", "n_folds", "owner_universe",
        "program", "provider_mode", "seed",
    } for item in descriptors)
    assert all("secret" not in str(item).lower() for item in descriptors)
    replayed = compositions_from_descriptors(descriptors)
    assert [item.to_dict() for item in replayed] == [item["composition"] for item in descriptors]
    assert all(item["graph_content_address"].startswith("sha256:") for item in descriptors)
    assert all(item["admission_address"].startswith("sha256:") for item in descriptors)


def test_generated_work_does_not_execute_legacy_build_strategy(
        research_session, inst_factory, candles_factory, monkeypatch):
    """Hypothesis 5: generated Python remains a new-exposure execution authority."""
    import research.strategy.builder.load as load

    monkeypatch.setattr(
        load,
        "build_strategy",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("legacy runtime called")),
    )
    Candle = type(candles_factory(1)[0])
    source = StaticDataSource({("GOLDM", "day"): _osc_candles(Candle)})
    reports = run_generated(
        research_session, source, [inst_factory("GOLDM")], "day", owner_id=OWNER_ID,
        limit=1, git_commit="gen", min_trades=1, n_folds=3, min_positive_fold_frac=0.0)
    assert len(reports) == 1


@pytest.mark.parametrize("field", ("graph", "admission_address"))
def test_durable_generated_authority_mismatch_refuses_before_provider_io(
        research_session, inst_factory, field):
    """Hypothesis 5: a forged durable graph or receipt reaches provider-backed research."""
    from research.orchestrator.generate import generated_descriptors

    class PoisonSource:
        def candles(self, *_args, **_kwargs):
            raise AssertionError("unverified durable graph must not fetch provider data")

    descriptors = generated_descriptors(
        research_session, [inst_factory("GOLDM")], "day", owner_id=OWNER_ID,
        limit=1, seed=7, git_commit="build-a", provider_mode="mock")
    if field == "graph":
        descriptors[0]["graph"] = {**descriptors[0]["graph"], "identifier": "forged.graph"}
    else:
        descriptors[0]["admission_address"] = "sha256:" + "0" * 64
    with pytest.raises(RuntimeError, match="graph|admission|identity"):
        run_generated(
            research_session, PoisonSource(), [inst_factory("GOLDM")], "day",
            owner_id=OWNER_ID, limit=1, git_commit="build-a", claim_guard=lambda: None,
            durable_descriptors=descriptors, durable_item_keys=["generated:0"],
        )


def test_generated_descriptor_rejects_oversized_work_before_enumeration(
        research_session, inst_factory, monkeypatch):
    import research.orchestrator.generate as generate

    monkeypatch.setattr(generate, "_enumerate_for_owner", lambda *_args, **_kwargs:
                        (_ for _ in ()).throw(AssertionError("search must not run")))
    with pytest.raises(ValueError, match="generated descriptor limit"):
        generate.generated_descriptors(
            research_session, [inst_factory("GOLDM")], "day", owner_id=OWNER_ID,
            limit=65, seed=7, git_commit="build-a", provider_mode="mock",
        )
