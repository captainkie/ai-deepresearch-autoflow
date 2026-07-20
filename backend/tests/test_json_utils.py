from __future__ import annotations

import pytest

from app.providers.json_utils import JSONParseError, extract_json


def test_extract_json_with_surrounding_text():
    assert extract_json('prefix {"a": 1} suffix') == {"a": 1}


def test_extract_json_from_fenced_block():
    text = 'Here you go:\n```json\n{"brief": {"objective": "x"}, "sections": []}\n```\nDone.'
    out = extract_json(text)
    assert out["brief"]["objective"] == "x"
    assert out["sections"] == []


def test_extract_json_strips_trailing_commas():
    assert extract_json('{"a": 1, "b": [1, 2,], }') == {"a": 1, "b": [1, 2]}


def test_extract_json_ignores_braces_inside_strings():
    assert extract_json('{"note": "a } b { c"}') == {"note": "a } b { c"}


def test_extract_json_raises_on_garbage():
    with pytest.raises(JSONParseError):
        extract_json("no json here at all")


def test_extract_json_raises_on_unbalanced():
    with pytest.raises(JSONParseError):
        extract_json('{"a": 1')
