from pathlib import Path


def test_project_has_double_click_launcher() -> None:
    launcher = Path("open_opportunity_copilot.command")

    assert launcher.is_file()
    assert "127.0.0.1:8501" in launcher.read_text(encoding="utf-8")
