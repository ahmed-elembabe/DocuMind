import asyncio
import time

import pytest

from app.repositories.chunk_repo import ChunkRepo
from app.repositories.document_repo import DocumentRepo
from app.repositories.file_repo import FileRepo
from app.services import ingestion_service
from app.services.ingestion_service import IngestionService, split_into_chunks


def test_split_into_chunks_by_blank_lines():
    text = "الفقرة الأولى\nسطر تاني فيها\n\n\n  الفقرة التانية  \n \nالتالتة"

    assert split_into_chunks(text) == [
        "الفقرة الأولى\nسطر تاني فيها",
        "الفقرة التانية",
        "التالتة",
    ]


def test_split_into_chunks_of_whitespace_is_empty():
    assert split_into_chunks("  \n\n \t\n") == []


@pytest.fixture
def setup():
    docs, files, chunks = DocumentRepo(), FileRepo(), ChunkRepo()
    return docs, files, chunks, IngestionService(docs, files, chunks)


def _upload(docs, files, data: bytes):
    doc = docs.add("org-a", "f.txt", len(data))
    files.save("org-a", doc.id, data)
    return doc


def test_process_marks_ready_and_saves_chunks(setup):
    docs, files, chunks, service = setup
    doc = _upload(docs, files, "أ\n\nب".encode())

    asyncio.run(service.process("org-a", doc.id))

    assert docs.get("org-a", doc.id).status == "ready"
    assert [c.text for c in chunks.list_by_document("org-a", doc.id)] == ["أ", "ب"]


def test_process_strips_utf8_bom(setup):
    docs, files, chunks, service = setup
    doc = _upload(docs, files, "﻿نص".encode())

    asyncio.run(service.process("org-a", doc.id))

    assert chunks.list_by_document("org-a", doc.id)[0].text == "نص"


def test_process_rejects_non_utf8(setup):
    docs, files, _, service = setup
    doc = _upload(docs, files, b"\xff\xfe\x00bad")

    asyncio.run(service.process("org-a", doc.id))

    failed = docs.get("org-a", doc.id)
    assert failed.status == "failed"
    assert "UTF-8" in failed.error


def test_unexpected_error_marks_failed_with_generic_reason(setup, monkeypatch):
    docs, files, chunks, service = setup
    doc = _upload(docs, files, b"text")

    def boom(text):
        raise RuntimeError("internal details")

    monkeypatch.setattr(ingestion_service, "split_into_chunks", boom)
    asyncio.run(service.process("org-a", doc.id))

    failed = docs.get("org-a", doc.id)
    assert failed.status == "failed"
    assert failed.error == "حصل خطأ غير متوقع أثناء معالجة الملف"
    # تفاصيل الخطأ الداخلية متطلعش للعميل
    assert "internal" not in failed.error


def test_process_skips_deleted_document(setup):
    docs, files, chunks, service = setup

    asyncio.run(service.process("org-a", "missing"))

    assert chunks.list_by_document("org-a", "missing") == []


def test_process_twice_does_not_duplicate_chunks(setup):
    docs, files, chunks, service = setup
    doc = _upload(docs, files, "أ\n\nب".encode())

    asyncio.run(service.process("org-a", doc.id))
    asyncio.run(service.process("org-a", doc.id))

    assert [c.text for c in chunks.list_by_document("org-a", doc.id)] == ["أ", "ب"]
    assert docs.get("org-a", doc.id).status == "ready"


def test_process_replaces_chunks_left_by_a_crashed_run(setup):
    docs, files, chunks, service = setup
    doc = _upload(docs, files, "أ\n\nب".encode())
    # التشغيل اللي فات حفظ الفقرات ومات قبل ما يغيّر الحالة
    chunks.add_many("org-a", doc.id, ["أ", "ب"])

    asyncio.run(service.process("org-a", doc.id))

    assert [c.text for c in chunks.list_by_document("org-a", doc.id)] == ["أ", "ب"]
    assert docs.get("org-a", doc.id).status == "ready"


def test_parsing_runs_in_a_thread_so_the_event_loop_keeps_working(setup, monkeypatch):
    docs, files, _, service = setup
    doc = _upload(docs, files, b"text")

    def slow_extract(filename: str, data: bytes) -> str:
        # شغل تقيل من غير أي انتظار زي قراية ملف كبير
        time.sleep(0.3)
        return "text"

    monkeypatch.setattr(ingestion_service, "extract_text", slow_extract)

    async def run() -> int:
        ticks = 0

        # بتمثّل باقي الطلبات اللي السيرفر بيرد عليها وهو بيقرا الملف
        async def other_requests() -> None:
            nonlocal ticks
            while True:
                await asyncio.sleep(0.01)
                ticks += 1

        task = asyncio.create_task(other_requests())
        await service.process("org-a", doc.id)
        task.cancel()
        return ticks

    ticks = asyncio.run(run())

    # لو القراية اشتغلت على السيرفر نفسه العداد هيفضل صفر
    assert ticks >= 10
    assert docs.get("org-a", doc.id).status == "ready"
