"""Command-line interface: ``tablemd``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional, Sequence

from . import __version__
from ._convert import FORMATS, convert
from ._io import format_from_path, from_csv, from_json, read_xlsx
from ._parse import parse
from ._table import Table, TablemdError

__all__ = ["main", "build_parser"]

_EPILOG = """\
examples:
  tablemd notes.md                      first table in notes.md -> CSV on stdout
  tablemd notes.md -o data.xlsx         first table -> Excel (pip install tablemd[xlsx])
  tablemd notes.md --all -o data.xlsx   every table -> one sheet each
  tablemd notes.md -n 2 -t json         second table -> JSON
  tablemd notes.md --list               show the tables found
  tablemd -c --copy                     clipboard Markdown -> clipboard CSV
  tablemd -c -o out.xlsx --plain        clipboard -> Excel, **bold** etc. stripped
  tablemd data.csv                      CSV -> aligned Markdown table
  tablemd messy.md -t md                re-align an untidy Markdown table
  cat report.md | tablemd -t tsv        works in pipes too
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tablemd",
        description="Convert Markdown tables to CSV / TSV / JSON / Excel and back.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "input",
        nargs="?",
        metavar="INPUT",
        help="input file (.md/.csv/.tsv/.json/.xlsx); '-' or omitted reads stdin",
    )
    p.add_argument("-o", "--output", metavar="FILE", help="write here instead of stdout; format inferred from extension")
    p.add_argument("-t", "--to", choices=FORMATS, help="output format (default: csv for Markdown input, md otherwise)")
    p.add_argument("-f", "--from", dest="from_", choices=("md", "csv", "tsv", "json", "xlsx"), help="input format (default: inferred)")

    sel = p.add_mutually_exclusive_group()
    sel.add_argument("-n", "--table", type=int, default=1, metavar="N", help="which table to convert, 1-based (default: 1)")
    sel.add_argument("-a", "--all", action="store_true", help="convert every table found")

    p.add_argument("-l", "--list", action="store_true", help="list the tables found and exit")
    p.add_argument("-p", "--plain", action="store_true", help="strip **bold**, `code`, [links](...) etc. from cells")
    p.add_argument("-c", "--clipboard", action="store_true", help="read input from the clipboard")
    p.add_argument("--copy", action="store_true", help="copy the result to the clipboard (text formats only)")

    fmt = p.add_argument_group("format options")
    fmt.add_argument("-d", "--delimiter", metavar="CHAR", help="CSV delimiter for input and output, e.g. ';' or '\\t' (default: ',')")
    fmt.add_argument("--encoding", default="utf-8", metavar="ENC", help="output text encoding, also used for piped stdout (default: utf-8; use utf-8-sig for Excel-friendly CSV)")
    fmt.add_argument("--input-encoding", default="utf-8-sig", metavar="ENC", help="input text encoding, e.g. cp950 / big5 (default: utf-8-sig)")
    fmt.add_argument("--sheet", metavar="NAME", help="Excel sheet to read (name or 0-based index); with -o FILE.xlsx the name of the single sheet to write")
    fmt.add_argument("--orient", choices=("records", "split"), default="records", help="JSON layout (default: records)")
    fmt.add_argument("--indent", type=int, default=2, metavar="N", help="JSON indentation; 0 for compact (default: 2)")
    fmt.add_argument("--no-infer", action="store_true", help="keep every cell as text in JSON/Excel output")
    fmt.add_argument("--no-pretty", action="store_true", help="do not align columns in Markdown output")

    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    return p


# --------------------------------------------------------------------------- #
# Input handling
# --------------------------------------------------------------------------- #

def _sniff_format(text: str) -> str:
    """Guess whether *text* is Markdown, JSON, TSV or CSV."""
    if parse(text):
        return "md"
    stripped = text.lstrip("﻿").strip()
    if stripped[:1] in ("[", "{"):
        try:
            json.loads(stripped)
            return "json"
        except ValueError:
            pass
    first = next((ln for ln in stripped.splitlines() if ln.strip()), "")
    if "\t" in first:
        return "tsv"
    if "," in first or ";" in first:
        return "csv"
    return "md"


def _load_tables(args: argparse.Namespace) -> "tuple[List[Table], str]":
    from_fmt: Optional[str] = args.from_
    text: Optional[str] = None

    if args.clipboard:
        from ._clipboard import read_clipboard

        text = read_clipboard()
    elif args.input and args.input != "-":
        path = args.input
        if not os.path.exists(path):
            raise TablemdError(f"file not found: {path}")
        if os.path.isdir(path):
            raise TablemdError(f"{path} is a directory, expected a file")
        from_fmt = from_fmt or format_from_path(path)
        if from_fmt == "xlsx":
            sheet = _sheet_selector(args.sheet)
            tables = read_xlsx(path, sheet=sheet)
            if not tables:
                raise TablemdError("workbook has no non-empty sheets")
            return tables, "xlsx"
        with open(path, "r", encoding=args.input_encoding) as fh:
            text = fh.read()
    elif args.input == "-" or not sys.stdin.isatty():
        buffer = getattr(sys.stdin, "buffer", None)
        text = buffer.read().decode(args.input_encoding) if buffer is not None else sys.stdin.read()
    else:
        raise TablemdError(
            "no input given. Pass a file, pipe text into stdin, or use -c to read the clipboard (see --help)"
        )

    assert text is not None
    if from_fmt == "xlsx":
        raise TablemdError("Excel input must be a file path")
    if from_fmt is None:
        from_fmt = _sniff_format(text)

    if from_fmt == "md":
        tables = parse(text)
        if not tables:
            raise TablemdError("no Markdown table found in input")
    elif from_fmt == "csv":
        tables = [from_csv(text, delimiter=args.delimiter)]
    elif from_fmt == "tsv":
        tables = [from_csv(text, delimiter="\t")]
    elif from_fmt == "json":
        tables = [from_json(text)]
    else:  # pragma: no cover - argparse restricts choices
        raise TablemdError(f"unsupported input format {from_fmt!r}")
    return tables, from_fmt


