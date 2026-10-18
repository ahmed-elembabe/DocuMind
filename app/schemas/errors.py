from pydantic import BaseModel


class FieldErrorOut(BaseModel):
    # مكان الغلط في الطلب
    # body.question
    field: str
    message: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    # ابعته للدعم الفني، وبيه نلاقي الطلب ده في السجل
    request_id: str
    # بيظهر في أخطاء البيانات بس
    # 422
    details: list[FieldErrorOut] | None = None


# شكل أي إيرور راجع من الواجهة، عشان يظهر في صفحة التوثيق
class ErrorOut(BaseModel):
    error: ErrorDetail
