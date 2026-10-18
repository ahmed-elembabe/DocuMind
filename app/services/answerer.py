from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Source:
    document_id: str
    filename: str
    chunk_index: int
    text: str
    score: int


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class Answer:
    text: str
    sources: list[Source] = field(default_factory=list)
    # فاضي دلوقتي لأن مفيش ذكاء اصطناعي، ولما نستخدمه هيتملي بعدد التوكنز
    # None now, RagAnswerer fills it
    usage: Usage | None = None


NO_ANSWER = "ملقتش إجابة في ملفاتك"


class Answerer(ABC):
    """
    أي طريقة بتجاوب على سؤال من ملفات الشركة

    الراوتر بيتعامل مع الواجهة دي بس، فلما نبدّل البحث بالكلمات بالذكاء الاصطناعي
    مش هنغيّر غير دالة واحدة في ملف الاعتماديات
    get_answerer() in app/core/deps.py
    """

    # الدالة غير متزامنة من دلوقتي، لأن الذكاء الاصطناعي هيستنى رد من النت
    # ولو غيرناها بعدين، الراوتر هيتغير
    # async def answer(...)
    @abstractmethod
    async def answer(self, org_id: str, question: str) -> Answer: ...
