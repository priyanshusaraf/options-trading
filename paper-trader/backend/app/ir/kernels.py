"""
The kernel registry seam.

Where a kernel declares its cache identity (C8), purity (C9) and warmup (C10).
These live in the registry, not in the §3 artefact grammar. The field set is
closed on purpose: an open one is C9's forbidden escape hatch waiting to happen.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from app.ir.causal import CausalContract

PURE = "pure"

IMPURITY_POLICIES = ("account_state", "broker_state", "wall_clock")

CACHE_IDENTITIES = ("transitive", "declared")


@dataclass(frozen=True)
class KernelSpec:
    """What a registry knows about one leaf implementation.

    `warmup` may be a function of the node's bound parameters; it is then
    evaluated during resolution and checked the same way a constant is.
    """

    warmup: int | Callable[[Mapping[str, Any]], int] = 0
    purity: str = PURE
    cache_identity: str = "transitive"
    cache_key: str | None = None
    causal: CausalContract | None = None

    def warmup_for(self, params: Mapping[str, Any]) -> int:
        return self.warmup(params) if callable(self.warmup) else self.warmup


_FIELDS = frozenset({"warmup", "purity", "cache_identity", "cache_key", "causal"})


class KernelDeclarationError(ValueError):
    """A kernel declaration that no conforming registry may hold."""

    def __init__(self, clause: str, message: str) -> None:
        super().__init__(f"{clause}: {message}")
        self.clause = clause


def kernel_spec(**fields: Any) -> KernelSpec:
    """Build a `KernelSpec`, rejecting anything outside the closed field set."""
    unknown = sorted(set(fields) - _FIELDS)
    if unknown:
        raise KernelDeclarationError(
            "C9",
            f"a kernel declares only {sorted(_FIELDS)}; {unknown} would be an "
            "escape hatch, and impurity is expressible only as a declared policy",
        )

    spec = KernelSpec(**fields)

    if spec.causal is not None and not isinstance(spec.causal, CausalContract):
        raise KernelDeclarationError(
            "C11", "causal metadata must be a CausalContract or None")

    # A callable warmup is checked at resolution instead: no parameters here yet.
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
    """C11: warmup counts backwards only."""
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
