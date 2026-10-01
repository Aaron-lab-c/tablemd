"""Text helpers: display width (CJK aware), inline-Markdown stripping, type coercion."""

from __future__ import annotations

import datetime
import html
import math
import re
import unicodedata
from typing import Any, List, Optional, Union

# --------------------------------------------------------------------------- #
# Display width
# --------------------------------------------------------------------------- #

_ZERO_WIDTH_CATEGORIES = {"Mn", "Me", "Cf"}


def display_width(text: str) -> int:
    """Return the number of terminal columns *text* occupies.

    East-Asian wide/fullwidth characters (Chinese, Japanese, Korean, fullwidth
    punctuation, most emoji) count as 2 columns; combining marks and format
    characters count as 0; everything else counts as 1. This is what makes a
    ``to_markdown()`` table line up in a monospace font even when it mixes
    中文 and ASCII.
    """
    width = 0
    for ch in text:
        if unicodedata.category(ch) in _ZERO_WIDTH_CATEGORIES:
            continue
        if unicodedata.east_asian_width(ch) in ("W", "F"):
            width += 2
        else:
            width += 1
    return width


def pad(text: str, width: int, align: Optional[str] = None) -> str:
    """Pad *text* with spaces to *width* display columns using *align*."""
    gap = width - display_width(text)
    if gap <= 0:
        return text
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


# --------------------------------------------------------------------------- #
# Inline Markdown stripping
# --------------------------------------------------------------------------- #

_CODE_SPAN_RE = re.compile(r"(`+)(.+?)\1", re.DOTALL)
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_REF_LINK_RE = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")
_AUTOLINK_RE = re.compile(r"<((?:https?|ftp|mailto):[^>\s]+)>")
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_HTML_TAG_RE = re.compile(
    r"</?(?:b|i|em|strong|code|kbd|sub|sup|u|s|del|ins|span|mark|small|big|tt|var|samp|abbr|a|font)\b[^>]*>",
    re.IGNORECASE,
)
_STRONG_RE = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", re.DOTALL)
_EM_STAR_RE = re.compile(r"\*(?=\S)(.+?)(?<=\S)\*", re.DOTALL)
_EM_UNDER_RE = re.compile(r"(?<!\w)_(?=\S)(.+?)(?<=\S)_(?!\w)", re.DOTALL)
_STRIKE_RE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~", re.DOTALL)
_BACKSLASH_ESCAPE_RE = re.compile(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~])")

_PLACEHOLDER = "\x00{}\x00"
_PLACEHOLDER_RE = re.compile("\x00(\\d+)\x00")


def strip_formatting(text: str) -> str:
    """Remove inline Markdown/HTML formatting from a table cell.

    ``**bold**`` -> ``bold``, ```` `code` ```` -> ``code``, ``[t](url)`` -> ``t``,
    ``![alt](src)`` -> ``alt``, ``~~x~~`` -> ``x``, ``<br>`` -> newline,
    simple HTML tags are dropped, HTML entities and backslash escapes are
    decoded. The result is what a human would *read* in a rendered table,
    which is usually what you want in a spreadsheet.
    """
    if not text:
        return text

    # 1. Protect code spans and backslash-escaped punctuation so they are left
    #    untouched by the emphasis/link passes below.
    stash: List[str] = []

    def _keep(value: str) -> str:
        stash.append(value)
        return _PLACEHOLDER.format(len(stash) - 1)

    text = _CODE_SPAN_RE.sub(lambda m: _keep(m.group(2).strip()), text)
    text = _BACKSLASH_ESCAPE_RE.sub(lambda m: _keep(m.group(1)), text)

    # 2. Links and images.
    text = _IMAGE_RE.sub(r"\1", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _REF_LINK_RE.sub(r"\1", text)
    text = _AUTOLINK_RE.sub(r"\1", text)

    # 3. HTML line breaks and tags.
    text = _BR_RE.sub("\n", text)
    text = _HTML_TAG_RE.sub("", text)

    # 4. Emphasis / strikethrough (repeat to handle nesting like ***x***).
    for _ in range(3):
        before = text
        text = _STRONG_RE.sub(r"\2", text)
        text = _EM_STAR_RE.sub(r"\1", text)
        text = _EM_UNDER_RE.sub(r"\1", text)
        text = _STRIKE_RE.sub(r"\1", text)
        if text == before:
            break

    # 5. HTML entities.
    text = html.unescape(text)

    # 6. Restore protected spans.
    text = _PLACEHOLDER_RE.sub(lambda m: stash[int(m.group(1))], text)
    return text.strip()


_BACKSLASH_BEFORE_SPECIAL_RE = re.compile(r"\\(?=[\\|])")


def escape_cell(text: str) -> str:
    """Make *text* safe to place inside a Markdown table cell.

    Pipes become ``\\|``; a backslash that would otherwise combine with a
    following pipe or backslash is doubled, so :func:`tablemd.split_row`
    returns exactly *text* again. Other backslashes (``C:\\Users``) are left
    alone because GFM already treats them literally.
    """
    text = _BACKSLASH_BEFORE_SPECIAL_RE.sub(r"\\\\", text)
    text = text.replace("|", "\\|")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if "\n" in text:
        text = text.replace("\n", "<br>")
    return text


# --------------------------------------------------------------------------- #
# Type coercion
# --------------------------------------------------------------------------- #

_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?$")
_THOUSANDS_RE = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?$")
_MAX_SAFE_DIGITS = 15  # beyond this Excel/JS lose precision -> keep as text

Scalar = Union[str, int, float, bool, None]


def coerce(value: str) -> Scalar:
    """Best-effort conversion of a cell string to a typed scalar.

    Conservative on purpose: strings that *look* numeric but are really
    identifiers (leading zeros such as ``007`` or ``0912345678``, or more than
    15 digits) stay strings. ``""`` becomes ``None``.
    """
    s = value.strip()
    if s == "":
        return None
    lowered = s.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False

    candidate = s
    if _THOUSANDS_RE.match(s):
        candidate = s.replace(",", "")

    if _INT_RE.match(candidate):
        digits = candidate.lstrip("+-")
        if len(digits) > 1 and digits.startswith("0"):
            return s  # identifier-like, keep leading zeros
        if len(digits) > _MAX_SAFE_DIGITS:
            return s
        return int(candidate)

    if _FLOAT_RE.match(candidate):
        try:
            number = float(candidate)
        except ValueError:  # pragma: no cover - regex should prevent this
            return value
        return number if math.isfinite(number) else s
    return value


def stringify(value: Any) -> str:
    """Turn an arbitrary scalar back into cell text."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer() and math.isfinite(value):
        return str(int(value))
    if isinstance(value, datetime.datetime):
        if value.time() == datetime.time(0) and value.tzinfo is None:
            return value.date().isoformat()  # Excel "date" cells
        return value.isoformat(sep=" ")
    if isinstance(value, (datetime.date, datetime.time)):
        return value.isoformat()
    return str(value)
