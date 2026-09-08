Reference: [section index](../DEFECT_PATTERNS.md). Read with its scope; this is not a new assignment.

## DP-017 — Producer-selected executable subset mistaken for complete dependency proof

- Severity: Critical when executable closure supports migration, persistence,
  research integrity, deployment, phase acceptance, or any authority claim.
- Status: CONTAINED/BLOCKED. Recovery 9 is frozen and root-rejected. Product,
  test, PostgreSQL, migration, runtime, deployment, live, order, and money bytes
  remain unchanged. A new named dependency-proof recovery lineage, not Recovery
  10, must pass a root-owned current-member oracle before another package can be
  accepted.
- Incident: Recovery 9 sealed `ast-proof-table.json` with `complete=true`, but
  the table contained four script rows while the package contained seven Python
  members. It omitted the chronology validator and both relocated harness
  copies. It also recorded only the first alias from grouped `import` statements,
  omitting eight imports from `final_validate.py` and six from `seal.py`, and it
  omitted the sealer's subprocess edge to `final_validate.py`.
- Root cause: the builder hard-coded a producer-selected four-script subset,
  reduced every `ast.Import` node to `node.names[0]`, marked every call target
  resolved without independently deriving its origin, and declared only one
  approved subprocess edge. The final validator reproduced that same extraction
  algorithm, so equality proved shared implementation behavior rather than
  completeness.
- Violated invariant: executable proof must derive the complete script universe
  from current package members, enumerate every import alias, bind every local
  dependency and subprocess callee to current bytes, classify every call origin,
  and reject any omitted, extra, stale, unresolved, dynamic, reflective, or
  unsafe member. A producer and validator may not share the authority-selection
  error they claim to detect.
- Why prior evidence missed it: the proof generator and final validator used the
  same hard-coded script list and first-alias extraction. The sealed PASS was
  syntactically self-consistent and therefore unable to reveal its own omitted
  universe.
- False assumption: a proof becomes complete because every producer-selected row
  reproduces and every call row carries `resolved=true`.
- Prevention invariant: a root-owned oracle walks every current regular Python
  member recursively, expands every import alias, derives exact local dependencies
  and call origins, enumerates every subprocess site, binds each direct literal
  callee to a current script hash, and rejects dynamic imports, reflection,
  bytecode, symlinks, special files, unresolved origins, and subset proofs.
- Permanent regressions: accept one complete baseline, then reject an omitted
  script row, extra row, stale script hash, omitted grouped-import alias, omitted
  local dependency, forged call origin, omitted subprocess edge, wrong subprocess
  callee, dynamic import, reflection, and false completeness claim. Each future
  package must also replay the four exact Recovery 9 diagnostics and prove the
  root oracle is immutable and external to the package owner.
- Adversarial generalization: search copied and relocated executables, chronology
  and auxiliary validators, builders and sealers, grouped imports, aliased
  subprocess calls, generated scripts, nested packages, dynamic import seams,
  reflection, and any proof whose universe is a literal list instead of a current
  member walk.
- Transitive evidence map: executable dependency authority -> database-free
  trigger-fixture package -> semantic package and complete PostgreSQL evidence ->
  native-state and migration evidence -> sandbox and migration/refusal capsules ->
  foundation closure -> Phase 5 handoff. Recovery 9 final validation, seal, owner
  report, and every dependent acceptance claim remain invalidated.
- Owner: root owns
  `.agent/runs/phase1-4-foundation-critical-closure/root/executable-dependency-oracle-contract.json`
  and its validator. One independent Sol Ultra assignment must challenge the
  oracle before the serial Sol Extra High package owner starts. Root alone may
  accept the fresh package.
- Evidence: Recovery 9 root rejection
  `.agent/runs/phase1-4-foundation-critical-closure/postgresql16-semantic-trigger-fixture-contract-evidence-harness-replacement-recovery-9-root-rejection.json`
  SHA-256
  `ed022e5e8010e9d5922bd2868f22f82e3144869ba5e559d00928e2d8370fc0d1`;
  independent audit and recheck SHA-256
  `626f3728a34254e449814471b02a25dde467c53e805718a47c62621780ef4783`;
  root oracle contract, validator, and twelve-test self-test SHA-256
  `eb36d2d4a124727ea5c0b717e406e1749c197601b42251e73230db8b7cc28ef4`,
  `02642674633b4d064c3b5f77e9fb951f87fe7175202a4c6e19171aa6405bed01`,
  and
  `729ed245cd4a44da594c509e100766193299f12945562c8cc838b262fc8cbac2`.

