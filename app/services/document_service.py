import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import UploadFile

from app.core.errors import AppError
from app.models.document import Document, DocumentStatus
from app.repositories.chunk_repo import ChunkRepo
from app.repositories.document_repo import DocumentRepo
from app.repositories.file_repo import FileRepo
from app.repositories.idempotency_repo import IdempotencyRepo

ALLOWED_EXTENSIONS = {".txt", ".md"}

# رقم منع التكرار بيفضل شغال يوم، وبعد كده نفس الرقم بيعمل مستند جديد
IDEMPOTENCY_TTL = timedelta(hours=24)


def utc_now() -> datetime:
    return datetime.now(UTC)


def file_fingerprint(filename: str, data: bytes) -> str:
    # بصمة للاسم والمحتوى مع بعض، ولو حرف واحد اتغير البصمة بتتغير
    # sha256
    return hashlib.sha256(filename.encode() + b"\0" + data).hexdigest()


class DocumentService:
    def __init__(
        self,
        docs: DocumentRepo,
        files: FileRepo,
        chunks: ChunkRepo,
        idempotency: IdempotencyRepo,
        max_upload_bytes: int,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self._docs = docs
        self._files = files
        self._chunks = chunks
        self._idempotency = idempotency
        self._max_upload_bytes = max_upload_bytes
        # الوقت بيتبعت من برا عشان التستات تقدر تعدّي يوم
        self._now = now

    async def upload(
        self, org_id: str, file: UploadFile, idempotency_key: str | None = None
    ) -> tuple[Document, bool]:
        """
        بترجّع المستند، ومعاه هل هو جديد ولا راجع من طلب قديم بنفس الرقم
        (doc, is_new)
        """
        # بناخد اسم الملف بس ونشيل أي مسار جواه، عشان محدش يبعت اسم يطلع برا الفولدر
        # Path(...).name: ../../etc/passwd -> passwd
        filename = Path(file.filename or "").name
        if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise AppError("unsupported_file_type", "مسموح بملفات .txt و .md بس", 422)

        # بنقرا بايت واحد زيادة عن الحد، ولو اتقرا يبقى الملف أكبر من المسموح
        # ومن غير ما نحمّل ملف ضخم كله في الذاكرة
        data = await file.read(self._max_upload_bytes + 1)
        if len(data) > self._max_upload_bytes:
            max_mb = self._max_upload_bytes / (1024 * 1024)
            raise AppError("file_too_large", f"أقصى حجم للملف {max_mb:g} ميجا", 413)

        # من هنا لحد آخر الدالة مفيش انتظار، فطلبين بنفس الرقم في نفس اللحظة
        # مش هيدخلوا في بعض، والتاني هيلاقي رقم الأول متسجل
        # no await below
        fingerprint = file_fingerprint(filename, data)
        if idempotency_key is not None:
            previous = self._find_previous_upload(org_id, idempotency_key, fingerprint)
            if previous is not None:
                return previous, False

        doc = self._docs.add(org_id, filename, len(data))
        self._files.save(org_id, doc.id, data)
        if idempotency_key is not None:
            self._idempotency.save(org_id, idempotency_key, doc.id, fingerprint, self._now())
        return doc, True

    def _find_previous_upload(self, org_id: str, key: str, fingerprint: str) -> Document | None:
        record = self._idempotency.get(org_id, key)
        if record is None or self._now() - record.created_at > IDEMPOTENCY_TTL:
            return None
        if record.fingerprint != fingerprint:
            # نفس الرقم مع ملف تاني يبقى غلط من العميل
            # فمنرجّعش المستند القديم كأن مفيش حاجة حصلت
            raise AppError(
                "idempotency_key_reused", "الرقم ده اتستخدم قبل كده مع ملف تاني", 422
            )
        # لو المستند اتمسح، بنعتبر الرقم مش مستخدم ونعمل مستند جديد
        return self._docs.get(org_id, record.document_id)

    def get(self, org_id: str, doc_id: str) -> Document:
        doc = self._docs.get(org_id, doc_id)
        if doc is None:
            # نفس الرد سواء المستند مش موجود أو بتاع شركة تانية
            # عشان محدش يعرف إن المعرّف ده موجود عند حد تاني
            raise AppError("document_not_found", "المستند ده مش موجود", 404)
        return doc

    def list(
        self, org_id: str, status: DocumentStatus | None, limit: int, after: str | None
    ) -> tuple[list[Document], str | None]:
        # بنطلب واحد زيادة، ولو جه يبقى فيه صفحة بعد دي
        # limit + 1
        docs = self._docs.list(org_id, status=status, limit=limit + 1, after=after)
        items = docs[:limit]
        next_cursor = items[-1].id if len(docs) > limit else None
        return items, next_cursor

    def delete(self, org_id: str, doc_id: str) -> None:
        # بيرمي 404 لو المستند مش موجود
        self.get(org_id, doc_id)
        self._docs.delete(org_id, doc_id)
        self._files.delete(org_id, doc_id)
        self._chunks.delete_by_document(org_id, doc_id)
