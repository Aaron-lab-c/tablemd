"""tablemd — convert Markdown tables to CSV / TSV / JSON / Excel and back.

Quick start::

    import tablemd

    md = '''
    | Name  | Qty | Price |
    |:------|----:|------:|
    | Apple |   3 |  1.50 |
    | 香蕉  |  12 |  0.25 |
    '''

    table = tablemd.parse_one(md)
    table.to_csv("fruit.csv")
    table.to_xlsx("fruit.xlsx")      # pip install tablemd[xlsx]
    print(table.to_json())           # [{"Name": "Apple", "Qty": 3, "Price": 1.5}, ...]

    # ...and back again
    print(tablemd.read_csv("fruit.csv").to_markdown())

Command line::

    tablemd notes.md -o data.xlsx          # first table in notes.md -> Excel
    tablemd notes.md --all -o data.xlsx    # every table -> one sheet each
    tablemd -c --copy                      # clipboard Markdown -> clipboard CSV
    tablemd data.csv                       # CSV -> pretty Markdown on stdout
"""

from ._convert import FORMATS, TEXT_FORMATS, convert
from ._io import (
    format_from_path,
    from_csv,
    from_dataframe,
    from_json,
    from_records,
    from_rows,
    read,
    read_csv,
    read_json,
    read_markdown,
    read_xlsx,
)
from ._parse import is_delimiter_row, parse, parse_one, split_row
from ._table import Table, TablemdError, unique_headers
from ._text import coerce, display_width, strip_formatting

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "Table",
    "TablemdError",
    "parse",
    "parse_one",
    "convert",
    "from_rows",
    "from_records",
    "from_csv",
    "from_json",
    "from_dataframe",
    "read",
    "read_markdown",
    "read_csv",
    "read_json",
    "read_xlsx",
    "write_xlsx",
    "format_from_path",
    "split_row",
    "is_delimiter_row",
    "unique_headers",
    "strip_formatting",
    "display_width",
    "coerce",
    "FORMATS",
    "TEXT_FORMATS",
]


def write_xlsx(tables, path, **kwargs):
    """Write several tables to one ``.xlsx`` workbook, one sheet each (requires openpyxl)."""
    from ._xlsx import write_xlsx as _write

    return _write(tables, path, **kwargs)
