"""Constructors that build :class:`Table` objects from other formats."""

from __future__ import annotations

import csv
import io
import json
from typing import TYPE_CHECKING, Any, Iterable, List, Mapping, Optional, Sequence, Union

from ._parse import parse
from ._table import PathLike, Table, TablemdError
from ._text import stringify

if TYPE_CHECKING:  # pragma: no cover
    import pandas  # noqa: F401

__all__ = [
    "from_rows",
    "from_records",
    "from_csv",
    "from_json",
    "from_dataframe",
    "read_markdown",
    "read_csv",
    "read_json",
    "read_xlsx",
    "read",
]


# --------------------------------------------------------------------------- #
# In-memory constructors
# --------------------------------------------------------------------------- #

def from_rows(
    header: Sequence[Any],
    rows: Iterable[Sequence[Any]],
    *,
    align: Optional[Sequence[Optional[str]]] = None,
) -> Table:
    """Build a table from a header sequence and an iterable of row sequences."""
    return Table(
        header=[stringify(h) for h in header],
        rows=[[stringify(c) for c in row] for row in rows],
        align=list(align or []),
    )


def from_records(
    records: Iterable[Mapping[str, Any]],
    *,
    columns: Optional[Sequence[str]] = None,
) -> Table:
    """Build a table from dicts. Columns default to the union of keys in first-seen order."""
    items = list(records)
    if columns is None:
        seen: List[str] = []
        for rec in items:
            for key in rec:
                if key not in seen:
                    seen.append(key)
        columns = seen
    rows = [[stringify(rec.get(col)) for col in columns] for rec in items]
    return Table(header=list(columns), rows=rows)


def from_csv(text: str, *, delimiter: Optional[str] = None, header: bool = True) -> Table:
    """Parse CSV/TSV *text*. The delimiter is sniffed when not given."""
    text = text.lstrip("﻿")
    if not text.strip():
        raise TablemdError("CSV input is empty")
    if delimiter is None:
        delimiter = _sniff_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [row for row in reader]
    # Drop trailing completely-empty lines.
    while rows and not any(cell.strip() for cell in rows[-1]):
        rows.pop()
    if not rows:
        raise TablemdError("CSV input is empty")
    if header:
        head, body = rows[0], rows[1:]
    else:
        width = max(len(r) for r in rows)
        head, body = [f"col_{i + 1}" for i in range(width)], rows
    width = max([len(head)] + [len(r) for r in body])
    head = head + [""] * (width - len(head))
    return Table(header=head, rows=body)


def _sniff_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:20])
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;|").delimiter
    except csv.Error:
        first = text.splitlines()[0] if text.splitlines() else ""
        return "\t" if "\t" in first else ","


def from_json(data: Union[str, bytes, Any]) -> Table:
    """Build a table from JSON text or an already-decoded object.

    Accepts the shapes :meth:`Table.to_json` produces (``records`` and
    ``split``) plus a plain list of lists whose first row is the header.
    """
    if isinstance(data, (str, bytes, bytearray)):
        if isinstance(data, str):
            data = data.lstrip("﻿")
        try:
            obj = json.loads(data)
        except ValueError as exc:
            raise TablemdError(f"invalid JSON: {exc}") from exc
    else:
        obj = data
    if isinstance(obj, dict) and "columns" in obj and "data" in obj:
        return from_rows(obj["columns"], obj["data"])
    if isinstance(obj, list):
        if not obj:
            raise TablemdError("JSON array is empty")
        if all(isinstance(item, Mapping) for item in obj):
            return from_records(obj)
        if all(isinstance(item, (list, tuple)) for item in obj):
            return from_rows(obj[0], obj[1:])
    raise TablemdError(
        "unsupported JSON shape; expected a list of objects, a list of arrays, "
        "or {'columns': [...], 'data': [...]}"
    )


def from_dataframe(df: "pandas.DataFrame", *, index: bool = False) -> Table:
    """Build a table from a :class:`pandas.DataFrame`."""
    frame = df.reset_index() if index else df
    header = [stringify(c) for c in frame.columns]
    rows = [[_pandas_scalar(v) for v in row] for row in frame.itertuples(index=False, name=None)]
    return Table(header=header, rows=rows)


def _pandas_scalar(value: Any) -> str:
    try:
        import pandas as pd  # type: ignore

        if pd.isna(value):
            return ""
    except (ImportError, TypeError, ValueError):  # pragma: no cover
        pass
    return stringify(value)


# --------------------------------------------------------------------------- #
# File readers
# --------------------------------------------------------------------------- #

def _read_text(path: PathLike, encoding: str) -> str:
    with open(path, "r", encoding=encoding) as fh:
        return fh.read()


def read_markdown(path: PathLike, *, encoding: str = "utf-8-sig", plain: bool = False) -> List[Table]:
    """Read a Markdown file and return every table in it (``utf-8-sig`` also accepts a BOM)."""
    return parse(_read_text(path, encoding), plain=plain)


def read_csv(path: PathLike, *, encoding: str = "utf-8-sig", delimiter: Optional[str] = None) -> Table:
    """Read a CSV/TSV file (``utf-8-sig`` transparently handles a BOM)."""
    return from_csv(_read_text(path, encoding), delimiter=delimiter)


def read_json(path: PathLike, *, encoding: str = "utf-8-sig") -> Table:
    """Read a JSON file (see :func:`from_json` for accepted shapes)."""
    return from_json(_read_text(path, encoding))


def read_xlsx(path: PathLike, *, sheet: Union[str, int, None] = None) -> List[Table]:
    """Read an Excel workbook; one table per sheet (requires openpyxl)."""
    from ._xlsx import read_xlsx as _read

    return _read(path, sheet=sheet)


_EXT_FORMATS = {
    ".md": "md",
    ".markdown": "md",
    ".mdown": "md",
    ".txt": "md",
    ".csv": "csv",
    ".tsv": "tsv",
    ".tab": "tsv",
    ".json": "json",
    ".xlsx": "xlsx",
    ".xlsm": "xlsx",
}


def format_from_path(path: PathLike) -> Optional[str]:
    """Guess a format name (``md``/``csv``/``tsv``/``json``/``xlsx``/``html``) from a file extension."""
    import os

    ext = os.path.splitext(str(path))[1].lower()
    if ext in (".html", ".htm"):
        return "html"
    return _EXT_FORMATS.get(ext)


def read(path: PathLike, *, fmt: Optional[str] = None, sheet: Union[str, int, None] = None) -> List[Table]:
    """Read any supported file, picking the reader from *fmt* or the extension."""
    fmt = fmt or format_from_path(path)
    if fmt is None:
        raise TablemdError(f"cannot infer format of {path!s}; pass fmt=")
    if fmt == "md":
        return read_markdown(path)
    if fmt == "csv":
        return [read_csv(path)]
    if fmt == "tsv":
        return [read_csv(path, delimiter="\t")]
    if fmt == "json":
        return [read_json(path)]
    if fmt == "xlsx":
        return read_xlsx(path, sheet=sheet)
    raise TablemdError(f"unsupported input format {fmt!r}")
