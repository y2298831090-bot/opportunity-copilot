from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.package_submission import build_submission_archive


def test_submission_package_excludes_secrets_and_cache_files(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("print('ok')", encoding="utf-8")
    (project / ".env").write_text("secret", encoding="utf-8")
    (project / ".streamlit").mkdir()
    (project / ".streamlit" / "secrets.toml").write_text("secret", encoding="utf-8")
    (project / "__pycache__").mkdir()
    (project / "__pycache__" / "app.pyc").write_bytes(b"cache")
    (project / ".superpowers").mkdir()
    (project / ".superpowers" / "state.json").write_text("dev", encoding="utf-8")
    (project / "server.pid").write_text("123", encoding="utf-8")
    (project / "docs" / "superpowers").mkdir(parents=True)
    (project / "docs" / "superpowers" / "plan.md").write_text("dev", encoding="utf-8")

    archive = build_submission_archive(project, tmp_path / "submission.zip")

    with ZipFile(archive) as zip_file:
        assert zip_file.namelist() == ["app.py"]


def test_submission_package_rejects_local_absolute_paths_in_delivery_text(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("Project root: /Users/example/project", encoding="utf-8")

    with pytest.raises(RuntimeError, match="本机绝对路径"):
        build_submission_archive(project, tmp_path / "submission.zip")
