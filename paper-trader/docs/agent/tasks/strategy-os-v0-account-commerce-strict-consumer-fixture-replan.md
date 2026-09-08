---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-account-commerce-strict-consumer-fixture-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "important_read_only_account_commerce_consumer_fixture_replan",
  "goal": "Define the smallest fresh successor that closes V0-ACAPI-EG-001 with strict Precision Slate response validation and an executable consumer-owned abort seam while preserving the already-passing unregistered API.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "One zero-product-write decision freezes the full response field/nullability/time/uniqueness/state matrix, malformed vectors, deterministic abort seam, exact successor paths and one fresh review route."},
  "risk_tags": ["important", "auth", "privacy", "api", "frontend-contract", "test-evidence", "replan"],
  "depends_on": ["strategy-os-v0-account-commerce-unregistered-api-foundation"],
  "dependency_gate": {"recheck_verdict": ".agent/runs/strategy-os-v0-account-commerce-unregistered-api-foundation/review/recheck-verdict.json", "recheck_verdict_sha256": "38c2bcbafb2d049083fea96b3ea2903ba68e53cbd9a0262d515febba68861647", "closed": ["V0-ACAPI-CR-001"], "open": ["V0-ACAPI-EG-001"], "policy": "Preserve the accepted route semantics and concurrency correction; plan only the missing consumer strictness and abort evidence."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-account-commerce-unregistered-api-foundation/review/recheck-verdict.json", "sections": ["QUALITY", "open_gaps", "independent_checks", "nonclaims"]},
    {"path": ".agent/runs/strategy-os-v0-account-commerce-unregistered-api-replan/route-matrix.json", "sections": ["precision_slate_consumer"]},
    {"path": "paper-trader/backend/tests/test_v0_account_commerce_routes.py", "sections": ["PrecisionSlateConsumerFixture", "test_precision_slate_consumer_contract_fixture"]},
    {"path": "paper-trader/backend/AGENTS.md", "sections": ["API and authentication constraints"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-strict-consumer-fixture-replan.md", ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-strict-consumer-fixture-replan.md", ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json"],
  "scope": ["Freeze every access/status/profile/trial success field, exact type, enum, nullability, UTC RFC3339 representation, allowed/unique field codes and cross-field state/source/time consistency.", "Define adversarial malformed vectors for every field family, including nested objects, arrays, booleans, non-finite/numeric time values, duplicate codes and secret-bearing coupon/profile values.", "Define an executable consumer-owned transport timeout/abort seam and deterministic slow-response rejection; do not claim TestClient timeout metadata as cancellation evidence.", "Name one smallest successor that changes only the account-commerce route test consumer fixture and its evidence unless inspection proves a producer defect.", "Keep the passing API route semantics, simultaneous retry correction, shared registration, external frontend, providers, production data, money and deployment untouched."],
  "acceptance": ["Decision distinguishes producer correctness from consumer test strictness and preserves V0-ACAPI-CR-001 closure.", "Response matrix and malformed corpus cover every declared success field and privacy-bearing cross-type value.", "Abort contract names an injectable seam, exact bound and deterministic rejection/restoration test without external network or sleeps.", "Successor owns exact test/evidence paths, one Important review and no backend route/product path by default.", "Architecture passes and protected hashes remain identical."],
  "test_plan": ["Read-only inspection of the immutable recheck, route matrix and current fixture; architecture and protected-manifest checks only. Executable correction tests belong to the successor."],
  "risk_classification": {"tier": "Important", "reason": "The missing fixture is an auth/privacy consumer-contract proof, while the API producer remains unregistered and SPEC-passing."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_account_commerce_strict_consumer_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "read-only-consumer-contract-replan", "depends_on": [], "write_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-strict-consumer-fixture-replan.md", ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-replan"], "output": ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-replan/decision.json"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_account_commerce_strict_consumer_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Read-only evidence replan; the corrective successor receives the Important review.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-replan/decision.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-strict-consumer-fixture-replan.md", ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-replan/decision.json", "verdicts": ["CONSUMER_CONTRACT", "PRIVACY", "ABORT", "SUCCESSOR"], "max_rechecks": 0},
  "owner_gates": ["No backend/frontend product edit, shared registration, provider/Google/email/Razorpay network or credentials, production data, money, deployment or release claim."],
  "stop_conditions": ["Inspection reveals a producer-schema defect rather than test-only weakness.", "A real abort proof requires external network or production frontend ownership.", "Concurrent ownership appears on the exact successor test path."],
  "deployment_impact": {"classification": "none; read-only consumer-contract replan", "highest_claim": "locally_runnable unregistered API", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No API/product/frontend implementation, route registration, provider billing, payment/refund, deployment, release readiness or V0 completion."]
}
---

# Account-commerce strict consumer-fixture replan

Plan only the smallest fresh successor for the final consumer-contract evidence
gap. Preserve the SPEC-passing API and its closed concurrency finding.

## Sealed replan receipt

Decision: `KEEP + HARDEN + API PRESENTATION CORRECTION`.

The read-only owner preserved closed `V0-ACAPI-CR-001` and assigned open
`V0-ACAPI-EG-001` to one fresh Important successor. Direct executable inspection
also opened `V0-ACAPI-PD-001`: before an entitlement event, the unchanged API
returns internal `UNKNOWN` through both public access-state fields. The narrow
successor boundary maps only that valid internal no-row fact to public
`INACTIVE` in `account_commerce_routes.py`; service and repository authority
semantics remain protected.

The successor proposal owns only the route presentation file, its existing route
test file, a fresh capsule and its evidence. It freezes the complete four-schema
field/type/nullability/canonical-UTC/uniqueness/cross-field matrix, the
malformed/privacy-bearing corpus, and a consumer-owned injectable abort seam with
deterministic cooperative slow-response rejection. It removes the TestClient
timeout claim and requires one fresh Important `SPEC PASS` / `QUALITY PASS`
review for both open findings.

Artifacts:

- decision: `.agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-replan/decision.json` (`578867c7af8c0204a7e9899cd9d21f4ecdea042ef242201ac156d04f91861d90`)
- successor capsule: `.agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-replan/successor-correction-capsule.md` (`6aa5a5ede8e4c52e0c0ecfe7e1e1aad6029d69b02557f7ada04e3721c5eff25d`)
- response matrix: `.agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-replan/response-contract-matrix.json` (`fff896b02560cfc48c81888499f545cd669106bee2c03921a676b8e510b385d0`)
- malformed corpus: `.agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-replan/malformed-corpus.json` (`74d1658f90f17193aa318d86002727f33780c5f709fd00e15d012a4e06b22fd2`)
- report: `.agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-replan/report.md` (`2d9b9074b618b5f7aebd0b95eeb190243778dfae3df52581b3896d24d8c5c45a`)
- protected manifest: `.agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-replan/protected-manifest.json` (`dd61b566ad1f949ec61c444496e869c06898906ce73a2181efea916cb921cbcb`)
- seal: `.agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-replan/replan-seal.json` (`28df04e09cf750dbcc35e4d7f3e5a6b24f0d2ade6bf69c9188648504e8e4a6f9`)

Architecture validation passed across 473 files with zero failures. Every exact
protected file and all three protected tree digests matched the pre-write
baseline. No backend/frontend product, test, service, repository, control,
CURRENT, PROGRAMME, registration, provider, network, credential, production,
money or deploy path changed. This receipt does not implement or close either
open finding and makes no release, deployment or V0-complete claim.
