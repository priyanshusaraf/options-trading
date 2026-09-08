# Professional engineering reference programme

These are standing project instructions adopted by the owner on 28 August 2026. Read the [preserved professional engineering programme](STRATEGY_OS_PROFESSIONAL_ENGINEERING_REFERENCE_PROGRAM_2026-08-28.md) for architecture, correctness, recovery, research validity, security, dependency and phase/release reviews. Root `AGENTS.md` routes relevant tasks here.

## How to apply the instructions

Follow the owner's short chain: **source identifies a relevant failure → check our code → reproduce or substantiate it → make the smallest justified change → verify the outcome**. Record assumptions and, where affected, migration/recovery behavior. High-risk recommendations need a conceptual or independent source plus official implementation evidence or a direct experiment. If the problem is absent, record a future trigger and move on. A respected source alone never requires a new database, queue, framework or deployment unit.

Keep source inventory, retrieval, reading, applicability and verification separate. Update the [source registry](source-registry.yaml) and [claim registry](claim-registry.jsonl) when a source is actually checked or a claim influences a decision. Do not turn an unreviewed registry entry into an accepted dependency or a product promise.

## Authority and release labels

The original owner file is preserved byte for byte, with [provenance](owner-source-provenance.json). Its V1.1 and other release labels describe reference topics; they do not silently undo the accepted hybrid rebase or change the active product capsule. Resolve timing through the current owner decisions, [canonical reconciliation](../strategy-os-v1-v2-v3/CANONICAL-DOCUMENT-RECONCILIATION.md), and the [current programme pointer](../agent/CURRENT.md). Document a conflict before proposing a scheduling change.

The V2 [Kleppmann review mandate](../research/kleppmann/STRATEGY_OS_KLEPPMANN_AND_PROFESSIONAL_ENGINEERING_REVIEW_PROMPT_V2_2026-08-28.md) is a separate, larger review assignment. Its [intake capsule](../research/kleppmann/INTAKE-CAPSULE.md) records this task's bounded work; completing intake is not completing that mandate.

The [29 August artifact/DDIA 2e packet](reading-packets/2026-08-29-kleppmann-artifacts-ddia2e.md)
continues that lineage. It does not close the full mandate or implement its findings.

## Refresh and evidence

The owner's [5 September database reading review](reading-packets/2026-09-05-planetscale-database-failures.md) covers all eight articles in the Sam Lambert thread. It records one reproduced backup-TLS defect, targeted verification work, absent patterns and explicit triggers for deferred topology changes. Use those dispositions rather than adopting the vendor's stack.

Run explicit dated refreshes at phase starts, before release freeze, after serious incidents or architecture defects, before major dependency adoption, and after material provider changes. This instruction does not schedule a background task. Record sources checked, version changes, findings, rejected advice, and no-change decisions in `refresh-reports/`.

Use `reading-packets/` for bounded reading assignments, `source-notes/` for reviewed claims, `incident-library/` for evidence-backed failure cases, and `rejected-patterns/` for explicit exclusions. Raw third-party downloads belong under ignored `.agent/runs/`, not in this directory. Public-source access and code reuse remain subject to their licences and the repository gates.

No new runtime, database, workflow engine, cache, queue, cryptographic scheme, live authority or deployment follows merely from this programme. Deployment impact of this instruction intake: none.
