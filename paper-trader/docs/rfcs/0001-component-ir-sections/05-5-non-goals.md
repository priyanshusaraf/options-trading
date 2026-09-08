Reference: [section index](../0001-component-ir.md). Read with its scope; this is not a new assignment.

## 5. Non-goals

Each is excluded deliberately, with its reason.

1. **No runtime or execution mechanism.** §4 states properties; how they are achieved belongs to
   the runtime's own RFC.
2. **No migration machinery.** The preconditions are adopted now — F1's version stamp and F2's
   stable identifiers. The machinery waits for the first real migration, because building rewrite
   infrastructure before there is anything to rewrite is speculative.
3. **No marketplace trust or sandboxing model.** Sandboxing constrains what a component *kernel*
   may do. That is a property of the kernel registry, not of the graph language.
4. **No editor or UI concepts.** A different plane (§1.2).
5. **No search or optimisation strategy.** A different plane; C14 makes the boundary normative.
6. **Forward compatibility is explicitly declined.** Backward compatibility is adopted: newer
   readers MUST carry older artefacts forward. Forward compatibility — an older reader
   interpreting a newer artefact — is **not** promised. Blender accepts that constraint because an
   old binary must open a new file; that is not our situation, and assuming otherwise would
   constrain the format permanently for no benefit.
7. **No tick-level or intrabar semantics.** C10 and C11 rest on this platform acting on completed
   candles only. `~/dev/multiverse-of-ideas/reviews/nautilus-trader.md` §10 is the recorded trigger
   to revisit if that ever changes.

---

## 6. Amendment procedure

### 6.1 Change classes

**Erratum** — corrects wording without changing any conforming artefact or implementation. No
`format_version` increment.

**Non-breaking amendment** — adds an optional construct, or a clause no existing artefact
violates. `format_version` increments; older artefacts remain readable unchanged.

**Breaking amendment** — changes or removes an existing construct, or adds a required one.
`format_version` increments **and** a migration pass MUST ship with it. Per §5(6), no forward
compatibility is promised: a reader of an older `format_version` MUST reject a newer artefact
rather than guess at it.

### 6.2 Process

> Every new platform capability MUST either fit inside this IR unchanged, or be accompanied by an
> RFC that amends it. There is no third path. A capability that quietly extends the language
> without an amendment is architectural drift, and this section exists to make that
> distinguishable from ordinary work rather than to forbid it in spirit only.

An amendment is accepted by the owner. An amendment MUST pass the same expressiveness gate this
document passed: every example in Appendix A MUST be re-expressed under the amended language, and
a failure to express any of them is a defect in the amendment.

### 6.3 Errata

**E1 — 2026-08-02. An override MAY be a parameter reference.** No `format_version` change.

Appendix A.2 writes `override length ← length`: the ATR component forwards its own `length`
parameter into the `n_smooth` node inside its body. Building the resolver found that the §3
validator rejected it, because it enforced F10 as *no mapping may be an override value* rather
than as what F10 says — no **kind**, no **bounds**, no **display name**. A parameter reference
carries none of those three, and the format already contains a reference-valued override: F6
makes a secret's value one.

This is an erratum and not an amendment because no conforming artefact changes meaning and no
new construct is added — `{"param_ref": "length"}` was already a value the grammar's
`override = parameter-identifier , value` admitted; the validator was narrower than the clause.
The accepted forms are now a closed set (`schema.VALUE_REFERENCE_FORMS`), so "any mapping" is
still refused. Without it, A.2 — the acceptance-set artefact that exists to prove
decomposability — is inexpressible, and no component whose body is a graph can forward a
parameter into it.

**Two resolution conventions were added without touching §3, deliberately.** They are recorded
here because a reader of the format will otherwise wonder where they live.

- *Boundary nodes.* A body graph says which internal node an interface socket attaches to by
  referencing two reserved component identifiers, `graph.input` and `graph.output`. Resolution
  elides them and splices the connection through. A reserved identifier is a **value**, not a
  grammar construct, so §3 stays the size it was and no migration pass is owed. Blender,
  Node-RED and ComfyUI all converged on this shape.
- *Kernel declarations.* C8's cache identity, C9's purity policy and C10's warmup are declared by
  the **kernel registry** (`app/ir/kernels.py`), keyed by content address — not by the artefact.
  §2 already defines a kernel as "supplied by a registry". Serialising them would have bought
  nothing and cost a rewrite pass forever.

---

## Appendix A — Worked examples (informative)

These five artefacts are the **acceptance set**. A failure to express any one of them is a defect
in this RFC, not in the example. Each uses real parameters from the running system, not plausible
ones.

### A.1 The EMA-z strategy (`expanding_z_v4`)

Expressed as a `graph-def` whose interface declares the strategy's fifteen real parameters, and
whose nodes reference indicator and predicate components. Abbreviated to its shape:

