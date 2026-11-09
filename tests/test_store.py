import pytest

from ss.store import (
    KEY_FILE,
    generate_key,
    load,
    load_key,
    read_assignments,
    rekey,
    store_assignments,
    write_assignments,
)


def test_round_trip(tmp_path):
    key = generate_key()
    pairs = [("a", "b"), ("b", "a")]
    write_assignments(tmp_path / "x.json", pairs, key)
    raw = load(tmp_path / "x.json")
    assert [a for a, _ in raw] == ["a", "b"] and all(b.startswith("gAAAA") for _, b in raw)
    assert load(tmp_path / "x.json", key) == pairs


def test_legacy_key_then_rekey(tmp_path):
    (tmp_path / "config.yaml").write_text("groups: {}\n")
    legacy = load_key(tmp_path)
    store_assignments(tmp_path, [("a", "b")], key=legacy, year=2020)
    store_assignments(tmp_path, [("b", "a")], key=legacy, year=2021)
    with pytest.raises(FileExistsError):
        store_assignments(tmp_path, [("b", "a")], key=legacy, year=2021)

    new_key = generate_key()
    rekey(tmp_path, legacy, new_key)
    (tmp_path / KEY_FILE).write_bytes(new_key + b"\n")
    assert load_key(tmp_path) == new_key
    # editing config.yaml no longer matters
    (tmp_path / "config.yaml").write_text("groups: {changed: []}\n")
    history = read_assignments(tmp_path, history=True, key=load_key(tmp_path))
    assert history == {"2020": [("a", "b")], "2021": [("b", "a")]}
    assert read_assignments(tmp_path, history=False, key=new_key, year=2021) == [("b", "a")]


def test_rekey_fails_before_writing_if_old_key_is_wrong(tmp_path):
    good = generate_key()
    store_assignments(tmp_path, [("a", "b")], key=good, year=2020)
    with pytest.raises(Exception):
        rekey(tmp_path, b"wrong", generate_key())
    assert load(tmp_path / "history" / "2020.json", good) == [("a", "b")]
