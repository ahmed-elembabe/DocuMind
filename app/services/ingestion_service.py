import asyncio
import logging
import re

from app.core.errors import AppError
from app.repositories.chunk_repo import ChunkRepo
from app.repositories.document_repo import DocumentRepo
from app.repositories.file_repo import FileRepo
from app.services.text_extraction import extract_text

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

    async def process(self, org_id: str, doc_id: str) -> None:
        """
        بتشتغل في الخلفية بعد ما الرد يوصل للعميل

        مفيش حد مستني الرد بتاعها، فلازم أي خطأ يتمسك ويتسجل في المستند
        بدل ما يضيع
        """
        doc = self._docs.get(org_id, doc_id)
        data = self._files.get(org_id, doc_id)
        if doc is None or data is None:
            # المستند اتمسح قبل ما المعالجة تبدأ
            return

        try:
            # قراية الملف شغل تقيل على المعالج ومفيهوش أي انتظار
            # فلو اشتغل هنا السيرفر كله هيقف لحد ما يخلص
            # فبنبعته لثريد تاني والسيرفر يكمّل يرد على باقي الطلبات
            # asyncio.to_thread -> the event loop stays free
            text = await asyncio.to_thread(extract_text, doc.filename, data)

            texts = split_into_chunks(text)
            if not texts:
                raise AppError("empty_file", "الملف فاضي، مفيهوش أي نص يتقسم لفقرات", 422)

            # المهمة ممكن تشتغل مرتين لو اللي بيشغّلها مات في النص بعد ما حفظ الفقرات
            # فبنمسح أي فقرات قديمة الأول، عشان التشغيل التاني يدّي نفس النتيجة من غير تكرار
            # idempotent: delete old chunks -> add new chunks
            self._chunks.delete_by_document(org_id, doc_id)
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
