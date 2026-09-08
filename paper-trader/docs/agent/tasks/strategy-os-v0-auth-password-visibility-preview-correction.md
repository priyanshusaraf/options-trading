---
{
  "id": "strategy-os-v0-auth-password-visibility-preview-correction",
  "phase": "v0",
  "status": "accepted",
  "kind": "important_frontend_auth_usability_correction",
  "goal": "Add an accessible show/hide control to every password entry owned by AuthGate and verify the existing preview login without changing authentication semantics.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "All AuthGate password fields have independent keyboard-accessible visibility controls, login remains transport-identical, the preview journey passes, an isolated control-removal ablation turns RED and exact restoration returns GREEN."},
  "observable_outcome": "A user can reveal or hide the password being entered through an eye control while login, enrollment, password change and sign-out-all continue to submit the same in-memory values over the existing TLS/session boundary.",
  "risk_tags": ["important", "frontend", "authentication", "accessibility", "privacy"],
  "required_skills": ["strategyos-repo-orientation", "auth-and-session-hardening", "accessibility-audit", "running-strategy-os-safely", "frontend-design", "risk-weighted-verification"],
  "depends_on": ["strategy-os-v0-auth-session-transport", "strategy-os-v0-frontend-product-acceptance-recovery"],
  "dependency_gate": {"preview_origin": "https://127.0.0.1:5187", "api_origin": "https://127.0.0.1:8090", "schema": "0051", "real_login_probe": "PASS_200_WITH_STORED_ARGON2_MATCH", "policy": "Use only the existing synthetic preview account and local runtime. Never place a password, verifier, cookie, invitation or token in source, logs, screenshots, test names, URLs, storage or evidence."},
  "required_docs": [
    {"path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.tsx", "sections": ["signed-out form", "account password forms"]},
    {"path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.test.tsx", "sections": ["identity bootstrap", "invitation form", "CSRF and logout"]},
    {"path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css", "sections": ["slate auth controls"]},
    {"path": "paper-trader/backend/app/accounts/browser_auth.py", "sections": ["password_bytes", "hash_password", "verify_password", "login", "mutate_session"]},
    {"path": "paper-trader/backend/app/api/auth_session_routes.py", "sections": ["login", "password action", "logout all"]}
  ],
  "source_claims": [
    {"source": "OWASP Authentication Cheat Sheet", "url": "https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html", "claim": "Passwords should support password managers, remain length-bounded without silent normalization/truncation, travel only over TLS, and current credentials should protect password changes.", "application": "The visibility control changes only input presentation; autocomplete, current/new-password purpose, maximum length, existing TLS transport and reauthentication remain unchanged."},
    {"source": "OWASP Session Management Cheat Sheet", "url": "https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html", "claim": "Session identifiers and credentials must not leak through URLs, logs or client storage.", "application": "The control keeps state inside React and never persists or emits password values."}
  ],
  "allowed_paths": [
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css",
    "paper-trader/docs/agent/tasks/strategy-os-v0-auth-password-visibility-preview-correction.md",
    ".agent/runs/strategy-os-v0-auth-password-visibility-preview-correction"
  ],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-auth-password-visibility-preview-correction.md", ".agent/runs/strategy-os-v0-auth-password-visibility-preview-correction"],
  "external_review_paths": ["/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.tsx", "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.test.tsx", "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css"],
  "protected_paths": ["paper-trader/backend", "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/api.ts", "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/contracts.ts", "/Users/priyanshusaraf/dev/strategy-os-frontend/src/features", "/Users/priyanshusaraf/dev/strategy-os-frontend/package.json", "/Users/priyanshusaraf/dev/strategy-os-frontend/pnpm-lock.yaml", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Implement one reusable AuthGate-local password input wrapper with Eye/EyeOff icons, independent visibility state, type=password by default, type=text only after explicit activation, and a type=button control with changing Show/Hide accessible name, aria-pressed and aria-controls.",
    "Use it for login/enrollment password, current password, new password and sign-out-all password. Do not reveal invitation tokens or broker/API secrets in this capsule.",
    "Preserve input name, id, required, maxlength, autocomplete, disabled, aria-describedby/invalid, paste and password-manager behavior. Toggling must retain value, focus, selection and form payload and must not submit the form.",
    "Add compact desktop styling with visible focus and at least a 44px control target without changing the surrounding auth layout or adding a dependency.",
    "Verify the existing local account path only with non-echoing interactive input; evidence records match/status only, never the credential or verifier."
  ],
  "acceptance": [
    "Every AuthGate password field starts concealed and has an independently named Show control; activation reveals only that field, changes to Hide, preserves its value and can be toggled by keyboard without form submission.",
    "Login, invitation enrollment, password change and sign-out-all submit byte-identical field names/values through the existing StrategyApi; no password enters URL, localStorage, sessionStorage, logs, analytics or rendered feedback.",
    "Autocomplete remains current-password/new-password as appropriate; invitation remains concealed without a visibility control; pending/disabled behavior and focus/error behavior remain correct.",
    "Focused and full frontend tests, typecheck, lint and production build pass on the supported Node runtime. A safe real browser login against 5187/8090 succeeds and the control has correct accessible name/state.",
    "An isolated mutation that prevents type switching turns the named control assertion RED; exact source restoration returns GREEN. Architecture and protected hashes pass.",
    "No backend authentication policy, password hashing, session, cookie, CSRF, rate limit, account entitlement, provider credential, production user or deployment state changes."
  ],
  "test_plan": ["Capture external source/protected hashes and current real-login status without secret output.", "Write focused failing tests for independent toggle/value/focus/form/autocomplete/storage behavior; implement component and CSS only.", "Run focused/full frontend, typecheck/lint/build, isolated toggle ablation and safe 5187 browser journey; seal a compact Important review package."],
  "risk_classification": {"tier": "Important", "reason": "The feature is presentation-only but handles password DOM state, form submission and accessibility at an authentication boundary."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_auth_password_visibility_preview_correction_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "frontend-auth-usability", "depends_on": [], "write_paths": ["/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.tsx", "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.test.tsx", "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css", "paper-trader/docs/agent/tasks/strategy-os-v0-auth-password-visibility-preview-correction.md", ".agent/runs/strategy-os-v0-auth-password-visibility-preview-correction"], "output": ".agent/runs/strategy-os-v0-auth-password-visibility-preview-correction/report.md"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_auth_password_visibility_preview_correction_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Important presentation-only correction with no authentication-policy or backend mutation; integrated release/security reviews remain later V0 gates.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-auth-password-visibility-preview-correction/review-package.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-auth-password-visibility-preview-correction.md", ".agent/runs/strategy-os-v0-auth-password-visibility-preview-correction"], "external_review_paths": ["/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.tsx", "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.test.tsx", "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css"], "exclude_paths": ["paper-trader/backend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-auth-password-visibility-preview-correction/report.md", "verdicts": ["IMPLEMENTATION", "ACCESSIBILITY", "AUTH_BOUNDARY"], "max_rechecks": 0},
  "owner_gates": ["No backend auth/session/password policy, recovery/MFA/email flow, provider secret visibility, real user/production state, commit, deployment or V0-complete claim."],
  "stop_conditions": ["Any need to read/log/persist the supplied password or verifier.", "Existing auth transport or payload must change to implement visibility.", "A new dependency or backend mutation is required.", "The preview no longer runs in local mock/API-only/no-execution-authority mode."],
  "result": {"status": "accepted", "implementation": "PASS", "accessibility": "PASS_LIMITED_WCAG_2_2_AA_SCOPE", "auth_boundary": "PASS", "focused_tests": "8/8", "full_frontend_tests": "252/252", "typecheck": "PASS", "lint": "PASS", "production_build": "PASS", "type_switch_ablation": "RED_THEN_EXACT_RESTORE_GREEN", "browser": "Chrome/152.0.7977.66", "real_browser_enrollment": "PASS", "real_browser_login": "PASS_200", "storage_empty": true, "secret_rendered": false, "secret_in_url": false, "architecture": "499/0", "execution_schema": "0051/0051", "execution_authority": false, "shared_processes_preserved": true, "source_hashes": {"AuthGate.tsx": "1d67d7cf15db802483fea70b05d78d2a43a07405d2f9bb3296000b8966dbe813", "AuthGate.test.tsx": "4beefc39717d9e3c376ec7a4f8fc8896b08a24261386c5bdb673c9abfe8af323", "precision.css": "085c2c885a38148ab990a42db5b3201df0a37d4e1bce50842ad8412e8ab833d5"}, "report": ".agent/runs/strategy-os-v0-auth-password-visibility-preview-correction/report.md", "review_package": ".agent/runs/strategy-os-v0-auth-password-visibility-preview-correction/review-package.json", "browser_receipt_sha256": "49aa92d742344ce2740944793f265805e2339004124271585c38c19295c88bb8"},
  "deployment_impact": {"classification": "frontend-only additive control", "schema_change": false, "configuration_change": false, "dependency_change": false, "locally_runnable": true, "release_deployable": false, "production_rehearsed": false, "deployed": false, "future_gate": "strategy-os-v0-security-operations-deployability"},
  "nonclaims": ["No password reset/recovery, MFA, public signup, email verification, provider-secret reveal, backend auth change, production readiness, deployment or V0 completion."]
}
---

# Password visibility preview correction

This side capsule changes only how existing password inputs are displayed. The
server-side verifier, session lifecycle and authorization boundary remain unchanged.
