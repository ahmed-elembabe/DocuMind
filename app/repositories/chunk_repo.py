from uuid import uuid4

from app.models.chunk import Chunk


class ChunkRepo:
    """
    فقرات المستندات، مؤقتاً في الذاكرة
    كل فقرة زي صف في جدول
    """

    def __init__(self) -> None:
        self._chunks: dict[str, Chunk] = {}

    def add_many(self, org_id: str, document_id: str, texts: list[str]) -> list[Chunk]:
        chunks = [
            Chunk(id=uuid4().hex, org_id=org_id, document_id=document_id, index=i, text=text)
            for i, text in enumerate(texts)
        ]
        for chunk in chunks:
            self._chunks[chunk.id] = chunk
        return chunks

    def list_by_document(self, org_id: str, document_id: str) -> list[Chunk]:
        chunks = [
            c
            for c in self._chunks.values()
            if c.org_id == org_id and c.document_id == document_id
        ]
        return sorted(chunks, key=lambda c: c.index)

    def list_by_org(self, org_id: str) -> list[Chunk]:
        return [c for c in self._chunks.values() if c.org_id == org_id]

    def delete_by_document(self, org_id: str, document_id: str) -> None:
        for chunk in self.list_by_document(org_id, document_id):
            del self._chunks[chunk.id]
