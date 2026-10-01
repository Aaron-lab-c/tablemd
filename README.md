# tablemd

**Convert Markdown tables to CSV / TSV / JSON / Excel — and back.**
Library + CLI · zero dependencies · clipboard-aware · CJK-friendly alignment.

[![PyPI](https://img.shields.io/pypi/v/tablemd.svg)](https://pypi.org/project/tablemd/)
[![Python](https://img.shields.io/pypi/pyversions/tablemd.svg)](https://pypi.org/project/tablemd/)
[![CI](https://github.com/Aaron-lab-c/tablemd/actions/workflows/ci.yml/badge.svg)](https://github.com/Aaron-lab-c/tablemd/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/Aaron-lab-c/tablemd/blob/main/LICENSE)

ChatGPT, Claude and friends love to answer in Markdown tables. Spreadsheets do
not read Markdown. `tablemd` is the missing step: paste the table, get a
`.csv`, `.xlsx` or JSON file, with `**bold**` and `[links](…)` cleaned up,
`1,234` turned into a real number, and `0912345678` kept as text.
It also goes the other way, turning CSV / Excel / JSON back into a tidy,
column-aligned Markdown table — even when the cells are 中文.

[中文說明在下方](#中文說明)

---

## Install

```bash
pip install tablemd            # core: Markdown ⇄ CSV / TSV / JSON / HTML
pip install "tablemd[xlsx]"    # + Excel support (openpyxl)
pip install "tablemd[all]"     # + pandas interop
```

Python 3.9+. No required dependencies.

## Command line

```bash
tablemd notes.md                       # first table in notes.md → CSV on stdout
tablemd notes.md -o data.xlsx          # first table → Excel
tablemd notes.md --all -o data.xlsx    # every table → one sheet each
tablemd notes.md -n 2 -t json          # second table → JSON
tablemd notes.md --list                # what tables are in there?
tablemd notes.md --plain -o clean.csv  # strip **bold**, `code`, [links](…)

tablemd -c --copy                      # clipboard Markdown → clipboard CSV
tablemd -c -o out.xlsx --plain         # clipboard → Excel

tablemd data.csv                       # CSV → aligned Markdown table
tablemd report.xlsx --sheet Sales      # Excel sheet → Markdown
tablemd messy.md -t md                 # re-align an untidy Markdown table
cat report.md | tablemd -t tsv         # pipes work too
```

Formats are inferred from file extensions; override with `-f` (input) and
`-t` (output). Without `-o`, Markdown input defaults to CSV and everything
else defaults to Markdown.

<details>
<summary>Full option list (<code>tablemd --help</code>)</summary>

```
positional arguments:
  INPUT                 input file (.md/.csv/.tsv/.json/.xlsx); '-' or omitted reads stdin

options:
  -o, --output FILE     write here instead of stdout; format inferred from extension
  -t, --to FMT          output format: md, csv, tsv, json, html, xlsx
  -f, --from FMT        input format (default: inferred)
  -n, --table N         which table to convert, 1-based (default: 1)
  -a, --all             convert every table found
  -l, --list            list the tables found and exit
  -p, --plain           strip **bold**, `code`, [links](...) etc. from cells
  -c, --clipboard       read input from the clipboard
  --copy                copy the result to the clipboard (text formats only)
  -V, --version

format options:
  -d, --delimiter CHAR  CSV delimiter for input and output, e.g. ';' or '\t' (default: ',')
  --encoding ENC        output text encoding, also used for piped stdout
                        (default: utf-8; use utf-8-sig for Excel-friendly CSV)
  --input-encoding ENC  input text encoding, e.g. cp950 / big5 (default: utf-8-sig)
  --sheet NAME          Excel sheet to read (name or 0-based index); with -o FILE.xlsx
                        the name of the single sheet to write
  --orient {records,split}
                        JSON layout (default: records)
  --indent N            JSON indentation; 0 for compact (default: 2)
  --no-infer            keep every cell as text in JSON/Excel output
  --no-pretty           do not align columns in Markdown output
```

</details>

## Python API

```python
import tablemd

md = """
| Product | Qty   | Price  |
|:--------|------:|-------:|
| **iPhone** | 1,200 | 29,900 |
| 香蕉    | 12    | 0.25   |
"""

table = tablemd.parse_one(md)          # tablemd.parse(md) → list of every table

table.header        # ['Product', 'Qty', 'Price']
table.rows          # [['**iPhone**', '1,200', '29,900'], ['香蕉', '12', '0.25']]
table.align         # ['left', 'right', 'right']
table.shape         # (2, 3)

table.to_csv("out.csv")                # or table.to_csv() → str
table.to_tsv("out.tsv")
table.to_json("out.json")              # [{"Product": "**iPhone**", "Qty": 1200, "Price": 29900}, …]
table.to_xlsx("out.xlsx")              # bold header, frozen pane, aligned, auto-width
table.to_html()                        # plain <table> markup
table.to_dicts()                       # list of dicts (duplicate/empty headers made unique)
table.to_dataframe()                   # pandas, if installed

clean = table.plain()                  # '**iPhone**' → 'iPhone', '<br>' → newline, …
print(clean.to_markdown())             # columns padded so 中文 and ASCII line up
```

Going the other way:

```python
tablemd.from_csv("a,b\n1,2\n")                  # delimiter is sniffed
tablemd.from_json('[{"a": 1}, {"a": 2}]')       # records, split, or list-of-lists
tablemd.from_records([{"x": 1, "y": 2}])
tablemd.from_rows(["x", "y"], [[1, 2], [3, 4]])
tablemd.from_dataframe(df)

tablemd.read_csv("data.csv")                    # file readers
tablemd.read_json("data.json")
tablemd.read_xlsx("book.xlsx")                  # → one Table per sheet
tablemd.read_markdown("notes.md")               # → every table in the file
tablemd.read("anything.ext")                    # dispatches on the extension

tablemd.write_xlsx(tables, "book.xlsx", sheet_names=["Q1", "Q2"])
```

One-liner for scripts:

```python
tablemd.convert(md_text, "xlsx", "out.xlsx", plain=True)
csv_text = tablemd.convert(md_text, "csv")                 # first table
json_all = tablemd.convert(md_text, "json", table=None)    # every table
```

## What it handles

- **GFM parsing** — optional outer pipes, `\|` escapes, `:---:` alignment,
  ragged rows (padded/truncated like GitHub does), tables inside `>` quotes or
  indented blocks, and it skips tables inside fenced code blocks.
- **Several tables per document** — pick one (`-n 2`) or take them all
  (`--all`; one sheet each for Excel).
- **Clean cells** — `--plain` turns `**bold**`, `*em*`, `` `code` ``,
  `[text](url)`, `![alt](src)`, `~~strike~~`, `<br>`, simple HTML tags and
  entities into what you would read on screen.
- **Sensible types** — for JSON and Excel, `1,234` → `1234`, `3.5` → `3.5`,
  `true` → `true`; but `007`, `0912345678` and 16+-digit numbers stay text so
  IDs and phone numbers survive. `--no-infer` keeps everything as text.
- **Excel niceties** — bold header, frozen header row, column alignment taken
  from the Markdown, auto column widths (CJK-aware), wrapped multi-line cells,
  sheet names sanitised to Excel's rules, and cells like `==` or `=>` stored
  as text rather than being mistaken for formulas.
- **CJK-aware Markdown output** — fullwidth characters count as two columns,
  so `to_markdown()` lines up in a monospace editor.
- **Clipboard** — `-c` / `--copy` use `pbcopy`/`pbpaste` on macOS, the native
  clipboard on Windows, and `wl-clipboard`/`xclip`/`xsel` on Linux (WSL falls
  back to the Windows clipboard).

## Notes on the parsing rules

`tablemd` follows the [GFM table spec](https://github.github.com/gfm/#tables-extension-)
with two deliberate, user-friendly deviations:

1. A table ends at the first line that contains no `|` (GFM would swallow the
   following paragraph as a one-cell row).
2. A header row and delimiter row with different cell counts are still
   accepted (the wider of the two wins) instead of being ignored, because
   LLM-generated tables are often slightly off.

Pipes inside backticks still split cells, as in GFM — write `\|` for a literal
pipe. `\|` and `\\` are unescaped when parsing and re-escaped by
`to_markdown()`, so Markdown → Table → Markdown round-trips exactly.

With `--all` (or `convert(..., table=None)`) JSON output is always a list with
one entry per table, even when only one table was found, so scripts can rely
on the shape.

## Development

```bash
git clone https://github.com/Aaron-lab-c/tablemd.git
cd tablemd
pip install -e ".[all]" pytest
pytest
```

Releases are published to PyPI automatically by GitHub Actions when a `v*`
tag is pushed (see `.github/workflows/publish.yml`).

Bug reports and ideas: https://github.com/Aaron-lab-c/tablemd/issues

## License

MIT © ARON

---

## 中文說明

**把 Markdown 表格轉成 CSV / TSV / JSON / Excel，也能反向轉回來。**
純 Python、零相依套件，支援剪貼簿，中文全形字元對齊正確。

ChatGPT、Claude 回答時很愛用 Markdown 表格，但 Excel 看不懂 Markdown。
`tablemd` 就是中間那一步：貼上表格，得到 `.csv`、`.xlsx` 或 JSON，順手把
`**粗體**`、`[連結](…)` 清乾淨、把 `1,234` 變成真正的數字、
而 `0912345678` 這種電話號碼依然保留為文字。反向也行：CSV / Excel / JSON
轉回欄位對齊整齊的 Markdown 表格，中英夾雜也不會歪。

### 安裝

```bash
pip install tablemd            # 核心：Markdown ⇄ CSV / TSV / JSON / HTML
pip install "tablemd[xlsx]"    # 加上 Excel 支援（openpyxl）
pip install "tablemd[all]"     # 加上 pandas 互通
```

### 指令列

```bash
tablemd 筆記.md                        # 第一個表格 → CSV 輸出到螢幕
tablemd 筆記.md -o 資料.xlsx            # 第一個表格 → Excel
tablemd 筆記.md --all -o 資料.xlsx      # 所有表格 → 每個一張工作表
tablemd 筆記.md -n 2 -t json           # 第二個表格 → JSON
tablemd 筆記.md --list                 # 列出檔案裡有哪些表格
tablemd 筆記.md --plain -o 乾淨.csv     # 去掉 **粗體**、`程式碼`、[連結](…)
tablemd 筆記.md -o 資料.csv --encoding utf-8-sig   # 加 BOM，Excel 直接開不會亂碼

tablemd -c --copy                      # 剪貼簿的 Markdown → 轉成 CSV 放回剪貼簿
tablemd -c -o out.xlsx --plain         # 剪貼簿 → Excel

tablemd 資料.csv                        # CSV → 對齊好的 Markdown 表格
tablemd 舊檔.csv --input-encoding cp950 # Big5 編碼的舊 CSV 也能讀
tablemd 報表.xlsx --sheet 銷售          # Excel 工作表 → Markdown
tablemd 亂掉的.md -t md                 # 重新排版對齊 Markdown 表格
```

格式會依副檔名自動判斷，也可用 `-f`（輸入）/ `-t`（輸出）指定。
沒給 `-o` 時，Markdown 輸入預設輸出 CSV，其他格式預設輸出 Markdown。

### Python 用法

```python
import tablemd

table = tablemd.parse_one(markdown_text)   # tablemd.parse() 會回傳所有表格
table.to_csv("out.csv")
table.to_xlsx("out.xlsx")                  # 粗體標題、凍結首列、自動欄寬
table.to_json("out.json")                  # 數字自動轉型，前導零的字串保留
table.plain().to_markdown()                # 去除格式後重新對齊輸出

tablemd.read_csv("data.csv").to_markdown()
tablemd.read_xlsx("book.xlsx")             # 每張工作表一個 Table
tablemd.convert(markdown_text, "xlsx", "out.xlsx", plain=True)   # 一行搞定
```

### 特色

- 完整支援 GFM 表格語法：可省略外側 `|`、`\|` 跳脫、`:---:` 對齊、長短不一的列、引用區塊或縮排內的表格，並會跳過程式碼區塊裡的表格。
- 一份文件多個表格：用 `-n` 選一個，或 `--all` 全部轉（Excel 會分成多張工作表）。
- `--plain` 把 `**粗體**`、`` `程式碼` ``、`[文字](網址)`、`<br>`、HTML 標籤與實體轉成你在畫面上看到的純文字。
- JSON / Excel 輸出時聰明轉型：`1,234` → `1234`，但 `007`、`0912345678`、超過 15 位的數字保持文字，身分證字號與電話不會壞掉。`--no-infer` 可全部保留文字。
- Markdown 輸出時全形字算兩格，中英夾雜的表格在等寬字型下也能對齊。
- 剪貼簿支援 macOS、Windows、Linux（wl-clipboard / xclip / xsel）與 WSL。

MIT 授權。問題回報與建議：https://github.com/Aaron-lab-c/tablemd/issues
