import pytest

from apps.common.markdown import _safe_href, render_markdown


class TestMarkdown:
    def test_empty(self):
        assert render_markdown("") == ""

    @pytest.mark.parametrize(
        "src, expected_fragments",
        [
            pytest.param("**bold**", ("<strong>bold</strong>",), id="bold"),
            pytest.param("```\nx = 1\n```", ("<pre>", "<code>"), id="fenced-code"),
            pytest.param("| a | b |\n|---|---|\n| 1 | 2 |", ("<table>", "<th>"), id="table"),
            pytest.param("a\nb", ("<br",), id="single-newline"),
            pytest.param("H<sub>2</sub>O", ("<sub>2</sub>",), id="subscript"),
            pytest.param(
                '<abbr title="HyperText">HTML</abbr>',
                ('<abbr title="HyperText">HTML</abbr>',),
                id="html-attribute",
            ),
            pytest.param(
                "```python\nprint(1)\n```", ('class="language-python"',), id="code-language"
            ),
            pytest.param("~~gone~~", ("~~gone~~",), id="literal-double-tilde"),
            pytest.param(
                "| a | b | c |\n|:-|:-:|-:|\n" + "| 1 | 2 | 3 |\n" * 300,
                ("<table>",),
                id="large-aligned-table",
            ),
        ],
    )
    def test_allowed_markup_renders(self, src, expected_fragments):
        out = render_markdown(src)
        for fragment in expected_fragments:
            assert fragment in out

    @pytest.mark.parametrize(
        "src, absent, present",
        [
            pytest.param("<script>alert(1)</script>hello", ("<script",), ("hello",), id="script"),
            pytest.param(
                '<span class="fixed inset-0 z-50">fake banner</span>',
                ("class=",),
                ("fake banner",),
                id="arbitrary-span-class",
            ),
            pytest.param(
                '<code class="fixed inset-0">x</code>',
                ("class=",),
                (),
                id="non-language-code-class",
            ),
            pytest.param(
                "![pixel](https://tracker.example/p.gif)",
                ("<img", "tracker.example"),
                (),
                id="inline-image",
            ),
        ],
    )
    def test_unsafe_markup_is_stripped(self, src, absent, present):
        out = render_markdown(src)
        for fragment in absent:
            assert fragment not in out
        for fragment in present:
            assert fragment in out

    def test_reference_definitions_do_not_become_links(self):
        out = render_markdown("[a]: https://example.com\n\nsee [a]")
        assert "href" not in out

    def test_many_attributed_raw_tags_render_as_text(self):
        out = render_markdown('<u title="x">' * 40 + "y")
        assert "&lt;u" in out

    def test_attributed_tags_inside_code_do_not_disable_raw_html(self):
        sample = "```html\n" + '<u title="x">\n' * 40 + "```\n\n"
        generics = "`HashMap<String, Vec<u8>>` " * 40
        out = render_markdown(sample + generics + "H<sub>2</sub>O")
        assert "<sub>2</sub>" in out


@pytest.mark.parametrize(
    "src",
    [
        pytest.param("[x](javascript:alert(1))", id="javascript"),
        pytest.param("[a](//evil.com)", id="protocol-relative"),
        pytest.param("[a](../x)", id="parent-relative"),
        pytest.param("[a](x/y)", id="relative-path"),
        pytest.param('<a href="/\\evil.com">a</a>', id="slash-backslash"),
        pytest.param('<a href=" //evil.com">a</a>', id="leading-space"),
        pytest.param('<a href="/&#9;/evil.com">a</a>', id="tab-entity"),
    ],
)
def test_disallowed_href_is_dropped(src):
    assert "href" not in render_markdown(src)


@pytest.mark.parametrize(
    "src,href",
    [
        ("[a](/c/python)", "/c/python"),
        ("[a](#comment-5)", "#comment-5"),
        ("[a](https://x.com)", "https://x.com"),
        ("[a](mailto:a@x.com)", "mailto:a@x.com"),
    ],
)
def test_allowed_hrefs_are_kept(src, href):
    assert f'href="{href}"' in render_markdown(src)


def test_external_link_gets_rel():
    assert 'rel="nofollow noopener noreferrer ugc"' in render_markdown("[x](https://example.com)")


def test_safe_href_rejects_schemes_outside_the_allowlist():
    # nh3 does not re-check url_schemes on the value the attribute filter returns.
    assert _safe_href("java\tscript:alert(1)") is None


class TestMentionLinks:
    def test_mention_links_to_profile(self):
        out = render_markdown("thanks @alice_1!")
        assert '<a href="/u/alice_1" rel="nofollow noopener noreferrer ugc">@alice_1</a>!' in out

    def test_several_mentions_in_one_line(self):
        out = render_markdown("@bob and @carol")
        assert 'href="/u/bob"' in out
        assert 'href="/u/carol"' in out

    @pytest.mark.parametrize(
        "src",
        [
            pytest.param("mail me at me@example.com", id="email"),
            pytest.param("`@alice`\n\n```\n@bob\n```", id="inline-and-fenced-code"),
        ],
    )
    def test_non_mention_text_stays_unlinked(self, src):
        assert "href" not in render_markdown(src)

    def test_existing_link_is_not_nested(self):
        out = render_markdown("[ask @alice](https://example.com)")
        assert out.count("<a ") == 1
        assert 'href="https://example.com"' in out

    def test_mention_inside_emphasis(self):
        out = render_markdown("**@alice**")
        assert '<strong><a href="/u/alice"' in out
