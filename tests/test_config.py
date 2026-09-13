from config.settings import COMPLETENESS_DIMENSIONS, UPLOAD_LIMITS


def test_upload_limits_are_loaded_from_inspectable_yaml() -> None:
    assert UPLOAD_LIMITS.max_upload_mb == 10
    assert UPLOAD_LIMITS.max_pdf_pages == 20
    assert UPLOAD_LIMITS.min_meaningful_text_chars == 40


def test_completeness_dimensions_are_loaded_from_inspectable_yaml() -> None:
    assert COMPLETENESS_DIMENSIONS == (
        "客户需求",
        "核心场景",
        "预算",
        "决策人",
        "影响人",
        "时间计划",
        "下一步行动",
        "商机阶段证据",
    )
