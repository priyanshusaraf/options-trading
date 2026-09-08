from __future__ import annotations

import json
import datetime as dt
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import SessionLocal, init_db
from app.db.models import Organization
from research.config import research_database_url
from research.domain.base import ResearchBase, init_research_db, make_engine, make_sessionmaker


def _csv_spec(*, asset_class="INDEX", volume=None):
    return {
        "instrument": "NIFTY 50",
        "source_label": "NSE Indices historical export",
        "venue_code": "XNSE",
        "asset_class": asset_class,
        "columns": {
            "instrument": "Index Name", "date": "Date", "open": "Open",
            "high": "High", "low": "Low", "close": "Close", "volume": volume,
        },
    }


def _csv(rows):
    return ("Index Name,Date,Open,High,Low,Close\n" + "\n".join(rows) + "\n").encode()


def _upload(client, project_id, action, raw, spec=None, session_metadata=None):
    files = {"file": ("daily.csv", raw, "text/csv")}
    if session_metadata is not None:
        files["session_metadata"] = ("sessions.json", session_metadata, "application/json")
    return client.post(
        f"/api/v1/ir/projects/{project_id}/research-datasets/{action}",
        data={"metadata": json.dumps(spec or _csv_spec())},
        files=files,
    )


def test_instrument_display_name_never_uses_a_foreign_or_different_alias(monkeypatch):
    from app.api.research_dataset_routes import _instrument_display_name
    from app.market_truth.identity import MarketTruthError
    import app.market_data.observations as observations
    import app.market_truth.identity as identity

    physical = SimpleNamespace(address="instrument-a", venue_code="XNSE", asset_class="EQUITY", contract_kind="SPOT")
    manifest = SimpleNamespace(owner_id="owner-a", provider_observation_addresses=("observation-a",))
    observation = SimpleNamespace(owner_id="owner-a", mapping_address="mapping-a")
    alias = SimpleNamespace(canonical_instrument_address="instrument-a", provider_symbol="RELIANCE")
    monkeypatch.setattr(observations, "load_provider_observation", lambda *args: observation)
    monkeypatch.setattr(identity, "load_provider_alias", lambda *args: alias)
    assert _instrument_display_name(None, manifest, physical, None) == "RELIANCE · XNSE · EQUITY SPOT"
    observation.owner_id = "owner-b"
    with pytest.raises(MarketTruthError):
        _instrument_display_name(None, manifest, physical, None)
    observation.owner_id = "owner-a"
    alias.canonical_instrument_address = "instrument-b"
    with pytest.raises(MarketTruthError):
        _instrument_display_name(None, manifest, physical, None)
    manifest.provider_observation_addresses = ()
    assert _instrument_display_name(None, manifest, physical, None) is None
    assert _instrument_display_name(None, manifest, physical, "CSV name") == "CSV name · XNSE · EQUITY SPOT"


@pytest.fixture(autouse=True)
def _stores(monkeypatch):
    init_db(reset=True)
    engine = make_engine(research_database_url())
    ResearchBase.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE IF EXISTS research_schema_version")
    init_research_db(engine)
    engine.dispose()
    monkeypatch.setattr(get_settings(), "research_enabled", True)
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")


def test_real_canonical_dataset_index_is_owner_scoped_bounded_and_selection_ready():
    from app.main import app
    from research_tests.test_canonical_dataset import seed_canonical
    project = TestClient(app).post("/api/v1/ir/projects", json={"name": "Datasets", "description": ""}).json()
    engine = make_engine(research_database_url())
    Session = make_sessionmaker(engine)
    try:
        with SessionLocal() as execution_session, Session() as research_session:
            manifest = seed_canonical(execution_session, research_session, count=4, owner="owner")
    finally:
        engine.dispose()
    client = TestClient(app)
    response = client.get(f"/api/v1/ir/projects/{project['project_id']}/research-datasets?limit=1")
    assert response.status_code == 200, response.text
    assert response.json()["schema"] == "strategy-os-canonical-dataset-index/1"
    assert response.json()["next_cursor"] is None
    item = response.json()["items"][0]
    assert item["manifest_address"] == manifest.manifest_address
    assert item["instrument_address"] == manifest.instrument_addresses[0]
    assert item["canonical_instrument_label"].startswith("XNSE · EQUITY SPOT · ")
    assert item["instrument_display_name"] == "NIFTY · XNSE · EQUITY SPOT"
    assert item["interval"] == "15minute"
    assert item["bar_count"] == 4
    assert item["backtest_eligibility"] == "ELIGIBLE_Q03"
    assert item["refusal_code"] is None
    serialized = str(item).lower()
    assert "provider_token" not in serialized and "credential" not in serialized

    from fastapi import HTTPException
    from app.api.research_dataset_routes import _item
    wrong_address = SimpleNamespace(
        canonical_bytes=manifest.canonical_bytes, manifest_address="sha256:" + "0" * 64)
    with pytest.raises(HTTPException) as refused:
        _item(None, None, wrong_address)
    assert refused.value.status_code == 409
    assert refused.value.detail["code"] == "CANONICAL_DATASET_AUTHORITY_CORRUPT"


def test_unsupported_canonical_history_is_an_explicit_server_refusal():
    from app.main import app
    from research_tests.test_canonical_dataset import seed_canonical
    client = TestClient(app)
    project = client.post("/api/v1/ir/projects", json={"name": "Unsupported", "description": ""}).json()
    engine = make_engine(research_database_url()); Session = make_sessionmaker(engine)
    try:
        with SessionLocal() as execution_session, Session() as research_session:
            manifest = seed_canonical(execution_session, research_session, count=4,
                                      owner="owner", asset_class="INDEX")
    finally:
        engine.dispose()
    response = client.get(f"/api/v1/ir/projects/{project['project_id']}/research-datasets")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["manifest_address"] == manifest.manifest_address
    assert item["backtest_eligibility"] == "UNAVAILABLE"
    assert item["refusal_code"] == "CANONICAL_INDEX_BENCHMARK_ONLY"


def test_missing_or_foreign_project_is_private_absence_and_query_bounds_are_closed(monkeypatch):
    from app.main import app
    client = TestClient(app)
    assert client.get("/api/v1/ir/projects/project.missing/research-datasets").status_code == 404
    assert client.get("/api/v1/ir/projects/project.missing/research-datasets?limit=51").status_code == 422


def test_real_foreign_dataset_endpoint_matches_guessed_private_absence(monkeypatch):
    from app.main import app
    settings = get_settings()
    monkeypatch.setattr(settings, "owner_id", "owner.dataset-a")
    with SessionLocal.begin() as session:
        session.add_all([Organization(organization_id="owner.dataset-a", name="A"),
                         Organization(organization_id="owner.dataset-b", name="B")])
    client = TestClient(app)
    project = client.post("/api/v1/ir/projects", json={"name": "Private dataset", "description": ""}).json()
    monkeypatch.setattr(settings, "owner_id", "owner.dataset-b")
    foreign = client.get(f"/api/v1/ir/projects/{project['project_id']}/research-datasets")
    guessed = client.get("/api/v1/ir/projects/project.guessed/research-datasets")
    assert foreign.status_code == guessed.status_code == 404
    assert foreign.json() == guessed.json()


