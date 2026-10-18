from dataclasses import dataclass
from datetime import datetime
from typing import Literal

# اترفع والمعالجة شغالة، أو اتقسم لفقرات، أو المعالجة فشلت
# processing | ready | failed
DocumentStatus = Literal["processing", "ready", "failed"]


# المستند مقفول، محدش يقدر يعدّله من برا الريبو
# والتعديل بيبقى دالة في الريبو زي ما بيحصل في الداتابيز
# frozen=True
@dataclass(frozen=True, slots=True)
class Document:
    id: str
    org_id: str
    filename: str
    size_bytes: int
    status: DocumentStatus
    created_at: datetime
    # سبب الفشل لو المعالجة فشلت
    error: str | None = None
