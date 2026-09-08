from __future__ import annotations

import importlib.util
import math
import sys

import pytest

from app.ir.causal import (
    HistoryBound,
    RecursiveStateContract,
    causal_contract,
)
from app.ir.implementation_identity import (
    ImplementationUnidentified,
    implementation_address,
)
from app.ir import implementation_identity
from app.ir.registry import DependencyBoundary, registered_kernel


BODY = "sha256:" + "1" * 64


def _contract():
    return causal_contract(
        node_input_sockets=("close",),
        history=HistoryBound("bounded"),
    )


def _identity(params, node_inputs, context_inputs):
    return {"out": node_inputs["close"]}


def _changed_rma(series, length):
    return series.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean() + 1.0


def test_real_helper_change_changes_transitive_identity():
    def helper_a(value):
        return value + 1

    def helper_b(value):
        return value + 2

    def kernel_a(params, node_inputs, context_inputs):
        return {"out": helper_a(node_inputs["close"])}

    def kernel_b(params, node_inputs, context_inputs):
        return {"out": helper_b(node_inputs["close"])}

    assert implementation_address(
        kernel_a, DependencyBoundary("declared_objects", (helper_a,))
    ) != implementation_address(
        kernel_b, DependencyBoundary("declared_objects", (helper_b,))
    )


def test_undeclared_global_dependency_refuses_registration():
    def helper(value):
        return value + 1

    def kernel(params, node_inputs, context_inputs):
        return {"out": helper(node_inputs["close"])}

    with pytest.raises(ImplementationUnidentified, match="undeclared"):
        registered_kernel(
            body_ref=BODY,
            implementation=kernel,
            causal=_contract(),
            dependency_boundary=DependencyBoundary("declared_objects"),
        )


def test_address_cannot_be_forged():
    with pytest.raises(TypeError):
        registered_kernel(
            body_ref=BODY,
            implementation=_identity,
            causal=_contract(),
            dependency_boundary=DependencyBoundary("declared_objects"),
            implementation_address="sha256:" + "0" * 64,
        )


def test_spec_callable_and_derived_address_travel_in_one_registration():
    registration = registered_kernel(
        body_ref=BODY,
        implementation=_identity,
        causal=_contract(),
        dependency_boundary=DependencyBoundary("declared_objects"),
    )

    assert registration.spec.causal == _contract()
    assert registration.implementation is _identity
    assert registration.implementation_address.startswith("sha256:")


def test_module_dependencies_must_be_declared_exactly():
    def kernel(params, node_inputs, context_inputs):
        return {"out": math.fabs(node_inputs["close"])}

    with pytest.raises(ImplementationUnidentified, match="undeclared"):
        implementation_address(kernel, DependencyBoundary("declared_objects"))

    assert implementation_address(
        kernel, DependencyBoundary("declared_objects", (math,))
    ).startswith("sha256:")

    with pytest.raises(ImplementationUnidentified, match="extra"):
        implementation_address(
            _identity, DependencyBoundary("declared_objects", (math,))
        )


def test_distribution_discovery_is_cached_without_changing_exact_versions(monkeypatch):
    """Recursive identity reads discover installed-package ownership once per process."""
    implementation_identity._distribution_packages.cache_clear()
    calls = []

    def discover_packages():
        calls.append("discovered")
        return {"math": ["identity-probe"]}

    monkeypatch.setattr(implementation_identity.importlib.metadata,
                        "packages_distributions", discover_packages)
    monkeypatch.setattr(implementation_identity.importlib.metadata, "version",
                        lambda name: "7.4.2" if name == "identity-probe" else None)
    try:
        first = implementation_identity._module_identity(math)
        second = implementation_identity._module_identity(math)
    finally:
        implementation_identity._distribution_packages.cache_clear()

    assert calls == ["discovered"]
    assert first == second == {
        "kind": "distribution_module",
        "module": "math",
        "distributions": [{"name": "identity-probe", "version": "7.4.2"}],
        "path": "math",
    }


def test_runtime_import_and_dynamic_module_lookup_refuse():
    def importing(params, node_inputs, context_inputs):
        import math as runtime_math

        return {"out": runtime_math.fabs(node_inputs["close"])}

    def dynamic(params, node_inputs, context_inputs):
        operation = getattr(math, params["operation"])
        return {"out": operation(node_inputs["close"])}

    with pytest.raises(ImplementationUnidentified, match="runtime import"):
        implementation_address(importing, DependencyBoundary("declared_objects"))
    with pytest.raises(ImplementationUnidentified, match="dynamic attribute"):
        implementation_address(
            dynamic, DependencyBoundary("declared_objects", (math,))
        )


