from datetime import datetime

from app.models.idempotency import IdempotencyRecord


class IdempotencyRepo:
    """
    أرقام منع التكرار اللي اتستخدمت في الرفع، مؤقتاً في الذاكرة

    الرقم محفوظ لكل شركة لوحدها، فلو شركتين بعتوا نفس الرقم كل واحدة ليها مستندها
    (org_id, key) -> record

    في الداتابيز هيبقى عليه قيد إنه ميتكررش، ومهمة بتمسح الأرقام القديمة كل شوية
    UNIQUE (org_id, key)
    """

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], IdempotencyRecord] = {}

    def get(self, org_id: str, key: str) -> IdempotencyRecord | None:
        return self._records.get((org_id, key))

    def save(
        self, org_id: str, key: str, document_id: str, fingerprint: str, created_at: datetime
    ) -> IdempotencyRecord:
        record = IdempotencyRecord(
            org_id=org_id,
            key=key,
            document_id=document_id,
            fingerprint=fingerprint,
            created_at=created_at,
        )
        self._records[(org_id, key)] = record
        return record
