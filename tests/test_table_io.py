import json

import pytest

import tablemd
from tablemd import Table, TablemdError, convert, parse_one, unique_headers

MD = """\
| Name  | Qty | Price |
|:------|----:|:-----:|
| Apple |   3 |  1.50 |
| 香蕉  |  12 |  0.25 |
"""


@pytest.fixture
def table():
    return parse_one(MD)


# ---------------------------------------------------------------- Markdown --

def test_to_markdown_pretty_aligns_cjk(table):
    out = table.to_markdown()
    lines = out.splitlines()
    # Every line has the same display width when CJK counts as 2 columns.
    widths = {tablemd.display_width(line) for line in lines}
    assert len(widths) == 1
    assert lines[1] == "| :---- | --: | :---: |"
    assert "| 香蕉  |  12 | 0.25  |" in out


def test_to_markdown_compact(table):
    out = table.to_markdown(pretty=False)
    assert out.splitlines()[0] == "| Name | Qty | Price |"
    assert out.splitlines()[1] == "| :-- | --: | :-: |"


def test_markdown_round_trip_escapes_pipes_and_newlines():
    t = Table(header=["a|b", "c"], rows=[["x\ny", "p|q"]])
    md = t.to_markdown()
    back = parse_one(md)
    assert back.header == ["a|b", "c"]
    assert back.rows == [["x<br>y", "p|q"]]
    assert back.plain().rows == [["x\ny", "p|q"]]


@pytest.mark.parametrize(
    "cell",
    ["x\\|y", "C:\\Users\\me", "a\\\\b", "\\\\|", "trailing\\", "\\|\\|", "\\\\\\|", "plain|pipe"],
)
def test_markdown_round_trip_backslashes(cell):
    t = Table(header=["v"], rows=[[cell]])
    assert parse_one(t.to_markdown()).rows == [[cell]]
    assert parse_one(t.to_markdown(pretty=False)).rows == [[cell]]


def test_str_is_markdown(table):
    assert str(table) == table.to_markdown()
    assert "Table(ncols=3, nrows=2" in repr(table)


# --------------------------------------------------------------------- CSV --

def test_to_csv_text_and_file(table, tmp_path):
    text = table.to_csv()
    assert text == "Name,Qty,Price\nApple,3,1.50\n香蕉,12,0.25\n"
    path = tmp_path / "t.csv"
    assert table.to_csv(path, encoding="utf-8-sig") is None
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    back = tablemd.read_csv(path)
    assert back.rows == table.rows


def test_to_tsv_and_quoting():
    t = Table(header=["a", "b"], rows=[["has,comma", 'has "quote"']])
    assert t.to_csv() == 'a,b\n"has,comma","has ""quote"""\n'
    assert t.to_tsv() == 'a\tb\nhas,comma\t"has ""quote"""\n'


def test_from_csv_sniffs_delimiter():
    assert tablemd.from_csv("a;b\n1;2\n").rows == [["1", "2"]]
    assert tablemd.from_csv("a\tb\n1\t2\n").rows == [["1", "2"]]
    assert tablemd.from_csv("a,b\n1,2\n\n\n").rows == [["1", "2"]]
    t = tablemd.from_csv("1,2\n3,4\n", header=False)
    assert t.header == ["col_1", "col_2"] and t.nrows == 2
    with pytest.raises(TablemdError):
        tablemd.from_csv("   ")


def test_from_csv_ragged_keeps_data():
    t = tablemd.from_csv("a,b\n1,2,3\n")
    assert t.header == ["a", "b", ""]
    assert t.rows == [["1", "2", "3"]]


# -------------------------------------------------------------------- JSON --

def test_to_json_records_with_types(table):
    data = json.loads(table.to_json())
    assert data == [
        {"Name": "Apple", "Qty": 3, "Price": 1.5},
        {"Name": "香蕉", "Qty": 12, "Price": 0.25},
    ]
    raw = json.loads(table.to_json(infer_types=False, indent=None))
    assert raw[0]["Qty"] == "3"


def test_to_json_split_and_file(table, tmp_path):
    data = json.loads(table.to_json(orient="split"))
    assert data["columns"] == ["Name", "Qty", "Price"]
    assert data["data"][1] == ["香蕉", 12, 0.25]
    path = tmp_path / "t.json"
    table.to_json(path, infer_types=False)
    assert tablemd.read_json(path).rows == table.rows
    table.to_json(path)  # typed: "1.50" comes back as 1.5 -> "1.5"
    assert tablemd.read_json(path).rows[0] == ["Apple", "3", "1.5"]
    with pytest.raises(TablemdError):
        table.to_json(orient="bogus")


