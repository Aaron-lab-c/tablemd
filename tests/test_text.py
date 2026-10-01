import pytest

from tablemd import coerce, display_width, strip_formatting
from tablemd._text import escape_cell, pad, stringify


@pytest.mark.parametrize(
    "text,width",
    [
        ("abc", 3),
        ("中文", 4),
        ("a中b", 4),
        ("", 0),
        ("ｆｕｌｌ", 8),  # fullwidth latin
        ("é", 1),  # combining accent is zero width
    ],
)
def test_display_width(text, width):
    assert display_width(text) == width


def test_pad_alignments():
    assert pad("ab", 5) == "ab   "
    assert pad("ab", 5, "right") == "   ab"
    assert pad("ab", 5, "center") == " ab  "
    assert pad("中", 4, "right") == "  中"
    assert pad("toolong", 3) == "toolong"


@pytest.mark.parametrize(
    "raw,plain",
    [
        ("**bold**", "bold"),
        ("__bold__", "bold"),
        ("*em*", "em"),
        ("_em_", "em"),
        ("***both***", "both"),
        ("~~gone~~", "gone"),
        ("`code`", "code"),
        ("``co`de``", "co`de"),
        ("`**not bold**`", "**not bold**"),
        ("[text](http://x.y)", "text"),
        ("[text][ref]", "text"),
        ("![alt](img.png)", "alt"),
        ("<https://a.b>", "https://a.b"),
        ("line<br>break", "line\nbreak"),
        ("line<br/>break", "line\nbreak"),
        ("line<br />break", "line\nbreak"),
        ("<b>x</b> <span class='c'>y</span>", "x y"),
        ("a &amp; b &lt; c", "a & b < c"),
        (r"\*literal\*", "*literal*"),
        ("snake_case_name", "snake_case_name"),
        ("2 * 3 * 4", "2 * 3 * 4"),
        ("a < b", "a < b"),
        ("", ""),
        ("plain", "plain"),
    ],
)
def test_strip_formatting(raw, plain):
    assert strip_formatting(raw) == plain


def test_escape_cell():
    assert escape_cell("a|b") == "a\\|b"
    assert escape_cell("l1\nl2") == "l1<br>l2"
    assert escape_cell("l1\r\nl2") == "l1<br>l2"
    assert escape_cell("C:\\Users") == "C:\\Users"  # harmless backslash untouched
    assert escape_cell("x\\|y") == "x\\\\\\|y"  # backslash before pipe is doubled
    assert escape_cell("a\\\\b") == "a\\\\\\b"  # first of two backslashes doubled


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("12", 12),
        ("-7", -7),
        ("+3", 3),
        ("1.5", 1.5),
        (".5", 0.5),
        ("1e3", 1000.0),
        ("1,234", 1234),
        ("1,234.5", 1234.5),
        ("1,23", "1,23"),
        ("007", "007"),
        ("0", 0),
        ("0912345678", "0912345678"),
        ("1234567890123456", "1234567890123456"),
        ("true", True),
        ("False", False),
        ("", None),
        ("   ", None),
        ("12%", "12%"),
        ("abc", "abc"),
        ("1.2.3", "1.2.3"),
        ("N/A", "N/A"),
        ("1e400", "1e400"),
        ("-1e999", "-1e999"),
        ("NaN", "NaN"),
        ("Infinity", "Infinity"),
        (" 007 ", "007"),
        ("2024-01-01", "2024-01-01"),
    ],
)
def test_coerce(raw, expected):
    result = coerce(raw)
    assert result == expected
    assert type(result) is type(expected)


def test_stringify():
    import datetime

    assert stringify(None) == ""
    assert stringify(True) == "true"
    assert stringify(3.0) == "3"
    assert stringify(2.5) == "2.5"
    assert stringify(7) == "7"
    assert stringify("x") == "x"
    assert stringify(float("inf")) == "inf"
    assert stringify(datetime.datetime(2024, 1, 1)) == "2024-01-01"
    assert stringify(datetime.datetime(2024, 1, 1, 9, 30)) == "2024-01-01 09:30:00"
    assert stringify(datetime.date(2024, 1, 1)) == "2024-01-01"
    assert stringify(datetime.time(8, 5)) == "08:05:00"
