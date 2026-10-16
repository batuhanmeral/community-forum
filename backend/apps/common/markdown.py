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
_URL_SCHEMES = {"http", "https", "mailto"}
_URL_SCHEME = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*):")
_URL_IGNORED_CHARS = re.compile(r"[\t\n\r]")
_URL_LEADING_JUNK = "".join(map(chr, range(0x21)))


def _safe_href(value: str) -> str | None:
    # Browsers drop these characters before parsing, so `/\t/host` would still mean `//host`.
    href = _URL_IGNORED_CHARS.sub("", value).lstrip(_URL_LEADING_JUNK)
    if href.startswith("#"):
        return href
    scheme = _URL_SCHEME.match(href)
    if scheme:
        # nh3 checks url_schemes before this filter, not on the value returned from it.
        return href if scheme.group(1).lower() in _URL_SCHEMES else None
    # `//host` and `/\host` leave the site; other relative paths resolve per page.
    if href.startswith("/") and href[1:2] not in ("/", "\\"):
        return href
    return None


def _keep_safe_attribute(tag: str, attr: str, value: str) -> str | None:
    # Arbitrary classes would let users restyle the app (e.g. full-screen fake banners).
    if attr == "class":
        return value if tag == "code" and _LANGUAGE_CLASS.match(value) else None
    if tag == "a" and attr == "href":
        return _safe_href(value)
    return value


def _count_raw_tags_with_attributes(tokens) -> int:
    # Only html_block/html_inline reach the HTML parser unescaped; code samples must not count.
    raw_html = [t.content for t in tokens if t.type == "html_block"]
    raw_html += [
        child.content
        for t in tokens
        if t.type == "inline"
        for child in t.children or ()
        if child.type == "html_inline"
    ]
    return sum(len(_RAW_TAG_WITH_ATTRIBUTES.findall(chunk)) for chunk in raw_html)


def render_markdown(text: str) -> str:
    """Render markdown to sanitized HTML; safe for direct injection in templates."""
    if not text:
        return ""
    env = {}
    tokens = _MD.parse(text, env)
    if _count_raw_tags_with_attributes(tokens) <= MAX_RAW_TAGS_WITH_ATTRIBUTES:
        rendered = _MD.renderer.render(tokens, _MD.options, env)
    else:
        rendered = _MD_NO_RAW_HTML.render(text)
    html = nh3.clean(
        rendered,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        attribute_filter=_keep_safe_attribute,
        url_schemes=_URL_SCHEMES,
        link_rel="nofollow noopener noreferrer ugc",
    )
    if len(html) > max(MAX_HTML_EXPANSION * len(text), MIN_HTML_LIMIT):
        return "<p>" + escape(text).replace("\n", "<br>\n") + "</p>"
    return html
