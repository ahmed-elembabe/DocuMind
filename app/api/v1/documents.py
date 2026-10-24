from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Header, Query, Response, UploadFile

from app.core.deps import CurrentOrgDep, DocumentServiceDep, IngestionServiceDep
from app.models.document import DocumentStatus
from app.schemas.document import DocumentListOut, DocumentOut

router = APIRouter(prefix="/documents", tags=["documents"])


# استلمنا الملف، بس المعالجة لسه مخلصتش
# 202 Accepted
@router.post("", status_code=202, response_model=DocumentOut)
async def upload_document(
    org: CurrentOrgDep,
    file: Annotated[UploadFile, File(description="ملف .txt أو .md أو .pdf، أقصى حجم 2MB")],
    service: DocumentServiceDep,
    ingestion: IngestionServiceDep,
    background_tasks: BackgroundTasks,
    response: Response,
    idempotency_key: Annotated[
        str | None,
        Header(
            min_length=1,
            max_length=255,
            description="رقم فريد لكل عملية رفع، ولو اتبعت تاني بيرجع نفس المستند",
        ),
    ] = None,
) -> DocumentOut:
    doc, is_new = await service.upload(org.id, file, idempotency_key)
    if is_new:
        # بتشتغل بعد ما الرد يوصل للعميل، فهو مش مستني التقسيم
        background_tasks.add_task(ingestion.process, org.id, doc.id)
    else:
        # بنقول للعميل إن ده رد طلب قديم، ومتعملش مستند جديد
        response.headers["Idempotent-Replayed"] = "true"
    return DocumentOut.model_validate(doc)


@router.get("", response_model=DocumentListOut)
def list_documents(
    org: CurrentOrgDep,
    service: DocumentServiceDep,
    status: DocumentStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    after: str | None = None,
) -> DocumentListOut:
    items, next_cursor = service.list(org.id, status, limit, after)
    return DocumentListOut(
        items=[DocumentOut.model_validate(d) for d in items], next_cursor=next_cursor
    )


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(org: CurrentOrgDep, doc_id: str, service: DocumentServiceDep) -> DocumentOut:
    return DocumentOut.model_validate(service.get(org.id, doc_id))


# اتمسح ومفيش محتوى يرجع في الرد
# 204 No Content
@router.delete("/{doc_id}", status_code=204)
def delete_document(org: CurrentOrgDep, doc_id: str, service: DocumentServiceDep) -> None:
    service.delete(org.id, doc_id)
