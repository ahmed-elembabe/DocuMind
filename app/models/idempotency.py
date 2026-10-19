from dataclasses import dataclass
from datetime import datetime


# رقم منع التكرار اللي العميل بعته، والمستند اللي اتعمل بيه
@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    org_id: str
    key: str
    document_id: str
    # بصمة الملف، عشان نعرف لو نفس الرقم جه مع ملف تاني
    # sha256(filename + content)
    fingerprint: str
    created_at: datetime
