from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class AskIn(BaseModel):
    # بنشيل المسافات الأول، عشان سؤال كله مسافات ميعدّيش شرط الـ 3 حروف
    # strip_whitespace=True
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)
    ]


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    filename: str
    chunk_index: int
    text: str
    score: int


class UsageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    input_tokens: int
    output_tokens: int


class AskOut(BaseModel):
    answer: str
    sources: list[SourceOut]
    usage: UsageOut | None
