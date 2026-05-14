from __future__ import annotations

import json
import sqlite3

from motionjson.backend.api import MotionJSONAPI
from motionjson.backend.api_keys import create_api_key
from motionjson.backend.auth import create_session, register_user
from motionjson.backend.billing import get_billing_status, list_plan_catalog
from motionjson.backend.db import initialize_database
from motionjson.cli import main


def backend(tmp_path):
    conn = sqlite3.connect(tmp_path / "backend.sqlite")
    conn.row_factory = sqlite3.Row
    initialize_database(conn)
    user = register_user(conn, email="billing@example.com", password="pw")
    return conn, user


def assert_billing_payload(payload):
    raw = json.dumps(payload)
    assert payload["billingProvider"] == "local_catalog"
    assert payload["paymentCollection"] == "not_configured"
    assert payload["checkout"] == "out_of_scope"
    assert payload["aiUsage"] == "none"
    assert "stripe" not in raw.lower()
    assert "checkout.session" not in raw.lower()
    assert "tax" not in raw.lower()
    assert "invoice" not in raw.lower()
    assert "secret" not in raw.lower()
    assert "api_key" not in raw.lower()


def test_local_plan_catalog_and_entitlement_status_do_not_require_paid_provider(monkeypatch):
    monkeypatch.setenv("MOTIONJSON_DEFAULT_PLAN", "studio")

    catalog = list_plan_catalog()
    status = get_billing_status(user_id="user_1")

    assert [plan["id"] for plan in catalog["plans"]] == ["starter", "studio", "production"]
    assert status["plan"]["id"] == "studio"
    assert status["subscription"]["state"] == "catalog_only"
    assert status["entitlements"]["monthlyExtractFrames"] == 18000
    assert_billing_payload(catalog)
    assert_billing_payload(status)


def test_rest_api_exposes_billing_plans_and_status(tmp_path, monkeypatch):
    monkeypatch.delenv("MOTIONJSON_DEFAULT_PLAN", raising=False)
    conn, user = backend(tmp_path)
    key = create_api_key(conn, user_id=user["id"], name="billing")["apiKey"]
    conn.close()
    api = MotionJSONAPI(db_path=tmp_path / "backend.sqlite", storage_root=tmp_path / "storage")
    headers = {"authorization": f"Bearer {key}"}

    status, _headers, body = api.handle("GET", "/v1/billing/plans", headers, b"")
    assert status == 200
    catalog = json.loads(body)
    assert catalog["plans"][0]["id"] == "starter"
    assert_billing_payload(catalog)

    status, _headers, body = api.handle("GET", "/v1/billing/status", headers, b"")
    assert status == 200
    billing_status = json.loads(body)
    assert billing_status["userId"] == user["id"]
    assert billing_status["plan"]["id"] == "starter"
    assert_billing_payload(billing_status)


def test_cli_exposes_billing_catalog_and_session_status(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "backend.sqlite"
    storage_root = tmp_path / "storage"
    conn, user = backend(tmp_path)
    session = create_session(conn, user_id=user["id"])
    conn.close()
    common = ["--db", str(db_path), "--storage-root", str(storage_root)]

    main(["backend", "list-plans", *common])
    catalog = json.loads(capsys.readouterr().out)
    assert catalog["plans"][1]["id"] == "studio"
    assert_billing_payload(catalog)

    monkeypatch.setenv("MJ_TEST_TOKEN", session.token)
    main(["backend", "billing-status", *common, "--session-token-env", "MJ_TEST_TOKEN"])
    status = json.loads(capsys.readouterr().out)
    assert status["userId"] == user["id"]
    assert status["entitlements"]["assetStorageGb"] == 5
    assert_billing_payload(status)
