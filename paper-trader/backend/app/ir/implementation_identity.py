"""Closed, transitive identities for executable Component IR implementations."""
from __future__ import annotations

import dataclasses
import dis
import ast
import functools
import hashlib
import importlib.metadata
import inspect
import pathlib
import sys
import textwrap
import types
from collections.abc import Mapping
from typing import Any

from app.ir.hashing import canonical_json

IDENTITY_SCHEME = "ir-kernel-implementation/1"
_BOUNDARY_MODES = frozenset({"declared_objects", "defining_module"})
_DYNAMIC_GLOBALS = frozenset({"eval", "exec", "globals", "locals", "__import__"})


class ImplementationUnidentified(ValueError):
    """An implementation whose complete executable dependency set is unknown."""


def implementation_address(
    implementation: object,
    boundary: object,
    recursive_state: object | None = None,
) -> str:
    """Return a canonical address after proving the dependency boundary is exact."""
    mode = getattr(boundary, "mode", None)
    declared = tuple(getattr(boundary, "objects", ()))
    if mode not in _BOUNDARY_MODES:
        raise ImplementationUnidentified(f"unsupported dependency boundary {mode!r}")
    if len({id(value) for value in declared}) != len(declared):
        raise ImplementationUnidentified("dependency declarations contain duplicates")

    builder = _IdentityBuilder(mode=mode, declared=declared, implementation=implementation)
    payload: dict[str, Any] = {
        "scheme": IDENTITY_SCHEME,
        "boundary": mode,
        "implementation": builder.root(implementation, "implementation"),
        "recursive_state": builder.recursive_state(recursive_state),
    }
    if mode == "defining_module":
        payload["defining_module"] = builder.defining_module_identity()
    builder.require_exact_declarations()
    payload["dependencies"] = sorted(
        builder.dependency_identities, key=canonical_json
    )
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


