from __future__ import annotations

import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

EXCLUDED_NAMES = {".git", ".env", ".DS_Store", "__MACOSX", "__pycache__", ".pytest_cache", ".ruff_cache", ".superpowers", "dist", "server.pid"}
EXCLUDED_PATHS = {Path(".streamlit/secrets.toml"), Path("docs/superpowers")}
DELIVERY_TEXT_FILES = {Path("README.md"), Path("FINAL_ACCEPTANCE_REPORT.md")}
LOCAL_ABSOLUTE_PATH_PATTERN = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\Users\\)")


def _should_exclude(relative_path: Path) -> bool:
    return (
        any(part in EXCLUDED_NAMES for part in relative_path.parts)
        or any(relative_path == excluded or excluded in relative_path.parents for excluded in EXCLUDED_PATHS)
        or relative_path.suffix == ".pyc"
    )


def build_submission_archive(project_root: Path, archive_path: Path) -> Path:
    """Create a source-only ZIP and refuse to include secret-bearing paths."""
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    files = [path for path in project_root.rglob("*") if path.is_file()]
    selected = [path for path in files if not _should_exclude(path.relative_to(project_root))]
    for path in selected:
        relative_path = path.relative_to(project_root)
        if "secrets.toml" in relative_path.parts or relative_path.name == ".env":
            raise ValueError(f"拒绝将敏感文件写入提交包：{relative_path}")
        if relative_path in DELIVERY_TEXT_FILES:
            content = path.read_text(encoding="utf-8")
            if LOCAL_ABSOLUTE_PATH_PATTERN.search(content):
                raise RuntimeError("提交包文本文件包含本机绝对路径。")
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as zip_file:
        for path in selected:
            zip_file.write(path, path.relative_to(project_root))
    with ZipFile(archive_path) as zip_file:
        unsafe = [
            name for name in zip_file.namelist()
            if _should_exclude(Path(name)) or name.endswith("secrets.toml")
        ]
    if unsafe:
        raise RuntimeError(f"提交包安全检查失败：{', '.join(unsafe)}")
    return archive_path


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    archive = build_submission_archive(project_root, project_root / "dist" / "opportunity-copilot-submission.zip")
    print(f"已生成安全提交包：{archive}")


if __name__ == "__main__":
    main()
