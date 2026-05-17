from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from backend.api import create_app


def _basic_auth(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _api_config(mock_config, tmp_path):
    config = dict(mock_config)
    config["system"] = dict(mock_config["system"])
    config["system"]["db_path"] = str(tmp_path / "api_auth.sqlite3")
    return config


def test_basic_auth_disabled_by_default(monkeypatch, mock_config, tmp_path) -> None:
    monkeypatch.delenv("APP_USERNAME", raising=False)
    monkeypatch.delenv("APP_PASSWORD", raising=False)

    client = TestClient(create_app(_api_config(mock_config, tmp_path)))

    assert client.get("/api/status").status_code == 200


def test_basic_auth_protects_app_when_configured(monkeypatch, mock_config, tmp_path) -> None:
    monkeypatch.setenv("APP_USERNAME", "me")
    monkeypatch.setenv("APP_PASSWORD", "secret")
    client = TestClient(create_app(_api_config(mock_config, tmp_path)))

    denied = client.get("/api/status")
    assert denied.status_code == 401
    assert denied.headers["www-authenticate"] == 'Basic realm="Stock Trading System"'

    wrong = client.get("/api/status", headers={"Authorization": _basic_auth("me", "bad")})
    assert wrong.status_code == 401

    allowed = client.get("/api/status", headers={"Authorization": _basic_auth("me", "secret")})
    assert allowed.status_code == 200


def test_initial_positions_json_bootstraps_positions(monkeypatch, mock_config, tmp_path) -> None:
    monkeypatch.delenv("APP_USERNAME", raising=False)
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.setenv(
        "INITIAL_POSITIONS_JSON",
        """[
          {
            "symbol": "688820.SH",
            "name": "盛合晶微",
            "entry_price": 163.955,
            "entry_date": "2026-05-17",
            "quantity": 200,
            "notes": "secret bootstrap"
          }
        ]""",
    )
    with TestClient(create_app(_api_config(mock_config, tmp_path))) as client:
        response = client.get("/api/positions")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["symbol"] == "688820.SH"
    assert payload[0]["name"] == "盛合晶微"
