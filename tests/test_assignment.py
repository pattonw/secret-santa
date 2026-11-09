import pytest
from omegaconf import OmegaConf

from ss.assignment import assignment, display_name, participants


def check(config, pairs):
    people = participants(config)
    assert sorted(a for a, _ in pairs) == sorted(people)
    assert sorted(b for _, b in pairs) == sorted(people)
    for a, b in pairs:
        assert a != b
        assert people[a].group != people[b].group
        assert (b, a) not in pairs


def test_constraints_hold(config):
    for seed in range(20):
        pairs, repeats = assignment(config, {}, seed=seed)
        check(config, pairs)
        assert repeats == 0


def test_repeats_are_strictly_minimised(config):
    # build a history out of a previous valid assignment; a repeat-free
    # solution still exists, so the solver must always find one
    previous, _ = assignment(config, {}, seed=1)
    history = {"2020": previous}
    for seed in range(30):
        pairs, repeats = assignment(config, history, seed=seed)
        check(config, pairs)
        assert repeats == 0
        assert not set(pairs) & set(previous)


def test_history_with_people_who_left(config):
    history = {"2019": [("zed", "a"), ("a", "zed")]}
    pairs, repeats = assignment(config, history, seed=3)
    check(config, pairs)
    assert repeats == 0


def test_two_people_need_allow_reciprocal():
    config = OmegaConf.create({"groups": {"x": [{"name": "x"}], "y": [{"name": "y"}]}})
    with pytest.raises(RuntimeError):
        assignment(config, {})
    config.allow_reciprocal = True
    pairs, _ = assignment(config, {})
    assert sorted(pairs) == [("x", "y"), ("y", "x")]


def test_duplicate_names_rejected():
    config = OmegaConf.create({"groups": {"x": [{"name": "Sam"}], "y": [{"name": "sam"}]}})
    with pytest.raises(ValueError, match="twice"):
        participants(config)


def test_display_name():
    assert display_name("ana maria") == "Ana Maria"
    assert display_name("  WILL ") == "Will"
