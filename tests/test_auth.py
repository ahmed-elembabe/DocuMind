import re

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import OrgConfig, Settings, get_settings
from app.main import app

ACME_KEY = "test-acme-key"
GLOBEX_KEY = "test-globex-key"


@pytest.fixture
def client():
    # شركتين ثابتين للتستات بدل اللي في ملف الإعدادات
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        orgs=[
            OrgConfig(id="org-acme", name="Acme", api_key=ACME_KEY),
            OrgConfig(id="org-globex", name="Globex", api_key=GLOBEX_KEY),
        ],
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_missing_api_key_returns_401(client):
    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_api_key"


def test_wrong_api_key_returns_401(client):
    response = client.get("/api/v1/me", headers={"X-API-Key": "wrong"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


def test_each_key_identifies_its_own_org(client):
    acme = client.get("/api/v1/me", headers={"X-API-Key": ACME_KEY})
    globex = client.get("/api/v1/me", headers={"X-API-Key": GLOBEX_KEY})

    assert acme.json() == {"id": "org-acme", "name": "Acme"}
    assert globex.json() == {"id": "org-globex", "name": "Globex"}


def test_health_works_without_api_key(client):
    assert client.get("/health").status_code == 200


def test_every_endpoint_except_health_requires_api_key(client):
    # بناخد كل المسارات من التوثيق التلقائي، فأي مسار جديد هيتختبر لوحده
    # app.openapi()['paths']
    endpoints = [
        (method, path)
        for path, methods in app.openapi()["paths"].items()
        if path != "/health"
        for method in methods
    ]
    assert endpoints, "لازم يبقى فيه endpoints نتأكد منها"

    unprotected = []
    for method, path in endpoints:
        # أي جزء متغير في المسار بنحط مكانه قيمة وهمية
        # {doc_id} -> x
        url = re.sub(r"\{[^}]+\}", "x", path)
        if client.request(method, url).status_code != 401:
            unprotected.append(f"{method.upper()} {path}")

    assert unprotected == []


def test_orgs_are_read_from_env_as_json(monkeypatch):
    monkeypatch.setenv("ORGS", '[{"id": "org-x", "name": "X", "api_key": "k"}]')

    settings = Settings(_env_file=None)

    assert settings.orgs[0].id == "org-x"
    assert settings.orgs[0].api_key.get_secret_value() == "k"
    # المفتاح مستخبي لو اتطبع
    assert "k" not in repr(settings.orgs[0].api_key)


def test_duplicate_api_keys_are_rejected():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            orgs=[
                OrgConfig(id="a", name="A", api_key="same"),
                OrgConfig(id="b", name="B", api_key="same"),
            ],
        )
