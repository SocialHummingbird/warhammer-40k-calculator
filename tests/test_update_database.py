from update_database import _build_import_diff


def test_build_import_diff_counts_added_removed_and_changed_rows():
    before = {
        "units": {
            "u1": {"unit_id": "u1", "name": "Old"},
            "u2": {"unit_id": "u2", "name": "Removed"},
        },
        "weapons": {},
        "abilities": {},
        "keywords": {},
        "unit_keywords": {},
    }
    after = {
        "units": {
            "u1": {"unit_id": "u1", "name": "New"},
            "u3": {"unit_id": "u3", "name": "Added"},
        },
        "weapons": {},
        "abilities": {},
        "keywords": {},
        "unit_keywords": {},
    }

    diff = _build_import_diff(before, after, source_before={}, source_after={})

    unit_diff = diff["tables"]["units"]
    assert unit_diff["before_count"] == 2
    assert unit_diff["after_count"] == 2
    assert unit_diff["added_count"] == 1
    assert unit_diff["removed_count"] == 1
    assert unit_diff["changed_count"] == 1
    assert unit_diff["added_samples"] == ["u3"]
    assert unit_diff["removed_samples"] == ["u2"]
    assert unit_diff["changed_samples"] == ["u1"]
