Reference: [section index](../DEFECT_PATTERNS.md). Read with its scope; this is not a new assignment.

## DP-015 — Single-parent traversal and traversal order mistaken for complete canonical ancestry

- Severity: Critical when ancestry supports migration, fixture, ownership,
  lineage, tenancy, deployment, research-integrity, or acceptance evidence.
- Status: CONTAINED/BLOCKED. The bounded correction stopped after its initial
  attempt and sole repair. It changed no product, test, migration, runtime, or
  PostgreSQL state. Root independently reproduced the missing edge and ordering
  drift, accepted only the blocked evidence, and requires fresh Sol-high
  database-free recovery architecture before another implementation attempt.
- Incident: the accepted trigger-fixture universe contains 119 tuples, but the
  correction constructed 118. Its `parents={child: parent}` map retained only
  the last parent for a child. The `research_dataset_manifest_segments_v2`
  fixture row03 has parent edges to row00 and row01, so row03 -> row00 was lost.
  The same implementation emitted depth-first traversal order for ancestry in
  the experiment-spec and optimization-trial fixtures even though the accepted
  authority orders children and ancestors by frozen insertion position.
- Root cause: the implementation modeled a directed acyclic graph as a partial
  function from child to one parent, then treated an implementation traversal
  sequence as semantic order. It did not freeze adjacency multiplicity,
  cycle/duplicate-edge rules, transitive-closure semantics, or a canonical
  output order independent of traversal strategy.
- Violated invariant: a claimed ancestry universe must be constructed from an
  exact adjacency multimap, reject self-edges, unknown endpoints, duplicates,
  and cycles, compute the complete transitive closure without losing
  multi-parent paths, deduplicate reachability facts, and order each result by
  independently frozen subject and ancestor keys. Traversal order is never
  authority.
- Why prior evidence missed it: most fixture ancestry was chain-shaped; aggregate
  counts and selected examples did not force a multi-parent branch; the
  producer and verifier shared the same single-parent representation; and no
  adversarial reorder proved that traversal order was presentation rather than
  identity.
- False assumption: every child has at most one parent, and a deterministic
  graph walk produces the canonical semantic order.
- Prevention invariant: declare the complete edge multiset, endpoint universe,
  stable row ordering, cycle policy, duplicate policy, reachability semantics,
  and output ordering before construction. Build expected closure independently
  from candidate output. Require exact equality of identities, multiplicity,
  order, and full claimed-universe cardinality.
- Searched surfaces and current result: root reconstructed the accepted
  ancestry domains. Dataset-link row03 reaches row00 then row01. Experiment-spec
  row01 reaches row00, while row02 reaches row00 then row01. Optimization-trial
  child rows row01 through row04 reach all prior rows in ascending insertion
  order. This yields the accepted 119-tuple universe across 8 fixtures and 11
  predicate families. The failed owner produced 118 and stopped; no database or
  product path changed.
- Permanent regressions: (1) an explicit multi-parent branch/diamond that loses
  an edge under a single-parent map; (2) direct and transitive duplicate-path
  deduplication; (3) cycle, self-edge, duplicate-edge, unknown-endpoint, and
  disconnected-node cases; (4) stable canonical child/ancestor ordering under
  reversed edge declaration and different traversal algorithms; (5) exact
  independently reconstructed equality across all 8 fixtures, 11 families, 88
  applicability records, and 119 tuples; (6) the accepted baseline, seven
  transforms, thirteen adversarial cases, and exact restoration; and (7)
  selected-subset rejection after explicitly asking `What is the
  4-of-24-tables equivalent?` and exercising a declared 4-of-8 fixture subset.
- Adversarial generalization: search for scalar maps used where the domain is a
  multimap or relation, and for iteration, insertion, query, filesystem,
  provider, or traversal order used as semantic order. Apply the same tests to
  strategy graphs, research lineage, ownership inheritance, dependency DAGs,
  requested/resolved authority, provider routes, migration prerequisites,
  causal event ancestry, order/fill attribution, and evidence registries.
- Transitive evidence map: canonical graph authority -> trigger-fixture evidence
  correction -> semantic package and complete PostgreSQL evidence ->
  contract-core and native-state slices -> observers and complete DATA/CAT
  obligations -> mutation attestation -> migration runtime and integration ->
  numeric correction -> transitive revalidation -> one Critical review ->
  Phase 1-4 acceptance -> combined Phase 5/6 planning. Every downstream artifact
  that consumed the 118-tuple result remains invalidated until re-executed.
- Proportionality: exact enumeration is mandatory for this finite 119-tuple
  claim. Equivalence partitions may organize mutations but cannot replace the
  independently enumerated baseline universe or its canonical order.
- Owner: fresh
  `phase1-4-foundation-postgresql16-semantic-trigger-fixture-contract-evidence-correction-2-repeated-failure-recovery`
  defines the corrected database-free architecture. A fresh correction-3 owner
  may implement it only after root same-byte acceptance and exact dispatch.
  Transitive revalidation and the final Critical reviewer alone may restore the
  Phase 1-4 acceptance chain.