def test_dynamic_lookup_refuses_a_module_captured_as_a_nonlocal():
    module = math

    def dynamic(params, node_inputs, context_inputs):
        operation = getattr(module, params["operation"])
        return {"out": operation(node_inputs["close"])}

    with pytest.raises(ImplementationUnidentified, match="dynamic attribute"):
        implementation_address(
            dynamic, DependencyBoundary("declared_objects", (math,))
        )


def test_unsupported_mutable_closure_state_refuses():
    mutable = [1]

    def kernel(params, node_inputs, context_inputs):
        return {"out": node_inputs["close"] + mutable[0]}

    with pytest.raises(ImplementationUnidentified, match="unsupported closure value"):
        implementation_address(kernel, DependencyBoundary("declared_objects"))


def test_recursive_state_functions_and_type_change_identity():
    class StateA:
        pass

    class StateB:
        pass

    def initializer(params):
        return StateA()

    def initializer_b(params):
        return StateB()

    def encoder(state):
        return {}

    def update(state, params, node_inputs, context_inputs):
        return state

    def step(state, params, node_inputs, context_inputs):
        return {"out": node_inputs["close"]}

    first = RecursiveStateContract(initializer, StateA, encoder, update, step)
    second = RecursiveStateContract(initializer_b, StateB, encoder, update, step)
    boundary_a = DependencyBoundary(
        "declared_objects", (initializer, StateA, encoder, update, step))
    boundary_b = DependencyBoundary(
        "declared_objects", (initializer_b, StateB, encoder, update, step))

    assert implementation_address(_identity, boundary_a, first) != \
        implementation_address(_identity, boundary_b, second)


