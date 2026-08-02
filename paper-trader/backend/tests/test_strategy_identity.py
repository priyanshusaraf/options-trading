"""Strategy identity — the `(key, version)` execution artifact, and the fail-closed
resolution that stops an unresolvable strategy from trading the platform default with
somebody else's capital (audit finding C4).

Two properties are pinned here, and both are safety properties rather than API taste:

1. A version is a *content* hash — stable across processes, sensitive to anything that
   changes behaviour, insensitive to anything that does not. If this drifts, every
   performance claim and attribution report becomes unfalsifiable.
2. `resolve_strategy` raises for an unknown key while `get_strategy` still falls back.
   The legacy fallback must keep working byte-for-byte (the engine's per-instrument
   path depends on it and invariant 2 says never block an exit) — this is additive.
"""
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from app.strategy import identity
from app.strategy.registry import (
    DEFAULT_STRATEGY_KEY, StrategyNotFound, all_strategies, get_strategy,
    resolve_strategy, strategy_meta)
from app.strategy.registry.base import Strategy


# --------------------------------------------------------------------------- identity

def test_content_hash_is_deterministic_for_identical_inputs():
    a = identity.content_hash(key="k", code="x=1", default_params={"a": 1, "b": 2})
    b = identity.content_hash(key="k", code="x=1", default_params={"b": 2, "a": 1})
    assert a == b            # dict ordering must not matter
    assert len(a) == 64 and all(c in "0123456789abcdef" for c in a)


def test_content_hash_changes_when_behaviour_changes():
    base = dict(key="k", code="x=1", default_params={"a": 1}, risk_model=None)
    h = identity.content_hash(**base)
    assert identity.content_hash(**{**base, "key": "k2"}) != h
    assert identity.content_hash(**{**base, "code": "x=2"}) != h
    assert identity.content_hash(**{**base, "default_params": {"a": 2}}) != h
    assert identity.content_hash(**{**base, "risk_model": {"atr_length": 14}}) != h


def test_hash_is_stable_across_processes():
    """PYTHONHASHSEED randomisation must not reach the version. A version computed on
    the VPS has to equal one computed on the Mac or cross-machine attribution is a
    fiction, and `hash()`-based schemes look correct in a single-process test."""
    root = Path(__file__).resolve().parents[1]
    snippet = (
        "from app.strategy.identity import content_hash;"
        "print(content_hash(key='k', code='src', default_params={'z':1,'a':[1,2]},"
        " risk_model={'atr_length':14}))")
    outs = set()
    for seed in ("0", "12345"):
        r = subprocess.run([sys.executable, "-c", snippet], cwd=root, capture_output=True,
                           text=True,
                           env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin",
                                "PYTHONPATH": str(root),
                                # no pytest in this process → `.env` would otherwise be
                                # read; keep the subprocess as isolated as the suite.
                                "PT_DISABLE_DOTENV": "1", "PT_PROVIDER": "mock",
                                "PT_EXECUTION": "paper", "PT_LIVE_ACK": ""})
        assert r.returncode == 0, r.stderr
        outs.add(r.stdout.strip())
    assert len(outs) == 1, f"version varied across processes: {outs}"
    assert outs.pop() == identity.content_hash(
        key="k", code="src", default_params={"z": 1, "a": [1, 2]},
        risk_model={"atr_length": 14})


def test_display_name_is_not_part_of_identity():
    """Renaming a strategy in the UI must not mint a new execution artifact — no trade
    behaves differently for a label."""
    class _S(Strategy):
        key = "ident_label_test"
        display_name = "Before"
        default_params = {"a": 1}

        def compute(self, df, **p):
            return df

    s = _S()
    v1 = identity.compute_version(s)
    s.display_name = "After"
    assert identity.compute_version(s) == v1


def test_unhashable_param_still_yields_a_version():
    """Identity is metadata; it must never be able to break signal generation."""
    class _S(Strategy):
        key = "ident_exotic"
        default_params = {"fn": lambda x: x, "s": {3, 1, 2}}

        def compute(self, df, **p):
            return df

    v = identity.compute_version(_S())
    assert v != identity.UNKNOWN_VERSION and len(v) == 64


