# Authorization comparison packet

## Current Strategy OS boundary

The current request principal resolves:

- bearer digest;
- active session;
- active user;
- active organization;
- active membership;
- role;
- closed action vocabulary.

Repositories scope resource reads by owner. Money and credential commands retain explicit owner-only actions. WebSocket delivery uses server-derived owner and broker-account channels.

This is the correct V1 base. A separate policy service is not required.

## Comparison

| System | Useful lesson | Limit |
| --- | --- | --- |
| Current Strategy OS | typed action vocabulary, centralized request classification, owner-scoped repositories | action coverage and support access still need complete review |
| Casbin | subject, domain, object, and action at one decision boundary | generic matcher strings and mutable policy history |
| OpenFGA | immutable authorization models and relationship tuples | another service; does not enforce database scoping or trading safety |
| OpenFGA sample stores | model, tuples, request context, grants, and denials in one fixture | toy domains and no storage isolation |

## Permission matrix

| Resource | Viewer | Member | Admin | Owner | Service principal | Support |
| --- | --- | --- | --- | --- | --- | --- |
| Tenant and membership | read own tenant | read own tenant | manage non-owner members | manage tenant | no default | diagnostic only |
| Strategy | read | create and edit draft | archive | all tenant actions | exact job-scoped read | no content by default |
| Strategy revision | read | publish when granted | archive aliases | all | exact immutable read | receipt only |
| Universe definition and snapshot | read | create and evaluate | archive aliases | all | exact evaluation input | summary only |
| Workflow definition | read | create draft | publish and retire | all | exact instance input | status only |
| Dataset | read owned | admit owned | revoke alias | all | exact job-scoped read | quality receipt only |
| Experiment and evidence | read | start and compare | research decision | all | exact job-scoped write | evidence metadata only |
| Broker connection | none | none | none unless explicit future grant | create, rotate, revoke | token use through narrow runtime port | no secret access |
| Deployment | read | no authority by default | research decision only | create, arm, pause, retire | invoke exact command if granted | diagnostics only |
| Position and order | read own when granted | no mutation | no mutation | controlled commands | exact execution command | redacted diagnostic only |
| Break-glass | none | none | none | initiate under policy | execute scoped action | time-bound, approved, audited |

This matrix is a proposed product policy. It is not a current runtime claim.

## Tenancy invariants

1. Server derives user, organization, and broker-account scope.
2. Resource IDs never grant access by themselves.
3. Every query contains the full owner and account predicate before materialization.
4. Cache keys include every answer-changing owner dimension.
5. Public market facts use an explicit public classification.
6. Strategy content and broker credentials use separate access paths.
7. Support cannot browse strategy graphs or source by default.
8. WebSocket channels come from the resolved principal, never a client topic string.
9. Background workers use service-principal identity and exact resource grants.
10. Authorization answers who may ask. Admission, risk, lease, and execution authority decide whether the action may occur.

## Support access policy

Default support data:

- build identity;
- service health;
- refusal code;
- provider state;
- receipt address;
- timestamps;
- bounded redacted diagnostics.

Restricted data:

- graph body;
- custom strategy source;
- raw provider payload;
- credential ciphertext;
- access token;
- broker personal identifiers;
- exact private trading logic.

Break-glass requirements:

- named incident;
- owner approval where possible;
- time-bound grant;
- exact resource and action;
- separate strategy-content and credential permissions;
- immutable audit;
- automatic expiry;
- review after use.

## Strategy IP separation

Do not claim zero-knowledge execution while the server evaluates strategy logic.

V1 controls should include:

- encrypted storage where required;
- strict owner-scoped repositories;
- no support UI for private graph contents;
- telemetry that records feature use without reconstructing strategy logic;
- separate credential and strategy access;
- redacted logs and WebSocket payload diagnostics.

## Authorization test plan

1. Cross-tenant direct object reference for every resource.
2. Same display name under two owners.
3. Same broker account label under two owners.
4. Revoked session on HTTP and WebSocket.
5. User removed from organization while session remains unexpired.
6. Viewer attempts publish, deployment, credential, and execution commands.
7. Member attempts connection and arm commands.
8. Admin attempts owner-only credential access.
9. Service principal uses a resource outside its grant.
10. Cache lookup with another owner's valid content address.
11. WebSocket client requests another tenant channel.
12. Support diagnostic contains no graph, token, or raw broker payload.
13. Break-glass expiry races a command.
14. Policy version changes after a consequential command.
15. Authorization PASS followed by admission or risk refusal remains a refusal.

## Adoption decision

KEEP + HARDEN the current typed action boundary.

Do not install OpenFGA or Casbin now. Reconsider when organization sharing or desk approval requires relations that the fixed role model cannot express. If that trigger fires, retain database tenant scoping and record the exact policy model version for consequential decisions.