def test_daily_ohlc_csv_inspection_preserves_absent_volume_and_declares_assumptions():
    from app.main import app
    client = TestClient(app)
    project = client.post("/api/v1/ir/projects", json={"name": "Imported", "description": ""}).json()
    response = _upload(client, project["project_id"], "inspect-csv", _csv([
        "NIFTY 50,04 Sep 2026,100,102,99,101",
        "NIFTY 50,03 Sep 2026,99,101,98,100",
    ]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema"] == "strategy-os-user-csv-inspection/1"
    assert body["source_type"] == "USER_SUPPLIED"
    assert body["source_order"] == "DESCENDING"
    assert body["fields"] == ["OPEN", "HIGH", "LOW", "CLOSE"]
    assert body["historical_source_availability"] == "NOT_SUPPLIED"
    assert body["calendar_coverage"] == "NOT_ASSERTED"
    assert body["rights_scope"] == "PERSONAL_RESEARCH_ONLY"

    no_symbol = _csv_spec()
    no_symbol["columns"]["instrument"] = None
    normalized = _upload(
        client, project["project_id"], "inspect-csv",
        b"Date,Open,High,Low,Close\n2026-09-03,99,101,98,100\n",
        {**no_symbol, "date_format": "%Y-%m-%d"},
    )
    assert normalized.status_code == 200, normalized.text
    assert normalized.json()["row_count"] == 1
    opened = {**_csv_spec(), "authority_namespace": "client-controlled"}
    assert _upload(
        client, project["project_id"], "inspect-csv",
        _csv(["NIFTY 50,03 Sep 2026,99,101,98,100"]), opened,
    ).status_code == 422
    from research.data.user_csv_import import MAX_CSV_BYTES
    assert _upload(
        client, project["project_id"], "inspect-csv", b"x" * (MAX_CSV_BYTES + 1),
    ).status_code == 413


@pytest.mark.parametrize(("raw", "code"), [
    (_csv(["NIFTY 50,03 Sep 2026,99,101,98,100",
           "NIFTY 50,03 Sep 2026,99,101,98,100"]), "CSV_DUPLICATE_DATE"),
    (_csv(["NIFTY 50,03 Sep 2026,99,101,98,NaN"]), "CSV_VALUE_INVALID"),
    (_csv(["NIFTY BANK,03 Sep 2026,99,101,98,100"]), "CSV_INSTRUMENT_MISMATCH"),
    (_csv(["NIFTY 50,not-a-date,99,101,98,100"]), "CSV_DATE_INVALID"),
    (_csv(["NIFTY 50,03 Sep 2026,99,98,97,100"]), "CSV_OHLC_INVALID"),
    (b"Index Name,Date,Open,High,Close\nNIFTY 50,03 Sep 2026,99,101,100\n",
     "CSV_HEADER_MISMATCH"),
    (b"Index Name,Date,Open,High,Low,Close,Close\n"
     b"NIFTY 50,03 Sep 2026,99,101,98,100,101\n", "CSV_HEADER_MISMATCH"),
])
def test_csv_inspection_refuses_duplicate_nonfinite_and_missing_required_data(raw, code):
    from app.main import app
    client = TestClient(app)
    project = client.post("/api/v1/ir/projects", json={"name": "Invalid", "description": ""}).json()
    response = _upload(client, project["project_id"], "inspect-csv", raw)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == code


def test_foreign_project_csv_import_matches_private_absence(monkeypatch):
    from app.main import app
    import app.api.research_dataset_routes as routes
    settings = get_settings()
    monkeypatch.setattr(settings, "owner_id", "owner.dataset-a")
    with SessionLocal.begin() as session:
        session.add_all([Organization(organization_id="owner.dataset-a", name="A"),
                         Organization(organization_id="owner.dataset-b", name="B")])
    client = TestClient(app)
    project = client.post("/api/v1/ir/projects", json={"name": "Private", "description": ""}).json()
    monkeypatch.setattr(settings, "owner_id", "owner.dataset-b")
    monkeypatch.setattr(
        routes, "make_engine",
        lambda *_args, **_kwargs: pytest.fail("foreign project initialized research storage"),
    )
    raw = _csv(["NIFTY 50,03 Sep 2026,99,101,98,100"])
    foreign = _upload(client, project["project_id"], "import-csv", raw)
    guessed = _upload(client, "project.guessed", "import-csv", raw)
    assert foreign.status_code == guessed.status_code == 404
    assert foreign.json() == guessed.json()


def test_imported_daily_ohlc_is_listed_and_read_as_price_only_benchmark(monkeypatch):
    from app.main import app
    import app.api.research_dataset_routes as routes
    from research.data.canonical_dataset import (
        CanonicalDatasetRefused,
        load_canonical_datasets,
        project_verified_research_inputs,
    )

    observed_at = dt.datetime(2026, 9, 5, 2, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(routes, "_now", lambda: observed_at)
    client = TestClient(app)
    project = client.post("/api/v1/ir/projects", json={"name": "Imported", "description": ""}).json()
    raw = _csv([
        "NIFTY 50,28 Aug 2026,99,101,98,100",
        "NIFTY 50,04 Sep 2026,100,102,99,101",
    ])
    imported = _upload(client, project["project_id"], "import-csv", raw)
    assert imported.status_code == 200, imported.text
    receipt = imported.json()
    assert receipt["imported_at"] == observed_at.isoformat()
    assert receipt["historical_source_availability"] == "NOT_SUPPLIED"
    from app.db.models import AuthorityRawSegment
    with SessionLocal() as session:
        stored_raw = session.query(AuthorityRawSegment).one()
        assert bytes(stored_raw.raw_bytes) == raw
        assert stored_raw.byte_digest == receipt["source_sha256"]

    listed = client.get(
        f"/api/v1/ir/projects/{project['project_id']}/research-datasets").json()["items"]
    assert len(listed) == 1
    assert listed[0]["manifest_address"] == receipt["manifest_address"]
    assert listed[0]["interval"] == "day"
    assert listed[0]["canonical_instrument_label"].startswith("NIFTY 50 · XNSE · INDEX SPOT")
    assert listed[0]["instrument_display_name"] == "NIFTY 50 · XNSE · INDEX SPOT"
    assert listed[0]["fields"] == ["CLOSE", "HIGH", "LOW", "OPEN"]
    assert listed[0]["source_type"] == "USER_SUPPLIED"
    assert listed[0]["provider_evidence_state"] == "USER_CSV_SHAPE_VALIDATED"
    assert listed[0]["market_truth_state"] == "RECONSTRUCTED_WITH_GAPS"
    assert listed[0]["research_compatibility"] == "BENCHMARK_INPUT_ONLY"
    assert listed[0]["backtest_eligibility"] == "UNAVAILABLE"
    assert listed[0]["refusal_code"] == "CANONICAL_INDEX_BENCHMARK_ONLY"
    other_project = client.post(
        "/api/v1/ir/projects", json={"name": "Other", "description": ""}).json()
    assert client.get(
        f"/api/v1/ir/projects/{other_project['project_id']}/research-datasets"
    ).json()["items"] == []

    engine = make_engine(research_database_url())
    ResearchSession = make_sessionmaker(engine)
    try:
        with SessionLocal() as execution_session, ResearchSession() as research_session:
            selection = SimpleNamespace(
                manifest_address=receipt["manifest_address"],
                as_of=dt.datetime.fromisoformat(receipt["ready_as_of"]),
            )
            _, dataset = load_canonical_datasets(
                research_session, execution_session=execution_session,
                owner_id="owner", selections=[selection], now=selection.as_of,
            )[0]
            assert dataset.interval == "day"
            assert dataset.bar_count == 2
            assert [candle.ts.date() for candle in dataset.candles] == [
                dt.date(2026, 8, 27), dt.date(2026, 9, 3)]
            assert dataset.candles[1].ts - dataset.candles[0].ts == dt.timedelta(days=7)
            assert all(candle.volume is None for candle in dataset.candles)
            assert dataset._verified_authority.manifest.mode == "RESEARCH"
            assert dataset._verified_authority.manifest.purpose == \
                f"user-supplied-personal-research:{project['project_id']}"
            assert dataset.binding["projection"] is None
            timing = dataset.binding["time_interpretation"]
            assert timing["retrospective_evaluation"] is True
            assert timing["historical_source_availability"] == "NOT_SUPPLIED"
            assert timing["actual_source_observed_at"] == observed_at.isoformat()
            projected = project_verified_research_inputs(
                dataset, owner_id="owner", graph_input_fields={"benchmark": ("CLOSE",)})
            assert list(projected.inputs["benchmark"]["close"]) == [100.0, 101.0]
            with pytest.raises(CanonicalDatasetRefused):
                project_verified_research_inputs(
                    dataset, owner_id="owner", graph_input_fields={"benchmark": ("VOLUME",)})
    finally:
        engine.dispose()


def test_durable_browser_session_requires_csrf_and_viewer_cannot_import(monkeypatch):
    from app.accounts import browser_auth
    from app.api.principal import issue_user_session
    from app.db.models import Membership, User
    from app.main import app

    origin = "https://testserver"
    settings = get_settings()
    for name, value in {
        "browser_auth_enabled": True,
        "browser_auth_origin": origin,
        "browser_auth_counter_secret": "c3" * 32,
        "auth_disabled": False,
        "api_token": "",
    }.items():
        monkeypatch.setattr(settings, name, value)
    init_db(reset=True)
    invite = browser_auth.create_invite("csv-owner@example.test")
    browser = TestClient(app, base_url=origin)
    enrolled = browser.post("/api/v1/auth/enroll", headers={"Origin": origin}, json={
        "email": "csv-owner@example.test",
        "password": "a synthetic sufficiently long password",
        "display_name": "CSV Owner",
        "invitation": invite.token,
    })
    assert enrolled.status_code == 200, enrolled.text
    state = browser.get("/api/v1/auth/session").json()
    headers = {"Origin": origin, "x-strategy-csrf": state["csrf"]}
    project = browser.post(
        "/api/v1/ir/projects", headers=headers,
        json={"name": "Durable import", "description": ""},
    ).json()
    raw = _csv(["NIFTY 50,03 Sep 2026,99,101,98,100"])
    assert _upload(browser, project["project_id"], "inspect-csv", raw).status_code == 403
    allowed = browser.post(
        f"/api/v1/ir/projects/{project['project_id']}/research-datasets/inspect-csv",
        headers=headers, data={"metadata": json.dumps(_csv_spec())},
        files={"file": ("daily.csv", raw, "text/csv")},
    )
    assert allowed.status_code == 200, allowed.text

    organization_id = state["memberships"][0]["organization_id"]
    with SessionLocal.begin() as session:
        session.add(User(user_id="csv-viewer", email_normalized="csv-viewer@example.test",
                         display_name="CSV Viewer"))
        session.flush()
        session.add(Membership(organization_id=organization_id, user_id="csv-viewer",
                               role="viewer", status="active"))
        issued = issue_user_session(
            session, user_id="csv-viewer", organization_id=organization_id,
            expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
        )
    viewer = TestClient(app)
    denied = viewer.post(
        f"/api/v1/ir/projects/{project['project_id']}/research-datasets/import-csv",
        headers={"Authorization": f"Bearer {issued.token}"},
        data={"metadata": json.dumps(_csv_spec())},
        files={"file": ("daily.csv", raw, "text/csv")},
    )
    assert denied.status_code == 403


def test_import_retry_reconciles_after_publication_failure(monkeypatch):
    from app.db.models import AuthorityRawSegment
    from app.main import app
    import app.api.research_dataset_routes as routes
    from research.domain.models import ResearchDatasetManifestV2

    observed_at = dt.datetime(2026, 9, 5, 2, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(routes, "_now", lambda: observed_at)
    client = TestClient(app, raise_server_exceptions=False)
    project = client.post("/api/v1/ir/projects", json={"name": "Retry", "description": ""}).json()
    raw = _csv(["NIFTY 50,03 Sep 2026,99,101,98,100"])
    publish = routes.publish_user_csv
    monkeypatch.setattr(routes, "publish_user_csv",
                        lambda *_args: (_ for _ in ()).throw(RuntimeError("synthetic publication failure")))
    failed = _upload(client, project["project_id"], "import-csv", raw)
    assert failed.status_code == 500
    with SessionLocal() as session:
        assert session.query(AuthorityRawSegment).count() == 1
    engine = make_engine(research_database_url())
    ResearchSession = make_sessionmaker(engine)
    try:
        with ResearchSession() as session:
            assert session.query(ResearchDatasetManifestV2).count() == 0
        monkeypatch.setattr(routes, "publish_user_csv", publish)
        first = _upload(client, project["project_id"], "import-csv", raw)
        monkeypatch.setattr(routes, "_now", lambda: observed_at + dt.timedelta(minutes=30))
        retry = _upload(client, project["project_id"], "import-csv", raw)
        assert first.status_code == retry.status_code == 200
        assert first.json()["manifest_address"] == retry.json()["manifest_address"]
        assert first.json()["imported_at"] == retry.json()["imported_at"] == observed_at.isoformat()
        revised = _upload(
            TestClient(app), project["project_id"], "import-csv",
            _csv(["NIFTY 50,03 Sep 2026,99,102,98,101"]),
        )
        assert revised.status_code == 422
        assert revised.json()["detail"]["code"] == "CSV_REVISION_UNSUPPORTED"
        with SessionLocal() as session:
            assert session.query(AuthorityRawSegment).count() == 1
        with ResearchSession() as session:
            assert session.query(ResearchDatasetManifestV2).count() == 1
        later = observed_at + dt.timedelta(hours=1)
        monkeypatch.setattr(routes, "_now", lambda: later)
        changed_spec = {**_csv_spec(), "source_label": "A distinct declaration"}
        changed = _upload(
            TestClient(app), project["project_id"], "import-csv", raw, changed_spec)
        assert changed.status_code == 200, changed.text
        assert changed.json()["imported_at"] == later.isoformat()
        assert changed.json()["manifest_address"] != first.json()["manifest_address"]
        with SessionLocal() as session:
            assert session.query(AuthorityRawSegment).count() == 2
    finally:
        engine.dispose()


def test_same_owner_can_import_two_instruments_on_the_same_date(monkeypatch):
    from app.main import app
    import app.api.research_dataset_routes as routes

    monkeypatch.setattr(
        routes, "_now",
        lambda: dt.datetime(2026, 9, 5, 2, 0, tzinfo=dt.timezone.utc),
    )
    client = TestClient(app)
    project = client.post("/api/v1/ir/projects", json={"name": "Two", "description": ""}).json()
    first = _upload(
        client, project["project_id"], "import-csv",
        _csv(["NIFTY 50,03 Sep 2026,99,101,98,100"]),
    )
    second_spec = {**_csv_spec(), "instrument": "NIFTY BANK"}
    second = _upload(
        client, project["project_id"], "import-csv",
        _csv(["NIFTY BANK,03 Sep 2026,199,201,198,200"]), second_spec,
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["manifest_address"] != second.json()["manifest_address"]

    first_page = client.get(
        f"/api/v1/ir/projects/{project['project_id']}/research-datasets?limit=1").json()
    assert len(first_page["items"]) == 1
    assert first_page["next_cursor"] == first_page["items"][0]["manifest_address"]
    next_page = client.get(
        f"/api/v1/ir/projects/{project['project_id']}/research-datasets",
        params={"limit": 1, "after": first_page["next_cursor"]},
    ).json()
    assert len(next_page["items"]) == 1
    assert next_page["next_cursor"] is None
    assert {first_page["items"][0]["manifest_address"],
            next_page["items"][0]["manifest_address"]} == {
                first.json()["manifest_address"], second.json()["manifest_address"]}


@pytest.mark.parametrize(("field", "value", "code"), [
    ("source_label", " ", "CSV_MAPPING_INVALID"),
    ("venue_code", "UNSUPPORTED", "CSV_MAPPING_UNSUPPORTED"),
    ("date_format", "%m/%d/%Y", "CSV_MAPPING_UNSUPPORTED"),
])
def test_internal_csv_import_rejects_invalid_declarations(field, value, code):
    from dataclasses import replace
    from app.api.research_dataset_routes import UserCsvDatasetSpec
    from research.data.user_csv_import import UserCsvImportRefused, inspect_user_csv

    spec = replace(UserCsvDatasetSpec(**_csv_spec()).importer_spec(), **{field: value})
    with pytest.raises(UserCsvImportRefused) as refused:
        inspect_user_csv(
            _csv(["NIFTY 50,03 Sep 2026,99,101,98,100"]), spec,
            observed_at=dt.datetime(2026, 9, 5, tzinfo=dt.timezone.utc))
    assert refused.value.code == code


def test_corrupt_dataset_manifest_has_a_stable_authority_refusal():
    from fastapi import HTTPException
    from app.api.research_dataset_routes import _item

    with pytest.raises(HTTPException) as refused:
        _item(None, None, SimpleNamespace(canonical_bytes=b"{}"))
    assert refused.value.status_code == 409
    assert refused.value.detail["code"] == "CANONICAL_DATASET_AUTHORITY_CORRUPT"


def _csv_limit_probe(messages, *, headers=(), path=None, method="POST", scope_type="http", root_path=""):
    """Drive the ASGI limit directly, keeping received and replayed bytes visible."""
    import asyncio
    from starlette.responses import JSONResponse
    from app.api.csv_request_limits import CsvRequestBodyLimitMiddleware

    result = {"received": [], "delivered": [], "responses": [], "called": 0}
    queued = iter(messages)

    async def receive():
        message = next(queued, {"type": "http.disconnect"})
        result["received"].append(message)
        return message

    async def send(message):
        result["responses"].append(message)

    async def downstream(scope, receive, send):
        result["called"] += 1
        result["received_at_entry"] = len(result["received"])
        while True:
            message = await receive()
            result["delivered"].append(message)
            if not message.get("more_body", False):
                break
        result["after_body"] = await receive()
        await JSONResponse({"ok": True})(scope, receive, send)

    scope = {"type": scope_type, "method": method, "headers": list(headers),
             "path": path or "/api/ir/projects/p/research-datasets/import-csv", "root_path": root_path}
    if scope_type != "http":
        scope.pop("method")
    asyncio.run(CsvRequestBodyLimitMiddleware(downstream, max_file_bytes=32)(scope, receive, send))
    return result


@pytest.mark.parametrize("prefix", ("/api", "/api/v1"))
@pytest.mark.parametrize("action", ("inspect-csv", "import-csv"))
@pytest.mark.parametrize("declared", (None, b"1"))
def test_csv_request_limit_counts_actual_chunks_before_downstream(prefix, action, declared):
    from app.api.csv_request_limits import CSV_MULTIPART_ALLOWANCE

    limit = 32 + CSV_MULTIPART_ALLOWANCE
    headers = [] if declared is None else [(b"content-length", declared)]
    messages = [
        {"type": "http.request", "body": b"x" * limit, "more_body": True},
        {"type": "http.request", "body": b"y", "more_body": True},
        {"type": "http.request", "body": b"not consumed", "more_body": False},
    ]
    result = _csv_limit_probe(messages, headers=headers,
                             path=f"{prefix}/ir/projects/p/research-datasets/{action}")
    assert result["called"] == 0
    assert len(result["received"]) == 2
    assert result["responses"][0]["status"] == 413
    assert json.loads(result["responses"][1]["body"])["detail"]["code"] == "CSV_REQUEST_TOO_LARGE"


@pytest.mark.parametrize("headers,status", (
    ([(b"content-length", b"65569")], 413),
    ([(b"content-length", b"-1")], 400),
    ([(b"content-length", b"invalid")], 400),
    ([(b"content-length", b"9" * 5000)], 400),
    ([(b"content-length", b"1"), (b"Content-Length", b"1")], 400),
))
def test_csv_request_limit_rejects_declared_lengths_without_receiving(headers, status):
    result = _csv_limit_probe([], headers=headers)
    assert result["called"] == 0
    assert result["received"] == []
    assert result["responses"][0]["status"] == status


@pytest.mark.parametrize("declared", (None, b"1", b"65568"))
def test_csv_request_limit_replays_the_exact_boundary_once(declared):
    from app.api.csv_request_limits import CSV_MULTIPART_ALLOWANCE

    limit = 32 + CSV_MULTIPART_ALLOWANCE
    headers = [] if declared is None else [(b"content-length", declared)]
    messages = [{"type": "http.request", "body": b"a" * (limit - 1), "more_body": True},
                {"type": "http.request", "body": b"b", "more_body": False}]
    result = _csv_limit_probe(messages, headers=headers)
    assert result["received_at_entry"] == 2
    assert result["delivered"] == [{"type": "http.request", "body": b"a" * (limit - 1) + b"b", "more_body": False}]
    assert result["after_body"] == {"type": "http.disconnect"}
    assert result["responses"][0]["status"] == 200


def test_csv_request_disconnect_never_enters_downstream():
    result = _csv_limit_probe([
        {"type": "http.request", "body": b"partial", "more_body": True},
        {"type": "http.disconnect"},
    ])
    assert result["called"] == 0
    assert result["responses"] == []


@pytest.mark.parametrize("method,path,scope_type,root_path,expected", (
    ("POST", "/api/v1/ir/projects/review/research-datasets/import-csv\n", "http", "", 1),
    ("POST", "/mounted/api/ir/projects/p/research-datasets/inspect-csv", "http", "/mounted", 1),
    ("POST", "/api/ir/projects/p/research-datasets/import-csv/", "http", "", 0),
    ("POST", "/api/other", "http", "", 0),
    ("GET", "/api/ir/projects/p/research-datasets/import-csv", "http", "", 0),
    ("POST", "/api/ir/projects/p/research-datasets/import-csv", "websocket", "", 0),
))
def test_csv_request_limit_matches_only_registered_upload_shapes(method, path, scope_type, root_path, expected):
    result = _csv_limit_probe([{"type": "http.request", "body": b"", "more_body": False}],
                             method=method, path=path, scope_type=scope_type, root_path=root_path)
    assert result["received_at_entry"] == expected
    assert result["responses"][0]["status"] == 200


@pytest.mark.parametrize("count,consumed,refused", ((2000, 2000, False), (2001, 2001, True), (5000, 2001, True)))
def test_csv_row_limit_stops_the_reader_at_one_extra_row(monkeypatch, count, consumed, refused):
    import csv
    from app.api.research_dataset_routes import UserCsvDatasetSpec
    from research.data import user_csv_import

    original = csv.DictReader
    observed = []

    class CountedReader(original):
        def __next__(self):
            row = super().__next__()
            observed.append(None)
            return row

    monkeypatch.setattr(user_csv_import.csv, "DictReader", CountedReader)
    raw = _csv(["NIFTY 50,03 Sep 2026,99,101,98,100"] * count)
    spec = UserCsvDatasetSpec(**_csv_spec()).importer_spec()
    if refused:
        with pytest.raises(user_csv_import.UserCsvImportRefused) as failure:
            user_csv_import._csv_rows(raw, spec)
        assert failure.value.code == "CSV_ROW_COUNT_INVALID"
    else:
        assert len(user_csv_import._csv_rows(raw, spec)) == count
    assert len(observed) == consumed


def _oversized_multipart(*, extra_file=False):
    from research.data.user_csv_import import MAX_CSV_BYTES
    from app.api.csv_request_limits import CSV_MULTIPART_ALLOWANCE

    boundary = b"csv-request-boundary"
    body = b"--" + boundary + b'\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'
    body += json.dumps(_csv_spec()).encode() + b"\r\n"
    body += b"--" + boundary + b'\r\nContent-Disposition: form-data; name="file"; filename="daily.csv"\r\n\r\n'
    if extra_file:
        body += _csv(["NIFTY 50,03 Sep 2026,99,101,98,100"]) + b"\r\n"
        body += b"--" + boundary + b'\r\nContent-Disposition: form-data; name="extra"; filename="extra.csv"\r\n\r\n'
    body += b"x" * (MAX_CSV_BYTES + CSV_MULTIPART_ALLOWANCE + 1)
    return body + b"\r\n--" + boundary + b"--\r\n", "multipart/form-data; boundary=" + boundary.decode()


@pytest.mark.parametrize("prefix", ("/api", "/api/v1"))
@pytest.mark.parametrize("action", ("inspect-csv", "import-csv"))
@pytest.mark.parametrize("declared", (None, "1"))
@pytest.mark.parametrize("extra_file", (False, True))
def test_mounted_csv_limit_refuses_before_multipart_spooling(monkeypatch, prefix, action, declared, extra_file):
    from app.main import app
    from starlette.formparsers import MultiPartParser
    from tests.test_cross_tenant_idor import _headers, _seed_http_principals

    issued = _seed_http_principals(monkeypatch)

    async def no_parse(_self):
        pytest.fail("oversized upload reached multipart parsing")

    monkeypatch.setattr(MultiPartParser, "parse", no_parse)
    body, content_type = _oversized_multipart(extra_file=extra_file)
    headers = {**_headers(issued, "user.a"), "Content-Type": content_type}
    if declared is not None:
        headers["Content-Length"] = declared
    response = TestClient(app).post(
        f"{prefix}/ir/projects/project.absent/research-datasets/{action}",
        headers=headers, content=iter([body[:100], body[100:]]))
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "CSV_REQUEST_TOO_LARGE"


@pytest.mark.parametrize("prefix", ("/api", "/api/v1"))
@pytest.mark.parametrize("user", (None, "viewer.a"))
def test_csv_authorization_denies_before_body_limit(monkeypatch, prefix, user):
    from app.main import app
    from app.api import csv_request_limits
    from tests.test_cross_tenant_idor import _headers, _seed_http_principals

    issued = _seed_http_principals(monkeypatch)
    monkeypatch.setattr(csv_request_limits, "_is_csv_upload",
                        lambda *_args: pytest.fail("denied caller reached CSV body intake"))
    headers = {} if user is None else _headers(issued, user)
    response = TestClient(app).post(
        f"{prefix}/ir/projects/project.absent/research-datasets/import-csv",
        headers=headers, content=b"unused")
    assert response.status_code == (401 if user is None else 403)


@pytest.mark.parametrize("count", [248, 2000])
def test_supported_ohlcv_history_imports_publishes_and_loads_all_rows(count, monkeypatch):
    from app.main import app
    import app.api.research_dataset_routes as routes
    from research.data.canonical_dataset import load_canonical_datasets
    from app.market_data.dataset_authority import DatasetCreationEvidence
    from research.data.user_csv_import import MAX_CSV_ROWS
    assert MAX_CSV_ROWS * 5 * 2 == DatasetCreationEvidence.MAX_SOURCE_ADDRESSES
    monkeypatch.setattr(routes, "_now", lambda: dt.datetime(2026, 9, 5, tzinfo=dt.timezone.utc))
    client = TestClient(app)
    project = client.post('/api/v1/ir/projects', json={"name": "Full daily history", "description": ""}).json()
    spec = _csv_spec(asset_class="EQUITY", volume="Volume")
    spec.update(instrument="RELIANCE", source_label="Synthetic cardinality test", date_format="%Y-%m-%d")
    start = dt.date(2020, 1, 1)
    rows = [f"RELIANCE,{start + dt.timedelta(days=index)},100,102,99,101,1000" for index in range(count)]
    raw = ("Index Name,Date,Open,High,Low,Close,Volume\n" + "\n".join(rows) + "\n").encode()
    response = _upload(client, project["project_id"], "import-csv", raw, spec)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["row_count"] == count
    engine = make_engine(research_database_url()); ResearchSession = make_sessionmaker(engine)
    try:
        with SessionLocal() as execution_session, ResearchSession() as research_session:
            selection = SimpleNamespace(manifest_address=receipt["manifest_address"], as_of=dt.datetime.fromisoformat(receipt["ready_as_of"]))
            _, dataset = load_canonical_datasets(research_session, execution_session=execution_session,
                owner_id="owner", selections=[selection], now=selection.as_of)[0]
            assert dataset.bar_count == count
            assert dataset._verified_authority is not None
            manifest = dataset._verified_authority.manifest
            assert len(manifest.provider_observation_addresses) == count * 5
            assert len(manifest.normalized_observation_addresses) == count * 5
    finally:
        engine.dispose()


def _session_metadata_bytes():
    return json.dumps({"schema": "user-declared-daily-sessions/1", "provenance": "USER_DECLARED",
        "source": "Synthetic declared session times", "timezone": "Asia/Kolkata",
        "complete_full_sessions": True, "rows": [
            {"date_label": "2026-09-03", "session_id": "synthetic:03",
             "session_open_at": "2026-09-03T09:00:00+05:30", "session_close_at": "2026-09-03T13:00:00+05:30"},
            {"date_label": "2026-09-04", "session_id": "synthetic:04",
             "session_open_at": "2026-09-04T09:00:00+05:30", "session_close_at": "2026-09-04T15:00:00+05:30"},
        ]}).encode()


def _session_csv_bytes():
    return _csv(["NIFTY 50,04 Sep 2026,106,108,104,106", "NIFTY 50,03 Sep 2026,99,100,96,99"])


def test_session_metadata_api_inspection_import_and_exact_retry_keep_both_digests(monkeypatch):
    import hashlib
    from app.main import app
    import app.api.research_dataset_routes as routes
    monkeypatch.setattr(routes, "_now", lambda: dt.datetime(2026, 9, 5, tzinfo=dt.timezone.utc))
    client = TestClient(app)
    project = client.post("/api/v1/ir/projects", json={"name": "Session files", "description": ""}).json()
    raw, metadata = _session_csv_bytes(), _session_metadata_bytes()
    legacy = _upload(client, project["project_id"], "inspect-csv", raw)
    inspected = _upload(client, project["project_id"], "inspect-csv", raw, session_metadata=metadata)
    assert inspected.status_code == 200, inspected.text
    receipt = inspected.json()
    assert receipt["schema"] == "strategy-os-user-csv-inspection/2"
    assert receipt["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert receipt["session_metadata"] == {"state": "USER_DECLARED_COMPLETE",
        "schema": "user-declared-daily-sessions/1", "source": "Synthetic declared session times",
        "row_count": 2, "source_sha256": hashlib.sha256(metadata).hexdigest(), "byte_count": len(metadata)}
    assert receipt["calendar_coverage"] == "NOT_ASSERTED"
    assert receipt["historical_source_availability"] == "NOT_SUPPLIED"
    assert "session_metadata" not in legacy.json()
    assert {**{k: v for k, v in receipt.items() if k != "session_metadata"},
            "schema": "strategy-os-user-csv-inspection/1"} == legacy.json()
    imported = _upload(client, project["project_id"], "import-csv", raw, session_metadata=metadata)
    assert imported.status_code == 200, imported.text
    assert imported.json()["schema"] == "strategy-os-user-csv-import/2"
    assert imported.json()["session_metadata"] == receipt["session_metadata"]
    assert imported.json()["source_sha256"] == receipt["source_sha256"]
    monkeypatch.setattr(routes, "_now", lambda: dt.datetime(2026, 9, 6, tzinfo=dt.timezone.utc))
    retry = _upload(client, project["project_id"], "import-csv", raw, session_metadata=metadata)
    assert retry.status_code == 200, retry.text
    assert retry.content == imported.content
    changed = json.loads(metadata); changed["source"] = "Later declaration"
    refused = _upload(client, project["project_id"], "import-csv", raw, session_metadata=json.dumps(changed).encode())
    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "CSV_SESSION_METADATA_RETRY_MISMATCH"


@pytest.mark.parametrize("action", ["inspect-csv", "import-csv"])
def test_session_metadata_api_refuses_invalid_overlimit_and_missing_project_before_content_parse(monkeypatch, action):
    from app.main import app
    import app.api.research_dataset_routes as routes
    client = TestClient(app)
    project = client.post("/api/v1/ir/projects", json={"name": "Refusals", "description": ""}).json()
    invalid = _upload(client, project["project_id"], action, _session_csv_bytes(), session_metadata=b"{}")
    assert invalid.status_code == 422, invalid.text
    assert invalid.json()["detail"]["code"] == "CSV_SESSION_METADATA_REFUSED"
    oversized = _upload(client, project["project_id"], action, _session_csv_bytes(),
                        session_metadata=b"x" * (routes.MAX_SESSION_BYTES + 1))
    assert oversized.status_code == 413
    async def forbidden(_file):
        pytest.fail("missing project parsed uploaded contents")
    monkeypatch.setattr(routes, "_read_csv", forbidden)
    monkeypatch.setattr(routes, "_read_session_metadata", forbidden)
    missing = _upload(client, "project.absent", action, b"invalid", session_metadata=b"invalid")
    assert missing.status_code == 404


def test_session_metadata_api_cannot_backdate_new_sidecar_on_prior_csv(monkeypatch):
    from app.main import app
    import app.api.research_dataset_routes as routes
    monkeypatch.setattr(routes, "_now", lambda: dt.datetime(2026, 9, 5, tzinfo=dt.timezone.utc))
    client = TestClient(app)
    project = client.post("/api/v1/ir/projects", json={"name": "Existing CSV", "description": ""}).json()
    raw = _session_csv_bytes()
    initial = _upload(client, project["project_id"], "import-csv", raw)
    assert initial.status_code == 200, initial.text
    monkeypatch.setattr(routes, "_now", lambda: dt.datetime(2026, 9, 6, tzinfo=dt.timezone.utc))
    refused = _upload(client, project["project_id"], "import-csv", raw, session_metadata=_session_metadata_bytes())
    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "CSV_SESSION_METADATA_RETRY_MISMATCH"
    retry = _upload(client, project["project_id"], "import-csv", raw)
    assert retry.content == initial.content


def test_session_metadata_upload_reader_has_individual_limit():
    import asyncio
    import io
    from fastapi import HTTPException, UploadFile
    from app.api.research_dataset_routes import _read_session_metadata, MAX_SESSION_BYTES
    assert asyncio.run(_read_session_metadata(None)) is None
    with pytest.raises(HTTPException) as error:
        asyncio.run(_read_session_metadata(UploadFile(file=io.BytesIO(b"x" * (MAX_SESSION_BYTES + 1)))))
    assert error.value.status_code == 413
    assert error.value.detail["code"] == "CSV_SESSION_METADATA_SIZE_INVALID"


# Reuse the browser-owner/data-vault fixture and fake wire from its existing home.
from tests.test_v0_data_connection_onboarding import direct_client


def _provider_history_api_setup(direct_client, monkeypatch, *, empty=(), grant=True):
    from tests.test_v0_data_connection_onboarding import (
        _history_fetch_setup, _HistoryFetchRuntime, _install_history_fetch_runtime, _initiate)
    from research.data import provider_history_fetch
    client, _ = direct_client
    request, reference, _, _, _ = _history_fetch_setup(client, monkeypatch, grant=grant)
    state = _initiate(client)
    completed = client.get('/api/v1/data-connections/oauth/callback',
        params={'state':state, 'request_token':'synthetic-request-token'}, follow_redirects=False)
    assert completed.status_code == 303
    captured = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=2)
    monkeypatch.setattr(provider_history_fetch, '_now', lambda: captured + dt.timedelta(seconds=1))
    runtime = _HistoryFetchRuntime(reference, captured, empty=empty)
    _install_history_fetch_runtime(monkeypatch, runtime)
    body = {'selection_address':request['selection_address'], 'start_date':request['from_date'],
        'end_date':request['to_date'], 'interval':'day'}
    return client, request['project_id'], body, runtime


@pytest.mark.parametrize('empty', [(), (0,)])
def test_provider_history_api_fetch_publish_reopen_and_revoke(direct_client, monkeypatch, empty):
    from app.db.models import AuthorityRawSegment
    from research.data.provider_history_bundle import DEFINITION_SCHEMA
    from tests.test_v0_data_connection_onboarding import OWNER
    from research.data.canonical_dataset import load_canonical_datasets
    client, project_id, body, runtime = _provider_history_api_setup(direct_client, monkeypatch, empty=empty)
    response = client.post(f'/api/v1/ir/projects/{project_id}/research-datasets/from-provider', json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['schema'] == 'strategy-os-provider-history-import/1'
    assert result['reused'] is False
    assert result['selection_address'] == result['item']['provider_selection_address'] == body['selection_address']
    assert result['request_count'] == 2 and result['empty_request_count'] == len(empty)
    assert result['request_window_days'] == 1900 and result['application_bar_limit'] == 2000
    assert result['provider_retention'] == 'UNKNOWN'
    assert result['item']['bar_count'] == 2-len(empty)
    assert result['item']['research_compatibility'] == 'PRIMARY_BACKTEST'
    assert result['item']['market_truth_state'] == 'RECONSTRUCTED_WITH_GAPS'
    assert result['item']['calendar_coverage'] == 'NOT_ASSERTED'
    assert 'app-key-a' not in response.text and 'app-secret-a' not in response.text
    assert client.delete('/api/v1/data-connections').status_code == 200
    reopened = client.get(f'/api/v1/ir/projects/{project_id}/research-datasets')
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()['items'] == [result['item']]
    reused = client.post(f'/api/v1/ir/projects/{project_id}/research-datasets/from-provider', json=body)
    assert reused.status_code == 200, reused.text
    assert reused.json() == {**result, 'reused':True}
    assert len(runtime.calls) == 2  # Reopening does not reconnect or fetch again.
    engine = make_engine(research_database_url())
    try:
        with SessionLocal() as es, make_sessionmaker(engine)() as rs:
            retained, = [row for row in es.query(AuthorityRawSegment).all()
                if json.loads(row.canonical_json)['fact']['raw_schema'] == DEFINITION_SCHEMA]
            assert json.loads(retained.raw_bytes)['document']['instrument_address'] == result['item']['instrument_address']
            cutoff = dt.datetime.fromisoformat(result['item']['as_of'])
            _, data = load_canonical_datasets(rs, execution_session=es, owner_id=OWNER,
                selections=[SimpleNamespace(manifest_address=result['item']['manifest_address'], as_of=cutoff)], now=cutoff)[0]
            assert data.bar_count == 2-len(empty)
            assert [row.close for row in data.candles] == [101]*(2-len(empty))
    finally:
        engine.dispose()


def test_provider_history_api_refuses_ungranted_and_private_projects_before_fetch(direct_client, monkeypatch):
    from app.api.principal import get_principal
    from app.main import app
    from tests.test_v0_data_connection_onboarding import _seed_identity, _principal
    client, project_id, body, runtime = _provider_history_api_setup(direct_client, monkeypatch, grant=False)
    missing_grant = client.post(f'/api/v1/ir/projects/{project_id}/research-datasets/from-provider', json=body)
    assert missing_grant.status_code == 409
    assert missing_grant.json()['detail']['code'] == 'HISTORICAL_FETCH_GRANT_UNAVAILABLE'
    assert runtime.calls == []
    _seed_identity('history-other-owner', 'history-other-user', 'history-other-session', with_account=False)
    app.dependency_overrides[get_principal] = lambda: _principal('history-other-owner', 'history-other-user', 'history-other-session')
    foreign = client.post(f'/api/v1/ir/projects/{project_id}/research-datasets/from-provider', json=body)
    missing = client.post('/api/v1/ir/projects/not-present/research-datasets/from-provider', json=body)
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()
    assert runtime.calls == []


@pytest.mark.parametrize('patch', [
    {'owner_id':'foreign'}, {'interval':'15minute'}, {'start_date':'2026-W01-1'},
    {'start_date':'2026-02-30'}, {'selection_address':'sha256:'+'X'*64},
    {'end_date':'2018-01-01'},
])
def test_provider_history_api_has_closed_date_identity_and_interval_inputs(direct_client, monkeypatch, patch):
    client, project_id, body, runtime = _provider_history_api_setup(direct_client, monkeypatch)
    response = client.post(f'/api/v1/ir/projects/{project_id}/research-datasets/from-provider', json={**body, **patch})
    assert response.status_code == 422
    assert runtime.calls == []


def test_provider_history_api_rechecks_browser_session_before_publication(direct_client, monkeypatch):
    from app.db.models import UserSession, AuthorityRawSegment
    from research.data import provider_history_fetch
    from tests.test_v0_data_connection_onboarding import SESSION
    client, project_id, body, _ = _provider_history_api_setup(direct_client, monkeypatch)
    original = provider_history_fetch.fetch_provider_history
    def withdraw(*args, **kwargs):
        result = original(*args, **kwargs)
        with SessionLocal.begin() as session:
            session.get(UserSession, SESSION).revoked_at = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        return result
    monkeypatch.setattr(provider_history_fetch, 'fetch_provider_history', withdraw)
    response = client.post(f'/api/v1/ir/projects/{project_id}/research-datasets/from-provider', json=body)
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'HISTORICAL_FETCH_ACCESS_CHANGED'
    with SessionLocal() as session:
        assert session.query(AuthorityRawSegment).count() == 0


def test_provider_history_api_recovers_from_second_plane_commit_failure(direct_client, monkeypatch):
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.exc import SQLAlchemyError
    from app.api import research_dataset_routes as routes
    from app.db.models import AuthorityRawSegment
    from research.domain.models import ResearchDatasetManifestV2
    client, project_id, body, runtime = _provider_history_api_setup(direct_client, monkeypatch)
    failures = []
    class ResearchCommitFailsOnce(Session):
        def commit(self):
            if not failures:
                failures.append(True)
                raise SQLAlchemyError('synthetic-internal-storage-detail')
            return super().commit()
    monkeypatch.setattr(routes, 'make_sessionmaker', lambda engine: sessionmaker(bind=engine, class_=ResearchCommitFailsOnce))
    failed = client.post(f'/api/v1/ir/projects/{project_id}/research-datasets/from-provider', json=body)
    assert failed.status_code == 503, failed.text
    assert failed.json()['detail']['code'] == 'HISTORICAL_DATASET_SAVE_FAILED'
    assert 'synthetic-internal-storage-detail' not in failed.text
    engine = make_engine(research_database_url())
    try:
        with SessionLocal() as es, make_sessionmaker(engine)() as rs:
            retained = es.query(AuthorityRawSegment).count()
            assert retained > 0
            assert rs.query(ResearchDatasetManifestV2).count() == 0
        recovered = _resume_history_in_new_process(project_id, body)
        assert recovered['status'] == 200 and recovered['reused'] is True, recovered
        assert len(runtime.calls) == 2
        with SessionLocal() as es, make_sessionmaker(engine)() as rs:
            assert es.query(AuthorityRawSegment).count() == retained
            assert rs.query(ResearchDatasetManifestV2).count() == 1
    finally:
        engine.dispose()


def _resume_history_in_new_process(project_id, body):
    import os
    import subprocess
    import sys
    import textwrap
    from pathlib import Path
    from sqlalchemy.engine import make_url
    execution = SessionLocal.kw['bind'].url
    research = make_url(research_database_url())
    assert execution.get_backend_name() == research.get_backend_name() == 'sqlite'
    directory = Path(execution.database).parent
    assert directory == Path(research.database).parent and directory.name.startswith('paper-trader-pytest-')
    # Use only this fixture's verified temporary paths and explicit dummy flags;
    # conftest module names can be shadowed when both test trees are collected.
    environment = {'PATH':os.defpath, 'PT_DISABLE_DOTENV':'1', 'PT_PROVIDER':'mock',
        'PT_EXECUTION':'paper', 'PT_LIVE_ACK':'', 'PT_DATABASE_URL':'', 'PT_PRODUCTION':'0',
        'PT_DB_PATH':execution.database, 'PT_RESEARCH_DATABASE_URL':'', 'PT_RESEARCH_DB_PATH':research.database,
        'PT_LEDGER_DB_PATH':str(directory/'ledger.db'), 'PT_BACKTEST_DATASET_DIR':str(directory/'backtest_datasets'),
        'PT_EVENT_CURSOR_SECRET':'synthetic-provider-history-restart-secret',
        'PT_RELEASE_PROFILE':'v0_research_signal', 'PT_RELEASE_SERVICE_ROLE':'api',
        'PT_RESEARCH_ENABLED':'1'}
    script = textwrap.dedent('''
        import json, sys
        import pytest  # Also disables dotenv in the existing Settings contract.
        from fastapi.testclient import TestClient
        from app.api.principal import Principal, get_principal
        from app.main import app
        from research.data import provider_history_fetch
        request = json.load(sys.stdin)
        app.dependency_overrides[get_principal] = lambda: Principal(
            id='provider-user-a', kind='user', scopes=frozenset({'*'}), user_id='provider-user-a',
            organization_id='provider-owner-a', role='owner', session_id='provider-session-a')
        def forbidden(*args, **kwargs):
            raise AssertionError('a resumed publication must not fetch from the provider')
        provider_history_fetch.fetch_provider_history = forbidden
        response = TestClient(app).post(
            '/api/v1/ir/projects/'+request['project_id']+'/research-datasets/from-provider', json=request['body'])
        document = response.json()
        print(json.dumps({'status':response.status_code, 'reused':document.get('reused'),
            'manifest_address':document.get('item',{}).get('manifest_address')}))
    ''')
    child = subprocess.run([sys.executable, '-c', script],
        input=json.dumps({'project_id':project_id, 'body':body}), text=True,
        # A measured cold API import spends about 62 seconds validating the
        # implementation registry. This bounds the whole process, not a request.
        capture_output=True, env=environment, timeout=180)
    assert child.returncode == 0, child.stderr
    return json.loads(child.stdout.strip().splitlines()[-1])


def test_history_publication_lookup_requires_aware_whole_request_times():
    from research.data.provider_history_publication import _request
    start = dt.datetime(2026, 1, 1, tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30)))
    end = start + dt.timedelta(days=1, seconds=-1)
    assert _request('selection', start, end)['start'] == '2025-12-31T18:30:00+00:00'
    for invalid in (start.replace(tzinfo=None), start.replace(microsecond=1), '2026-01-01'):
        with pytest.raises(ValueError):
            _request('selection', invalid, end)


def _assert_history_publication_lookup(engine):
    from sqlalchemy import MetaData, Table, Column, String, Text, LargeBinary, select
    from sqlalchemy.orm import Session
    from app.ir.hashing import canonical_json
    from app.market_data.observations import RawObservationSegment
    from research.data.provider_history_publication import _candidate_addresses, _payload_text, SCHEMA
    from app.db.models import AuthorityRawSegment
    table = Table('authority_raw_segments', MetaData(),
        Column('address', String, primary_key=True), Column('owner_id', String),
        Column('schema', String), Column('canonical_json', Text), Column('raw_bytes', LargeBinary))
    table.metadata.create_all(engine)
    request = {'selection_address':'sha256:'+'1'*64, 'start':'2025-01-01T00:00:00+00:00', 'end':'2025-02-01T00:00:00+00:00'}
    payload = canonical_json({'request':request, 'source_label':'café_日本'}).encode()
    def raw_row(owner, schema, body):
        raw = RawObservationSegment(owner, 'sha256:'+'3'*64, 'sha256:'+'4'*64,
            'application/json', schema, body, dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc))
        return {'address':raw.address, 'owner_id':owner, 'schema':raw.SCHEMA,
            'canonical_json':raw.canonical_bytes.decode(), 'raw_bytes':raw.payload}
    rows = [raw_row('owner-a', SCHEMA, payload), raw_row('owner-b', SCHEMA, payload),
        raw_row('owner-a', SCHEMA, canonical_json({'request':{**request, 'end':'2025-03-01T00:00:00+00:00'}}).encode()),
        raw_row('owner-a', 'binary-market-input/1', b'\x00\xff')]
    with engine.begin() as connection:
        connection.execute(table.insert(), rows)
    with Session(engine) as session:
        # Project every row without a WHERE filter: correctness cannot depend
        # on the optimizer filtering unrelated binary bytes before UTF-8 decoding.
        projected = dict(session.execute(select(AuthorityRawSegment.address,
            _payload_text(session, AuthorityRawSegment.address != rows[-1]['address']))).all())
        assert projected[rows[-1]['address']] == ''
        assert projected[rows[0]['address']] == payload.decode()
        assert _candidate_addresses(session, 'owner-a', request) == [rows[0]['address']]
        assert _candidate_addresses(session, 'absent-owner', request) == []
        assert _candidate_addresses(session, 'owner-a', {**request, 'selection_address':'sha256:'+'2'*64}) == []


def test_history_publication_lookup_sqlite_utf8_and_owner_filter():
    from sqlalchemy import create_engine
    engine = create_engine('sqlite://')
    try:
        _assert_history_publication_lookup(engine)
    finally:
        engine.dispose()


def test_history_publication_lookup_postgresql_utf8_and_owner_filter(pg_sandbox):
    _assert_history_publication_lookup(pg_sandbox.engine('execution'))


def _saved_history_publication(direct_client, monkeypatch):
    from app.db.models import AuthorityRawSegment
    from app.market_data.observations import load_raw_segment
    from research.data.provider_history_publication import SCHEMA
    client, project_id, body, runtime = _provider_history_api_setup(direct_client, monkeypatch)
    response = client.post(f'/api/v1/ir/projects/{project_id}/research-datasets/from-provider', json=body)
    assert response.status_code == 200, response.text
    with SessionLocal() as session:
        row, = [row for row in session.query(AuthorityRawSegment).all()
            if json.loads(row.canonical_json)['fact']['raw_schema'] == SCHEMA]
        snapshot = load_raw_segment(session, row.address)
    return client, project_id, body, runtime, snapshot


@pytest.mark.parametrize('change', ['owner', 'request', 'manifest_owner', 'recorded', 'media', 'noncanonical'])
def test_history_publication_refuses_relabelled_or_changed_output(direct_client, monkeypatch, change):
    from dataclasses import replace
    from copy import deepcopy
    from app.ir.hashing import canonical_json
    from research.data.provider_history_publication import _publication_document
    _, _, _, _, original = _saved_history_publication(direct_client, monkeypatch)
    document = json.loads(original.payload)
    request = deepcopy(document['request'])
    raw = original
    if change == 'owner':
        document['owner_id'] = 'other-owner'
    elif change == 'request':
        document['request']['end'] = '2025-02-01T00:00:00+00:00'
    elif change == 'manifest_owner':
        document['manifest']['owner_id'] = 'other-owner'
    elif change == 'recorded':
        raw = replace(raw, recorded_at=raw.recorded_at+dt.timedelta(seconds=1))
    elif change == 'media':
        raw = replace(raw, media_type='text/plain')
    payload = json.dumps(document, indent=1).encode() if change == 'noncanonical' else canonical_json(document).encode()
    raw = replace(raw, payload=payload)
    with pytest.raises(ValueError):
        _publication_document(raw, original.owner_id, request)


def test_history_publication_refuses_ambiguous_saved_outputs_without_refetch(direct_client, monkeypatch):
    from dataclasses import replace
    from app.ir.hashing import canonical_json
    from app.market_data.observations import persist_raw_segment
    from research.data.provider_history_publication import _publication_document
    from research.data.historical_capture import PURPOSE
    client, project_id, body, runtime, original = _saved_history_publication(direct_client, monkeypatch)
    document = json.loads(original.payload)
    document['project_id'] = 'another-project'
    document['manifest']['purpose'] = PURPOSE+'another-project'
    other = replace(original, payload=canonical_json(document).encode())
    _publication_document(other, original.owner_id, document['request'])
    with SessionLocal.begin() as session:
        persist_raw_segment(session, other)
    refused = client.post(f'/api/v1/ir/projects/{project_id}/research-datasets/from-provider', json=body)
    assert refused.status_code == 422
    assert refused.json()['detail']['code'] == 'HISTORICAL_PUBLICATION_AMBIGUOUS'
    assert len(runtime.calls) == 2


def test_history_publication_refuses_duplicate_or_missing_index_parts(direct_client, monkeypatch):
    from copy import deepcopy
    from research.data.provider_history_publication import _publication_document, _publication_segments
    _, _, _, _, original = _saved_history_publication(direct_client, monkeypatch)
    document = json.loads(original.payload)
    _, manifest = _publication_document(original, original.owner_id, document['request'])
    with SessionLocal() as session:
        for parts in ([], [document['segments'][0], document['segments'][0]]):
            altered = {**deepcopy(document), 'segments':parts}
            with pytest.raises(ValueError):
                _publication_segments(session, altered, manifest)
