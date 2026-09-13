from dataclasses import dataclass

import pytest

from services.input_parser import MAX_UPLOAD_BYTES, parse_submission


@dataclass
class Upload:
    data: bytes
    type: str

    def getvalue(self) -> bytes:
        return self.data


def test_text_submission_has_no_visual_source() -> None:
    result = parse_submission("客户明确提出业务需求", None)
    assert result.has_visual_source is False


def test_image_submission_preserves_visual_source() -> None:
    result = parse_submission("", Upload(b"image", "image/png"))
    assert result.has_visual_source is True
    assert result.image_data_urls


def test_empty_submission_is_rejected() -> None:
    with pytest.raises(ValueError, match="请输入销售拜访记录"):
        parse_submission(" ", None)


def test_oversized_upload_is_rejected() -> None:
    with pytest.raises(ValueError, match="超过"):
        parse_submission("", Upload(b"x" * (MAX_UPLOAD_BYTES + 1), "image/png"))
