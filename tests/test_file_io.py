from warhammer.file_io import read_json_object, write_json_file, write_text_file


def test_write_json_file_creates_parent_and_formats_json(tmp_path):
    path = tmp_path / "nested" / "payload.json"

    write_json_file(path, {"b": 2})

    assert path.read_text(encoding="utf-8") == '{\n  "b": 2\n}'


def test_write_text_file_creates_parent(tmp_path):
    path = tmp_path / "nested" / "report.md"

    write_text_file(path, "# Report\n")

    assert path.read_text(encoding="utf-8") == "# Report\n"


def test_read_json_object_returns_dict_only(tmp_path):
    path = tmp_path / "payload.json"
    path.write_text('{"edition":"10e"}', encoding="utf-8")

    assert read_json_object(path) == {"edition": "10e"}

    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert read_json_object(path) == {}


def test_read_json_object_tolerates_missing_and_invalid_json(tmp_path):
    assert read_json_object(tmp_path / "missing.json") == {}

    path = tmp_path / "payload.json"
    path.write_text("{", encoding="utf-8")

    assert read_json_object(path) == {}
