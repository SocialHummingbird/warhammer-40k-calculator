import pytest

from warhammer.update_args import build_update_arg_parser, parse_update_args
from warhammer.update_config import default_update_paths


def test_parse_update_args_uses_edition_scoped_defaults(tmp_path):
    paths = default_update_paths(tmp_path)

    args = parse_update_args(["--edition", "11E"], paths=paths, model_types=("centroid", "logistic_regression"))

    assert args.repo_dir == tmp_path / "data" / "wh40k-10e"
    assert args.csv_dir == tmp_path / "data" / "11e" / "latest"
    assert args.snapshot_dir == tmp_path / "data" / "11e" / "snapshots"
    assert args.legacy_latest_dir == tmp_path / "data" / "latest"
    assert args.remote == "origin"
    assert args.branch == "main"
    assert args.skip_fetch is False
    assert args.skip_ml is False
    assert args.ml_max_rows == 10000
    assert args.ml_strategy == "sample"
    assert args.ml_seed == 40
    assert args.ml_feature_set == "pre_match"
    assert args.ml_model_type == "centroid"
    assert args.ml_labels is None
    assert args.ml_label_key_columns == ["edition", "mode", "attacker_id", "defender_id"]


def test_parse_update_args_preserves_explicit_paths_and_flags(tmp_path):
    paths = default_update_paths(tmp_path)

    args = parse_update_args(
        [
            "--edition",
            "10e",
            "--repo-dir",
            "repo",
            "--csv-dir",
            "csv",
            "--snapshot-dir",
            "snapshots",
            "--legacy-latest-dir",
            "legacy",
            "--skip-fetch",
            "--skip-ml",
            "--skip-html",
            "--skip-snapshot",
            "--skip-legacy-latest",
            "--ml-strategy",
            "sequential",
            "--ml-max-rows",
            "0",
            "--ml-model-type",
            "logistic_regression",
            "--ml-labels",
            "labels.csv",
            "--ml-label-key-columns",
            "attacker_id",
            "defender_id",
        ],
        paths=paths,
        model_types=("centroid", "logistic_regression"),
    )

    assert str(args.repo_dir) == "repo"
    assert str(args.csv_dir) == "csv"
    assert str(args.snapshot_dir) == "snapshots"
    assert str(args.legacy_latest_dir) == "legacy"
    assert args.skip_fetch is True
    assert args.skip_ml is True
    assert args.skip_html is True
    assert args.skip_snapshot is True
    assert args.skip_legacy_latest is True
    assert args.ml_strategy == "sequential"
    assert args.ml_max_rows == 0
    assert args.ml_model_type == "logistic_regression"
    assert str(args.ml_labels) == "labels.csv"
    assert args.ml_label_key_columns == ["attacker_id", "defender_id"]


def test_parse_update_args_rejects_non_positive_sample_size(tmp_path):
    paths = default_update_paths(tmp_path)

    with pytest.raises(SystemExit):
        parse_update_args(["--ml-max-rows", "0"], paths=paths, model_types=("centroid",))


def test_build_update_arg_parser_exposes_model_type_choices(tmp_path):
    parser = build_update_arg_parser(paths=default_update_paths(tmp_path), model_types=("b", "a"))

    help_text = parser.format_help()

    assert "--ml-model-type" in help_text
    assert "--ml-labels" in help_text
    assert "--ml-label-key-columns" in help_text
    assert "{a,b}" in help_text
