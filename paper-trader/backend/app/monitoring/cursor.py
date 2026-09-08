"""Signed opaque cursor contract for owner-scoped monitoring reads."""
from __future__ import annotations

import base64
from dataclasses import dataclass
import datetime as dt
import hashlib
import hmac
import json
import re

from app.ir.hashing import canonical_json, content_address
from app.ir.schema import is_content_address


MAX_CURSOR_BYTES = 2048
_OWNER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class MonitoringCursorRefusal(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AlertInboxCursor:
    event_at: dt.datetime
    alert_address: str


class AlertCursorCodec:
    def __init__(self, secret: bytes) -> None:
        if type(secret) is not bytes or len(secret) < 32:
            raise MonitoringCursorRefusal("cursor secret must be at least 32 bytes")
        self._secret = bytes(secret)

    @staticmethod
    def _filters(assignment_id: str | None, unread_only: bool | None) -> str:
        if assignment_id is not None and (
            type(assignment_id) is not str or not _OWNER.fullmatch(assignment_id)
        ):
            raise MonitoringCursorRefusal("cursor assignment filter is invalid")
        if unread_only is not None and type(unread_only) is not bool:
            raise MonitoringCursorRefusal("cursor unread filter is invalid")
        return content_address({
            "schema": "monitoring-alert-filter/1",
            "assignment_id": assignment_id,
            "unread_only": unread_only,
        })

    @staticmethod
    def _owner(owner_id: str) -> str:
        if type(owner_id) is not str or not _OWNER.fullmatch(owner_id):
            raise MonitoringCursorRefusal("cursor owner is invalid")
        return owner_id

    @staticmethod
    def _encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    @staticmethod
    def _decode(value: str) -> bytes:
        if type(value) is not str or not value or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise MonitoringCursorRefusal("cursor encoding is invalid")
        try:
            return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        except (ValueError, TypeError) as exc:
            raise MonitoringCursorRefusal("cursor encoding is invalid") from exc

    def encode(
        self, *, owner_id: str, assignment_id: str | None,
        unread_only: bool | None, event_at: dt.datetime, alert_address: str,
    ) -> str:
        owner = self._owner(owner_id)
        if type(event_at) is not dt.datetime or event_at.tzinfo is not dt.timezone.utc:
            raise MonitoringCursorRefusal("cursor time must be UTC")
        if type(alert_address) is not str or not is_content_address(alert_address):
            raise MonitoringCursorRefusal("cursor alert address is invalid")
        payload = canonical_json({
            "schema": "monitoring-alert-cursor/1",
            "event_at": event_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "alert_address": alert_address,
            "filter_address": self._filters(assignment_id, unread_only),
        }).encode("utf-8")
        signature = hmac.new(
            self._secret, owner.encode("utf-8") + b"\0" + payload, hashlib.sha256,
        ).digest()
        token = self._encode(payload) + "." + self._encode(signature)
        if len(token.encode("ascii")) > MAX_CURSOR_BYTES:
            raise MonitoringCursorRefusal("cursor exceeds size bound")
        return token

    def decode(
        self, token: str, *, owner_id: str, assignment_id: str | None,
        unread_only: bool | None,
    ) -> AlertInboxCursor:
        owner = self._owner(owner_id)
        if type(token) is not str or len(token.encode("utf-8")) > MAX_CURSOR_BYTES \
                or token.count(".") != 1:
            raise MonitoringCursorRefusal("cursor is invalid")
        encoded_payload, encoded_signature = token.split(".")
        payload = self._decode(encoded_payload)
        signature = self._decode(encoded_signature)
        expected = hmac.new(
            self._secret, owner.encode("utf-8") + b"\0" + payload, hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(signature, expected):
            raise MonitoringCursorRefusal("cursor is invalid")
        try:
            value = json.loads(payload)
            if type(value) is not dict or set(value) != {
                "schema", "event_at", "alert_address", "filter_address",
            } or value["schema"] != "monitoring-alert-cursor/1" \
                    or value["filter_address"] != self._filters(assignment_id, unread_only) \
                    or not is_content_address(value["alert_address"]):
                raise ValueError
            event_at = dt.datetime.strptime(
                value["event_at"], "%Y-%m-%dT%H:%M:%S.%fZ",
            ).replace(tzinfo=dt.timezone.utc)
            if event_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ") != value["event_at"]:
                raise ValueError
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise MonitoringCursorRefusal("cursor is invalid") from exc
        return AlertInboxCursor(event_at, value["alert_address"])


__all__ = ["AlertCursorCodec", "AlertInboxCursor", "MonitoringCursorRefusal"]
