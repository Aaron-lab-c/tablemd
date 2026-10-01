"""Parsing GitHub-Flavored-Markdown tables out of arbitrary Markdown text."""

from __future__ import annotations

import re
from typing import List, Optional

from ._table import Alignment, Table, TablemdError

__all__ = ["parse", "parse_one", "split_row", "is_delimiter_row"]

_DELIM_CELL_RE = re.compile(r"^:?-+:?$")
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")
_BLOCKQUOTE_RE = re.compile(r"^(?:>\s?)+")


def _strip_prefix(line: str) -> str:
    """Remove indentation and blockquote markers so quoted/indented tables are found too."""
    line = line.strip()
    return _BLOCKQUOTE_RE.sub("", line).strip()


def split_row(line: str) -> List[str]:
    """Split one table line into stripped cell strings.

    Follows the GFM rules: optional leading/trailing pipes, ``\\|`` is a
    literal pipe, ``\\\\`` is a literal backslash (both are unescaped in the
    result). Pipes inside backticks still separate cells (as in GFM) unless
    escaped.
    """
    cells: List[str] = []
    buf: List[str] = []
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "\\" and i + 1 < n:
            nxt = line[i + 1]
            if nxt == "|":
                buf.append("|")
                i += 2
                continue
            if nxt == "\\":
                buf.append("\\")
                i += 2
                continue
            buf.append(ch)
            i += 1
            continue
        if ch == "|":
            cells.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    cells.append("".join(buf))

    # Leading pipe produces an empty first cell; trailing pipe an empty last cell.
    if cells and cells[0].strip() == "" and line.lstrip().startswith("|"):
        cells.pop(0)
    if cells and cells[-1].strip() == "" and _ends_with_unescaped_pipe(line):
        cells.pop()
    return [c.strip() for c in cells]


def _ends_with_unescaped_pipe(line: str) -> bool:
    stripped = line.rstrip()
    if not stripped.endswith("|"):
        return False
    # Count the run of backslashes before the final pipe.
    j = len(stripped) - 2
    backslashes = 0
    while j >= 0 and stripped[j] == "\\":
        backslashes += 1
        j -= 1
    return backslashes % 2 == 0


def is_delimiter_row(line: str) -> Optional[List[Alignment]]:
    """If *line* is a GFM delimiter row (``| --- | :-: |``) return its alignments, else ``None``."""
    if "|" not in line or "-" not in line:
        return None
    cells = split_row(line)
    if not cells:
        return None
    aligns: List[Alignment] = []
    for cell in cells:
        if not _DELIM_CELL_RE.match(cell):
            return None
        left = cell.startswith(":")
        right = cell.endswith(":")
        if left and right:
            aligns.append("center")
        elif right:
            aligns.append("right")
        elif left:
            aligns.append("left")
        else:
            aligns.append(None)
    return aligns


def _is_table_row(line: str) -> bool:
    return "|" in line


def parse(text: str, *, plain: bool = False) -> List[Table]:
    """Find every Markdown table in *text* and return them in document order.

    A table is a header line containing ``|`` followed by a delimiter row; it
    ends at the first blank line or the first line without a pipe. Tables
    inside fenced code blocks are ignored; blockquoted (``> | a |``) and
    indented tables are recognised. With ``plain=True`` inline formatting is
    stripped from every cell (see :meth:`Table.plain`).
    """
    text = text.lstrip("﻿")  # UTF-8 BOM from Windows editors / stdin
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    tables: List[Table] = []
    i = 0
    n = len(lines)
    fence: Optional[str] = None

    while i < n:
        raw = lines[i]
        line = _strip_prefix(raw)

        fence_match = _FENCE_RE.match(line)
        if fence is not None:
            if fence_match and fence_match.group(1)[0] == fence[0] and len(fence_match.group(1)) >= len(fence):
                fence = None
            i += 1
            continue
        if fence_match:
            fence = fence_match.group(1)
            i += 1
            continue

        if _is_table_row(line) and i + 1 < n:
            aligns = is_delimiter_row(_strip_prefix(lines[i + 1]))
            if aligns is not None:
                header = split_row(line)
                ncols = max(len(header), len(aligns))
                header = header + [""] * (ncols - len(header))
                aligns = aligns + [None] * (ncols - len(aligns))
                rows: List[List[str]] = []
                j = i + 2
                while j < n:
                    body_line = _strip_prefix(lines[j])
                    if body_line == "" or not _is_table_row(body_line) or _FENCE_RE.match(body_line):
                        break
                    rows.append(split_row(body_line))
                    j += 1
                table = Table(header=header, rows=rows, align=aligns)
                tables.append(table.plain() if plain else table)
                i = j
                continue
        i += 1
    return tables


def parse_one(text: str, *, index: int = 0, plain: bool = False) -> Table:
    """Return the table at 0-based *index* in *text*, raising :class:`TablemdError` if absent."""
    tables = parse(text, plain=plain)
    if not tables:
        raise TablemdError("no Markdown table found in input")
    try:
        return tables[index]
    except IndexError as exc:
        raise TablemdError(
            f"input has {len(tables)} table(s); table index {index} is out of range"
        ) from exc
