"""Prove the provider-conformance guards can go red, one defect at a time.

A conformance suite that has only ever been observed passing is indistinguishable from one that
checks nothing. Each mutation below reintroduces exactly one of the defects this slice fixed,
runs the suite, and requires that the guard which is supposed to catch it fails — and that it
fails naming that defect, not something incidental. Every file is restored byte-for-byte.

Run from `backend/`:  .venv/bin/python scripts/provider_conformance_mutations.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUITE = "tests/test_provider_conformance.py"
SUITES = {"tests/test_provider_read_failures.py": (
    "test_a_failing_history_call_raises_rather_than_reporting_no_data",
    "test_the_raised_error_still_reads_as_an_expired_token",
)}

# (label, file, find, replace, test that must fail, string its failure must contain)
MUTATIONS = [
    ("replay narrows option_ltp back to one argument",
     "app/providers/replay.py",
     "    def option_ltp(self, inst, tradingsymbol, strike, expiry, option_type) -> float | None:",
     "    def option_ltp(self, tradingsymbol) -> float | None:",
     "test_replay_can_be_asked_for_an_option_price_by_inherited_code",
     "TypeError"),

    ("replay refuses an option chain with [] again",
     "app/providers/replay.py",
     "    def get_option_chain(self, inst) -> None:",
     "    def get_option_chain(self, inst): return []\n    def _unused_chain(self, inst) -> None:",
     "test_replay_refuses_an_option_chain_in_the_contracts_vocabulary",
     "assert [] is None"),

    ("the mock stops declaring the futures pricing it implements",
     "app/providers/mock.py",
     "caps.OPTION_CHAIN, caps.FUTURES_QUOTES,",
     "caps.OPTION_CHAIN,",
     "test_the_mock_declares_the_futures_pricing_it_actually_implements",
     "futures_quotes"),

    ("the mock prices a contract that has already settled",
     "app/providers/mock.py",
     "        if days < 0:",
     "        if False:",
     "test_the_mock_refuses_an_expiry_that_has_already_passed",
     "is None"),

    ("kite looks for futures on the underlying's cash exchange again",
     "app/providers/kite.py",
     "        for row in self._instruments(inst.segment):",
     "        for row in self._instruments(inst.spot_exchange):",
     "test_kite_still_prices_the_exact_series_and_refuses_the_others",
     "None is not None"),

    ("the futures entry path invents today as the contract expiry again",
     "app/engine/runner.py",
     "            expiry = self.provider.front_month_expiry(inst)",
     "            expiry = getattr(inst, 'expiry', None) or now.date()",
     "test_the_futures_entry_path_refuses_when_no_contract_can_be_named",
     "must not open a futures position"),

    ("the mock's front month converges to spot again",
     "app/providers/mock.py",
     "        return self._active_expiry(self.now())",
     "        return self.now().date()",
     "test_the_mock_never_prices_its_own_front_month_at_spot",
     "assert"),

    ("kite swallows a failed history read and reports no data again",
     "app/providers/kite.py",
     '            raise ProviderReadError(f"historical_data failed: {e}") from e',
     '            log.error(f"historical_data failed: {e}"); return []',
     "test_a_failing_history_call_raises_rather_than_reporting_no_data",
     "DID NOT RAISE"),

    ("the read error stops carrying the transport's message",
     "app/providers/kite.py",
     '            raise ProviderReadError(f"historical_data failed: {e}") from e',
     '            raise ProviderReadError("historical_data failed") from e',
     "test_the_raised_error_still_reads_as_an_expired_token",
     "the auth-error latch reads the message"),

    ("kite quotes the futures contract on the cash exchange again",
     "app/providers/kite.py",
     '        key = f"{inst.segment}:{row[\'tradingsymbol\']}"',
     '        key = f"{inst.spot_exchange}:{row[\'tradingsymbol\']}"',
     "test_kite_still_prices_the_exact_series_and_refuses_the_others",
     "None is not None"),
]


def run(test: str = "") -> tuple[int, str]:
    env = {**os.environ, "PT_DISABLE_DOTENV": "1", "PT_PROVIDER": "mock",
           "PT_EXECUTION": "paper", "PT_LIVE_ACK": ""}
    suite = next((f for f, names in SUITES.items() if test in names), SUITE)
    target = f"{suite}::{test}" if test else f"{SUITE} {' '.join(SUITES)}"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *target.split(), "--tb=long", "-rA"],
        cwd=ROOT, env=env, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    failures = []
    for label, rel, find, repl, test, expect in MUTATIONS:
        path = ROOT / rel
        original = path.read_text()
        if original.count(find) != 1:
            failures.append(f"{label}: anchor appears {original.count(find)} times — the "
                            f"mutation never applied, so its result means nothing")
            continue
        path.write_text(original.replace(find, repl))
        try:
            code, out = run(test)
        finally:
            path.write_text(original)
        assert path.read_text() == original, f"{rel} was not restored"

        if code == 0:
            failures.append(f"{label}: {test} STAYED GREEN — the guard is vacuous")
        elif expect not in out:
            failures.append(f"{label}: {test} failed, but not for its own reason "
                            f"(expected {expect!r} in the output)")
        else:
            print(f"RED as intended · {label}\n              → {test}")

    # And the restored tree must be green, or the sweep itself broke something.
    code, out = run("")
    if code != 0:
        failures.append(f"the suite is not green after restoration:\n{out[-2000:]}")

    if failures:
        print("\nSWEEP FAILED")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"\n{len(MUTATIONS)}/{len(MUTATIONS)} mutations reddened their own guard and were "
          f"restored · suite green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
