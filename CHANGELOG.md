# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- CLI: redirected stdout (`tablemd x.md > out.csv`, pipes) now always uses
  `\n` line endings, so the bytes match `-o out.csv` on Windows too
  (previously Windows emitted `\r\n`).

### Changed

- CI: bumped `actions/checkout`, `actions/setup-python`,
  `actions/upload-artifact` and `actions/download-artifact` to their current
  major versions (removes the Node.js 20 deprecation warning).

## [0.1.0] - 2026-10-01

Initial release.

### Added

- GFM Markdown table parser: `parse()`, `parse_one()`, escaped pipes,
  alignment row, ragged rows, blockquoted/indented tables, fenced code blocks
  skipped, several tables per document.
- `Table` model with `to_csv`, `to_tsv`, `to_json` (records / split),
  `to_xlsx`, `to_html`, `to_markdown` (CJK-aware alignment), `to_dicts`,
  `to_dataframe`, and `plain()` to strip inline formatting.
- Reverse constructors `from_csv`, `from_json`, `from_records`, `from_rows`,
  `from_dataframe` and file readers `read_csv`, `read_json`, `read_xlsx`,
  `read_markdown`, `read`.
- Conservative type inference for JSON/Excel output (thousands separators,
  leading-zero identifiers and 16+-digit numbers preserved as text).
- `tablemd` CLI with format inference, `--all`, `--list`, `--plain`,
  clipboard input (`-c`) and output (`--copy`), Excel sheet selection.
- Dependency-free clipboard support for macOS, Windows, Linux and WSL.
