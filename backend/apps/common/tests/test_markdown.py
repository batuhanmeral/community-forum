import pytest

from apps.common.markdown import _safe_href, render_markdown


class TestMarkdown:
    def test_empty(self):
        assert render_markdown("") == ""

    def test_bold(self):
        assert "<strong>bold</strong>" in render_markdown("**bold**")

    def test_link_gets_rel(self):
        out = render_markdown("[x](https://example.com)")
        assert 'rel="nofollow noopener noreferrer ugc"' in out

    def test_strips_script(self):
        out = render_markdown("<script>alert(1)</script>hello")
        assert "<script" not in out
        assert "hello" in out

    def test_strips_javascript_url(self):
        out = render_markdown("[x](javascript:alert(1))")
        assert "href" not in out

    def test_fenced_code(self):
        out = render_markdown("```\nx = 1\n```")
        assert "<pre>" in out and "<code>" in out

    def test_table(self):
        out = render_markdown("| a | b |\n|---|---|\n| 1 | 2 |")
        assert "<table>" in out and "<th>" in out

    def test_no_app_config_needed(self):
        """Importing render_markdown shouldn't require django apps loaded."""
        # The fact that this module imports cleanly is the test
        assert callable(render_markdown)

    def test_strips_arbitrary_classes(self):
        out = render_markdown('<span class="fixed inset-0 z-50">fake banner</span>')
        assert "class=" not in out
        assert "fake banner" in out

    def test_keeps_code_language_class(self):
        out = render_markdown("```python\nprint(1)\n```")
        assert 'class="language-python"' in out

    def test_drops_code_class_that_is_not_a_language(self):
        out = render_markdown('<code class="fixed inset-0">x</code>')
        assert "class=" not in out

    def test_drops_inline_images(self):
        out = render_markdown("![pixel](https://tracker.example/p.gif)")
        assert "<img" not in out
        assert "tracker.example" not in out

    def test_single_newline_is_a_line_break(self):
        assert "<br" in render_markdown("a\nb")

    def test_keeps_allowlisted_raw_html(self):
        assert "<sub>2</sub>" in render_markdown("H<sub>2</sub>O")

    def test_large_aligned_table_still_renders(self):
        text = "| a | b | c |\n|:-|:-:|-:|\n" + "| 1 | 2 | 3 |\n" * 300
        assert "<table>" in render_markdown(text)

    def test_reference_definitions_do_not_become_links(self):
        out = render_markdown("[a]: https://example.com\n\nsee [a]")
        assert "href" not in out

    def test_keeps_raw_html_with_a_few_attributes(self):
        out = render_markdown('<abbr title="HyperText">HTML</abbr>')
        assert '<abbr title="HyperText">HTML</abbr>' in out

    def test_many_attributed_raw_tags_render_as_text(self):
        out = render_markdown('<u title="x">' * 40 + "y")
        assert "&lt;u" in out

    def test_attributed_tags_inside_code_do_not_disable_raw_html(self):
        sample = "```html\n" + '<u title="x">\n' * 40 + "```\n\n"
        generics = "`HashMap<String, Vec<u8>>` " * 40
        out = render_markdown(sample + generics + "H<sub>2</sub>O")
        assert "<sub>2</sub>" in out

    def test_double_tilde_stays_literal(self):
        assert "~~gone~~" in render_markdown("~~gone~~")


@pytest.mark.parametrize("src", ["[a](//evil.com)", "[a](../x)", "[a](x/y)"])
def test_non_root_relative_href_is_dropped(src):
    assert "href" not in render_markdown(src)


@pytest.mark.parametrize(
    "src",
    [
        '<a href="/\\evil.com">a</a>',
        '<a href=" //evil.com">a</a>',
        '<a href="/&#9;/evil.com">a</a>',
    ],
)
def test_disguised_protocol_relative_href_is_dropped(src):
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


def test_links_carry_noreferrer():
    assert 'rel="nofollow noopener noreferrer ugc"' in render_markdown("[a](https://x.com)")


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

    def test_email_is_not_a_mention(self):
        assert "href" not in render_markdown("mail me at me@example.com")

    def test_code_is_left_alone(self):
        out = render_markdown("`@alice`\n\n```\n@bob\n```")
        assert "href" not in out

    def test_existing_link_is_not_nested(self):
        out = render_markdown("[ask @alice](https://example.com)")
        assert out.count("<a ") == 1
        assert 'href="https://example.com"' in out

    def test_mention_inside_emphasis(self):
        out = render_markdown("**@alice**")
        assert '<strong><a href="/u/alice"' in out
