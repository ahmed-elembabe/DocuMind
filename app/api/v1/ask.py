from fastapi import APIRouter

from app.core.deps import AnswererDep, CurrentOrgDep, QuotaServiceDep
from app.schemas.ask import AskIn, AskOut, SourceOut, UsageOut
from app.schemas.errors import ErrorOut

router = APIRouter(tags=["ask"])


# الراوتر مش عارف الإجابة جاية من بحث بالكلمات ولا من ذكاء اصطناعي
# router -> Answerer
@router.post(
    "/ask",
    response_model=AskOut,
    responses={429: {"model": ErrorOut, "description": "الشركة خلصت حد الأسئلة النهارده"}},
)
async def ask(
    org: CurrentOrgDep, body: AskIn, answerer: AnswererDep, quota: QuotaServiceDep
) -> AskOut:
    # لو السؤال نفسه غلط بيرجع 422 قبل ما نوصل هنا، فمش بيتحسب من الحد
    quota.consume_question(org.id)
    result = await answerer.answer(org.id, body.question)
    return AskOut(
        answer=result.text,
        sources=[SourceOut.model_validate(s) for s in result.sources],
        usage=UsageOut.model_validate(result.usage) if result.usage else None,
    )
