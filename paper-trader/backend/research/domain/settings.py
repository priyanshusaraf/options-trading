"""Revisioned research preferences in the app DB; no runtime configuration reads."""
from __future__ import annotations

import copy
import datetime as dt
import json
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import WorkspaceResearchSettingsRevision, StrategyResearchSettingsRevision, Organization
from app.ir.hashing import canonical_json, content_address
from research.pipeline.v2_parameter_search import disabled_search


class ResearchValuesV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    research_capital: float = Field(gt=0, le=1_000_000_000)
    seed: int = Field(ge=0, le=2_147_483_647)
    min_trades: int = Field(ge=1, le=100_000)
    n_folds: int = Field(ge=2, le=32)
    min_positive_fold_frac: float = Field(ge=0, le=1)
    risk_policy: Literal["none", "pine-v4-ratchet/1", "pine-v4-reversal/1"]


class ResearchValues(ResearchValuesV1):
    stop_loss_pct: float = Field(default=0.0, ge=0, lt=1)
    take_profit_pct: float = Field(default=0.0, ge=0, lt=1)


class ResearchValuesV3(ResearchValues):
    optimization: dict[str, Any] = Field(default_factory=disabled_search)

    @field_validator("optimization")
    @classmethod
    def _optimization(cls, value):
        from research.pipeline.v2_parameter_search import validate_search_settings
        return validate_search_settings(value)


LEGACY_DEFAULTS = {
    "research_capital": 100000.0, "seed": 0, "min_trades": 10,
    "n_folds": 4, "min_positive_fold_frac": 0.6, "risk_policy": "none",
}

V2_DEFAULTS = {**LEGACY_DEFAULTS, "stop_loss_pct": 0.0, "take_profit_pct": 0.0}
PLATFORM_DEFAULTS = {**V2_DEFAULTS, "optimization": disabled_search()}


CURRENT_SCHEMA = "research-settings-revision/3"


def _defaults(schema):
    defaults = {
        "1": LEGACY_DEFAULTS,
        "2": V2_DEFAULTS,
        "3": PLATFORM_DEFAULTS,
    }
    if schema not in {f"research-settings-{kind}/{version}" for kind in ("revision", "snapshot")
                      for version in defaults}:
        raise ValueError("Unsupported research settings version.")
    return copy.deepcopy(defaults[schema.rsplit("/", 1)[1]])


def fixed_assumptions(risk_policy="none"):
    from research.orchestrator.v2_preparation import execution_policy
    policy = execution_policy(PLATFORM_DEFAULTS["research_capital"], risk_policy)
    return {"schema": policy["schema"], "fee": policy["fee"], "slippage": policy["slippage"],
            "adapter_policy_address": policy["adapter_policy_address"],
            "sizing_model": policy["risk"]["sizing_model"], "fill": policy["risk"]["fill"]}


class SettingsConflict(ValueError):
    pass


def validate_values(values: dict[str, Any], *, sparse: bool = False, schema=CURRENT_SCHEMA) -> dict[str, Any]:
    defaults = _defaults(schema)
    model = {"1": ResearchValuesV1, "2": ResearchValues, "3": ResearchValuesV3}[schema.rsplit("/", 1)[1]]
    validated = model.model_validate({**defaults, **values} if sparse else values).model_dump()
    return {key: validated[key] for key in values} if sparse else validated


def _validate_update_identity(expected_revision, request_id, enabled):
    if type(expected_revision) is not int or not 0 <= expected_revision <= 2_147_483_646:
        raise ValueError("Settings revision must be a non-negative integer.")
    identity = UUID(request_id)
    if identity.version != 4 or str(identity) != request_id:
        raise ValueError("Use a canonical UUID4 request ID.")
    if type(enabled) is not bool:
        raise ValueError("Choose whether strategy overrides are enabled.")


def _document(owner_id, graph_identifier, revision, expected_revision, request_id, values, enabled,
              schema=CURRENT_SCHEMA):
    return {
        "schema": schema, "owner_id": owner_id,
        "graph_identifier": graph_identifier, "revision": revision,
        "expected_revision": expected_revision, "request_id": request_id,
        "enabled": enabled, "values": values,
    }


def _view(document):
    return {**document, "content_address": content_address(document)}


