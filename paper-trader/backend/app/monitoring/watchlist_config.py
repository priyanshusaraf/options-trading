"""Closed watchlist row preferences, separate from strategy and alert identity."""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ir.hashing import content_address
from app.monitoring.evaluation_policy import load_monitoring_evaluation_policy
from app.monitoring.state_contracts import _parse_time


ADDRESS_PATTERN = r"^sha256:[0-9a-f]{64}$"
IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
TIMEFRAMES = {"15minute": (900, "15 min"), "30minute": (1800, "30 min"),
    "60minute": (3600, "1 hour"), "day": (86400, "1 day")}
Timeframe = Literal["15minute", "30minute", "60minute", "day"]


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)


class WatchlistContext(ClosedModel):
    project_id: str = Field(min_length=1, max_length=64)
    scope_id: str = Field(pattern=r"^scope\.[A-Za-z0-9][A-Za-z0-9._-]{0,57}$")
    scope_revision: int = Field(ge=1, le=2_147_483_647)
    scope_address: str = Field(pattern=ADDRESS_PATTERN)
    membership_address: str = Field(pattern=ADDRESS_PATTERN)


class WatchlistStrategy(ClosedModel):
    graph_id: str = Field(pattern=IDENTIFIER_PATTERN)
    graph_version: int = Field(ge=1, le=2_147_483_647)
    graph_version_address: str = Field(pattern=ADDRESS_PATTERN)
    label: str = Field(min_length=1, max_length=128)

    @field_validator("label")
    @classmethod
    def label_is_safe(cls, value):
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("strategy label contains control characters")
        return value


class WatchlistValues(ClosedModel):
    graph: WatchlistStrategy | None = None
    timeframe: Timeframe = "15minute"
    pinned: bool = False
    monitoring_intent: Literal["MONITOR", "PAUSE"] = "PAUSE"
    assignment_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    evaluation_policy: dict[str, Any] | None = None
    canonical_instrument_address: str | None = Field(default=None, pattern=ADDRESS_PATTERN)

    @model_validator(mode="after")
    def bindings_are_closed(self):
        if self.monitoring_intent == "MONITOR" and self.graph is None:
            raise ValueError("Choose a saved strategy before starting monitoring.")
        if (self.assignment_id is None) != (self.evaluation_policy is None):
            raise ValueError("monitoring assignment and policy must stay paired")
        if (self.assignment_id is None) != (self.canonical_instrument_address is None):
            raise ValueError("monitoring assignment and instrument must stay paired")
        if self.evaluation_policy is not None:
            if self.graph is None:
                raise ValueError("a monitoring assignment requires its saved strategy")
            policy = load_monitoring_evaluation_policy(self.evaluation_policy)
            if policy.document["assignment_id"] != self.assignment_id:
                raise ValueError("monitoring policy names a different assignment")
        return self


class WatchlistSelection(ClosedModel):
    graph_id: str = Field(pattern=IDENTIFIER_PATTERN)
    graph_version: int = Field(ge=1, le=2_147_483_647)
    timeframe: Timeframe


class WatchlistCommand(ClosedModel):
    operation: Literal["CONFIGURE", "PIN", "MONITOR"]
    expected_revision: int = Field(ge=0, le=2_147_483_646)
    selection: WatchlistSelection | None = None
    flag: bool | None = None

    @model_validator(mode="after")
    def operation_values_match(self):
        configure = self.operation == "CONFIGURE"
        if configure != (self.selection is not None) or configure != (self.flag is None):
            raise ValueError("watchlist command fields do not match its operation")
        return self


class WatchlistConfiguration(WatchlistValues):
    schema_version: Literal["watchlist-monitoring-configuration/1"] = Field(
        default="watchlist-monitoring-configuration/1", alias="schema")
    owner_id: str = Field(pattern=IDENTIFIER_PATTERN, max_length=64)
    project_id: str = Field(min_length=1, max_length=64)
    scope_id: str = Field(pattern=r"^scope\.[A-Za-z0-9][A-Za-z0-9._-]{0,57}$")
    member_key: str = Field(pattern=r"^(?:CANONICAL|PROVIDER_REFERENCE):sha256:[0-9a-f]{64}$")
    revision: int = Field(ge=1, le=2_147_483_647)
    predecessor_address: str | None = Field(pattern=ADDRESS_PATTERN)
    request_id: str
    created_by: str = Field(pattern=IDENTIFIER_PATTERN, max_length=64)
    created_at: str
    context: WatchlistContext
    command: WatchlistCommand

    @field_validator("request_id")
    @classmethod
    def request_is_uuid(cls, value):
        parsed = UUID(value)
        if parsed.version != 4 or str(parsed) != value:
            raise ValueError("request identity must be a canonical UUID4")
        return value

    @field_validator("created_at")
    @classmethod
    def clock_is_exact(cls, value):
        _parse_time(value, "watchlist configuration time")
        return value

    @model_validator(mode="after")
    def identity_is_consistent(self):
        if (self.revision == 1) != (self.predecessor_address is None):
            raise ValueError("configuration predecessor and revision differ")
        if self.revision != self.command.expected_revision + 1:
            raise ValueError("configuration does not follow the requested revision")
        if (self.project_id, self.scope_id) != (self.context.project_id, self.context.scope_id):
            raise ValueError("configuration watchlist context differs")
        if (self.canonical_instrument_address is not None
                and self.member_key.startswith("CANONICAL:")
                and self.member_key != f"CANONICAL:{self.canonical_instrument_address}"):
            raise ValueError("monitoring instrument differs from this watchlist member")
        policy = self.evaluation_policy
        if policy is not None and policy["owner_id"] != self.owner_id:
            raise ValueError("configuration policy owner differs")
        return self

    def payload(self):
        return self.model_dump(by_alias=True)

    @property
    def address(self):
        return content_address(self.payload())

    def stored_payload(self):
        return {**self.payload(), "address": self.address}

    def row_values(self):
        return WatchlistValues(**{name: getattr(self, name) for name in WatchlistValues.model_fields})