def _sheet_selector(value: Optional[str]):
    # read_xlsx() tries the string as a sheet name first, then as an index.
    return value


def _delimiter(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    mapping = {"\\t": "\t", "tab": "\t", "TAB": "\t"}
    value = mapping.get(value, value)
    if len(value) != 1:
        raise TablemdError("--delimiter must be a single character (use '\\t' for tab)")
    return value


def _check_encoding(name: str, flag: str) -> None:
    import codecs

    try:
        codecs.lookup(name)
    except LookupError as exc:
        raise TablemdError(f"unknown encoding {name!r} for {flag}") from exc


def _list_tables(tables: Sequence[Table]) -> str:
    lines = []
    for i, t in enumerate(tables, start=1):
        head = " | ".join(h.replace("\n", " ") for h in t.header)
        if len(head) > 70:
            head = head[:67] + "..."
        lines.append(f"#{i}  {t.nrows} rows x {t.ncols} cols   {head}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def run(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    _check_encoding(args.encoding, "--encoding")
    _check_encoding(args.input_encoding, "--input-encoding")
    args.delimiter = _delimiter(args.delimiter)
    _configure_stdout(args.encoding)

    tables, in_fmt = _load_tables(args)
    if args.plain:
        tables = [t.plain() for t in tables]

    if args.list:
        print(_list_tables(tables))
        return 0

    to = args.to or (format_from_path(args.output) if args.output else None)
    if to is None:
        to = "csv" if in_fmt == "md" else "md"
    if to == "xlsx" and not args.output:
        raise TablemdError("Excel output needs -o FILE.xlsx")
    if to == "xlsx" and args.copy:
        raise TablemdError("--copy only works with text formats (csv, tsv, json, md, html)")

    if args.table < 1:
        raise TablemdError("--table is 1-based; use 1 for the first table")
    if not args.all and args.table > len(tables):
        raise TablemdError(f"input has {len(tables)} table(s); --table {args.table} is out of range")
    index: Optional[int] = None if args.all else args.table - 1

    sheet_names = [args.sheet] if (args.sheet and not args.all and in_fmt != "xlsx") else None
    indent = None if args.indent is not None and args.indent <= 0 else args.indent

    result = convert(
        tables,
        to,
        args.output,
        table=index,
        delimiter=args.delimiter,
        encoding=args.encoding,
        indent=indent,
        orient=args.orient,
        infer_types=not args.no_infer,
        pretty=not args.no_pretty,
        sheet_names=sheet_names,
    )

    if args.copy:
        from ._clipboard import write_clipboard

        if result is None:
            # Output went to a file; re-render for the clipboard.
            result = convert(
                tables, to, None, table=index, delimiter=args.delimiter, indent=indent,
                orient=args.orient, infer_types=not args.no_infer, pretty=not args.no_pretty,
            )
        write_clipboard(result or "")
        count = len(tables) if args.all else 1
        print(f"tablemd: copied {count} table(s) as {to} to the clipboard", file=sys.stderr)
    elif result is not None:
        sys.stdout.write(result)
        if not result.endswith("\n"):
            sys.stdout.write("\n")
        sys.stdout.flush()
    return 0


def _configure_stdout(encoding: str) -> None:
    """When stdout is a pipe or file, emit UTF-8 (or --encoding) with ``\n`` line endings.

    Interactive consoles are left alone: Python already handles Unicode there
    (on Windows through the UTF-16 console API). A redirected stdout, however,
    would otherwise use the locale codec (crashing on the first CJK character
    on a cp950/cp1252 system) and, on Windows, translate ``\n`` to ``\r\n``.
    Fixing both makes ``tablemd x.md > out.csv`` byte-identical to
    ``tablemd x.md -o out.csv`` on every platform.
    """
    stream = sys.stdout
    try:
        if stream.isatty():
            return
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding=encoding, errors="replace", newline="\n")
    except (AttributeError, ValueError, OSError):  # pragma: no cover - exotic streams
        pass


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Console-script entry point. Returns the process exit code."""
    try:
        return run(argv)
    except TablemdError as exc:
        print(f"tablemd: error: {exc}", file=sys.stderr)
        return 1
    except BrokenPipeError:  # pragma: no cover - e.g. `tablemd x.md | head`
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 0
    except KeyboardInterrupt:  # pragma: no cover
        return 130
    except UnicodeDecodeError as exc:
        print(
            f"tablemd: error: could not decode input as {exc.encoding}: {exc.reason} "
            f"(try --input-encoding cp950, big5, utf-16 ...)",
            file=sys.stderr,
        )
        return 1
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"tablemd: error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - last resort, keep the traceback out of users' faces
        if os.environ.get("TABLEMD_DEBUG"):
            raise
        print(f"tablemd: error: unexpected {type(exc).__name__}: {exc} (set TABLEMD_DEBUG=1 for a traceback)", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
