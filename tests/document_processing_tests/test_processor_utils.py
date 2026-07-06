"""Focused tests for _processor_utils.py — parse_llm_json and
normalize_confidence."""

import pytest

from backend.document_processing._processor_utils import (
    normalize_confidence,
    parse_llm_json,
)


# ---------------- parse_llm_json: success cases ----------------

def test_plain_json_object():
    assert parse_llm_json('{"a": 1}') == {"a": 1}


def test_fenced_json_response():
    raw = "```json\n{\"a\": 1}\n```"
    assert parse_llm_json(raw) == {"a": 1}


def test_fenced_without_json_tag():
    raw = "```\n{\"a\": 1}\n```"
    assert parse_llm_json(raw) == {"a": 1}


def test_prose_before_and_after():
    raw = 'Sure, here is the result: {"a": 1} — hope that helps!'
    assert parse_llm_json(raw) == {"a": 1}


def test_valid_object_followed_by_trailing_noise():
    # Deterministic behavior: the first complete JSON object is parsed;
    # anything after it (more prose, another object) is ignored rather
    # than corrupting the parse.
    raw = '{"a": 1} some noise {"b": 2}'
    assert parse_llm_json(raw) == {"a": 1}


# ---------------- parse_llm_json: failure cases ----------------

def test_empty_response():
    with pytest.raises(ValueError):
        parse_llm_json("")
    with pytest.raises(ValueError):
        parse_llm_json("   ")


def test_no_json_object():
    with pytest.raises(ValueError):
        parse_llm_json("no json here at all")


def test_malformed_json():
    with pytest.raises(ValueError):
        parse_llm_json('{"a": 1,}')


def test_top_level_json_array_is_rejected():
    with pytest.raises(ValueError):
        parse_llm_json("[1, 2, 3]")


def test_top_level_array_containing_object_is_rejected():
    # The processor contract requires a top-level JSON object. An array
    # that merely contains an object is still an array at the top
    # level and must be rejected, not unwrapped.
    with pytest.raises(ValueError):
        parse_llm_json('[{"a": 1}]')


# ---------------- normalize_confidence ----------------

def test_confidence_0_to_100_scale():
    assert normalize_confidence(87) == pytest.approx(0.87)


def test_confidence_already_normalized():
    assert normalize_confidence(0.5) == pytest.approx(0.5)


def test_confidence_above_range_clamped():
    assert normalize_confidence(150) == 1.0


def test_confidence_negative_clamped():
    assert normalize_confidence(-10) == 0.0


def test_confidence_none():
    assert normalize_confidence(None) is None


def test_confidence_non_numeric():
    assert normalize_confidence("high") is None