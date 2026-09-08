Reference: [section index](../DEFECT_PATTERNS.md). Read with its scope; this is not a new assignment.

## DP-009 — Logical ORM transaction mistaken for a physical outer transaction

- Severity: Critical when a nested write records authority, a terminal state,
  or a state-plus-outbox fact.
- Status: ARCHITECTURE CLOSED; implementation and transitive evidence remain
  open in `phase4-authority-transaction-correction`.
- Incident: ADV-003 injected a DBAPI commit refusal after execution and research
  graph-plus-receipt writers returned. On SQLite, both rows remained durable
  after caller rollback. The Session reported an active transaction, but the
  driver had no outer transaction; `begin_nested()` created a top-level
  savepoint and releasing it committed the rows.
- Root cause: code treated SQLAlchemy autobegin, `Session.begin()`, or an
  ownership wrapper as proof of a real database transaction. SQLite legacy
  transaction mode does not start a DBAPI transaction for a clean SELECT, while
  PostgreSQL does, so same-shaped local code had different durability.
- Prevention invariant: every nested persistence writer enters the sole
  `caller_owned_savepoint(session, *, scope)` boundary. It proves or starts the
  physical root on the same supported-dialect connection before SAVEPOINT,
  binds proof to the live root transaction, clears proof at root end, rechecks
  driver state, and refuses failed state or unproved external SQLite nesting.
  It owns only the savepoint and never commits, rolls back, closes, invalidates,
  retries, or replaces caller resources.
- Searched surfaces: every `begin_nested`, literal SAVEPOINT, commit, rollback,
  and transaction-owner wrapper under current Phase 1-4 `backend/app` and
  `backend/research`. The seven impacted seams are execution admission,
  research admission, research dataset authority, fenced backtest result batch,
  terminal backtest state/outbox, public computation cache, and ledger
  snapshot/outbox. `outbox.writer` remains the ledger transaction owner but is
  not physical SQLite proof. No other current savepoint seam was found.
- Permanent regression: both authority planes cover no prior SQL, clean SELECT,
  prior write, explicit/external root, proved recursive nesting, unproved
  external SQLite nesting, unrelated pending work, flush failure, DBAPI commit
  refusal plus caller rollback, rollback failure, exact retry/collision,
  successful commit, and fresh-process reconstruction on SQLite and
  disposable PostgreSQL 16 where semantics differ. Each of the other five
  seams gets a direct failed-commit/rollback and success/retry test.
- Mutation ownership: kill and byte-restore physical-root establishment, root-
  marker cleanup, external-nesting refusal, and the no-helper-commit/rollback/
  close invariant, plus one real adoption guard in each of all seven seams.
- Transitive invalidation map: shared transaction helper and seven callers ->
  graph/receipt, dataset manifest, fenced result/progress, terminal/outbox,
  public cache, ledger snapshot/outbox, portable outbox, two-plane lifecycle,
  ADV-002/ADV-003, full matrix, official review package, and final review.
  Historical stopped-matrix logs remain counterexample evidence only.
- Owner: `phase4-authority-transaction-correction` for product closure;
  `phase4-adversarial-matrix-closure` for fresh ADV-001..ADV-027 attribution;
  `phase4-final-review-4` for review readiness.
- Evidence: `.agent/runs/phase4-authority-transaction-architecture-correction/owner/`.

## DP-010 — Current-head or hybrid fixtures presented as supported-old migration evidence

- Severity: Critical when the fixture grants migration, persistence, research
  integrity, or deployability credit.
- Status: CLOSED at the finite direct local boundary. The active runner supports
  only clean, exact frozen `0010`, and exact `0011`; unsupported and drifted
  states refuse before writes. Direct SQLite and disposable PostgreSQL 16
  matrices, complete catalog/data digests, killed/restored guards, root
  integration, and one independent recheck are current. Historical recovery
  packages remain immutable and unaccepted.
- Closure evidence: `.agent/runs/phase1-4-foundation-direct-closure/root/direct-acceptance-report.md`,
  `.agent/runs/phase1-4-foundation-direct-closure/root/recheck-command-metadata.json`,
  `.agent/runs/phase1-4-foundation-direct-closure/review/recheck-verdict.json`
  with SHA-256 `d43994cc2d4d1d6e9b827a0f6169a1a75128b24d862e3ac3461ded7fca153069`.
