import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.core.body_limit import MULTIPART_OVERHEAD, BodySizeLimitMiddleware
from app.core.config import OrgConfig, Settings, get_settings
from app.core.deps import get_document_repo, get_file_repo
from app.main import app
from app.repositories.document_repo import DocumentRepo
from app.repositories.file_repo import FileRepo

ACME = {"X-API-Key": "test-acme-key"}
MB = 1024 * 1024
LIMIT = 2 * MB + MULTIPART_OVERHEAD


@pytest.fixture
def client():
    docs, files = DocumentRepo(), FileRepo()
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        orgs=[OrgConfig(id="org-acme", name="Acme", api_key="test-acme-key")],
    )
    app.dependency_overrides[get_document_repo] = lambda: docs
    app.dependency_overrides[get_file_repo] = lambda: files
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_too_large_body_is_rejected_before_parsing(client):
    # الوسيط بيرفض على طول من غير ما الملف يتفك أصلاً
    # فمحتوى الطلب مش مهم، المهم حجمه
    response = client.post(
        "/api/v1/documents",
        content=b"a" * (LIMIT + 1),
        headers=ACME | {"Content-Type": "multipart/form-data; boundary=x"},
    )

    assert response.status_code == 413
    error = response.json()["error"]
    assert error["code"] == "file_too_large"
    assert error["message"] == "أقصى حجم للملف 2 ميجا"
    assert error["request_id"] == response.headers["X-Request-Id"]
    assert client.get("/api/v1/documents", headers=ACME).json()["items"] == []


def run_middleware(chunks: int, chunk_size: int, app_to_wrap) -> tuple[int, list[dict]]:
    """
    بيشغّل الوسيط على طلب متقسم حتت ومن غير حجم معروف
    وبيرجّع اتقرا كام حتة والرسايل اللي اتبعتت للعميل
    Transfer-Encoding: chunked
    """
    pulled = 0
    sent: list[dict] = []

    async def receive() -> dict:
        nonlocal pulled
        pulled += 1
        return {"type": "http.request", "body": b"a" * chunk_size, "more_body": pulled < chunks}

    async def send(message: dict) -> None:
        sent.append(message)

    scope = {"type": "http", "method": "POST", "path": "/", "headers": [], "query_string": b""}
    middleware = BodySizeLimitMiddleware(app_to_wrap, max_upload_bytes=2 * MB)
    asyncio.run(middleware(scope, receive, send))
    return pulled, sent


async def reads_whole_body(scope, receive, send):
    # زي اللي بيفك الملف بالظبط، بيقرا لحد آخر حتة
    while (await receive()).get("more_body"):
        pass
    await send({"type": "http.response.start", "status": 202, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def status_of(sent: list[dict]) -> int:
    return next(m["status"] for m in sent if m["type"] == "http.response.start")


def test_stops_reading_a_chunked_body_right_after_the_limit():
    # ملف 100 ميجا بيوصل حتت كل حتة ميجا
    pulled, sent = run_middleware(chunks=100, chunk_size=MB, app_to_wrap=reads_whole_body)

    # بعد 3 حتت الحجم عدّى الحد فالقراية وقفت ومتقراش الباقي
    assert pulled == 3
    assert status_of(sent) == 413
    body = json.loads(b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body"))
    assert body["error"]["code"] == "file_too_large"


def test_chunked_body_under_the_limit_passes_through():
    pulled, sent = run_middleware(chunks=2, chunk_size=MB, app_to_wrap=reads_whole_body)

    assert pulled == 2
    assert status_of(sent) == 202


async def turns_errors_into_400(scope, receive, send):
    # الإطار بيحوّل أي خطأ وهو بيقرا الملف لرد 400
    try:
        while (await receive()).get("more_body"):
            pass
    except Exception:
        await send({"type": "http.response.start", "status": 400, "headers": []})
        await send({"type": "http.response.body", "body": b"bad request"})


def test_app_response_after_the_limit_is_replaced_with_413():
    _, sent = run_middleware(chunks=100, chunk_size=MB, app_to_wrap=turns_errors_into_400)

    # رد 400 اترمى والعميل خد 413 بس
    statuses = [m["status"] for m in sent if m["type"] == "http.response.start"]
    assert statuses == [413]
