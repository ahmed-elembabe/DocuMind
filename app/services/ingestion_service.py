import logging
import re

from app.core.errors import AppError
from app.repositories.chunk_repo import ChunkRepo
from app.repositories.document_repo import DocumentRepo
from app.repositories.file_repo import FileRepo

logger = logging.getLogger(__name__)


def split_into_chunks(text: str) -> list[str]:
    # الفقرة بتنتهي بسطر فاضي أو سطر فيه مسافات بس
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


class IngestionService:
    def __init__(self, docs: DocumentRepo, files: FileRepo, chunks: ChunkRepo) -> None:
        self._docs = docs
        self._files = files
        self._chunks = chunks

    def process(self, org_id: str, doc_id: str) -> None:
        """
        بتشتغل في الخلفية بعد ما الرد يوصل للعميل

        مفيش حد مستني الرد بتاعها، فلازم أي خطأ يتمسك ويتسجل في المستند
        بدل ما يضيع
        """
        data = self._files.get(org_id, doc_id)
        if data is None:
            # المستند اتمسح قبل ما المعالجة تبدأ
            return

        try:
            try:
                # الترميز ده بيشيل العلامة المخفية اللي بعض البرامج بتحطها في أول الملف
                # utf-8-sig strips the BOM
                text = data.decode("utf-8-sig")
            except UnicodeDecodeError:
                raise AppError("invalid_encoding", "الملف لازم يبقى نص بترميز UTF-8", 422)

            texts = split_into_chunks(text)
            if not texts:
                raise AppError("empty_file", "الملف فاضي، مفيهوش أي نص يتقسم لفقرات", 422)

            self._chunks.add_many(org_id, doc_id, texts)
        except AppError as e:
            self._docs.update_status(org_id, doc_id, "failed", error=e.message_ar)
            return
        except Exception:
            # خطأ مش متوقع، التفاصيل في السجل والعميل ياخد رسالة عامة
            logger.exception("ingestion failed for document %s", doc_id)
            self._docs.update_status(
                org_id, doc_id, "failed", error="حصل خطأ غير متوقع أثناء معالجة الملف"
            )
            return

        if self._docs.update_status(org_id, doc_id, "ready") is None:
            # المستند اتمسح وهو بيتعالج، فمنسيبش فقرات ملهاش صاحب
            self._chunks.delete_by_document(org_id, doc_id)
