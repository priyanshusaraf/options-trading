# Security threat model

> Timing amendment: bounded point-in-time reference/events and chart artifacts are now V1 scope. Their data rights, export, vendor access and security controls remain unresolved gates. Deeper non-OHLCV domains remain later.

Status: architecture recommendation

## Protected assets

- private Strategy graphs and source;
- research hypotheses, data, trials, findings, and evidence;
- broker credentials and account identity;
- deployment and execution authority;
- orders, fills, positions, capital, and accounting;
- user sessions and organization membership;
- data-provider entitlements and licensed data;
- immutable content identities and audit records;
- deployment, backup, and restore credentials;
- future external signals, chart artifacts, and Workflow approvals.

## Trust boundaries

1. Browser to API and WebSocket.
2. API to execution database.
3. API or worker to research database.
4. API to journal ledger database.
5. Engine to market-data provider.
6. Execution holder to broker venue.
7. Database metadata to object or file storage.
8. Build and CI to deploy artifact.
9. Support operator to production diagnostics.
10. Future webhook or chart vendor to Strategy OS ingress.
11. Future custom code to host runtime.

## Current controls

- bearer plaintext is hashed before persistence;
- a principal requires active session, user, organization, and membership;
- route actions use a closed vocabulary;
- repositories bind owner scope;
- WebSocket channels derive from server identity;
- inbound WebSocket payload logging is redacted;
- broker credentials use AES-256-GCM with an environment-held key;
- credential read occurs late and revocation fails closed;
- strategy content and credentials use different paths;
- paper and live books are separate;
- account execution leases use fence epochs;
- execution commands, intents, and events retain owner and account;
- provider adapters contain raw vendor types;
- generated strategy source uses a strict AST allowlist and no-builtins execution;
- deploy.sh protects environment, database, token, backup, cache, and frontend artifacts;
- no V2 product work can silently enable live IR.

## Current gaps

- full route-action coverage needs ongoing audit;
- support and break-glass product policy is not complete;
- the current log bus is process-local;
- no full supply-chain inventory or retained SBOM gate is proven;
- no general upload-admission system exists;
- arbitrary custom Python is not an implemented product;
- future webhooks have no typed ingress;
- strategy artifact encryption-at-rest claims need deployment evidence;
- managed secret storage and rotation remain production obligations;
- production RPO, RTO, PITR, and off-account retention are unproven;
- bounded V1 reference/event and chart-artifact data rights/export policy remain external decisions; deeper non-OHLCV domains remain later;
- frontend telemetry consent and strategy-privacy controls remain incomplete.

## Threat catalogue

| Threat | STRIDE class | Severity | Current control | Required action |
| --- | --- | --- | --- | --- |
| Cross-tenant graph read | information disclosure | Critical | owner-scoped repository and principal | permanent direct-object tests on every resource |
| Cross-tenant cache hit | information disclosure | Critical | owner in protected cache keys | complete cache-key audit |
| Broker credential leak | information disclosure | Critical | encrypted row, environment key, redaction | rotation drill and least-privilege service role |
| Credential substitution | spoofing and elevation | Critical | owner/account-scoped connection and broker registry | signed or audited connection changes |
| Unauthorized arm or kill | elevation and denial | Critical | owner action and execution access checks | policy-version audit and race tests |
| Stale session after membership removal | elevation | High | active membership checked on resolution | HTTP and WebSocket revocation tests |
| WebSocket topic forgery | information disclosure | Critical | server-derived channel | keep client topics non-authoritative |
| Strategy IP in logs | information disclosure | High | payload redaction and bounded logging | structured-field allowlist |
| Strategy IP in telemetry | information disclosure | High | no need to collect logic | consented aggregate event schema |
| Direct webhook to order | elevation | Critical | no current ingress | typed signal boundary and normal admission |
| Replayed webhook | spoofing | High | absent | signature, timestamp, nonce, deduplication |
| Custom code network or file access | elevation | Critical | generated code AST boundary | separate sandbox process before arbitrary Python |
| Sandbox escape | elevation | Critical | arbitrary tier absent | threat model, OS isolation, resource and syscall limits |
| CSV formula injection | tampering | High | no V1 upload product path proven | neutralize formulas in exports and previews |
| Decompression bomb | denial | High | bounded current raw segments | streaming size, ratio, row, and time limits |
| Malformed timestamp | tampering | High | aware time checks in authority facts | maintain pre-coercion checks for every importer |
| Provider payload correction rewrites history | tampering | Critical | immutable correction lineage | never update old observation in place |
| Dependency compromise | tampering | Critical | pinned requirements only partly established | lock, SBOM, signature, vulnerability gate |
| Secret in source or history | information disclosure | Critical | ignored environment and credential vault | Gitleaks or equivalent release check |
| CI credential theft | elevation | Critical | not fully inspected here | short-lived CI identity and protected environment |
| Backup theft | information disclosure | Critical | manifest excludes secrets, encryption plan open | encrypted off-account retention |
| Restore old-primary split brain | tampering | Critical | old-primary isolation and higher lease epoch | production rehearsal |
| Support misuse | elevation | Critical | no ordinary support graph view | explicit diagnostics and break-glass policy |
| Chart artifact tampering | tampering | High | feature absent | content address and exact Strategy dependency |
| Universe manipulation | tampering | High | feature absent | immutable definition, input authority, and evaluation receipt |
| Approval detached from reviewed facts | elevation | Critical | current research decisions are exact in bounded paths | exact approval envelope and stale-on-change |
| Reservation forgery | elevation | Critical | feature absent | account lease, transaction lock, immutable decisions |
| Provider entitlement misuse | repudiation and legal | High | provider contract facts exist | licence and permitted-use gate at export and deployment |

