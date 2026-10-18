import re

from app.repositories.chunk_repo import ChunkRepo
from app.repositories.document_repo import DocumentRepo
from app.services.answerer import NO_ANSWER, Answer, Answerer, Source

TOP_K = 3


def to_words(text: str) -> set[str]:
    # بيمسك الحروف العربي والإنجليزي والأرقام، وبيشيل علامات الترقيم
    # \w+
    return set(re.findall(r"\w+", text.lower()))


class KeywordAnswerer(Answerer):
    """
    بحث بالكلمات مكان الذكاء الاصطناعي مؤقتاً
    الفقرة اللي فيها كلمات مشتركة أكتر مع السؤال تكسب
    """

    def __init__(self, docs: DocumentRepo, chunks: ChunkRepo) -> None:
        self._docs = docs
        self._chunks = chunks

    async def answer(self, org_id: str, question: str) -> Answer:
        question_words = to_words(question)

        scored = []
        # بنجيب فقرات الشركة دي بس، فمستحيل نجاوب من ملفات شركة تانية
        # list_by_org(org_id)
        for chunk in self._chunks.list_by_org(org_id):
            score = len(question_words & to_words(chunk.text))
            if score > 0:
                scored.append((score, chunk))

        # الأعلى في عدد الكلمات المشتركة الأول، ولو اتساووا بترتيب الملف والفقرة عشان النتيجة تبقى ثابتة
        scored.sort(key=lambda pair: (-pair[0], pair[1].document_id, pair[1].index))

        sources = []
        for score, chunk in scored[:TOP_K]:
            doc = self._docs.get(org_id, chunk.document_id)
            if doc is None:
                # المستند اتمسح
                continue
            sources.append(
                Source(
                    document_id=doc.id,
                    filename=doc.filename,
                    chunk_index=chunk.index,
                    text=chunk.text,
                    score=score,
                )
            )

        if not sources:
            return Answer(text=NO_ANSWER)
        # مفيش ذكاء اصطناعي يكتب إجابة، فأحسن فقرة هي الإجابة
        return Answer(text=sources[0].text, sources=sources)
