import asyncio
import io
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from app.core.config import OrgConfig, Settings, get_settings
from app.core.deps import (
    get_chunk_repo,
    get_document_repo,
    get_file_repo,
    get_idempotency_repo,
)
from app.core.errors import AppError
from app.main import app
from app.repositories.chunk_repo import ChunkRepo
from app.repositories.document_repo import DocumentRepo
from app.repositories.file_repo import FileRepo
from app.repositories.idempotency_repo import IdempotencyRepo
from app.services.document_service import IDEMPOTENCY_TTL, DocumentService

ACME = {"X-API-Key": "test-acme-key"}
GLOBEX = {"X-API-Key": "test-globex-key"}


@pytest.fixture
def chunks() -> ChunkRepo:
    return ChunkRepo()


@pytest.fixture
def client(chunks):
    docs, files, keys = DocumentRepo(), FileRepo(), IdempotencyRepo()
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        orgs=[
            OrgConfig(id="org-acme", name="Acme", api_key="test-acme-key"),
            OrgConfig(id="org-globex", name="Globex", api_key="test-globex-key"),
        ],
    )
    app.dependency_overrides[get_document_repo] = lambda: docs
    app.dependency_overrides[get_file_repo] = lambda: files
    app.dependency_overrides[get_chunk_repo] = lambda: chunks
    app.dependency_overrides[get_idempotency_repo] = lambda: keys
    yield TestClient(app)
    app.dependency_overrides.clear()


def upload(client, content=b"a\n\nb", key=None, headers=ACME, filename="notes.txt"):
    headers = headers | ({"Idempotency-Key": key} if key else {})
    return client.post(
        "/api/v1/documents", files={"file": (filename, content)}, headers=headers
    )


def list_ids(client, headers=ACME):
    return [d["id"] for d in client.get("/api/v1/documents", headers=headers).json()["items"]]


def test_same_key_returns_same_document_without_duplicate(client, chunks):
    first = upload(client, key="k1")
    # النت قطع والعميل بعت نفس الطلب تاني
    second = upload(client, key="k1")

    assert first.status_code == second.status_code == 202
    assert second.json()["id"] == first.json()["id"]
    assert list_ids(client) == [first.json()["id"]]
    # الرد التاني بيقول إنه راجع من طلب قديم
    assert "Idempotent-Replayed" not in first.headers
    assert second.headers["Idempotent-Replayed"] == "true"
    # الطلب التاني بيرجّع الحالة الحالية، والتقسيم متعملش مرتين
    assert second.json()["status"] == "ready"
    assert len(chunks.list_by_document("org-acme", first.json()["id"])) == 2


def test_without_key_every_upload_is_new(client):
    upload(client)
    upload(client)

    assert len(list_ids(client)) == 2


def test_different_keys_make_different_documents(client):
    upload(client, key="k1")
    upload(client, key="k2")

    assert len(list_ids(client)) == 2


def test_same_key_with_different_file_returns_422(client):
    upload(client, content=b"first", key="k1")

    response = upload(client, content=b"second", key="k1")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "idempotency_key_reused"
    assert len(list_ids(client)) == 1


def test_same_key_with_different_filename_returns_422(client):
    upload(client, key="k1", filename="a.txt")

    assert upload(client, key="k1", filename="b.txt").status_code == 422


def test_same_key_in_two_orgs_makes_two_documents(client):
    acme = upload(client, key="k1", headers=ACME).json()
    globex = upload(client, key="k1", headers=GLOBEX).json()

    assert acme["id"] != globex["id"]
    assert list_ids(client, ACME) == [acme["id"]]
    assert list_ids(client, GLOBEX) == [globex["id"]]


def test_key_of_deleted_document_makes_new_document(client):
    old_id = upload(client, key="k1").json()["id"]
    client.delete(f"/api/v1/documents/{old_id}", headers=ACME)

    new = upload(client, key="k1")

    assert new.status_code == 202
    assert new.json()["id"] != old_id
    assert "Idempotent-Replayed" not in new.headers


@pytest.mark.parametrize("bad_key", ["", "k" * 256])
def test_invalid_key_returns_422(client, bad_key):
    response = client.post(
        "/api/v1/documents",
        files={"file": ("notes.txt", b"text")},
        headers=ACME | {"Idempotency-Key": bad_key},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_invalid_file_does_not_use_the_key(client):
    # الملف اترفض، فالرقم متسجلش ويقدر يتستخدم مع ملف سليم
    assert upload(client, key="k1", filename="report.pdf").status_code == 422

    assert upload(client, key="k1").status_code == 202


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def make_service(clock: FakeClock) -> DocumentService:
    return DocumentService(
        DocumentRepo(), FileRepo(), ChunkRepo(), IdempotencyRepo(), 1024, now=clock
    )


def make_file(content: bytes = b"text") -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename="notes.txt")


def test_key_expires_after_ttl():
    clock = FakeClock()
    service = make_service(clock)
    first, _ = asyncio.run(service.upload("org-a", make_file(), "k1"))

    clock.now += IDEMPOTENCY_TTL - timedelta(seconds=1)
    still_same, is_new = asyncio.run(service.upload("org-a", make_file(), "k1"))
    assert (still_same.id, is_new) == (first.id, False)

    clock.now += timedelta(seconds=2)
    after_ttl, is_new = asyncio.run(service.upload("org-a", make_file(), "k1"))
    assert after_ttl.id != first.id
    assert is_new is True


def test_expired_key_accepts_a_different_file():
    clock = FakeClock()
    service = make_service(clock)
    asyncio.run(service.upload("org-a", make_file(b"first"), "k1"))

    clock.now += IDEMPOTENCY_TTL + timedelta(seconds=1)

    # مفيش إيرور، لأن الرقم انتهى
    _, is_new = asyncio.run(service.upload("org-a", make_file(b"second"), "k1"))
    assert is_new is True


class SlowUpload:
    # ملف وهمي، القراية بتاعته مبتخلصش غير لما الطلبين الاتنين يوصلوا للقراية
    # فالطلبين بيكمّلوا مع بعض في نفس اللحظة بالظبط، مش بالصدفة
    # asyncio.Barrier
    filename = "notes.txt"

    def __init__(self, barrier: asyncio.Barrier) -> None:
        self._barrier = barrier

    async def read(self, size: int = -1) -> bytes:
        await self._barrier.wait()
        return b"text"


def test_two_uploads_with_same_key_at_the_same_time_make_one_document():
    service = make_service(FakeClock())

    async def both():
        barrier = asyncio.Barrier(2)
        return await asyncio.gather(
            service.upload("org-a", SlowUpload(barrier), "k1"),
            service.upload("org-a", SlowUpload(barrier), "k1"),
        )

    (first, first_new), (second, second_new) = asyncio.run(both())

    assert first.id == second.id
    assert sorted([first_new, second_new]) == [False, True]


def test_reused_key_error_is_app_error():
    service = make_service(FakeClock())
    asyncio.run(service.upload("org-a", make_file(b"first"), "k1"))

    with pytest.raises(AppError) as exc_info:
        asyncio.run(service.upload("org-a", make_file(b"second"), "k1"))

    assert exc_info.value.status == 422
