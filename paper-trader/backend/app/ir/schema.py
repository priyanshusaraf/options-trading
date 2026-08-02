"""
RFC 0001 §3 — the Format, as data.

This module holds only the closed vocabularies and structural shapes the RFC's
EBNF fixes. It is deliberately declarative: `validate.py` reads these tables and
does not hard-code a vocabulary of its own, so widening the language is an edit
here and nowhere else.

Everything in this file is a permanent migration liability — that is what §3
*means*. A name added here is a name some future rewrite pass carries forward
forever. Blender carries 44,246 lines of such passes. Add nothing casually.
"""
from __future__ import annotations

# ── F1 — envelope ─────────────────────────────────────────────────────────

SUPPORTED_FORMAT_VERSION = 1

ARTEFACT_KINDS = ("component", "graph")


# ── F5 — parameter kinds (closed) ─────────────────────────────────────────
#
# The kind is not redundant with the value's type: "it is a float" does not tell
# a consumer whether 0.8 means 80% or 0.8 ATR. `bool` is present because five of
# expanding_z_v4's fifteen real parameters are booleans (Appendix A.1).

KINDS = (
    "length",
    "thr",
    "pct",
    "mult",
    "choice",
    "minute",
    "bool",
    "secret",
)


# ── F7 — wire types: value × structure × domain ───────────────────────────
#
# "The set of value types MUST be closed, versioned, and exact-matched. There
# MUST NOT be a wildcard type, overlap matching, or coercion by string
# comparison." ComfyUI's ecosystem froze around the opposite choice.

VALUE_TYPES = ("float", "int", "bool")

STRUCTURE_TYPES = ("scalar", "series", "auto")

DOMAIN_AXES = ("instrument", "timeframe")

SOCKET_DIRECTIONS = ("input", "output")


# ── F2 — content addressing ───────────────────────────────────────────────
#
# The body is "stored once and content-addressed". A ref that is a filename or a
# key is a name, not an address, and does not satisfy F2.

CONTENT_ADDRESS_PREFIX = "sha256:"
CONTENT_ADDRESS_HEX_LEN = 64

BODY_KINDS = ("kernel", "graph")


# ── The grammar's key sets ────────────────────────────────────────────────
#
# Membership is exhaustive on purpose. F13 requires that presentation state live
# *beside* the graph rather than inside it, and the enforcement mechanism for
# that is simply: the grammar has no place to put a coordinate. Any key not
# listed here is rejected, which catches `position` and `viewport` without
# enumerating every cosmetic key someone might invent.

ENVELOPE_KEYS = frozenset({"format_version", "kind"})

COMPONENT_KEYS = ENVELOPE_KEYS | frozenset({
    "identifier", "version", "parent_version", "display_name", "interface", "body",
})

GRAPH_KEYS = ENVELOPE_KEYS | frozenset({
    "identifier", "version", "parent_version", "display_name", "interface",
    "nodes", "edges", "groups",
})

PANEL_KEYS = frozenset({"item", "identifier", "display_name", "items"})

SOCKET_KEYS = frozenset({
    "item", "identifier", "display_name", "direction", "wire_type", "default_source",
})

PARAMETER_KEYS = frozenset({
    "item", "identifier", "display_name", "kind", "bounds", "default",
})

INTERFACE_ITEMS = {
    "panel": PANEL_KEYS,
    "socket": SOCKET_KEYS,
    "parameter": PARAMETER_KEYS,
}

# `secret_params` names which of a node's overrides target `secret`-kind
# parameters. It is on the node because a graph is validated without its
# component library; with a library, F6 is checked against the real interface.
NODE_KEYS = frozenset({"instance_id", "component", "overrides", "domain", "secret_params"})

COMPONENT_REF_KEYS = frozenset({"identifier", "version"})

EDGE_KEYS = frozenset({"source", "target"})

SOCKET_REF_KEYS = frozenset({"instance", "socket"})

GROUP_KEYS = frozenset({"identifier", "display_name", "members"})

BODY_KEYS = frozenset({"body", "ref"})

WIRE_TYPE_KEYS = frozenset({"value", "structure", "domain"})


def is_content_address(ref: object) -> bool:
    """F2 — a body ref must be a content address, not a name."""
    if not isinstance(ref, str) or not ref.startswith(CONTENT_ADDRESS_PREFIX):
        return False
    digest = ref[len(CONTENT_ADDRESS_PREFIX):]
    return len(digest) == CONTENT_ADDRESS_HEX_LEN and all(
        c in "0123456789abcdef" for c in digest
    )


def is_secret_reference(value: object) -> bool:
    """F6 — a secret's value is a reference. A literal never conforms."""
    return isinstance(value, dict) and set(value) == {"secret_ref"} and isinstance(
        value["secret_ref"], str
    ) and bool(value["secret_ref"])


def is_parameter_reference(value: object) -> bool:
    """An override that binds to an enclosing component's parameter.

    Appendix A.2 writes this as `override length ← length`: the ATR component
    passes its own `length` down to the smoothing node inside its body. Without
    it, a component whose body is a graph cannot forward a single parameter, and
    A.2 — the acceptance-set artefact that exists to prove decomposability — is
    inexpressible.

    This is a *reference*, exactly as F6 makes a secret's value a reference, and
    it carries no kind, no bounds and no display name. F10 forbids those three
    things; it does not forbid references, and the precedent is already in the
    format. Recorded as an erratum to RFC 0001 rather than an amendment: no
    conforming artefact changes meaning and `format_version` does not move.
    """
    return isinstance(value, dict) and set(value) == {"param_ref"} and isinstance(
        value["param_ref"], str
    ) and bool(value["param_ref"])


VALUE_REFERENCE_FORMS = (is_secret_reference, is_parameter_reference)


def is_value_reference(value: object) -> bool:
    """True for every reference form an override may legitimately carry."""
    return any(form(value) for form in VALUE_REFERENCE_FORMS)