def test_compute_version_never_raises():
    class _Hostile:
        key = "boom"

        @property
        def default_params(self):
            raise RuntimeError("nope")

    assert identity.compute_version(_Hostile()) == identity.UNKNOWN_VERSION


def test_class_code_falls_back_without_source():
    """A class with no obtainable source gets a weaker-but-stable identity instead of
    an import-time crash. Marked in the text so it is not mistaken for a real hash."""
    ns = {}
    exec("class NoSrc:\n    pass\n", ns)          # noqa: S102 — test fixture
    code = identity.class_code(ns["NoSrc"])
    assert code.startswith("<no-source:")


# -------------------------------------------------------- version on real strategies

def test_every_registered_strategy_has_a_stable_version():
    for s in all_strategies():
        assert s.version and s.version != identity.UNKNOWN_VERSION, s.key
        assert s.version == s.version                  # cached, not regenerated
        assert s.version == identity.compute_version(s)


def test_versions_are_unique_per_strategy():
    versions = {s.key: s.version for s in all_strategies()}
    assert len(set(versions.values())) == len(versions), versions


def test_strategy_meta_includes_version():
    meta = strategy_meta()
    assert meta
    for m in meta:
        assert m["version"] == get_strategy(m["key"]).version
        assert set(m) >= {"key", "version", "display_name", "default_params"}


def test_pin_version_overrides_the_derived_one():
    s = get_strategy(DEFAULT_STRATEGY_KEY)
    original = s.version
    try:
        s.pin_version("pinned")
        assert s.version == "pinned"
    finally:
        s.pin_version(original)                 # registry is a process-wide singleton


# ------------------------------------------------------------------- fail-closed path

def test_resolve_strategy_raises_for_unknown_key():
    with pytest.raises(StrategyNotFound) as ei:
        resolve_strategy("no_such_strategy_v9")
    assert ei.value.key == "no_such_strategy_v9"
    assert DEFAULT_STRATEGY_KEY in ei.value.available


def test_resolve_strategy_raises_for_none():
    """'No strategy specified' is not a resolvable identity for a deployment-bound
    caller; silently handing back the platform default is the exact C4 failure."""
    with pytest.raises(StrategyNotFound):
        resolve_strategy(None)


def test_strategy_not_found_is_a_lookup_error():
    assert issubclass(StrategyNotFound, LookupError)


def test_resolve_strategy_returns_the_real_strategy_for_a_known_key():
    assert resolve_strategy(DEFAULT_STRATEGY_KEY).key == DEFAULT_STRATEGY_KEY


def test_allow_fallback_reproduces_legacy_behaviour():
    assert resolve_strategy(None, allow_fallback=True).key == DEFAULT_STRATEGY_KEY
    assert resolve_strategy("nope", allow_fallback=True).key == DEFAULT_STRATEGY_KEY


# --------------------------------------------------------- legacy path is unchanged

def test_get_strategy_still_falls_back():
    assert get_strategy(None).key == DEFAULT_STRATEGY_KEY
    assert get_strategy("does_not_exist").key == DEFAULT_STRATEGY_KEY


def test_get_strategy_logs_loudly_when_it_substitutes():
    from app.core.logging import log
    seen = []
    log.subscribe(seen.append)
    try:
        get_strategy("ghost_strategy_for_log_test")
    finally:
        log.unsubscribe(seen.append)
    hits = [e for e in seen if e.get("event") == "strategy_fallback"]
    assert hits, "substituting a strategy must be logged"
    assert hits[0]["level"] == "ERROR"
    assert "ghost_strategy_for_log_test" in hits[0]["msg"]


def test_get_strategy_none_is_not_logged_as_a_substitution():
    """`None` is the explicit 'give me the default' idiom used by the chart and
    backtest paths on every request — logging it would bury the real substitutions."""
    from app.core.logging import log
    seen = []
    log.subscribe(seen.append)
    try:
        get_strategy(None)
    finally:
        log.unsubscribe(seen.append)
    assert not [e for e in seen if e.get("event") == "strategy_fallback"]


