import logging
import re
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response

from app.core.logging_config import request_id_var

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-Id"

# بنقبل رقم الطلب اللي جاي من برا بس لو شكله سليم
# عشان محدش يبعت سطر جديد أو كلام طويل يبوّظ بيه السجل
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


async def request_context_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    incoming = request.headers.get(REQUEST_ID_HEADER, "")
    request_id = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else uuid4().hex

    # في مكانين: الأول لمعالج الإيرورز، والتاني لأي سطر في السجل
    # request.state -> handlers, ContextVar -> logs
    request.state.request_id = request_id
    request_id_var.set(request_id)

    start = time.perf_counter()
    # لو حصل خطأ مش متوقع، مش هيرجع رد لحد هنا، فالحالة هتفضل 500
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %s in %.1fms", request.method, request.url.path, status_code, duration_ms
        )
