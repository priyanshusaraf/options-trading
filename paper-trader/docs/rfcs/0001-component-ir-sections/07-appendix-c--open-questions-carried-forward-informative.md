Reference: [section index](../0001-component-ir.md). Read with its scope; this is not a new assignment.

## Appendix C — Open questions carried forward (informative)

These are carried **inside** the constitution deliberately. A frozen architecture that hides its
own soft spots is how drift begins. Each names the trigger that would reopen it.

### C(a) Fork semantics beyond a parent pointer

No system studied has a real fork relation — Langflow makes every graph a fork, the rest have
none. The parent-pointer model in F3 is therefore *derived* rather than *observed*.
**Trigger:** the first request for merge, rebase, or divergence display. Additive metadata on a
version record; not a change to how graphs reference components.

### C(b) Field and structure inference rules in our domain

Blender's `Auto` inference proves inference works, but their rules concern geometry domains, not
bars and instruments. Ours must be derived from our own semantics. F7 freezes the two-axis
**shape**; the inference algorithm sits above the format.
**Trigger:** the first component that cannot declare its structure.

### C(c) Migration machinery

The preconditions (F1, F2) are adopted; the machinery is deferred.
**Trigger:** the first breaking amendment.

### C(d) Whether and when the live engine executes IR graphs

C12 says it eventually must. That is a production change to a real-money path and needs its own
phase with its own parity evidence, in the compile-first / adopt-second order this platform already
uses for the decision kernel and the strategy specification. **This is a migration question, not a
language question.**
**Trigger:** its own phase.

### C(e) Tick-level and intrabar strategies

C10 and C11 rest on this platform acting on completed candles only.
**Trigger:** any intrabar strategy. `~/dev/multiverse-of-ideas/reviews/nautilus-trader.md` §10 is
the note to whoever revisits it.

### C(f) Marketplace trust and sandboxing at scale

The existing AST allow-list is stronger than anything in the nine systems studied — none of them
sandbox user code at all. Sandboxing constrains what a *kernel* may do, which is a property of the
kernel registry rather than of the graph language.
**Trigger:** third-party component distribution.
