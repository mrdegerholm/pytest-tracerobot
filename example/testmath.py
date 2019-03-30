import pytest

def test_add():
    x = 1
    y = 2
    assert x + y == 3

def test_sub():
    x = -1
    assert x - x == 0

def test_mul():
    assert 1 * 2 == 2

def test_div():
    assert 2 / 1 == 2
