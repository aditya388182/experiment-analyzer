import pytest

from analyzer.preview import PreviewError, parse_preview


def test_truncated_chunk_drops_partial_last_line_and_split_utf8():
    data = "v,m\nA,1\nB,2\nC,é".encode()[:-1]  # cut inside the 2-byte 'é'
    p = parse_preview(data, truncated=True)
    assert p.rows == [["A", "1"], ["B", "2"]]


def test_bom_and_crlf_are_handled():
    p = parse_preview("﻿v,m\r\nA,1\r\n".encode(), truncated=False)
    assert p.columns == ["v", "m"] and p.rows == [["A", "1"]]


def test_quoted_fields():
    p = parse_preview(b'v,m\n"A, with comma",1\n', truncated=False)
    assert p.rows == [["A, with comma", "1"]]


def test_truncated_without_newline_fails():
    with pytest.raises(PreviewError):
        parse_preview(b"x" * 100, truncated=True)
