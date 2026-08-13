"""Immutable transport for Component IR declarations and implementations."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Mapping

from app.ir.causal import CausalContract
from app.ir.hashing import content_address
from app.ir.implementation_identity import ImplementationUnidentified, implementation_address
from app.ir.kernels import KernelSpec, kernel_spec
from app.ir.resolve import Library
from app.ir.schema import is_content_address


@dataclass(frozen=True)
class DependencyBoundary:
    mode: str
    objects: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        if self.mode not in {"declared_objects", "defining_module"}:
            raise ValueError(f"unsupported dependency boundary {self.mode!r}")
        object.__setattr__(self, "objects", tuple(self.objects))


@dataclass(frozen=True)
class KernelRegistration:
    body_ref: str
    spec: KernelSpec
    implementation: Callable[..., Mapping[str, Any]]
    dependency_boundary: DependencyBoundary
    implementation_address: str


def registered_kernel(
    *,
    body_ref: str,
    implementation: Callable[..., Mapping[str, Any]],
    causal: CausalContract,
    dependency_boundary: DependencyBoundary,
    warmup: int | Callable[[Mapping[str, Any]], int] = 0,
    purity: str = "pure",
    cache_identity: str = "transitive",
    cache_key: str | None = None,
) -> KernelRegistration:
    """Create one registration; the implementation address is never caller input."""
    if not is_content_address(body_ref):
        raise ValueError("body_ref must be a canonical content address")
    spec = kernel_spec(
        warmup=warmup,
        purity=purity,
        cache_identity=cache_identity,
        cache_key=cache_key,
        causal=causal,
    )
    address = implementation_address(
        implementation,
        dependency_boundary,
        recursive_state=causal.recursive_state,
    )
    return KernelRegistration(
        body_ref=body_ref,
        spec=spec,
        implementation=implementation,
        dependency_boundary=dependency_boundary,
        implementation_address=address,
    )


class PlatformRegistry:
    """One immutable authority for component bytes and executable registrations."""

    def __init__(
        self,
        *,
        components: Mapping[tuple[str, int], Mapping[str, Any]],
        bodies: Mapping[str, Mapping[str, Any]],
        registrations: Mapping[str, KernelRegistration],
    ) -> None:
        copied_components = {key: _freeze(value) for key, value in components.items()}
        copied_bodies = {key: _freeze(value) for key, value in bodies.items()}
        copied_registrations = dict(registrations)
        for ref, registration in copied_registrations.items():
            if ref != registration.body_ref:
                raise ValueError(
                    f"registration key {ref!r} differs from body_ref {registration.body_ref!r}"
                )
            try:
                actual_address = implementation_address(
                    registration.implementation,
                    registration.dependency_boundary,
                    recursive_state=(registration.spec.causal.recursive_state
                                     if registration.spec.causal else None),
                )
            except ImplementationUnidentified as exc:
                raise ValueError(
                    f"registration {ref} has stale implementation dependency closure"
                ) from exc
            if actual_address != registration.implementation_address:
                raise ValueError(
                    f"registration {ref} has stale or forged implementation_address"
                )
        component_kernel_refs = {
            component["body"]["ref"]
            for component in copied_components.values()
            if component.get("body", {}).get("body") == "kernel"
        }
        if component_kernel_refs != set(copied_registrations):
            missing = sorted(component_kernel_refs - set(copied_registrations))
            extra = sorted(set(copied_registrations) - component_kernel_refs)
            raise ValueError(
                f"component/registration closure differs; missing={missing}, extra={extra}"
            )
        component_graph_refs = {
            component["body"]["ref"]
            for component in copied_components.values()
            if component.get("body", {}).get("body") == "graph"
        }
        if component_graph_refs != set(copied_bodies):
            missing = sorted(component_graph_refs - set(copied_bodies))
            extra = sorted(set(copied_bodies) - component_graph_refs)
            raise ValueError(
                f"component/graph body closure differs; missing={missing}, extra={extra}"
            )
        for ref, body in copied_bodies.items():
            if content_address(body) != ref:
                raise ValueError(f"graph body {ref} does not match its content address")
        self._registrations = MappingProxyType(copied_registrations)
        self._library = Library(
            components=MappingProxyType(copied_components),
            bodies=MappingProxyType(copied_bodies),
            kernels=MappingProxyType({
                ref: registration.spec
                for ref, registration in copied_registrations.items()
            }),
        )
        self._implementations = MappingProxyType({
            ref: registration.implementation
            for ref, registration in copied_registrations.items()
        })

    @property
    def registrations(self) -> Mapping[str, KernelRegistration]:
        return self._registrations

    @property
    def library(self) -> Library:
        return self._library

    @property
    def implementations(self) -> Mapping[str, Callable[..., Mapping[str, Any]]]:
        return self._implementations


class _FrozenDict(dict):
    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("registry values are immutable")

    __setitem__ = __delitem__ = __ior__ = clear = pop = popitem = setdefault = update = _immutable


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _FrozenDict({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


__all__ = [
    "DependencyBoundary",
    "KernelRegistration",
    "PlatformRegistry",
    "registered_kernel",
]
