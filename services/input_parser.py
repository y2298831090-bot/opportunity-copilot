from __future__ import annotations

import base64
from dataclasses import dataclass, field

from config.settings import UPLOAD_LIMITS
from services.document_parser import parse_pdf

MAX_UPLOAD_BYTES = UPLOAD_LIMITS.max_upload_mb * 1024 * 1024
SUPPORTED_IMAGE_TYPES = {"image/png", "image/jpeg"}
SUPPORTED_FILE_TYPES = SUPPORTED_IMAGE_TYPES | {"application/pdf"}


@dataclass
class ParsedInput:
    text: str
    image_data_urls: list[str]
    source_description: str
    has_visual_source: bool = False
    visual_source_labels: list[str] = field(default_factory=list)


def _data_url(data: bytes, mime_type: str) -> str:
    return f"data:{mime_type};base64,{base64.b64encode(data).decode('ascii')}"


def parse_submission(text: str, uploaded_file: object | None) -> ParsedInput:
    clean_text = text.strip()
    if uploaded_file is None:
        if len(clean_text) < 2:
            raise ValueError("请输入销售拜访记录或上传文件后再开始分析。")
        return ParsedInput(text=clean_text, image_data_urls=[], source_description="text")
    data = uploaded_file.getvalue()
    mime_type = getattr(uploaded_file, "type", "")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("文件超过 10 MB 限制，请上传更小的文件。")
    if mime_type not in SUPPORTED_FILE_TYPES:
        raise ValueError("暂不支持该文件格式。")
    if mime_type in SUPPORTED_IMAGE_TYPES:
        return ParsedInput(
            text=clean_text,
            image_data_urls=[_data_url(data, mime_type)],
            source_description="image",
            has_visual_source=True,
            visual_source_labels=["图片"],
        )
    pdf = parse_pdf(data)
    combined_text = "\n\n".join(part for part in [clean_text, pdf.text] if part).strip()
    images = [_data_url(image, "image/png") for image in pdf.page_images]
    if not combined_text and not images:
        raise ValueError("当前内容无法可靠识别，建议重新上传更清晰的文件或人工复核。")
    return ParsedInput(
        text=combined_text,
        image_data_urls=images,
        source_description="PDF",
        has_visual_source=pdf.used_image_fallback,
        visual_source_labels=[f"PDF page {page_number}" for page_number in pdf.image_page_numbers],
    )
