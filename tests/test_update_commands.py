from pathlib import Path

from warhammer.update_commands import bsdata_import_command, local_html_export_command


def test_bsdata_import_command_includes_repo_output_and_edition():
    command = bsdata_import_command(
        repo_dir=Path("data/wh40k-10e"),
        csv_dir=Path("data/10e/latest"),
        edition="10e",
        python_executable="python",
    )

    assert command == [
        "python",
        "import_bsdata.py",
        "data\\wh40k-10e",
        "--output",
        "data\\10e\\latest",
        "--edition",
        "10e",
    ]


def test_local_html_export_command_omits_model_when_no_ml_artifact():
    command = local_html_export_command(
        csv_dir=Path("data/10e/latest"),
        python_executable="python",
    )

    assert command == ["python", "export_local_html.py", "--csv-dir", "data\\10e\\latest"]


def test_local_html_export_command_includes_model_when_available():
    command = local_html_export_command(
        csv_dir=Path("data/10e/latest"),
        ml_artifacts={"model_path": Path("models/10e/matchup_centroid_model.json")},
        python_executable="python",
    )

    assert command == [
        "python",
        "export_local_html.py",
        "--csv-dir",
        "data\\10e\\latest",
        "--model",
        "models\\10e\\matchup_centroid_model.json",
    ]
