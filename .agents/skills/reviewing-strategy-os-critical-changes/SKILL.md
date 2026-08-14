---
name: reviewing-strategy-os-critical-changes
description: "Independently review critical-risk Strategy OS changes affecting money, authority, research integrity, tenancy, providers, migrations, runtime, performance, or operator UI. Use after implementation when the change reaches one of these risk boundaries."
---

# Review critical Strategy OS changes

Review the diff and its evidence; do not implement the reviewed change. This review is required for critical-risk changes, not every slice.

1. Identify the risk boundary and load its reference. State `CLEAN`, `AT RISK`, or `VIOLATED` with concrete file and line evidence.
2. Test the claimed evidence: look for a guard that cannot fail, an incomplete reproduction, a mismatch between runtime behavior and a test double, or a check that proves the wrong thing.
3. Check that the selected verification tier matches the blast radius and that observable behavior was actually exercised where needed.
4. Identify owner gates reached or approached. A green test does not discharge an owner gate.
5. Return a plain `PASS`, `FAIL`, or `UNVERIFIABLE`, plus findings, smallest corrective actions, remaining risks, and deferred work.

Load only the relevant reference:

- [Money and authority review](references/money-and-authority.md)
- [Research, provider, tenancy, migration, and performance review](references/domain-review.md)
- [Runtime and UI review](references/runtime-and-ui.md)

## Programme phase and release gates

When all declared slices for a phase or release are integrated, the gate is one fresh Sol-high durable review goal. Product code is read-only: write only the verdict and the minimal programme transition.

Return two independent verdicts, each `PASS`, `FAIL`, or `UNVERIFIABLE`:

- `SPEC` — the integrated result satisfies the capsule and mapped owner steers.
- `QUALITY` — the implementation and current evidence are safe, maintainable, non-vacuous, and proportionate to risk.

Both must pass before the next phase starts. On any other result, leave the next phase blocked and record a bounded Terra correction state. One recheck is allowed; a second rejection requires replanning.
