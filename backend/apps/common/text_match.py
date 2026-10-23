import html
import re
import unicodedata
from urllib.parse import unquote, urlsplit

from django.utils.html import strip_tags

_HREF = re.compile(r'href="([^"]*)"')
# Hangul fillers are letters to `isalnum()` but render blank, so they would split a word unseen.
_BLANK_LETTERS = {"\u115f", "\u1160", "\u3164", "\uffa0"}


def normalize_for_match(text: str) -> str:
    """Fold case, accents, invisible characters and punctuation so filters can't be dodged by styling."""
    folded = unicodedata.normalize("NFKD", text.casefold()).replace("ı", "i").replace("@", "a")
    kept = []
    for ch in folded:
        category = unicodedata.category(ch)
        if category[0] == "M" or category == "Cf" or ch in _BLANK_LETTERS:
            continue
        if ch.isalnum():
            kept.append(ch)
        elif ch.isspace():
            kept.append(" ")
        # Punctuation is dropped, not spaced, so "b.a.d" and "b**a**d" still read as "bad".
    return " ".join("".join(kept).split())


def html_text(rendered: str) -> str:
    """Visible text of rendered markdown: entities and inline markup resolved."""
    return html.unescape(strip_tags(rendered))


def url_forms(url: str) -> list[str]:
    """A URL as written, percent-decoded, and with a punycode host decoded."""
    if not url:
        return []
    decoded = unquote(url)
    forms = [url, decoded]
    try:
        host = urlsplit(decoded).hostname or ""
        forms.append(host.encode("ascii").decode("idna"))
    except (UnicodeError, ValueError):
        pass
    return forms


def link_targets(rendered: str) -> list[str]:
    """Decoded hrefs of rendered markdown; `html_text` drops them, yet they are where spam points."""
    return [form for href in _HREF.findall(rendered) for form in url_forms(html.unescape(href))]
