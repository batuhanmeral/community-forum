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
        assert "javascript" not in out

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
