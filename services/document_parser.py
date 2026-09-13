from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from config.settings import UPLOAD_LIMITS

MAX_PDF_PAGES = UPLOAD_LIMITS.max_pdf_pages
MIN_MEANINGFUL_TEXT_CHARS = UPLOAD_LIMITS.min_meaningful_text_chars


@dataclass
class PdfParseResult:
    text: str
    page_images: list[bytes]
    image_page_numbers: list[int]
    used_image_fallback: bool


def parse_pdf(data: bytes) -> PdfParseResult:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("当前环境未安装 PyMuPDF，无法解析 PDF。") from exc
    try:
        document = fitz.open(stream=BytesIO(data), filetype="pdf")
    except (RuntimeError, ValueError) as exc:
        raise ValueError("PDF 文件无法读取，请确认文件完整且未加密。") from exc
    if document.page_count > MAX_PDF_PAGES:
        raise ValueError(f"PDF 超过 {MAX_PDF_PAGES} 页限制，请上传更小的文件。")
    text_pages: list[str] = []
    images: list[bytes] = []
    image_page_numbers: list[int] = []
    for index in range(document.page_count):
        page = document.load_page(index)
        page_text = page.get_text("text").strip()
        if len(page_text) >= MIN_MEANINGFUL_TEXT_CHARS:
            text_pages.append(page_text)
            continue
        images.append(page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).tobytes("png"))
        image_page_numbers.append(index + 1)
    return PdfParseResult(
        text="\n".join(text_pages).strip(),
        page_images=images,
        image_page_numbers=image_page_numbers,
        used_image_fallback=bool(images),
    )
