from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import OrgConfig, Settings, get_settings
from app.core.deps import get_chunk_repo, get_document_repo, get_file_repo, get_usage_repo
from app.core.errors import AppError
from app.main import app
from app.repositories.chunk_repo import ChunkRepo
from app.repositories.document_repo import DocumentRepo
from app.repositories.file_repo import FileRepo
from app.repositories.usage_repo import UsageRepo
from app.services.quota_service import QuotaService

ACME = {"X-API-Key": "test-acme-key"}
GLOBEX = {"X-API-Key": "test-globex-key"}
LIMIT = 3


class FakeClock:
    # تاريخ بنحركه بإيدنا عشان نجرّب اليوم اللي بعده
    def __init__(self) -> None:
        self.day = date(2026, 1, 1)

    def __call__(self) -> date:
        return self.day


def test_default_daily_quota_is_20():
    assert Settings(_env_file=None).daily_question_quota == 20


def test_usage_repo_counts_per_org_and_day():
    repo = UsageRepo()
    day = date(2026, 1, 1)

    assert repo.increment("org-a", day) == 1
    assert repo.increment("org-a", day) == 2

    assert repo.get_count("org-a", day) == 2
    assert repo.get_count("org-b", day) == 0
    assert repo.get_count("org-a", day + timedelta(days=1)) == 0


def test_service_raises_429_after_limit():
    service = QuotaService(UsageRepo(), daily_limit=2, today=FakeClock())
    service.consume_question("org-a")
    service.consume_question("org-a")

    with pytest.raises(AppError) as exc_info:
        service.consume_question("org-a")

    assert exc_info.value.status == 429
    assert exc_info.value.code == "quota_exceeded"


def test_service_quota_resets_next_day():
    clock = FakeClock()
    service = QuotaService(UsageRepo(), daily_limit=1, today=clock)
    service.consume_question("org-a")

    clock.day += timedelta(days=1)

    # مفيش إيرور، يعني اتعدّ من الأول
    service.consume_question("org-a")


def test_rejected_question_is_not_counted():
    usage = UsageRepo()
    clock = FakeClock()
    service = QuotaService(usage, daily_limit=1, today=clock)
    service.consume_question("org-a")

    for _ in range(3):
        with pytest.raises(AppError):
            service.consume_question("org-a")

    assert usage.get_count("org-a", clock.day) == 1


@pytest.fixture
def client():
    docs, files, chunks, usage = DocumentRepo(), FileRepo(), ChunkRepo(), UsageRepo()
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        daily_question_quota=LIMIT,
        orgs=[
            OrgConfig(id="org-acme", name="Acme", api_key="test-acme-key"),
            OrgConfig(id="org-globex", name="Globex", api_key="test-globex-key"),
        ],
    )
    app.dependency_overrides[get_document_repo] = lambda: docs
    app.dependency_overrides[get_file_repo] = lambda: files
    app.dependency_overrides[get_chunk_repo] = lambda: chunks
    app.dependency_overrides[get_usage_repo] = lambda: usage
    yield TestClient(app)
    app.dependency_overrides.clear()


def ask(client, question="أي سؤال", headers=ACME):
    return client.post("/api/v1/ask", json={"question": question}, headers=headers)


def test_ask_returns_429_with_arabic_message_after_limit(client):
    for _ in range(LIMIT):
        assert ask(client).status_code == 200

    response = ask(client)

    assert response.status_code == 429
    error = response.json()["error"]
    assert error["code"] == "quota_exceeded"
    assert error["message"] == f"خلصت حد الأسئلة النهارده ({LIMIT} سؤال)، جرّب تاني بكره"
    assert error["request_id"] == response.headers["X-Request-Id"]


def test_quota_is_per_org(client):
    for _ in range(LIMIT):
        ask(client, headers=ACME)

    assert ask(client, headers=ACME).status_code == 429
    assert ask(client, headers=GLOBEX).status_code == 200


def test_invalid_question_does_not_use_quota(client):
    for _ in range(LIMIT + 2):
        assert ask(client, question="أب").status_code == 422

    assert ask(client).status_code == 200