class ResearchSettingsRepository:
    """Each update inserts one immutable revision using a unique-key CAS."""
    def __init__(self, session):
        self.session = session

    def lock_owner(self, owner_id):
        connection = self.session.connection()
        if connection.dialect.name == "sqlite":
            if not connection.connection.driver_connection.in_transaction:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
        owner = self.session.scalar(select(Organization).where(
            Organization.organization_id == owner_id, Organization.status == "active").with_for_update())
        if owner is None:
            raise SettingsConflict("The workspace is unavailable. Sign in to an active workspace.")

    def _query(self, owner_id, graph_identifier):
        model = WorkspaceResearchSettingsRevision if graph_identifier is None else StrategyResearchSettingsRevision
        query = select(model).where(model.owner_id == owner_id)
        if graph_identifier is not None:
            query = query.where(model.graph_identifier == graph_identifier)
        return model, query

    def _read_row(self, row):
        document = json.loads(row.document_json)
        _validate_update_identity(row.revision - 1, row.request_id, document.get("enabled"))
        graph = getattr(row, "graph_identifier", None)
        expected = _document(row.owner_id, graph, row.revision, row.revision - 1,
                             row.request_id, validate_values(document["values"], sparse=graph is not None, schema=document["schema"]),
                             document["enabled"], schema=document["schema"])
        if canonical_json(document) != canonical_json(expected) or content_address(document) != row.content_address:
            raise ValueError("Stored research settings identity is invalid.")
        return _view(document)

    def read(self, *, owner_id: str, graph_identifier: str | None = None):
        model, query = self._query(owner_id, graph_identifier)
        row = self.session.scalar(query.order_by(model.revision.desc()).limit(1))
        if row is not None:
            return self._read_row(row)
        values = _defaults(CURRENT_SCHEMA) if graph_identifier is None else {}
        return _view(_document(owner_id, graph_identifier, 0, 0, None, values, True))

    def read_revision(self, *, owner_id, graph_identifier=None, revision):
        if revision == 0:
            values = _defaults(CURRENT_SCHEMA) if graph_identifier is None else {}
            return _view(_document(owner_id, graph_identifier, 0, 0, None, values, True))
        model, query = self._query(owner_id, graph_identifier)
        row = self.session.scalar(query.where(model.revision == revision))
        if row is None:
            raise SettingsConflict("The selected settings revision is unavailable. Reload the preview.")
        return self._read_row(row)

    def snapshot(self, *, owner_id, graph_identifier, workspace_revision, strategy_revision,
                 run_overrides, require_current=True):
        if require_current:
            current = self.effective(owner_id=owner_id, graph_identifier=graph_identifier)
            if (current["workspace"]["revision"], current["strategy"]["revision"]) != (workspace_revision, strategy_revision):
                raise SettingsConflict("Research settings changed. Review the current preview before starting.")
        return resolve_snapshot(owner_id=owner_id, graph_identifier=graph_identifier,
            workspace=self.read_revision(owner_id=owner_id, revision=workspace_revision),
            strategy=self.read_revision(owner_id=owner_id, graph_identifier=graph_identifier, revision=strategy_revision),
            run_overrides=run_overrides)

    def _replay(self, owner_id, graph_identifier, request_id, expected):
        model, query = self._query(owner_id, graph_identifier)
        row = self.session.scalar(query.where(model.request_id == request_id))
        if row is None:
            return None
        actual = self._read_row(row)
        try:
            values = validate_values(expected["values"], sparse=graph_identifier is not None,
                                     schema=actual["schema"])
        except ValueError as exc:
            raise SettingsConflict("This request ID was already used with different settings.") from exc
        replay = {**expected, "schema": actual["schema"], "values": values}
        if canonical_json(actual) != canonical_json(_view(replay)):
            raise SettingsConflict("This request ID was already used with different settings.")
        return actual

    def update(self, *, owner_id, created_by, expected_revision, request_id, values,
               graph_identifier=None, enabled=True):
        _validate_update_identity(expected_revision, request_id, enabled)
        self.lock_owner(owner_id)
        normalized_values = validate_values(values, sparse=graph_identifier is not None)
        if graph_identifier is None and normalized_values["optimization"]["enabled"]:
            raise ValueError("Optimization axes belong to one saved strategy. Configure them in strategy Settings.")
        document = _document(owner_id, graph_identifier, expected_revision + 1,
                             expected_revision, request_id, values, enabled)
        replay = self._replay(owner_id, graph_identifier, request_id, document)
        if replay is not None:
            return replay
        document["values"] = normalized_values
        current = self.read(owner_id=owner_id, graph_identifier=graph_identifier)
        if current["revision"] != expected_revision:
            raise SettingsConflict("Settings changed. Reload the current values before saving.")
        return self._insert(document, created_by)

    def _insert(self, document, created_by):
        graph = document["graph_identifier"]
        model, _ = self._query(document["owner_id"], graph)
        fields = dict(owner_id=document["owner_id"], revision=document["revision"],
                      request_id=document["request_id"], created_by=created_by,
                      created_at=dt.datetime.now(dt.UTC).replace(tzinfo=None),
                      document_json=json.dumps(document, sort_keys=True, separators=(",", ":")),
                      content_address=content_address(document))
        if graph is not None:
            fields["graph_identifier"] = graph
        try:
            self.session.add(model(**fields))
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            return self._reconcile_insert(document, exc)
        return _view(document)

    def _reconcile_insert(self, document, error):
        replay = self._replay(document["owner_id"], document["graph_identifier"],
                              document["request_id"], document)
        if replay is not None:
            return replay
        raise SettingsConflict("Settings changed or the owner is no longer available. Reload before saving.") from error

    def effective(self, *, owner_id, graph_identifier):
        workspace = self.read(owner_id=owner_id)
        strategy = self.read(owner_id=owner_id, graph_identifier=graph_identifier)
        overrides = strategy["values"] if strategy["enabled"] else {}
        values = {**_defaults(CURRENT_SCHEMA), **workspace["values"], **overrides}
        return {"workspace": workspace, "strategy": strategy, "values": values,
                "sources": {key: "strategy" if key in overrides else "workspace" for key in values}}


