import pytest

from apps.common.markdown import render_markdown
from apps.common.text_match import html_text, link_targets, normalize_for_match, url_forms


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("SPAMMY", "spammy"),
        ("s.p.a.m.m.y", "spammy"),
        ("s**pa**mmy", "spammy"),
        ("sp​ammy", "spammy"),
        ("ｓｐａｍｍｙ", "spammy"),
        ("spämmy", "spammy"),
        ("IŞIK ışık İyi", "isik isik iyi"),
        ("buy   now\n\tplease", "buy now please"),
    ],
)
def test_normalize_for_match(raw, expected):
    assert normalize_for_match(raw) == expected


def test_html_text_resolves_entities_and_tags():
    assert html_text("<p>sp&#97;<strong>m</strong>my &amp; co</p>") == "spammy & co"


@pytest.mark.parametrize("raw", ["spㅤammy", "sp@mmy"])
def test_normalize_folds_blank_letters_and_at_sign(raw):
    assert normalize_for_match(raw) == "spammy"


def test_url_forms_decode_percent_and_punycode():
    assert "https://spammy.example" in url_forms("https://%73pammy.example")
    assert "spämmy.example" in url_forms("https://xn--spmmy-hra.example")
    assert url_forms("") == []
    assert url_forms("http://[::1") == ["http://[::1", "http://[::1"]


def test_link_targets_decode_hidden_link_destinations():
    for body in ("[click](https://sp&#97;mmy.example)", "[click](https://%73pammy.example)"):
        assert "https://spammy.example" in link_targets(render_markdown(body))
