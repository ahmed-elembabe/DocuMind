import pytest
from fastapi.testclient import TestClient

from app.core.config import OrgConfig, Settings, get_settings
from app.core.deps import (
    get_answerer,
    get_chunk_repo,
    get_document_repo,
    get_file_repo,
    get_usage_repo,
)
from app.main import app
from app.repositories.chunk_repo import ChunkRepo
from app.repositories.document_repo import DocumentRepo
from app.repositories.file_repo import FileRepo
from app.repositories.usage_repo import UsageRepo
from app.services.answerer import Answer, Answerer, Source, Usage

ACME = {"X-API-Key": "test-acme-key"}
GLOBEX = {"X-API-Key": "test-globex-key"}


@pytest.fixture
def client():
    docs, files, chunks, usage = DocumentRepo(), FileRepo(), ChunkRepo(), UsageRepo()
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
    app.dependency_overrides[get_usage_repo] = lambda: usage
    yield TestClient(app)
    app.dependency_overrides.clear()


def upload(client, text: str, filename="notes.txt", headers=ACME):
    files = {"file": (filename, text.encode())}
    return client.post("/api/v1/documents", files=files, headers=headers).json()


def ask(client, question, headers=ACME):
    return client.post("/api/v1/ask", json={"question": question}, headers=headers)


def test_answer_has_answer_sources_and_empty_usage(client):
    doc = upload(client, "مقدمة\n\nمدة عقد الإيجار سنة واحدة", filename="عقد.txt")

    response = ask(client, "ما هي مدة عقد الإيجار؟")

    assert response.status_code == 200
    assert response.json() == {
        "answer": "مدة عقد الإيجار سنة واحدة",
        "sources": [
            {
                "document_id": doc["id"],
                "filename": "عقد.txt",
                "chunk_index": 1,
                "text": "مدة عقد الإيجار سنة واحدة",
                "score": 3,
            }
        ],
        "usage": None,
    }


def test_no_match_returns_no_answer_message(client):
    upload(client, "كلام مالوش علاقة")

    body = ask(client, "سؤال تاني خالص").json()

    assert body == {"answer": "ملقتش إجابة في ملفاتك", "sources": [], "usage": None}


def test_does_not_answer_from_other_org_files(client):
    upload(client, "سر شركة جلوبكس", headers=GLOBEX)

    assert ask(client, "سر شركة جلوبكس", headers=ACME).json()["sources"] == []


@pytest.mark.parametrize("question", ["أب", "   أب   ", "x" * 501])
def test_question_length_is_validated(client, question):
    assert ask(client, question).status_code == 422


def test_question_at_limits_is_accepted(client):
    assert ask(client, "أبت").status_code == 200
    assert ask(client, "x" * 500).status_code == 200


class FakeAnswerer(Answerer):
    async def answer(self, org_id: str, question: str) -> Answer:
        source = Source(document_id="d1", filename="f.md", chunk_index=0, text="t", score=1)
        return Answer(text=f"{org_id}: {question}", sources=[source], usage=Usage(10, 5))


def test_router_works_with_any_answerer(client):
    # ده اللي هيحصل في صفحة 6، نبدّل طريقة الإجابة والراوتر زي ما هو
    app.dependency_overrides[get_answerer] = lambda: FakeAnswerer()

    body = ask(client, "أي سؤال").json()

    assert body["answer"] == "org-acme: أي سؤال"
    assert body["usage"] == {"input_tokens": 10, "output_tokens": 5}
