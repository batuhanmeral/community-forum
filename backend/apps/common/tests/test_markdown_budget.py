import time
from itertools import islice, product

import pytest

from apps.common.markdown import render_markdown

# Largest body the API accepts (post body and preview cap).
MAX_BODY_CHARS = 40_000
BUDGET_SECONDS = 2.0
MAX_EXPANSION = 10

# Short rows get padded to the header's width: ~1.4 k chars become 65 k empty cells.
PADDED_TABLE = "|" + "a|" * 181 + "\n|" + "-|" * 181 + "\n" + "x\n" * 362 + "\n"

PATHOLOGICAL_PATTERNS = {
    "backticks": "`",
    "double-backticks": "``",
    "backtick-word": "`a ",
    "backtick-runs": "````````a",
    "open-brackets": "[",
    "image-openers": "![",
    "link-openers": "[a](",
    "double-quotes": '"',
    "single-quotes": "'",
    "nested-ordered-lists": "1. ",
    "emphasis": "*a",
    "html-openers": "<a ",
    "backslashes": "\\",
    "padded-tables": PADDED_TABLE,
}

AMPLIFYING_INPUTS = {
    "padded-table": PADDED_TABLE,
    "padded-tables": PADDED_TABLE * 30,
    "reference-url": "[a]: https://e.x/" + "a" * 20_000 + "\n\n" + "[a]x" * 5_000,
    "reference-title": '[a]: https://e.x "' + "t" * 10_000 + '"\n\n' + "[a]x" * 7_000,
}


# The HTML parser re-opens every unclosed formatting tag at each new <p>; distinct
# attributes defeat its dedup, so 2 000 such tags cost 2 000 elements per paragraph.
# Python's \s matches these, HTML does not: they form attribute names, not separators.
NON_HTML_WHITESPACE = "\x0b\x1c\x1d\x1e\x1f\x85\xa0"
REOPENED_FORMATTING_INPUTS = {
    "attributed-bold-tags": "".join(f"<b x={i}>" for i in range(2_000)) + "<p>a" * 20_000,
    "slash-attributed-tags": "".join(f"<b/x={i}>" for i in range(2_000)) + "<p>a" * 20_000,
    "html-block-underlines": "<div><p>\n"
    + "".join(f"<u title={i}>" for i in range(1_000))
    + "<p>a" * 20_000,
    "lt-attribute-names": "<div><p>\n"
    + "".join(f"<u <{i}>" for i in range(2_000))
    + "<p>a" * 20_000,
    "non-html-whitespace-attribute-names": "<div><p>\n"
    + "".join(
        f"<b {''.join(name)}>" for name in islice(product(NON_HTML_WHITESPACE, repeat=4), 1_500)
    )
    + "<p>a" * 20_000,
}

PATHOLOGICAL_INPUTS = {
    **{name: pattern * MAX_BODY_CHARS for name, pattern in PATHOLOGICAL_PATTERNS.items()},
    **REOPENED_FORMATTING_INPUTS,
}


@pytest.mark.parametrize("text", PATHOLOGICAL_INPUTS.values(), ids=PATHOLOGICAL_INPUTS.keys())
def test_pathological_input_renders_within_budget(text):
    text = text[:MAX_BODY_CHARS]
    started = time.perf_counter()
    render_markdown(text)
    assert time.perf_counter() - started < BUDGET_SECONDS


@pytest.mark.parametrize("text", AMPLIFYING_INPUTS.values(), ids=AMPLIFYING_INPUTS.keys())
def test_output_stays_proportional_to_input(text):
    text = text[:MAX_BODY_CHARS]
    assert len(render_markdown(text)) <= MAX_EXPANSION * len(text)


def test_amplifying_input_falls_back_to_escaped_source():
    out = render_markdown(PADDED_TABLE)
    assert "<table" not in out
    assert "|a|a|" in out