- Incident: foundation audit A-01, A-03, A-04, and A-05 found that the exact
  populated SQLite 0005 projection cannot reach research head 0010. Stage 0007
  lacks three dataset-manifest triggers; 0008 and 0009 also lack two
  graph-version immutability triggers. Retained tests started at later prefixes
  or created current tables and rewound selected objects. Populated-old
  PostgreSQL support and the SQLite/PostgreSQL marker difference remained
  unproved.
- Root cause: the 0007 and 0008 routines create copied `Table` objects with
  `checkfirst=True`. SQLAlchemy listeners attached to current model `Table`
  objects do not follow those copies, so table creation omits the full trigger
  contract. Historical projections are derived from current metadata, and
  tests treated current-head rewinds as historical facts. Marker advancement
  and evidence therefore trusted construction provenance that they did not
  verify.
- Repeated-failure classification: projection repair 1 left PostgreSQL catalog
  inspection incomplete and did not bind SQLite to an explicit reopen consumer.
  Projection repair 2 added exact catalog inspection, but its caller-state
  comparison still covered only four of 24 durable tables. Committed changes to
  `research_hypothesis` and `research_finding` survived close, engine disposal,
  and reopen while the selected consumer stayed green. The shared material
  defect is a subset oracle presented as complete state evidence. Catalog
  hardening from repair 2 remains valid input; neither repair is accepted.
- Native-oracle implementation false green: the later fresh owner initially
  raised a SQLite `KeyError: sql`, then correctly repaired the declaration join
  by matching table name/type through `INVENTORY.sqlite_schema`. That KeyError
  did not survive. The focused SQLite/PostgreSQL 16 suite then passed while the
  suite still named none of the 24 DATA or 39 CAT obligations and contained no
  typed immutable two-dialect `ExpectedNativeState`, effective reopened
  mutation receipt, restoration receipt, or aggregate `ClaimAttestation`.
  Treat a green collected suite without exact obligation-set validation as the
  same DP-010 false-green class. The prevention gate must fail current bytes,
  pass a complete 63-ID registry, and reject one-at-a-time omissions before an
  implementation pass is eligible.
- Repeated implementation failure: the failed capsule assigned immutable type
  design, dialect declarations, both builders, process isolation, complete
  63-obligation integration, receipt taxonomy, and adversarial coverage to one
  owner and one acceptance boundary. A focused selector could therefore pass
  after the SQLite join repair while no sealed consumer bound the 24 DATA and
  39 CAT sets. This was an unimplementable monolith for the allowed two-attempt
  budget, not a missing PostgreSQL harness: the narrow disposable PostgreSQL 16
  selector ran and passed. Prevent recurrence with three root-gated serial
  nodes for contract core, observers, and obligation evidence, followed by the
  separate mutation node. Each node has exact disjoint write paths, one durable
  goal, no children, one initial patch, and at most one repair. No successor may
  reinterpret or patch an accepted dependency.
- Recovery result: exact committed bytes reproduce PostgreSQL `0003` through
  `0005` empty schemas, but no complete version-owned catalog and transition
  contracts cover arbitrary valid user and sequence state. Accepted dirty
  `0006` through `0009` deltas do not define frozen full catalogs. Exact current
  `0010` bytes define the only defensible retained catalog start after a frozen
  product contract and data-parametric witness builder pass.
  Authority ledger SHA-256 is
  `32a3735b5fe992e193a0e053b7940d77937fcfd7d86377a0f45b118bd828e0b1`.
- Prevention invariant: each supported version has one frozen, dialect-specific
  catalog projection independent of current model metadata. Every SQLite
  catalog cites its exact named product source authority; no inferred or
  invented catalog fact is accepted. Contract-valid rows and sequence state are
  parameters, not projection authority. Deterministic synthetic corpora prove
  parameterization but define no schema, historical fact, or user fact. After
  root accepts the explicit revisions, SQLite supports only empty direct
  construction, exact or enumerated-five-guard `0010`, and exact `0011`;
  unversioned and `0001` through `0009` refuse before writes.
  PostgreSQL supports only empty, exact catalog `0010` with arbitrary valid
  user and sequence state, and exact current
  `0011`; `0003` through `0009` refuse before writes. A migration validates the
  exact source, installs the complete target table, constraint, index,
  function, and trigger contract, validates target behavior, and only then
  advances the marker. Only an `EXACT_HISTORICAL_CATALOG_PROJECTION` may prove
  catalog provenance. `SYNTHETIC_CONTRACT_VALID_WITNESS` proves only behavior
  over contract-valid state. `CURRENT_HEAD`, `HYBRID_FAULT_INJECTION`, and
  `RETIRED` fixtures cannot prove actual-old support.
  The expected native state for each of both materially different corpora comes
  only from caller rows, caller-requested sequence values, and frozen ordered
  column/type declarations. It never reads an observed row or inventory. The
  production consumer compares every row and column in all 24 durable tables,
  the exact marker, exact non-advancing sequence state and bindings, keys, foreign
  keys, storage/driver types, and the complete catalog. Textual JSON and Unicode
  retain exact UTF-8 bytes; binary retains exact bytes and length; timestamp and
  boolean adaptation is declared per dialect rather than normalized after read.
