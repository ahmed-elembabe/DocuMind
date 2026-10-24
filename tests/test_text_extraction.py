import pymupdf
import pytest

from app.core.errors import AppError
from app.services.text_extraction import extract_text
from tests.pdf_factory import make_pdf


def error_code(filename: str, data: bytes) -> str:
    with pytest.raises(AppError) as exc_info:
        extract_text(filename, data)
    return exc_info.value.code


def test_pdf_paragraphs_and_pages_are_separated_by_blank_lines():
    data = make_pdf([["Introduction", "Rent is one year"], ["Second page"]])

    assert extract_text("contract.pdf", data) == "Introduction\n\nRent is one year\n\nSecond page"


def test_pdf_extension_is_case_insensitive():
    assert extract_text("CONTRACT.PDF", make_pdf([["Hello"]])) == "Hello"


def test_text_file_is_decoded_and_bom_is_stripped():
    assert extract_text("notes.txt", "﻿نص".encode()) == "نص"


def test_non_utf8_text_file_is_rejected():
    assert error_code("notes.md", b"\xff\xfe\x00bad") == "invalid_encoding"


def test_broken_pdf_is_rejected():
    assert error_code("broken.pdf", b"%PDF-1.7 garbage") == "invalid_pdf"


def test_password_protected_pdf_is_rejected():
    data = make_pdf(
        [["secret"]], encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="pw", owner_pw="owner"
    )

    assert error_code("locked.pdf", data) == "encrypted_pdf"


def test_pdf_without_text_is_rejected():
    # صفحة فاضية زي ملف متصور سكانر مفيهوش غير صور
    assert error_code("scan.pdf", make_pdf([[]])) == "pdf_has_no_text"


def test_arabic_presentation_forms_become_normal_letters():
    # الملف ده بيتكتب بأشكال العرض فمن غير التصليح البحث مش هيلاقي ولا كلمة
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_htmlbox(pymupdf.Rect(50, 50, 550, 400), '<p dir="rtl">مدة عقد سنة واحدة</p>')
    data = pdf.tobytes()

    words = extract_text("contract.pdf", data).split()

    assert "مدة" in words
    assert "عقد" in words