def test_defining_module_hashes_complete_file_bytes(tmp_path):
    module_path = tmp_path / "identity_probe.py"
    module_path.write_text(
        "def kernel(params, node_inputs, context_inputs):\n"
        "    return {'out': node_inputs['close']}\n"
        "\nUNUSED_BUT_DEFINING = 1\n"
    )
    spec = importlib.util.spec_from_file_location("identity_probe", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        first = implementation_address(
            module.kernel, DependencyBoundary("defining_module")
        )
        module_path.write_text(module_path.read_text().replace("= 1", "= 2"))
        second = implementation_address(
            module.kernel, DependencyBoundary("defining_module")
        )
    finally:
        sys.modules.pop(spec.name, None)

    assert first != second


def test_defining_module_rejects_closure_state():
    offset = 1

    def kernel(params, node_inputs, context_inputs):
        return {"out": node_inputs["close"] + offset}

    with pytest.raises(ImplementationUnidentified, match="closures"):
        implementation_address(kernel, DependencyBoundary("defining_module"))


def test_recursive_state_class_method_helper_is_transitively_identified(tmp_path):
    module_path = tmp_path / "state_method_probe.py"
    module_path.write_text(
        "class State:\n"
        "    def signal(self):\n"
        "        return helper()\n"
        "\n"
        "def helper():\n"
        "    return 1\n"
        "\n"
        "def helper_v2():\n"
        "    return 2\n"
        "\n"
        "def initializer(params):\n"
        "    return State()\n"
        "\n"
        "def encoder(state):\n"
        "    return {}\n"
        "\n"
        "def update(state, params, node_inputs, context_inputs):\n"
        "    return state\n"
        "\n"
        "def step(state, params, node_inputs, context_inputs):\n"
        "    return {'out': state.signal()}\n"
    )
    spec = importlib.util.spec_from_file_location("state_method_probe", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        recursive = RecursiveStateContract(
            module.initializer, module.State, module.encoder, module.update, module.step)
        incomplete = DependencyBoundary(
            "declared_objects",
            (module.initializer, module.State, module.encoder, module.update, module.step),
        )
        with pytest.raises(ImplementationUnidentified, match="undeclared"):
            implementation_address(_identity, incomplete, recursive)

        complete = DependencyBoundary(
            "declared_objects", (*incomplete.objects, module.helper))
        first = implementation_address(_identity, complete, recursive)
        original_helper = module.helper
        module.helper = module.helper_v2
        changed = DependencyBoundary(
            "declared_objects",
            tuple(module.helper_v2 if value is original_helper else value
                  for value in complete.objects),
        )
        second = implementation_address(_identity, changed, recursive)
    finally:
        sys.modules.pop(spec.name, None)

    assert first != second


def test_actual_expanding_z_rma_change_makes_registration_stale(monkeypatch):
    from app.ir.registry import PlatformRegistry
    from app.ir.strategies import expanding_z

    registration = expanding_z.REGISTRATIONS[expanding_z.WILDER["body"]["ref"]]
    original_address = registration.implementation_address
    original_rma = expanding_z._rma
    monkeypatch.setattr(expanding_z, "_rma", _changed_rma)
    changed_boundary = DependencyBoundary(
        registration.dependency_boundary.mode,
        tuple(_changed_rma if value is original_rma else value
              for value in registration.dependency_boundary.objects),
    )
    changed_address = implementation_address(
        registration.implementation,
        changed_boundary,
        registration.spec.causal.recursive_state,
    )

    assert changed_address != original_address
    with pytest.raises(ValueError, match="stale"):
        PlatformRegistry(
            components={(expanding_z.WILDER["identifier"], 1): expanding_z.WILDER},
            bodies={},
            registrations={registration.body_ref: registration},
        )


def test_identity_reuses_each_successful_function_observation_once(monkeypatch):
    calls = {"source": 0, "closure": 0}
    source = implementation_identity.inspect.getsource
    closure = implementation_identity.inspect.getclosurevars
    def observed_source(fn):
        calls["source"] += 1
        return source(fn)
    def observed_closure(fn):
        calls["closure"] += 1
        return closure(fn)
    expected = implementation_address(_identity, DependencyBoundary("declared_objects", ()))
    monkeypatch.setattr(implementation_identity.inspect, "getsource", observed_source)
    monkeypatch.setattr(implementation_identity.inspect, "getclosurevars", observed_closure)
    assert implementation_address(_identity, DependencyBoundary("declared_objects", ())) == expected
    assert calls == {"source": 1, "closure": 1}


def test_new_identity_visit_observes_mapping_and_default_mutations():
    state = {"offset": 1}
    def kernel(params=None, node_inputs=None, context_inputs=None):
        return state["offset"]
    boundary = DependencyBoundary("declared_objects", ())
    first = implementation_address(kernel, boundary)
    state["offset"] = 2
    second = implementation_address(kernel, boundary)
    kernel.__defaults__ = (1, None, None)
    third = implementation_address(kernel, boundary)
    assert len({first, second, third}) == 3
    state["offset"] = 1
    kernel.__defaults__ = (None, None, None)
    assert implementation_address(kernel, boundary) == first


def _identity_replacement(params, node_inputs, context_inputs):
    return {"out": node_inputs["close"] + 1}


def test_new_identity_visit_observes_replaced_code(monkeypatch):
    boundary = DependencyBoundary("declared_objects", ())
    first = implementation_address(_identity, boundary)
    with monkeypatch.context() as change:
        change.setattr(_identity, "__code__", _identity_replacement.__code__)
        assert implementation_address(_identity, boundary) != first
    assert implementation_address(_identity, boundary) == first


def test_constant_module_and_input_attribute_lookups_keep_prior_identity_rules():
    def constant(params, node_inputs, context_inputs):
        operation = getattr(math, "fabs")
        return {"out": operation(node_inputs["close"])}
    def input_attribute(params, node_inputs, context_inputs):
        return {"out": getattr(node_inputs["close"], params["attribute"])}
    assert implementation_address(constant, DependencyBoundary("declared_objects", (math,))).startswith("sha256:")
    assert implementation_address(input_attribute, DependencyBoundary("declared_objects", ())).startswith("sha256:")


def test_unreadable_source_preserves_dynamic_and_defining_module_guard_order():
    namespace = {"__name__": __name__}
    exec(compile(
        "def missing(params, node_inputs, context_inputs):\n    return node_inputs['close']\n"
        "def importing(params, node_inputs, context_inputs):\n    import math\n    return math.pi\n"
        "def outer():\n    value = 1\n    def closed(params, node_inputs, context_inputs):\n        return value\n    return closed\n",
        "<identity-unreadable-source>", "exec"), namespace)
    with pytest.raises(ImplementationUnidentified, match="has no readable source"):
        implementation_address(namespace["missing"], DependencyBoundary("declared_objects", ()))
    with pytest.raises(ImplementationUnidentified, match="performs a runtime import"):
        implementation_address(namespace["importing"], DependencyBoundary("declared_objects", ()))
    with pytest.raises(ImplementationUnidentified, match="uses closures under defining_module"):
        implementation_address(namespace["outer"](), DependencyBoundary("defining_module"))


_IDENTITY_GLOBAL_PROBE = 0


def test_new_identity_visit_observes_reassigned_global(monkeypatch):
    def kernel(params, node_inputs, context_inputs):
        return _IDENTITY_GLOBAL_PROBE
    monkeypatch.setitem(globals(), "_IDENTITY_GLOBAL_PROBE", 1)
    boundary = DependencyBoundary("declared_objects", ())
    first = implementation_address(kernel, boundary)
    monkeypatch.setitem(globals(), "_IDENTITY_GLOBAL_PROBE", 2)
    assert implementation_address(kernel, boundary) != first