- Current recovery disposition: the SQLite architecture is exact but inactive
  pending root acceptance. Ledger SHA-256
  `874cc53fc1e455428915359a1253e225467bbe5d3057cd94abd153b3f4c9e7b8`
  and support-matrix SHA-256
  `63aa4c648d5a20298671810012dabaee690f886c52d562cb0dcc05cd270fd8e0`
  reject every unproved historical start. Never infer those catalogs from
  current metadata, synthetic witnesses, or later-head subtraction.
- Searched surfaces: `backend/research/domain/migrate.py`, every module under
  `backend/research/domain/migrations`, research and backend migration tests,
  fixture builders that call current `metadata.create_all()` before stamping an
  old version, schema-head checks, SQLite schema-cookie logic, PostgreSQL
  version-only logic, and migration/deployability claims. The correction must
  repeat the search after final product bytes freeze.
- Permanent regression: independently build the sole SQLite target contract
  plus PostgreSQL exact `0010`, run at least two materially different synthetic
  contract-valid corpora under each catalog, execute the declared direct route,
  terminate and reopen at transaction boundaries, assert exact inventory and marker state, execute direct SQL
  guards, and preserve row, key, sequence, owner, classification, and canonical
  bytes. SQLite checks storage class, affinity, textual JSON and BLOB bytes;
  PostgreSQL preserves text/varchar JSON bytes and uses dialect-native
  representation for any catalog-declared json/jsonb. Inspect sequence state
  without advancing it. Direct guard writes run only inside rollback-only
  savepoints or subtransactions, commit nothing, and leave the complete
  preflight digest byte-identical. Cover interruption, restart, downgrade, unknown head, stale cookie,
  arbitrary drift, and the enumerated missing-trigger repair states. Kill and
  restore each 0007/0008 trigger installer and the 0011 certification guard.
  Also execute one effective stored-data mutation for every durable table under
  both corpora and dialects. Immutable-table cases use a valid committed extra
  row with guards enabled. Every mutation must change the complete digest after
  real reopen, fail at its named consumer code, restore exactly, and be bound to
  a machine receipt. A statement refusal, no-op, self-comparison, selected slice,
  or report-only claim receives no credit.
- Invalidation rule: any fixture built from current model metadata, any missing
  supported prefix or dialect, any target marker written before complete
  validation, any unclassified fixture, or any changed migration byte makes all
  dependent migration, persistence, deployability, package, and review claims
  `STALE/REQUIRES RECHECK`. Historical review artifacts remain immutable.
- Owner gate: both matrix revisions are inactive until root-owner architecture
  acceptance. The recovery capsules require root and user direction only if a
  revision could strand a released, deployed, production, supported-database,
  customer, or externally promised database. Repository evidence shows none
  for the removed SQLite or PostgreSQL starts, so no
  extra user gate applies on present evidence. Later contrary evidence stops
  work for both root and user direction.
- Owner: `phase1-4-foundation-direct-closure` owns the finite product boundary,
  direct evidence, one bounded correction, and one independent recheck. The
  historical projection, native-state, grammar, and evidence-integration
  lineages remain immutable and unaccepted outside the critical path.
- Evidence requirements: owner direction SHA-256
  `eb66946c5f7a8807ab116883b9847e337122dd3ebf6e118de2bf7d45d3322d01`,
  refreshed review package SHA-256
  `0e67dfcebb0b85161efa34501a8a3a6a953c4bed5a9e66bc93b2ffe481a56cfc`,
  the direct-closure evidence root, and the reviewed current source/test hashes.
