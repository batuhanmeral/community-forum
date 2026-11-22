from apps.common.markdown import render_markdown


class TestSpoilerMarkdown:
    def test_spoiler_becomes_class_span(self):
        assert render_markdown("see >!the twist!< here") == (
            '<p>see <span class="spoiler">the twist</span> here</p>\n'
        )

    def test_inline_markup_inside_spoiler(self):
        out = render_markdown("x >!**bold** and @bob!<")
        assert '<span class="spoiler"><strong>bold</strong> and <a href="/u/bob"' in out

    def test_unterminated_or_empty_marker_stays_text(self):
        assert "spoiler" not in render_markdown(">!never closed")
        assert "spoiler" not in render_markdown(">!!<")

    def test_code_span_is_not_a_spoiler(self):
        assert "spoiler" not in render_markdown("`>!x!<`")

    def test_spoiler_text_is_escaped(self):
        out = render_markdown(">!<script>alert(1)</script>!<")
        assert "<script" not in out

    def test_user_cannot_pick_other_classes_or_attributes(self):
        out = render_markdown('<span class="spoiler evil" style="position:fixed">x</span>')
        assert "evil" not in out and "style" not in out
        out = render_markdown('<span class="banner">x</span>')
        assert "banner" not in out
        out = render_markdown('<div class="spoiler">x</div>')
        assert "<div" not in out

    def test_raw_span_with_exact_class_is_allowed_but_harmless(self):
        out = render_markdown('<span class="spoiler">x</span>')
        assert '<span class="spoiler">x</span>' in out

    def test_other_tags_still_cannot_carry_the_class(self):
        assert "spoiler" not in render_markdown('<a class="spoiler" href="/x">x</a>')

    def test_marker_at_line_start_is_a_spoiler_not_a_quote(self):
        assert render_markdown(">!x!<") == '<p><span class="spoiler">x</span></p>\n'
        assert render_markdown("   >!x!< tail") == ('<p><span class="spoiler">x</span> tail</p>\n')
        out = render_markdown("intro\n>!the twist!<")
        assert "<blockquote>" not in out and '<span class="spoiler">the twist</span>' in out

    def test_line_start_odd_cases_stay_safe(self):
        # Inside a real quote the marker is still a spoiler.
        out = render_markdown("> >!x!<")
        assert out.startswith("<blockquote>") and '<span class="spoiler">x</span>' in out
        # Unterminated or closed on a later line: an ordinary quote, as before.
        assert render_markdown(">!never closed").startswith("<blockquote>")
        assert render_markdown(">!x\nclosed!<").startswith("<blockquote>")
        assert render_markdown(">!!<").startswith("<blockquote>")
        out = render_markdown(">!<script>alert(1)</script>!<")
        assert "<script" not in out


def test_unclosed_spoiler_openers_search_for_a_close_once(monkeypatch):
    """Each `>!` used to rescan to the end for `!<`: quadratic on many unclosed openers."""
    from apps.common import markdown

    calls = []
    real = markdown._find_close

    def counting(src, start):
        calls.append(start)
        return real(src, start)

    monkeypatch.setattr(markdown, "_find_close", counting)
    out = render_markdown("x " + ">!a " * 5_000)
    assert "spoiler" not in out
    assert len(calls) <= 2
    calls.clear()
    out = render_markdown("x " + ">!a " * 2_000 + ">!b!< and >!c!<")
    assert out.count('class="spoiler"') == 2
    assert len(calls) <= 4


class TestSpoilerAfterAQuote:
    def test_quote_continuation_line_is_a_spoiler(self):
        # The quote's paragraph may lazily continue onto the line; the text stays hidden.
        out = render_markdown("> quote\n>!secret!<")
        assert out.startswith("<blockquote>")
        assert '<span class="spoiler">secret</span>' in out
        assert "!secret" not in out

    def test_nested_quote_continuation(self):
        out = render_markdown("> > a\n> >!secret!<")
        assert '<span class="spoiler">secret</span>' in out and "!secret" not in out

    def test_ordinary_continuations_are_unchanged(self):
        assert render_markdown("> a\n> b") == "<blockquote>\n<p>a<br>\nb</p>\n</blockquote>\n"
        out = render_markdown("> a\n>!not closed")
        assert out.startswith("<blockquote>") and "spoiler" not in out
