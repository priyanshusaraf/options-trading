# Strategy OS — Razorpay, Google Authentication, Entitlements, and Admin Workstream

**Date:** 29 August 2026\
**Status:** V0 implementation brief\
**Scope:** Test Mode and production-ready architecture; no live charge authorization in this workstream\
**Source policy:** Verify every operational step against current official Razorpay and Google documentation at implementation time.

---

## 0. Outcome

A user should be able to:

```text
sign in securely
→ possess a durable Strategy OS account
→ begin/complete a Razorpay Test Mode checkout
→ have the server verify payment facts
→ receive the correct product entitlement exactly once
→ see billing/account status
```

An authorized operator should be able to inspect and reconcile failures without seeing payment secrets or customer strategy IP.

---

# 1. Human-controlled browser and secret boundary

A browser-capable agent may navigate the Razorpay and Google dashboards, but it must pause for the owner at:

- account selection/sign-in;
- password entry;
- OTP/2FA;
- consent that affects the owner's account;
- API-key generation confirmation;
- any live-mode, KYC, bank, settlement, or domain-verification action.

The agent must never:

- ask the owner to paste a Key Secret into chat;
- print a Key Secret to terminal output;
- save secrets in repository files;
- place server secrets in frontend environment variables or bundles;
- include secrets in screenshots, logs, test fixtures, CI output, or reports;
- enable Live Mode or make a real charge without a separate explicit owner gate.

Preferred secret flow:

```text
owner completes dashboard authentication/OTP
→ key is generated in Test Mode
→ owner/agent writes secret directly into approved local/hosted secret storage
→ only a redacted Key ID suffix and configuration status appear in reports
```

If the current environment cannot securely write the key without exposing it to chat or logs, stop and give the owner a precise one-line secret placement instruction.

---

# 2. Inspect before selecting an integration pattern

Codex must discover:

- current frontend/backend stack;
- auth/session library or managed auth provider;
- user/tenant schema;
- current environment and secret management;
- current deployment domains and callback URLs;
- current pricing/plan decisions;
- whether V0 uses one-time payment, subscription, free trial, invite entitlement, or a combination;
- whether a billing abstraction already exists;
- existing admin/role model;
- current webhook/job mechanism;
- current email/support path.

Do not add a second auth system or billing framework if the existing one can be extended safely.

---

# 3. Google sign-in

## 3.1 Preferred approach

Use the existing framework/provider's maintained Google OpenID Connect integration where one exists.

Otherwise use the current Google Identity Services flow appropriate to the actual web architecture.

Required security behavior:

- use HTTPS in production;
- register the correct web client and exact origins/redirect URIs;
- request only authentication scopes needed for sign-in (`openid`, identity/profile/email as appropriate);
- verify the Google ID token on the backend or through the trusted auth provider;
- validate signature, issuer, audience, and expiry;
- use the stable `sub` claim as the external account identifier;
- do not trust a client-provided Google user ID or email alone;
- create/link the internal user transactionally;
- protect redirect flows against CSRF/state attacks;
- handle revoked/expired sessions;
- support account linking rules without silent takeover;
- avoid requesting unrelated Google API scopes.

## 3.2 Account-linking cases

Define behavior for:

- first sign-in with Google;
- returning Google user;
- existing email/password account with same verified email;
- Google account using a non-Gmail address;
- changed email/profile name;
- disabled/deleted Strategy OS account;
- multiple Google identities;
- owner/admin accounts;
- account deletion and re-registration.

Never merge accounts silently based only on an email string without a reviewed rule.

## 3.3 Session behavior

Verify:

- secure, HttpOnly, SameSite cookie or equivalent maintained session;
- session fixation prevention;
- logout/revocation;
- expiry/refresh;
- CSRF protection where required;
- tenant/user authorization on every server request;
- no identity data in insecure local storage if avoidable;
- websocket session authorization and reconnect behavior.

---

# 4. Razorpay Test Mode setup

Current official documentation should be rechecked, but the expected owner-assisted flow is:

1. Open the Razorpay Dashboard.
2. Sign in with the owner's intended merchant account.
3. Switch explicitly to **Test Mode**.
4. Navigate to Account & Settings → API Keys under website/app settings.
5. Generate the Test Key.
6. Save the Key ID and one-time-visible Key Secret directly into approved secret storage.
7. Configure a test webhook endpoint and a distinct webhook secret.
8. Create a test plan if recurring subscriptions are the chosen V0 business model.
9. Never switch to Live Mode during this workstream.

Only the public Key ID may reach browser configuration. The Key Secret remains server-side.

---

# 5. Internal billing model

