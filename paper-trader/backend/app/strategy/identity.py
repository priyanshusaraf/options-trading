"""Content-addressed identity for strategies — the `version` half of `(key, version)`.

Audit finding C4: a strategy's identity today is a mutable string. `generated_strategies`
keys are a primary key with no version, so redeploying an edited strategy under the same
key silently rewrites history — every past trade attributed to `gen_x` now points at
different logic, and no backtest, attribution report or performance claim can be
falsified afterwards. The fix is to make the *behaviour* the identity: a version derived
from a hash of the things that actually decide what the strategy does.

The rules that make this trustworthy, and why each one is here:

* **Deterministic across processes and machines.** sha256 over a canonical JSON
  encoding with sorted keys — never `hash()` (PYTHONHASHSEED-randomised), never
  `id()`, never a timestamp or a counter. Two boxes running the same code must
  compute the same version or cross-machine attribution is meaningless.
* **Behaviour only.** `display_name` is deliberately NOT in the payload: renaming a
  strategy in the UI must not create a new execution artifact, because no trade
  behaves differently for it. `key`, the code/composition, `default_params` and
  `risk_model` are in, because each of them changes what gets traded.
* **Comments and formatting DO change the version.** This is a content hash, not a
  semantic hash. Over-sensitivity is the safe failure direction here: a spurious new
  version costs an attribution row, a missed one silently merges two different
  behaviours into one performance record.

These are pure functions. Nothing here touches the DB, the registry, or the engine.
"""
from __future__ import annotations

import hashlib
import inspect
import json
from typing import Any

# Bumped only if the *payload construction* below changes in a way that would make old
# and new hashes incomparable. It is part of the hashed payload so a scheme change is
# visible as a version change rather than as a silent collision across schemes.
IDENTITY_SCHEME = "strategy-identity/1"

# A version we could not derive from content. Deliberately NOT a random or a
# timestamp value: an unknown version must be recognisably unknown everywhere it
# lands, the same way `build_sha='unknown'` is distinguishable from a real SHA.
UNKNOWN_VERSION = "unknown"


def _stable(obj: Any) -> Any:
    """Coerce `obj` into something `json.dumps` can encode deterministically.

    Params are user/grammar supplied and may hold numpy scalars, tuples, enums, or a
    callable. Falling back to `repr()` keeps the hash *stable* for those (repr of a
    numpy float is fixed) without letting an exotic value abort version computation —
    a strategy must always have a version, even an imperfect one.
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        # keys coerced to str so mixed-type key dicts still sort deterministically
        return {str(k): _stable(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [_stable(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted(_stable(v) for v in obj)
    return repr(obj)


def canonical_json(obj: Any) -> str:
    """The exact bytes that get hashed. Sorted keys, no incidental whitespace."""
    return json.dumps(_stable(obj), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def behaviour_payload(*, key: str, code: str, default_params: Any = None,
                      risk_model: Any = None) -> dict:
    """The canonical description of what a strategy does. Hash input, and also the
    thing to diff when two versions differ and somebody asks *why*."""
    return {
        "scheme": IDENTITY_SCHEME,
        "key": key or "",
        "code": code or "",
        "default_params": _stable(default_params or {}),
        "risk_model": _stable(risk_model) if risk_model else None,
    }


def content_hash(*, key: str, code: str, default_params: Any = None,
                 risk_model: Any = None) -> str:
    """sha256 (full 64-hex) of the behaviour payload.

    Full digest, not a truncation: this is written next to money records and is the
    only evidence of which code executed a trade. Storage is 64 bytes; a collision
    argument is not something anyone should have to make in a regulatory conversation.
    """
    blob = canonical_json(behaviour_payload(
        key=key, code=code, default_params=default_params, risk_model=risk_model))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def composition_code(composition_dict: Any) -> str:
    """Behaviour text for a *generated* strategy.

    A generated strategy's Python class source is identical for every generated
    strategy (`GeneratedStrategy` in the builder) — the behaviour lives entirely in
    the composition. Hashing the canonical dict rather than the stored JSON string
    means re-serialising a row (different key order, different whitespace) does not
    invent a new version for logic that did not change.
    """
    return canonical_json(composition_dict)


def class_code(cls: type) -> str:
    """Behaviour text for a hand-written strategy: its class source.

    `inspect.getsource` can fail for a class with no source file (exec'd, zipped, or
    a REPL definition). We fall back to a stable module/qualname identity rather than
    raising: a strategy with no obtainable source still needs *an* identity, and a
    hard failure here would take down the engine at import time for a cosmetic
    reason. The fallback is weaker — it does not change when the logic changes — so
    it is marked in the payload so nobody mistakes it for a real content hash.
    """
    try:
        return inspect.getsource(cls)
    except (OSError, TypeError):
        return f"<no-source:{cls.__module__}.{cls.__qualname__}>"


def strategy_code(strat: Any) -> str:
    """Pick the right behaviour text for a Strategy instance.

    Composition wins over class source: for generated strategies the class source is
    a constant and would hash every generated strategy to the same version.
    """
    comp = getattr(strat, "composition", None)
    if comp is not None:
        to_dict = getattr(comp, "to_dict", None)
        if callable(to_dict):
            return composition_code(to_dict())
        return composition_code(comp)
    return class_code(type(strat))


def compute_version(strat: Any) -> str:
    """The immutable content version of a Strategy instance.

    Never raises. A strategy that cannot be hashed returns `UNKNOWN_VERSION`, which
    is recognisably-unknown downstream, rather than a plausible-looking wrong hash.
    """
    try:
        return content_hash(
            key=getattr(strat, "key", "") or "",
            code=strategy_code(strat),
            default_params=getattr(strat, "default_params", None),
            risk_model=getattr(strat, "risk_model", None),
        )
    except Exception:  # identity is metadata; it must never break signal generation
        return UNKNOWN_VERSION


# NOTE: no `short_version()` helper here on purpose. Abbreviating a content hash for
# display belongs to the surface that displays it, and this codebase's defining defect
# is mechanisms built but wired to nothing — a truncation helper with no caller would be
# exactly that, and `__all__` would hide it from the unconsumed-mechanism guard.

__all__ = ["IDENTITY_SCHEME", "UNKNOWN_VERSION", "canonical_json", "behaviour_payload",
           "content_hash", "composition_code", "class_code", "strategy_code",
           "compute_version"]
