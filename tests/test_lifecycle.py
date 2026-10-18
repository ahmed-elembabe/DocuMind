import pytest
from fastapi.testclient import TestClient

from app.core.config import OrgConfig, Settings, get_settings
from app.core.deps import get_chunk_repo, get_document_repo, get_file_repo, get_usage_repo
from app.main import app
from app.repositories.chunk_repo import ChunkRepo
from app.repositories.document_repo import DocumentRepo
from app.repositories.file_repo import FileRepo
from app.repositories.usage_repo import UsageRepo
from app.services.answerer import NO_ANSWER

ACME = {"X-API-Key": "test-acme-key"}
QUESTION = "ما هي مدة عقد الإيجار؟"


@pytest.fixture
def client():
    docs, files, chunks, usage = DocumentRepo(), FileRepo(), ChunkRepo(), UsageRepo()
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        orgs=[OrgConfig(id="org-acme", name="Acme", api_key="test-acme-key")],
    )
    app.dependency_overrides[get_document_repo] = lambda: docs
    app.dependency_overrides[get_file_repo] = lambda: files
    app.dependency_overrides[get_chunk_repo] = lambda: chunks
    app.dependency_overrides[get_usage_repo] = lambda: usage
    yield TestClient(app)
    app.dependency_overrides.clear()


def ask(client):
    return client.post("/api/v1/ask", json={"question": QUESTION}, headers=ACME).json()


def test_full_document_lifecycle(client):
    # بنمشي زي العميل الحقيقي بالظبط، من الواجهة بس ومن غير ما نلمس الريبوهات
    # upload -> ready -> list -> ask -> delete -> gone

    # 1. الرفع: الرد بيرجع قبل التقسيم
    files = {"file": ("عقد.txt", "مقدمة\n\nمدة عقد الإيجار سنة واحدة".encode())}
    uploaded = client.post("/api/v1/documents", files=files, headers=ACME)
    assert uploaded.status_code == 202
    assert uploaded.json()["status"] == "processing"
    doc_id = uploaded.json()["id"]

    # 2. التقسيم خلص
    assert client.get(f"/api/v1/documents/{doc_id}", headers=ACME).json()["status"] == "ready"

    # 3. بيظهر في القايمة
    listed = client.get("/api/v1/documents", headers=ACME).json()
    assert [d["id"] for d in listed["items"]] == [doc_id]

    # 4. السؤال بيلاقي الإجابة في الملف
    answer = ask(client)
    assert answer["answer"] == "مدة عقد الإيجار سنة واحدة"
    assert answer["sources"][0]["document_id"] == doc_id

    # 5. المسح
    assert client.delete(f"/api/v1/documents/{doc_id}", headers=ACME).status_code == 204

    # 6. الملف اختفى من كل حتة، حتى من الإجابات
    assert client.get(f"/api/v1/documents/{doc_id}", headers=ACME).status_code == 404
    assert client.get("/api/v1/documents", headers=ACME).json()["items"] == []
    assert ask(client) == {"answer": NO_ANSWER, "sources": [], "usage": None}
