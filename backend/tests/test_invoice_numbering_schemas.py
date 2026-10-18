from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.invoice_numbering import (
    BAD_TEXT,
    NO_SEQUENCE,
    TOO_LONG,
    TWO_SEQUENCES,
    NextNumberWrite,
    NumberingFormat,
    TextToken,
)

SEQ: dict[str, Any] = {
    "type": "sequence",
    "digits": 4,
    "start_at": 1,
    "restart": "yearly",
}


def _error(tokens: list[dict[str, Any]]) -> str:
    with pytest.raises(ValidationError) as caught:
        NumberingFormat.model_validate({"tokens": tokens})
    return caught.value.errors()[0]["msg"]


def test_default_shape_is_valid() -> None:
    fmt = NumberingFormat.model_validate(
        {
            "tokens": [
                {"type": "text", "value": "INV-"},
                {"type": "year"},
                {"type": "text", "value": "-"},
                SEQ,
            ]
        }
    )
    assert fmt.sequence.digits == 4


def test_a_sequence_is_required() -> None:
    assert _error([{"type": "text", "value": "INV-"}, {"type": "year"}]) == NO_SEQUENCE


def test_only_one_sequence() -> None:
    assert _error([SEQ, SEQ]) == TWO_SEQUENCES


def test_text_characters() -> None:
    assert _error([{"type": "text", "value": "INV#"}, SEQ]) == BAD_TEXT
    assert _error([{"type": "text", "value": "INV 1"}, SEQ]) == BAD_TEXT
    NumberingFormat.model_validate(
        {"tokens": [{"type": "text", "value": "A-b/9_"}, SEQ]}
    )


def test_hundred_characters_at_most() -> None:
    ten_digits = {**SEQ, "digits": 10}
    NumberingFormat.model_validate(
        {"tokens": [{"type": "text", "value": "x" * 90}, ten_digits]}
    )
    assert _error([{"type": "text", "value": "x" * 91}, ten_digits]) == TOO_LONG
    # Year, month and day count at their width.
    assert (
        _error(
            [
                {"type": "text", "value": "x" * 89},
                {"type": "year"},
                {"type": "month"},
                {"type": "day"},
                SEQ,
            ]
        )
        == TOO_LONG
    )


def test_adjacent_texts_are_joined() -> None:
    fmt = NumberingFormat.model_validate(
        {
            "tokens": [
                {"type": "text", "value": "INV"},
                {"type": "text", "value": "-"},
                SEQ,
            ]
        }
    )
    assert fmt.tokens[0] == TextToken(type="text", value="INV-")
    assert len(fmt.tokens) == 2


@pytest.mark.parametrize(
    "sequence",
    [
        {**SEQ, "digits": 0},
        {**SEQ, "digits": 11},
        {**SEQ, "start_at": -1},
        {**SEQ, "start_at": 10_000_000_000},
        {**SEQ, "restart": "weekly"},
    ],
)
def test_sequence_bounds(sequence: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        NumberingFormat.model_validate({"tokens": [sequence]})


def test_unknown_token_and_empty_text() -> None:
    with pytest.raises(ValidationError):
        NumberingFormat.model_validate({"tokens": [{"type": "week"}, SEQ]})
    with pytest.raises(ValidationError):
        NumberingFormat.model_validate({"tokens": [{"type": "text", "value": ""}, SEQ]})


def test_at_most_50_tokens() -> None:
    with pytest.raises(ValidationError):
        NumberingFormat.model_validate({"tokens": [{"type": "year"}] * 50 + [SEQ]})


def test_next_number_bounds() -> None:
    NextNumberWrite(next_value=0)
    NextNumberWrite(next_value=9_999_999_999)
    with pytest.raises(ValidationError):
        NextNumberWrite.model_validate({"next_value": -1})
    with pytest.raises(ValidationError):
        NextNumberWrite.model_validate({"next_value": 10_000_000_000})
