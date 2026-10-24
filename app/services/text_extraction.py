import unicodedata
from pathlib import Path

import pymupdf

from app.core.errors import AppError

# أي ملف من النوع ده لازم يبدأ بالعلامة دي
PDF_MAGIC = b"%PDF-"


def extract_text(filename: str, data: bytes) -> str:
    """
    بتطلّع النص من الملف على حسب امتداده
    وبين كل فقرة والتانية سطر فاضي عشان التقسيم يلاقيها

    الدالة دي مش متزامنة لأنها شغل تقيل على المعالج ومفيهاش انتظار
    فلازم تتنادى من ثريد تاني عشان متوقفش السيرفر
    asyncio.to_thread(extract_text, filename, data)
    """
    if Path(filename).suffix.lower() == ".pdf":
        return _extract_pdf(data)
    return _decode_text(data)


def _decode_text(data: bytes) -> str:
    try:
        # الترميز ده بيشيل العلامة المخفية اللي بعض البرامج بتحطها في أول الملف
        # utf-8-sig strips the BOM
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise AppError("invalid_encoding", "الملف لازم يبقى نص بترميز UTF-8", 422)


def _extract_pdf(data: bytes) -> str:
    try:
        pdf = pymupdf.open(stream=data, filetype="pdf")
    except pymupdf.FileDataError:
        raise AppError("invalid_pdf", "الملف ده مش PDF سليم", 422)

    with pdf:
        if pdf.needs_pass:
            raise AppError("encrypted_pdf", "الملف محمي بباسورد، ارفعه من غير باسورد", 422)

        # كل صفحة بتتقسم لبلوكات وكل بلوك تقريباً فقرة
        # والنوع صفر يعني نص والواحد يعني صورة
        # page.get_text("blocks") -> (x0, y0, x1, y1, text, block_no, block_type)
        blocks = [
            block[4].strip()
            for page in pdf
            for block in page.get_text("blocks")
            if block[6] == 0 and block[4].strip()
        ]

    if not blocks:
        # غالباً الملف صور متصورة ومفيهوش نص يتقري
        raise AppError(
            "pdf_has_no_text", "الملف مفيهوش نص يتقري، ممكن يكون صور متصورة سكانر", 422
        )

    # بعض البرامج بتكتب الحروف العربي بأشكال العرض بتاعتها مش بالحروف نفسها
    # فالكلمة بتتشاف زي ما هي بس حروفها مختلفة والبحث مش هيلاقيها
    # فبنرجّع كل حرف لأصله
    # unicodedata.normalize("NFKC", text)
    return unicodedata.normalize("NFKC", "\n\n".join(blocks))
