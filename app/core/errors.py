import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.errors import ErrorDetail, ErrorOut, FieldErrorOut

logger = logging.getLogger(__name__)


class AppError(Exception):
    """
    الإيرور الوحيد اللي بنرفعه في التطبيق
    """

    def __init__(self, code: str, message_ar: str, status: int = 400) -> None:
        super().__init__(message_ar)
        self.code = code
        self.message_ar = message_ar
        self.status = status


def error_response(
    request: Request,
    status: int,
    code: str,
    message: str,
    details: list[FieldErrorOut] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    # كل الإيرورز بتطلع من هنا، فشكل الرد واحد دايماً
    body = ErrorOut(
        error=ErrorDetail(
            code=code,
            message=message,
            request_id=getattr(request.state, "request_id", "-"),
            details=details,
        )
    )
    return JSONResponse(
        status_code=status, content=body.model_dump(exclude_none=True), headers=headers
    )


# بيحوّل أي خطأ من أخطاء التطبيق لرد بنفس الشكل دايماً
# AppError -> JSONResponse
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return error_response(request, exc.status, exc.code, exc.message_ar)


# البيانات اللي في الطلب مش مظبوطة، زي سؤال أقصر من 3 حروف
# RequestValidationError -> 422
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        FieldErrorOut(field=".".join(str(part) for part in err["loc"]), message=err["msg"])
        for err in exc.errors()
    ]
    return error_response(
        request, 422, "validation_error", "البيانات اللي بعتها فيها مشكلة، شوف التفاصيل", details
    )


_HTTP_ERRORS = {
    404: ("not_found", "المسار ده مش موجود"),
    405: ("method_not_allowed", "الطريقة دي مش مسموحة على المسار ده"),
}


# أخطاء بيرميها الإطار نفسه، زي مسار مش موجود
# HTTPException -> 404, 405
async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code, message = _HTTP_ERRORS.get(exc.status_code, ("http_error", str(exc.detail)))
    # بنحافظ على الهيدرز اللي جاية مع الإيرور، زي الطرق المسموحة في 405
    # Allow
    return error_response(request, exc.status_code, code, message, headers=exc.headers)


# أي خطأ محدش توقعه: العميل بياخد رسالة عامة ورقم الطلب بس
# والتفاصيل كلها بتتكتب في السجل، عشان منكشفش حاجة من جوه السيستم
# Exception -> 500
# ملحوظة: لو وضع التصحيح شغال، الإطار بيعرض صفحة الخطأ بتاعته بدل المعالج ده
# DEBUG=true
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # بيكتب الخطأ كله مع مكانه في الكود
    # logger.exception -> traceback
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    # المعالج ده بيشتغل برا الوسيط، فلازم نحط رقم الطلب في الهيدر بنفسنا
    # outside request_context_middleware
    request_id = getattr(request.state, "request_id", "-")
    return error_response(
        request,
        500,
        "internal_error",
        "حصل خطأ عندنا، جرّب تاني بعد شوية، ولو اتكرر ابعت رقم الطلب للدعم",
        headers={"X-Request-Id": request_id},
    )