Do not couple every page request to a live Razorpay lookup.

Recommended internal concepts, adapted to the current codebase:

```text
BillingPlan
ExternalPlanMapping
BillingCustomer
CheckoutAttempt or PaymentOrder
PaymentRecord
SubscriptionRecord if recurring
WebhookReceipt
Entitlement
EntitlementTransition
BillingAuditEvent
```

## 5.1 Entitlement as product authority

Strategy OS controls what a user can access through an internal entitlement record.

Razorpay provides external payment/subscription facts. Verified facts cause idempotent entitlement transitions.

Never authorize paid capability based solely on:

- a client-side “success” callback;
- a query parameter;
- a screenshot;
- an unverified payment ID;
- the presence of a Razorpay customer record.

## 5.2 Minimal states

Adapt to chosen business model, but preserve ambiguity explicitly.

Possible payment states:

```text
CREATED
ATTEMPTED
AUTHORIZED
CAPTURED
FAILED
REFUNDED
PARTIALLY_REFUNDED
DISPUTED
UNKNOWN_RECONCILIATION_REQUIRED
```

Possible subscription states:

```text
CREATED
AUTHENTICATED
ACTIVE
PENDING
HALTED
PAUSED
CANCELLED
COMPLETED
EXPIRED
UNKNOWN_RECONCILIATION_REQUIRED
```

Possible entitlement states:

```text
TRIAL
ACTIVE
GRACE
SUSPENDED
EXPIRED
REVOKED
```

Do not collapse provider state and product access state into one Boolean.

---

# 6. Checkout/order/subscription flow

## 6.1 Server creates canonical external intent

The backend creates the Razorpay order or subscription using server credentials.

Persist before presenting checkout:

- internal attempt ID;
- user/tenant;
- plan/version;
- exact amount and currency;
- external order/subscription ID;
- idempotency/deduplication identity;
- creation time and expiry;
- status.

The frontend receives only the data required by Checkout, including the public Key ID and server-created external ID.

## 6.2 Client callback is provisional

On checkout callback:

- send identifiers/signature to the backend;
- verify using official SDK/helper and server secret;
- update a provisional verified state;
- await or reconcile canonical webhook/payment state according to the integration design;
- show the user a truthful pending/success/failure state.

## 6.3 Amount and product binding

The server must derive plan amount and currency from trusted configuration/database, not client input.

Verify that:

- order/subscription belongs to the current user;
- amount and currency match the expected plan;
- payment belongs to the expected external order/subscription;
- a previously consumed order cannot grant multiple entitlements;
- plan changes are versioned.

---

# 7. Webhook contract

## 7.1 Security

- receive the **raw request body**;
- verify `X-Razorpay-Signature` using the configured webhook secret;
- reject invalid signatures before state changes;
- do not reuse the API Key Secret as the webhook secret;
- redact payload fields from logs according to policy;
- use current official SDK/helper where available.

## 7.2 Durability and idempotency

Persist a webhook receipt keyed by a stable provider event identity or a content-derived fallback designed for the actual payload.

Processing must tolerate:

- duplicates;
- retries;
- delayed events;
- out-of-order events;
- process death after receipt but before effect;
- effect committed but response lost;
- unknown entity;
- provider/dashboard replay.

A recommended flow:

```text
receive raw payload
→ verify signature
→ durably record receipt/idempotency state
→ return success within provider requirements
→ process through existing durable job mechanism if needed
→ apply state transition transactionally
→ record effect and audit
→ reconcile inconsistencies
```

Do not introduce a new queue merely because a general integration guide mentions one; use the current durable mechanism if it satisfies the contract.

## 7.3 State transitions

Transitions should be monotonic where provider semantics permit, but do not simply compare enum order. Define valid transitions by event/entity type.

Store impossible or conflicting transitions for reconciliation rather than silently overwriting history.

---

# 8. Admin and reconciliation

Authorized admin view should include:

- user and tenant ID;
- current plan and entitlement;
- checkout/order/subscription/payment IDs;
- redacted provider status;
- webhook receipts and processing status;
- last reconciliation;
- failures and actionable reason;
- entitlement transition history;
- manual recovery controls with confirmation and audit.

Manual controls should be narrow:

- retry processing;
- fetch/reconcile current provider entity where supported;
- grant/revoke a bounded manual invite entitlement;
- suspend account;
- annotate support outcome.

Do not provide an unrestricted “set paid = true” action without reason, role, and audit.

---

# 9. Test plan

## Authentication

- valid Google sign-in;
- invalid/tampered token;
- wrong audience/issuer;
- expired token;
- account linking;
- duplicate callback;
- logout/session expiry;
- tenant authorization;
- websocket reconnect;
- disabled account.

