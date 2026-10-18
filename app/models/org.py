from dataclasses import dataclass


# الشركة اللي بتوصل للمسارات، من غير المفتاح بتاعها
@dataclass(frozen=True, slots=True)
class Org:
    id: str
    name: str