- Evidence: root blocker acceptance
  `.agent/runs/phase1-4-foundation-critical-closure/postgresql16-semantic-trigger-fixture-contract-evidence-correction-2-blocker-acceptance.json`
  SHA-256
  `a73adf40fc69da510bdcedf2ea885a84ba07796cc3cb250f92368564b396e0f0`;
  blocked report, manifest, and failure-lineage SHA-256
  `9572345de9cd3243e119c8d0be9e34921074c568a9cf5befeb6e39efd8c6ed66`,
  `eb8744187ad2d2f28db1d941178a25ce63ea281ca031a7a1cdba44128ed7db61`,
  and
  `7b182618ea10db847e0dc3c016e793246b4655e71b9b7163540c994249106963`;
  root acceptance validator and passing log SHA-256
  `2672539d700593f096fce5d45ce738e6d280ee8fd3358cf0b77796dcd4c7655b`
  and
  `c0de8026b10ebc725d745dafcc7783035ce1167281dc3da67fb95c2a51e058ef`.

## DP-016 — Final assurance consumes evidence before its producer can create it

- Severity: Critical when an evidence package supports migration, persistence,
  research integrity, tenancy, execution authority, deployability, phase
  acceptance, or any money-safety claim.
- Status: CONTAINED/BLOCKED. Recovery 8 changed no product, database, test,
  migration, runtime, deployment, live, order, or money byte. Root independently
  reproduced the frozen package's final-validator crash and replay timeout. The
  package is rejected, its sole repair is exhausted, and no successor is
  authorized. Accepted correction-2 authority remains byte-exact but does not
  make the rejected harness acceptable.
- Incident: Recovery 8 reached a materially better intermediate state. Its exact
  copied package passed strict normal validation, two semantic probes, and all
  22 candidate cases with complete restoration. It could not lawfully reach
  `FINAL`. The validator's final branch dereferences and requires 28 populated
  mutation-execution rows. Every row is initially null. The only executable that
  can populate those rows invokes the same validator with `--expected-stage
  FINAL`. On an exact independent copy, the final validator raises
  `AttributeError` before emitting a disposition. Replay later waits for that
  validator's changed-after-read readiness signal and fails with
  `VALIDATOR_READY_TIMEOUT`.
- Related identity defect: case and child receipts require their absolute `cwd`
  and script paths to equal the validator's current package location. Package
  scripts must execute only from an immutable copy, so honest receipts record
  that copy's location. Publishing the same bytes at the evidence root changes
  the incidental absolute path. Rewriting the receipt would falsify execution;
  retaining it would fail validation. Content identity and execution-location
  attestation were collapsed into one fact.
- Root cause: the evidence lifecycle was designed as mutually validating files
  and scripts rather than an acyclic producer-consumer state machine. Static
  package readiness, case execution, mutation execution, restoration, sealing,
  and final acceptance had no independently frozen transition contract. The
  implementation also treated an absolute filesystem address as executable
  identity instead of separately recording root-relative logical identity,
  immutable package content, and actual execution location.
- Violated invariant: every evidence transition consumes only an immutable
  predecessor state and produces one new successor state. No validator may
  require an output that only the operation it gates can create. Executable
  identity binds to root-relative logical paths and content hashes. Actual
  executable, environment, working directory, and absolute paths remain
  separately attested observations and cannot redefine portable content
  identity.
- Why earlier controls missed it: normal validation checked the repaired static
  package, probes checked two semantic branches, and the 22-case runner checked
  candidate outcomes and restoration. None executed the whole lifecycle from a
  clean package through final mutation evidence and relocation. Root pre-audits
  progressively closed schema, topology, authority, AST, subprocess, receipt,
  and restoration defects, but the complete producer-consumer graph itself was
  not executed before the repair budget was spent.
- False assumption: if every individual stage has a strict validator and every
  final field is required, the combined workflow must be constructible. A set of
  locally strict checks can still form a cycle or make honest evidence
  impossible to relocate.
- Historical failure progression that every future review must retain:
  (1) Recovery 1 sealed a 30-member intermediate closure while later required
  logs expanded the final closure to 36 members; (2) Recovery 2 omitted
  recursive bytecode and local dependencies, accepted duplicate JSON keys, and
  discarded required per-case structural and restoration evidence; (3)
  Recovery 3 allowed indirect dynamic imports and aliased subprocess calls to
  bypass static dependency proof; (4) Recovery 4 accepted embedded candidate
  data in place of correction-2 authority, omitted callable-origin and
  call-target tables, simulated changed-after-read before validator invocation,
  and silently changed Python 3.13.5 to 3.9.6; (5) Recovery 5 made an untouched
  complete package reject because topology compared 19 regular files with an
  18-member nonself set; (6) Recovery 6 rejected a disconnected row explicitly
  allowed by accepted applicability authority; (7) Recovery 7 captured only 17
  assignment files at case boundaries instead of the complete 21 typed package
  entries; and (8) Recovery 8 formed the final-evidence cycle and absolute-path
  contradiction described above.
