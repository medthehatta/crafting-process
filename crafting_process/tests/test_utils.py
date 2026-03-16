import pytest

from crafting_process.utils import only


def test_only_returns_single_element():
    assert only([42]) == 42


def test_only_works_with_any_iterable():
    assert only(x for x in ["hello"]) == "hello"


def test_only_raises_on_empty():
    with pytest.raises(ValueError, match="empty"):
        only([])


def test_only_raises_on_multiple():
    with pytest.raises(ValueError, match="2"):
        only([1, 2])
