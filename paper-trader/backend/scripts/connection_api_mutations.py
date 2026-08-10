"""Prove the connection API's guards can go red.

`tests/test_connection_routes.py` passed on its first run, which is not evidence — this codebase
has caught five distinct shapes of vacuous test that way. Every mutation below is a plausible
edit that a reviewer could wave through, and every one of them is a way for the HTTP surface to
re-introduce something the store underneath it was careful about:

  * the owner coming from the principal id rather than the configured owner — every connection
    created on the tailnet box (auth off) filed under an identity the engine never reads;
  * a credential leaving the process, or a missing vault key reported as a success;
  * a refusal degraded into a crash, so the operator cannot tell "this broker has no adapter"
    from "the server is broken".

A GREEN line means that behaviour is unguarded. Run from `backend/`.
"""
import fcntl
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
API = ROOT / "app/api/connection_routes.py"
PRINCIPAL = ROOT / "app/api/principal.py"
MODELS = ROOT / "app/db/models.py"
MAIN = ROOT / "app/main.py"
STORE = ROOT / "app/providers/connection_store.py"
AUTH = ROOT / "app/providers/broker_auth.py"
PY = "/Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python"
TESTS = ["tests/test_connection_routes.py", "tests/test_principal.py",
         "tests/test_safe_kite_construction_invariant.py"]

