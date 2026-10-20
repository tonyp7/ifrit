from pathlib import Path

import pytest

from app.pdf.tokens import TOKENS

PAGE = Path(__file__).resolve().parents[2] / "docs" / "guide" / "invoice-template.md"


@pytest.mark.skipif(
    not PAGE.exists(), reason="the documentation is not part of this checkout"
)
def test_the_guide_lists_every_placeholder() -> None:
    text = PAGE.read_text()
    missing = []
    for name in TOKENS:
        # The parties table shows the vendor's names and says the client's work the same way.
        listed = name.replace("bill_to_", "bill_from_", 1)
        if f"`{{{{{listed}}}}}`" not in text:
            missing.append(name)
    assert missing == []


@pytest.mark.skipif(
    not PAGE.exists(), reason="the documentation is not part of this checkout"
)
def test_the_guide_names_no_placeholder_that_does_not_exist() -> None:
    import re

    shown = set(re.findall(r"\{\{([a-z0-9_]+)\??\}\}", PAGE.read_text()))
    known = set(TOKENS) | {name.replace("bill_to_", "bill_from_", 1) for name in TOKENS}
    # `{{bill_to_name}}`-style mentions are fine: they are real names too.
    assert shown - known - set(TOKENS) == set()
