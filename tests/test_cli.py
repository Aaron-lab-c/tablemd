import io
import json
import subprocess
import sys

import pytest

from tablemd import cli
from tablemd._clipboard import TablemdError

MD = """\
# Report

| Name | Qty | Note |
|------|----:|------|
| **A** | 1,000 | x<br>y |
| B | 2 | [l](http://e) |

| k | v |
|---|---|
| 1 | 2 |
"""


@pytest.fixture
def md_file(tmp_path):
    p = tmp_path / "r.md"
    p.write_text(MD, encoding="utf-8")
    return p


def run(args, stdin_text=None, monkeypatch=None):
    """Run the CLI in-process; return (code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    old = sys.stdin, sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    if stdin_text is not None:
        sys.stdin = io.StringIO(stdin_text)
    try:
        code = cli.main([str(a) for a in args])
    finally:
        sys.stdin, sys.stdout, sys.stderr = old
    return code, out.getvalue(), err.getvalue()


def test_default_md_to_csv(md_file):
    code, out, err = run([md_file])
    assert code == 0 and err == ""
    assert out == 'Name,Qty,Note\n**A**,"1,000",x<br>y\nB,2,[l](http://e)\n'


def test_plain_and_second_table(md_file):
    code, out, _ = run([md_file, "-p"])
    assert out.splitlines()[1] == 'A,"1,000","x'
    code, out, _ = run([md_file, "-n", "2", "-t", "json", "--indent", "0"])
    assert json.loads(out) == [{"k": 1, "v": 2}]


def test_list(md_file):
    code, out, _ = run([md_file, "--list"])
    assert code == 0
    assert out.splitlines() == [
        "#1  2 rows x 3 cols   Name | Qty | Note",
        "#2  1 rows x 2 cols   k | v",
    ]


def test_all_to_markdown_realigns(md_file):
    code, out, _ = run([md_file, "--all", "-t", "md", "-p"])
    assert code == 0
    assert "| Name |   Qty | Note   |" in out
    assert "| ---- | ----: | ------ |" in out
    assert out.count("\n\n") == 1


def test_output_file_infers_format(md_file, tmp_path):
    dest = tmp_path / "out.tsv"
    code, out, _ = run([md_file, "-o", dest])
    assert code == 0 and out == ""
    assert dest.read_text(encoding="utf-8") == "Name\tQty\tNote\n**A**\t1,000\tx<br>y\nB\t2\t[l](http://e)\n"
    dest = tmp_path / "out.json"
    run([md_file, "-o", dest, "--orient", "split", "--no-infer"])
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data["data"][0] == ["**A**", "1,000", "x<br>y"]


def test_xlsx_output_and_input(md_file, tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    dest = tmp_path / "out.xlsx"
    code, _, err = run([md_file, "--all", "-o", dest, "-p"])
    assert code == 0, err
    wb = openpyxl.load_workbook(dest)
    assert wb.sheetnames == ["Table1", "Table2"]
    assert wb["Table1"]["B2"].value == 1000

    code, _, _ = run([md_file, "-o", tmp_path / "named.xlsx", "--sheet", "Sales"])
    assert openpyxl.load_workbook(tmp_path / "named.xlsx").sheetnames == ["Sales"]

    code, out, _ = run([dest, "--sheet", "Table2"])
    assert code == 0
    assert out.splitlines()[0] == "| k   | v   |"
    code, out, _ = run([dest, "--sheet", "1", "-t", "csv"])
    assert out == "k,v\n1,2\n"
    code, _, err = run([dest, "--sheet", "nope"])
    assert code == 1 and "no sheet named" in err


def test_xlsx_needs_output_path(md_file):
    code, _, err = run([md_file, "-t", "xlsx"])
    assert code == 1 and "needs -o" in err
    code, _, err = run([md_file, "-t", "xlsx", "-o", "x.xlsx", "--copy"])
    assert code == 1 and "--copy" in err


def test_stdin_csv_to_markdown():
    code, out, _ = run([], stdin_text="a,b\n1,中文\n")
    assert code == 0
    assert out == "| a   | b    |\n| --- | ---- |\n| 1   | 中文 |\n"
    code, out, _ = run(["-"], stdin_text="a\tb\n1\t2\n")
    assert out.splitlines()[0] == "| a   | b   |"
    code, out, _ = run(["-t", "json"], stdin_text='[{"a": 1}]')
    assert json.loads(out) == [{"a": 1}]
    code, out, _ = run([], stdin_text='[{"a": 1}]')
    assert out.splitlines()[0] == "| a   |"


def test_stdin_markdown_detected():
    code, out, _ = run([], stdin_text=MD)
    assert code == 0 and out.startswith("Name,Qty,Note")


def test_explicit_from_format(tmp_path):
    p = tmp_path / "data.txt"
    p.write_text("a;b\n1;2\n", encoding="utf-8")
    code, out, _ = run([p, "-f", "csv", "-d", ";"])
    assert code == 0 and out.splitlines()[2] == "| 1   | 2   |"
    code, out, _ = run([p, "-f", "csv", "-t", "csv", "-d", ";"])
    assert out == "a;b\n1;2\n"


def test_errors(md_file, tmp_path):
    code, _, err = run([tmp_path / "missing.md"])
    assert code == 1 and "file not found" in err
    code, _, err = run([], stdin_text="just words")
    assert code == 1 and "no Markdown table" in err
    code, _, err = run([md_file, "-n", "5"])
    assert code == 1 and "--table 5 is out of range" in err
    code, _, err = run([md_file, "-n", "0"])
    assert code == 1 and "1-based" in err
    code, _, err = run([md_file, "-f", "xlsx"])
    assert code == 1 and "Excel workbook" in err
    code, _, err = run(["-f", "xlsx"], stdin_text="| a |\n|---|\n")
    assert code == 1 and "file path" in err


def test_friendly_errors_instead_of_tracebacks(tmp_path, md_file):
    code, _, err = run([tmp_path])
    assert code == 1 and "is a directory" in err
    code, _, err = run([md_file, "--encoding", "nosuch"])
    assert code == 1 and "unknown encoding" in err
    code, _, err = run([md_file, "--input-encoding", "nosuch"])
    assert code == 1 and "unknown encoding" in err
    code, _, err = run([md_file, "-o", str(tmp_path / "missing" / "x.csv")])
    assert code == 1 and err.startswith("tablemd: error:")
    code, _, err = run([md_file, "-d", ";;"])
    assert code == 1 and "single character" in err
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    code, _, err = run([bad])
    assert code == 1 and "invalid JSON" in err
    big5 = tmp_path / "big5.csv"
    big5.write_bytes("名稱,數量\n蘋果,3\n".encode("cp950"))
    code, _, err = run([big5])
    assert code == 1 and "could not decode" in err and "cp950" in err
    code, out, _ = run([big5, "--input-encoding", "cp950"])
    assert code == 0 and "蘋果" in out


def test_tab_delimiter_alias(md_file):
    code, out, _ = run([md_file, "-d", "\\t", "-t", "csv"])
    assert code == 0 and out.splitlines()[0] == "Name\tQty\tNote"
    code, out, _ = run([md_file, "-d", "tab", "-t", "csv"])
    assert out.splitlines()[0] == "Name\tQty\tNote"


def test_stdin_bom_and_input_encoding(monkeypatch):
    class FakeStdin(io.TextIOWrapper):
        pass

    raw = io.BytesIO("﻿| a | b |\n|---|---|\n| 1 | 2 |\n".encode("utf-8"))
    fake = io.TextIOWrapper(raw, encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", fake)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    assert cli.main([]) == 0
    assert out.getvalue() == "a,b\n1,2\n"

    raw = io.BytesIO("a,b\n蘋果,2\n".encode("cp950"))
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(raw, encoding="utf-8"))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    assert cli.main(["--input-encoding", "cp950"]) == 0
    assert "蘋果" in out.getvalue()


def test_piped_stdout_is_utf8_even_under_legacy_locale(md_file, tmp_path):
    cjk = tmp_path / "cjk.md"
    cjk.write_text("| 產品 | 數量 |\n|---|---|\n| 香蕉 | 1 |\n", encoding="utf-8")
    import os

    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    res = subprocess.run([sys.executable, "-m", "tablemd", str(cjk)], capture_output=True, env=env)
    assert res.returncode == 0, res.stderr
    assert res.stdout.decode("utf-8") == "產品,數量\n香蕉,1\n"
    res = subprocess.run([sys.executable, "-m", "tablemd", str(cjk), "--encoding", "utf-16"], capture_output=True, env=env)
    assert res.stdout.decode("utf-16") == "產品,數量\n香蕉,1\n"
    # A CJK path inside an *error message* must not crash on a legacy-locale stderr either.
    res = subprocess.run([sys.executable, "-m", "tablemd", str(tmp_path / "不存在.md")], capture_output=True, env=env)
    assert res.returncode == 1 and res.stderr.startswith(b"tablemd: error: file not found")


def test_no_input_on_tty(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO())
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    code, _, err = run([])
    assert code == 1 and "no input given" in err


def test_clipboard_flow(monkeypatch, md_file):
    store = {"text": MD}
    monkeypatch.setattr("tablemd._clipboard.read_clipboard", lambda: store["text"])
    monkeypatch.setattr("tablemd._clipboard.write_clipboard", lambda t: store.__setitem__("text", t))
    code, out, err = run(["-c", "--copy"])
    assert code == 0 and out == ""
    assert "copied 1 table(s) as csv" in err
    assert store["text"].startswith("Name,Qty,Note")
    # --copy together with -o writes the file AND copies.
    dest = md_file.parent / "o.md"
    code, out, err = run([md_file, "-o", dest, "--copy", "-t", "md"])
    assert dest.exists() and store["text"].startswith("| Name")


def test_clipboard_missing_tool(monkeypatch):
    def boom():
        raise TablemdError("no clipboard tool found")

    monkeypatch.setattr("tablemd._clipboard.read_clipboard", boom)
    code, _, err = run(["-c"])
    assert code == 1 and "no clipboard" in err


def test_version_and_help():
    with pytest.raises(SystemExit) as exc:
        run(["--version"])
    assert exc.value.code == 0
    with pytest.raises(SystemExit):
        run(["--help"])


def test_console_script_and_module(md_file):
    res = subprocess.run([sys.executable, "-m", "tablemd", str(md_file), "-t", "tsv"], capture_output=True, text=True)
    assert res.returncode == 0 and res.stdout.startswith("Name\tQty\tNote")
    res = subprocess.run([sys.executable, "-m", "tablemd", "--version"], capture_output=True, text=True)
    assert res.stdout.strip().startswith("tablemd ")