## DP-018 — Enumerated dangerous spellings mistaken for a closed executable authority grammar

- Severity: Critical when an executable proof controls migration, persistence,
  research integrity, deployment, phase acceptance, or authority.
- Status: CONTAINED/BLOCKED. The dependency-proof recovery exhausted its one
  root repair and sole independent recheck. No package owner started. Recovery
  9, oracle v1, and oracle v2 are immutable rejected evidence. Product, test,
  PostgreSQL, migration, runtime, deployment, live, order, and money bytes remain
  unchanged.
- Incident: validation-only oracle v2 closed all eight v1 false accepts and kept
  all nine controls green, but its sole Sol Ultra recheck found four new false
  accepts. `builtins.__import__`, `builtins.eval`, and `builtins.getattr`
  bypassed the forbidden dynamic-import, dynamic-execution, and reflection
  classes because only bare builtin spellings were listed. `subprocess.call`
  launched a process while sitting outside both the four approved subprocess
  origins and the enumerated forbidden process origins.
- Root cause: the oracle used growing allow and deny sets of spellings while its
  contract claimed complete semantic classes. Module qualification, equivalent
  import forms, and an unlisted process API crossed the gaps. The expanded
  self-tests selected known spellings instead of deriving closed origin
  partitions and deny-by-default behavior.
- Violated invariant: Critical executable authority must be expressed as a
  closed grammar. Every import and call origin must belong to one explicitly
  permitted semantic production; all other builtins, modules, dynamic execution,
  reflection, process launch, callable indirection, and unresolved forms reject.
  A blacklist or a partial allowlist cannot establish completeness.
- Why prior evidence missed it: all 24 v2 self-tests exercised the chosen bare
  builtin and process spellings. The independent recheck varied qualification
  and selected a process API outside both sets, proving the partition was open.
- False assumption: enumerating the dangerous names already seen in historical
  failures is equivalent to defining the complete forbidden semantic class.
- Prevention invariant: define a minimal closed import and call grammar for the
  fresh database-free package. Permit only named standard-library imports,
  current hash-bound local modules, named builtins, named receiver methods, and
  four direct-literal subprocess forms. Reject every unlisted origin by default.
  Canonicalize bare, `builtins.*`, and `from builtins import *` forms before
  policy. Treat every process API outside the four exact approved forms as
  forbidden. Do not implement a general Python static analyzer when a smaller
  package language can satisfy the evidence workflow.
- Permanent regressions: all 24 v2 tests, all eight v1 false accepts, all nine v1
  controls, module-qualified and from-builtins forms for import/exec/eval/compile/
  getattr/setattr/delattr/vars, every `subprocess` public launcher, representative
  `os` spawn/exec/posix_spawn, asyncio, multiprocessing, pty, shell and library
  launchers, alias/partial/decorator/factory/container indirection, unknown
  origins, and one novel outside-partition case. A permitted baseline must use
  only the closed grammar and remain independently hand-authored.
- Adversarial generalization: search every security, authority, dependency,
  provider, migration, and deployment proof for open-ended lists presented as
  complete policy. Ask which valid spelling or unlisted member sits outside both
  the allow and deny sets.
- Transitive evidence map: closed executable grammar -> dependency proof -> fresh
  database-free fixture package -> complete PostgreSQL evidence -> sandbox and
  migration/refusal capsules -> foundation closure -> Phase 5 handoff. Every
  package-owner and downstream claim remains blocked.
- Owner: a fresh root task must architecture-replan to the smallest closed
  package grammar. No second repair or recheck may enter the exhausted
  dependency-proof recovery capsule.
- Evidence: v1 independent report SHA-256
  `f323497ead52feb663bd5d8dd2410c4e0506ad178250b1970e3a5d198129e35a`;
  v2 sole-recheck report and matrix SHA-256
  `eea06d5bae4313b8b8cab61100bd019ac05bae6c4d5cd09d5692510c3d0b331f`
  and
  `ec9f5d47ef05085021c58d0fe4f76d672a313ed2d1426404f4cd68ec33c40430`.