MUTATIONS = [
    # ── whose rows these are ───────────────────────────────────────────────
    ("owner-taken-from-the-principal-id", PRINCIPAL,
     '    configured = (get_settings().owner_id or "").strip()\n'
     "    return configured or LEGACY_OWNER_ID",
     "    return principal.id"),
    # Two guards, two mutations. `is_allowed` checks `is_owner` BEFORE reaching `owner_id_for`,
    # so each can be removed independently and only one of them used to be pinned. The anchors
    # carry a following line because the `if` itself is now identical in both functions and
    # `replace(..., 1)` would silently mutate whichever comes first in the file.
    ("is_allowed-lets-a-non-owner-principal-through", PRINCIPAL,
     "    if principal is None or not principal.is_owner:\n        return False\n"
     '    resource_owner = getattr(resource, "owner_id", None)',
     "    if principal is None:\n        return False\n"
     '    resource_owner = getattr(resource, "owner_id", None)'),
    ("owner_id_for-falls-through-to-the-owner-for-a-non-owner", PRINCIPAL,
     "    if principal is None or not principal.is_owner:\n"
     '        raise Forbidden("no owner identity for this principal")',
     "    if principal is None:\n"
     '        raise Forbidden("no owner identity for this principal")'),
    # The vacuity this closes: `LEGACY_OWNER_ID`, `Settings.owner_id`'s default and the model's
    # column default all produce `"owner"`, so the owner test used to pass under a constant.
    ("owner-hardcoded-to-the-single-owner-default", PRINCIPAL,
     '    configured = (get_settings().owner_id or "").strip()\n'
     "    return configured or LEGACY_OWNER_ID",
     "    return LEGACY_OWNER_ID"),

    # ── per-resource ownership: the policy must actually decide something ──
    ("the-resource-argument-goes-back-to-being-ignored", PRINCIPAL,
     '    resource_owner = getattr(resource, "owner_id", None)',
     "    resource_owner = None\n    _unused = getattr(resource, \"owner_id\", None)"),
    ("a-foreign-owner-passes-the-policy", PRINCIPAL,
     "        return str(resource_owner) == owner_id_for(principal)",
     "        return bool(owner_id_for(principal))"),
    ("an-unowned-resource-is-refused-instead-of-allowed", PRINCIPAL,
     "    if resource_owner is None:\n        return True",
     "    if resource_owner is None:\n        return False"),
    ("the-route-never-hands-the-policy-the-loaded-row", API,
     "    if not is_allowed(principal, action, row):",
     "    if not is_allowed(principal, action, None):"),

    # ── the credential ─────────────────────────────────────────────────────
    ("a-missing-vault-key-is-reported-as-a-success", API,
     "        except CredentialVaultUnavailable as e:\n"
     "            raise HTTPException(status_code=503, detail=str(e)) from e",
     "        except CredentialVaultUnavailable:\n"
     '            return {"has_credential": False}'),
    ("the-credential-bundle-is-unbounded", API,
     "    if len(body.secrets) > _MAX_SECRET_KEYS:",
     "    if False:"),
    ("a-revoked-connection-can-be-re-credentialed", STORE,
     '        row = self.get(connection_id)\n'
     '        if row.status != "active":\n'
     '            raise ConnectionNotFound(\n'
     '                f"connection {connection_id} is {row.status}, not active")\n'
     "        ciphertext, key_id = seal(secrets)",
     "        row = self.get(connection_id)\n        ciphertext, key_id = seal(secrets)"),
    ("the-credential-field-NAME-is-unbounded", API,
     "    if any(len(k) > _MAX_SECRET_KEY_LEN or len(v) > _MAX_SECRET_LEN\n"
     "           for k, v in body.secrets.items()):",
     "    if any(len(v) > _MAX_SECRET_LEN for v in body.secrets.values()):"),
    ("the-422-body-echoes-the-rejected-credential", MAIN,
     '    if path.startswith("/api/connections/") and path.endswith("/credential"):',
     "    if False:"),
    ("a-whitespace-padded-scope-is-accepted", API,
     "    if body.scope != body.scope.strip():",
     "    if False:"),
    ("the-capabilities-list-is-unbounded", API,
     "    capabilities: list[str] | None = Field(default=None, max_length=len(caps.ALL))",
     "    capabilities: list[str] | None = None"),
    # Anchored on the CURRENT two-part check. The previous anchor was the values-only line that
    # finding #2 replaced, so this entry silently went SKIP — a stale anchor means the behaviour
    # is no longer proven guarded, which is why a SKIP counts as a failure here and not a note.
    ("an-oversized-credential-VALUE-is-accepted", API,
     "    if any(len(k) > _MAX_SECRET_KEY_LEN or len(v) > _MAX_SECRET_LEN\n"
     "           for k, v in body.secrets.items()):",
     "    if any(len(k) > _MAX_SECRET_KEY_LEN for k in body.secrets):"),
    ("an-empty-credential-bundle-is-accepted", API,
     "    secrets: dict[str, str] = Field(min_length=1)",
     "    secrets: dict[str, str]"),
    ("to-dict-leaks-the-ciphertext-to-the-api", MODELS,
     '            "has_credential": bool(self.credential_ciphertext),',
     '            "has_credential": bool(self.credential_ciphertext),\n'
     '            "credential_ciphertext": self.credential_ciphertext,'),

    # ── acquiring a credential ─────────────────────────────────────────────
    ("the-login-url-falls-back-to-the-process-wide-api-key", AUTH,
     '        (api_key,) = _required(secrets, "api_key")',
     '        from app.core.config import get_settings\n'
     '        api_key = (secrets or {}).get("api_key") or get_settings().kite_api_key'),
    # Caught in the full suite by the F-10 construction invariant, not by any connection test —
    # so it is anchored here too, because a sweep that only runs the connection suite would have
    # reported this behaviour as guarded when only a different file's test was holding it.
    ("the-authenticator-holds-an-order-capable-client", AUTH,
     "        from app.providers.safe_kite import SafePaperKite\n"
     "        return SafePaperKite(api_key=api_key)",
     "        from kiteconnect import KiteConnect\n"
     "        return KiteConnect(api_key=api_key)"),
    ("the-exchange-drops-the-app-keys", AUTH,
     "        return {**{k: v for k, v in (secrets or {}).items() if isinstance(v, str)},\n"
     '                "access_token": str(token),',
     "        return {\n"
     '                "access_token": str(token),'),
    ("the-brokers-exception-message-is-passed-through", AUTH,
     '                f"Kite refused the session exchange ({type(e).__name__}). A request_token is "\n'
     '                f"single-use and expires within minutes — start the login again.") from e',
     '                f"Kite refused the session exchange: {e}") from e'),
    ("a-long-lived-key-broker-invents-a-login-url", AUTH,
     "    def login_url(self, secrets: dict) -> str:\n"
     "        raise NoInteractiveLogin(",
     "    def login_url(self, secrets: dict) -> str:\n"
     "        return self.docs_url\n"
     "    def _unreachable(self, secrets: dict) -> str:\n"
     "        raise NoInteractiveLogin("),
    ("an-unregistered-broker-gets-a-silent-none-authenticator", API,
     "    if auth is None:\n        raise HTTPException(\n            status_code=501,",
     "    if False:\n        raise HTTPException(\n            status_code=501,"),

    # ── refusals that must not become crashes or successes ────────────────
    ("an-unsupported-broker-crashes-instead-of-refusing", API,
     "        except registry.BrokerNotSupported as e:\n"
     "            raise HTTPException(status_code=400, detail=str(e)) from e\n",
     ""),
    ("a-duplicate-scope-crashes-instead-of-conflicting", API,
     "        except IntegrityError as e:\n"
     "            s.rollback()\n"
     "            raise HTTPException(\n"
     "                status_code=409,",
     "        except IntegrityError as e:\n"
     "            s.rollback()\n"
     "            raise HTTPException(\n"
     "                status_code=500,"),
    ("an-unknown-capability-crashes-instead-of-refusing", API,
     "        except caps.UnknownCapability as e:\n"
     "            raise HTTPException(status_code=400, detail=str(e)) from e\n",
     ""),
    ("another-owners-connection-is-forbidden-rather-than-absent", API,
     "        except ConnectionNotFound as e:\n"
     "            raise HTTPException(status_code=404, detail=str(e)) from e\n"
     "\n"
     "\n"
     "@router.post(\"/connections\", status_code=status.HTTP_201_CREATED)",
     "        except ConnectionNotFound as e:\n"
     "            raise HTTPException(status_code=403, detail=str(e)) from e\n"
     "\n"
     "\n"
     "@router.post(\"/connections\", status_code=status.HTTP_201_CREATED)"),

    # ── the request body ───────────────────────────────────────────────────
    ("an-unknown-request-field-is-ignored-rather-than-refused", API,
     '    model_config = ConfigDict(extra="forbid", frozen=True)',
     '    model_config = ConfigDict(extra="ignore", frozen=True)'),

    # ── what the operator is shown ─────────────────────────────────────────
    ("the-broker-list-hides-the-planned-brokers", API,
     "        for b in registry.BROKERS",
     "        for b in registry.supported()"),
    ("the-execution-role-is-derived-from-the-support-status", API,
     '            "roles": {"data": b.data is not None, "execution": b.venue is not None},',
     '            "roles": {"data": b.data is not None,\n'
     '                      "execution": b.status is registry.Status.SUPPORTED},'),
    ("a-revoked-connection-still-appears-in-the-default-listing", API,
     "    include_revoked: bool = Query(default=False),",
     "    include_revoked: bool = Query(default=True),"),

    # ── durability ─────────────────────────────────────────────────────────
    # A route that flushes without committing looks correct in the response and has written
    # nothing. The store deliberately only flushes; the commit boundary is the route's.
    ("create-never-commits", API,
     "                capabilities=declared)\n            s.commit()",
     "                capabilities=declared)"),
    ("storing-a-credential-never-commits", API,
     "            row = store.store_credential(connection_id, dict(body.secrets))\n"
     "            s.commit()",
     "            row = store.store_credential(connection_id, dict(body.secrets))"),
    ("revocation-never-commits", API,
     "            row = store.revoke(connection_id)\n            s.commit()",
     "            row = store.revoke(connection_id)"),
]

