"""Convert legacy rich HTML (e.g. Apple Pages exports) to plain or display-safe text."""
import html
import re

from django.utils.html import strip_tags

_STYLE_SCRIPT_RE = re.compile(
    r'<(?:style|script)[^>]*>.*?</(?:style|script)>',
    re.IGNORECASE | re.DOTALL,
)
_WHITESPACE_RE = re.compile(r'\s+')


def strip_rich_html_blocks(value):
    """Remove embedded style/script blocks from HTML fragments."""
    if not value:
        return ''
    return _STYLE_SCRIPT_RE.sub('', value).strip()


def rich_html_to_plain_text(value):
    """Plain text from HTML, without CSS/JS leakage from pasted exports."""
    cleaned = strip_rich_html_blocks(value)
    text = strip_tags(cleaned)
    text = html.unescape(text)
    return _WHITESPACE_RE.sub(' ', text).strip()


def rich_html_for_display(value):
    """HTML safe for public pages: strip style/script, keep other markup."""
    return strip_rich_html_blocks(value)
