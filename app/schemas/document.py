from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus


class DocumentOut(BaseModel):
    # يقدر يتعمل من كلاس المستند مباشرة
    # from_attributes=True
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    size_bytes: int
    status: DocumentStatus
    error: str | None
    created_at: datetime


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    # ابعته في الطلب الجاي عشان تجيب الصفحة اللي بعدها، ولو فاضي يبقى خلصت
    # ?after=next_cursor  (None = last page)
    next_cursor: str | None
