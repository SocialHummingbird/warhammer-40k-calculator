from pathlib import Path

from warhammer.ml.update import refresh_ml_artifacts


def test_refresh_ml_artifacts_builds_update_commands(tmp_path):
    commands = []
    csv_dir = tmp_path / "data" / "10e" / "latest"
    ml_root = tmp_path / "data" / "ml"
    model_root = tmp_path / "models"
    csv_dir.mkdir(parents=True)

    def write_features(command, cwd):
        commands.append((list(command), cwd))
        if command[1] == "export_ml_features.py":
            output = command[command.index("--output") + 1]
            path = Path(output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("winner_label\nattacker\n", encoding="utf-8")

    result = refresh_ml_artifacts(
        csv_dir=csv_dir,
        edition="10E",
        max_rows=500,
        strategy="sample",
        seed=42,
        feature_set="pre_match",
        model_type="centroid",
        ml_root=ml_root,
        model_root=model_root,
        project_root=tmp_path,
        command_runner=write_features,
        python_executable="python",
        supported_rulesets={"10e"},
    )

    assert result is not None
    assert result["edition"] == "10e"
    assert result["feature_rows"] == 1
    assert result["feature_path"] == ml_root / "10e" / "matchup_training_rows.csv"
    assert result["model_path"] == model_root / "10e" / "matchup_centroid_model.json"
    assert [command[0][1] for command in commands] == [
        "export_ml_features.py",
        "train_ml_model.py",
        "compare_ml_models.py",
        "verify_ml_artifacts.py",
    ]
    assert all(cwd == tmp_path for _, cwd in commands)


def test_refresh_ml_artifacts_passes_external_labels_to_training_and_comparison(tmp_path):
    commands = []
    csv_dir = tmp_path / "data" / "10e" / "latest"
    labels_path = tmp_path / "labels.csv"
    ml_root = tmp_path / "data" / "ml"
    model_root = tmp_path / "models"
    csv_dir.mkdir(parents=True)
    labels_path.write_text("edition,attacker_id,defender_id,winner_label\n", encoding="utf-8")

    def capture(command, cwd):
        commands.append((list(command), cwd))
        if command[1] == "export_ml_features.py":
            output = command[command.index("--output") + 1]
            path = Path(output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("winner_label\nattacker\n", encoding="utf-8")

    refresh_ml_artifacts(
        csv_dir=csv_dir,
        edition="10e",
        max_rows=500,
        strategy="sample",
        seed=42,
        feature_set="pre_match",
        model_type="centroid",
        label_overrides_path=labels_path,
        label_key_columns=["edition", "attacker_id", "defender_id"],
        ml_root=ml_root,
        model_root=model_root,
        project_root=tmp_path,
        command_runner=capture,
        python_executable="python",
        supported_rulesets={"10e"},
    )

    train_command = next(command for command, _ in commands if command[1] == "train_ml_model.py")
    comparison_command = next(command for command, _ in commands if command[1] == "compare_ml_models.py")
    for command in (train_command, comparison_command):
        assert command[command.index("--labels") + 1] == str(labels_path)
        assert command[command.index("--label-key-columns") + 1 : command.index("--label-key-columns") + 4] == [
            "edition",
            "attacker_id",
            "defender_id",
        ]


def test_refresh_ml_artifacts_skips_unsupported_ruleset(tmp_path):
    messages = []
    commands = []

    result = refresh_ml_artifacts(
        csv_dir=tmp_path / "latest",
        edition="11e",
        max_rows=100,
        strategy="sample",
        seed=1,
        feature_set="pre_match",
        model_type="centroid",
        ml_root=tmp_path / "ml",
        model_root=tmp_path / "models",
        project_root=tmp_path,
        command_runner=lambda command, cwd: commands.append((command, cwd)),
        supported_rulesets={"10e"},
        message_sink=messages.append,
    )

    assert result is None
    assert commands == []
    assert messages == ["Skipping ML refresh for unsupported rules edition: 11e"]
