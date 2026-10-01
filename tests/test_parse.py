import pytest

import tablemd
from tablemd import Table, TablemdError, is_delimiter_row, parse, parse_one, split_row

SIMPLE = """\
| Name  | Qty | Price |
|:------|----:|:-----:|
| Apple |   3 |  1.50 |
| Pear  |  12 |  0.25 |
"""


def test_parse_simple_table():
    (t,) = parse(SIMPLE)
    assert t.header == ["Name", "Qty", "Price"]
    assert t.rows == [["Apple", "3", "1.50"], ["Pear", "12", "0.25"]]
    assert t.align == ["left", "right", "center"]
    assert t.shape == (2, 3)
    assert len(t) == 2


def test_parse_one_and_index():
    t = parse_one(SIMPLE)
    assert t.header[0] == "Name"
    with pytest.raises(TablemdError):
        parse_one("no tables here")
    with pytest.raises(TablemdError):
        parse_one(SIMPLE, index=1)


def test_no_outer_pipes():
    md = "a | b\n--|--\n1 | 2\n"
    (t,) = parse(md)
    assert t.header == ["a", "b"]
    assert t.rows == [["1", "2"]]


def test_single_column_table_requires_pipes():
    md = "| only |\n|------|\n| one  |\n"
    (t,) = parse(md)
    assert t.header == ["only"]
    assert t.rows == [["one"]]
    # A setext heading must NOT be mistaken for a table.
    assert parse("a | b\n---\n") == []


def test_escaped_pipe_and_backslashes():
    md = r"| a \| b | c |" + "\n|---|---|\n" + r"| x \\ | y \| z | C:\Users |" + "\n"
    (t,) = parse(md)
    assert t.header == ["a | b", "c"]
    # GFM: "\\" is a literal backslash, "\|" a literal pipe, other backslashes stay.
    assert t.rows == [["x \\", "y | z"]]
    assert split_row(r"| x \\ | y \| z | C:\Users |") == ["x \\", "y | z", "C:\\Users"]
    # An escaped backslash followed by a real pipe still splits.
    assert split_row(r"a \\| b") == ["a \\", "b"]


def test_bom_is_ignored():
    (t,) = parse("\ufeff| a | b |\n|---|---|\n| 1 | 2 |\n")
    assert t.header == ["a", "b"]
    assert t.rows == [["1", "2"]]


def test_trailing_escaped_pipe_is_content():
    cells = split_row(r"| a | b \|")
    assert cells == ["a", "b |"]


def test_ragged_rows_are_normalised():
    md = "| a | b | c |\n|---|---|---|\n| 1 |\n| 1 | 2 | 3 | 4 |\n"
    (t,) = parse(md)
    assert t.rows == [["1", "", ""], ["1", "2", "3"]]


def test_delimiter_wider_than_header_keeps_data():
    md = "| a | b |\n|---|---|---|\n| 1 | 2 | 3 |\n"
    (t,) = parse(md)
    assert t.header == ["a", "b", ""]
    assert t.rows == [["1", "2", "3"]]


def test_table_ends_at_blank_line_or_non_pipe_line():
    md = SIMPLE + "\nSome paragraph | with a pipe\n\n| x |\n|---|\n| 1 |\nplain line\n| ignored |\n"
    tables = parse(md)
    assert len(tables) == 2
    assert tables[1].rows == [["1"]]


def test_multiple_tables_in_document_order():
    md = "# T\n\n| a |\n|---|\n| 1 |\n\ntext\n\n| b |\n|---|\n| 2 |\n"
    tables = parse(md)
    assert [t.header for t in tables] == [["a"], ["b"]]


def test_fenced_code_blocks_are_skipped():
    md = "```\n| a |\n|---|\n| 1 |\n```\n\n~~~md\n| b |\n|---|\n~~~\n\n| c |\n|---|\n| 3 |\n"
    tables = parse(md)
    assert [t.header for t in tables] == [["c"]]


def test_blockquoted_and_indented_tables():
    md = "> | a | b |\n> |---|---|\n> | 1 | 2 |\n\n    | c |\n    |---|\n    | 3 |\n"
    tables = parse(md)
    assert tables[0].rows == [["1", "2"]]
    assert tables[1].header == ["c"]


def test_crlf_input():
    md = SIMPLE.replace("\n", "\r\n")
    (t,) = parse(md)
    assert t.rows[0] == ["Apple", "3", "1.50"]


def test_delimiter_row_detection():
    assert is_delimiter_row("|---|:--:|--:|:--|") == [None, "center", "right", "left"]
    assert is_delimiter_row("| - | - |") == [None, None]
    assert is_delimiter_row("| abc | --- |") is None
    assert is_delimiter_row("---") is None
    assert is_delimiter_row("| :: |") is None


def test_plain_option_strips_formatting():
    md = "| **Name** | Link |\n|---|---|\n| *x* | [t](http://e.com) |\n"
    (t,) = parse(md, plain=True)
    assert t.header == ["Name", "Link"]
    assert t.rows == [["x", "t"]]


def test_cjk_content_preserved():
    md = "| 產品 | 數量 |\n|---|---|\n| 香蕉 | 12 |\n"
    (t,) = parse(md)
    assert t.rows == [["香蕉", "12"]]


def test_header_only_table():
    md = "| a | b |\n|---|---|\n"
    (t,) = parse(md)
    assert t.header == ["a", "b"]
    assert t.rows == []


def test_table_constructor_normalises():
    t = Table(header=["a", "b"], rows=[["1"], ["1", "2", "3"]], align=["left"])
    assert t.rows == [["1", ""], ["1", "2"]]
    assert t.align == ["left", None]
    assert t.column("b") == ["", "2"]
    assert t.column(0) == ["1", "1"]


def test_version_is_exposed():
    assert tablemd.__version__
