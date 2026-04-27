from warhammer.ml.artifacts import ml_artifact_paths, ml_feature_path, ml_model_filename, ml_model_path


def test_ml_artifact_paths_are_edition_scoped(tmp_path):
    ml_root = tmp_path / "data" / "ml"
    model_root = tmp_path / "models"

    paths = ml_artifact_paths("10E", ml_root=ml_root, model_root=model_root, model_type="logistic_regression")

    assert paths.edition == "10e"
    assert paths.feature_path == ml_root / "10e" / "matchup_training_rows.csv"
    assert paths.model_path == model_root / "10e" / "matchup_logistic_model.json"
    assert paths.audit_path == model_root / "10e" / "matchup_logistic_model.md"
    assert paths.comparison_path == model_root / "10e" / "model_comparison.md"


def test_ml_feature_and_model_path_helpers_use_roots(tmp_path):
    assert ml_feature_path("10e", ml_root=tmp_path / "features") == tmp_path / "features" / "10e" / "matchup_training_rows.csv"
    assert ml_model_path("10e", model_root=tmp_path / "models") == tmp_path / "models" / "10e" / "matchup_centroid_model.json"


def test_ml_model_filename_maps_known_model_types():
    assert ml_model_filename("centroid") == "matchup_centroid_model.json"
    assert ml_model_filename("nearest-centroid") == "matchup_centroid_model.json"
    assert ml_model_filename("logistic_regression") == "matchup_logistic_model.json"
    assert ml_model_filename("custom") == "matchup_custom_model.json"
