from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]


def test_app_icon_assets_are_present_and_parseable():
    svg_path = ROOT / "web" / "assets" / "app-icon.svg"
    ico_path = ROOT / "web" / "assets" / "app-icon.ico"

    assert svg_path.exists()
    assert ico_path.exists()
    ElementTree.parse(svg_path)
    assert ico_path.read_bytes()[:4] == b"\x00\x00\x01\x00"


def test_desktop_shortcut_script_uses_project_icon():
    script = (ROOT / "create_desktop_shortcut.ps1").read_text(encoding="utf-8")

    assert "start_warhammer_calculator.ps1" in script
    assert "web\\assets\\app-icon.ico" in script
    assert "IconLocation" in script


def test_update_launcher_forwards_ml_training_options():
    script = (ROOT / "update_and_open_local_html.ps1").read_text(encoding="utf-8")

    for flag in [
        "--skip-ml",
        "--ml-max-rows",
        "--ml-strategy",
        "--ml-seed",
        "--ml-feature-set",
        "--ml-model-type",
        "--ml-labels",
        "--ml-label-key-columns",
    ]:
        assert flag in script
