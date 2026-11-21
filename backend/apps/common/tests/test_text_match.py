import pytest

from apps.common.markdown import render_markdown
from apps.common.text_match import html_text, link_targets, normalize_for_match, url_forms


@pytest.mark.parametrize(
    "raw, expected",
    [
        pytest.param("SPAMMY", "spammy", id="uppercase"),
        pytest.param("s.p.a.m.m.y", "spammy", id="dots"),
        pytest.param("s**pa**mmy", "spammy", id="markdown"),
        pytest.param("sp\u200bammy", "spammy", id="zero-width-space"),
        pytest.param("ｓｐａｍｍｙ", "spammy", id="fullwidth"),
        pytest.param("spämmy", "spammy", id="accent"),
        pytest.param("IŞIK ışık İyi", "isik isik iyi", id="turkish-i"),
        pytest.param("buy   now\n\tplease", "buy now please", id="whitespace"),
        pytest.param("spㅤammy", "spammy", id="hangul-filler"),
        pytest.param("sp@mmy", "spammy", id="at-sign"),
    ],
)
def test_normalize_for_match(raw, expected):
    assert normalize_for_match(raw) == expected


def test_html_text_resolves_entities_and_tags():
    assert html_text("<p>sp&#97;<strong>m</strong>my &amp; co</p>") == "spammy & co"


def test_url_forms_decode_percent_and_punycode():
    assert "https://spammy.example" in url_forms("https://%73pammy.example")
    assert "spämmy.example" in url_forms("https://xn--spmmy-hra.example")
    assert url_forms("") == []
    assert url_forms("http://[::1") == ["http://[::1", "http://[::1"]


def test_link_targets_decode_hidden_link_destinations():
    for body in ("[click](https://sp&#97;mmy.example)", "[click](https://%73pammy.example)"):
        assert "https://spammy.example" in link_targets(render_markdown(body))
