from functools import lru_cache
from secrets import compare_digest
from typing import Annotated

from fastapi import Depends
from fastapi.security import APIKeyHeader

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.models.org import Org
from app.repositories.chunk_repo import ChunkRepo
from app.repositories.document_repo import DocumentRepo
from app.repositories.file_repo import FileRepo
from app.repositories.idempotency_repo import IdempotencyRepo
from app.repositories.usage_repo import UsageRepo
from app.services.answerer import Answerer
from app.services.document_service import DocumentService
from app.services.ingestion_service import IngestionService
from app.services.keyword_answerer import KeywordAnswerer
from app.services.quota_service import QuotaService

# بيقرا المفتاح من الهيدر، وبيظهر زرار التسجيل في صفحة التوثيق
# APIKeyHeader -> Authorize in /docs
# بنقفل الإيرور التلقائي عشان احنا اللي نرد بإيرور التطبيق بتاعنا
# auto_error=False -> AppError
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

SettingsDep = Annotated[Settings, Depends(get_settings)]
ApiKeyDep = Annotated[str | None, Depends(api_key_header)]


def get_current_org(settings: SettingsDep, api_key: ApiKeyDep) -> Org:
    if not api_key:
        raise AppError("missing_api_key", "لازم تبعت الـ API key في header اسمه X-API-Key", 401)

    for org in settings.orgs:
        # الدالة دي بتاخد نفس الوقت سواء المفتاح قريب من الصح أو بعيد
        # فمحدش يقدر يخمّن المفتاح حرف حرف من وقت الرد
        # compare_digest: prevents timing attacks
        if compare_digest(api_key.encode(), org.api_key.get_secret_value().encode()):
            return Org(id=org.id, name=org.name)

    raise AppError("invalid_api_key", "الـ API key ده غلط", 401)


CurrentOrgDep = Annotated[Org, Depends(get_current_org)]


# التخزين في الذاكرة لازم يبقى نسخة واحدة لكل التطبيق
# وإلا كل طلب هيشوف قاموس فاضي، ولما ننقل للداتابيز دي هتبقى جلسة اتصال
# lru_cache -> one instance; Postgres -> session
@lru_cache
def get_document_repo() -> DocumentRepo:
    return DocumentRepo()


@lru_cache
def get_file_repo() -> FileRepo:
    return FileRepo()


@lru_cache
def get_chunk_repo() -> ChunkRepo:
    return ChunkRepo()


@lru_cache
def get_usage_repo() -> UsageRepo:
    return UsageRepo()


@lru_cache
def get_idempotency_repo() -> IdempotencyRepo:
    return IdempotencyRepo()


DocumentRepoDep = Annotated[DocumentRepo, Depends(get_document_repo)]
FileRepoDep = Annotated[FileRepo, Depends(get_file_repo)]
ChunkRepoDep = Annotated[ChunkRepo, Depends(get_chunk_repo)]
UsageRepoDep = Annotated[UsageRepo, Depends(get_usage_repo)]
IdempotencyRepoDep = Annotated[IdempotencyRepo, Depends(get_idempotency_repo)]


def get_document_service(
    settings: SettingsDep,
    docs: DocumentRepoDep,
    files: FileRepoDep,
    chunks: ChunkRepoDep,
    idempotency: IdempotencyRepoDep,
) -> DocumentService:
    return DocumentService(docs, files, chunks, idempotency, settings.max_upload_bytes)


def get_ingestion_service(
    docs: DocumentRepoDep, files: FileRepoDep, chunks: ChunkRepoDep
) -> IngestionService:
    return IngestionService(docs, files, chunks)


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
IngestionServiceDep = Annotated[IngestionService, Depends(get_ingestion_service)]


def get_quota_service(settings: SettingsDep, usage: UsageRepoDep) -> QuotaService:
    return QuotaService(usage, settings.daily_question_quota)


QuotaServiceDep = Annotated[QuotaService, Depends(get_quota_service)]


# المكان الوحيد اللي بيقرر أنهي طريقة إجابة شغالة، وفي صفحة 6 هنغيّرها هنا
# KeywordAnswerer now, RagAnswerer later
def get_answerer(docs: DocumentRepoDep, chunks: ChunkRepoDep) -> Answerer:
    return KeywordAnswerer(docs, chunks)


AnswererDep = Annotated[Answerer, Depends(get_answerer)]
