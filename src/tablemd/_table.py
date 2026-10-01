"""The :class:`Table` data model and its export methods."""

from __future__ import annotations

import csv
import html as _html
import io
import json
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence, Union

from ._text import coerce, display_width, escape_cell, pad, strip_formatting, stringify

if TYPE_CHECKING:  # pragma: no cover
    import pandas  # noqa: F401

PathLike = Union[str, "os.PathLike[str]"]
Alignment = Optional[str]  # "left" | "center" | "right" | None

__all__ = ["Table", "TablemdError", "unique_headers"]


class TablemdError(Exception):
    """Base class for all errors raised by tablemd."""


def unique_headers(header: Sequence[str]) -> List[str]:
    """Return header names made unique and non-empty.

    Empty names become ``col_N`` (1-based); duplicates get ``_2``, ``_3`` ...
    suffixes. Used wherever headers must act as keys (dicts, JSON records,
    DataFrame columns).
    """
    seen: Dict[str, int] = {}
    out: List[str] = []
    for i, raw in enumerate(header, start=1):
        name = raw.strip() or f"col_{i}"
        base = name
        if name in seen:
            seen[base] += 1
            name = f"{base}_{seen[base]}"
            while name in seen:
                seen[base] += 1
                name = f"{base}_{seen[base]}"
        seen[name] = seen.get(name, 1)
        out.append(name)
    return out


