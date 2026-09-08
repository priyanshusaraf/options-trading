# Diagnostic receipt contract

Use this as a review/output template, not a new product schema or automatic exporter.
Reuse an existing equivalent contract. Collect only fields relevant to the symptom;
missing evidence stays explicitly unknown. No real customer data belongs in examples.

| Field | Allowed content and limit |
| --- | --- |
| Case | Case-scoped opaque reference; no embedded tenant/user/strategy identity. |
| Collection | UTC time, bounded observation window, collection procedure/version and reviewer. |
| Runtime | Build/version, release profile, service role and environment class; no hostnames, internal addresses, paths or raw environment dump. |
| Symptom | Typed operation and error/state codes; manually reviewed minimal narrative. No arbitrary free text copied from payloads. |
| Readiness | Necessary dependency/schema/worker/freshness status, with unknown/stale distinct from healthy. |
| Measurements | Needed aggregate counts/durations and units; bounded window/sample size, no raw business values or unbounded labels. |
| Reproduction | Synthetic steps/fixture reference and observed result; no original graph, parameter set, dataset or account export. |
| Evidence | Restricted internal reference with reader authorization, or a reviewed redacted artifact with digest; no public raw log URL. |
| Review | Included/omitted categories, redaction/tenant checks, reviewer, permitted audience and sharing approval. |
| Lifecycle | Approved storage location, access scope, retention/expiry, revocation and deletion responsibility. |

Before release, check the serialized output, nested fields and attachments against
the allowlist. Treat object names, hashes, free text, stack traces and timestamps
as potentially identifying. A digest detects artifact changes; it does not sanitize
the artifact or authorize access. Keep any alias-to-owner mapping restricted and
separate from the support-facing receipt.

Do not add an `extra`, `raw`, `context` or arbitrary key-value escape hatch. If the
symptom needs a new field, document its purpose and sensitivity, obtain the required
approval and extend the existing contract/test deliberately.

A useful receipt answers: what operation failed, on which permitted build/profile,
when, with which typed state, what safe evidence supports that observation, and who
owns the next step. It must not disclose how the customer's proprietary strategy
works or imply that support can execute it.
