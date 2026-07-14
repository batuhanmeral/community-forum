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