class _IdentityBuilder:
    def __init__(self, *, mode: str, declared: tuple[object, ...], implementation: object):
        self.mode = mode
        self.declared = declared
        self._declared_by_id = {id(value): value for value in declared}
        self._required_ids: set[int] = set()
        self._active: set[int] = set()
        self._memo: dict[int, Mapping[str, Any]] = {}
        self.dependency_identities: list[Mapping[str, Any]] = []
        self._module = inspect.getmodule(implementation)
        self._module_name = getattr(self._module, "__name__", None)
        if mode == "defining_module" and self._module is None:
            raise ImplementationUnidentified("defining_module requires a defining module")

    def root(self, value: object, path: str) -> Mapping[str, Any]:
        return self._object(
            value, path,
            require_declaration=self.mode == "declared_objects"
            and path.startswith("recursive_state."),
        )

    def recursive_state(self, state: object | None) -> object:
        if state is None:
            return None
        fields = ("initializer", "state_type", "state_encoder", "update", "step")
        missing = [name for name in fields if not hasattr(state, name)]
        if missing:
            raise ImplementationUnidentified(
                f"recursive state is missing identity fields {missing}"
            )
        return {
            name: self.root(getattr(state, name), f"recursive_state.{name}")
            for name in fields
        }

    def defining_module_identity(self) -> Mapping[str, Any]:
        assert self._module is not None
        path = _module_file(self._module)
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ImplementationUnidentified(
                f"defining module {self._module_name!r} has no readable complete file"
            ) from exc
        return {
            "kind": "defining_module",
            "name": self._module_name,
            "file_sha256": hashlib.sha256(data).hexdigest(),
        }

    def require_exact_declarations(self) -> None:
        declared_ids = set(self._declared_by_id)
        missing = self._required_ids - declared_ids
        extra = declared_ids - self._required_ids
        if missing:
            names = sorted(_object_label(self._memo.get(item) or self._declared_by_id.get(item))
                           for item in missing)
            raise ImplementationUnidentified(f"undeclared dependencies: {names}")
        if extra:
            names = sorted(_object_label(self._declared_by_id[item]) for item in extra)
            raise ImplementationUnidentified(f"extra dependency declarations: {names}")

    def _object(
        self, value: object, path: str, *, require_declaration: bool
    ) -> Mapping[str, Any]:
        if inspect.ismodule(value) or inspect.isfunction(value) or inspect.isclass(value):
            internal = self.mode == "defining_module" and _defined_in(value, self._module_name)
            if require_declaration and not internal:
                self._required_ids.add(id(value))

            marker = id(value)
            if marker in self._memo:
                return self._memo[marker]
            if marker in self._active:
                return {"kind": "recursive_reference", "name": _qualified_name(value)}
            self._active.add(marker)
            try:
                if inspect.ismodule(value):
                    identity = _module_identity(value)
                elif inspect.isfunction(value):
                    identity = self._function(value, path, module_local=internal)
                else:
                    identity = self._class(value, path, module_local=internal)
            finally:
                self._active.remove(marker)
            self._memo[marker] = identity
            if require_declaration and not internal:
                self.dependency_identities.append(identity)
            return identity
        raise ImplementationUnidentified(
            f"{path} has unsupported executable identity {type(value).__name__}"
        )

    def _function(
        self, fn: types.FunctionType, path: str, *, module_local: bool
    ) -> Mapping[str, Any]:
        instructions, source, closure = _reject_dynamic_code(fn)
        if self.mode == "defining_module" and fn.__closure__:
            raise ImplementationUnidentified(
                f"{path} uses closures under defining_module"
            )
        source, closure = _complete_function_observations(fn, path, source, closure)
        loaded_globals = {
            instruction.argval for instruction in instructions
            if instruction.opname in {"LOAD_GLOBAL", "LOAD_NAME"}
        }
        unresolved_globals = set(closure.unbound) & loaded_globals
        if unresolved_globals:
            raise ImplementationUnidentified(
                f"{path} has unresolved globals {sorted(unresolved_globals)}"
            )
        dependencies: dict[str, Any] = {}
        for name, value in sorted({**closure.globals, **closure.nonlocals}.items()):
            dependencies[name] = self._value(value, f"{path}.{name}")

        return {
            "kind": "module_function" if module_local else "function",
            "qualname": fn.__qualname__,
            "source": source,
            "defaults": self._value(fn.__defaults__, f"{path}.__defaults__"),
            "kwdefaults": self._value(fn.__kwdefaults__, f"{path}.__kwdefaults__"),
            "annotations": self._value(fn.__annotations__, f"{path}.__annotations__"),
            "dependencies": dependencies,
        }

    def _class(self, cls: type, path: str, *, module_local: bool) -> Mapping[str, Any]:
        try:
            source = textwrap.dedent(inspect.getsource(cls))
        except (OSError, TypeError) as exc:
            raise ImplementationUnidentified(
                f"{path} class has no readable source; names are not identities"
            ) from exc
        source_file = inspect.getsourcefile(cls)
        methods: dict[str, Any] = {}
        for name, member in sorted(vars(cls).items()):
            raw = member.__func__ if isinstance(member, (staticmethod, classmethod)) else member
            if not inspect.isfunction(raw) or not source_file:
                continue
            try:
                same_file = pathlib.Path(raw.__code__.co_filename).resolve() == \
                    pathlib.Path(source_file).resolve()
            except OSError:
                same_file = False
            if same_file:
                methods[name] = self._function(
                    raw, f"{path}.{name}", module_local=module_local)
        return {
            "kind": "module_class" if module_local else "class",
            "qualname": cls.__qualname__,
            "source": source,
            "methods": methods,
        }

    def _value(self, value: object, path: str) -> Any:
        if value is None or isinstance(value, (str, int, bool)):
            return value
        if isinstance(value, float):
            if value != value or value in (float("inf"), float("-inf")):
                raise ImplementationUnidentified(f"{path} contains non-finite float")
            return value
        if isinstance(value, bytes):
            return {"bytes_sha256": hashlib.sha256(value).hexdigest()}
        if isinstance(value, tuple):
            return [self._value(item, f"{path}[{index}]")
                    for index, item in enumerate(value)]
        if isinstance(value, frozenset):
            return {"frozenset": sorted(
                (self._value(item, f"{path}[]") for item in value), key=canonical_json
            )}
        if isinstance(value, Mapping):
            if not all(isinstance(key, str) for key in value):
                raise ImplementationUnidentified(f"{path} mapping keys must be strings")
            return {key: self._value(item, f"{path}.{key}")
                    for key, item in sorted(value.items())}
        if inspect.ismodule(value) or inspect.isfunction(value) or inspect.isclass(value):
            return self._object(value, path, require_declaration=True)
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            raise ImplementationUnidentified(
                f"{path} closes over mutable declared state; bind its immutable fields directly"
            )
        raise ImplementationUnidentified(
            f"{path} has unsupported closure value {type(value).__name__}"
        )