def test_from_json_shapes():
    recs = tablemd.from_json('[{"a": 1, "b": null}, {"a": 2, "c": true}]')
    assert recs.header == ["a", "b", "c"]
    assert recs.rows == [["1", "", ""], ["2", "", "true"]]
    rows = tablemd.from_json([["a", "b"], [1, 2]])
    assert rows.header == ["a", "b"] and rows.rows == [["1", "2"]]
    split = tablemd.from_json({"columns": ["x"], "data": [[1.0]]})
    assert split.rows == [["1"]]
    with pytest.raises(TablemdError):
        tablemd.from_json("[]")
    with pytest.raises(TablemdError):
        tablemd.from_json('{"nope": 1}')


def test_to_dicts_and_unique_headers():
    t = Table(header=["a", "", "a", "a"], rows=[["1", "2", "3", "4"]])
    assert unique_headers(t.header) == ["a", "col_2", "a_2", "a_3"]
    assert t.to_dicts() == [{"a": "1", "col_2": "2", "a_2": "3", "a_3": "4"}]
    assert t.to_dicts(infer_types=True)[0]["a"] == 1


def test_from_rows_and_records():
    t = tablemd.from_rows(["a", "b"], [[1, None], [2.0, True]], align=["right"])
    assert t.rows == [["1", ""], ["2", "true"]]
    assert t.align == ["right", None]
    t2 = tablemd.from_records([{"x": 1}, {"y": 2}], columns=["y", "x"])
    assert t2.header == ["y", "x"] and t2.rows == [["", "1"], ["2", ""]]


# -------------------------------------------------------------------- HTML --

def test_to_html_escapes(table):
    t = Table(header=["<b>"], rows=[["a & b"]], align=["right"])
    html = t.to_html()
    assert "&lt;b&gt;" in html and "a &amp; b" in html
    assert '<td style="text-align:right">' in html
    assert html.startswith("<table>") and html.endswith("</table>")


# ------------------------------------------------------------------- Excel --

