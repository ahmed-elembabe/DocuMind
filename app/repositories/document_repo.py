from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from app.models.document import Document, DocumentStatus


class DocumentRepo:
    """
    تخزين مؤقت في الذاكرة لحد ما نوصل للداتابيز

    الواجهة معمولة كأنها داتابيز، فلما ننقل هنغيّر الملف ده بس
    Postgres
    """

    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}

    def add(self, org_id: str, filename: str, size_bytes: int) -> Document:
        # الريبو هو اللي بيولّد المعرّف ووقت الإنشاء، زي ما الداتابيز بتعمل وقت الإضافة
        # INSERT ... RETURNING
        doc = Document(
            id=uuid4().hex,
            org_id=org_id,
            filename=filename,
            size_bytes=size_bytes,
            status="processing",
            created_at=datetime.now(UTC),
        )
        self._docs[doc.id] = doc
        return doc

    def get(self, org_id: str, doc_id: str) -> Document | None:
        doc = self._docs.get(doc_id)
        # العزل من هنا، مستند شركة تانية بيرجع فاضي كأنه مش موجود
        return doc if doc and doc.org_id == org_id else None

    def update_status(
        self, org_id: str, doc_id: str, status: DocumentStatus, error: str | None = None
    ) -> Document | None:
        doc = self.get(org_id, doc_id)
        if doc is None:
            return None
        # المستند مقفول ومش بيتعدّل، فبنحط نسخة جديدة مكانه
        # UPDATE ... RETURNING
        updated = replace(doc, status=status, error=error)
        self._docs[doc_id] = updated
        return updated

    def delete(self, org_id: str, doc_id: str) -> bool:
        if self.get(org_id, doc_id) is None:
            return False
        del self._docs[doc_id]
        return True

    def list(
        self,
        org_id: str,
        status: DocumentStatus | None = None,
        limit: int = 20,
        after: str | None = None,
    ) -> list[Document]:
        docs = [
            d
            for d in self._docs.values()
            if d.org_id == org_id and (status is None or d.status == status)
        ]
        # ترتيب ثابت بالوقت وبعدين بالمعرّف، عشان لو وقتين اتساووا
        docs.sort(key=lambda d: (d.created_at, d.id))

        # تقسيم النتايج لصفحات بالمؤشر، وهو معرّف آخر مستند في الصفحة اللي فاتت
        # cursor pagination: after = last id
        if after is not None:
            cursor = self.get(org_id, after)
            if cursor is None:
                # المؤشر مش موجود أو بتاع شركة تانية، فمنرجّعش حاجة
                return []
            cursor_key = (cursor.created_at, cursor.id)
            docs = [d for d in docs if (d.created_at, d.id) > cursor_key]

        return docs[:limit]
