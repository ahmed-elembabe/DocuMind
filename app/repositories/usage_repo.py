from datetime import date


class UsageRepo:
    """
    عدد أسئلة كل شركة في كل يوم، مؤقتاً في الذاكرة
    كل يوم لشركة زي صف في جدول
    (org_id, day) -> count
    """

    def __init__(self) -> None:
        self._counts: dict[tuple[str, date], int] = {}

    def get_count(self, org_id: str, day: date) -> int:
        return self._counts.get((org_id, day), 0)

    def increment(self, org_id: str, day: date) -> int:
        # في الداتابيز هتبقى عملية واحدة عشان طلبين في نفس اللحظة ميعدّوش نفس الرقم
        # INSERT ... ON CONFLICT DO UPDATE SET count = count + 1
        count = self.get_count(org_id, day) + 1
        self._counts[(org_id, day)] = count
        return count
