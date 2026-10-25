from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response

# مسافة زيادة فوق حجم الملف عشان حدود الطلب المتقسم وهيدرز كل جزء فيه
# multipart boundaries + part headers
MULTIPART_OVERHEAD = 64 * 1024


class BodyTooLarge(Exception):
    """
    بتوقف قراية الطلب أول ما حجمه يعدّي الحد
    ودي مش إيرور بيوصل للعميل، الوسيط بيمسكها ويرجّع الرد بنفسه
    """


class BodySizeLimitMiddleware:
    """
    بيرفض أي طلب أكبر من الحد قبل ما السيرفر يستقبله كله

    من غيره الإطار كان بيستقبل الملف كله ويكتبه على الهارد الأول
    وبعدين السيرفس يرفضه، فملف 2 جيجا كان هيتسحب كله على الفاضي

    الوسيط ده بيشتغل برا معالجات الإيرورز، فمينفعش يرمي إيرور التطبيق
    وبيبني الرد بنفس الشكل الموحّد بنفسه
    AppError -> error_response()
    """

    def __init__(self, app: ASGIApp, max_upload_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_upload_bytes + MULTIPART_OVERHEAD
        max_mb = max_upload_bytes / (1024 * 1024)
        self.message = f"أقصى حجم للملف {max_mb:g} ميجا"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # لو العميل قال حجم الطلب من الأول نرفضه من غير ما نقرا ولا بايت
        # Content-Length
        content_length = Headers(scope=scope).get("content-length", "")
        if content_length.isdigit() and int(content_length) > self.max_body_bytes:
            await self._reject(scope, receive, send)
            return

        # لو مقالش الحجم بنعدّ البايتات وهي داخلة حتة حتة
        # Transfer-Encoding: chunked
        received = 0
        too_large = False

        async def limited_receive() -> Message:
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_bytes:
                    too_large = True
                    raise BodyTooLarge()
            return message

        async def guarded_send(message: Message) -> None:
            # الإطار ممكن يحوّل التوقف لرد تاني زي 400، فبنرميه ونبعت ردنا احنا
            if not too_large:
                await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except BodyTooLarge:
            pass

        if too_large:
            await self._reject(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = error_response(Request(scope), 413, "file_too_large", self.message)
        await response(scope, receive, send)
