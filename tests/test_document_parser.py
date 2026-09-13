
import fitz
import pytest

from services.document_parser import MAX_PDF_PAGES, parse_pdf


def _pdf_bytes(text: str, pages: int = 1) -> bytes:
    document = fitz.open()
    for _ in range(pages):
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


def test_pdf_uses_native_text_when_meaningful_text_exists() -> None:
    result = parse_pdf(_pdf_bytes("Customer confirmed the knowledge-base support project. " * 3))
    assert "knowledge-base" in result.text
    assert result.used_image_fallback is False


def test_scanned_like_pdf_renders_page_images_for_vision() -> None:
    result = parse_pdf(_pdf_bytes(""))
    assert result.text == ""
    assert result.used_image_fallback is True
    assert result.page_images[0].startswith(b"\x89PNG")


def test_mixed_pdf_uses_native_text_and_visual_pages() -> None:
    document = fitz.open()
    text_page = document.new_page()
    text_page.insert_text((72, 72), "Native text page. " * 5)
    document.new_page()
    data = document.tobytes()
    document.close()

    result = parse_pdf(data)

    assert "Native text page" in result.text
    assert len(result.page_images) == 1
    assert result.used_image_fallback is True


def test_pdf_page_limit_is_enforced() -> None:
    with pytest.raises(ValueError, match=str(MAX_PDF_PAGES)):
        parse_pdf(_pdf_bytes("x", pages=MAX_PDF_PAGES + 1))
