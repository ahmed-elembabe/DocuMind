from pathlib import Path

from fastapi import UploadFile

from app.core.errors import AppError
from app.models.document import Document, DocumentStatus
from app.repositories.chunk_repo import ChunkRepo
from app.repositories.document_repo import DocumentRepo
from app.repositories.file_repo import FileRepo

ALLOWED_EXTENSIONS = {".txt", ".md"}


class DocumentService:
    def __init__(
        self, docs: DocumentRepo, files: FileRepo, chunks: ChunkRepo, max_upload_bytes: int
    ) -> None:
        self._docs = docs
        self._files = files
        self._chunks = chunks
        self._max_upload_bytes = max_upload_bytes

    async def upload(self, org_id: str, file: UploadFile) -> Document:
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

        doc = self._docs.add(org_id, filename, len(data))
        self._files.save(org_id, doc.id, data)
        return doc

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