def test_fallback_logging_does_not_break_signal_generation():
    df = pd.DataFrame({"date": pd.date_range("2024-01-01 09:15", periods=120, freq="15min"),
                       "open": 100.0, "high": 101.0, "low": 99.0,
                       "close": [100 + i * 0.1 for i in range(120)]})
    out = get_strategy("still_missing").signals(df)
    assert "longEntry" in out.columns


# ------------------------------------------------------------ generated strategies

_COMP = {
    "key": "gen_ident_test_v1",
    "longEntry":  {"all": ["ema_slope_up(50,5)", "zscore_cross_up(50,1.0)"]},
    "shortEntry": {"all": ["ema_slope_down(50,5)", "zscore_cross_down(50,1.0)"]},
    "longExit":   {"any": ["zscore_lt(50,0.0)", "ema_slope_down(50,5)"]},
    "shortExit":  {"any": ["zscore_gt(50,0.0)", "ema_slope_up(50,5)"]},
}
_COMP_EDITED = {**_COMP, "longExit": {"any": ["zscore_lt(50,0.5)", "ema_slope_down(50,5)"]}}


def _register_comp(comp: dict) -> str:
    """Persist `comp` and run the real startup path; returns the registered version."""
    import json
    from app.core import generated_strategies as gs
    from app.db.session import SessionLocal, init_db
    init_db(reset=True)
    with SessionLocal() as s:
        gs.save_generated(s, comp["key"], json.dumps(comp))
        s.commit()
    with SessionLocal() as s:
        assert gs.register_all(s) >= 1
    return get_strategy(comp["key"]).version


@pytest.fixture
def _clean_registry():
    yield
    from app.strategy import registry
    registry._REGISTRY.pop("gen_ident_test_v1", None)   # process-global singleton


def test_generated_strategy_registers_with_its_content_hash(_clean_registry):
    from app.core.generated_strategies import generated_version
    v = _register_comp(_COMP)
    assert v != identity.UNKNOWN_VERSION and len(v) == 64
    assert v == generated_version(_COMP)
    # the pinned version must equal what the lazy derivation would give — one scheme,
    # not two that could disagree about which artifact traded.
    assert v == identity.compute_version(get_strategy("gen_ident_test_v1"))


def test_editing_a_generated_strategy_changes_its_version(_clean_registry):
    """The history-rewrite guard. `generated_strategies.key` is a primary key, so a
    re-deploy overwrites the row in place; without a content version, past trades would
    silently re-attribute to logic that never ran."""
    v1 = _register_comp(_COMP)
    v2 = _register_comp(_COMP_EDITED)
    assert v1 != v2


def test_generated_version_is_insensitive_to_json_reserialisation():
    """Same logic ⇒ same hash. Key order / whitespace in the stored JSON must not mint
    a new artifact, or every restart could look like a new strategy."""
    from app.core.generated_strategies import generated_version
    shuffled = {k: _COMP[k] for k in reversed(list(_COMP))}
    assert generated_version(_COMP) == generated_version(shuffled)


def test_two_generated_strategies_do_not_share_a_version(_clean_registry):
    """They share the `GeneratedStrategy` wrapper class, so hashing class source would
    collapse every generated strategy onto one version."""
    from app.core.generated_strategies import generated_version
    other = {**_COMP_EDITED, "key": "gen_ident_other_v1"}
    assert generated_version(_COMP) != generated_version(other)


def test_generated_strategy_resolves_fail_closed_after_registration(_clean_registry):
    _register_comp(_COMP)
    assert resolve_strategy("gen_ident_test_v1").key == "gen_ident_test_v1"


def test_unregistered_generated_key_fails_closed():
    """A row that failed to rebuild must NOT reach the market as the platform default
    for any deployment-bound caller — that is the whole of C4."""
    with pytest.raises(StrategyNotFound):
        resolve_strategy("gen_never_deployed_v1")
