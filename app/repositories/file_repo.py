class FileRepo:
    """
    محتوى الملفات المرفوعة، مؤقتاً في الذاكرة

    بعدين ممكن يتخزن على الهارد أو في خدمة تخزين سحابية من غير ما حاجة تانية تتغيّر
    disk / S3
    """

    def __init__(self) -> None:
        # مفتاح القاموس فيه معرّف الشركة، فمستحيل توصل لملف شركة تانية بمعرّف الملف بس
        # key = (org_id, doc_id)
        self._files: dict[tuple[str, str], bytes] = {}

    def save(self, org_id: str, doc_id: str, data: bytes) -> None:
        self._files[(org_id, doc_id)] = data

    def get(self, org_id: str, doc_id: str) -> bytes | None:
        return self._files.get((org_id, doc_id))

    def delete(self, org_id: str, doc_id: str) -> None:
        self._files.pop((org_id, doc_id), None)
