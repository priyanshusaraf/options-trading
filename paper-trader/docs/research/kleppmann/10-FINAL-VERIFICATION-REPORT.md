# Intake verification report

Date: 28 August 2026. **The bounded intake/inventory and first job-claim packet passed its validation checks. The full V2 mandate remains OPEN.** The filename follows the requested output convention; it does not claim full-corpus or release acceptance.

## Decision

Install the professional engineering programme as durable project instructions. Preserve the current job-claim implementation for the specific stale-writer contract tested here. Continue the remaining review through bounded packets; do not introduce new infrastructure on the strength of source titles or broad distributed-systems advice.

## Repository context and changes

- Worktree: `/Users/priyanshusaraf/dev/options-trading/.claude/worktrees/codex-execution-foundation`.
- Branch: `codex/execution-foundation`; starting and last checked HEAD: `de6faae3e97cf5537338bee2143350e53f70da1c`. No commit or deployment was made.
- Initial baseline: 633 dirty status entries, 1,853 hashed files, eight worktrees, `origin` remote. Full context is in `root/orientation.log` under the evidence root below. Remote credential values are not reproduced in this report.
- Own inherited-file change: append the professional-reference instructions to root `AGENTS.md`, preserving its inherited text. Added both source documents byte for byte, provenance, registries, inventory/reading records, bounded source-to-code findings, next scopes, and three audit scripts.
- Five other inherited paths changed concurrently: `backend/app/ir/first_party/analytical_v2/core_math.py`, `backend/tests/test_indicator_accuracy_core_math.py`, the F02 capsule, `docs/agent/CURRENT.md`, and `docs/agent/programme/PROGRAMME.json`. All five belong to ongoing product work; this task did not edit or revert them. No missing inherited files were observed. See `root/protected-check.json` and the final validation receipt.
- The job repository and selected test files stayed outside this task's write scope. Evidence is from a dirty, concurrently changing checkout, not clean exact-HEAD release evidence.

Technologies inspected: Python/FastAPI/Uvicorn, SQLAlchemy, Alembic, SQLite and PostgreSQL-capable database paths, pandas/NumPy, persisted `BacktestRun` claims with local workers, execution-change event production, and the legacy React/Vite/TypeScript frontend manifest. Broker/provider code remains separate; no provider was contacted by tests. Installed versions are captured in `root/technology-receipt.log`. Docker and psql were absent from PATH; no claim is made about all installed tools or production database state.

## Corpus coverage

| Measure | Observed |
| --- | ---: |
| First-party content records | 373 |
| Successfully fetched | 368 |
| HTML / PDF responses | 339 / 29 |
| First-party error / deliberately deferred downloads | 1 / 4 |
| Byte-identical duplicate records | 6 |
| Direct external links awaiting triage | 2,016 |
| Image/media assets inventoried | 459 |
| Fully read first-party articles | 2 |
| Technical images directly inspected | 3 |
| PDF pages text-extracted | 954 |
| PDFs visually/deep reviewed | 0 |
| Videos / transcripts reviewed | 0 / 0 |
| Initial Tier 0 priority seeds / unscreened records | 20 / 353 |

The HTML-discovered first-party queue exhausted. PDF annotation links, external one-hop artifacts/courses, alternate-format/semantic deduplication and full priority screening remain incomplete. This is not an exhaustive completed corpus review. Page retrieval and extraction never set `fully_read`.

The one HTTP 404 is the musical-site `die-tuerme-des-februar/tdf.html` page. Deferred files are three ZIPs and one XML example; they are not classified as inaccessible. See [inaccessible records](inaccessible-sources.md), [coverage JSON](coverage.json), and [top twenty initial reading priorities](05-PRIORITY-READING-MAP.md). Numeric relevance scores remain null rather than fabricated. Historical database/Redis statements are treated as dated; current behavior needs current official evidence or tests.

## Findings and decisions

The [source/code packet](source-notes/job-claim-fencing.md) and [gap matrix](04-ARCHITECTURE-GAP-MATRIX.md) distinguish observations from missing proof.