# An exclusive lock on the tree. Two sweeps at once is destructive, not merely slow: sweep B
# captures its baseline while sweep A has a mutant applied, and B's restore writes A's mutant
# back permanently. That happened on 2026-08-10 and cost `revoke()` its credential destruction.
# The lock file is shared with the other sweep scripts on purpose.
_LOCK_FD = open(pathlib.Path(__file__).resolve().parent / ".mutation-sweep.lock", "w")
try:
    fcntl.flock(_LOCK_FD, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print("REFUSED: another mutation sweep is already running in this tree.")
    sys.exit(2)

baselines = {p: p.read_bytes() for p in {m[1] for m in MUTATIONS}}
bad = 0
try:
    for name, path, orig, mutant in MUTATIONS:
        src = baselines[path].decode()
        if orig not in src:
            print(f"  SKIP  {name}: anchor not found — this table is stale")
            bad += 1
            continue
        path.write_text(src.replace(orig, mutant, 1))
        r = subprocess.run([PY, "-m", "pytest", *TESTS, "-q"], cwd=ROOT,
                           capture_output=True, text=True)
        red = r.returncode != 0
        print(f"  {'RED ' if red else 'GREEN'}  {name}{'' if red else '   <-- UNGUARDED'}")
        bad += 0 if red else 1
        path.write_bytes(baselines[path])
finally:
    for p, b in baselines.items():
        p.write_bytes(b)
print("RESTORED byte-identical:",
      all(p.read_bytes() == b for p, b in baselines.items()))
print(f"{len(MUTATIONS) - bad}/{len(MUTATIONS)} reddened")
sys.exit(1 if bad else 0)