## Tenant and authorization rules

1. Derive identity server-side.
2. Authorize once at the command boundary.
3. Query by full owner and account scope.
4. Keep public and private data classifications explicit.
5. Record actor and authority version for consequential actions.
6. Keep authorization separate from admission, risk, and execution authority.
7. Deny an unclassified state-changing route.
8. Keep service principals narrower than human owners.

## Credential policy

- Store only authenticated ciphertext.
- Keep the key outside databases and deploy artifacts.
- Record key fingerprint for rotation.
- Do not log the fingerprint to user-visible channels.
- Read credentials at command time.
- Revocation stops the next command.
- A decrypt failure blocks the connection.
- Broker-specific secret bundles remain inside venue builders.
- Never use one broker's credential at another broker's adapter.

## Custom code policy

Tier 1:

- generated or formula code;
- closed AST and call vocabulary;
- no imports, attributes, file, network, or broker access;
- content-addressed implementation;
- eligible for research and later admitted runtime after normal evidence.

Tier 2, future:

- arbitrary user Python in an isolated process;
- no production network by default;
- read-only staged inputs;
- CPU, memory, file, process, and wall-clock limits;
- no inherited credential or environment;
- paper or research only until a separate owner gate;
- output schema validation;
- image and dependency pinning;
- kill and cleanup evidence.

Do not represent Tier 2 as cryptographic containment.

## Upload admission

Future uploads require:

- byte and decompression bounds;
- media type and parser allowlist;
- quarantine;
- timestamp and schema review;
- formula neutralization;
- canonical object address;
- malware and archive traversal checks where applicable;
- owner and retention;
- no automatic execution eligibility;
- clear warnings for uncertain timezone, corporate action, and licensing.

## Supply chain

Proposed controls:

- locked Python and frontend dependencies;
- hashes or signed artifacts where supported;
- SBOM for release artifacts;
- Gitleaks for secret detection;
- Semgrep for targeted unsafe patterns;
- Trivy or equivalent for built images;
- Syft and Grype or equivalent for inventory and vulnerability review;
- dependency update review against exact affected contracts.

Tool adoption needs its own deployability capsule. Do not create several overlapping scanners without one owner.

## Incident response

For a suspected credential or execution compromise:

1. disarm affected account;
2. keep risk-reducing exits available under verified ownership;
3. revoke connection;
4. rotate broker and vault credentials;
5. preserve logs, commands, order events, and lease history;
6. reconcile broker account;
7. isolate affected build;
8. restore only from verified authority;
9. record scope and user impact;
10. add a permanent regression and update this threat model.

## Required tests

1. Every cross-tenant direct object route.
2. Revoked membership on an existing socket.
3. Credential ciphertext mutation.
4. Wrong vault key.
5. Secret redaction in logs, errors, backups, and receipts.
6. Broker adapter substitution.
7. Stale approval after any material input change.
8. Webhook replay and timestamp expiry.
9. Archive traversal and decompression bounds.
10. Formula injection in exported CSV.
11. Custom-code file and network attempts.
12. Restore old-primary split brain.
13. Support diagnostic cannot read private graph.
14. Telemetry cannot reconstruct a graph.
15. Capability entitlement expires before deployment.

## Verdict

KEEP + HARDEN current tenancy and credential foundations. DEFER external ingress and arbitrary custom code until dedicated security capsules. No production-security claim follows from this static threat model.
