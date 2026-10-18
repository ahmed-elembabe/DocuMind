from dataclasses import dataclass


# فقرة واحدة من مستند، ومعاها رقم ترتيبها جوه المستند
# index = position in document
@dataclass(frozen=True, slots=True)
class Chunk:
    id: str
    org_id: str
    document_id: str
    index: int
    text: str
