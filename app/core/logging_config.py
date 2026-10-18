import logging
from contextvars import ContextVar

# رقم الطلب الحالي، وكل طلب شغال ليه نسخته لوحده حتى لو طلبات كتير في نفس الوقت
# ContextVar
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    # بيحط رقم الطلب في كل سطر في السجل، فمش محتاجين نبعته بإيدنا في كل مكان
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def setup_logging(level: int = logging.INFO) -> None:
    # بنظبط سجل التطبيق بس، وسجل السيرفر نفسه بيفضل زي ما هو
    # "app" -> app.core.errors, app.core.middleware, ...
    logger = logging.getLogger("app")
    logger.setLevel(level)
    if logger.handlers:
        return

    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
    )
    logger.addHandler(handler)
