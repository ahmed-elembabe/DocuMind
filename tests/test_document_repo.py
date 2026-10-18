import pytest

from app.repositories.document_repo import DocumentRepo


@pytest.fixture
def repo() -> DocumentRepo:
    return DocumentRepo()


def test_add_returns_new_processing_document(repo):
    doc = repo.add("org-a", "عقد.txt", 120)

    assert doc.id
    assert doc.org_id == "org-a"
    assert doc.filename == "عقد.txt"
    assert doc.size_bytes == 120
    assert doc.status == "processing"
    assert doc.error is None


def test_get_returns_document_for_same_org(repo):
    doc = repo.add("org-a", "doc.txt", 1)

    assert repo.get("org-a", doc.id) == doc


def test_get_hides_document_from_other_org(repo):
    doc = repo.add("org-a", "doc.txt", 1)

    assert repo.get("org-b", doc.id) is None


def test_get_missing_document_returns_none(repo):
    assert repo.get("org-a", "missing") is None


def test_update_status_changes_document(repo):
    doc = repo.add("org-a", "doc.txt", 1)

    updated = repo.update_status("org-a", doc.id, "failed", error="السبب")

    assert (updated.status, updated.error) == ("failed", "السبب")
    assert repo.get("org-a", doc.id) == updated


def test_update_status_ignores_other_org(repo):
    doc = repo.add("org-a", "doc.txt", 1)

    assert repo.update_status("org-b", doc.id, "ready") is None
    assert repo.get("org-a", doc.id).status == "processing"


def test_delete_removes_document(repo):
    doc = repo.add("org-a", "doc.txt", 1)

    assert repo.delete("org-a", doc.id) is True
    assert repo.get("org-a", doc.id) is None


def test_delete_ignores_other_org(repo):
    doc = repo.add("org-a", "doc.txt", 1)

    assert repo.delete("org-b", doc.id) is False
    assert repo.get("org-a", doc.id) == doc


def test_list_returns_only_org_documents_in_creation_order(repo):
    first = repo.add("org-a", "1.txt", 1)
    repo.add("org-b", "other.txt", 1)
    second = repo.add("org-a", "2.txt", 1)

    assert repo.list("org-a") == [first, second]


def test_list_filters_by_status(repo):
    processing = repo.add("org-a", "processing.txt", 1)
    ready = repo.update_status("org-a", repo.add("org-a", "ready.txt", 1).id, "ready")

    assert repo.list("org-a", status="processing") == [processing]
    assert repo.list("org-a", status="ready") == [ready]


def test_list_paginates_with_limit_and_after(repo):
    docs = [repo.add("org-a", f"{i}.txt", 1) for i in range(5)]

    page1 = repo.list("org-a", limit=2)
    page2 = repo.list("org-a", limit=2, after=page1[-1].id)
    page3 = repo.list("org-a", limit=2, after=page2[-1].id)

    assert page1 + page2 + page3 == docs
    assert len(page3) == 1


def test_list_ignores_cursor_from_other_org(repo):
    other = repo.add("org-b", "other.txt", 1)
    repo.add("org-a", "mine.txt", 1)

    assert repo.list("org-a", after=other.id) == []
