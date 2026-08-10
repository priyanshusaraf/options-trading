"""Encryption for stored broker credentials — ADR 0015's "the key is not a row".

A `broker_connections` row is the authority to place real orders on a real account. Storing the
credential in plaintext would make a database file — which is rsynced to a laptop by
`deploy.sh`, backed up, and copied between environments — equivalent to the account itself.

**AES-256-GCM**, authenticated: a tampered ciphertext fails to decrypt rather than decrypting to
something else. That property is why AEAD rather than plain AES, and it is not decorative — an
attacker who can write to the database but not read the key must not be able to flip a stored
credential to one they control.

Three decisions worth stating because each has a plausible-looking wrong alternative:

  * **The key comes from the environment, never from the database.** `PT_CREDENTIAL_KEY`, a
    base64 32-byte value. If it lived in a table, a database compromise would be a credential
    compromise and the encryption would be theatre.
  * **A missing key is a refusal, not a fallback to plaintext.** Fail closed: without a key this
    module cannot store a credential, and the connection stays credential-less. The alternative
    — quietly storing plaintext when unconfigured — is how a development default reaches
    production, and it is invisible precisely where it matters.
  * **Every ciphertext records which key wrote it.** A rotation needs to find the rows it has
    still to re-wrap; discovering them one failed decrypt at a time happens on the order path,
    at 09:15.

The plaintext is a JSON object rather than a bare token because brokers need different bundles:
Kite is one token, Dhan is a token *and* a client id, and a TOTP-session broker stores a seed.
One shape for all of them keeps the vault from growing a per-broker branch.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ENV_KEY = "PT_CREDENTIAL_KEY"

#: AES-GCM standard nonce length. 12 bytes, prepended to the ciphertext rather than stored in
#: its own column: a nonce is not a secret, and one fewer column is one fewer way for the two to
#: be separated by a partial write.
_NONCE_BYTES = 12


class CredentialVaultUnavailable(RuntimeError):
    """No usable encryption key. Deliberately fatal to the *store* operation only.

    The engine must keep running — an existing in-memory connection is unaffected — but nothing
    new may be persisted, because the only alternatives are storing plaintext or silently
    dropping the credential, and both are worse than refusing.
    """


class CredentialDecryptionFailed(RuntimeError):
    """The ciphertext did not authenticate under the current key.

    Means one of: the key rotated and this row was not re-wrapped, the row was tampered with, or
    the wrong environment's key is loaded. All three must be loud — a credential that silently
    reads as absent looks exactly like "this owner never connected", and the operator would
    reconnect rather than investigate.
    """


def _configured_key() -> str:
    """The key as the operator actually set it — environment first, then `.env` via settings.

    Both sources are needed and the reason is a trap this project has already paid for:
    **pydantic-settings reads `.env` itself and does NOT export to `os.environ`.** Reading only
    `os.environ` meant the documented setup path (`PT_CREDENTIAL_KEY=...` in `backend/.env`, as
    `.env.example` instructs) left `available()` returning False while the variable was
    demonstrably set — and the error message said "is not set". Found by an independent security
    review, 2026-08-10.

    Environment wins over `.env` because that is the precedence pydantic-settings itself uses,
    and because a deployment overriding a file-set key must not be silently ignored.

    Settings is imported lazily: `app.core.config` must not become an import-time dependency of
    a module the engine loads on the order path.
    """
    raw = (os.environ.get(ENV_KEY) or "").strip()
    if raw:
        return raw
    try:
        from app.core.config import get_settings
        return (getattr(get_settings(), "credential_key", "") or "").strip()
    except Exception:                               # noqa: BLE001 — settings must never break the vault
        return ""


def key_material() -> bytes:
    raw = _configured_key()
    if not raw:
        raise CredentialVaultUnavailable(
            f"{ENV_KEY} is not set, so no broker credential can be stored. Generate one with "
            f"`python -c \"import os,base64;print(base64.b64encode(os.urandom(32)).decode())\"` "
            f"and set it in the environment — NOT in the database, and not in a file that "
            f"deploy.sh rsyncs.")
    try:
        key = base64.b64decode(raw, validate=True)
    except Exception as e:                          # noqa: BLE001
        raise CredentialVaultUnavailable(f"{ENV_KEY} is not valid base64") from e
    if len(key) != 32:
        raise CredentialVaultUnavailable(
            f"{ENV_KEY} decodes to {len(key)} bytes; AES-256 needs exactly 32")
    return key


def key_id() -> str:
    """A short, non-reversible fingerprint of the active key.

    A hash rather than a version number the operator maintains by hand: a number can be set to
    the same value for two different keys, and the failure that causes surfaces as an
    undecryptable credential on the order path.
    """
    return hashlib.sha256(key_material()).hexdigest()[:16]


def available() -> bool:
    """Can credentials be stored at all? Used to report the condition at startup rather than
    discovering it when an owner first tries to connect."""
    try:
        key_material()
        return True
    except CredentialVaultUnavailable:
        return False


def seal(secrets: dict) -> tuple[str, str]:
    """Encrypt a credential bundle. Returns `(ciphertext_b64, key_id)`.

    Both are returned together so a caller cannot store one without the other; a ciphertext with
    no key id is one nobody can prove they are able to read.
    """
    if not isinstance(secrets, dict):
        raise TypeError("a credential bundle is a dict — one shape for every broker")
    key = key_material()
    nonce = os.urandom(_NONCE_BYTES)
    blob = AESGCM(key).encrypt(nonce, json.dumps(secrets, sort_keys=True).encode(), None)
    return base64.b64encode(nonce + blob).decode(), key_id()


def unseal(ciphertext_b64: str | None) -> dict:
    """Decrypt a bundle. `None`/empty is an empty bundle — "this connection has no credential",
    a real state that is distinct from a failed decrypt."""
    if not ciphertext_b64:
        return {}
    key = key_material()
    try:
        raw = base64.b64decode(ciphertext_b64, validate=True)
        plain = AESGCM(key).decrypt(raw[:_NONCE_BYTES], raw[_NONCE_BYTES:], None)
        bundle = json.loads(plain.decode())
    except Exception as e:                          # noqa: BLE001
        # The exception carries no ciphertext and no key material: this message reaches logs.
        raise CredentialDecryptionFailed(
            f"stored credential did not authenticate under key {key_id()} "
            f"({type(e).__name__}). The key may have rotated without re-wrapping this row.") from e
    if not isinstance(bundle, dict):
        raise CredentialDecryptionFailed("stored credential decoded to a non-object")
    return bundle