def test_xlsx_round_trip(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    md = "| 產品 | 數量 | 備註 |\n|---|---:|---|\n| 蘋果 | 1,200 | a<br>b |\n| 007 | 0912 | |\n"
    t = parse_one(md, plain=True)
    path = tmp_path / "out.xlsx"
    t.to_xlsx(path, sheet_name="銷售:Q3?")
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames == ["銷售_Q3_"]
    ws = wb.active
    assert ws["A1"].font.bold
    assert ws.freeze_panes == "A2"
    assert ws["B2"].value == 1200
    assert ws["A3"].value == "007"
    assert ws["B3"].value == "0912"
    assert ws["C2"].value == "a\nb"
    assert ws["C3"].value is None
    assert ws["B2"].alignment.horizontal == "right"

    tables = tablemd.read_xlsx(path)
    assert len(tables) == 1
    assert tables[0].header == ["產品", "數量", "備註"]
    assert tables[0].rows == [["蘋果", "1200", "a\nb"], ["007", "0912", ""]]
    assert tablemd.read_xlsx(path, sheet="銷售_Q3_")[0].nrows == 2
    assert tablemd.read_xlsx(path, sheet=0)[0].nrows == 2
    with pytest.raises(TablemdError):
        tablemd.read_xlsx(path, sheet="missing")
    with pytest.raises(TablemdError):
        tablemd.read_xlsx(path, sheet=5)


def test_xlsx_formula_like_cells_stay_text(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    t = Table(header=["Op", "=Meaning"], rows=[["==", "equal"], ["=>", "arrow"], ["=SUM(A1)", "x\x00y"]])
    path = tmp_path / "ops.xlsx"
    t.to_xlsx(path)
    ws = openpyxl.load_workbook(path).active
    assert ws["B1"].value == "=Meaning" and ws["B1"].data_type == "s"
    assert ws["A2"].value == "==" and ws["A2"].data_type == "s"
    assert ws["A4"].value == "=SUM(A1)" and ws["A4"].data_type == "s"
    assert ws["B4"].value == "xy"  # control character dropped instead of crashing
    back = tablemd.read_xlsx(path)[0]
    assert back.rows[0] == ["==", "equal"] and back.rows[2][0] == "=SUM(A1)"


def test_xlsx_dates_and_numeric_sheet_names(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    import datetime

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "2023"
    ws.append(["when", "at", "n"])
    ws.append([datetime.datetime(2024, 1, 1), datetime.datetime(2024, 1, 1, 9, 30), 1.0])
    ws.append([datetime.date(2024, 2, 2), datetime.time(8, 5), 2.5])
    path = tmp_path / "dates.xlsx"
    wb.save(path)
    (t,) = tablemd.read_xlsx(path, sheet="2023")
    assert t.rows == [["2024-01-01", "2024-01-01 09:30:00", "1"], ["2024-02-02", "08:05:00", "2.5"]]
    assert tablemd.read_xlsx(path, sheet="0")[0].nrows == 2


def test_write_xlsx_many_sheets(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    tables = [Table(header=["a"], rows=[["1"]]), Table(header=["b"], rows=[["2"]]), Table(header=["c"])]
    path = tmp_path / "many.xlsx"
    tablemd.write_xlsx(tables, path, sheet_names=["Same", "same"])
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames == ["Same", "same (2)", "Table3"]
    back = tablemd.read_xlsx(path)
    assert [t.header for t in back] == [["a"], ["b"], ["c"]]
    with pytest.raises(TablemdError):
        tablemd.write_xlsx([], path)


def test_safe_sheet_name():
    from tablemd._xlsx import safe_sheet_name

    assert safe_sheet_name("a/b\\c[d]e:f*g?h") == "a_b_c_d_e_f_g_h"
    assert len(safe_sheet_name("x" * 50)) == 31
    assert safe_sheet_name("", []) == "Sheet"
    assert safe_sheet_name("A", ["a"]) == "A (2)"


# ----------------------------------------------------------------- convert --

def test_convert_text_formats(table):
    assert convert(MD, "csv").startswith("Name,Qty,Price")
    assert convert(table, "tsv").splitlines()[0] == "Name\tQty\tPrice"
    assert json.loads(convert(MD, "json"))[0]["Qty"] == 3
    assert convert(MD, "md").splitlines()[1] == "| :---- | --: | :---: |"
    assert convert(MD, "markdown") == convert(MD, "md")
    assert convert(MD, "html").startswith("<table>")
    with pytest.raises(TablemdError):
        convert(MD, "pdf")
    with pytest.raises(TablemdError):
        convert("nothing here", "csv")
    with pytest.raises(TablemdError):
        convert(MD, "csv", table=3)
    with pytest.raises(TablemdError):
        convert([], "csv")


def test_convert_all_tables(tmp_path):
    md = MD + "\n| x |\n|---|\n| 1 |\n"
    csv_all = convert(md, "csv", table=None)
    assert csv_all.count("\n\n") == 1 and csv_all.endswith("x\n1")
    js = json.loads(convert(md, "json", table=None))
    assert isinstance(js, list) and len(js) == 2 and js[1] == [{"x": 1}]
    # "all" mode keeps the list-of-tables shape even for a single table.
    assert json.loads(convert(MD, "json", table=None)) == [json.loads(convert(MD, "json"))]
    md_all = convert(md, "md", table=None)
    assert md_all.count("| --- |") == 1

    path = tmp_path / "out.csv"
    assert convert(md, "csv", path, table=None) is None
    assert (tmp_path / "out-1.csv").exists() and (tmp_path / "out-2.csv").exists()
    assert not path.exists()

    single = tmp_path / "one.md"
    convert(md, "md", single)
    assert single.read_text(encoding="utf-8").endswith("|\n")


def test_convert_xlsx(tmp_path):
    pytest.importorskip("openpyxl")
    with pytest.raises(TablemdError):
        convert(MD, "xlsx")
    path = tmp_path / "x.xlsx"
    assert convert(MD, "excel", path) is None
    assert tablemd.read(path)[0].header == ["Name", "Qty", "Price"]


def test_read_dispatch(tmp_path):
    (tmp_path / "a.md").write_text(MD, encoding="utf-8")
    (tmp_path / "a.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (tmp_path / "a.tsv").write_text("a\tb\n1\t2\n", encoding="utf-8")
    (tmp_path / "a.json").write_text('[{"a": 1}]', encoding="utf-8")
    (tmp_path / "a.weird").write_text("x", encoding="utf-8")
    assert tablemd.read(tmp_path / "a.md")[0].nrows == 2
    assert tablemd.read(tmp_path / "a.csv")[0].rows == [["1", "2"]]
    assert tablemd.read(tmp_path / "a.tsv")[0].rows == [["1", "2"]]
    assert tablemd.read(tmp_path / "a.json")[0].rows == [["1"]]
    assert tablemd.read(tmp_path / "a.weird", fmt="csv")[0].header == ["x"]
    with pytest.raises(TablemdError):
        tablemd.read(tmp_path / "a.weird")
    with pytest.raises(TablemdError):
        tablemd.read(tmp_path / "a.weird", fmt="pdf")
    assert tablemd.format_from_path("x.HTML") == "html"
    assert tablemd.format_from_path("x.unknown") is None


def test_pandas_round_trip(table):
    pd = pytest.importorskip("pandas")
    df = table.to_dataframe()
    assert list(df.columns) == ["Name", "Qty", "Price"]
    assert df["Qty"].tolist() == [3, 12]
    back = tablemd.from_dataframe(df)
    assert back.rows == [["Apple", "3", "1.5"], ["香蕉", "12", "0.25"]]
    df2 = pd.DataFrame({"a": [1, None]})
    assert tablemd.from_dataframe(df2).rows == [["1"], [""]]
    assert tablemd.from_dataframe(df2, index=True).header == ["index", "a"]
