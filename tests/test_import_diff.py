from warhammer.import_diff import build_import_diff, csv_data_row_count, load_tables, row_key


def test_build_import_diff_counts_added_removed_and_changed_rows():
    before = {
        "units": {
            "u1": {"unit_id": "u1", "name": "Old"},
            "u2": {"unit_id": "u2", "name": "Removed"},
        },
        "weapons": {},
    }
    after = {
        "units": {
            "u1": {"unit_id": "u1", "name": "New"},
            "u3": {"unit_id": "u3", "name": "Added"},
        },
        "weapons": {},
    }

    diff = build_import_diff(before, after, source_before={}, source_after={}, table_names=("units", "weapons"))

    unit_diff = diff["tables"]["units"]
    assert unit_diff["before_count"] == 2
    assert unit_diff["after_count"] == 2
    assert unit_diff["added_count"] == 1
    assert unit_diff["removed_count"] == 1
    assert unit_diff["changed_count"] == 1
    assert unit_diff["added_samples"] == ["u3"]
    assert unit_diff["removed_samples"] == ["u2"]
    assert unit_diff["changed_samples"] == ["u1"]


def test_load_tables_deduplicates_repeated_keys(tmp_path):
    (tmp_path / "units.csv").write_text("unit_id,name\nu1,First\nu1,Second\n,No ID\n", encoding="utf-8")

    tables = load_tables(tmp_path, tables={"units": ("units.csv", "unit_id")})

    assert set(tables["units"]) == {"u1", "u1#2", "<row-3>"}
    assert tables["units"]["u1#2"]["name"] == "Second"


def test_row_key_joins_compound_fields():
    assert row_key({"unit_id": "u1", "keyword_id": "k1"}, ("unit_id", "keyword_id")) == "u1:k1"
    assert row_key({"unit_id": " u1 "}, "unit_id") == "u1"


def test_csv_data_row_count_excludes_header(tmp_path):
    path = tmp_path / "rows.csv"
    path.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")

    assert csv_data_row_count(path) == 2
    assert csv_data_row_count(tmp_path / "missing.csv") == 0