def _complete_function_observations(fn, path, source, closure):
    # Preserve the prior source-error fallback after the defining-module guard.
    if source is None:
        try:
            source = textwrap.dedent(inspect.getsource(fn))
        except (OSError, TypeError) as exc:
            raise ImplementationUnidentified(
                f"{path} has no readable source; repr and names are not identities"
            ) from exc
    if closure is None:
        closure = inspect.getclosurevars(fn)
    return source, closure


def _dynamic_attribute_target(node):
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return None
    if node.func.id != "getattr" or not node.args:
        return None
    if not isinstance(node.args[0], ast.Name):
        return None
    if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) \
            and isinstance(node.args[1].value, str):
        return None
    return node.args[0].id


def _reject_dynamic_attributes(fn, tree, closure):
    module_bindings = {
        name for name, value in {**closure.globals, **closure.nonlocals}.items()
        if inspect.ismodule(value)
    }
    for node in ast.walk(tree):
        if _dynamic_attribute_target(node) in module_bindings:
            raise ImplementationUnidentified(
                f"{fn.__qualname__} performs dynamic attribute lookup"
            )


def _reject_dynamic_code(fn: types.FunctionType):
    """Return fresh per-visit observations after the existing dynamic-code guards."""
    instructions = tuple(dis.get_instructions(fn))
    for instruction in instructions:
        if instruction.opname in {"IMPORT_NAME", "IMPORT_FROM"}:
            raise ImplementationUnidentified(
                f"{fn.__qualname__} performs a runtime import"
            )
        if instruction.opname in {"LOAD_GLOBAL", "LOAD_NAME"} \
                and instruction.argval in _DYNAMIC_GLOBALS:
            raise ImplementationUnidentified(
                f"{fn.__qualname__} performs dynamic global lookup via {instruction.argval}"
            )
    try:
        source = textwrap.dedent(inspect.getsource(fn))
        tree = ast.parse(source)
    except (OSError, TypeError, SyntaxError):
        return instructions, None, None
    closure = inspect.getclosurevars(fn)
    _reject_dynamic_attributes(fn, tree, closure)
    return instructions, source, closure


def _defined_in(value: object, module_name: str | None) -> bool:
    return module_name is not None and getattr(value, "__module__", None) == module_name


def _qualified_name(value: object) -> str:
    return f"{getattr(value, '__module__', '')}.{getattr(value, '__qualname__', '')}"


def _module_file(module: types.ModuleType) -> pathlib.Path:
    filename = getattr(module, "__file__", None)
    if not filename:
        raise ImplementationUnidentified(
            f"module {module.__name__!r} has no file identity"
        )
    path = pathlib.Path(filename)
    if path.suffix in {".pyc", ".pyo"} and path.with_suffix(".py").exists():
        path = path.with_suffix(".py")
    return path.resolve()


@functools.cache
def _distribution_packages() -> Mapping[str, tuple[str, ...]]:
    """Freeze the process's installed-package ownership map for identity reads.

    Package discovery walks every installed distribution's metadata. The installed
    environment is immutable for a running process, whereas implementation identity
    must remain repeatable within that process, so discovering it for every recursive
    module identity is needless bootstrap work. Versions are still looked up for every
    identity payload and remain part of the content-addressed bytes.
    """
    return types.MappingProxyType({
        package: tuple(sorted(distributions))
        for package, distributions in importlib.metadata.packages_distributions().items()
    })


def _module_identity(module: types.ModuleType) -> Mapping[str, Any]:
    path = _module_file(module)
    top_level = module.__name__.split(".", 1)[0]
    distributions = _distribution_packages().get(top_level, ())
    if distributions:
        names = sorted(distributions)
        return {
            "kind": "distribution_module",
            "module": module.__name__,
            "distributions": [
                {"name": name, "version": importlib.metadata.version(name)}
                for name in names
            ],
            "path": "/".join(module.__name__.split(".")),
        }
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ImplementationUnidentified(
            f"module {module.__name__!r} has no readable identity"
        ) from exc
    return {
        "kind": "stdlib_or_application_module",
        "module": module.__name__,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "file_sha256": hashlib.sha256(data).hexdigest(),
    }


def _object_label(value: object) -> str:
    if isinstance(value, Mapping):
        return str(value.get("qualname") or value.get("module") or value.get("kind"))
    return _qualified_name(value) or type(value).__name__


__all__ = [
    "IDENTITY_SCHEME",
    "ImplementationUnidentified",
    "implementation_address",
]
