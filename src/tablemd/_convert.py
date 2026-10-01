"""High-level ``convert()`` used by both the public API and the CLI."""

from __future__ import annotations

import os
from typing import List, Optional, Sequence, Union

from ._parse import parse
from ._table import PathLike, Table, TablemdError

__all__ = ["convert", "FORMATS", "TEXT_FORMATS"]

TEXT_FORMATS = ("md", "csv", "tsv", "json", "html")
FORMATS = TEXT_FORMATS + ("xlsx",)

Source = Union[str, Table, Sequence[Table]]


def _as_tables(source: Source, *, plain: bool) -> List[Table]:
    if isinstance(source, Table):
        tables = [source]
    elif isinstance(source, str):
        tables = parse(source)
        if not tables:
            raise TablemdError("no Markdown table found in input")
    else:
        tables = list(source)
        if not tables:
            raise TablemdError("no tables given")
    return [t.plain() for t in tables] if plain else tables


def _render_text(table: Table, fmt: str, **opts) -> str:
    if fmt == "csv":
        return table.to_csv(delimiter=opts.get("delimiter") or ",") or ""
    if fmt == "tsv":
        return table.to_tsv() or ""
    if fmt == "json":
        return table.to_json(
            orient=opts.get("orient", "records"),
            indent=opts.get("indent", 2),
            infer_types=opts.get("infer_types", True),
        ) or ""
    if fmt == "md":
        return table.to_markdown(pretty=opts.get("pretty", True))
    if fmt == "html":
        return table.to_html()
    raise TablemdError(f"unsupported output format {fmt!r}")


def _numbered(path: PathLike, i: int) -> str:
    root, ext = os.path.splitext(str(path))
    return f"{root}-{i}{ext}"


def convert(
    source: Source,
    to: str,
    path: Optional[PathLike] = None,
    *,
    table: Optional[int] = 0,
    plain: bool = False,
    delimiter: Optional[str] = None,
    encoding: str = "utf-8",
    indent: Optional[int] = 2,
    orient: str = "records",
    infer_types: bool = True,
    pretty: bool = True,
    sheet_names: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """Convert Markdown text (or tables) to *to* and return the text or write *path*.

    *source* may be Markdown text, a :class:`Table`, or a sequence of tables.
    *table* picks one table by 0-based index (default: the first); ``None``
    selects all of them. Text formats return a string when *path* is omitted.
    ``to="xlsx"`` always needs *path*; several tables become several sheets.
    With ``table=None`` JSON output is always a list with one entry per table.
    When several tables go to a single CSV/TSV path they are written to
    numbered files (``out-1.csv``, ``out-2.csv`` ...).
    """
    to = to.lower().lstrip(".")
    if to == "markdown":
        to = "md"
    if to == "excel":
        to = "xlsx"
    if to not in FORMATS:
        raise TablemdError(f"unsupported output format {to!r}; choose from {', '.join(FORMATS)}")

    tables = _as_tables(source, plain=plain)
    if table is not None:
        try:
            tables = [tables[table]]
        except IndexError as exc:
            raise TablemdError(
                f"input has {len(tables)} table(s); table index {table} is out of range"
            ) from exc

    if to == "xlsx":
        if path is None:
            raise TablemdError("Excel output needs a file path")
        from ._xlsx import write_xlsx

        write_xlsx(tables, path, sheet_names=sheet_names, infer_types=infer_types)
        return None

    opts = dict(delimiter=delimiter, indent=indent, orient=orient, infer_types=infer_types, pretty=pretty)

    if to == "json" and table is None:
        # "all tables" mode always yields a list of per-table payloads, even
        # when there happens to be only one, so scripts get a stable shape.
        import json

        payloads = [json.loads(_render_text(t, "json", indent=None, orient=orient, infer_types=infer_types)) for t in tables]
        text = json.dumps(payloads, indent=indent, ensure_ascii=False)
    elif to in ("csv", "tsv") and len(tables) > 1 and path is not None:
        for i, t in enumerate(tables, start=1):
            with open(_numbered(path, i), "w", encoding=encoding, newline="") as fh:
                fh.write(_render_text(t, to, **opts))
        return None
    else:
        text = "\n\n".join(_render_text(t, to, **opts).rstrip("\n") for t in tables)

    if path is None:
        return text
    with open(path, "w", encoding=encoding, newline="") as fh:
        fh.write(text)
        if not text.endswith("\n"):
            fh.write("\n")
    return None