```
graph-def
  identifier    "strategy.expanding_z_impulse"
  version       4
  display-name  "Expanding Z Impulse V4"
  interface
    panel "trend"      → parameter ema_length      length  default 50
                       → parameter slope_lookback  length  default 5
    panel "zscore"     → parameter z_length        length  default 50
                       → parameter adapt_length    length  default 200
                       → parameter entry_pct       pct     default 65.0
                       → parameter exit_pct        pct     default 35.0
                       → parameter min_abs_z       thr     default 0.60
    panel "volatility" → parameter atr_length      length  default 14
                       → parameter min_drift_atr   mult    default 0.08
                       → parameter max_signal_atr  mult    default 2.75
    panel "behaviour"  → parameter require_expansion         bool default true
                       → parameter allow_reexpansion         bool default true
                       → parameter use_absz_contraction_exit bool default false
                       → parameter exit_on_drift_flip        bool default true
                       → parameter exit_on_ema_cross         bool default true
    socket longEntry   output  wire-type(bool, series, (instrument, timeframe))
    socket shortEntry  output  wire-type(bool, series, (instrument, timeframe))
    socket longExit    output  wire-type(bool, series, (instrument, timeframe))
    socket shortExit   output  wire-type(bool, series, (instrument, timeframe))
  node  n_ema   → component-ref (indicator.ema, 1)     override length ← ema_length
  node  n_z     → component-ref (indicator.zscore, 1)  override length ← z_length
  ...
  edge  (n_ema.out) → (n_z.reference)
```

**Red state recorded and resolved.** The first attempt failed: the grammar's `kind` list omitted
`bool`, and five of this strategy's fifteen parameters are booleans (`require_expansion`,
`allow_reexpansion`, `use_absz_contraction_exit`, `exit_on_drift_flip`, `exit_on_ema_cross`). The
real `KINDS` tuple in the running system already carries it. Resolved by adding `"bool"` to F5's
vocabulary — a grammar correction, not a new clause, and therefore no new migration liability.

**Observation, not a defect.** The four canonical output sockets are exactly the four boolean
columns the current engine contract mandates. The IR expresses them as ordinary typed output
sockets, which means the four-column contract becomes a convention of one component family rather
than a property of the language. That is the intended direction and requires no clause.

### A.2 A decomposed ATR indicator

```
component-def
  identifier    "indicator.atr.wilder"
  version       1
  display-name  "ATR (Wilder)"
  interface
    socket    high    input  wire-type(float, series, (instrument, timeframe))
    socket    low     input  wire-type(float, series, (instrument, timeframe))
    socket    close   input  wire-type(float, series, (instrument, timeframe))
    parameter length  length default 14
    socket    atr     output wire-type(float, series, (instrument, timeframe))
  body graph-ref →
        node n_tr     → component-ref (indicator.true_range, 1)
        node n_smooth → component-ref (smoothing.wilder, 1)  override length ← length
        edge (n_tr.out) → (n_smooth.in)
```

**This is the example the acceptance set exists for.** Because the body is a graph rather than a
kernel, "fork ATR, replace the smoothing" is a new version of `indicator.atr.wilder` whose
`n_smooth` node references `smoothing.ema` instead — expressible as a component reference change,
with F3 recording the parent.

**Red state recorded — a defect in the current system, not in the RFC.** The running block library
has no ATR *component* at all. Wilder's ATR is a private helper (`_atr`), and every public block
returns `Series[bool]`: ATR appears only inside boolean predicates such as `atr_pct_lt(length,
max_pct)` and `range_atr_lt(length, mult)`. There is no float-valued output anywhere in the
vocabulary, so a value like ATR cannot be named, shared, or forked today. The IR expresses this
artefact without amendment — F7's value axis already admits float-valued series. **The gap is in
`blocks.py`, which is precisely the Generation-2 failure C15 exists to close.** No clause was
added.

### A.3 A generated strategy from the block grammar

A generated strategy composes named blocks with bounded numeric arguments. Each block becomes a
`component-ref` with overrides; the composition becomes edges:

```
graph-def
  identifier   "generated.<content-hash>"
  version      1
  node n_1 → component-ref (block.atr_pct_lt, 1)    override length ← 14, max_pct ← 3.0
  node n_2 → component-ref (block.range_atr_lt, 1)  override length ← 14, mult   ← 0.8
  node n_3 → component-ref (logic.and, 1)
  edge (n_1.out) → (n_3.a)
  edge (n_2.out) → (n_3.b)
```

**Observation.** Each block's `BlockSpec` already declares `(param_name, kind)` pairs drawn from
the same bounded vocabulary as F5 — `length`, `pct`, `mult`. The block registry is therefore
already most of a component interface; what it lacks is F2's version and F4's declared panels.

**Red state recorded and resolved without a clause.** Generated strategies currently identify
themselves by a content hash over their source. Under F2 that is the *body's* content address, not
the identity: identity is `(identifier, version)`. Expressible as written above — the hash becomes
the identifier's suffix and the version starts at 1. This is the concrete case D-disproof (d) in
the findings warned about: identity MUST NOT be the definition, because reformatting would
otherwise be a semantic change.
