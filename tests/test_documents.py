import pytest
from fastapi.testclient import TestClient

from app.core.config import OrgConfig, Settings, get_settings
from app.core.deps import get_chunk_repo, get_document_repo, get_file_repo
from app.main import app
from app.repositories.chunk_repo import ChunkRepo
from app.repositories.document_repo import DocumentRepo
from app.repositories.file_repo import FileRepo

ACME = {"X-API-Key": "test-acme-key"}
GLOBEX = {"X-API-Key": "test-globex-key"}
MAX_BYTES = 2 * 1024 * 1024


@pytest.fixture
def chunks() -> ChunkRepo:
    return ChunkRepo()


@pytest.fixture
def client(chunks):
    # ريبوهات جديدة لكل تست عشان التستات متأثرش في بعض
    docs, files = DocumentRepo(), FileRepo()
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
    yield TestClient(app)
    app.dependency_overrides.clear()


def upload(client, content: bytes, filename="notes.txt", headers=ACME):
    return client.post("/api/v1/documents", files={"file": (filename, content)}, headers=headers)


def test_upload_returns_202_processing_then_becomes_ready(client, chunks):
    response = upload(client, "الفقرة الأولى\n\nالفقرة التانية".encode())

    # الرد بيرجع قبل المعالجة، فالحالة لسه شغالة
    # status == processing
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "processing"
    assert body["filename"] == "notes.txt"

    # عميل التست بيشغّل المهمة اللي في الخلفية بعد الرد، فدلوقتي خلصت
    # TestClient runs background tasks after the response
    doc = client.get(f"/api/v1/documents/{body['id']}", headers=ACME).json()
    assert doc["status"] == "ready"
    assert doc["error"] is None
    texts = [c.text for c in chunks.list_by_document("org-acme", body["id"])]
    assert texts == ["الفقرة الأولى", "الفقرة التانية"]


def test_upload_markdown_is_accepted(client):
    assert upload(client, b"# Title", filename="README.MD").status_code == 202


def test_upload_wrong_type_returns_422(client):
    response = upload(client, b"%PDF", filename="report.pdf")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_upload_exactly_max_size_is_accepted(client):
    assert upload(client, b"a" * MAX_BYTES).status_code == 202


def test_upload_over_max_size_returns_413(client):
    response = upload(client, b"a" * (MAX_BYTES + 1))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_empty_file_fails_with_clear_reason(client):
    doc_id = upload(client, b"").json()["id"]

    doc = client.get(f"/api/v1/documents/{doc_id}", headers=ACME).json()
    assert doc["status"] == "failed"
    assert doc["error"] == "الملف فاضي، مفيهوش أي نص يتقسم لفقرات"


def test_other_org_document_returns_404(client):
    doc_id = upload(client, b"acme secret").json()["id"]

    response = client.get(f"/api/v1/documents/{doc_id}", headers=GLOBEX)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


def test_missing_document_returns_404(client):
    assert client.get("/api/v1/documents/nope", headers=ACME).status_code == 404


def test_list_shows_only_own_documents_filtered_by_status(client):
    ready_id = upload(client, b"text").json()["id"]
    # الملف ده هيفشل
    upload(client, b"").json()
    upload(client, b"globex", headers=GLOBEX)

    all_docs = client.get("/api/v1/documents", headers=ACME).json()
    ready = client.get("/api/v1/documents?status=ready", headers=ACME).json()

    assert len(all_docs["items"]) == 2
    assert [d["id"] for d in ready["items"]] == [ready_id]


def test_list_paginates_with_cursor(client):
    ids = [upload(client, f"doc {i}".encode()).json()["id"] for i in range(5)]

    seen, after = [], None
    while True:
        params = {"limit": 2} | ({"after": after} if after else {})
        page = client.get("/api/v1/documents", params=params, headers=ACME).json()
        seen += [d["id"] for d in page["items"]]
        after = page["next_cursor"]
        if after is None:
            break

    assert seen == ids


def test_list_rejects_invalid_limit(client):
    assert client.get("/api/v1/documents?limit=0", headers=ACME).status_code == 422
    assert client.get("/api/v1/documents?limit=101", headers=ACME).status_code == 422


def test_delete_returns_204_and_removes_everything(client, chunks):
    doc_id = upload(client, b"a\n\nb").json()["id"]

    response = client.delete(f"/api/v1/documents/{doc_id}", headers=ACME)

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/api/v1/documents/{doc_id}", headers=ACME).status_code == 404
    assert chunks.list_by_document("org-acme", doc_id) == []


def test_delete_other_org_document_returns_404_and_keeps_it(client):
    doc_id = upload(client, b"acme").json()["id"]

    assert client.delete(f"/api/v1/documents/{doc_id}", headers=GLOBEX).status_code == 404
    assert client.get(f"/api/v1/documents/{doc_id}", headers=ACME).status_code == 200
