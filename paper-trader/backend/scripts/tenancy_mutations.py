"""Prove the tenancy and credential guards can go red.

Every mutation here is a plausible refactor that a reviewer could wave through, and every one of
them is a way for the system to hurt a user rather than fail:

  * dropping an owner filter is one customer trading on another's account;
  * storing a credential unencrypted is a rsynced database file that IS the account;
  * a fallback where there should be a refusal places orders through a credential nobody chose.

A GREEN line means that behaviour is unguarded. Run from `backend/`.
"""
import pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
STORE = ROOT / "app/providers/connection_store.py"
VAULT = ROOT / "app/core/credential_vault.py"
CONN = ROOT / "app/providers/connection.py"
PLANES = ROOT / "app/db/planes.py"
KOC = ROOT / "app/engine/kite_order_client.py"
KPROV = ROOT / "app/providers/kite.py"
LIFECYCLE = ROOT / "app/engine/execution_lifecycle.py"
VAULTC = ROOT / "app/core/credential_vault.py"
PY = "/Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python"
TESTS = ["tests/test_connection_store.py", "tests/test_db_planes.py",
         "tests/test_execution_connection.py", "tests/test_split_routing.py",
         "tests/test_execution_lifecycle.py"]

MUTATIONS = [
    # ── cross-owner isolation ──────────────────────────────────────────────
    ("get-drops-the-owner-filter", STORE,
     """        row = self.s.query(BrokerConnection).filter(
            BrokerConnection.id == connection_id,
            BrokerConnection.owner_id == self.owner_id).one_or_none()""",
     """        row = self.s.query(BrokerConnection).filter(
            BrokerConnection.id == connection_id).one_or_none()"""),
    ("list-drops-the-owner-filter", STORE,
     """        q = self.s.query(BrokerConnection).filter(
            BrokerConnection.owner_id == self.owner_id)""",
     "        q = self.s.query(BrokerConnection)"),
    ("by-scope-drops-the-owner-filter", STORE,
     """        return self.s.query(BrokerConnection).filter(
            BrokerConnection.owner_id == self.owner_id,
            BrokerConnection.scope == scope).one_or_none()""",
     """        return self.s.query(BrokerConnection).filter(
            BrokerConnection.scope == scope).one_or_none()"""),
    ("late-token-read-drops-the-owner-filter", STORE,
     """                        BrokerConnection.id == cid,
                        BrokerConnection.owner_id == owner_id,
                        BrokerConnection.status == "active").one_or_none()""",
     """                        BrokerConnection.id == cid,
                        BrokerConnection.status == "active").one_or_none()"""),
    ("an-explicitly-empty-owner-defaults-to-the-real-owner", STORE,
     "    if owner_id is _UNSPECIFIED:\n        return LEGACY_OWNER_ID",
     "    if not owner_id or owner_id is _UNSPECIFIED:\n        return LEGACY_OWNER_ID"),

    # ── the credential at rest ─────────────────────────────────────────────
    ("no-key-falls-back-to-plaintext", VAULT,
     '''        raise CredentialVaultUnavailable(
            f"{ENV_KEY} is not set, so no broker credential can be stored. Generate one with "''',
     '''        return b"0" * 32
    if False:
        raise CredentialVaultUnavailable(
            f"{ENV_KEY} is not set, so no broker credential can be stored. Generate one with "'''),
    ("a-failed-decrypt-reads-as-no-credential", VAULT,
     '''        raise CredentialDecryptionFailed(
            f"stored credential did not authenticate under key {key_id()} "''',
     '''        return {}
    if False:
        raise CredentialDecryptionFailed(
            f"stored credential did not authenticate under key {key_id()} "'''),
    ("revocation-keeps-the-ciphertext", STORE,
     """        row.credential_ciphertext = None
        row.credential_key_id = None
        row.revoked_at = dt.datetime.now()""",
     "        row.revoked_at = dt.datetime.now()"),
    ("to-dict-leaks-the-ciphertext", ROOT / "app/db/models.py",
     '''            "has_credential": bool(self.credential_ciphertext),''',
     '''            "has_credential": bool(self.credential_ciphertext),
            "credential_ciphertext": self.credential_ciphertext,'''),
    ("a-revoked-connection-can-still-be-bound", STORE,
     '''        if row.status != "active":
            raise ConnectionNotFound(
                f"connection {connection_id} is {row.status}, not active")''',
     "        pass"),

    # ── refusals that must not become fallbacks ────────────────────────────
    ("a-planned-broker-connection-is-allowed", STORE,
     """        if s.load_data() is None and s.load_venue() is None:
            raise BrokerNotSupported(""",
     """        if False:
            raise BrokerNotSupported("""),
    ("a-missing-stored-connection-falls-back-to-the-env-var", CONN,
     """        if row is None or row.status != "active":""",
     "        if False:"),

    # ── the withdrawal path (found by security review 2026-08-10) ─────────
    # Each of these restores the exact hole: a revoked/unreadable credential that the wire
    # client keeps trading on because it ignores a None.
    ("withdrawn-token-silently-discarded", KOC,
     "        if self._ever_authenticated:\n            self._last_token = None",
     "        if False:\n            self._last_token = None"),
    ("withdrawn-token-not-cleared-from-the-wire-client", KOC,
     '                self.kite.set_access_token("")',
     "                pass"),
    # ── the execution-safety review's F1/F2/F3 (2026-08-10) ───────────────
    # Each restores a defect that the withdrawal FIX itself shipped with. They are here rather
    # than in a new script because they belong to the same credential lifecycle.
    ("withdrawal-guard-keyed-on-last-token-so-it-is-inert-at-startup", KOC,
     "        if self._ever_authenticated:",
     "        if self._last_token is not None:"),
    ("client-does-not-adopt-the-credential-at-construction", KOC,
     "        try:\n            self._sync_token()\n        except Exception:"
     "                          # noqa: BLE001 — see above\n            pass",
     "        pass"),
    # F4: the execution-role provider serving a token from before the daily re-login.
    ("execution-connection-serves-a-stale-cached-token", CONN,
     '        token_source=(getattr(provider, "current_access_token", None)\n'
     '                      or (lambda: getattr(provider, "access_token", None))),',
     '        token_source=lambda: getattr(provider, "access_token", None),'),
    ("token-file-never-re-read-after-a-relogin", KPROV,
     "        if stamp != getattr(self, \"_token_file_stamp\", None):",
     "        if False:"),
    ("stored-connection-loses-its-tick-reader", CONN,
     "        return replace(conn, tick_source=_tick_source_for(conn.broker))",
     "        return conn"),

    ("dotenv-key-ignored-again", VAULTC,
     """    try:
        from app.core.config import get_settings
        return (getattr(get_settings(), "credential_key", "") or "").strip()
    except Exception:                               # noqa: BLE001 — settings must never break the vault
        return """"",
     "    return """),

    # ── restart recovery: whose money, and which venue ────────────────────
    # Both dimensions were found missing by two independent reviews. Adopting another owner's
    # or another venue's unresolved live entries is the worst failure available here.
    ("recovery-drops-the-owner-dimension", LIFECYCLE,
     "                ExecutionIntent.owner_id == owner_id,",
     "                # dropped"),
    ("recovery-drops-the-broker-dimension", LIFECYCLE,
     "                ExecutionIntent.broker == broker,",
     "                # dropped"),

    # ── the plane ratchet ──────────────────────────────────────────────────
    ("connections-move-to-the-market-plane", PLANES,
     '"broker_connections": Plane.MONEY,',
     '"broker_connections": Plane.MARKET,'),
    ("the-ratchet-is-widened-to-anything", PLANES,
     'GRANDFATHERED_CROSS_PLANE_FKS: frozenset[tuple[str, str]] = frozenset({',
     'GRANDFATHERED_CROSS_PLANE_FKS: frozenset[tuple[str, str]] = frozenset({\n    ("positions", "deployment_id"),'),
]


# ── concurrency guard ─────────────────────────────────────────────────────
# A mutation sweep writes mutants into the WORKING TREE and restores from an in-memory baseline.
# Two sweeps running at once is therefore destructive, not merely slow: sweep B captures its
# baseline while sweep A has a mutant applied, and B's restore writes A's mutant back
# permanently. That happened on 2026-08-10 — `OwnedConnectionStore.revoke` silently lost
# `credential_ciphertext = None`, so revocation stopped destroying the credential, and the only
# reason it was caught is that the sweep reported the anchor as stale.
#
# An exclusive lock on the repo makes the second sweep refuse instead of corrupting the first.
import fcntl
_LOCK_PATH = pathlib.Path(__file__).resolve().parent / ".mutation-sweep.lock"
_LOCK_FD = open(_LOCK_PATH, "w")
try:
    fcntl.flock(_LOCK_FD, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print("REFUSED: another mutation sweep is already running in this tree. Running two at once "
          "restores one sweep's mutant permanently over the other's baseline.")
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
sys.exit(1 if bad else 0)
