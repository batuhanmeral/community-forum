import re

import markdown as _markdown
import nh3

_MD = _markdown.Markdown(
    extensions=["fenced_code", "tables", "nl2br", "sane_lists", "smarty"],
    output_format="html",
)

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
    _MD.reset()
    html = _MD.convert(text)
    return nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        attribute_filter=_keep_safe_attribute,
        url_schemes={"http", "https", "mailto"},
        link_rel="nofollow noopener ugc",
    )
