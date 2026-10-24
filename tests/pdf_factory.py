import pymupdf


def make_pdf(pages: list[list[str]], **save_options) -> bytes:
    """
    بتعمل ملف بي دي إف حقيقي في الذاكرة للتستات
    كل صفحة فيها فقرات وكل فقرة بعيدة عن اللي قبلها فبتطلع بلوك لوحدها
    make_pdf([["para 1", "para 2"], ["page 2"]])
    """
    pdf = pymupdf.open()
    for paragraphs in pages:
        page = pdf.new_page()
        for i, text in enumerate(paragraphs):
            page.insert_text((72, 72 + i * 100), text)
    data = pdf.tobytes(**save_options)
    pdf.close()
    return data
