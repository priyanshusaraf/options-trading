"""
The kernel registry seam.

RFC 0001 §2 defines a kernel as "an opaque leaf implementation of a component
body, supplied by a registry". Three §4 clauses — C8 (cache identity), C9
(purity) and C10 (warmup) — are properties of that implementation, and this
module is where a kernel declares them.

**Why these declarations are not in §3.** They are not serialised into an
artefact. A graph references a component; the component's body is a content
address; the registry is what turns that address into an implementation and its
properties. Putting `warmup` into the artefact grammar would have bought nothing
and cost a migration pass forever (§3's preamble). This file is free; the
grammar is not.

**Why the field set is closed.** C9 says impurity "MUST NOT be available as an
escape hatch". ComfyUI's `IS_CHANGED` is the named counter-example: a per-node
hook that makes the cache correct while destroying its value as a provenance
claim. An open field set is that hook waiting to be added, so
`kernel_spec()` rejects any field it does not know.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

# ── C9 — purity ───────────────────────────────────────────────────────────
#
# A component is pure, or it names one of a closed set of policies. The set is
# closed because "declared policy" and "escape hatch" differ only in whether
# the vocabulary is finite. These three are the platform's real impurities:
# what the account holds, what the broker knows, and what time it is.

PURE = "pure"

IMPURITY_POLICIES = ("account_state", "broker_state", "wall_clock")


# ── C8 — cache identity ───────────────────────────────────────────────────
#
# "Cache identity MUST be transitive over the upstream subgraph by default, and
# MAY be declared per component." Transitive is the default because correctness
# under composition should be automatic — the property Prefect lacks. `declared`
# exists for components whose identity genuinely is not their inputs, and it
# must then say what its identity *is*, which is what keeps it a declaration
# rather than an opt-out.

CACHE_IDENTITIES = ("transitive", "declared")


@dataclass(frozen=True)
class KernelSpec:
    """What a registry knows about one leaf implementation.

    `warmup` is an integer **or a function of the node's bound parameters**.
    C10 says warmup "MUST be **derived** per component", and for almost every
    real indicator it is derived from a parameter: a 200-bar EMA does not warm
    up in the 50 bars its default asks for. A constant here would be right only
    for nodes that happen to take the default, and wrong silently for the rest —
    a backtest reading unwarmed values and looking plausible.

    The function is evaluated during resolution, with that node's parameters,
    and its result is checked the same way a constant is (C11: non-negative).
    """

    warmup: int | Callable[[Mapping[str, Any]], int] = 0
    purity: str = PURE
    cache_identity: str = "transitive"
    cache_key: str | None = None

    def warmup_for(self, params: Mapping[str, Any]) -> int:
        """This kernel's warmup at these parameters."""
        return self.warmup(params) if callable(self.warmup) else self.warmup


_FIELDS = frozenset({"warmup", "purity", "cache_identity", "cache_key"})


class KernelDeclarationError(ValueError):
    """A kernel declaration that no conforming registry may hold."""

    def __init__(self, clause: str, message: str) -> None:
        super().__init__(f"{clause}: {message}")
        self.clause = clause


def kernel_spec(**fields: Any) -> KernelSpec:
    """Build a `KernelSpec`, rejecting anything outside the closed field set.

    The rejection is the point. `kernel_spec(is_changed=...)` is ComfyUI's
    escape hatch by name, and C9 forbids it existing at all rather than
    forbidding its use.
    """
    unknown = sorted(set(fields) - _FIELDS)
    if unknown:
        raise KernelDeclarationError(
            "C9",
            f"a kernel declares only {sorted(_FIELDS)}; {unknown} would be an "
            "escape hatch, and impurity is expressible only as a declared policy",
        )

    spec = KernelSpec(**fields)

    # C11 — lookahead is prevented structurally. Warmup is the only temporal
    # declaration a kernel has, and it counts *backwards*. A negative warmup
    # would be a component asking for bars that have not happened; there is no
    # other way to express it, so refusing this one refuses all of them.
    #
    # A callable is checked at resolution instead, with the node's parameters —
    # it cannot be checked here, because here there are no parameters yet.
    if not callable(spec.warmup):
        check_warmup(spec.warmup)

    if spec.purity != PURE and spec.purity not in IMPURITY_POLICIES:
        raise KernelDeclarationError(
            "C9",
            f"{spec.purity!r} is neither {PURE!r} nor one of the declared "
            f"policies {IMPURITY_POLICIES}",
        )

    if spec.cache_identity not in CACHE_IDENTITIES:
        raise KernelDeclarationError(
            "C8", f"cache_identity must be one of {CACHE_IDENTITIES}")
    if spec.cache_identity == "declared" and not spec.cache_key:
        raise KernelDeclarationError(
            "C8",
            "a declared cache identity must say what it is; a declaration with "
            "no key is an opt-out of caching correctness",
        )
    if spec.cache_identity == "transitive" and spec.cache_key:
        raise KernelDeclarationError(
            "C8", "a transitive cache identity is its upstream; a key would be ignored")

    return spec


def check_warmup(warmup: Any, where: str = "a kernel") -> int:
    """C11 — the one temporal declaration, and it counts backwards only."""
    if not isinstance(warmup, int) or isinstance(warmup, bool) or warmup < 0:
        raise KernelDeclarationError(
            "C11",
            f"{where}'s warmup must be a non-negative integer of bars, not "
            f"{warmup!r}; a negative warmup is a read of the future",
        )
    return warmup


def kernel_registry(entries: Mapping[str, Mapping[str, Any] | KernelSpec]
                    ) -> dict[str, KernelSpec]:
    """Build a content-address → `KernelSpec` registry, validating each entry."""
    registry: dict[str, KernelSpec] = {}
    for ref, entry in entries.items():
        registry[ref] = entry if isinstance(entry, KernelSpec) else kernel_spec(**entry)
    return registry