@dataclass
class Table:
    """A rectangular table: a header row, body rows and per-column alignment.

    Every cell is stored as a :class:`str`. Rows are normalised to the header
    length on construction (short rows are padded with ``""``, long rows are
    truncated), so ``table.rows[i][j]`` is always safe for ``j < table.ncols``.
    """

    header: List[str]
    rows: List[List[str]] = field(default_factory=list)
    align: List[Alignment] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.header = [str(h) for h in self.header]
        n = len(self.header)
        self.rows = [self._fit([str(c) for c in row], n) for row in self.rows]
        self.align = list(self.align)[:n] + [None] * max(0, n - len(self.align))

    @staticmethod
    def _fit(row: List[str], n: int) -> List[str]:
        if len(row) < n:
            return row + [""] * (n - len(row))
        return row[:n]

    # ------------------------------------------------------------------ #
    # Basic properties
    # ------------------------------------------------------------------ #

    @property
    def ncols(self) -> int:
        return len(self.header)

    @property
    def nrows(self) -> int:
        """Number of body rows (the header is not counted)."""
        return len(self.rows)

    @property
    def shape(self) -> "tuple[int, int]":
        """``(nrows, ncols)`` like NumPy/pandas."""
        return (self.nrows, self.ncols)

    def __len__(self) -> int:
        return self.nrows

    def __iter__(self):
        return iter(self.rows)

    def column(self, key: Union[int, str]) -> List[str]:
        """Return one column by 0-based index or header name."""
        idx = key if isinstance(key, int) else self.header.index(key)
        return [row[idx] for row in self.rows]

    def plain(self) -> "Table":
        """Return a copy with inline Markdown/HTML formatting stripped from every cell."""
        return Table(
            header=[strip_formatting(h) for h in self.header],
            rows=[[strip_formatting(c) for c in row] for row in self.rows],
            align=list(self.align),
        )

    def typed_rows(self) -> List[List[Any]]:
        """Body rows with cells coerced to ``int``/``float``/``bool``/``None`` where unambiguous."""
        return [[coerce(c) for c in row] for row in self.rows]

    def to_dicts(self, *, infer_types: bool = False) -> List[Dict[str, Any]]:
        """Return body rows as a list of ``{header: value}`` dicts."""
        keys = unique_headers(self.header)
        source = self.typed_rows() if infer_types else self.rows
        return [dict(zip(keys, row)) for row in source]

    # ------------------------------------------------------------------ #
    # Markdown / HTML
    # ------------------------------------------------------------------ #

    def to_markdown(self, *, pretty: bool = True) -> str:
        """Render as a GitHub-Flavored-Markdown table.

        With ``pretty=True`` columns are padded so the source lines up in a
        monospace font, taking fullwidth CJK characters into account.
        """
        header = [escape_cell(h) for h in self.header]
        rows = [[escape_cell(c) for c in row] for row in self.rows]

        if pretty:
            widths = [max(3, display_width(h)) for h in header]
            for row in rows:
                for i, cell in enumerate(row):
                    widths[i] = max(widths[i], display_width(cell))
        else:
            widths = [0] * self.ncols

        def fmt(cells: Sequence[str]) -> str:
            padded = [pad(c, widths[i], self.align[i]) for i, c in enumerate(cells)]
            return "| " + " | ".join(padded) + " |"

        delim_cells = []
        for i in range(self.ncols):
            w = widths[i] if pretty else 3
            a = self.align[i]
            if a == "left":
                delim_cells.append(":" + "-" * (w - 1))
            elif a == "right":
                delim_cells.append("-" * (w - 1) + ":")
            elif a == "center":
                delim_cells.append(":" + "-" * (w - 2) + ":")
            else:
                delim_cells.append("-" * w)

        lines = [fmt(header), "| " + " | ".join(delim_cells) + " |"]
        lines.extend(fmt(row) for row in rows)
        return "\n".join(lines)

    def to_html(self, *, indent: str = "  ") -> str:
        """Render as a plain ``<table>`` element (cell text is HTML-escaped)."""

        def td(tag: str, text: str, a: Alignment) -> str:
            style = f' style="text-align:{a}"' if a else ""
            return f"<{tag}{style}>{_html.escape(text)}</{tag}>"

        out = ["<table>", f"{indent}<thead>", f"{indent*2}<tr>"]
        out += [indent * 3 + td("th", h, self.align[i]) for i, h in enumerate(self.header)]
        out += [f"{indent*2}</tr>", f"{indent}</thead>", f"{indent}<tbody>"]
        for row in self.rows:
            out.append(f"{indent*2}<tr>")
            out += [indent * 3 + td("td", c, self.align[i]) for i, c in enumerate(row)]
            out.append(f"{indent*2}</tr>")
        out += [f"{indent}</tbody>", "</table>"]
        return "\n".join(out)

    # ------------------------------------------------------------------ #
    # CSV / TSV
    # ------------------------------------------------------------------ #

    def to_csv(
        self,
        path: Optional[PathLike] = None,
        *,
        delimiter: str = ",",
        encoding: str = "utf-8",
        header: bool = True,
    ) -> Optional[str]:
        """Serialise to CSV.

        Returns the CSV text when *path* is ``None``, otherwise writes the file
        and returns ``None``. Use ``encoding="utf-8-sig"`` to get a BOM, which
        makes Excel open non-ASCII CSVs correctly.
        """
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=delimiter, lineterminator="\n")
        if header:
            writer.writerow(self.header)
        writer.writerows(self.rows)
        text = buf.getvalue()
        if path is None:
            return text
        with open(path, "w", encoding=encoding, newline="") as fh:
            fh.write(text)
        return None

    def to_tsv(self, path: Optional[PathLike] = None, **kwargs: Any) -> Optional[str]:
        """Serialise to tab-separated values (see :meth:`to_csv`)."""
        kwargs.setdefault("delimiter", "\t")
        return self.to_csv(path, **kwargs)

    # ------------------------------------------------------------------ #
    # JSON
    # ------------------------------------------------------------------ #

    def to_json(
        self,
        path: Optional[PathLike] = None,
        *,
        orient: str = "records",
        indent: Optional[int] = 2,
        infer_types: bool = True,
        ensure_ascii: bool = False,
        encoding: str = "utf-8",
    ) -> Optional[str]:
        """Serialise to JSON.

        ``orient="records"`` gives ``[{col: val}, ...]``; ``orient="split"``
        gives ``{"columns": [...], "data": [[...], ...]}``. With
        ``infer_types`` numeric/boolean-looking cells become real JSON numbers
        and booleans and empty cells become ``null``.
        """
        if orient not in ("records", "split"):
            raise TablemdError(f"unknown orient {orient!r}; expected 'records' or 'split'")
        data = self.typed_rows() if infer_types else self.rows
        obj: Any
        if orient == "records":
            keys = unique_headers(self.header)
            obj = [dict(zip(keys, row)) for row in data]
        else:
            obj = {"columns": list(self.header), "data": data}
        text = json.dumps(obj, indent=indent, ensure_ascii=ensure_ascii)
        if path is None:
            return text
        with open(path, "w", encoding=encoding) as fh:
            fh.write(text)
            fh.write("\n")
        return None

    # ------------------------------------------------------------------ #
    # Excel
    # ------------------------------------------------------------------ #

    def to_xlsx(
        self,
        path: PathLike,
        *,
        sheet_name: str = "Table1",
        infer_types: bool = True,
        bold_header: bool = True,
        freeze_header: bool = True,
        autofit: bool = True,
    ) -> None:
        """Write an ``.xlsx`` workbook with this table as its only sheet.

        Requires ``openpyxl`` (``pip install tablemd[xlsx]``). For several
        tables in one workbook use :func:`tablemd.write_xlsx`.
        """
        from ._xlsx import write_xlsx

        write_xlsx(
            [self],
            path,
            sheet_names=[sheet_name],
            infer_types=infer_types,
            bold_header=bold_header,
            freeze_header=freeze_header,
            autofit=autofit,
        )

    # ------------------------------------------------------------------ #
    # pandas
    # ------------------------------------------------------------------ #

    def to_dataframe(self, *, infer_types: bool = True) -> "pandas.DataFrame":
        """Convert to a :class:`pandas.DataFrame` (requires pandas)."""
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise TablemdError("pandas is required for to_dataframe(); pip install pandas") from exc
        data = self.typed_rows() if infer_types else self.rows
        return pd.DataFrame(data, columns=unique_headers(self.header))

    # ------------------------------------------------------------------ #
    # Dunder niceties
    # ------------------------------------------------------------------ #

    def __str__(self) -> str:
        return self.to_markdown()

    def __repr__(self) -> str:
        return f"Table(ncols={self.ncols}, nrows={self.nrows}, header={self.header!r})"


def _iter_str(cells: Iterable[Any]) -> List[str]:
    return [stringify(c) for c in cells]
