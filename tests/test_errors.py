import logging

import pytest
from fastapi.testclient import TestClient

from app.core.config import OrgConfig, Settings, get_settings
from app.core.deps import get_answerer, get_usage_repo
from app.core.logging_config import RequestIdFilter
from app.main import app
from app.repositories.usage_repo import UsageRepo
from app.services.answerer import Answer, Answerer

ACME = {"X-API-Key": "test-acme-key"}
SECRET = "db password is hunter2"


class BrokenAnswerer(Answerer):
    # خطأ عن قصد، زي ما يحصل لو الداتابيز وقعت
    async def answer(self, org_id: str, question: str) -> Answer:
        raise RuntimeError(SECRET)


@pytest.fixture
def client():
    usage = UsageRepo()
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        orgs=[OrgConfig(id="org-acme", name="Acme", api_key="test-acme-key")],
    )
    app.dependency_overrides[get_usage_repo] = lambda: usage
    # عميل التست بيرمي أي خطأ في التست نفسه، فبنقفل ده عشان نشوف الرد 500 زي العميل الحقيقي
    # raise_server_exceptions=False
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def logs(caplog):
    # الفلتر بيتحط على مكان السجل في التطبيق، فبنحطه هنا كمان عشان نشوف رقم الطلب
    caplog.handler.addFilter(RequestIdFilter())
    caplog.set_level(logging.INFO, logger="app")
    return caplog


def test_unexpected_error_returns_generic_500(client, logs):
    app.dependency_overrides[get_answerer] = lambda: BrokenAnswerer()

    response = client.post("/api/v1/ask", json={"question": "أي سؤال"}, headers=ACME)

    assert response.status_code == 500
    request_id = response.headers["X-Request-Id"]
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "حصل خطأ عندنا، جرّب تاني بعد شوية، ولو اتكرر ابعت رقم الطلب للدعم",
            "request_id": request_id,
        }
    }
    # التفاصيل مش بتوصل للعميل
    assert SECRET not in response.text
    assert "RuntimeError" not in response.text

    # بس موجودة كلها في السجل، ومعاها رقم الطلب
    [record] = [r for r in logs.records if r.levelno == logging.ERROR]
    assert record.request_id == request_id
    assert record.exc_info[0] is RuntimeError
    assert SECRET in logs.text


def test_every_response_has_a_request_id(client):
    first = client.get("/health").headers["X-Request-Id"]
    second = client.get("/health").headers["X-Request-Id"]

    assert first and second and first != second


def test_incoming_request_id_is_kept(client):
    response = client.get("/health", headers={"X-Request-Id": "from-proxy-123"})

    assert response.headers["X-Request-Id"] == "from-proxy-123"


@pytest.mark.parametrize("bad_id", ["a" * 65, "has space", "bad!id"])
def test_invalid_incoming_request_id_is_replaced(client, bad_id):
    response = client.get("/health", headers={"X-Request-Id": bad_id})

    assert response.headers["X-Request-Id"] != bad_id


def test_each_request_is_logged_with_status_and_duration(client, logs):
    response = client.get("/health")

    [record] = [r for r in logs.records if r.name == "app.core.middleware"]
    assert record.request_id == response.headers["X-Request-Id"]
    assert record.getMessage().startswith("GET /health -> 200 in ")
    assert record.getMessage().endswith("ms")


def test_validation_error_has_same_shape_with_details(client):
    response = client.post("/api/v1/ask", json={"question": "أب"}, headers=ACME)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["request_id"] == response.headers["X-Request-Id"]
    assert [d["field"] for d in error["details"]] == ["body.question"]


def test_unknown_route_has_same_shape(client):
    response = client.get("/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert response.json()["error"]["message"] == "المسار ده مش موجود"


def test_wrong_method_keeps_allow_header(client):
    response = client.delete("/health")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
    assert response.headers["Allow"] == "GET"


def test_app_error_includes_request_id(client):
    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["error"]["request_id"] == response.headers["X-Request-Id"]
