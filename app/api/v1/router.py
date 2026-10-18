from fastapi import APIRouter, Depends

from app.api.v1 import ask, documents, me
from app.core.deps import get_current_org
from app.schemas.errors import ErrorOut

# التحقق من المفتاح متحطوط على الراوتر كله، فأي مسار تحته محمي لوحده
# Depends(get_current_org) on every /api/v1 route
api_router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(get_current_org)],
    # بدل شكل 422 الافتراضي في التوثيق، عشان احنا بنرجّع شكل الإيرور بتاعنا
    responses={
        401: {"model": ErrorOut, "description": "الـ API key مش موجود أو غلط"},
        422: {"model": ErrorOut, "description": "البيانات اللي في الطلب مش مظبوطة"},
        500: {"model": ErrorOut, "description": "خطأ عندنا، والتفاصيل في السجل"},
    },
)

api_router.include_router(me.router)
api_router.include_router(documents.router)
api_router.include_router(ask.router)
