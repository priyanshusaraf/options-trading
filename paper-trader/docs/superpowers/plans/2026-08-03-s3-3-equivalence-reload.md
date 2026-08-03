# S3.3 Executable Equivalence and Lossless Reload Plan

**Goal:** Prove that a closed editor command history produces the same canonical executable graph
and content address as an independently hand-authored reference at the same server-issued version,
then prove the coherent semantic and presentation document reloads without loss.

**Architecture:** Use the existing S3.2b semantic and presentation endpoints only. Build the
reference graph directly from the accepted IR fixture, without calling `app.ir.edit`, and compare
canonical JSON plus content address after one structural publication. Presentation setup and
reconciliation remain outside the reference graph and must not affect equivalence. Reload proof
disposes database connections and reconstructs the application-facing snapshot from persisted
rows; the client performs no topology, descriptor or group repair.

## Task 1: Add the executable equivalence oracle

- [ ] Construct a hand-authored reference that removes `n_exit_fallback`, adds a disconnected
      `value.scalar` node, replaces the fallback edge with `n_exit_floor.out`, preserves authored
      array order and declares the next server version/parent.
- [ ] Publish the equivalent closed batch through `/edits` and assert canonical JSON and content
      address match exactly.
- [ ] Assert the request carries revisions and operations only: no raw graph, immutable version or
      content address.

## Task 2: Prove presentation exclusion and reconciliation

- [ ] Before publication, position and visually group the removed node.
- [ ] Assert removal prunes its position and membership, while the expected executable identity is
      unchanged by whether that presentation setup exists.
- [ ] Mutate the oracle to include visual groups in executable JSON and prove the equivalence guard
      fails before restoring it.

## Task 3: Prove lossless persisted reload

- [ ] Persist a position, visual group and structural publication, dispose database connections,
      then load a fresh coherent editor snapshot.
- [ ] Assert exact graph bytes, content address, graph/presentation revisions, descriptors,
      positions and groups match the accepted response.
- [ ] Replay the accepted inverse receipt after reload and prove semantic plus presentation state
      restores without client reconstruction.

## Task 4: Add precise mismatch diagnostics

- [ ] Return or generate field-level diagnostics for semantic content, node/edge ordering,
      executable identity and presentation contamination without accepting raw replacement.
- [ ] Cover each diagnostic with one focused negative test.

## Task 5: Verify, publish and continue

- [ ] Run focused equivalence/reload tests during implementation and the WS-04 regression when the
      slice closes.
- [ ] Run the full shared checkpoint only if S3.3 changes shared persistence or canonical identity.
- [ ] Update `EXECUTION_PLAN.md`, `WS-04-editor.md` and `CONTINUE.md`, commit deliberately, push,
      inspect the exact-head Actions run and continue into the next unblocked slice.