def _revision_number(document):
    revision = document["revision"]
    if type(revision) is not int or revision < 0 or type(document["enabled"]) is not bool:
        raise ValueError("Pinned settings revision is invalid.")
    return revision


def _validate_revision_view(document, owner_id, graph_identifier):
    if not isinstance(document, dict) or set(document) != {
        "schema", "owner_id", "graph_identifier", "revision", "expected_revision",
        "request_id", "enabled", "values", "content_address",
    }:
        raise ValueError("Pinned settings revision is incomplete.")
    revision = _revision_number(document)
    schema = document["schema"]
    if schema not in {"research-settings-revision/1", "research-settings-revision/2", CURRENT_SCHEMA}:
        raise ValueError("Unsupported research settings revision.")
    values = validate_values(document["values"], sparse=graph_identifier is not None, schema=schema)
    expected = _document(owner_id, graph_identifier, revision, max(0, revision - 1),
                         document["request_id"], values, document["enabled"], schema=schema)
    if revision > 0:
        _validate_update_identity(revision - 1, document["request_id"], document["enabled"])
    if revision == 0:
        expected = _document(owner_id, graph_identifier, 0, 0, None,
                             dict(_defaults(schema)) if graph_identifier is None else {}, True, schema=schema)
    if canonical_json(document) != canonical_json(_view(expected)):
        raise ValueError("Pinned settings revision identity differs.")


def _snapshot_schema(workspace, strategy, run_overrides):
    if "optimization" in run_overrides or any(row["schema"] == CURRENT_SCHEMA for row in (workspace, strategy)):
        return "research-settings-snapshot/3"
    legacy = workspace["schema"] == strategy["schema"] == "research-settings-revision/1"
    return ("research-settings-snapshot/1" if legacy and not set(run_overrides).difference(LEGACY_DEFAULTS)
            else "research-settings-snapshot/2")


def _validate_snapshot_schema(schema, workspace, strategy):
    _defaults(schema)
    version = int(schema.rsplit("/", 1)[1])
    if any(int(row["schema"].rsplit("/", 1)[1]) > version for row in (workspace, strategy)):
        raise ValueError("Snapshots cannot reinterpret a newer settings revision as an older version.")


def resolve_snapshot(*, owner_id, graph_identifier, workspace, strategy, run_overrides, schema=None):
    _validate_revision_view(workspace, owner_id, None)
    _validate_revision_view(strategy, owner_id, graph_identifier)
    schema = schema or _snapshot_schema(workspace, strategy, run_overrides)
    _validate_snapshot_schema(schema, workspace, strategy)
    intent = validate_values(run_overrides, sparse=True, schema=schema)
    overrides = strategy["values"] if strategy["enabled"] else {}
    values = {**_defaults(schema), **workspace["values"], **overrides, **intent}
    sources = {key: "strategy" if key in overrides else "workspace" for key in values}
    sources.update({key: "run" for key in intent})
    document = {"schema": schema, "owner_id": owner_id,
                "graph_identifier": graph_identifier, "workspace": workspace,
                "strategy": strategy, "run_overrides": intent, "values": values, "sources": sources}
    return {**document, "content_address": content_address(document)}


def validate_snapshot(document, *, owner_id, graph_identifier):
    if not isinstance(document, dict):
        raise ValueError("Pinned settings snapshot is missing.")
    expected = resolve_snapshot(owner_id=owner_id, graph_identifier=graph_identifier,
        workspace=document.get("workspace"), strategy=document.get("strategy"),
        run_overrides=document.get("run_overrides"), schema=document.get("schema"))
    if canonical_json(document) != canonical_json(expected):
        raise ValueError("Pinned research settings snapshot differs.")
    return expected
