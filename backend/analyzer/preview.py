"""Parse the first rows of an uploaded CSV for the column-mapping step."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

PREVIEW_ROWS = 20
PREVIEW_BYTES = 256 * 1024


class PreviewError(ValueError):
    pass


@dataclass
class Preview:
    columns: list[str]
    rows: list[list[str]]


def parse_preview(data: bytes, truncated: bool) -> Preview:
    """``data`` is the start of the file; ``truncated`` says whether more bytes follow it.
    A truncated chunk can end mid-line (or mid-character), so its last partial line is dropped before decoding."""
    if truncated:
        cut = data.rfind(b"\n")
        if cut < 0:
            raise PreviewError("The first 256 KB contain no complete line. Is this a CSV file?")
        data = data[: cut + 1]
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise PreviewError(f"The file is not UTF-8 text (bad byte at position {e.start}). Save it as UTF-8 CSV.") from e
    if "\x00" in text:
        raise PreviewError("The file contains NUL bytes; it looks binary, not CSV.")
    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        header = next(reader, None)
        rows = []
        for row in reader:
            if not row:
                continue
            rows.append(row)
            if len(rows) == PREVIEW_ROWS:
                break
    except csv.Error as e:
        raise PreviewError(f"Could not parse the CSV: {e}.") from e
    if not header or all(not h.strip() for h in header):
        raise PreviewError("The file has no header row.")
    columns = [h.strip() for h in header]
    if len(columns) < 2:
        raise PreviewError("The CSV needs at least 2 columns (a variant column and a metric column).")
    if len(set(columns)) != len(columns):
        raise PreviewError("Column names in the header must be unique.")
    for i, row in enumerate(rows, start=2):
        if len(row) != len(columns):
            raise PreviewError(f"Row {i} has {len(row)} fields but the header has {len(columns)}.")
    if not rows:
        raise PreviewError("The CSV has a header but no data rows.")
    return Preview(columns=columns, rows=rows)
