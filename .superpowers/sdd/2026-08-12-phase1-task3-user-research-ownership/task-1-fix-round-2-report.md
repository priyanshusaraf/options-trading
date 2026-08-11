# Task 1A.1 fix round 2 report

## Scope

- `load_version` now uses its existing owner-scoped `GraphVersion -> GraphArtifact -> Project`
  SQL query as the only lookup and returns `GraphNotFound()` for every no-row result. A wrong
  owner, an absent version, and an absent graph therefore have the same exception class, args,
  and string form.
- `list_versions` has explicit wrong-owner versus absent-graph evidence.
- The graph test records hash inputs, verifies stored canonical JSON, and guards the public
  version/list reads against `GraphVersion.content_address` lookup predicates. Owner provenance
  is not part of the document or its hash input.
- Revision `0020` now checks duplicate tenant-local project names before the existing
  non-legacy-owner refusal. This only selects the specific refusal shape when both invalid
  downgrade conditions exist; it performs no DDL or data mutation.
- Added a downgrade test with two valid organizations sharing `Shared` under the `(owner_id,
  name)` uniqueness contract. It proves refusal preserves the schema, rows, Alembic revision,
  and caller foreign-key setting.

## RED and GREEN evidence

The verified interpreter initially ran these four exact nodes:

```text
tests/test_user_plane_tenant_isolation.py::test_load_version_uses_one_absent_shape_for_owner_graph_and_version_misses
tests/test_user_plane_tenant_isolation.py::test_list_versions_hides_another_owners_graph_as_an_absent_graph
tests/test_graph_artifacts.py::test_owner_provenance_stays_out_of_graph_bytes_hashes_and_repository_hash_lookups
tests/test_schema_migrations.py::test_revision_0020_downgrade_refuses_two_valid_owner_same_name_before_destructive_ddl
```

RED was `F.FF`: the wrong-owner `load_version` case raised args `(project_id, identifier)` while
the absent-version case used `(project_id, identifier, version)`; the source assertion needed to
distinguish returning `content_address` from querying by it; and downgrade selected the generic
non-legacy-owner refusal before the duplicate-name refusal.

After the minimal production edits, the same four nodes passed.

## Verification

- Migration and tenant isolation gate: 53 passed.
- Original Task 1A.1 graph/migration/route gate: completed with exit 0.
- Review-source and related route gate: completed with exit 0.
- `python -m compileall -q app migrations tests`: exit 0.
- `git diff --check`: exit 0.
- AST caller audit: no public graph repository calls missing `owner_id` outside the deliberate
  TypeError isolation tests.

The pytest runs retain existing SQLite datetime-adapter and Starlette `TestClient` deprecation
warnings.

## Deferred boundary

`identifier` remains canonical graph JSON and revision `0020` retains global graph identifiers.
Two owners cannot simultaneously persist byte-identical canonical graphs until Task 1A.3 creates
composite owner/graph identities. This fix does not change hashing or add a fake same-identifier
persistence case.

## Protected files

The pre-existing dirty broker/provider files were not edited or staged.