1. The inspected database writers already reject a replaced claimant using an atomic owner/run/token predicate. **KEEP** this design for that boundary.
2. The reviewed test named claim race is sequential. An independent synchronized two-session probe now exercises same-run contention against the real repository on a private SQLite database. This does not establish that all other race tests were absent.
3. PostgreSQL failover, full-process recovery, remote side effects and all-domain job lineage remain unproven by this packet. They are explicit remaining evidence obligations, not automatically new product bugs.

**No new current product bug was confirmed.** Active F02 is pre-existing negative evidence owned by the separate numerical correction. No critical fix, accepted new ADR, schema/API migration, frontend change, live action or release approval is claimed.

## Verification

Evidence root: `.agent/runs/kleppmann-professional-review-20260828/`.

| Check | Observed result | Evidence |
| --- | --- | --- |
| Owner source preservation | Both copied documents match their source SHA-256 | `root/preserve-owner-documents.log`; tracked `owner-source-provenance.json` |
| Selected existing tests | 53 passing progress marks, 100%, process exit 0 | `root/existing-job-claim-tests.log` |
| Independent simultaneous claim/takeover probe | PASS: one claimant, stale terminal rejected, foreign heartbeat rejected, current terminal persisted | `root/independent-claim-green.log` |
| Token predicate removed in isolated audit process | Expected exit 1 at stale-claim assertion: mutation killed | `root/independent-claim-mutant.log` |
| New clean audit process | PASS; no mutation persisted on disk | `root/independent-claim-restored.log` |
| PDF extraction | 29 PDFs / 954 pages; parser warnings retained; none marked reviewed | `root/pdf-metadata.log` |
| Document/registry/link/scope checks | PASS; local links, schemas/counts, source hashes, unchanged job/test bytes and concurrent-edit accounting checked | `root/validation.json`; `root/validate-intake-final.log` |

Selected test command, from `paper-trader/backend`:

```sh
PT_DISABLE_DOTENV=1 .venv/bin/python ../../.codex/scripts/run_logged.py --task kleppmann-professional-review-20260828 --assignment root --label existing-job-claim-tests --cwd . -- .venv/bin/python -m pytest -q tests/test_no_live_under_pytest.py tests/test_backtest_job_claims.py tests/test_backtest_batch_persistence.py
```

Independent probe, same directory:

```sh
PT_DISABLE_DOTENV=1 .venv/bin/python ../docs/research/kleppmann/scripts/probe_job_claim.py
PT_DISABLE_DOTENV=1 .venv/bin/python ../docs/research/kleppmann/scripts/probe_job_claim.py --mutate-token-fence
```

The mutation command is supposed to fail. Actual runs used the logged wrapper, with separate green/mutant/restored labels. Root conftest creates unique temporary databases, disables dotenv, forces mocked provider/paper execution and checks that live authority is absent before the probe touches data.

The first documentation checker incorrectly appended a newline before comparing the inherited `AGENTS.md` prefix and failed. The direct prefix already contained the original newline. The corrected exact-byte comparison passed; no instruction bytes were changed to satisfy it. The failed `root/validate-intake.log` and successful recheck are retained. Final validation is reproducible with `python3 .agent/runs/kleppmann-professional-review-20260828/root/verify_intake.py` from the repository root.

No full backend/research suite, frontend build, production-engine concurrency test, migration rehearsal, load test, formal proof or clean-environment restore was run. This slice changed no product contract. Those checks must be selected under their owning future capsule. The selected existing suite emitted one Starlette/httpx deprecation warning; no dependency was changed in response.

## Remaining work and rollback

The [remaining plan](07-IMPLEMENTATION-AND-MIGRATION-PLAN.md) assigns exact bounded review scopes and names the accepted V0 stages that consume relevant findings. The full mandate still requires high-priority PDFs/visuals, DDIA 2e, all-domain contingencies, numeric/unit and governance work, credentials, supply chain, portability/restore, UX uncertainty and future seams.

Deployment impact: **none**. Migration: **none**. Rollback removes only this task's new documentation/audit artifacts and appended instruction section. Preserve all inherited and concurrently changed product files. No background automation or separate task was started, and this report does not authorize deployment or live access.
