import json
from pathlib import Path


def test_builtin_samples_cover_required_cases() -> None:
    samples = json.loads(Path("samples/sample_cases.json").read_text(encoding="utf-8"))
    names = {item["name"] for item in samples}
    assert {"S0 线索", "S1 需求初探", "S2 方案验证", "S3 商务评估", "S4 决策审批", "S5 赢单/签约", "模糊表达", "冲突信息"} <= names
