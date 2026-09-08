# Sealed indicator assurance inputs

This bundle contains exact historical expected vectors, independent oracle sources,
source decisions, seals and required pre-change snapshots. It makes the indicator
assurance suite reproducible in a fresh checkout. Expected values were copied from
the retained evidence; they were not regenerated from the current implementation.

`manifest.json` records every logical path, byte size and SHA-256 digest, plus the
archive digest. The test bootstrap verifies those values and restores inputs into
the ignored `.agent/runs` locations expected by the original assurance tests.
Existing files must match exactly. Test outputs stay outside version control.

The bundle excludes runtime databases, credentials, private conversation records,
mutation checkouts, coordination files, logs and generated comparison outputs.
Four hash-pinned technical reports are retained because their original bytes form
part of the independent source evidence. The historical rulebook copy matches its
original source-authority seal; the current production file remains separate.

The session-prefix generator reproduces the historical F01 correction artifact,
not every subsequent maintained version of `session_data.py`. Later local-role
binding and validation changes have separate current compilation, execution and
restore tests. Historical regeneration runs in a temporary checkout and checks
the original sealed receipt; it must never overwrite current product source.

The loose `historical_sources/` files preserve three original source versions
without changing the sealed archive or manifest. They are byte fixtures, not
current runtime contributors:

- `session_data_before_prefix_correction.py` has SHA-256
  `7dd508c41cb267f7fe571b60fef414c3244b6c3373178c043226811213a4b897`,
  recorded by the session-data closure seal and rejected fresh-assurance seal.
- `session_data_prefix_correction.py` has SHA-256
  `3592d4478cf9494c196b415c468438d3ee9d9e157b2d2104922373e9f2eb534f`,
  recorded by the prefix-correction closure seal and source receipt.
- `contracts_session_data_assurance.py` has SHA-256
  `95e0ae03d2f3dc93fb959c9522cb636c517d7ebd5766e3ae3524d95964be0ba3`,
  recorded in the session-data closure seal's protected source hashes.

These exact bytes were recovered from retained isolated source copies and checked
against the original digests. Historical rejection and publication decisions stay
unchanged. Current contributor registration equality, source contracts, refused
components, numerical behavior and research-only restrictions are checked against
the maintained implementation separately.
