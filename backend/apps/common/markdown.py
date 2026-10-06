import re
from html import escape

import nh3
from markdown_it import MarkdownIt
from markdown_it.rules_block import table as _table_rule

# Tables pad short rows with empty cells; one document may only buy this many table tokens.
MAX_TABLE_TOKENS = 30_000
# Sanitized HTML larger than this multiple of its source is an amplification attack.
MAX_HTML_EXPANSION = 10
MIN_HTML_LIMIT = 10_000
# Unclosed raw tags with distinct attributes are re-opened at every <p> by the HTML parser.
MAX_RAW_TAGS_WITH_ATTRIBUTES = 32
# Counts every start tag that is not a bare `<name>` / `<name />` (HTML whitespace only).
_RAW_TAG_WITH_ATTRIBUTES = re.compile(r"<[A-Za-z](?![A-Za-z0-9]*[\t\n\f\r ]*/?>)")


def _bounded_table(state, start_line, end_line, silent):
    used = state.env.get("table_tokens", 0)
    if used >= MAX_TABLE_TOKENS:
        return False
    before = len(state.tokens)
    matched = _table_rule(state, start_line, end_line, silent)
    if matched and not silent:
        state.env["table_tokens"] = used + len(state.tokens) - before
    return matched


def _parser(allow_raw_html: bool) -> MarkdownIt:
    # CommonMark parsing is linear in input size; Python-Markdown backtracked cubically.
    # Typographer stays off: its smart quotes are quadratic on quote runs.
    # Reference definitions are off: one long URL or title gets copied into every `[label]`.
    md = (
        MarkdownIt("commonmark", {"breaks": True, "html": allow_raw_html})
        .enable("table")
        .disable("reference")
    )
    md.block.ruler.at("table", _bounded_table, {"alt": ["paragraph", "reference"]})
    return md


_MD = _parser(allow_raw_html=True)
_MD_NO_RAW_HTML = _parser(allow_raw_html=False)

_ALLOWED_TAGS = {
    "a",
    "abbr",
    "b",
    "blockquote",
    "br",
    "code",
    "em",
    "hr",
    "i",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "sub",
    "sup",
    "u",
    "ul",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "del",
    "ins",
}
_ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "code": {"class"},
}
_LANGUAGE_CLASS = re.compile(r"^language-[A-Za-z0-9_+-]+$")


def _keep_safe_attribute(tag: str, attr: str, value: str) -> str | None:
    # Arbitrary classes would let users restyle the app (e.g. full-screen fake banners).
    if attr == "class":
        return value if tag == "code" and _LANGUAGE_CLASS.match(value) else None
    return value


def render_markdown(text: str) -> str:
    """Render markdown to sanitized HTML; safe for direct injection in templates."""
    if not text:
        return ""
    raw_tags = len(_RAW_TAG_WITH_ATTRIBUTES.findall(text))
    md = _MD if raw_tags <= MAX_RAW_TAGS_WITH_ATTRIBUTES else _MD_NO_RAW_HTML
    html = nh3.clean(
        md.render(text),
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        attribute_filter=_keep_safe_attribute,
        url_schemes={"http", "https", "mailto"},
        link_rel="nofollow noopener ugc",
    )
    if len(html) > max(MAX_HTML_EXPANSION * len(text), MIN_HTML_LIMIT):
        return f"<p>{escape(text)}</p>"
    return html
