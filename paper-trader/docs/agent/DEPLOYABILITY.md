# Release obligations

V0 has no completed release or deployed-journey claim in the current documentation. Local foundation checks apply only to their recorded source and scope. Use [status](STATUS.md) for current work.

## Candidate checklist

| Boundary | Required evidence |
| --- | --- |
| Customer journey | Clean invited account through strategy/data/research/evidence/monitoring/alerts, including useful rejection and recovery. |
| Identity and security | Exact revision/data/implementation attribution, tenant isolation, session/credential handling and capability refusal. |
| Persistence | Supported migrations, backup/restore, restart recovery and correct cross-plane ownership on the candidate. |
| Runtime | Supported profile, configuration, dependency/build identity, worker lifecycle and observable failures. |
| Providers and commerce | Capability/rights decisions, expiry/recovery, test/live separation and trusted entitlements where enabled. |
| Deployment | Concrete candidate and owner approval; deploy through `paper-trader/scripts/deploy.sh`; verify running identity and repeat the customer journey. |

Do not infer live-money, credentials, production access or destructive authority from a local pass. Keep paper/live books separate and public execution closed in V0.

## Evidence and runbooks

Link a scoped result, command and observed limitation to the affected row when preparing a candidate. Do not append every implementation capsule to this page. Unchanged historical hashes or test totals are not a release rehearsal.

Use [PostgreSQL backup/restore](../operations/postgresql-backup-restore.md), [cutover](../operations/postgresql-cutover.md), [local verification](../operations/local-postgresql-verification.md), [admission](../operations/strategy-admission.md) and [execution leases](../operations/execution-leases.md) for the affected operation.

The earlier phase-by-phase ledger is preserved in [release history](../archive/release/DEPLOYABILITY.md). Its recorded verdicts remain historical; this refactor does not promote or invalidate behavioral evidence.
