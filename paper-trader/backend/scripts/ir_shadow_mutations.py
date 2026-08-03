#!/usr/bin/env python3
"""Prove the L1 Stage 1 shadow-lane guards can fail.

A guard nobody has watched go red is a guard nobody knows works. This applies one
deliberate defect at a time, runs the test that is supposed to catch it, and asserts the
test **fails**. Every mutation is reverted afterwards, including on error and on Ctrl-C.

    backend/.venv/bin/python scripts/ir_shadow_mutations.py

Exit 0 means every guard reddened on its own defect. Exit 1 names the guards that stayed
green while their defect was in place — those are the vacuous ones.

This is deliberately a script and not a test: it edits source files on disk, and a test
that rewrites the tree it is running from is a hazard, not evidence.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

BACKEND = pathlib.Path(__file__).resolve().parent.parent
PYTHON = BACKEND / ".venv" / "bin" / "python"

RUNNER = BACKEND / "app" / "engine" / "runner.py"
SHADOW = BACKEND / "app" / "engine" / "ir_shadow.py"
STORE = BACKEND / "app" / "engine" / "ir_shadow_store.py"
METRICS = BACKEND / "app" / "engine" / "ir_shadow_metrics.py"
CONFIG = BACKEND / "app" / "core" / "config.py"
ADAPTER = BACKEND / "app" / "strategy" / "ir_adapter.py"

ISOLATION = "tests/test_ir_shadow_isolation.py"
CORE = "tests/test_ir_shadow.py"


#: (name, file, find, replace, the test that must go red)
MUTATIONS: list[tuple[str, pathlib.Path, str, str, str]] = [
    (
        # NB the obvious version of this mutation — writing into `self.state[key]` from
        # inside `_observe_shadow` — is a NO-OP, because the observer is called before the
        # state entry is built and the assignment that follows replaces the dict wholesale.
        # The harness caught that as a vacuous guard, which is what it is for. The leak has
        # to be injected where a real one would live: after the state entry exists.
        "the shadow verdict is fed back into the engine's state",
        RUNNER,
        '                "priority_flag": self.priority_flags.get(key, False),\n'
        "            }",
        '                "priority_flag": self.priority_flags.get(key, False),\n'
        "            }\n"
        '            self.state[key]["shadow_signal"] = True',
        f"{ISOLATION}::test_the_shadow_lane_writes_nothing_into_the_engine_state",
    ),
    (
        "the shadow lane mutates shared execution parameters",
        RUNNER,
        "            if ir_shadow.pairing_for(strat.key) is None:",
        '            self.params["intraday_max_positions"] = 0\n'
        "            if ir_shadow.pairing_for(strat.key) is None:",
        f"{ISOLATION}::test_the_authoritative_state_is_identical_with_the_shadow_on_and_off",
    ),
    (
        "the shadow lane touches a broker seam",
        RUNNER,
        "            if ir_shadow.pairing_for(strat.key) is None:",
        "            self.broker.commit()\n"
        "            if ir_shadow.pairing_for(strat.key) is None:",
        f"{ISOLATION}::test_a_full_shadow_scan_reaches_no_broker_or_order_seam",
    ),
    (
        "the shadow store imports the order path",
        STORE,
        "from app.db.session import SessionLocal",
        "from app.db.session import SessionLocal\n"
        "from app.engine.kite_order_client import KiteOrderClient  # noqa: F401",
        f"{ISOLATION}::test_no_shadow_module_names_an_execution_seam_directly"
        "[app.engine.ir_shadow_store]",
    ),
    (
        "a shadow failure escapes into the signal lane",
        RUNNER,
        "        except Exception as e:\n"
        "            log.error(f\"IR shadow lane error (authoritative lane unaffected): {e}\",\n"
        "                      instrument=key, event=\"IR_SHADOW\")",
        "        except Exception as e:\n"
        "            raise",
        f"{ISOLATION}::test_a_failure_anywhere_in_the_lane_leaves_the_authoritative_output"
        "_unchanged",
    ),
    (
        "the feature flag ships on",
        CONFIG,
        "    ir_shadow_enabled: bool = False",
        "    ir_shadow_enabled: bool = True",
        f"{ISOLATION}::test_the_flag_is_off_by_default_and_the_lane_is_inert",
    ),
    (
        "agreement is counted per scan instead of per bar",
        METRICS,
        "            if self._last_bar.get(observation.instrument_key) == bar:\n"
        "                return                      # the same completed bar, re-scanned",
        "            if False:\n"
        "                return",
        "tests/test_ir_shadow_metrics.py::test_a_rescanned_bar_is_not_counted_twice",
    ),
    (
        "an unsettleable frame goes back to silent all-False",
        ADAPTER,
        "    refuse_insufficient_history: bool = True",
        "    refuse_insufficient_history: bool = False",
        f"{CORE}::test_a_frame_shorter_than_the_graph_warmup_is_classified_not_silent",
    ),
    (
        "a persistent cross-frame evaluation cache is reintroduced",
        SHADOW,
        "    def adapter(self) -> Any:",
        "    def build_cache(self):\n"
        "        from app.ir.runtime import Cache\n"
        "        return Cache()\n\n"
        "    def adapter(self) -> Any:",
        f"{CORE}::test_the_lane_never_constructs_a_persistent_evaluation_cache",
    ),
]


def run(test: str) -> bool:
    """True if the test passed."""
    result = subprocess.run(
        [str(PYTHON), "-m", "pytest", test, "-x", "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=BACKEND, capture_output=True, text=True)
    return result.returncode == 0


def main() -> int:
    failures: list[str] = []
    print(f"{'guard':<62} {'clean':<8} {'mutated':<8} verdict")
    print("-" * 96)
    for name, path, find, replace, test in MUTATIONS:
        original = path.read_text()
        if find not in original:
            print(f"{name:<62} {'-':<8} {'-':<8} ANCHOR NOT FOUND in {path.name}")
            failures.append(name)
            continue
        clean = run(test)
        try:
            path.write_text(original.replace(find, replace, 1))
            mutated = run(test)
        finally:
            path.write_text(original)
        caught = clean and not mutated
        print(f"{name:<62} {'PASS' if clean else 'FAIL':<8} "
              f"{'PASS' if mutated else 'FAIL':<8} "
              f"{'guard works' if caught else 'VACUOUS — guard did not catch it'}")
        if not caught:
            failures.append(name)

    print("-" * 96)
    if failures:
        print(f"{len(failures)} guard(s) did not redden: " + "; ".join(failures))
        return 1
    print(f"all {len(MUTATIONS)} guards reddened on their own defect and were restored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
