from apps.common.markdown import render_markdown


class TestMarkdown:
    def test_empty(self):
        assert render_markdown("") == ""

    def test_bold(self):
        assert "<strong>bold</strong>" in render_markdown("**bold**")

    def test_link_gets_rel(self):
        out = render_markdown("[x](https://example.com)")
        assert "nofollow" in out

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
