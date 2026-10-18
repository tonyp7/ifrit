import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

Restart = Literal["never", "yearly", "monthly", "daily"]

MAX_TOKENS = 50
MAX_NUMBER_LENGTH = 100
MAX_SEQUENCE_VALUE = 9_999_999_999
# What may appear between tokens: enough for prefixes and separators, nothing that needs
# escaping in a file name, a URL or an e-invoice.
_TEXT = re.compile(r"^[A-Za-z0-9/_-]+$")

# The plan's wording, returned as is so the format editor can show the server's reason.
NO_SEQUENCE = "Invoice numbers may not be unique. Add a sequence."
TWO_SEQUENCES = "A format can contain only one sequence."
BAD_TEXT = "Only letters, numbers, -, / and _ are allowed."
TOO_LONG = "Invoice numbers cannot exceed 100 characters."


class TextToken(BaseModel):
    type: Literal["text"]
    value: str = Field(min_length=1)


class YearToken(BaseModel):
    type: Literal["year"]


class MonthToken(BaseModel):
    type: Literal["month"]


class DayToken(BaseModel):
    type: Literal["day"]


class SequenceToken(BaseModel):
    type: Literal["sequence"]
    digits: int = Field(ge=1, le=10)
    start_at: int = Field(ge=0, le=MAX_SEQUENCE_VALUE)
    restart: Restart


Token = Annotated[
    TextToken | YearToken | MonthToken | DayToken | SequenceToken,
    Field(discriminator="type"),
]

# Characters each token can take in a rendered number; a sequence counts at its digits, the
# width it is padded to.
_WIDTH = {"year": 4, "month": 2, "day": 2}


def _width(token: TextToken | YearToken | MonthToken | DayToken | SequenceToken) -> int:
    match token:
        case TextToken(value=value):
            return len(value)
        case SequenceToken(digits=digits):
            return digits
        case _:
            return _WIDTH[token.type]


class NumberingFormat(BaseModel):
    tokens: list[Token] = Field(max_length=MAX_TOKENS)

    @model_validator(mode="after")
    def check_tokens(self) -> NumberingFormat:
        # Adjacent texts are one text: `INV` then `-` is `INV-`.
        joined: list[TextToken | YearToken | MonthToken | DayToken | SequenceToken] = []
        for token in self.tokens:
            previous = joined[-1] if joined else None
            if isinstance(token, TextToken) and isinstance(previous, TextToken):
                joined[-1] = TextToken(type="text", value=previous.value + token.value)
            else:
                joined.append(token)
        self.tokens = joined

        sequences = sum(isinstance(token, SequenceToken) for token in joined)
        if sequences == 0:
            raise PydanticCustomError("numbering_no_sequence", NO_SEQUENCE)
        if sequences > 1:
            raise PydanticCustomError("numbering_two_sequences", TWO_SEQUENCES)
        if any(isinstance(t, TextToken) and not _TEXT.match(t.value) for t in joined):
            raise PydanticCustomError("numbering_text", BAD_TEXT)
        if sum(_width(token) for token in joined) > MAX_NUMBER_LENGTH:
            raise PydanticCustomError("numbering_too_long", TOO_LONG)
        return self

    @property
    def sequence(self) -> SequenceToken:
        return next(t for t in self.tokens if isinstance(t, SequenceToken))


class NumberingFormatWrite(NumberingFormat):
    # Replacing the format once invoices have been issued must be confirmed explicitly.
    confirm: bool = False


class NextNumberWrite(BaseModel):
    # Strict, so "5" or 5.0 is refused rather than read as 5.
    model_config = ConfigDict(strict=True)

    next_value: int = Field(ge=0, le=MAX_SEQUENCE_VALUE)


class NumberingState(BaseModel):
    tokens: list[Token]
    # The sequence value the next invoice issued today would receive.
    next_value: int
    # The next three numbers, rendered for today.
    preview: list[str]
    # Whether any invoice has been issued (or issued then voided).
    has_issued: bool
