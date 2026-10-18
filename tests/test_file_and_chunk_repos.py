from app.repositories.chunk_repo import ChunkRepo
from app.repositories.file_repo import FileRepo


def test_file_repo_saves_and_deletes():
    files = FileRepo()
    files.save("org-a", "doc-1", b"hello")

    assert files.get("org-a", "doc-1") == b"hello"
    files.delete("org-a", "doc-1")
    assert files.get("org-a", "doc-1") is None


def test_file_repo_hides_other_org_file():
    files = FileRepo()
    files.save("org-a", "doc-1", b"secret")

    assert files.get("org-b", "doc-1") is None
    files.delete("org-b", "doc-1")
    assert files.get("org-a", "doc-1") == b"secret"


def test_chunk_repo_keeps_order_per_document():
    chunks = ChunkRepo()
    chunks.add_many("org-a", "doc-1", ["أول", "تاني"])
    chunks.add_many("org-a", "doc-2", ["مستند تاني"])

    result = chunks.list_by_document("org-a", "doc-1")

    assert [(c.index, c.text) for c in result] == [(0, "أول"), (1, "تاني")]


def test_chunk_repo_hides_and_protects_other_org_chunks():
    chunks = ChunkRepo()
    chunks.add_many("org-a", "doc-1", ["سر"])

    assert chunks.list_by_document("org-b", "doc-1") == []
    chunks.delete_by_document("org-b", "doc-1")
    assert len(chunks.list_by_document("org-a", "doc-1")) == 1


def test_chunk_repo_deletes_document_chunks():
    chunks = ChunkRepo()
    chunks.add_many("org-a", "doc-1", ["a", "b"])
    chunks.add_many("org-a", "doc-2", ["c"])

    chunks.delete_by_document("org-a", "doc-1")

    assert chunks.list_by_document("org-a", "doc-1") == []
    assert len(chunks.list_by_document("org-a", "doc-2")) == 1
