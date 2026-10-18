from collections.abc import Callable
from datetime import UTC, date, datetime

from app.core.errors import AppError
from app.repositories.usage_repo import UsageRepo


def utc_today() -> date:
    return datetime.now(UTC).date()


class QuotaService:
    """
    حد الأسئلة اليومي لكل شركة، واليوم بيبدأ الساعة 12 بالليل بتوقيت جرينتش
    UTC
    """

    def __init__(
        self, usage: UsageRepo, daily_limit: int, today: Callable[[], date] = utc_today
    ) -> None:
        self._usage = usage
        self._daily_limit = daily_limit
        # التاريخ بيتبعت من برا عشان التستات تقدر تنقل لليوم اللي بعده
        self._today = today

    def consume_question(self, org_id: str) -> None:
        # بنعدّ السؤال قبل الإجابة مش بعدها، فطلبات كتير في نفس الوقت متعدّيش الحد
        # ولما نستخدم الذكاء الاصطناعي ده هيمنع إننا ندفع تمن أسئلة زيادة
        day = self._today()
        if self._usage.get_count(org_id, day) >= self._daily_limit:
            raise AppError(
                "quota_exceeded",
                f"خلصت حد الأسئلة النهارده ({self._daily_limit} سؤال)، جرّب تاني بكره",
                429,
            )
        self._usage.increment(org_id, day)