## Checkout/payment

- successful Test Mode payment;
- closed checkout;
- failed payment;
- duplicate submission;
- page refresh;
- network timeout;
- wrong amount/currency;
- mismatched order/user;
- invalid checkout signature;
- captured/uncaptured behavior as applicable;
- refund/cancellation state if supported.

## Webhooks

- valid signature;
- invalid signature;
- parsed-body instead of raw-body regression;
- duplicate delivery;
- out-of-order events;
- delayed event;
- unknown entity;
- process death before/after effect;
- provider replay;
- old/new webhook secret during rotation.

## Subscription, if used

- plan created in Test Mode;
- authentication payment;
- activation;
- subsequent test charge;
- failed charge;
- halted/pending;
- cancellation at end/immediate according to product policy;
- completion/expiry;
- grace/access behavior.

## Entitlement

- exactly one grant;
- renewal;
- grace period;
- expiry;
- cancellation;
- admin manual grant/revoke;
- billing provider unavailable;
- reconciliation corrects drift;
- no client-side bypass.

## Security/secrets

- Key Secret absent from frontend bundle;
- repository secret scan;
- logs redacted;
- CI output redacted;
- unauthorized admin blocked;
- strategy IP unavailable in billing support path.

---

# 10. Deployment configuration

Expected names should adapt to the repository, for example:

```text
RAZORPAY_KEY_ID                 # public identifier; still managed by environment
RAZORPAY_KEY_SECRET             # server secret
RAZORPAY_WEBHOOK_SECRET         # distinct server secret
RAZORPAY_MODE=test
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET            # only if the chosen server flow/framework requires it
APP_BASE_URL
AUTH_CALLBACK_URL
```

Requirements:

- `.env.example` contains names only, never values;
- local/test/staging/production are separate;
- CI uses secret injection;
- startup validates required configuration;
- production refuses test/live key mismatch;
- key rotation procedure exists;
- reports show only redacted identifiers.

---

# 11. Live-mode gate, explicitly outside this task

Before accepting real payments, require a separate owner-approved checklist covering:

- business/KYC readiness;
- live website/domain details and policies;
- final pricing and tax treatment;
- privacy/terms/refund/cancellation pages;
- HTTPS and production webhook URL;
- Live API keys generated and stored securely;
- test keys removed from production;
- production signature/webhook/reconciliation tests;
- support and refund procedure;
- monitoring and alerting;
- legal/accounting review appropriate to the business.

This workstream ends with Test Mode verified and a documented live gate.

---

# 12. Required Codex artifacts

Create:

```text
docs/v0/billing-auth/
├── 00-CURRENT-STACK-AND-DECISIONS.md
├── 01-GOOGLE-IDENTITY-AND-ACCOUNT-LINKING.md
├── 02-SESSION-TENANCY-AND-AUTHORIZATION.md
├── 03-RAZORPAY-TEST-MODE-SETUP-RECEIPT.md
├── 04-BILLING-DOMAIN-AND-STATE-MACHINES.md
├── 05-CHECKOUT-AND-SERVER-VERIFICATION.md
├── 06-WEBHOOK-IDEMPOTENCY-AND-RECONCILIATION.md
├── 07-ENTITLEMENT-AUTHORITY.md
├── 08-ADMIN-AND-SUPPORT-BOUNDARY.md
├── 09-SECRET-ROTATION-AND-REDACTION.md
├── 10-TEST-MATRIX.md
├── 11-LIVE-MODE-GATE.md
└── 12-FINAL-VERIFICATION-REPORT.md
```

The setup receipt must contain no secret values.

---

# 13. Official references to verify at execution time

- Razorpay API keys and Test/Live modes: `https://razorpay.com/docs/payments/dashboard/account-settings/api-keys/`
- Razorpay payment quickstart: `https://razorpay.com/docs/payments/quickstart/`
- Razorpay Standard Checkout: `https://razorpay.com/docs/developer-tools/integrations/standard-checkout/`
- Razorpay subscription testing: `https://razorpay.com/docs/payments/subscriptions/test/`
- Razorpay webhook FAQs/signature behavior: `https://razorpay.com/docs/webhooks/faqs/`
- Google OAuth overview/policies: `https://developers.google.com/identity/protocols/oauth2`
- Google backend ID-token verification: `https://developers.google.com/identity/sign-in/web/backend-auth`
- Google Sign in with Google best practices: `https://developers.google.com/identity/siwg/best-practices`

Record retrieval date and any changed official guidance in the final report.
