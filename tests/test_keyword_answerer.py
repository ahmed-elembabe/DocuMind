import asyncio

import pytest

from app.repositories.chunk_repo import ChunkRepo
from app.repositories.document_repo import DocumentRepo
from app.services.answerer import NO_ANSWER
from app.services.keyword_answerer import KeywordAnswerer, to_words


@pytest.fixture
def repos():
    return DocumentRepo(), ChunkRepo()


def add_doc(repos, org_id, filename, paragraphs):
    docs, chunks = repos
    doc = docs.add(org_id, filename, 1)
    chunks.add_many(org_id, doc.id, paragraphs)
    return doc


def ask(repos, org_id, question):
    # الدالة غير متزامنة، فبنشغّلها بالطريقة دي في التست
    # asyncio.run(...)
    return asyncio.run(KeywordAnswerer(*repos).answer(org_id, question))


def test_to_words_ignores_case_and_punctuation():
    assert to_words("عقد الإيجار؟ Rent, rent!") == {"عقد", "الإيجار", "rent"}


def test_best_chunk_is_the_answer_with_filename_and_index(repos):
    doc = add_doc(repos, "org-a", "عقد.txt", ["مقدمة عامة", "مدة عقد الإيجار سنة واحدة"])

    result = ask(repos, "org-a", "ما هي مدة عقد الإيجار")

    assert result.text == "مدة عقد الإيجار سنة واحدة"
    top = result.sources[0]
    assert (top.document_id, top.filename, top.chunk_index, top.score) == (
        doc.id,
        "عقد.txt",
        1,
        3,
    )
    assert result.usage is None


def test_returns_top_3_sorted_by_score(repos):
    add_doc(
        repos,
        "org-a",
        "f.txt",
        ["a", "a b", "a b c", "a b c d", "x y z"],
    )

    result = ask(repos, "org-a", "a b c d")

    assert [s.score for s in result.sources] == [4, 3, 2]


def test_only_searches_own_org_chunks(repos):
    add_doc(repos, "org-b", "secret.txt", ["سر الشركة التانية"])

    result = ask(repos, "org-a", "سر الشركة التانية")

    assert result.text == NO_ANSWER
    assert result.sources == []


def test_no_shared_words_returns_no_answer(repos):
    add_doc(repos, "org-a", "f.txt", ["كلام مالوش علاقة"])

    assert ask(repos, "org-a", "سؤال تاني خالص").text == NO_ANSWER


def test_skips_chunks_of_deleted_document(repos):
    docs, _ = repos
    doc = add_doc(repos, "org-a", "f.txt", ["كلمة"])
    docs.delete("org-a", doc.id)

    assert ask(repos, "org-a", "كلمة").sources == []
