from warhammer.update_config import default_update_paths, edition_latest_dir, edition_snapshot_dir


def test_default_update_paths_are_project_scoped(tmp_path):
    paths = default_update_paths(tmp_path)

    assert paths.project_root == tmp_path
    assert paths.data_dir == tmp_path / "data"
    assert paths.repo_dir == tmp_path / "data" / "wh40k-10e"
    assert paths.legacy_latest_dir == tmp_path / "data" / "latest"
    assert paths.ml_dir == tmp_path / "data" / "ml"
    assert paths.model_dir == tmp_path / "models"


def test_edition_data_paths_normalize_edition_names(tmp_path):
    assert edition_latest_dir("10E", data_dir=tmp_path / "data") == tmp_path / "data" / "10e" / "latest"
    assert edition_snapshot_dir(" 11e ", data_dir=tmp_path / "data") == tmp_path / "data" / "11e" / "snapshots"


def test_edition_data_paths_fall_back_to_default(tmp_path):
    assert edition_latest_dir("", data_dir=tmp_path / "data") == tmp_path / "data" / "10e" / "latest"
    assert edition_snapshot_dir("", data_dir=tmp_path / "data") == tmp_path / "data" / "10e" / "snapshots"
