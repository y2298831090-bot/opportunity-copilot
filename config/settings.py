from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class UploadLimits:
    max_upload_mb: int
    max_pdf_pages: int
    min_meaningful_text_chars: int


def _load_crm_rules() -> dict:
    config_path = Path(__file__).with_name("crm_rules.yaml")
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def _load_upload_limits() -> UploadLimits:
    data = _load_crm_rules()
    limits = data["upload_limits"]
    return UploadLimits(
        max_upload_mb=int(limits["max_upload_mb"]),
        max_pdf_pages=int(limits["max_pdf_pages"]),
        min_meaningful_text_chars=int(limits["min_meaningful_text_chars"]),
    )


UPLOAD_LIMITS = _load_upload_limits()
COMPLETENESS_DIMENSIONS: tuple[str, ...] = tuple(_load_crm_rules()["completeness_dimensions"])
