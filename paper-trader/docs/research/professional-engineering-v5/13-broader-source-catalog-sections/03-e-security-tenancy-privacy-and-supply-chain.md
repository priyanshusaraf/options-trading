Reference: [section index](../13-BROADER-SOURCE-CATALOG.md). Read with its scope; this is not a new assignment.

## E. Security, tenancy, privacy and supply chain

| ID | Source and reviewed location | Review | Transferable claim | Strategy OS decision |
| --- | --- | --- | --- | --- |
| SEC-01 | OWASP [ASVS 5.0.0 stable release](https://github.com/OWASP/ASVS/releases/tag/v5.0.0_release) | RELEASE/METADATA | Requirement IDs are versioned and a scoped inspection must include unverified rows. | Use `v5.0.0-*` IDs and make no certification or full-level claim. |
| SEC-02 | OWASP [Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html) | FULL TEXT | Authentication is not object authorization; deny by default and test positive plus negative paths. | Server-derived owner scope remains mandatory across API, jobs, sockets, artifacts and caches. |
| SEC-03 | OWASP [Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) | FULL TEXT | Source code, sessions, tokens, secrets, bank data and commercially sensitive data should not be logged directly. | Strategy IP, broker facts and credentials stay out of logs/traces/support receipts. |
| SEC-04 | OWASP [File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) | FULL TEXT | Authorization, allowlists, content/signature checks, generated names, safe storage and decompression/size bounds are layered controls. | CSV/BYOD admission must fail before parser/resource effects and remain owner scoped. |
| SEC-05 | NIST [SSDF 1.1, SP 800-218](https://csrc.nist.gov/pubs/sp/800/218/final) | ABSTRACT/FRAMEWORK | Secure practices integrate into the SDLC and supply-chain communication. | Map current CI, dependency, review and incident evidence; do not claim compliance from prose. |
| SEC-06 | [SLSA 1.2](https://slsa.dev/spec/v1.2/) and [provenance](https://slsa.dev/spec/v1.2/provenance) | FULL TEXT | Provenance records where/how an artifact was built; verification must compare it against expectations. | Release receipts need source/artifact/config/database identities and an actual verifier. |
| SEC-07 | CISA, [Choosing Secure and Verifiable Technologies](https://www.cisa.gov/resources-tools/resources/choosing-secure-and-verifiable-technologies) | FULL TEXT | Technology procurement should consider verifiability and secure defaults. | New components must pass the existing eight-part exception and prior-art gates. |
| SEC-08 | NIST [Privacy Framework](https://www.nist.gov/privacy-framework/privacy-framework) | SELECTED FRAMEWORK | Privacy risk spans collection, retention, logging, use, disclosure, sharing and disposal. | Build data-flow/retention inventories; no legal-compliance conclusion is made. |

## F. Durable jobs and workflow comparison

| ID | Source and reviewed location | Review | Transferable claim | Strategy OS decision |
| --- | --- | --- | --- | --- |
| WF-01 | Temporal, [Workflow Execution](https://docs.temporal.io/workflow-execution) and [Retry Policies](https://docs.temporal.io/encyclopedia/retry-policies) | FULL TEXT | Durability depends on event history, deterministic replay, activity boundaries, retries and a Temporal service. | REFERENCE ONLY. Current V0 jobs do not justify a new deployable/service. |
| WF-02 | DBOS, [Architecture](https://docs.dbos.dev/architecture), [Recovery](https://docs.dbos.dev/production/workflow-recovery) and [transactional outbox](https://docs.dbos.dev/python/examples/outbox) | FULL TEXT | DBOS checkpoints inputs/steps in PostgreSQL; distributed recovery needs executor coordination or Conductor; nontransactional steps remain at least once. | REFERENCE ONLY. A bounded non-money spike is reconsidered only after current job recovery fails a named requirement under measured load. |
| WF-03 | Restate, [Key Concepts](https://docs.restate.dev/foundations/key-concepts) and [Architecture](https://docs.restate.dev/references/architecture) | FULL TEXT | Restate interposes a log-first server with journals, RocksDB state, partitions and Raft-based control. | REJECT NOW. It adds a deployable, state store, consensus, operational ownership and a second execution authority. |
| WF-04 | PostgreSQL, [`SKIP LOCKED`](https://www.postgresql.org/docs/17/sql-select.html) | SELECTED SECTION | Multiple workers can skip locked rows, but the result is intentionally inconsistent as a general view. | Keep exact claim token/owner/fencing predicates around queue selection and prove termination on PostgreSQL. |

## G. Architecture evolution and measured scale

| ID | Source and reviewed location | Review | Transferable claim | Strategy OS decision |
| --- | --- | --- | --- | --- |
| SCALE-01 | Shopify, [Deconstructing the Monolith](https://shopify.engineering/deconstructing-monolith-designing-software-maximizes-developer-productivity) and [Under Deconstruction](https://shopify.engineering/shopify-monolith) | FULL TEXT | Modular boundaries can reduce change cost without service extraction; services are split only for specific isolation/scale needs. | Keep the modular monolith and enforce existing dependency/authority seams. |
| SCALE-02 | Shopify, [Pods Architecture](https://shopify.engineering/a-pods-architecture-to-allow-shopify-to-scale) | FULL TEXT | Shopify sharded only after vertical database scaling was exhausted and then needed failure isolation. | Tenant podding/sharding is a future measured trigger, not a user-count assumption. |
| SCALE-03 | GitHub, [Partitioning relational databases](https://github.blog/engineering/infrastructure/partitioning-githubs-relational-databases-scale/) | FULL TEXT | GitHub introduced virtual schema domains before physical partitioning after primary load/incidents became material. | Preserve domain boundaries now; do not add Vitess, replicas or sharding without database evidence. |
| SCALE-04 | GitHub, [May 2026 availability report](https://github.blog/news-insights/company-news/github-availability-report-may-2026/) | FULL TEXT | Service/domain extraction addressed observed shared-failure and capacity problems at GitHub scale. | This is counterevidence to speculative extraction at Strategy OS scale. |
| SCALE-05 | Uber, [2026 payments retrospective](https://www.uber.com/ca/en/blog/ubers-payments-platform/) | FULL TEXT | Specialized stores, Kafka, workflows and batching answered billions of entities and extreme hot-key pressure. | Preserve zero-sum and audit invariants; reject the machinery until comparable measured constraints exist. |