- Prevention invariant: freeze and independently validate a finite lifecycle
  before another owner writes a package. A suitable minimum is
  `INITIAL_COMPLETE -> STATIC_READY -> CASES_COMPLETE -> MUTATIONS_COMPLETE ->
  SEALED_FINAL -> ROOT_ACCEPTED`. Each transition declares exact inputs,
  outputs, producer, consumer, allowed writes, failure disposition, restoration
  rule, and content fingerprint. The final validator consumes completed case
  and mutation receipts but never produces them. Mutation replay consumes
  `CASES_COMPLETE` or `STATIC_READY`, not `FINAL`. Sealing follows all evidence
  writes. Root acceptance is read-only.
- Permanent regressions: (1) construct the full lifecycle from a clean package
  with no bootstrap data and require every transition to terminate; (2) reject
  any transition whose required input is produced only by itself or a later
  transition; (3) execute all 22 cases and all 28 named mutations, including a
  real read-then-change handshake; (4) require exact before/after restoration of
  all 21 typed entries at every builder, observer, validator, and replay
  boundary; (5) copy the frozen package between two different absolute roots
  and require identical content identity and valid honest receipts; (6) retain
  the actual cwd, executable, argv, environment, interpreter, and package-copy
  location as observations without making their incidental root prefixes part
  of portable content identity; (7) reject rewritten or fabricated execution
  paths; (8) reject recursive unowned, nested, cache, bytecode, symlink, special,
  duplicate-key, duplicate-normalized-path, path-escape, self-hash, stale-hash,
  and undeclared-dependency states; (9) reject indirect import, callable alias,
  reflection, unapproved subprocess, unresolved call target, and missing AST
  proof states; (10) reconstruct accepted correction-2 graph, closure, universe,
  applicability, and counts from byte-exact authority rather than embedded
  claims; (11) rerun every Recovery 1-8 root counterexample; and (12) prove the
  final seal has no self-reference or member set that grows after sealing.
- Phase-wide carry-forward: later phase and combined reviews must first replay
  the historical regression corpus relevant to their changed surfaces, then
  conduct a fresh independent review of everything else. Passing the historical
  corpus proves only that known failures did not recur. It never narrows the
  review to those failures or substitutes for newly discovered counterexamples.
- Transitive evidence map: accepted correction-2 graph and finite-universe
  authority -> acyclic portable harness lifecycle -> trigger-fixture semantic
  evidence -> complete PostgreSQL evidence -> native-state and migration
  evidence -> runtime and integration evidence -> numeric correction ->
  transitive revalidation -> one Critical review -> Phase 1-4 acceptance ->
  combined Phase 5/6 planning. All downstream claims remain gated.
- Token-efficiency control: root must publish and run the lifecycle oracle and
  historical rejection corpus before dispatching Recovery 9. The next owner
  receives one consolidated pre-audit and may not spend its sole repair on a
  defect the oracle could have found before dispatch. Evidence files should
  carry exact facts and hashes; route documents should reference them rather
  than repeat long prose.
- Owner: root first owns the database-free lifecycle oracle. Only after its
  independent same-byte PASS may one fresh Recovery 9 owner construct the
  harness. Recovery 9 remains database-free and cannot claim deployability,
  production readiness, live readiness, money safety, phase acceptance, or
  successor activation.
- Evidence: Recovery 1-8 root-rejection SHA-256 values are respectively
  `ef7c84cf6540f6845f5c6927ce4bdfb1ca0e943c109fcf2ac48803856e0e0a2d`,
  `909f29236d77dfe462af22e91d6f5aab57d18c985baf0d9eaed73f3b74b1a075`,
  `98d6f5d78e68b537c7f373a3823ed1127f59f87bb6db6fe7fa5aca0297c2f7e1`,
  `837dfdf8e70791a88f60c0291c14b3776284c94990a1a7cf448fff001856fe27`,
  `cecf1ef4ba186b2df5d3b5631285eb45334096e880c894be708f23e89b96d6b1`,
  `046a352896a223067e281a60ef9c13e5bd139c4ada1428b85948d21b67d367ea`,
  `753c3ec64370fb983bf33d997c80f1ea816ced18c18d4e041891b5a5e8509821`,
  and
  `adaff6a86158cca6448573a7dcb754c51e89084bc4060e627d61eaee408fac5d`.
  Recovery 8 independent rejection audit and same-byte validation SHA-256 are
  `aafdc926e4a0b68299ec2377991a2117f04a04230b13a1bd324afdfb8ddc1b0b`
  and
  `10b7f6460b15f3f46237e74d0f361132a13f1f12853db0255259aad8fa4d6161`.
